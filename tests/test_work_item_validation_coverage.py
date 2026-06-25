from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

import pytest

from doll import state, workspace
from doll.project_state import ProjectService
from doll.state_repository import StateRepository
from doll.work_item import (
    MAX_LINKS,
    MAX_LIST_ITEMS,
    AcceptanceCriterion,
    VerificationState,
    WorkItemService,
    WorkItemStatus,
    WorkItemValidationError,
    _criteria,
    _reference_ids,
    _require_record,
    _text,
    _token,
    _validate_persisted_semantics,
    _validated_work_item_values,
)


def _workspace(tmp_path: Path) -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(tmp_path / "workspace")
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def _project(repository: StateRepository) -> str:
    return (
        ProjectService(repository)
        .create_v2(
            name="Validation project",
            description="Work-item validation coverage.",
            objective="Exercise semantic rejection branches.",
            in_scope=("Validation",),
            out_of_scope=("Execution",),
            success_criteria=("Invalid values fail closed",),
            project_status="active",
            started_at="2026-06-25T00:00:00Z",
        )
        .project_id
    )


def _values(
    repository: StateRepository,
    *,
    project_id: str,
    self_id: str,
    work_status: WorkItemStatus = "ready",
    started_at: str | None = None,
    completed_at: str | None = None,
    depends_on_ids: tuple[str, ...] = (),
    blocked_by_ids: tuple[str, ...] = (),
    verification_state: VerificationState = "not_verified",
    verification_evidence_ids: tuple[str, ...] = (),
    source_ids: tuple[str, ...] = (),
) -> dict[str, object]:
    return _validated_work_item_values(
        repository,
        self_id=self_id,
        project_id=project_id,
        kind="task",
        title="Validation item",
        description="Synthetic semantic validation item.",
        work_status=work_status,
        priority=50,
        started_at=started_at,
        completed_at=completed_at,
        depends_on_ids=depends_on_ids,
        blocked_by_ids=blocked_by_ids,
        acceptance_criteria=(),
        verification_state=verification_state,
        verification_evidence_ids=verification_evidence_ids,
        source_decision_ids=(),
        artifact_ids=(),
        source_ids=source_ids,
    )


def test_requested_value_semantic_rejections(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_id = _project(repository)
        self_id = str(uuid4())
        other_id = str(uuid4())

        with pytest.raises(WorkItemValidationError):
            _values(
                repository,
                project_id=project_id,
                self_id=self_id,
                work_status="completed",
                started_at="2026-06-25T02:00:00Z",
                completed_at="2026-06-25T01:00:00Z",
            )
        with pytest.raises(WorkItemValidationError):
            _values(
                repository,
                project_id=project_id,
                self_id=self_id,
                work_status="completed",
                started_at="2026-06-25T01:00:00Z",
            )
        with pytest.raises(WorkItemValidationError):
            _values(
                repository,
                project_id=project_id,
                self_id=self_id,
                completed_at="2026-06-25T01:00:00Z",
            )
        with pytest.raises(WorkItemValidationError):
            _values(
                repository,
                project_id=project_id,
                self_id=self_id,
                work_status="blocked",
            )
        with pytest.raises(WorkItemValidationError):
            _values(
                repository,
                project_id=project_id,
                self_id=self_id,
                depends_on_ids=(self_id,),
            )
        with pytest.raises(WorkItemValidationError):
            _values(
                repository,
                project_id=project_id,
                self_id=self_id,
                depends_on_ids=(other_id,),
                blocked_by_ids=(other_id,),
            )
        with pytest.raises(WorkItemValidationError):
            _values(
                repository,
                project_id=project_id,
                self_id=self_id,
                verification_state="passed",
            )
        with pytest.raises(WorkItemValidationError):
            _values(
                repository,
                project_id=project_id,
                self_id=self_id,
                verification_evidence_ids=(other_id,),
            )
        with pytest.raises(WorkItemValidationError):
            _values(
                repository,
                project_id=project_id,
                self_id=self_id,
                source_ids=(self_id,),
            )


def _persisted(
    *,
    self_id: str,
    status: WorkItemStatus = "ready",
    started_at: str | None = None,
    completed_at: str | None = None,
    dependencies: tuple[str, ...] = (),
    blockers: tuple[str, ...] = (),
    verification: VerificationState = "not_verified",
    evidence: tuple[str, ...] = (),
    source_ids: tuple[str, ...] = (),
) -> None:
    _validate_persisted_semantics(
        self_id,
        status,
        started_at,
        completed_at,
        dependencies,
        blockers,
        verification,
        evidence,
        source_ids,
    )


def test_persisted_semantic_rejections() -> None:
    self_id = str(uuid4())
    other_id = str(uuid4())

    invalid_calls: tuple[Callable[[], None], ...] = (
        lambda: _persisted(self_id=self_id, status="completed"),
        lambda: _persisted(
            self_id=self_id,
            completed_at="2026-06-25T01:00:00Z",
        ),
        lambda: _persisted(
            self_id=self_id,
            status="completed",
            started_at="2026-06-25T02:00:00Z",
            completed_at="2026-06-25T01:00:00Z",
        ),
        lambda: _persisted(self_id=self_id, status="blocked"),
        lambda: _persisted(self_id=self_id, blockers=(other_id,)),
        lambda: _persisted(self_id=self_id, dependencies=(self_id,)),
        lambda: _persisted(
            self_id=self_id,
            dependencies=(other_id,),
            blockers=(other_id,),
            status="blocked",
        ),
        lambda: _persisted(self_id=self_id, verification="failed"),
        lambda: _persisted(
            self_id=self_id,
            evidence=(other_id,),
        ),
    )
    for invalid_call in invalid_calls:
        with pytest.raises(WorkItemValidationError):
            invalid_call()


def test_additional_helper_and_record_lookup_defenses(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_id = _project(repository)
        service = WorkItemService(repository)
        item = service.create(
            project_id=project_id,
            kind="task",
            title="Lookup item",
            description="Record lookup defense fixture.",
        )
        wrong = repository.create_record(record_type="other", metadata={})

        assert _require_record(repository, item.work_item_id).id == item.work_item_id
        with pytest.raises(WorkItemValidationError):
            _require_record(repository, str(uuid4()))
        with pytest.raises(WorkItemValidationError):
            _require_record(repository, wrong.id)

    with pytest.raises(WorkItemValidationError):
        _criteria(
            tuple(
                AcceptanceCriterion(str(index), "d", None, True)
                for index in range(MAX_LIST_ITEMS + 1)
            )
        )
    criterion = AcceptanceCriterion("evidence-kind", "Description", "record", False)
    assert _criteria((criterion,)) == (criterion,)
    with pytest.raises(WorkItemValidationError):
        _reference_ids("IDs", tuple(str(uuid4()) for _ in range(MAX_LINKS + 1)))
    with pytest.raises(WorkItemValidationError):
        _text("text", "x" * 21, 20)
    with pytest.raises(WorkItemValidationError):
        _token("token", None)


def test_active_secret_source_is_rejected_after_storage_tampering(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project_id = _project(repository)
        source = repository.create_record(record_type="source", metadata={})
        repository.connection.execute(
            "UPDATE records SET sensitivity = 'secret' WHERE id = ?",
            (source.id,),
        )
        with pytest.raises(WorkItemValidationError):
            WorkItemService(repository).create(
                project_id=project_id,
                kind="task",
                title="Secret source",
                description="Tampered source must not be portable.",
                source_ids=(source.id,),
            )
