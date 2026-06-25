from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path
from typing import cast

import pytest

import doll.state_package as package
from doll import state, workspace
from doll.backup import create_state_backup, verify_backup
from doll.project_state import DecisionService, ProjectService
from doll.state import StaleRevisionError
from doll.state_package_registry import get_authoritative_record_registry
from doll.trust import ClaimEvidenceTrustService, TruthSource
from doll.work_item import (
    AcceptanceCriterion,
    WorkItemCorruptError,
    WorkItemService,
    WorkItemValidationError,
    _work_item_from_record,
)


def _initialized_workspace(tmp_path: Path, name: str = "workspace") -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(tmp_path / name)
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def _project(repository: state.StateRepository, name: str = "Project") -> str:
    return ProjectService(repository).create_v2(
        name=name,
        description="Synthetic WorkItemRecord test project.",
        objective="Prove durable bounded work continuity.",
        in_scope=("WorkItemRecord",),
        out_of_scope=("Automatic execution",),
        success_criteria=("Accepted work remains inspectable",),
        project_status="active",
        started_at="2026-06-26T00:00:00Z",
    ).project_id


def _criterion() -> AcceptanceCriterion:
    return AcceptanceCriterion(
        criterion_id="criterion-1",
        description="The accepted result is observable without a model.",
        required_evidence_kind="record",
        blocking=True,
    )


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


def test_trusted_work_item_lifecycle_revision_and_archive(tmp_path: Path) -> None:
    initialized = _initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_id = _project(repository)
        service = WorkItemService(repository)
        item = service.create(
            project_id=project_id,
            kind="task",
            title="Implement bounded work",
            description="Create one accepted unit of project work.",
            acceptance_criteria=(_criterion(),),
        )
        assert item.work_status == "ready"
        assert item.lifecycle_status == "active"

        started = service.transition(
            item.work_item_id,
            expected_revision=item.revision,
            to_status="in_progress",
            occurred_at="2026-06-26T01:00:00Z",
        )
        assert started.started_at == "2026-06-26T01:00:00Z"

        with pytest.raises(StaleRevisionError):
            service.transition(
                item.work_item_id,
                expected_revision=item.revision,
                to_status="cancelled",
            )

        completed = service.transition(
            item.work_item_id,
            expected_revision=started.revision,
            to_status="completed",
            occurred_at="2026-06-26T02:00:00Z",
        )
        archived = service.archive(
            item.work_item_id,
            expected_revision=completed.revision,
        )

    assert completed.work_status == "completed"
    assert completed.completed_at == "2026-06-26T02:00:00Z"
    assert archived.work_status == "completed"
    assert archived.lifecycle_status == "archived"


def test_untrusted_proposal_cannot_promote_complete_or_cancel(tmp_path: Path) -> None:
    initialized = _initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_id = _project(repository)
        service = WorkItemService(repository)
        proposal = service.propose(
            project_id=project_id,
            kind="investigation",
            title="Investigate dependency model",
            description="Untrusted proposal remains unaccepted until user promotion.",
            actor_type="model",
        )
        assert proposal.work_status == "proposed"
        assert proposal.provenance == "model-proposed"

        for target in ("ready", "completed", "cancelled"):
            with pytest.raises(WorkItemValidationError):
                service.transition(
                    proposal.work_item_id,
                    expected_revision=proposal.revision,
                    to_status=cast("str", target),
                    actor_type="model",
                )

        promoted = service.transition(
            proposal.work_item_id,
            expected_revision=proposal.revision,
            to_status="ready",
        )
        assert promoted.work_status == "ready"
        assert promoted.provenance == "user-confirmed"


def test_persisted_untrusted_accepted_state_is_corrupt(tmp_path: Path) -> None:
    initialized = _initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_id = _project(repository)
        proposal = WorkItemService(repository).propose(
            project_id=project_id,
            kind="review",
            title="Untrusted accepted-state fixture",
            description="Synthetic persisted corruption test.",
            actor_type="model",
        )
        record = repository.get_record(proposal.work_item_id)
        metadata = dict(record.metadata)
        metadata["status"] = "ready"
        repository.update_record(
            record.id,
            expected_revision=record.revision,
            metadata=metadata,
        )
        corrupt = repository.get_record(record.id)

        with pytest.raises(WorkItemCorruptError):
            _work_item_from_record(corrupt)


def test_dependency_blocker_scope_and_cycle_integrity(tmp_path: Path) -> None:
    initialized = _initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        first_project = _project(repository, "First")
        second_project = _project(repository, "Second")
        service = WorkItemService(repository)
        first = service.create(
            project_id=first_project,
            kind="task",
            title="First task",
            description="First dependency node.",
        )
        second = service.create(
            project_id=first_project,
            kind="task",
            title="Second task",
            description="Second dependency node.",
        )

        with pytest.raises(WorkItemValidationError):
            service.create(
                project_id=second_project,
                kind="task",
                title="Cross-project dependency",
                description="Must be rejected.",
                depends_on_ids=(first.work_item_id,),
            )
        with pytest.raises(WorkItemValidationError):
            service.transition(
                first.work_item_id,
                expected_revision=first.revision,
                to_status="blocked",
            )
        with pytest.raises(WorkItemValidationError):
            service.update_definition(
                first.work_item_id,
                expected_revision=first.revision,
                title=first.title,
                description=first.description,
                priority=first.priority,
                depends_on_ids=(first.work_item_id,),
                acceptance_criteria=(),
                source_decision_ids=(),
                artifact_ids=(),
                source_ids=(),
            )

        first_updated = service.update_definition(
            first.work_item_id,
            expected_revision=first.revision,
            title=first.title,
            description=first.description,
            priority=first.priority,
            depends_on_ids=(second.work_item_id,),
            acceptance_criteria=(),
            source_decision_ids=(),
            artifact_ids=(),
            source_ids=(),
        )
        with pytest.raises(WorkItemValidationError):
            service.update_definition(
                second.work_item_id,
                expected_revision=second.revision,
                title=second.title,
                description=second.description,
                priority=second.priority,
                depends_on_ids=(first_updated.work_item_id,),
                acceptance_criteria=(),
                source_decision_ids=(),
                artifact_ids=(),
                source_ids=(),
            )

        blocked = service.transition(
            second.work_item_id,
            expected_revision=second.revision,
            to_status="blocked",
            blocked_by_ids=(first_updated.work_item_id,),
        )
        assert blocked.blocked_by_ids == (first_updated.work_item_id,)


def test_verification_decision_links_and_deterministic_export(tmp_path: Path) -> None:
    initialized = _initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_id = _project(repository)
        decision = DecisionService(repository).create(
            decision="Implement WorkItemRecord v1",
            reason="Durable project continuity requires bounded work state.",
            decision_status="accepted",
            decided_at="2026-06-26T00:00:00Z",
            project_id=project_id,
        )
        truth = ClaimEvidenceTrustService(repository)
        source = TruthSource(
            origin_type="user_statement",
            creator_actor_type="user",
        )
        claim = truth.create_claim(
            title="Work item evidence claim",
            statement="The synthetic work-item verification passed.",
            source=source,
        )
        evidence = truth.create_evidence(
            title="Work item verification evidence",
            summary="Synthetic evidence for WorkItemRecord verification.",
            evidence_type="record",
            source=source,
            supports_claim_ids=(claim.record_id,),
        )
        service = WorkItemService(repository)
        item = service.create(
            project_id=project_id,
            kind="milestone",
            title="Verify WorkItemRecord",
            description="Exercise typed decision and evidence links.",
            source_decision_ids=(decision.decision_id,),
            source_ids=(claim.record_id,),
            acceptance_criteria=(_criterion(),),
        )
        verified = service.set_verification(
            item.work_item_id,
            expected_revision=item.revision,
            verification_state="passed",
            evidence_ids=(evidence.record_id,),
        )
        first = service.export_json(item.work_item_id)
        second = service.export_json(item.work_item_id)

    assert verified.verification_state == "passed"
    assert verified.verification_evidence_ids == (evidence.record_id,)
    assert first == second
    payload = json.loads(first)
    assert payload["export_schema"] == "doll.work-item.v1"
    assert payload["record"]["metadata"]["source_decision_ids"] == [decision.decision_id]


def test_work_item_package_transfer_and_state_backup(tmp_path: Path) -> None:
    initialized = _initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_id = _project(repository)
        item = WorkItemService(repository).create(
            project_id=project_id,
            kind="maintenance",
            title="Transfer durable work",
            description="Work item survives package and backup boundaries.",
            acceptance_criteria=(_criterion(),),
        )
    output = tmp_path / "state.zip"
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        package.export_state_package(
            repository,
            output,
            exported_at="2026-06-26T03:00:00Z",
        )
    inspection = package.verify_state_package(output)
    assert inspection.record_counts["work_item"] == 1

    target = tmp_path / "imported"
    package.import_state_package(output, target)
    with state.open_state_repository(target, read_only=True) as repository:
        imported = WorkItemService(repository).get(item.work_item_id)
    assert imported.project_id == project_id
    assert imported.acceptance_criteria == (_criterion(),)

    backup_path = tmp_path / "state-backup.zip"
    create_state_backup(
        initialized.root,
        backup_path,
        created_at="2026-06-26T04:00:00Z",
    )
    verify_backup(backup_path)
    with zipfile.ZipFile(backup_path, "r") as archive:
        nested = archive.read("doll-backup/payload/state-package.zip")
    nested_path = tmp_path / "nested-state.zip"
    nested_path.write_bytes(nested)
    nested_inspection = package.verify_state_package(nested_path)
    assert nested_inspection.record_counts["work_item"] == 1


def test_work_item_registry_is_package_v2_only() -> None:
    version_one = get_authoritative_record_registry(1)
    version_two = get_authoritative_record_registry(2)

    assert "work_item" not in version_one.record_types
    assert version_one.by_record_type.get("work_item") is None
    assert "work_item" in version_two.record_types
    assert version_two.by_record_type["work_item"].member_path == "records/work-items.jsonl"


def test_package_rejects_cross_project_work_item_relation_before_mutation(
    tmp_path: Path,
) -> None:
    initialized = _initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        first_project = _project(repository, "First")
        second_project = _project(repository, "Second")
        service = WorkItemService(repository)
        dependency = service.create(
            project_id=first_project,
            kind="task",
            title="Dependency",
            description="Valid dependency before tampering.",
        )
        dependent = service.create(
            project_id=first_project,
            kind="task",
            title="Dependent",
            description="Will be tampered into a cross-project relation.",
            depends_on_ids=(dependency.work_item_id,),
        )
    source = tmp_path / "source.zip"
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        package.export_state_package(
            repository,
            source,
            exported_at="2026-06-26T05:00:00Z",
        )

    members = _read_members(source)
    member_name = f"{package.PACKAGE_ROOT}/records/work-items.jsonl"
    payloads = [json.loads(line) for line in members[member_name].decode("utf-8").splitlines()]
    for payload in payloads:
        if payload["id"] == dependent.work_item_id:
            payload["metadata"]["project_id"] = second_project
    members[member_name] = b"".join(package._json_bytes(payload) for payload in payloads)
    hostile = tmp_path / "hostile.zip"
    _write_members(hostile, members)

    target = tmp_path / "target"
    target.mkdir()
    marker = target / "marker.txt"
    marker.write_text("unchanged", encoding="utf-8")
    with pytest.raises(package.StatePackageValidationError):
        package.import_state_package(hostile, target)
    assert marker.read_text(encoding="utf-8") == "unchanged"
