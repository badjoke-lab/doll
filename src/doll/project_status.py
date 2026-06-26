"""Deterministic read-only project status derived from authoritative records."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import cast
from uuid import UUID

from doll.checkpoint import (
    CheckpointCorruptError,
    ProjectCheckpointInfo,
    ProjectCheckpointService,
)
from doll.procedure import ProcedureCorruptError, ProcedureInfo, ProcedureService
from doll.project_state import (
    DecisionInfo,
    DecisionService,
    ProjectDecisionCorruptError,
    ProjectInfo,
    ProjectService,
)
from doll.settings import PolicyInfo, PolicyService, SettingsCorruptError
from doll.state import RecordSensitivity, StateError
from doll.state_repository import StateRepository
from doll.work_item import WorkItemCorruptError, WorkItemInfo, WorkItemService

PROJECT_STATUS_SCHEMA = "doll.project-status.v1"


class ProjectStatusError(StateError):
    """Base class for derived project-status failures."""


class ProjectStatusValidationError(ProjectStatusError):
    """Raised when a project cannot be selected for normal status output."""


class ProjectStatusCorruptError(ProjectStatusError):
    """Raised when authoritative records required by status are malformed."""


@dataclass(frozen=True, slots=True)
class StatusWorkItem:
    work_item_id: str
    kind: str
    title: str
    work_status: str
    priority: int
    blocked_by_ids: tuple[str, ...]
    verification_state: str
    revision: int


@dataclass(frozen=True, slots=True)
class PendingValidation:
    work_item_id: str
    title: str
    work_status: str
    verification_state: str
    blocking_criterion_ids: tuple[str, ...]
    verification_evidence_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class StatusCheckpoint:
    checkpoint_id: str
    as_of: str
    current_phase: str
    current_goal: str
    confirmation_state: str
    freshness: str | None
    basis_fingerprint: str | None
    required_validation_ids: tuple[str, ...]
    revision: int


@dataclass(frozen=True, slots=True)
class StatusDecision:
    decision_id: str
    decision: str
    reason: str
    decided_at: str
    constraints: tuple[str, ...]
    revision: int


@dataclass(frozen=True, slots=True)
class StatusPolicy:
    policy_id: str
    key: str
    rule: str
    enabled: bool
    revision: int


@dataclass(frozen=True, slots=True)
class StatusProcedure:
    procedure_id: str
    title: str
    purpose: str
    version: int
    last_verified_at: str | None
    revision: int


@dataclass(frozen=True, slots=True)
class ProjectStatusInfo:
    status_schema: str
    project_id: str
    project_name: str
    objective: str | None
    objective_available: bool
    project_status: str
    project_revision: int
    current_phase: str | None
    current_goal: str | None
    active_work: tuple[StatusWorkItem, ...]
    next_ready_work: tuple[StatusWorkItem, ...]
    blocked_work: tuple[StatusWorkItem, ...]
    pending_required_validation: tuple[PendingValidation, ...]
    latest_checkpoint: StatusCheckpoint | None
    governing_decisions: tuple[StatusDecision, ...]
    governing_policies: tuple[StatusPolicy, ...]
    approved_procedures: tuple[StatusProcedure, ...]
    omitted_record_counts: dict[str, int]
    source_state_revision: int


@dataclass(slots=True)
class ProjectStatusService:
    repository: StateRepository

    def build(self, project_id: str) -> ProjectStatusInfo:
        """Derive one project-scoped status without mutating authoritative state."""

        safe_project_id = _uuid(project_id)
        try:
            project = ProjectService(self.repository).get(safe_project_id)
            if project.lifecycle_status != "active":
                raise ProjectStatusValidationError(
                    "live project status requires an active ProjectRecord"
                )
            if project.sensitivity == "secret":
                raise ProjectStatusValidationError(
                    "secret projects cannot use normal project-status output"
                )

            omitted = {
                "work_items": 0,
                "checkpoints": 0,
                "decisions": 0,
                "policies": 0,
                "procedures": 0,
            }
            work_items = self._work_items(project, omitted)
            checkpoints = self._checkpoints(project, omitted)
            latest_checkpoint = _latest_checkpoint(checkpoints)
            decisions = self._decisions(project, omitted)
            policies = self._policies(project, omitted)
            procedures = self._procedures(project, omitted)
            source_revision = self.repository.status().state_revision
        except ProjectStatusValidationError:
            raise
        except (
            KeyError,
            ProjectDecisionCorruptError,
            WorkItemCorruptError,
            CheckpointCorruptError,
            ProcedureCorruptError,
            SettingsCorruptError,
        ) as exc:
            raise ProjectStatusCorruptError(
                "authoritative project status inputs are malformed"
            ) from exc

        active = tuple(
            _status_work_item(item)
            for item in work_items
            if item.work_status == "in_progress"
        )
        ready = tuple(
            _status_work_item(item)
            for item in work_items
            if item.work_status == "ready"
        )
        blocked = tuple(
            _status_work_item(item)
            for item in work_items
            if item.work_status == "blocked"
        )
        pending_validation = tuple(
            _pending_validation(item)
            for item in work_items
            if _requires_validation(item)
        )
        checkpoint_view = (
            _status_checkpoint(latest_checkpoint)
            if latest_checkpoint is not None
            else None
        )
        return ProjectStatusInfo(
            status_schema=PROJECT_STATUS_SCHEMA,
            project_id=project.project_id,
            project_name=project.name,
            objective=project.objective,
            objective_available=project.objective is not None,
            project_status=project.project_status,
            project_revision=project.revision,
            current_phase=(
                latest_checkpoint.current_phase
                if latest_checkpoint is not None
                else None
            ),
            current_goal=(
                latest_checkpoint.current_goal
                if latest_checkpoint is not None
                else None
            ),
            active_work=active,
            next_ready_work=ready,
            blocked_work=blocked,
            pending_required_validation=pending_validation,
            latest_checkpoint=checkpoint_view,
            governing_decisions=tuple(_status_decision(item) for item in decisions),
            governing_policies=tuple(_status_policy(item) for item in policies),
            approved_procedures=tuple(_status_procedure(item) for item in procedures),
            omitted_record_counts=omitted,
            source_state_revision=source_revision,
        )

    def export_json(self, project_id: str) -> str:
        return _canonical_json(_status_payload(self.build(project_id)))

    def render_text(self, project_id: str) -> str:
        status = self.build(project_id)
        lines = [
            f"Project: {status.project_name}",
            f"Project ID: {status.project_id}",
            f"Objective: {status.objective if status.objective is not None else '[not recorded]'}",
            f"Status: {status.project_status}",
            f"Project revision: {status.project_revision}",
            f"Source state revision: {status.source_state_revision}",
            f"Current phase: {status.current_phase or '[no confirmed checkpoint]'}",
            f"Current goal: {status.current_goal or '[no confirmed checkpoint]'}",
        ]
        if status.latest_checkpoint is None:
            lines.append("Latest checkpoint: none")
        else:
            checkpoint = status.latest_checkpoint
            lines.append(
                "Latest checkpoint: "
                f"{checkpoint.checkpoint_id} as_of={checkpoint.as_of} "
                f"freshness={checkpoint.freshness or '-'}"
            )
        lines.extend(_render_work_section("Active work", status.active_work))
        lines.extend(_render_work_section("Next ready work", status.next_ready_work))
        lines.extend(_render_work_section("Blocked work", status.blocked_work))
        lines.append("Pending required validation:")
        if not status.pending_required_validation:
            lines.append("  none")
        else:
            for item in status.pending_required_validation:
                criteria = ",".join(item.blocking_criterion_ids)
                lines.append(
                    f"  - {item.work_item_id} {item.title} "
                    f"state={item.verification_state} criteria={criteria}"
                )
        lines.append("Governing decisions:")
        if not status.governing_decisions:
            lines.append("  none")
        else:
            for decision in status.governing_decisions:
                lines.append(
                    f"  - {decision.decision_id} {decision.decision} "
                    f"decided_at={decision.decided_at}"
                )
        lines.append("Governing policies:")
        if not status.governing_policies:
            lines.append("  none")
        else:
            for policy in status.governing_policies:
                lines.append(
                    f"  - {policy.policy_id} {policy.key} enabled={policy.enabled}"
                )
        lines.append("Approved procedures:")
        if not status.approved_procedures:
            lines.append("  none")
        else:
            for procedure in status.approved_procedures:
                lines.append(
                    f"  - {procedure.procedure_id} {procedure.title} "
                    f"version={procedure.version}"
                )
        lines.append(
            "Omitted secret records: "
            + ", ".join(
                f"{key}={status.omitted_record_counts[key]}"
                for key in sorted(status.omitted_record_counts)
            )
        )
        return "\n".join(lines) + "\n"

    def _work_items(
        self,
        project: ProjectInfo,
        omitted: dict[str, int],
    ) -> tuple[WorkItemInfo, ...]:
        service = WorkItemService(self.repository)
        result: list[WorkItemInfo] = []
        for record_id in _record_ids(self.repository, "work_item"):
            item = service.get(record_id)
            if item.project_id != project.project_id or item.lifecycle_status != "active":
                continue
            if item.sensitivity == "secret":
                omitted["work_items"] += 1
                continue
            result.append(item)
        return tuple(sorted(result, key=_work_sort_key))

    def _checkpoints(
        self,
        project: ProjectInfo,
        omitted: dict[str, int],
    ) -> tuple[ProjectCheckpointInfo, ...]:
        service = ProjectCheckpointService(self.repository)
        result: list[ProjectCheckpointInfo] = []
        for record_id in _record_ids(self.repository, "project_checkpoint"):
            item = service.get(record_id)
            if item.project_id != project.project_id or item.lifecycle_status != "active":
                continue
            if item.confirmation_state == "proposed":
                continue
            if item.sensitivity == "secret":
                omitted["checkpoints"] += 1
                continue
            result.append(item)
        return tuple(sorted(result, key=_checkpoint_sort_key))

    def _decisions(
        self,
        project: ProjectInfo,
        omitted: dict[str, int],
    ) -> tuple[DecisionInfo, ...]:
        service = DecisionService(self.repository)
        explicit_ids = set(project.decision_ids)
        result: dict[str, DecisionInfo] = {}
        for record_id in _record_ids(self.repository, "decision"):
            item = service.get(record_id)
            if item.lifecycle_status != "active" or item.decision_status != "accepted":
                continue
            if item.project_id != project.project_id and item.decision_id not in explicit_ids:
                continue
            if item.sensitivity == "secret":
                omitted["decisions"] += 1
                continue
            result[item.decision_id] = item
        return tuple(sorted(result.values(), key=_decision_sort_key))

    def _policies(
        self,
        project: ProjectInfo,
        omitted: dict[str, int],
    ) -> tuple[PolicyInfo, ...]:
        service = PolicyService(self.repository)
        result: list[PolicyInfo] = []
        for record_id in sorted(project.governing_policy_ids):
            item = service.get(record_id)
            if item.status != "active":
                continue
            if item.sensitivity == "secret":
                omitted["policies"] += 1
                continue
            result.append(item)
        return tuple(sorted(result, key=lambda item: (item.key, item.record_id)))

    def _procedures(
        self,
        project: ProjectInfo,
        omitted: dict[str, int],
    ) -> tuple[ProcedureInfo, ...]:
        service = ProcedureService(self.repository)
        result: list[ProcedureInfo] = []
        for record_id in _record_ids(self.repository, "procedure"):
            item = service.get(record_id)
            if item.project_id != project.project_id or item.lifecycle_status != "active":
                continue
            if item.procedure_status != "approved":
                continue
            if item.sensitivity == "secret":
                omitted["procedures"] += 1
                continue
            result.append(item)
        return tuple(sorted(result, key=_procedure_sort_key))


def _uuid(value: str) -> str:
    try:
        return str(UUID(value))
    except (TypeError, ValueError) as exc:
        raise ProjectStatusValidationError("project ID is invalid") from exc


def _record_ids(repository: StateRepository, record_type: str) -> tuple[str, ...]:
    rows = repository.connection.execute(
        "SELECT id FROM records WHERE record_type = ? ORDER BY id",
        (record_type,),
    ).fetchall()
    return tuple(cast(str, row[0]) for row in rows)


def _work_sort_key(item: WorkItemInfo) -> tuple[int, str, str]:
    return (item.priority, item.title.casefold(), item.work_item_id)


def _checkpoint_sort_key(item: ProjectCheckpointInfo) -> tuple[str, str, str]:
    return (item.as_of, item.created_at, item.checkpoint_id)


def _decision_sort_key(item: DecisionInfo) -> tuple[str, str]:
    return (item.decided_at, item.decision_id)


def _procedure_sort_key(item: ProcedureInfo) -> tuple[str, int, str]:
    return (item.title.casefold(), item.version, item.procedure_id)


def _latest_checkpoint(
    checkpoints: tuple[ProjectCheckpointInfo, ...],
) -> ProjectCheckpointInfo | None:
    return checkpoints[-1] if checkpoints else None


def _status_work_item(item: WorkItemInfo) -> StatusWorkItem:
    return StatusWorkItem(
        work_item_id=item.work_item_id,
        kind=item.kind,
        title=item.title,
        work_status=item.work_status,
        priority=item.priority,
        blocked_by_ids=item.blocked_by_ids,
        verification_state=item.verification_state,
        revision=item.revision,
    )


def _requires_validation(item: WorkItemInfo) -> bool:
    if item.work_status in {"proposed", "cancelled"}:
        return False
    if item.verification_state in {"passed", "not_applicable"}:
        return False
    return any(criterion.blocking for criterion in item.acceptance_criteria)


def _pending_validation(item: WorkItemInfo) -> PendingValidation:
    return PendingValidation(
        work_item_id=item.work_item_id,
        title=item.title,
        work_status=item.work_status,
        verification_state=item.verification_state,
        blocking_criterion_ids=tuple(
            criterion.criterion_id
            for criterion in item.acceptance_criteria
            if criterion.blocking
        ),
        verification_evidence_ids=item.verification_evidence_ids,
    )


def _status_checkpoint(item: ProjectCheckpointInfo) -> StatusCheckpoint:
    return StatusCheckpoint(
        checkpoint_id=item.checkpoint_id,
        as_of=item.as_of,
        current_phase=item.current_phase,
        current_goal=item.current_goal,
        confirmation_state=item.confirmation_state,
        freshness=item.freshness,
        basis_fingerprint=item.basis_fingerprint,
        required_validation_ids=item.required_validation_ids,
        revision=item.revision,
    )


def _status_decision(item: DecisionInfo) -> StatusDecision:
    return StatusDecision(
        decision_id=item.decision_id,
        decision=item.decision,
        reason=item.reason,
        decided_at=item.decided_at,
        constraints=item.constraints,
        revision=item.revision,
    )


def _status_policy(item: PolicyInfo) -> StatusPolicy:
    return StatusPolicy(
        policy_id=item.record_id,
        key=item.key,
        rule=item.rule,
        enabled=item.enabled,
        revision=item.revision,
    )


def _status_procedure(item: ProcedureInfo) -> StatusProcedure:
    return StatusProcedure(
        procedure_id=item.procedure_id,
        title=item.title,
        purpose=item.purpose,
        version=item.version,
        last_verified_at=item.last_verified_at,
        revision=item.revision,
    )


def _status_payload(status: ProjectStatusInfo) -> dict[str, object]:
    payload = asdict(status)
    payload["omitted_record_counts"] = {
        key: status.omitted_record_counts[key]
        for key in sorted(status.omitted_record_counts)
    }
    return cast(dict[str, object], payload)


def _canonical_json(value: object) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise ProjectStatusValidationError(
            "project status is not strict JSON"
        ) from exc


def _render_work_section(
    title: str,
    items: tuple[StatusWorkItem, ...],
) -> list[str]:
    lines = [f"{title}:"]
    if not items:
        lines.append("  none")
        return lines
    for item in items:
        blockers = ",".join(item.blocked_by_ids) or "-"
        lines.append(
            f"  - {item.work_item_id} {item.title} "
            f"priority={item.priority} blockers={blockers}"
        )
    return lines
