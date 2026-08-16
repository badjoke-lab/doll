from __future__ import annotations

import sqlite3
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest

import doll.continuity_preflight as preflight
from doll import state, workspace
from doll.capabilities import CapabilityRegistry, built_in_capability_registry
from doll.continuity_preflight import (
    ContinuityPreflightService,
    ContinuityPreflightValidationError,
)
from doll.procedure import ProcedureService
from doll.project_experience import (
    ProjectExperienceService,
    ProjectExperienceValidationError,
)
from doll.project_state import ProjectInfo, ProjectService
from doll.settings import PermissionService, PolicyService, SettingsError
from doll.state import StateCorruptError
from doll.state_repository import StateRepository
from doll.work_item import WorkItemInfo, WorkItemService

_MISSING_ID = "00000000-0000-0000-0000-000000000001"


def _workspace(tmp_path: Path) -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(tmp_path / "workspace")
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def _project(repository: StateRepository, name: str = "Edge project") -> ProjectInfo:
    return ProjectService(repository).create_v2(
        name=name,
        description="Synthetic ContinuityPreflight edge fixture.",
        objective="Exercise deterministic fail-closed branches.",
        in_scope=("edge validation",),
        out_of_scope=("execution",),
        success_criteria=("edge rules are covered",),
        project_status="active",
        started_at="2026-08-16T01:00:00Z",
    )


def _work(
    repository: StateRepository,
    project_id: str,
    title: str,
    *,
    depends_on_ids: tuple[str, ...] = (),
) -> WorkItemInfo:
    return WorkItemService(repository).create(
        project_id=project_id,
        kind="task",
        title=title,
        description="Synthetic ContinuityPreflight edge work item.",
        priority=20,
        depends_on_ids=depends_on_ids,
    )


def _service(repository: StateRepository) -> ContinuityPreflightService:
    return ContinuityPreflightService(repository, built_in_capability_registry())


def test_imp_095_project_and_work_lifecycle_errors_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project = _project(repository)
        work = _work(repository, project.project_id, "Selected work")

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        service = _service(repository)
        with pytest.raises(ContinuityPreflightValidationError, match="project is invalid"):
            service.check(project_id=_MISSING_ID, proposed_action_class="edge.project")
        with pytest.raises(ContinuityPreflightValidationError, match="work item is invalid"):
            service.check(
                project_id=project.project_id,
                work_item_id=_MISSING_ID,
                proposed_action_class="edge.work",
            )

        monkeypatch.setattr(
            ProjectService,
            "get",
            lambda _self, _record_id: replace(project, lifecycle_status="archived"),
        )
        with pytest.raises(ContinuityPreflightValidationError, match="project is not active"):
            service.check(project_id=project.project_id, proposed_action_class="edge.project")
        monkeypatch.undo()

        monkeypatch.setattr(
            WorkItemService,
            "get",
            lambda _self, _record_id: replace(work, lifecycle_status="archived"),
        )
        with pytest.raises(ContinuityPreflightValidationError, match="work item is not active"):
            service.check(
                project_id=project.project_id,
                work_item_id=work.work_item_id,
                proposed_action_class="edge.work",
            )


def test_imp_095_dependency_state_is_authoritative(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project = _project(repository)
        dependency = _work(repository, project.project_id, "Dependency")
        target = _work(
            repository,
            project.project_id,
            "Dependent target",
            depends_on_ids=(dependency.work_item_id,),
        )

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        blocked = _service(repository).check(
            project_id=project.project_id,
            work_item_id=target.work_item_id,
            proposed_action_class="edge.dependency",
        )
    assert blocked.status == "blocked"
    assert dependency.work_item_id in blocked.authoritative_blocker_ids
    assert "work_item.dependency_incomplete" in blocked.warning_codes

    with state.open_state_repository(initialized.root) as repository:
        dependency = WorkItemService(repository).get(dependency.work_item_id)
        dependency = WorkItemService(repository).transition(
            dependency.work_item_id,
            expected_revision=dependency.revision,
            to_status="in_progress",
            occurred_at="2026-08-16T01:10:00Z",
        )
        WorkItemService(repository).transition(
            dependency.work_item_id,
            expected_revision=dependency.revision,
            to_status="completed",
            occurred_at="2026-08-16T01:11:00Z",
        )

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        clear = _service(repository).check(
            project_id=project.project_id,
            work_item_id=target.work_item_id,
            proposed_action_class="edge.dependency",
        )
    assert clear.status == "clear"
    assert dependency.work_item_id in clear.matched_record_ids


def test_imp_095_dependency_lookup_and_cross_project_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        first = _project(repository, "First")
        second = _project(repository, "Second")
        selected = _work(repository, first.project_id, "Selected")
        other = _work(repository, second.project_id, "Other")
        synthetic = replace(selected, depends_on_ids=(_MISSING_ID,))

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        original_get = WorkItemService.get

        def missing_dependency(self: WorkItemService, record_id: str) -> WorkItemInfo:
            if record_id == selected.work_item_id:
                return synthetic
            return original_get(self, record_id)

        monkeypatch.setattr(WorkItemService, "get", missing_dependency)
        with pytest.raises(ContinuityPreflightValidationError, match="dependency is invalid"):
            _service(repository).check(
                project_id=first.project_id,
                work_item_id=selected.work_item_id,
                proposed_action_class="edge.dependency",
            )
        monkeypatch.undo()

        synthetic_cross = replace(selected, depends_on_ids=(other.work_item_id,))

        def cross_dependency(self: WorkItemService, record_id: str) -> WorkItemInfo:
            if record_id == selected.work_item_id:
                return synthetic_cross
            return original_get(self, record_id)

        monkeypatch.setattr(WorkItemService, "get", cross_dependency)
        with pytest.raises(ContinuityPreflightValidationError, match="dependency belongs"):
            _service(repository).check(
                project_id=first.project_id,
                work_item_id=selected.work_item_id,
                proposed_action_class="edge.dependency",
            )


def test_imp_095_policy_and_procedure_record_boundaries(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project = _project(repository)
        secret_policy = PolicyService(repository).create(
            key="continuity.secret-policy",
            rule="Synthetic classified denial without secret material.",
            sensitivity="secret",
        )
        approved = ProcedureService(repository).create_approved(
            project_id=project.project_id,
            title="Approved procedure",
            purpose="Exercise the approved procedure branch.",
            version=1,
            ordered_steps=("Perform bounded synthetic step",),
            validation_steps=("Validate bounded synthetic step",),
            rollback_steps=("Rollback bounded synthetic step",),
        )
        secret_procedure = ProcedureService(repository).create_approved(
            project_id=project.project_id,
            title="Secret-labeled procedure",
            purpose="Exercise secret-labelled record exclusion without secret material.",
            version=1,
            ordered_steps=("Perform bounded synthetic step",),
            validation_steps=("Validate bounded synthetic step",),
            rollback_steps=("Rollback bounded synthetic step",),
            sensitivity="secret",
        )

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        service = _service(repository)
        with pytest.raises(ContinuityPreflightValidationError, match="denial policy is invalid"):
            service.check(
                project_id=project.project_id,
                proposed_action_class="edge.policy",
                applicable_policy_denial_ids=(_MISSING_ID,),
            )
        with pytest.raises(ContinuityPreflightValidationError, match="secret policy"):
            service.check(
                project_id=project.project_id,
                proposed_action_class="edge.policy",
                applicable_policy_denial_ids=(secret_policy.record_id,),
            )
        with pytest.raises(ContinuityPreflightValidationError, match="procedure is invalid"):
            service.check(
                project_id=project.project_id,
                proposed_action_class="edge.procedure",
                required_procedure_ids=(_MISSING_ID,),
            )
        with pytest.raises(ContinuityPreflightValidationError, match="secret procedure"):
            service.check(
                project_id=project.project_id,
                proposed_action_class="edge.procedure",
                required_procedure_ids=(secret_procedure.procedure_id,),
            )
        clear = service.check(
            project_id=project.project_id,
            proposed_action_class="edge.procedure",
            required_procedure_ids=(approved.procedure_id,),
        )
    assert clear.status == "clear"
    assert approved.procedure_id in clear.matched_record_ids


def test_imp_095_inactive_procedure_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project = _project(repository)
        procedure = ProcedureService(repository).create_approved(
            project_id=project.project_id,
            title="Synthetic procedure",
            purpose="Exercise inactive procedure validation.",
            version=1,
            ordered_steps=("Synthetic step",),
            validation_steps=("Synthetic validation",),
            rollback_steps=("Synthetic rollback",),
        )

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        monkeypatch.setattr(
            ProcedureService,
            "get",
            lambda _self, _record_id: replace(procedure, lifecycle_status="archived"),
        )
        with pytest.raises(ContinuityPreflightValidationError, match="procedure is not active"):
            _service(repository).check(
                project_id=project.project_id,
                proposed_action_class="edge.procedure",
                required_procedure_ids=(procedure.procedure_id,),
            )


def test_imp_095_capability_scope_confirmation_and_release_boundaries(
    tmp_path: Path,
) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project = _project(repository)
        PermissionService(repository).create(
            capability_id="adapter.fixed_process.example",
            scope={"kind": "project", "project_id": project.project_id},
            mode="scoped",
        )

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        service = _service(repository)
        with pytest.raises(ContinuityPreflightValidationError, match="incompatible"):
            service.check(
                project_id=project.project_id,
                proposed_action_class="edge.compute",
                capability_id="compute.transform",
                capability_version="1.0",
                permission_scope={"kind": "record", "record_id": project.project_id},
            )
        with pytest.raises(ContinuityPreflightValidationError, match="explicit permission scope"):
            service.check(
                project_id=project.project_id,
                proposed_action_class="edge.read",
                capability_id="state.read",
                capability_version="1.0",
            )
        with pytest.raises(ContinuityPreflightValidationError, match="incompatible"):
            service.check(
                project_id=project.project_id,
                proposed_action_class="edge.read",
                capability_id="state.read",
                capability_version="1.0",
                permission_scope={"kind": "project", "project_id": project.project_id},
            )
        tier3_definition = next(
            item
            for item in built_in_capability_registry().definitions()
            if item.capability_id == "adapter.fixed_process.example"
        )
        confirmation = ContinuityPreflightService(
            repository,
            CapabilityRegistry((replace(tier3_definition, release_available=True),)),
        ).check(
            project_id=project.project_id,
            proposed_action_class="edge.high-risk",
            capability_id="adapter.fixed_process.example",
            capability_version="1.0",
            permission_scope={"kind": "project", "project_id": project.project_id},
        )
        compute = service.check(
            project_id=project.project_id,
            proposed_action_class="edge.compute",
            capability_id="compute.transform",
            capability_version="1.0",
            permission_scope={"kind": "none"},
        )

        base_definition = next(
            item
            for item in built_in_capability_registry().definitions()
            if item.capability_id == "compute.transform"
        )
        release_excluded = ContinuityPreflightService(
            repository,
            CapabilityRegistry((replace(base_definition, release_available=False),)),
        ).check(
            project_id=project.project_id,
            proposed_action_class="edge.release",
            capability_id="compute.transform",
            capability_version="1.0",
            permission_scope={"kind": "none"},
        )

    assert confirmation.status == "confirmation_required"
    assert confirmation.requires_confirmation is True
    assert "capability.high_risk_confirmation_required" in confirmation.warning_codes
    assert compute.status == "clear"
    assert release_excluded.status == "blocked"
    assert "capability.release_excluded" in release_excluded.warning_codes


def test_imp_095_permission_resolution_errors_and_denied_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project = _project(repository)
        scope: dict[str, object] = {"kind": "record", "record_id": project.project_id}
        denied_permission = PermissionService(repository).create(
            capability_id="state.read",
            scope=scope,
            mode="denied",
        )

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        denied = _service(repository).check(
            project_id=project.project_id,
            proposed_action_class="edge.permission",
            capability_id="state.read",
            capability_version="1.0",
            permission_scope=scope,
        )
        assert denied.status == "blocked"
        assert denied_permission.record_id in denied.authoritative_blocker_ids

        def fail_resolve(
            _self: PermissionService,
            *,
            capability_id: str,
            scope: dict[str, object],
        ) -> object:
            del capability_id, scope
            raise SettingsError("synthetic permission failure")

        monkeypatch.setattr(PermissionService, "resolve", fail_resolve)
        with pytest.raises(ContinuityPreflightValidationError, match="could not be resolved"):
            _service(repository).check(
                project_id=project.project_id,
                proposed_action_class="edge.permission",
                capability_id="state.read",
                capability_version="1.0",
                permission_scope=scope,
            )


def test_imp_095_project_experience_read_failures_are_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project = _project(repository)

    with state.open_state_repository(initialized.root, read_only=True) as repository:

        def fail_list(
            _self: ProjectExperienceService,
            *,
            project_id: str | None = None,
            include_archived: bool = False,
            limit: int = 100,
        ) -> object:
            del project_id, include_archived, limit
            raise ProjectExperienceValidationError("synthetic experience failure")

        monkeypatch.setattr(ProjectExperienceService, "list", fail_list)
        with pytest.raises(ContinuityPreflightValidationError, match="could not be inspected"):
            _service(repository).check(
                project_id=project.project_id,
                proposed_action_class="edge.experience",
            )


def test_imp_095_corrupt_experience_count_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project = _project(repository)

    class _BrokenCursor:
        def __init__(self, row: object) -> None:
            self._row = row

        def fetchone(self) -> object:
            return self._row

    class _BrokenConnection:
        def __init__(self, row: object = None, *, database_error: bool = False) -> None:
            self._row = row
            self._database_error = database_error

        def execute(self, _query: str) -> _BrokenCursor:
            if self._database_error:
                raise sqlite3.DatabaseError("synthetic database failure")
            return _BrokenCursor(self._row)

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        monkeypatch.setattr(
            ProjectService,
            "get",
            lambda _self, _record_id: project,
        )
        original_connection = repository.connection
        repository.connection = cast(sqlite3.Connection, _BrokenConnection(database_error=True))
        with pytest.raises(StateCorruptError, match="project experiences are unreadable"):
            _service(repository).check(
                project_id=project.project_id,
                proposed_action_class="edge.database",
            )
        repository.connection = cast(sqlite3.Connection, _BrokenConnection(row=None))
        with pytest.raises(StateCorruptError, match="count is unreadable"):
            _service(repository).check(
                project_id=project.project_id,
                proposed_action_class="edge.database",
            )
        repository.connection = original_connection


def test_imp_095_input_helpers_cover_bounded_fail_closed_cases(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project = _project(repository)

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        service = _service(repository)
        with pytest.raises(ContinuityPreflightValidationError, match="must be text"):
            service.check(
                project_id=project.project_id,
                proposed_action_class=cast(str, 123),
            )
        with pytest.raises(ContinuityPreflightValidationError, match="action class is invalid"):
            service.check(
                project_id=project.project_id,
                proposed_action_class="x" * (preflight.MAX_ACTION_CLASS_LENGTH + 1),
            )
        with pytest.raises(ContinuityPreflightValidationError, match="must be a sequence"):
            service.check(
                project_id=project.project_id,
                proposed_action_class="edge.ids",
                applicable_policy_denial_ids=cast(tuple[str, ...], "not-a-sequence"),
            )
        with pytest.raises(ContinuityPreflightValidationError, match="bounded limit"):
            service.check(
                project_id=project.project_id,
                proposed_action_class="edge.ids",
                required_procedure_ids=tuple(
                    f"id-{index}" for index in range(preflight.MAX_EXPLICIT_LINKS + 1)
                ),
            )
        with pytest.raises(ContinuityPreflightValidationError, match="invalid ID"):
            service.check(
                project_id=project.project_id,
                proposed_action_class="edge.ids",
                required_procedure_ids=("",),
            )

    assert preflight._experience_warning_code("unknown") == (
        "experience.prior_failure.unknown_advisory"
    )
