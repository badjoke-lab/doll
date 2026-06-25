from __future__ import annotations

import hashlib
import json
import zipfile
from dataclasses import replace
from pathlib import Path
from typing import cast
from uuid import uuid4

import pytest

import doll.state_package as package
from doll import state, workspace
from doll.backup import create_state_backup, verify_backup
from doll.procedure import (
    MAX_LIST_LIMIT,
    ProcedureCorruptError,
    ProcedureService,
    ProcedureValidationError,
    _procedure_from_record,
)
from doll.project_state import ProjectService
from doll.state import StaleRevisionError
from doll.state_package_registry import get_authoritative_record_registry
from doll.state_repository import StateRepository
from doll.trust import ClaimEvidenceTrustService, TruthSource


def _workspace(tmp_path: Path, name: str = "workspace") -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(tmp_path / name)
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def _project(repository: StateRepository, name: str = "Project") -> str:
    return ProjectService(repository).create_v2(
        name=name,
        description="Synthetic ProcedureRecord project.",
        objective="Preserve inspectable methods without granting authority.",
        in_scope=("ProcedureRecord",),
        out_of_scope=("Procedure execution",),
        success_criteria=("Accepted procedures remain inspectable",),
        project_status="active",
        started_at="2026-06-25T00:00:00Z",
    ).project_id


def _complete_values() -> dict[str, object]:
    return {
        "prerequisites": ("A writable local workspace exists.",),
        "ordered_steps": (
            "Inspect the current authoritative project state.",
            "Apply the bounded change through the trusted management path.",
        ),
        "required_capability_ids": ("workspace.read", "workspace.write"),
        "expected_outputs": ("One validated authoritative record update.",),
        "validation_steps": ("Run the relevant deterministic validation suite.",),
        "rollback_steps": ("Restore the prior accepted record revision.",),
        "platform_constraints": ("Use a supported local Doll workspace.",),
    }


def _evidence(repository: StateRepository) -> str:
    truth = ClaimEvidenceTrustService(repository)
    source = TruthSource(
        origin_type="user_statement",
        creator_actor_type="user",
    )
    claim = truth.create_claim(
        title="Procedure verification claim",
        statement="The synthetic procedure validation passed.",
        source=source,
    )
    evidence = truth.create_evidence(
        title="Procedure verification evidence",
        summary="Synthetic record evidence for procedure verification.",
        evidence_type="record",
        source=source,
        supports_claim_ids=(claim.record_id,),
    )
    return evidence.record_id


def _read_members(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path, "r") as archive:
        return {info.filename: archive.read(info) for info in archive.infolist()}


def _write_members(path: Path, members: dict[str, bytes]) -> None:
    updated = dict(members)
    checksum_name = f"{package.PACKAGE_ROOT}/checksums.json"
    updated.pop(checksum_name, None)
    updated[checksum_name] = package._json_bytes(
        {
            "algorithm": package.CHECKSUM_ALGORITHM,
            "entries": [
                {
                    "path": name,
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "size_bytes": len(content),
                }
                for name, content in sorted(updated.items())
            ],
        }
    )
    package._write_deterministic_zip(path, updated)


def test_untrusted_draft_requires_trusted_completion_and_approval(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_id = _project(repository)
        service = ProcedureService(repository)
        draft = service.create_draft(
            project_id=project_id,
            title="Imported recovery method",
            purpose="Preserve imported method text as an unapproved draft.",
            version=1,
            actor_type="model",
        )
        assert draft.procedure_status == "draft"
        assert draft.provenance == "model-proposed"

        with pytest.raises(ProcedureValidationError):
            service.approve(
                draft.procedure_id,
                expected_revision=draft.revision,
                actor_type="model",
            )
        with pytest.raises(ProcedureValidationError):
            service.approve(
                draft.procedure_id,
                expected_revision=draft.revision,
            )

        completed = service.update_draft(
            draft.procedure_id,
            expected_revision=draft.revision,
            title=draft.title,
            purpose=draft.purpose,
            version=1,
            **_complete_values(),
        )
        approved = service.approve(
            completed.procedure_id,
            expected_revision=completed.revision,
            approved_at="2026-06-25T01:00:00Z",
        )

    assert approved.procedure_status == "approved"
    assert approved.provenance == "user-confirmed"
    assert approved.approved_at == "2026-06-25T01:00:00Z"


def test_lifecycle_revision_verification_and_archive(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_id = _project(repository)
        service = ProcedureService(repository)
        approved = service.create_approved(
            project_id=project_id,
            title="Validated local update",
            purpose="Apply one bounded local update.",
            version=1,
            approved_at="2026-06-25T01:00:00Z",
            **_complete_values(),
        )
        evidence_id = _evidence(repository)
        verified = service.verify(
            approved.procedure_id,
            expected_revision=approved.revision,
            verified_at="2026-06-25T02:00:00Z",
            evidence_ids=(evidence_id,),
        )

        with pytest.raises(StaleRevisionError):
            service.deprecate(
                approved.procedure_id,
                expected_revision=approved.revision,
            )

        deprecated = service.deprecate(
            verified.procedure_id,
            expected_revision=verified.revision,
        )
        archived = service.archive(
            deprecated.procedure_id,
            expected_revision=deprecated.revision,
        )

    assert verified.last_verified_at == "2026-06-25T02:00:00Z"
    assert verified.verification_evidence_ids == (evidence_id,)
    assert deprecated.procedure_status == "deprecated"
    assert archived.procedure_status == "deprecated"
    assert archived.lifecycle_status == "archived"


def test_supersession_preserves_prior_procedure(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_id = _project(repository)
        service = ProcedureService(repository)
        original = service.create_approved(
            project_id=project_id,
            title="Original procedure",
            purpose="Original accepted method.",
            version=1,
            **_complete_values(),
        )
        replacement = service.create_approved(
            project_id=project_id,
            title="Replacement procedure",
            purpose="Replacement accepted method.",
            version=2,
            supersedes_id=original.procedure_id,
            **_complete_values(),
        )
        superseded = service.supersede(
            original.procedure_id,
            replacement_id=replacement.procedure_id,
            expected_revision=original.revision,
        )
        restored_original = service.get(original.procedure_id)

    assert superseded.procedure_status == "superseded"
    assert superseded.superseded_by_id == replacement.procedure_id
    assert restored_original == superseded
    assert replacement.supersedes_id == original.procedure_id


def test_supersession_rejects_self_cross_project_and_bad_versions(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        first_project = _project(repository, "First")
        second_project = _project(repository, "Second")
        service = ProcedureService(repository)
        original = service.create_approved(
            project_id=first_project,
            title="Original",
            purpose="Original procedure.",
            version=2,
            **_complete_values(),
        )
        cross_project = service.create_approved(
            project_id=second_project,
            title="Cross-project replacement",
            purpose="Invalid replacement project.",
            version=3,
            **_complete_values(),
        )
        with pytest.raises(ProcedureValidationError):
            service.supersede(
                original.procedure_id,
                replacement_id=cross_project.procedure_id,
                expected_revision=original.revision,
            )
        with pytest.raises(ProcedureValidationError):
            service.create_draft(
                project_id=first_project,
                title="Self-link fixture",
                purpose="The public service generates its own ID, so a missing predecessor fails.",
                version=3,
                supersedes_id=str(uuid4()),
            )
        lower = service.create_approved(
            project_id=first_project,
            title="Lower version",
            purpose="Not a valid replacement.",
            version=1,
            **_complete_values(),
        )
        with pytest.raises(ProcedureValidationError):
            service.supersede(
                original.procedure_id,
                replacement_id=lower.procedure_id,
                expected_revision=original.revision,
            )


def test_capability_references_do_not_grant_authority(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_id = _project(repository)
        before_permissions = cast(
            int,
            repository.connection.execute(
                "SELECT COUNT(*) FROM records WHERE record_type = 'permission'"
            ).fetchone()[0],
        )
        procedure = ProcedureService(repository).create_approved(
            project_id=project_id,
            title="Capability reference only",
            purpose="Document required capabilities without granting them.",
            version=1,
            required_capability_ids=("network.http", "workspace.write"),
            ordered_steps=("Describe the intended bounded operation.",),
            validation_steps=("Validate without executing a capability.",),
            rollback_steps=("No execution occurred; preserve prior state.",),
        )
        after_permissions = cast(
            int,
            repository.connection.execute(
                "SELECT COUNT(*) FROM records WHERE record_type = 'permission'"
            ).fetchone()[0],
        )

    assert procedure.required_capability_ids == ("network.http", "workspace.write")
    assert before_permissions == after_permissions == 0


def test_deterministic_export_and_package_backup_transfer(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_id = _project(repository)
        procedure = ProcedureService(repository).create_approved(
            project_id=project_id,
            title="Transfer procedure",
            purpose="Survive deterministic state transfer.",
            version=1,
            **_complete_values(),
        )
        service = ProcedureService(repository)
        assert service.export_json(procedure.procedure_id) == service.export_json(
            procedure.procedure_id
        )

    output = tmp_path / "state.zip"
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        package.export_state_package(
            repository,
            output,
            exported_at="2026-06-25T03:00:00Z",
        )
    inspection = package.verify_state_package(output)
    assert inspection.record_counts["procedure"] == 1

    target = tmp_path / "imported"
    package.import_state_package(output, target)
    with state.open_state_repository(target, read_only=True) as repository:
        imported = ProcedureService(repository).get(procedure.procedure_id)
    assert imported == procedure

    backup_path = tmp_path / "backup.zip"
    create_state_backup(
        initialized.root,
        backup_path,
        created_at="2026-06-25T04:00:00Z",
    )
    verify_backup(backup_path)
    with zipfile.ZipFile(backup_path, "r") as archive:
        nested = archive.read("doll-backup/payload/state-package.zip")
    nested_path = tmp_path / "nested.zip"
    nested_path.write_bytes(nested)
    assert package.verify_state_package(nested_path).record_counts["procedure"] == 1


def test_procedure_registry_is_package_v2_only() -> None:
    version_one = get_authoritative_record_registry(1)
    version_two = get_authoritative_record_registry(2)
    assert "procedure" not in version_one.record_types
    assert "procedure" in version_two.record_types
    assert version_two.by_record_type["procedure"].member_path == "records/procedures.jsonl"


def test_hostile_package_procedure_project_link_fails_before_mutation(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_id = _project(repository)
        procedure = ProcedureService(repository).create_approved(
            project_id=project_id,
            title="Hostile fixture",
            purpose="Detect a tampered project relation.",
            version=1,
            **_complete_values(),
        )
    source = tmp_path / "source.zip"
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        package.export_state_package(
            repository,
            source,
            exported_at="2026-06-25T05:00:00Z",
        )
    members = _read_members(source)
    member_name = f"{package.PACKAGE_ROOT}/records/procedures.jsonl"
    payload = json.loads(members[member_name].decode("utf-8").strip())
    assert payload["id"] == procedure.procedure_id
    payload["metadata"]["project_id"] = str(uuid4())
    members[member_name] = package._json_bytes(payload)
    hostile = tmp_path / "hostile.zip"
    _write_members(hostile, members)

    target = tmp_path / "target"
    target.mkdir()
    marker = target / "marker.txt"
    marker.write_text("unchanged", encoding="utf-8")
    with pytest.raises(package.StatePackageValidationError):
        package.import_state_package(hostile, target)
    assert marker.read_text(encoding="utf-8") == "unchanged"


def test_malformed_accepted_procedure_and_list_guards(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_id = _project(repository)
        service = ProcedureService(repository)
        draft = service.create_draft(
            project_id=project_id,
            title="Malformed fixture",
            purpose="Synthetic malformed accepted procedure.",
            version=1,
            actor_type="model",
            **_complete_values(),
        )
        record = repository.get_record(draft.procedure_id)
        metadata = dict(record.metadata)
        metadata["status"] = "approved"
        metadata["approved_at"] = "2026-06-25T01:00:00Z"
        corrupt = replace(record, metadata=metadata)
        with pytest.raises(ProcedureCorruptError):
            _procedure_from_record(corrupt)

        for invalid_limit in (0, MAX_LIST_LIMIT + 1, True):
            with pytest.raises(ProcedureValidationError):
                service.list(limit=invalid_limit)
