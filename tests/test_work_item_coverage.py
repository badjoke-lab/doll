from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import cast
from uuid import uuid4

import pytest

from doll import state, workspace
from doll.project_state import ProjectService
from doll.state import RecordProvenance, RecordStatus
from doll.state_repository import StateRepository
from doll.work_item import (
    MAX_LIST_LIMIT,
    AcceptanceCriterion,
    VerificationState,
    WorkItemActor,
    WorkItemCorruptError,
    WorkItemKind,
    WorkItemService,
    WorkItemStatus,
    WorkItemValidationError,
    _canonical_json,
    _criteria,
    _kind,
    _metadata_criteria,
    _metadata_ids,
    _metadata_list,
    _optional_utc,
    _optional_uuid,
    _priority,
    _proposal_provenance,
    _reference_ids,
    _required_string,
    _text,
    _token,
    _uuid,
    _verification_state,
    _work_item_from_record,
    _work_status,
)


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
            description="Work-item coverage project.",
            objective="Exercise defensive WorkItemRecord branches.",
            in_scope=("Work items",),
            out_of_scope=("Execution",),
            success_criteria=("Invalid state fails closed",),
            project_status="active",
            started_at="2026-06-25T00:00:00Z",
        )
        .project_id
    )


def _criterion(identifier: str = "criterion") -> AcceptanceCriterion:
    return AcceptanceCriterion(identifier, "Observable result.", None, True)


def test_list_filters_limits_and_archived_guards(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        first_project = _project(repository, "First")
        second_project = _project(repository, "Second")
        service = WorkItemService(repository)
        first = service.create(
            project_id=first_project,
            kind="task",
            title="First",
            description="First item.",
        )
        second = service.create(
            project_id=second_project,
            kind="review",
            title="Second",
            description="Second item.",
        )
        archived = service.archive(first.work_item_id, expected_revision=first.revision)

        assert service.list(project_id=first_project) == ()
        assert service.list(project_id=first_project, include_archived=True) == (archived,)
        assert service.list(project_id=second_project, limit=1) == (second,)
        for invalid_limit in (0, MAX_LIST_LIMIT + 1, True):
            with pytest.raises(WorkItemValidationError):
                service.list(limit=invalid_limit)
        with pytest.raises(WorkItemValidationError):
            service.list(project_id="not-a-uuid")
        with pytest.raises(WorkItemValidationError):
            service.archive(archived.work_item_id, expected_revision=archived.revision)
        with pytest.raises(WorkItemValidationError):
            service.update_definition(
                archived.work_item_id,
                expected_revision=archived.revision,
                title=archived.title,
                description=archived.description,
                priority=archived.priority,
                depends_on_ids=(),
                acceptance_criteria=(),
                source_decision_ids=(),
                artifact_ids=(),
                source_ids=(),
            )


def test_transition_and_verification_guard_branches(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_id = _project(repository)
        service = WorkItemService(repository)
        blocker = service.create(
            project_id=project_id,
            kind="task",
            title="Blocker",
            description="Current blocker.",
        )
        item = service.create(
            project_id=project_id,
            kind="task",
            title="Item",
            description="Transition target.",
        )

        with pytest.raises(WorkItemValidationError):
            service.transition(
                item.work_item_id,
                expected_revision=item.revision,
                to_status="completed",
            )
        with pytest.raises(WorkItemValidationError):
            service.transition(
                item.work_item_id,
                expected_revision=item.revision,
                to_status="in_progress",
                blocked_by_ids=(blocker.work_item_id,),
            )
        with pytest.raises(WorkItemValidationError):
            service.transition(
                item.work_item_id,
                expected_revision=item.revision,
                to_status="blocked",
            )

        blocked = service.transition(
            item.work_item_id,
            expected_revision=item.revision,
            to_status="blocked",
            blocked_by_ids=(blocker.work_item_id,),
        )
        ready = service.transition(
            blocked.work_item_id,
            expected_revision=blocked.revision,
            to_status="ready",
        )
        assert ready.blocked_by_ids == ()

        for actor in ("model", "runtime", "capability", "system"):
            with pytest.raises(WorkItemValidationError):
                service.set_verification(
                    ready.work_item_id,
                    expected_revision=ready.revision,
                    verification_state="pending",
                    actor_type=cast(WorkItemActor, actor),
                )
        with pytest.raises(WorkItemValidationError):
            service.set_verification(
                ready.work_item_id,
                expected_revision=ready.revision,
                verification_state="passed",
            )
        with pytest.raises(WorkItemValidationError):
            service.set_verification(
                ready.work_item_id,
                expected_revision=ready.revision,
                verification_state="not_applicable",
                evidence_ids=(str(uuid4()),),
            )


def test_proposal_provenance_and_secret_export(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_id = _project(repository)
        service = WorkItemService(repository)
        user = service.propose(
            project_id=project_id,
            kind="task",
            title="User proposal",
            description="User-created proposal.",
            actor_type="user",
        )
        runtime = service.propose(
            project_id=project_id,
            kind="maintenance",
            title="Runtime proposal",
            description="System-generated proposal.",
            actor_type="runtime",
        )
        secret = service.create(
            project_id=project_id,
            kind="review",
            title="Secret item",
            description="Secret export boundary.",
            sensitivity="secret",
        )

        assert user.provenance == "user-created"
        assert runtime.provenance == "system-generated"
        assert _proposal_provenance("model") == "model-proposed"
        assert _proposal_provenance("system") == "system-generated"
        with pytest.raises(WorkItemValidationError):
            service.export_json(secret.work_item_id)


def test_invalid_parent_and_typed_links(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_id = _project(repository)
        service = WorkItemService(repository)
        wrong = repository.create_record(record_type="other", metadata={})
        secret_source = repository.create_record(
            record_type="other_source",
            sensitivity="secret",
            metadata={},
        )

        for invalid_project in (str(uuid4()), wrong.id):
            with pytest.raises(WorkItemValidationError):
                service.create(
                    project_id=invalid_project,
                    kind="task",
                    title="Bad project",
                    description="Invalid parent.",
                )
        with pytest.raises(WorkItemValidationError):
            service.create(
                project_id=project_id,
                kind="task",
                title="Bad decision",
                description="Wrong decision type.",
                source_decision_ids=(wrong.id,),
            )
        with pytest.raises(WorkItemValidationError):
            service.create(
                project_id=project_id,
                kind="task",
                title="Bad artifact",
                description="Wrong artifact type.",
                artifact_ids=(wrong.id,),
            )
        for invalid_source in (str(uuid4()), secret_source.id):
            with pytest.raises(WorkItemValidationError):
                service.create(
                    project_id=project_id,
                    kind="task",
                    title="Bad source",
                    description="Invalid source link.",
                    source_ids=(invalid_source,),
                )

        item = service.create(
            project_id=project_id,
            kind="task",
            title="Evidence target",
            description="Wrong evidence type.",
        )
        with pytest.raises(WorkItemValidationError):
            service.set_verification(
                item.work_item_id,
                expected_revision=item.revision,
                verification_state="failed",
                evidence_ids=(wrong.id,),
            )


def test_terminal_and_archived_blockers_are_rejected(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_id = _project(repository)
        service = WorkItemService(repository)
        completed = service.create(
            project_id=project_id,
            kind="task",
            title="Completed blocker",
            description="Terminal blocker fixture.",
        )
        started = service.transition(
            completed.work_item_id,
            expected_revision=completed.revision,
            to_status="in_progress",
        )
        completed = service.transition(
            started.work_item_id,
            expected_revision=started.revision,
            to_status="completed",
        )
        target = service.create(
            project_id=project_id,
            kind="task",
            title="Target",
            description="Blocker validation target.",
        )
        with pytest.raises(WorkItemValidationError):
            service.transition(
                target.work_item_id,
                expected_revision=target.revision,
                to_status="blocked",
                blocked_by_ids=(completed.work_item_id,),
            )

        active = service.create(
            project_id=project_id,
            kind="task",
            title="Archived blocker",
            description="Archived relation target.",
        )
        service.archive(active.work_item_id, expected_revision=active.revision)
        with pytest.raises(WorkItemValidationError):
            service.update_definition(
                target.work_item_id,
                expected_revision=target.revision,
                title=target.title,
                description=target.description,
                priority=target.priority,
                depends_on_ids=(active.work_item_id,),
                acceptance_criteria=(),
                source_decision_ids=(),
                artifact_ids=(),
                source_ids=(),
            )


def test_malformed_envelopes_and_metadata_fail_closed(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_id = _project(repository)
        item = WorkItemService(repository).create(
            project_id=project_id,
            kind="task",
            title="Base",
            description="Malformed record base.",
        )
        record = repository.get_record(item.work_item_id)

        invalid_envelopes = (
            replace(record, record_type="other"),
            replace(record, schema_version=2),
            replace(record, status=cast(RecordStatus, "deleted")),
            replace(record, revision=0),
            replace(record, title="Different"),
            replace(record, provenance=cast(RecordProvenance, "model-proposed")),
        )
        for invalid in invalid_envelopes:
            with pytest.raises(WorkItemCorruptError):
                _work_item_from_record(invalid)

        mutations: tuple[tuple[str, object], ...] = (
            ("status", "completed"),
            ("completed_at", "2026-06-25T01:00:00Z"),
            ("status", "blocked"),
            ("verification_state", "passed"),
            ("depends_on_ids", [record.id]),
            ("source_ids", [record.id]),
        )
        for key, value in mutations:
            metadata = dict(record.metadata)
            metadata[key] = value
            with pytest.raises(WorkItemCorruptError):
                _work_item_from_record(replace(record, metadata=metadata))

        metadata = dict(record.metadata)
        metadata["completed_at"] = "2026-06-24T00:00:00Z"
        metadata["started_at"] = "2026-06-25T00:00:00Z"
        metadata["status"] = "completed"
        with pytest.raises(WorkItemCorruptError):
            _work_item_from_record(replace(record, metadata=metadata))


def test_validation_helper_defenses() -> None:
    for value in (None, "unknown", 1):
        with pytest.raises(WorkItemValidationError):
            _kind(cast(WorkItemKind, value))
        with pytest.raises(WorkItemValidationError):
            _work_status(cast(WorkItemStatus, value))
        with pytest.raises(WorkItemValidationError):
            _verification_state(cast(VerificationState, value))

    for value in (-1, 101, True, "1"):
        with pytest.raises(WorkItemValidationError):
            _priority(value)

    with pytest.raises(WorkItemValidationError):
        _criteria(cast(tuple[AcceptanceCriterion, ...], "invalid"))
    with pytest.raises(WorkItemValidationError):
        _criteria((cast(AcceptanceCriterion, object()),))
    with pytest.raises(WorkItemValidationError):
        _criteria((_criterion("duplicate"), _criterion("duplicate")))
    with pytest.raises(WorkItemValidationError):
        _criteria((AcceptanceCriterion("bad id", "Description", None, True),))
    with pytest.raises(WorkItemValidationError):
        _criteria((AcceptanceCriterion("valid", "Description", "bad kind", True),))
    with pytest.raises(WorkItemValidationError):
        _criteria((AcceptanceCriterion("valid", "Description", None, cast(bool, 1)),))

    invalid_criteria: tuple[object, ...] = (
        None,
        ["not-object"],
        [{"criterion_id": "id", "description": "d", "required_evidence_kind": 1, "blocking": True}],
        [{"criterion_id": "id", "description": "d", "required_evidence_kind": None, "blocking": 1}],
    )
    for value in invalid_criteria:
        with pytest.raises(WorkItemValidationError):
            _metadata_criteria({"criteria": value}, "criteria")

    identifier = str(uuid4())
    with pytest.raises(WorkItemValidationError):
        _reference_ids("IDs", cast(tuple[str, ...], "invalid"))
    with pytest.raises(WorkItemValidationError):
        _reference_ids("IDs", (identifier, identifier))
    with pytest.raises(WorkItemValidationError):
        _metadata_ids({"ids": [1]}, "ids")
    with pytest.raises(WorkItemValidationError):
        _metadata_list({"items": "not-list"}, "items")
    with pytest.raises(WorkItemValidationError):
        _required_string({}, "missing")

    for value in (None, "", "C:/private/file", "/private/file"):
        with pytest.raises(WorkItemValidationError):
            _text("text", value, 20)
    with pytest.raises(WorkItemValidationError):
        _token("token", "bad token")
    with pytest.raises(WorkItemValidationError):
        _uuid("ID", None)
    with pytest.raises(WorkItemValidationError):
        _uuid("ID", "invalid")
    assert _optional_uuid("ID", None) is None

    for value in (1, "not-utc", "badZ"):
        with pytest.raises(WorkItemValidationError):
            _optional_utc("time", value)
    assert _optional_utc("time", None) is None
    assert _optional_utc("time", "2026-06-25T00:00:00Z") == "2026-06-25T00:00:00Z"

    with pytest.raises(WorkItemValidationError):
        _canonical_json({"invalid": {1, 2}})


def test_read_only_create_and_update_are_rejected(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_id = _project(repository)
        item = WorkItemService(repository).create(
            project_id=project_id,
            kind="task",
            title="Read-only item",
            description="Read-only mutation fixture.",
        )

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        service = WorkItemService(repository)
        with pytest.raises(state.ReadOnlyStateError):
            service.create(
                project_id=project_id,
                kind="task",
                title="Rejected create",
                description="Read-only repository.",
            )
        with pytest.raises(state.ReadOnlyStateError):
            service.update_definition(
                item.work_item_id,
                expected_revision=item.revision,
                title=item.title,
                description=item.description,
                priority=item.priority,
                depends_on_ids=(),
                acceptance_criteria=(),
                source_decision_ids=(),
                artifact_ids=(),
                source_ids=(),
            )
