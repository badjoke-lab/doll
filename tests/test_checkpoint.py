from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import cast
from uuid import uuid4

import pytest

import doll.state_package as package
from doll import state, workspace
from doll.backup import create_state_backup, verify_backup
from doll.checkpoint import (
    CheckpointCorruptError,
    CheckpointValidationError,
    ProjectCheckpointService,
    _checkpoint_from_record,
)
from doll.project_state import ProjectService
from doll.settings import PreferenceService
from doll.state import StaleRevisionError
from doll.state_package_registry import get_authoritative_record_registry
from doll.state_repository import StateRepository
from doll.work_item import WorkItemService


def _workspace(tmp_path: Path, name: str = "workspace") -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(tmp_path / name)
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def _project(repository: StateRepository) -> str:
    return ProjectService(repository).create_v2(
        name="Checkpoint project",
        description="Synthetic ProjectCheckpointRecord project.",
        objective="Preserve an explicit confirmed project position.",
        in_scope=("Checkpoint continuity",),
        out_of_scope=("Derived project status",),
        success_criteria=("Relevant changes make the checkpoint stale",),
        project_status="active",
        started_at="2026-06-25T00:00:00Z",
    ).project_id


def _work_items(repository: StateRepository, project_id: str) -> dict[str, str]:
    service = WorkItemService(repository)
    active = service.create(
        project_id=project_id,
        kind="task",
        title="Active work",
        description="Current in-progress work.",
    )
    active = service.transition(
        active.work_item_id,
        expected_revision=active.revision,
        to_status="in_progress",
        occurred_at="2026-06-25T01:00:00Z",
    )
    next_item = service.create(
        project_id=project_id,
        kind="task",
        title="Next work",
        description="Accepted ready work.",
    )
    blocker = service.create(
        project_id=project_id,
        kind="task",
        title="Blocker",
        description="Current blocker work.",
    )
    blocked = service.create(
        project_id=project_id,
        kind="task",
        title="Blocked work",
        description="Work currently blocked.",
    )
    blocked = service.transition(
        blocked.work_item_id,
        expected_revision=blocked.revision,
        to_status="blocked",
        blocked_by_ids=(blocker.work_item_id,),
    )
    milestone = service.create(
        project_id=project_id,
        kind="milestone",
        title="Completed milestone",
        description="Completed checkpoint milestone.",
    )
    milestone = service.transition(
        milestone.work_item_id,
        expected_revision=milestone.revision,
        to_status="in_progress",
        occurred_at="2026-06-25T01:00:00Z",
    )
    milestone = service.transition(
        milestone.work_item_id,
        expected_revision=milestone.revision,
        to_status="completed",
        occurred_at="2026-06-25T02:00:00Z",
    )
    return {
        "active": active.work_item_id,
        "next": next_item.work_item_id,
        "blocked": blocked.work_item_id,
        "blocker": blocker.work_item_id,
        "milestone": milestone.work_item_id,
    }


def _propose(
    repository: StateRepository,
    project_id: str,
    items: dict[str, str],
    *,
    basis_record_ids: tuple[str, ...] = (),
):
    return ProjectCheckpointService(repository).propose(
        project_id=project_id,
        as_of="2026-06-25T03:00:00Z",
        summary="Phase 4B checkpoint with explicit bounded work state.",
        current_phase="Phase 4B",
        current_goal="Complete model-independent project continuity records.",
        active_work_item_ids=(items["active"],),
        next_work_item_ids=(items["next"],),
        blocked_work_item_ids=(items["blocked"],),
        completed_milestone_ids=(items["milestone"],),
        required_validation_ids=(items["blocker"],),
        basis_record_ids=basis_record_ids,
        actor_type="model",
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


def test_user_confirmation_captures_deterministic_basis(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_id = _project(repository)
        items = _work_items(repository, project_id)
        additional = PreferenceService(repository).create(
            key="checkpoint.basis",
            value={"enabled": True},
        )
        service = ProjectCheckpointService(repository)
        proposed = _propose(
            repository,
            project_id,
            items,
            basis_record_ids=(additional.record_id,),
        )
        assert proposed.confirmation_state == "proposed"
        assert proposed.basis_fingerprint is None
        assert proposed.freshness is None

        with pytest.raises(CheckpointValidationError):
            service.confirm(
                proposed.checkpoint_id,
                expected_revision=proposed.revision,
                actor_type="model",
            )

        confirmed = service.confirm(
            proposed.checkpoint_id,
            expected_revision=proposed.revision,
        )
        exported_once = service.export_json(confirmed.checkpoint_id)
        exported_twice = service.export_json(confirmed.checkpoint_id)

    assert confirmed.confirmation_state == "confirmed"
    assert confirmed.confirmed_by == "user"
    assert confirmed.freshness == "current"
    assert confirmed.basis_fingerprint is not None
    assert confirmed.basis_fingerprint.startswith("sha256:")
    assert tuple(record_id for record_id, _ in confirmed.basis_record_revisions) == tuple(
        sorted(record_id for record_id, _ in confirmed.basis_record_revisions)
    )
    assert exported_once == exported_twice


def test_relevant_change_stales_but_unrelated_change_does_not(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_id = _project(repository)
        items = _work_items(repository, project_id)
        service = ProjectCheckpointService(repository)
        proposed = _propose(repository, project_id, items)
        confirmed = service.confirm(
            proposed.checkpoint_id,
            expected_revision=proposed.revision,
        )

        PreferenceService(repository).create(
            key="checkpoint.unrelated",
            value="does not stale checkpoint",
        )
        assert service.get(confirmed.checkpoint_id).freshness == "current"

        active = WorkItemService(repository).get(items["active"])
        WorkItemService(repository).update_definition(
            active.work_item_id,
            expected_revision=active.revision,
            title=active.title,
            description="Relevant work-item revision changed.",
            priority=active.priority,
            depends_on_ids=active.depends_on_ids,
            acceptance_criteria=active.acceptance_criteria,
            source_decision_ids=active.source_decision_ids,
            artifact_ids=active.artifact_ids,
            source_ids=active.source_ids,
        )
        stale = service.get(confirmed.checkpoint_id)

    assert stale.freshness == "stale"
    assert stale.basis_fingerprint == confirmed.basis_fingerprint


def test_missing_basis_record_makes_checkpoint_stale_not_corrupt(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_id = _project(repository)
        items = _work_items(repository, project_id)
        service = ProjectCheckpointService(repository)
        proposed = _propose(repository, project_id, items)
        confirmed = service.confirm(
            proposed.checkpoint_id,
            expected_revision=proposed.revision,
        )
        repository.connection.execute(
            "DELETE FROM records WHERE id = ?",
            (items["blocker"],),
        )
        missing = service.get(confirmed.checkpoint_id)

    assert missing.confirmation_state == "confirmed"
    assert missing.freshness == "stale"


def test_superseded_checkpoint_remains_inspectable(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_id = _project(repository)
        items = _work_items(repository, project_id)
        service = ProjectCheckpointService(repository)
        proposed = _propose(repository, project_id, items)
        confirmed = service.confirm(
            proposed.checkpoint_id,
            expected_revision=proposed.revision,
        )
        superseded = service.supersede(
            confirmed.checkpoint_id,
            expected_revision=confirmed.revision,
        )
        inspected = service.get(confirmed.checkpoint_id)

    assert superseded.confirmation_state == "superseded"
    assert superseded.freshness == "superseded"
    assert inspected == superseded


def test_stale_revision_and_invalid_work_item_roles_fail(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_id = _project(repository)
        items = _work_items(repository, project_id)
        service = ProjectCheckpointService(repository)
        proposed = _propose(repository, project_id, items)
        confirmed = service.confirm(
            proposed.checkpoint_id,
            expected_revision=proposed.revision,
        )
        with pytest.raises(StaleRevisionError):
            service.supersede(
                confirmed.checkpoint_id,
                expected_revision=proposed.revision,
            )
        with pytest.raises(CheckpointValidationError):
            service.propose(
                project_id=project_id,
                as_of="2026-06-25T03:00:00Z",
                summary="Invalid role overlap.",
                current_phase="Phase",
                current_goal="Goal",
                active_work_item_ids=(items["active"],),
                next_work_item_ids=(items["active"],),
            )
        with pytest.raises(CheckpointValidationError):
            service.propose(
                project_id=project_id,
                as_of="2026-06-25T03:00:00Z",
                summary="Wrong work-item state.",
                current_phase="Phase",
                current_goal="Goal",
                active_work_item_ids=(items["next"],),
            )


def test_checkpoint_package_transfer_and_backup(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_id = _project(repository)
        items = _work_items(repository, project_id)
        service = ProjectCheckpointService(repository)
        proposed = _propose(repository, project_id, items)
        confirmed = service.confirm(
            proposed.checkpoint_id,
            expected_revision=proposed.revision,
        )
    output = tmp_path / "state.zip"
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        package.export_state_package(
            repository,
            output,
            exported_at="2026-06-25T04:00:00Z",
        )
    inspection = package.verify_state_package(output)
    assert inspection.record_counts["project_checkpoint"] == 1

    target = tmp_path / "imported"
    package.import_state_package(output, target)
    with state.open_state_repository(target, read_only=True) as repository:
        imported = ProjectCheckpointService(repository).get(confirmed.checkpoint_id)
    assert imported.freshness == "current"
    assert imported.basis_fingerprint == confirmed.basis_fingerprint

    backup_path = tmp_path / "backup.zip"
    create_state_backup(
        initialized.root,
        backup_path,
        created_at="2026-06-25T05:00:00Z",
    )
    verify_backup(backup_path)
    with zipfile.ZipFile(backup_path, "r") as archive:
        nested = archive.read("doll-backup/payload/state-package.zip")
    nested_path = tmp_path / "nested.zip"
    nested_path.write_bytes(nested)
    assert (
        package.verify_state_package(nested_path).record_counts["project_checkpoint"]
        == 1
    )


def test_checkpoint_registry_is_package_v2_only() -> None:
    version_one = get_authoritative_record_registry(1)
    version_two = get_authoritative_record_registry(2)
    assert "project_checkpoint" not in version_one.record_types
    assert "project_checkpoint" in version_two.record_types
    assert (
        version_two.by_record_type["project_checkpoint"].member_path
        == "records/project-checkpoints.jsonl"
    )


def test_tampered_fingerprint_fails_before_target_mutation(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_id = _project(repository)
        items = _work_items(repository, project_id)
        service = ProjectCheckpointService(repository)
        proposed = _propose(repository, project_id, items)
        confirmed = service.confirm(
            proposed.checkpoint_id,
            expected_revision=proposed.revision,
        )
    source = tmp_path / "source.zip"
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        package.export_state_package(
            repository,
            source,
            exported_at="2026-06-25T06:00:00Z",
        )
    members = _read_members(source)
    member_name = f"{package.PACKAGE_ROOT}/records/project-checkpoints.jsonl"
    payload = cast(
        dict[str, object],
        json.loads(members[member_name].decode("utf-8").strip()),
    )
    metadata = cast(dict[str, object], payload["metadata"])
    metadata["basis_fingerprint"] = "sha256:" + "0" * 64
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


def test_malformed_confirmed_checkpoint_is_corrupt(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_id = _project(repository)
        items = _work_items(repository, project_id)
        proposed = _propose(repository, project_id, items)
        record = repository.get_record(proposed.checkpoint_id)
        metadata = dict(record.metadata)
        metadata["confirmation_state"] = "confirmed"
        metadata["confirmed_by"] = "user"
        metadata["basis_fingerprint"] = "sha256:" + "0" * 64
        corrupt = replace_record_metadata(record, metadata)

        with pytest.raises(CheckpointCorruptError):
            _checkpoint_from_record(corrupt)


def replace_record_metadata(record: state.RecordEnvelope, metadata: dict[str, object]):
    return state.RecordEnvelope(
        id=record.id,
        record_type=record.record_type,
        schema_version=record.schema_version,
        created_at=record.created_at,
        updated_at=record.updated_at,
        revision=record.revision,
        status=record.status,
        provenance=record.provenance,
        sensitivity=record.sensitivity,
        title=record.title,
        metadata=metadata,
    )
