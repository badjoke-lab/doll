from __future__ import annotations

import json
import sqlite3
from dataclasses import replace
from pathlib import Path
from typing import cast
from uuid import uuid4

import pytest

from doll import state, workspace
from doll.checkpoint import (
    MAX_LINKS,
    MAX_LIST_LIMIT,
    CheckpointCorruptError,
    CheckpointValidationError,
    ProjectCheckpointInfo,
    ProjectCheckpointService,
    _active_work_item,
    _audit_actor,
    _basis_revisions,
    _canonical_json,
    _checkpoint_from_record,
    _confirmation_state,
    _confirmed_by,
    _fingerprint,
    _metadata_basis_revisions,
    _metadata_ids,
    _metadata_list,
    _optional_uuid,
    _proposal_provenance,
    _reference_ids,
    _require_disjoint_work_lists,
    _require_record,
    _required_string,
    _text,
    _utc,
    _uuid,
    _validate_generic_basis_links,
    _validate_project_link,
    _validate_work_item_lists,
    _validated_checkpoint_values,
)
from doll.project_state import ProjectService
from doll.state import StateCorruptError
from doll.state_repository import StateRepository
from doll.work_item import WorkItemService


def _workspace(tmp_path: Path) -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(tmp_path / "workspace")
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def _project(repository: StateRepository, name: str = "Project") -> str:
    return (
        ProjectService(repository)
        .create_v2(
            name=name,
            description="Checkpoint defensive coverage project.",
            objective="Exercise ProjectCheckpointRecord failure boundaries.",
            in_scope=("Checkpoint validation",),
            out_of_scope=("Derived status command",),
            success_criteria=("Invalid state fails closed",),
            project_status="active",
            started_at="2026-06-25T00:00:00Z",
        )
        .project_id
    )


def _proposal(
    service: ProjectCheckpointService,
    project_id: str,
    *,
    sensitivity: state.RecordSensitivity = "personal",
) -> ProjectCheckpointInfo:
    return service.propose(
        project_id=project_id,
        as_of="2026-06-25T01:00:00Z",
        summary="Synthetic checkpoint proposal.",
        current_phase="Coverage",
        current_goal="Exercise defensive checkpoint branches.",
        sensitivity=sensitivity,
        actor_type="user",
    )


def _raise_database_error(_repository: StateRepository) -> int:
    raise sqlite3.DatabaseError("synthetic checkpoint database failure")


def _raise_runtime_error(_repository: StateRepository) -> int:
    raise RuntimeError("synthetic checkpoint runtime failure")


def test_list_lifecycle_actor_and_export_guards(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        first_project = _project(repository, "First")
        second_project = _project(repository, "Second")
        service = ProjectCheckpointService(repository)
        first = _proposal(service, first_project)
        second = _proposal(service, second_project)
        archived = service.archive(first.checkpoint_id, expected_revision=first.revision)

        assert service.list(project_id=first_project) == ()
        assert service.list(project_id=first_project, include_archived=True) == (archived,)
        assert service.list(project_id=second_project, limit=1) == (second,)
        for invalid_limit in (0, MAX_LIST_LIMIT + 1, True):
            with pytest.raises(CheckpointValidationError):
                service.list(limit=invalid_limit)
        with pytest.raises(CheckpointValidationError):
            service.list(project_id="invalid")
        with pytest.raises(CheckpointValidationError):
            service.archive(archived.checkpoint_id, expected_revision=archived.revision)
        with pytest.raises(CheckpointValidationError):
            service.confirm(archived.checkpoint_id, expected_revision=archived.revision)
        with pytest.raises(CheckpointValidationError):
            service.supersede(second.checkpoint_id, expected_revision=second.revision)

        confirmed = service.confirm(
            second.checkpoint_id,
            expected_revision=second.revision,
        )
        with pytest.raises(CheckpointValidationError):
            service.confirm(
                confirmed.checkpoint_id,
                expected_revision=confirmed.revision,
            )
        with pytest.raises(CheckpointValidationError):
            service.supersede(
                confirmed.checkpoint_id,
                expected_revision=confirmed.revision,
                actor_type="model",
            )
        superseded = service.supersede(
            confirmed.checkpoint_id,
            expected_revision=confirmed.revision,
        )
        with pytest.raises(CheckpointValidationError):
            service.supersede(
                superseded.checkpoint_id,
                expected_revision=superseded.revision,
            )
        with pytest.raises(CheckpointValidationError):
            service.archive(
                superseded.checkpoint_id,
                expected_revision=superseded.revision,
                actor_type="runtime",
            )

        secret = _proposal(service, first_project, sensitivity="secret")
        with pytest.raises(CheckpointValidationError):
            service.export_json(secret.checkpoint_id)


def test_requested_checkpoint_semantics_fail_closed(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_id = _project(repository)
        checkpoint_id = str(uuid4())
        fingerprint = "sha256:" + "0" * 64

        with pytest.raises(CheckpointValidationError):
            _validated_checkpoint_values(
                repository,
                self_id=project_id,
                project_id=project_id,
                as_of="2026-06-25T01:00:00Z",
                summary="Self basis.",
                current_phase="Phase",
                current_goal="Goal",
                active_work_item_ids=(),
                next_work_item_ids=(),
                blocked_work_item_ids=(),
                completed_milestone_ids=(),
                required_validation_ids=(),
                basis_record_ids=(),
                basis_record_revisions={},
                basis_fingerprint=None,
                confirmation_state="proposed",
                confirmed_by=None,
            )
        with pytest.raises(CheckpointValidationError):
            _validated_checkpoint_values(
                repository,
                self_id=checkpoint_id,
                project_id=project_id,
                as_of="2026-06-25T01:00:00Z",
                summary="Duplicate basis.",
                current_phase="Phase",
                current_goal="Goal",
                active_work_item_ids=(),
                next_work_item_ids=(),
                blocked_work_item_ids=(),
                completed_milestone_ids=(),
                required_validation_ids=(),
                basis_record_ids=(project_id,),
                basis_record_revisions={},
                basis_fingerprint=None,
                confirmation_state="proposed",
                confirmed_by=None,
            )
        for revisions, basis_fingerprint, confirmed_by in (
            ({project_id: 1}, None, None),
            ({}, fingerprint, None),
            ({}, None, "user"),
        ):
            with pytest.raises(CheckpointValidationError):
                _validated_checkpoint_values(
                    repository,
                    self_id=checkpoint_id,
                    project_id=project_id,
                    as_of="2026-06-25T01:00:00Z",
                    summary="Invalid proposed metadata.",
                    current_phase="Phase",
                    current_goal="Goal",
                    active_work_item_ids=(),
                    next_work_item_ids=(),
                    blocked_work_item_ids=(),
                    completed_milestone_ids=(),
                    required_validation_ids=(),
                    basis_record_ids=(),
                    basis_record_revisions=revisions,
                    basis_fingerprint=basis_fingerprint,
                    confirmation_state="proposed",
                    confirmed_by=confirmed_by,
                )
        with pytest.raises(CheckpointValidationError):
            _validated_checkpoint_values(
                repository,
                self_id=checkpoint_id,
                project_id=project_id,
                as_of="2026-06-25T01:00:00Z",
                summary="Missing confirmer.",
                current_phase="Phase",
                current_goal="Goal",
                active_work_item_ids=(),
                next_work_item_ids=(),
                blocked_work_item_ids=(),
                completed_milestone_ids=(),
                required_validation_ids=(),
                basis_record_ids=(),
                basis_record_revisions={project_id: 1},
                basis_fingerprint=fingerprint,
                confirmation_state="confirmed",
                confirmed_by=None,
            )
        with pytest.raises(CheckpointValidationError):
            _validated_checkpoint_values(
                repository,
                self_id=checkpoint_id,
                project_id=project_id,
                as_of="2026-06-25T01:00:00Z",
                summary="Mismatched basis.",
                current_phase="Phase",
                current_goal="Goal",
                active_work_item_ids=(),
                next_work_item_ids=(),
                blocked_work_item_ids=(),
                completed_milestone_ids=(),
                required_validation_ids=(),
                basis_record_ids=(),
                basis_record_revisions={},
                basis_fingerprint=fingerprint,
                confirmation_state="confirmed",
                confirmed_by="user",
            )
        with pytest.raises(CheckpointValidationError):
            _validated_checkpoint_values(
                repository,
                self_id=checkpoint_id,
                project_id=project_id,
                as_of="2026-06-25T01:00:00Z",
                summary="Invalid fingerprint.",
                current_phase="Phase",
                current_goal="Goal",
                active_work_item_ids=(),
                next_work_item_ids=(),
                blocked_work_item_ids=(),
                completed_milestone_ids=(),
                required_validation_ids=(),
                basis_record_ids=(),
                basis_record_revisions={project_id: 1},
                basis_fingerprint="invalid",
                confirmation_state="confirmed",
                confirmed_by="user",
            )


def test_project_work_item_and_basis_link_guards(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        first_project = _project(repository, "First")
        second_project = _project(repository, "Second")
        wrong = repository.create_record(record_type="other", metadata={})

        with pytest.raises(CheckpointValidationError):
            _validate_project_link(repository, str(uuid4()))
        with pytest.raises(CheckpointValidationError):
            _validate_project_link(repository, wrong.id)
        work = WorkItemService(repository)
        ready = work.create(
            project_id=first_project,
            kind="task",
            title="Ready work",
            description="Ready-state fixture.",
        )
        cross = work.create(
            project_id=second_project,
            kind="task",
            title="Cross-project work",
            description="Cross-project fixture.",
        )
        cross = work.transition(
            cross.work_item_id,
            expected_revision=cross.revision,
            to_status="in_progress",
        )
        second_record = repository.get_record(second_project)
        repository.update_record(
            second_project,
            expected_revision=second_record.revision,
            status="archived",
        )
        with pytest.raises(CheckpointValidationError):
            _validate_project_link(repository, second_project)

        completed_task = work.create(
            project_id=first_project,
            kind="task",
            title="Completed task",
            description="Wrong milestone-kind fixture.",
        )
        completed_task = work.transition(
            completed_task.work_item_id,
            expected_revision=completed_task.revision,
            to_status="in_progress",
        )
        completed_task = work.transition(
            completed_task.work_item_id,
            expected_revision=completed_task.revision,
            to_status="completed",
        )

        with pytest.raises(CheckpointValidationError):
            _validate_work_item_lists(
                repository,
                project_id=first_project,
                active_ids=(cross.work_item_id,),
                next_ids=(),
                blocked_ids=(),
                milestone_ids=(),
            )
        with pytest.raises(CheckpointValidationError):
            _validate_work_item_lists(
                repository,
                project_id=first_project,
                active_ids=(ready.work_item_id,),
                next_ids=(),
                blocked_ids=(),
                milestone_ids=(),
            )
        with pytest.raises(CheckpointValidationError):
            _validate_work_item_lists(
                repository,
                project_id=first_project,
                active_ids=(),
                next_ids=(),
                blocked_ids=(),
                milestone_ids=(completed_task.work_item_id,),
            )
        with pytest.raises(CheckpointValidationError):
            _active_work_item(repository, str(uuid4()))
        with pytest.raises(CheckpointValidationError):
            _active_work_item(repository, wrong.id)
        archived = work.archive(ready.work_item_id, expected_revision=ready.revision)
        with pytest.raises(CheckpointValidationError):
            _active_work_item(repository, archived.work_item_id)
        malformed = repository.create_record(record_type="work_item", metadata={})
        with pytest.raises(CheckpointValidationError):
            _active_work_item(repository, malformed.id)

        inactive = repository.create_record(record_type="basis", metadata={})
        repository.update_record(
            inactive.id,
            expected_revision=inactive.revision,
            status="archived",
        )
        secret = repository.create_record(record_type="basis", metadata={})
        repository.connection.execute(
            "UPDATE records SET sensitivity = 'secret' WHERE id = ?",
            (secret.id,),
        )
        with pytest.raises(CheckpointValidationError):
            _validate_generic_basis_links(repository, (str(uuid4()),), ())
        with pytest.raises(CheckpointValidationError):
            _validate_generic_basis_links(repository, (inactive.id,), ())
        with pytest.raises(CheckpointValidationError):
            _validate_generic_basis_links(repository, (), (secret.id,))


def test_malformed_checkpoint_envelopes_and_metadata(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_id = _project(repository)
        service = ProjectCheckpointService(repository)
        proposed = _proposal(service, project_id)
        proposed_record = repository.get_record(proposed.checkpoint_id)

        invalid_envelopes = (
            replace(proposed_record, record_type="other"),
            replace(proposed_record, schema_version=2),
            replace(proposed_record, status="deleted"),
            replace(proposed_record, revision=0),
            replace(proposed_record, title="not allowed"),
        )
        for invalid in invalid_envelopes:
            with pytest.raises(CheckpointCorruptError):
                _checkpoint_from_record(invalid)

        mutations: tuple[tuple[str, object], ...] = (
            ("basis_fingerprint", 1),
            ("fingerprint_format_version", 2),
            ("basis_record_ids", [proposed.checkpoint_id]),
            ("basis_record_ids", [project_id]),
            ("basis_record_revisions", {project_id: 1}),
            ("confirmed_by", "user"),
        )
        for key, value in mutations:
            metadata: dict[str, object] = dict(proposed_record.metadata)
            metadata[key] = value
            with pytest.raises(CheckpointCorruptError):
                _checkpoint_from_record(replace(proposed_record, metadata=metadata))

        confirmed = service.confirm(
            proposed.checkpoint_id,
            expected_revision=proposed.revision,
        )
        confirmed_record = repository.get_record(confirmed.checkpoint_id)
        confirmed_mutations: tuple[tuple[str, object], ...] = (
            ("confirmed_by", None),
            ("basis_record_revisions", {}),
            ("basis_fingerprint", "sha256:" + "0" * 64),
        )
        for key, value in confirmed_mutations:
            metadata = dict(confirmed_record.metadata)
            metadata[key] = value
            with pytest.raises(CheckpointCorruptError):
                _checkpoint_from_record(replace(confirmed_record, metadata=metadata))
        with pytest.raises(CheckpointCorruptError):
            _checkpoint_from_record(replace(confirmed_record, provenance="model-proposed"))


def test_validation_helpers() -> None:
    for value in (None, "unknown", 1):
        with pytest.raises(CheckpointValidationError):
            _confirmation_state(value)
    assert _confirmed_by(None) is None
    assert _confirmed_by("user") == "user"
    with pytest.raises(CheckpointValidationError):
        _confirmed_by("model")

    too_many = {str(uuid4()): 1 for _ in range(MAX_LINKS + 1)}
    with pytest.raises(CheckpointValidationError):
        _basis_revisions(too_many)
    for revision in (0, -1, True):
        with pytest.raises(CheckpointValidationError):
            _basis_revisions({str(uuid4()): revision})
    identifier = str(uuid4())
    with pytest.raises(CheckpointValidationError):
        _basis_revisions({identifier: 1, identifier.upper(): 2})
    with pytest.raises(CheckpointValidationError):
        _metadata_basis_revisions({"basis_record_revisions": []})
    with pytest.raises(CheckpointValidationError):
        _metadata_basis_revisions(cast(dict[str, object], {"basis_record_revisions": {1: 1}}))
    with pytest.raises(CheckpointValidationError):
        _metadata_basis_revisions({"basis_record_revisions": {str(uuid4()): "1"}})
    with pytest.raises(CheckpointValidationError):
        _fingerprint(None)
    with pytest.raises(CheckpointValidationError):
        _fingerprint("sha256:invalid")
    _require_disjoint_work_lists((str(uuid4()),), ())
    duplicate = str(uuid4())
    with pytest.raises(CheckpointValidationError):
        _require_disjoint_work_lists((duplicate,), (duplicate,))

    with pytest.raises(CheckpointValidationError):
        _reference_ids("IDs", cast(tuple[str, ...], "invalid"))
    with pytest.raises(CheckpointValidationError):
        _reference_ids("IDs", tuple(str(uuid4()) for _ in range(MAX_LINKS + 1)))
    with pytest.raises(CheckpointValidationError):
        _reference_ids("IDs", (duplicate, duplicate))
    with pytest.raises(CheckpointValidationError):
        _metadata_ids({"ids": [1]}, "ids")
    with pytest.raises(CheckpointValidationError):
        _metadata_list({"items": "invalid"}, "items")
    with pytest.raises(CheckpointValidationError):
        _required_string({}, "missing")

    for value in (None, "", "/private/path", "C:/private/path"):
        with pytest.raises(CheckpointValidationError):
            _text("text", value, 20)
    with pytest.raises(CheckpointValidationError):
        _text("text", "x" * 21, 20)
    with pytest.raises(CheckpointValidationError):
        _uuid("ID", None)
    with pytest.raises(CheckpointValidationError):
        _uuid("ID", "invalid")
    assert _optional_uuid("ID", None) is None
    for value in (None, "not-utc", "badZ"):
        with pytest.raises(CheckpointValidationError):
            _utc("time", value)
    with pytest.raises(CheckpointValidationError):
        _canonical_json({"invalid": {1, 2}})

    assert _proposal_provenance("user") == "user-created"
    assert _proposal_provenance("model") == "model-proposed"
    assert _proposal_provenance("importer") == "imported"
    assert _proposal_provenance("runtime") == "system-generated"
    assert _audit_actor("importer") == "system"
    assert _audit_actor("model") == "model"


def test_record_lookup_and_read_only_guards(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_id = _project(repository)
        service = ProjectCheckpointService(repository)
        proposed = _proposal(service, project_id)
        wrong = repository.create_record(record_type="other", metadata={})
        assert _require_record(repository, proposed.checkpoint_id).id == proposed.checkpoint_id
        with pytest.raises(CheckpointValidationError):
            _require_record(repository, str(uuid4()))
        with pytest.raises(CheckpointValidationError):
            _require_record(repository, wrong.id)

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        service = ProjectCheckpointService(repository)
        with pytest.raises(state.ReadOnlyStateError):
            _proposal(service, project_id)
        with pytest.raises(state.ReadOnlyStateError):
            service.confirm(
                proposed.checkpoint_id,
                expected_revision=proposed.revision,
            )


def test_create_failure_paths_roll_back(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_id = _project(repository)
        service = ProjectCheckpointService(repository)
        monkeypatch.setattr(
            StateRepository,
            "_commit_state_revision",
            _raise_database_error,
        )
        with pytest.raises(StateCorruptError):
            _proposal(service, project_id)
        assert (
            repository.connection.execute(
                "SELECT COUNT(*) FROM records WHERE record_type = 'project_checkpoint'"
            ).fetchone()[0]
            == 0
        )

    monkeypatch.undo()
    initialized = _workspace(tmp_path / "runtime")
    with state.open_state_repository(initialized.root) as repository:
        project_id = _project(repository)
        service = ProjectCheckpointService(repository)
        monkeypatch.setattr(
            StateRepository,
            "_commit_state_revision",
            _raise_runtime_error,
        )
        with pytest.raises(RuntimeError, match="synthetic checkpoint runtime failure"):
            _proposal(service, project_id)
        assert (
            repository.connection.execute(
                "SELECT COUNT(*) FROM records WHERE record_type = 'project_checkpoint'"
            ).fetchone()[0]
            == 0
        )


def test_update_failure_paths_roll_back(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_id = _project(repository)
        service = ProjectCheckpointService(repository)
        proposed = _proposal(service, project_id)
        monkeypatch.setattr(
            StateRepository,
            "_commit_state_revision",
            _raise_database_error,
        )
        with pytest.raises(StateCorruptError):
            service.confirm(
                proposed.checkpoint_id,
                expected_revision=proposed.revision,
            )
        unchanged = service.get(proposed.checkpoint_id)
        assert unchanged.confirmation_state == "proposed"
        assert unchanged.revision == proposed.revision

    monkeypatch.undo()
    initialized = _workspace(tmp_path / "runtime")
    with state.open_state_repository(initialized.root) as repository:
        project_id = _project(repository)
        service = ProjectCheckpointService(repository)
        proposed = _proposal(service, project_id)
        monkeypatch.setattr(
            StateRepository,
            "_commit_state_revision",
            _raise_runtime_error,
        )
        with pytest.raises(RuntimeError, match="synthetic checkpoint runtime failure"):
            service.confirm(
                proposed.checkpoint_id,
                expected_revision=proposed.revision,
            )
        unchanged = service.get(proposed.checkpoint_id)
        assert unchanged.confirmation_state == "proposed"
        assert unchanged.revision == proposed.revision


def test_same_revision_invalid_live_role_derives_stale(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_id = _project(repository)
        work = WorkItemService(repository)
        ready = work.create(
            project_id=project_id,
            kind="task",
            title="Next work",
            description="Next work before direct tampering.",
        )
        service = ProjectCheckpointService(repository)
        proposed = service.propose(
            project_id=project_id,
            as_of="2026-06-25T01:00:00Z",
            summary="Same-revision role tampering fixture.",
            current_phase="Coverage",
            current_goal="Exercise live-link freshness validation.",
            next_work_item_ids=(ready.work_item_id,),
            actor_type="user",
        )
        confirmed = service.confirm(
            proposed.checkpoint_id,
            expected_revision=proposed.revision,
        )
        record = repository.get_record(ready.work_item_id)
        metadata = dict(record.metadata)
        metadata["status"] = "cancelled"
        repository.connection.execute(
            "UPDATE records SET metadata_json = ? WHERE id = ?",
            (
                json.dumps(metadata, sort_keys=True, separators=(",", ":")),
                ready.work_item_id,
            ),
        )
        stale = service.get(confirmed.checkpoint_id)

    assert stale.freshness == "stale"
