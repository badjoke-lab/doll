"""Deterministic read-only continuity checks before a proposed action proceeds."""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from doll.capabilities import CapabilityRegistry, CapabilityRiskTier
from doll.procedure import ProcedureError, ProcedureService
from doll.project_experience import ProjectExperienceError, ProjectExperienceService
from doll.project_state import ProjectDecisionError, ProjectService
from doll.settings import PermissionService, PolicyService, SettingsError
from doll.state import StateCorruptError, StateError
from doll.state_repository import StateRepository
from doll.work_item import WorkItemError, WorkItemService

ContinuityPreflightStatus = Literal[
    "clear",
    "warning",
    "confirmation_required",
    "blocked",
]

CONTINUITY_PREFLIGHT_RULE_SET_ID = "doll.continuity-preflight"
CONTINUITY_PREFLIGHT_RULE_SET_VERSION = 1
MAX_EXPLICIT_LINKS = 64
MAX_PROJECT_EXPERIENCES = 500
MAX_ACTION_CLASS_LENGTH = 120
_ACTION_CLASS = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")


class ContinuityPreflightError(StateError):
    """Base class for deterministic continuity-preflight failures."""


class ContinuityPreflightValidationError(ContinuityPreflightError):
    """Raised when a bounded preflight request cannot be evaluated safely."""


@dataclass(frozen=True, slots=True)
class ContinuityPreflightResult:
    """Read-only pre-action result that never grants execution authority."""

    rule_set_id: str
    rule_set_version: int
    project_id: str
    proposed_action_class: str
    status: ContinuityPreflightStatus
    matched_record_ids: tuple[str, ...]
    warning_codes: tuple[str, ...]
    authoritative_blocker_ids: tuple[str, ...]
    requires_confirmation: bool


@dataclass(slots=True)
class ContinuityPreflightService:
    """Compose existing authority and advisory history without mutating Doll State."""

    repository: StateRepository
    capability_registry: CapabilityRegistry

    def check(
        self,
        *,
        project_id: str,
        proposed_action_class: str,
        work_item_id: str | None = None,
        capability_id: str | None = None,
        capability_version: str | None = None,
        permission_scope: dict[str, object] | None = None,
        applicable_policy_denial_ids: Sequence[str] = (),
        required_procedure_ids: Sequence[str] = (),
    ) -> ContinuityPreflightResult:
        """Evaluate one explicit project/action scope with deterministic bounded rules."""

        if not self.repository.read_only:
            raise ContinuityPreflightValidationError(
                "ContinuityPreflight requires a read-only repository"
            )
        safe_action = _action_class(proposed_action_class)
        safe_policy_ids = _explicit_ids(
            "applicable policy denial IDs", applicable_policy_denial_ids
        )
        safe_procedure_ids = _explicit_ids("required procedure IDs", required_procedure_ids)

        try:
            project = ProjectService(self.repository).get(project_id)
        except (KeyError, ProjectDecisionError) as exc:
            raise ContinuityPreflightValidationError("preflight project is invalid") from exc
        if project.lifecycle_status != "active":
            raise ContinuityPreflightValidationError("preflight project is not active")

        matched: set[str] = set()
        warnings: set[str] = set()
        blockers: set[str] = set()
        requires_confirmation = False

        work_item = None
        if work_item_id is not None:
            try:
                work_item = WorkItemService(self.repository).get(work_item_id)
            except (KeyError, WorkItemError) as exc:
                raise ContinuityPreflightValidationError("preflight work item is invalid") from exc
            if work_item.project_id != project.project_id:
                raise ContinuityPreflightValidationError(
                    "preflight work item belongs to another project"
                )
            if work_item.lifecycle_status != "active":
                raise ContinuityPreflightValidationError("preflight work item is not active")
            matched.add(work_item.work_item_id)
            if work_item.work_status == "blocked":
                blockers.add(work_item.work_item_id)
                blockers.update(work_item.blocked_by_ids)
                matched.update(work_item.blocked_by_ids)
                warnings.add("work_item.blocked")
            for dependency_id in work_item.depends_on_ids:
                try:
                    dependency = WorkItemService(self.repository).get(dependency_id)
                except (KeyError, WorkItemError) as exc:
                    raise ContinuityPreflightValidationError(
                        "preflight work-item dependency is invalid"
                    ) from exc
                if dependency.project_id != project.project_id:
                    raise ContinuityPreflightValidationError(
                        "preflight work-item dependency belongs to another project"
                    )
                matched.add(dependency.work_item_id)
                if dependency.lifecycle_status != "active" or dependency.work_status != "completed":
                    blockers.add(dependency.work_item_id)
                    warnings.add("work_item.dependency_incomplete")

        for policy_id in safe_policy_ids:
            try:
                policy = PolicyService(self.repository).get(policy_id)
            except (KeyError, SettingsError) as exc:
                raise ContinuityPreflightValidationError(
                    "applicable denial policy is invalid"
                ) from exc
            if policy.status != "active" or not policy.enabled:
                raise ContinuityPreflightValidationError(
                    "applicable denial policy is not active and enabled"
                )
            if policy.sensitivity == "secret":
                raise ContinuityPreflightValidationError(
                    "secret policy cannot be exposed through continuity preflight"
                )
            matched.add(policy.record_id)
            blockers.add(policy.record_id)
            warnings.add("policy.authoritative_denial")

        for procedure_id in safe_procedure_ids:
            try:
                procedure = ProcedureService(self.repository).get(procedure_id)
            except (KeyError, ProcedureError) as exc:
                raise ContinuityPreflightValidationError(
                    "required procedure is invalid"
                ) from exc
            if procedure.project_id != project.project_id:
                raise ContinuityPreflightValidationError(
                    "required procedure belongs to another project"
                )
            if procedure.lifecycle_status != "active":
                raise ContinuityPreflightValidationError("required procedure is not active")
            if procedure.sensitivity == "secret":
                raise ContinuityPreflightValidationError(
                    "secret procedure cannot be exposed through continuity preflight"
                )
            matched.add(procedure.procedure_id)
            if procedure.procedure_status != "approved":
                blockers.add(procedure.procedure_id)
                warnings.add("procedure.required_not_approved")

        if (capability_id is None) != (capability_version is None):
            raise ContinuityPreflightValidationError(
                "capability ID and version must be supplied together"
            )
        if capability_id is None:
            if permission_scope is not None:
                raise ContinuityPreflightValidationError(
                    "permission scope requires a capability"
                )
        else:
            definition = self.capability_registry.get(capability_id, capability_version or "")
            if definition is None:
                raise ContinuityPreflightValidationError(
                    "preflight capability is not registered at the requested version"
                )
            if not definition.release_available:
                warnings.add("capability.release_excluded")
            if definition.risk_tier is CapabilityRiskTier.HIGH_RISK:
                requires_confirmation = True
                warnings.add("capability.high_risk_confirmation_required")
            if definition.permission_scope_kind == "none":
                if permission_scope not in (None, {"kind": "none"}):
                    raise ContinuityPreflightValidationError(
                        "permission scope is incompatible with the capability"
                    )
            else:
                if permission_scope is None:
                    raise ContinuityPreflightValidationError(
                        "capability requires an explicit permission scope"
                    )
                try:
                    permission = PermissionService(self.repository).resolve(
                        capability_id=definition.capability_id,
                        scope=permission_scope,
                    )
                except SettingsError as exc:
                    raise ContinuityPreflightValidationError(
                        "capability permission could not be resolved"
                    ) from exc
                if permission.scope.get("kind") != definition.permission_scope_kind:
                    raise ContinuityPreflightValidationError(
                        "permission scope is incompatible with the capability"
                    )
                if permission.record_id is not None:
                    matched.add(permission.record_id)
                if permission.effective_mode == "ask":
                    requires_confirmation = True
                    warnings.add("permission.user_action_required")
                elif permission.effective_mode not in {"allow_once", "scoped"}:
                    if permission.record_id is not None:
                        blockers.add(permission.record_id)
                    warnings.add(f"permission.denied.{permission.reason}")
            if not definition.release_available:
                warnings.add("capability.not_release_available")

        self._add_failed_experience_warnings(
            project_id=project.project_id,
            work_item_id=work_item.work_item_id if work_item is not None else None,
            matched=matched,
            warnings=warnings,
        )

        blocked_without_record = any(
            code.startswith("permission.denied.") or code == "capability.not_release_available"
            for code in warnings
        )
        if blockers or blocked_without_record:
            status: ContinuityPreflightStatus = "blocked"
        elif requires_confirmation:
            status = "confirmation_required"
        elif warnings:
            status = "warning"
        else:
            status = "clear"

        return ContinuityPreflightResult(
            rule_set_id=CONTINUITY_PREFLIGHT_RULE_SET_ID,
            rule_set_version=CONTINUITY_PREFLIGHT_RULE_SET_VERSION,
            project_id=project.project_id,
            proposed_action_class=safe_action,
            status=status,
            matched_record_ids=tuple(sorted(matched)),
            warning_codes=tuple(sorted(warnings)),
            authoritative_blocker_ids=tuple(sorted(blockers)),
            requires_confirmation=requires_confirmation,
        )

    def _add_failed_experience_warnings(
        self,
        *,
        project_id: str,
        work_item_id: str | None,
        matched: set[str],
        warnings: set[str],
    ) -> None:
        try:
            row = self.repository.connection.execute(
                "SELECT COUNT(*) FROM records "
                "WHERE record_type = 'project_experience' AND status = 'active'"
            ).fetchone()
        except sqlite3.DatabaseError as exc:
            raise StateCorruptError("project experiences are unreadable") from exc
        if row is None or not isinstance(row[0], int):
            raise StateCorruptError("project experience count is unreadable")
        if row[0] > MAX_PROJECT_EXPERIENCES:
            raise ContinuityPreflightValidationError(
                "project experience scope exceeds the bounded preflight limit"
            )
        try:
            experiences = ProjectExperienceService(self.repository).list(
                project_id=project_id,
                limit=MAX_PROJECT_EXPERIENCES,
            )
        except ProjectExperienceError as exc:
            raise ContinuityPreflightValidationError(
                "project experience could not be inspected"
            ) from exc
        superseded_ids = {
            item.supersedes_id for item in experiences if item.supersedes_id is not None
        }
        for experience in experiences:
            if experience.experience_id in superseded_ids or experience.outcome != "failed":
                continue
            if work_item_id is None:
                relevant = experience.work_item_id is None
            else:
                relevant = experience.work_item_id in {None, work_item_id}
            if not relevant:
                continue
            matched.add(experience.experience_id)
            warnings.add(_experience_warning_code(experience.assertion_state))


def _action_class(value: str) -> str:
    if not isinstance(value, str):
        raise ContinuityPreflightValidationError("proposed action class must be text")
    normalized = value.strip()
    if (
        not normalized
        or len(normalized) > MAX_ACTION_CLASS_LENGTH
        or _ACTION_CLASS.fullmatch(normalized) is None
    ):
        raise ContinuityPreflightValidationError("proposed action class is invalid")
    return normalized


def _explicit_ids(name: str, values: Sequence[str]) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise ContinuityPreflightValidationError(f"{name} must be a sequence")
    items = tuple(values)
    if len(items) > MAX_EXPLICIT_LINKS:
        raise ContinuityPreflightValidationError(f"{name} exceeds the bounded limit")
    if len(items) != len(set(items)):
        raise ContinuityPreflightValidationError(f"{name} contains duplicate IDs")
    if any(not isinstance(item, str) or not item for item in items):
        raise ContinuityPreflightValidationError(f"{name} contains an invalid ID")
    return items


def _experience_warning_code(assertion_state: str) -> str:
    return {
        "user_recorded": "experience.prior_failure.user_recorded",
        "user_confirmed": "experience.prior_failure.user_confirmed",
        "deterministic_system": "experience.prior_failure.deterministic_system",
        "imported_external": "experience.prior_failure.imported_advisory",
        "model_proposed": "experience.prior_failure.model_advisory",
    }.get(assertion_state, "experience.prior_failure.unknown_advisory")
