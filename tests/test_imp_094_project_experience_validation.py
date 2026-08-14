from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest

from doll import state, workspace
from doll.memory import ConfirmedMemoryService
from doll.project_experience import (
    MAX_LINKS,
    MAX_SUMMARY_LENGTH,
    ProjectExperienceCorruptError,
    ProjectExperienceService,
    ProjectExperienceValidationError,
    _assertion_state,
    _event_kind,
    _ids,
    _metadata_ids,
    _optional_string,
    _optional_uuid,
    _outcome,
    _project_experience_from_record,
    _required_string,
    _text,
    _utc,
    _uuid,
)
from doll.project_state import ProjectService
from doll.state import RecordEnvelope
from doll.work_item import WorkItemService


def _workspace(tmp_path: Path) -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(tmp_path / "workspace")
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def _project(repository: object, name: str) -> object:
    return ProjectService(repository).create_v2(  # type: ignore[arg-type]
        name=name,
        description="Synthetic project for ProjectExperienceRecord validation coverage.",
        objective="Exercise deterministic validation boundaries.",
        in_scope=("validation",),
        out_of_scope=("authority mutation",),
        success_criteria=("invalid input fails closed",),
        project_status="active",
        started_at="2026-08-15T00:00:00Z",
    )


def _experience(repository: object, project_id: str) -> object:
    return ProjectExperienceService(repository).record(  # type: ignore[arg-type]
        project_id=project_id,
        event_kind="observation",
        summary="Synthetic valid experience.",
        occurred_at="2026-08-15T00:01:00Z",
        assertion_state="user_recorded",
        actor_type="user",
    )


def test_imp_094_service_export_list_and_missing_lookup_paths(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        first = _project(repository, "First project")
        second = _project(repository, "Second project")
        first_item = _experience(repository, first.project_id)  # type: ignore[attr-defined]
        _experience(repository, second.project_id)  # type: ignore[attr-defined]
        service = ProjectExperienceService(repository)

        exported = service.export_json(first_item.experience_id)  # type: ignore[attr-defined]
        assert '"export_schema":"doll.project-experience.v1"' in exported
        assert first_item.experience_id in exported  # type: ignore[attr-defined]
        assert service.list(project_id=first.project_id, limit=1) == (first_item,)  # type: ignore[attr-defined]

        for bad_limit in (0, 501, True):
            with pytest.raises(ProjectExperienceValidationError, match="list limit"):
                service.list(limit=bad_limit)  # type: ignore[arg-type]
        with pytest.raises(ProjectExperienceValidationError, match="does not exist"):
            service.get(str(uuid4()))
        with pytest.raises(ProjectExperienceValidationError, match="experience ID is invalid"):
            service.get("not-a-uuid")


def test_imp_094_link_validation_rejects_missing_wrong_type_and_cross_project(
    tmp_path: Path,
) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        first = _project(repository, "First project")
        second = _project(repository, "Second project")
        first_work = WorkItemService(repository).create(
            project_id=first.project_id,  # type: ignore[attr-defined]
            kind="investigation",
            title="First work",
            description="Synthetic first work item.",
            priority=10,
        )
        second_work = WorkItemService(repository).create(
            project_id=second.project_id,  # type: ignore[attr-defined]
            kind="investigation",
            title="Second work",
            description="Synthetic second work item.",
            priority=10,
        )
        memory = ConfirmedMemoryService(repository).create(
            subject="Wrong-type link fixture",
            content="Synthetic record used only as a wrong record type.",
        )
        first_experience = _experience(repository, first.project_id)  # type: ignore[attr-defined]
        second_experience = _experience(repository, second.project_id)  # type: ignore[attr-defined]
        service = ProjectExperienceService(repository)
        missing = str(uuid4())

        def record(**kwargs: object) -> None:
            service.record(
                project_id=first.project_id,  # type: ignore[attr-defined]
                event_kind="observation",
                summary="Synthetic invalid-link candidate.",
                occurred_at="2026-08-15T01:00:00Z",
                assertion_state="user_recorded",
                actor_type="user",
                **kwargs,  # type: ignore[arg-type]
            )

        with pytest.raises(ProjectExperienceValidationError, match="linked project does not exist"):
            service.record(
                project_id=missing,
                event_kind="observation",
                summary="Missing project.",
                occurred_at="2026-08-15T01:00:00Z",
                assertion_state="user_recorded",
                actor_type="user",
            )
        with pytest.raises(ProjectExperienceValidationError, match="project link"):
            service.record(
                project_id=memory.record_id,
                event_kind="observation",
                summary="Wrong project type.",
                occurred_at="2026-08-15T01:00:00Z",
                assertion_state="user_recorded",
                actor_type="user",
            )
        with pytest.raises(ProjectExperienceValidationError, match="linked work item does not exist"):
            record(work_item_id=missing)
        with pytest.raises(ProjectExperienceValidationError, match="work-item link"):
            record(work_item_id=memory.record_id)
        with pytest.raises(ProjectExperienceValidationError, match="another project"):
            record(work_item_id=second_work.work_item_id)
        with pytest.raises(ProjectExperienceValidationError, match="evidence link"):
            record(evidence_ids=(memory.record_id,))
        with pytest.raises(ProjectExperienceValidationError, match="linked evidence does not exist"):
            record(evidence_ids=(missing,))
        with pytest.raises(ProjectExperienceValidationError, match="related record does not exist"):
            record(related_record_ids=(missing,))
        with pytest.raises(ProjectExperienceValidationError, match="source does not exist"):
            record(source_ids=(missing,))
        with pytest.raises(ProjectExperienceValidationError, match="superseded experience does not exist"):
            record(supersedes_id=missing)
        with pytest.raises(ProjectExperienceValidationError, match="another record type"):
            record(supersedes_id=memory.record_id)
        with pytest.raises(ProjectExperienceValidationError, match="another project"):
            record(supersedes_id=second_experience.experience_id)  # type: ignore[attr-defined]

        valid = service.record(
            project_id=first.project_id,  # type: ignore[attr-defined]
            work_item_id=first_work.work_item_id,
            event_kind="lesson",
            summary="Valid linked lesson.",
            occurred_at="2026-08-15T01:05:00Z",
            assertion_state="user_recorded",
            actor_type="user",
            related_record_ids=(first_experience.experience_id,),  # type: ignore[attr-defined]
            source_ids=(memory.record_id,),
            supersedes_id=first_experience.experience_id,  # type: ignore[attr-defined]
        )
        assert valid.project_id == first.project_id  # type: ignore[attr-defined]


def test_imp_094_value_validators_cover_fail_closed_inputs() -> None:
    valid_uuid = str(uuid4())
    assert _optional_uuid("optional", None) is None
    assert _optional_uuid("optional", valid_uuid) == valid_uuid
    assert _outcome(None) is None
    assert _event_kind("lesson") == "lesson"
    assert _assertion_state("model_proposed") == "model_proposed"
    assert _utc("time", "2026-08-15T00:00:00Z") == "2026-08-15T00:00:00Z"
    assert _text("summary", "  hello  ", 20) == "hello"
    assert _ids("ids", (valid_uuid,)) == (valid_uuid,)

    with pytest.raises(ProjectExperienceValidationError, match="must be text"):
        _uuid("id", 1)  # type: ignore[arg-type]
    with pytest.raises(ProjectExperienceValidationError, match="is invalid"):
        _uuid("id", "bad")
    with pytest.raises(ProjectExperienceValidationError, match="event kind"):
        _event_kind("future")
    with pytest.raises(ProjectExperienceValidationError, match="outcome"):
        _outcome("future")
    with pytest.raises(ProjectExperienceValidationError, match="assertion state"):
        _assertion_state("future")
    with pytest.raises(ProjectExperienceValidationError, match="end in Z"):
        _utc("time", "2026-08-15T00:00:00+00:00")
    with pytest.raises(ProjectExperienceValidationError, match="is invalid"):
        _utc("time", "not-a-timeZ")
    with pytest.raises(ProjectExperienceValidationError, match="must be text"):
        _text("summary", 1, 20)  # type: ignore[arg-type]
    with pytest.raises(ProjectExperienceValidationError, match="empty or too long"):
        _text("summary", "", 20)
    with pytest.raises(ProjectExperienceValidationError, match="empty or too long"):
        _text("summary", "x" * (MAX_SUMMARY_LENGTH + 1), MAX_SUMMARY_LENGTH)
    with pytest.raises(ProjectExperienceValidationError, match="control characters"):
        _text("summary", "bad\x01text", 20)
    with pytest.raises(ProjectExperienceValidationError, match="absolute paths"):
        _text("summary", r"Observed C:\\Users\\example\\private.txt", 100)
    with pytest.raises(ProjectExperienceValidationError, match="must be a sequence"):
        _ids("ids", valid_uuid)  # type: ignore[arg-type]
    with pytest.raises(ProjectExperienceValidationError, match="exceeds"):
        _ids("ids", tuple(str(uuid4()) for _ in range(MAX_LINKS + 1)))
    with pytest.raises(ProjectExperienceValidationError, match="duplicates"):
        _ids("ids", (valid_uuid, valid_uuid))


def test_imp_094_malformed_record_helpers_fail_closed(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project = _project(repository, "Malformed fixture project")
        experience = _experience(repository, project.project_id)  # type: ignore[attr-defined]
        record = repository.get_record(experience.experience_id)  # type: ignore[attr-defined]

        assert _required_string(record, "summary") == "Synthetic valid experience."
        assert _optional_string(record, "work_item_id") is None
        assert _metadata_ids(record, "related_record_ids") == ()

        malformed: list[RecordEnvelope] = [
            replace(record, record_type="memory"),
            replace(record, schema_version=2),
            replace(record, revision=0),
            replace(record, status="proposed"),  # type: ignore[arg-type]
            replace(record, provenance="imported"),
            replace(record, metadata={**record.metadata, "event_kind": "future"}),
            replace(record, metadata={**record.metadata, "summary": 1}),
            replace(record, metadata={**record.metadata, "outcome": 1}),
            replace(record, metadata={**record.metadata, "occurred_at": "badZ"}),
            replace(record, metadata={**record.metadata, "assertion_state": "future"}),
            replace(record, metadata={**record.metadata, "related_record_ids": "not-a-list"}),
            replace(
                record,
                metadata={
                    **record.metadata,
                    "event_kind": "outcome",
                    "outcome": None,
                },
            ),
            replace(record, metadata={**record.metadata, "supersedes_id": record.id}),
        ]
        for item in malformed:
            with pytest.raises(ProjectExperienceCorruptError, match="malformed"):
                _project_experience_from_record(item, repository)

        missing_summary = dict(record.metadata)
        missing_summary.pop("summary")
        with pytest.raises(ProjectExperienceCorruptError, match="malformed"):
            _project_experience_from_record(replace(record, metadata=missing_summary), repository)

        wrong_optional = replace(record, metadata={**record.metadata, "work_item_id": 1})
        with pytest.raises(ProjectExperienceCorruptError, match="malformed"):
            _project_experience_from_record(wrong_optional, repository)


def test_imp_094_outcome_requires_value_and_cross_project_work_remains_rejected(
    tmp_path: Path,
) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project = _project(repository, "Outcome fixture")
        service = ProjectExperienceService(repository)
        with pytest.raises(ProjectExperienceValidationError, match="require an outcome"):
            service.record(
                project_id=project.project_id,  # type: ignore[attr-defined]
                event_kind="outcome",
                summary="Outcome without value.",
                occurred_at="2026-08-15T02:00:00Z",
                assertion_state="user_recorded",
                actor_type="user",
            )
