from __future__ import annotations

from pathlib import Path

import pytest

import doll.continuity_preflight as preflight
from doll import state, workspace
from doll.capabilities import built_in_capability_registry
from doll.continuity_preflight import (
    CONTINUITY_PREFLIGHT_RULE_SET_ID,
    CONTINUITY_PREFLIGHT_RULE_SET_VERSION,
    ContinuityPreflightService,
    ContinuityPreflightValidationError,
)
from doll.procedure import ProcedureService
from doll.project_experience import ProjectExperienceService
from doll.project_state import ProjectInfo, ProjectService
from doll.settings import PermissionService, PolicyService
from doll.state_repository import StateRepository
from doll.work_item import WorkItemInfo, WorkItemService


def _workspace(tmp_path: Path, name: str = "workspace") -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(tmp_path / name)
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def _project(repository: StateRepository, name: str = "Continuity preflight") -> ProjectInfo:
    return ProjectService(repository).create_v2(
        name=name,
        description="Synthetic deterministic ContinuityPreflight fixture.",
        objective="Check accepted state before a proposed action without model reasoning.",
        in_scope=("read-only preflight",),
        out_of_scope=("execution authority",),
        success_criteria=("MCON-011 through MCON-013",),
        project_status="active",
        started_at="2026-08-16T00:00:00Z",
    )


def _work(repository: StateRepository, project_id: str, title: str) -> WorkItemInfo:
    return WorkItemService(repository).create(
        project_id=project_id,
        kind="task",
        title=title,
        description="Synthetic preflight work item.",
        priority=10,
    )


def _service(repository: StateRepository) -> ContinuityPreflightService:
    return ContinuityPreflightService(repository, built_in_capability_registry())


def test_imp_095_requires_read_only_repository_and_has_clear_baseline(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project = _project(repository)
        with pytest.raises(ContinuityPreflightValidationError, match="read-only"):
            _service(repository).check(
                project_id=project.project_id,
                proposed_action_class="project.inspect",
            )

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        before = repository.status().state_revision
        result = _service(repository).check(
            project_id=project.project_id,
            proposed_action_class="project.inspect",
        )
        after = repository.status().state_revision

    assert result.rule_set_id == CONTINUITY_PREFLIGHT_RULE_SET_ID
    assert result.rule_set_version == CONTINUITY_PREFLIGHT_RULE_SET_VERSION
    assert result.status == "clear"
    assert result.matched_record_ids == ()
    assert result.warning_codes == ()
    assert result.authoritative_blocker_ids == ()
    assert result.requires_confirmation is False
    assert after == before


def test_mcon_011_prior_failed_experience_is_evidence_linked_warning_only(
    tmp_path: Path,
) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project = _project(repository)
        work = _work(repository, project.project_id, "Retry bounded operation")
        failed = ProjectExperienceService(repository).record(
            project_id=project.project_id,
            work_item_id=work.work_item_id,
            event_kind="outcome",
            summary="The selected bounded operation failed in the synthetic fixture.",
            outcome="failed",
            occurred_at="2026-08-16T00:10:00Z",
            assertion_state="user_confirmed",
            actor_type="user",
        )

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        before = repository.status().state_revision
        result = _service(repository).check(
            project_id=project.project_id,
            work_item_id=work.work_item_id,
            proposed_action_class="bounded.retry",
        )
        after = repository.status().state_revision

    assert result.status == "warning"
    assert result.authoritative_blocker_ids == ()
    assert result.requires_confirmation is False
    assert failed.experience_id in result.matched_record_ids
    assert work.work_item_id in result.matched_record_ids
    assert "experience.prior_failure.user_confirmed" in result.warning_codes
    assert after == before


def test_mcon_012_existing_authority_remains_authoritative_and_explainable(
    tmp_path: Path,
) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project = _project(repository)
        blocker = _work(repository, project.project_id, "Resolve authoritative blocker")
        target = _work(repository, project.project_id, "Run guarded operation")
        target = WorkItemService(repository).transition(
            target.work_item_id,
            expected_revision=target.revision,
            to_status="blocked",
            blocked_by_ids=(blocker.work_item_id,),
        )
        policy = PolicyService(repository).create(
            key="continuity.synthetic-denial",
            rule="Synthetic fixture already classified by the caller as an applicable denial.",
            enabled=True,
        )
        procedure = ProcedureService(repository).create_draft(
            project_id=project.project_id,
            title="Required guarded procedure",
            purpose="Remain unapproved so preflight exposes the existing procedure state.",
            version=1,
            ordered_steps=("Synthetic bounded step",),
            validation_steps=("Check synthetic result",),
            rollback_steps=("Restore synthetic fixture",),
        )
        permission = PermissionService(repository).create(
            capability_id="adapter.fixed_process.example",
            scope={"kind": "project", "project_id": project.project_id},
            mode="ask",
        )

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        before = repository.status().state_revision
        result = _service(repository).check(
            project_id=project.project_id,
            work_item_id=target.work_item_id,
            proposed_action_class="guarded.process",
            capability_id="adapter.fixed_process.example",
            capability_version="1.0",
            permission_scope={"kind": "project", "project_id": project.project_id},
            applicable_policy_denial_ids=(policy.record_id,),
            required_procedure_ids=(procedure.procedure_id,),
        )
        after = repository.status().state_revision

    assert result.status == "blocked"
    assert result.requires_confirmation is True
    assert {
        policy.record_id,
        target.work_item_id,
        blocker.work_item_id,
        procedure.procedure_id,
    }.issubset(set(result.authoritative_blocker_ids))
    assert permission.record_id in result.matched_record_ids
    assert "policy.authoritative_denial" in result.warning_codes
    assert "work_item.blocked" in result.warning_codes
    assert "procedure.required_not_approved" in result.warning_codes
    assert "permission.user_action_required" in result.warning_codes
    assert "capability.high_risk_confirmation_required" in result.warning_codes
    assert after == before


def test_mcon_013_imported_and_model_proposed_failures_remain_advisory(
    tmp_path: Path,
) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project = _project(repository)
        experience = ProjectExperienceService(repository)
        user_failure = experience.record(
            project_id=project.project_id,
            event_kind="outcome",
            summary="The same synthetic operation failed.",
            outcome="failed",
            occurred_at="2026-08-16T00:20:00Z",
            assertion_state="user_confirmed",
            actor_type="user",
        )
        imported_failure = experience.record(
            project_id=project.project_id,
            event_kind="outcome",
            summary="The same synthetic operation failed.",
            outcome="failed",
            occurred_at="2026-08-16T00:21:00Z",
            assertion_state="imported_external",
            actor_type="importer",
        )
        model_failure = experience.record(
            project_id=project.project_id,
            event_kind="outcome",
            summary="The same synthetic operation failed.",
            outcome="failed",
            occurred_at="2026-08-16T00:22:00Z",
            assertion_state="model_proposed",
            actor_type="model",
        )

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        result = _service(repository).check(
            project_id=project.project_id,
            proposed_action_class="same.synthetic.operation",
        )

    assert result.status == "warning"
    assert result.authoritative_blocker_ids == ()
    assert result.requires_confirmation is False
    assert {
        user_failure.experience_id,
        imported_failure.experience_id,
        model_failure.experience_id,
    }.issubset(set(result.matched_record_ids))
    assert "experience.prior_failure.user_confirmed" in result.warning_codes
    assert "experience.prior_failure.imported_advisory" in result.warning_codes
    assert "experience.prior_failure.model_advisory" in result.warning_codes


def test_imp_095_superseded_and_unrelated_failures_are_not_replayed(
    tmp_path: Path,
) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project = _project(repository)
        selected = _work(repository, project.project_id, "Selected work")
        other = _work(repository, project.project_id, "Other work")
        experience = ProjectExperienceService(repository)
        failed = experience.record(
            project_id=project.project_id,
            work_item_id=selected.work_item_id,
            event_kind="outcome",
            summary="Old failed attempt.",
            outcome="failed",
            occurred_at="2026-08-16T00:30:00Z",
            assertion_state="user_confirmed",
            actor_type="user",
        )
        replacement = experience.correct(
            failed.experience_id,
            summary="The corrected result worked.",
            outcome="worked",
            occurred_at="2026-08-16T00:31:00Z",
            assertion_state="user_confirmed",
            actor_type="user",
        )
        unrelated = experience.record(
            project_id=project.project_id,
            work_item_id=other.work_item_id,
            event_kind="outcome",
            summary="Other work failed.",
            outcome="failed",
            occurred_at="2026-08-16T00:32:00Z",
            assertion_state="user_confirmed",
            actor_type="user",
        )

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        result = _service(repository).check(
            project_id=project.project_id,
            work_item_id=selected.work_item_id,
            proposed_action_class="selected.work",
        )

    assert result.status == "clear"
    assert failed.experience_id not in result.matched_record_ids
    assert replacement.experience_id not in result.matched_record_ids
    assert unrelated.experience_id not in result.matched_record_ids
    assert selected.work_item_id in result.matched_record_ids


def test_imp_095_permission_denial_and_scoped_permission_are_not_grants(
    tmp_path: Path,
) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project = _project(repository)

    record_scope = {"kind": "record", "record_id": project.project_id}
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        denied = _service(repository).check(
            project_id=project.project_id,
            proposed_action_class="state.read",
            capability_id="state.read",
            capability_version="1.0",
            permission_scope=record_scope,
        )
    assert denied.status == "blocked"
    assert denied.authoritative_blocker_ids == ()
    assert "permission.denied.no_record" in denied.warning_codes

    with state.open_state_repository(initialized.root) as repository:
        permission = PermissionService(repository).create(
            capability_id="state.read",
            scope=record_scope,
            mode="scoped",
        )
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        allowed_boundary = _service(repository).check(
            project_id=project.project_id,
            proposed_action_class="state.read",
            capability_id="state.read",
            capability_version="1.0",
            permission_scope=record_scope,
        )
    assert allowed_boundary.status == "clear"
    assert permission.record_id in allowed_boundary.matched_record_ids
    assert allowed_boundary.authoritative_blocker_ids == ()
    assert allowed_boundary.requires_confirmation is False


def test_imp_095_validates_explicit_scope_without_interpreting_policy_text(
    tmp_path: Path,
) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project = _project(repository)
        disabled = PolicyService(repository).create(
            key="continuity.disabled",
            rule="This text is never parsed by ContinuityPreflight.",
            enabled=False,
        )

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        service = _service(repository)
        with pytest.raises(ContinuityPreflightValidationError, match="active and enabled"):
            service.check(
                project_id=project.project_id,
                proposed_action_class="policy.test",
                applicable_policy_denial_ids=(disabled.record_id,),
            )
        with pytest.raises(ContinuityPreflightValidationError, match="duplicate"):
            service.check(
                project_id=project.project_id,
                proposed_action_class="policy.test",
                applicable_policy_denial_ids=(disabled.record_id, disabled.record_id),
            )
        with pytest.raises(ContinuityPreflightValidationError, match="action class"):
            service.check(
                project_id=project.project_id,
                proposed_action_class="bad action",
            )
        with pytest.raises(ContinuityPreflightValidationError, match="supplied together"):
            service.check(
                project_id=project.project_id,
                proposed_action_class="capability.test",
                capability_id="state.read",
            )
        with pytest.raises(ContinuityPreflightValidationError, match="requires a capability"):
            service.check(
                project_id=project.project_id,
                proposed_action_class="capability.test",
                permission_scope={"kind": "record", "record_id": project.project_id},
            )
        with pytest.raises(ContinuityPreflightValidationError, match="not registered"):
            service.check(
                project_id=project.project_id,
                proposed_action_class="capability.test",
                capability_id="missing.capability",
                capability_version="1.0",
            )


def test_imp_095_project_and_procedure_scope_fail_closed(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        first = _project(repository, "First project")
        second = _project(repository, "Second project")
        other_work = _work(repository, second.project_id, "Other project work")
        other_procedure = ProcedureService(repository).create_approved(
            project_id=second.project_id,
            title="Other project procedure",
            purpose="Synthetic cross-project fixture.",
            version=1,
            ordered_steps=("Synthetic step",),
            validation_steps=("Synthetic validation",),
            rollback_steps=("Synthetic rollback",),
        )

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        service = _service(repository)
        with pytest.raises(ContinuityPreflightValidationError, match="another project"):
            service.check(
                project_id=first.project_id,
                work_item_id=other_work.work_item_id,
                proposed_action_class="cross.project",
            )
        with pytest.raises(ContinuityPreflightValidationError, match="another project"):
            service.check(
                project_id=first.project_id,
                proposed_action_class="cross.project",
                required_procedure_ids=(other_procedure.procedure_id,),
            )


def test_imp_095_experience_scope_limit_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        project = _project(repository)
        ProjectExperienceService(repository).record(
            project_id=project.project_id,
            event_kind="outcome",
            summary="One bounded failure.",
            outcome="failed",
            occurred_at="2026-08-16T00:40:00Z",
            assertion_state="deterministic_system",
            actor_type="system",
        )

    monkeypatch.setattr(preflight, "MAX_PROJECT_EXPERIENCES", 0)
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        with pytest.raises(ContinuityPreflightValidationError, match="bounded preflight limit"):
            _service(repository).check(
                project_id=project.project_id,
                proposed_action_class="bounded.limit",
            )
