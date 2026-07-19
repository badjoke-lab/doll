"""Explicit data-only memory, project, and decision context for local writing."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from doll.instruction_origin import InstructionOriginService, InstructionSource
from doll.memory import ConfirmedMemoryError, ConfirmedMemoryInfo, ConfirmedMemoryService
from doll.project_state import (
    DecisionInfo,
    DecisionService,
    ProjectDecisionError,
    ProjectInfo,
    ProjectService,
)
from doll.state import RecordSensitivity, StateError
from doll.state_repository import StateRepository

SelectedWritingContextKind = Literal["memory", "project", "decision"]

MAX_SELECTED_MEMORIES = 8
MAX_SELECTED_PROJECTS = 4
MAX_SELECTED_DECISIONS = 8
MAX_SELECTED_CONTEXT_ITEMS = 10
MAX_SELECTED_CONTEXT_CHARS = 24_000

_SENSITIVITY_RANK: dict[RecordSensitivity, int] = {
    "public": 0,
    "internal": 1,
    "personal": 2,
    "sensitive": 3,
    "secret": 4,
}


class SelectedWritingContextError(StateError):
    """Base class for explicit writing-context failures."""


class SelectedWritingContextValidationError(SelectedWritingContextError):
    """Raised before runtime execution when selected context is invalid."""


@dataclass(frozen=True, slots=True)
class SelectedWritingContextPlan:
    """Validated immutable snapshots ready for data-only materialization."""

    snapshots: tuple[SelectedWritingContextSnapshot, ...]
    memory_ids: tuple[str, ...]
    project_ids: tuple[str, ...]
    decision_ids: tuple[str, ...]
    memory_revisions: tuple[int, ...]
    project_revisions: tuple[int, ...]
    decision_revisions: tuple[int, ...]
    character_count: int
    required_sensitivity: RecordSensitivity


@dataclass(frozen=True, slots=True)
class SelectedWritingContextSnapshot:
    """One deterministic memory or project snapshot."""

    kind: SelectedWritingContextKind
    record_id: str
    revision: int
    content: str
    sensitivity: RecordSensitivity


@dataclass(frozen=True, slots=True)
class SelectedWritingContextResult:
    """Content-free identifiers for materialized selected context."""

    instruction_ids: tuple[str, ...]
    memory_ids: tuple[str, ...]
    project_ids: tuple[str, ...]
    decision_ids: tuple[str, ...]
    memory_revisions: tuple[int, ...]
    project_revisions: tuple[int, ...]
    decision_revisions: tuple[int, ...]
    character_count: int
    required_sensitivity: RecordSensitivity


@dataclass(slots=True)
class SelectedWritingContextService:
    """Resolve explicit authoritative records into data-only prompt context."""

    repository: StateRepository

    def plan(
        self,
        *,
        memory_ids: Sequence[str] = (),
        project_ids: Sequence[str] = (),
        decision_ids: Sequence[str] = (),
    ) -> SelectedWritingContextPlan:
        """Validate all selections before creating any instruction-origin record."""

        safe_memory_ids = _selected_ids(
            "memory IDs",
            memory_ids,
            maximum=MAX_SELECTED_MEMORIES,
        )
        safe_project_ids = _selected_ids(
            "project IDs",
            project_ids,
            maximum=MAX_SELECTED_PROJECTS,
        )
        safe_decision_ids = _selected_ids(
            "decision IDs",
            decision_ids,
            maximum=MAX_SELECTED_DECISIONS,
        )
        if (
            len(safe_memory_ids) + len(safe_project_ids) + len(safe_decision_ids)
            > MAX_SELECTED_CONTEXT_ITEMS
        ):
            raise SelectedWritingContextValidationError(
                "selected writing context exceeds the configured item limit"
            )

        memories = tuple(self._memory(record_id) for record_id in safe_memory_ids)
        projects = tuple(self._project(record_id) for record_id in safe_project_ids)
        decisions = tuple(self._decision(record_id) for record_id in safe_decision_ids)
        snapshots = (
            tuple(_memory_snapshot(memory) for memory in memories)
            + tuple(_project_snapshot(project) for project in projects)
            + tuple(_decision_snapshot(decision) for decision in decisions)
        )
        character_count = sum(len(snapshot.content) for snapshot in snapshots)
        if character_count > MAX_SELECTED_CONTEXT_CHARS:
            raise SelectedWritingContextValidationError(
                "selected writing context exceeds the configured character limit"
            )
        required_sensitivity = _maximum_sensitivity(
            tuple(snapshot.sensitivity for snapshot in snapshots)
        )
        return SelectedWritingContextPlan(
            snapshots=snapshots,
            memory_ids=safe_memory_ids,
            project_ids=safe_project_ids,
            decision_ids=safe_decision_ids,
            memory_revisions=tuple(memory.revision for memory in memories),
            project_revisions=tuple(project.revision for project in projects),
            decision_revisions=tuple(decision.revision for decision in decisions),
            character_count=character_count,
            required_sensitivity=required_sensitivity,
        )

    def require_unused(self, *, operation_id: str, plan: SelectedWritingContextPlan) -> None:
        """Fail before materialization when any deterministic preparation exists."""

        for snapshot in plan.snapshots:
            source_operation_id = _context_operation_id(operation_id, snapshot)
            row = self.repository.connection.execute(
                "SELECT 1 FROM records WHERE record_type = 'instruction_origin' "
                "AND json_extract(metadata_json, '$.parent_operation_id') = ? LIMIT 1",
                (source_operation_id,),
            ).fetchone()
            if row is not None:
                raise SelectedWritingContextValidationError(
                    "selected writing context preparation already exists"
                )

    def materialize(
        self,
        *,
        conversation_id: str,
        operation_id: str,
        plan: SelectedWritingContextPlan,
    ) -> SelectedWritingContextResult:
        """Create immutable external-content origins for one validated plan."""

        origins = InstructionOriginService(self.repository)
        instruction_ids: list[str] = []
        for snapshot in plan.snapshots:
            source_operation_id = _context_operation_id(operation_id, snapshot)
            origin = origins.create(
                title={
                    "memory": "Selected confirmed-memory context",
                    "project": "Selected project context",
                    "decision": "Selected decision context",
                }[snapshot.kind],
                content=snapshot.content,
                source=InstructionSource(
                    origin_class="external_content",
                    actor_type="retriever",
                    acquisition_method="retrieval",
                    source_identifier=(
                        f"{snapshot.kind}:{snapshot.record_id}:revision:{snapshot.revision}"
                    ),
                    parent_operation_id=source_operation_id,
                    session_id=conversation_id,
                    content_hash=_sha256_text(snapshot.content),
                ),
                operation_id=source_operation_id,
                sensitivity=snapshot.sensitivity,
            )
            instruction_ids.append(origin.record_id)
        return SelectedWritingContextResult(
            instruction_ids=tuple(instruction_ids),
            memory_ids=plan.memory_ids,
            project_ids=plan.project_ids,
            decision_ids=plan.decision_ids,
            memory_revisions=plan.memory_revisions,
            project_revisions=plan.project_revisions,
            decision_revisions=plan.decision_revisions,
            character_count=plan.character_count,
            required_sensitivity=plan.required_sensitivity,
        )

    def _memory(self, record_id: str) -> ConfirmedMemoryInfo:
        try:
            memory = ConfirmedMemoryService(self.repository).get(record_id)
        except (KeyError, ConfirmedMemoryError) as exc:
            raise SelectedWritingContextValidationError(
                "selected confirmed memory is unavailable"
            ) from exc
        if memory.status != "active":
            raise SelectedWritingContextValidationError("selected confirmed memory is not active")
        if memory.sensitivity == "secret":
            raise SelectedWritingContextValidationError(
                "secret confirmed memory cannot enter writing context"
            )
        return memory

    def _project(self, record_id: str) -> ProjectInfo:
        try:
            project = ProjectService(self.repository).get(record_id)
        except (KeyError, ProjectDecisionError) as exc:
            raise SelectedWritingContextValidationError("selected project is unavailable") from exc
        if project.lifecycle_status != "active":
            raise SelectedWritingContextValidationError("selected project is not active")
        if project.sensitivity == "secret":
            raise SelectedWritingContextValidationError(
                "secret project cannot enter writing context"
            )
        return project

    def _decision(self, record_id: str) -> DecisionInfo:
        try:
            decision = DecisionService(self.repository).get(record_id)
        except (KeyError, ProjectDecisionError) as exc:
            raise SelectedWritingContextValidationError("selected decision is unavailable") from exc
        if decision.lifecycle_status != "active":
            raise SelectedWritingContextValidationError("selected decision is not active")
        if decision.sensitivity == "secret":
            raise SelectedWritingContextValidationError(
                "secret decision cannot enter writing context"
            )
        return decision


def maximum_writing_sensitivity(
    requested: RecordSensitivity,
    selected: RecordSensitivity,
) -> RecordSensitivity:
    """Prevent selected context from being persisted at a lower sensitivity."""

    if _SENSITIVITY_RANK[selected] > _SENSITIVITY_RANK[requested]:
        return selected
    return requested


def _selected_ids(
    label: str,
    values: Sequence[str],
    *,
    maximum: int,
) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise SelectedWritingContextValidationError(f"{label} must be a sequence")
    result: list[str] = []
    for value in values:
        if not isinstance(value, str) or not value.strip():
            raise SelectedWritingContextValidationError(f"{label} contain an invalid value")
        result.append(value)
    if len(result) > maximum:
        raise SelectedWritingContextValidationError(
            f"{label} exceed the configured selection limit"
        )
    if len(set(result)) != len(result):
        raise SelectedWritingContextValidationError(f"{label} contain duplicates")
    return tuple(result)


def _memory_snapshot(memory: ConfirmedMemoryInfo) -> SelectedWritingContextSnapshot:
    payload = {
        "context_kind": "confirmed_memory",
        "record_id": memory.record_id,
        "revision": memory.revision,
        "subject": memory.subject,
        "content": memory.content,
        "valid_from": memory.valid_from,
        "valid_until": memory.valid_until,
        "confidence": memory.confidence,
    }
    return SelectedWritingContextSnapshot(
        kind="memory",
        record_id=memory.record_id,
        revision=memory.revision,
        content=_deterministic_json(payload),
        sensitivity=memory.sensitivity,
    )


def _project_snapshot(project: ProjectInfo) -> SelectedWritingContextSnapshot:
    payload: dict[str, object] = {
        "context_kind": "project",
        "record_id": project.project_id,
        "revision": project.revision,
        "schema_version": project.schema_version,
        "name": project.name,
        "description": project.description,
        "project_status": project.project_status,
        "started_at": project.started_at,
        "ended_at": project.ended_at,
    }
    if project.schema_version == 2:
        payload.update(
            {
                "objective": project.objective,
                "in_scope": list(project.in_scope),
                "out_of_scope": list(project.out_of_scope),
                "success_criteria": list(project.success_criteria),
            }
        )
    return SelectedWritingContextSnapshot(
        kind="project",
        record_id=project.project_id,
        revision=project.revision,
        content=_deterministic_json(payload),
        sensitivity=project.sensitivity,
    )


def _decision_snapshot(decision: DecisionInfo) -> SelectedWritingContextSnapshot:
    payload: dict[str, object] = {
        "context_kind": "decision",
        "record_id": decision.decision_id,
        "revision": decision.revision,
        "decision": decision.decision,
        "reason": decision.reason,
        "decision_status": decision.decision_status,
        "decided_at": decision.decided_at,
        "alternatives": list(decision.alternatives),
        "constraints": list(decision.constraints),
        "review_after": decision.review_after,
        "supersedes_id": decision.supersedes_id,
        "project_id": decision.project_id,
    }
    return SelectedWritingContextSnapshot(
        kind="decision",
        record_id=decision.decision_id,
        revision=decision.revision,
        content=_deterministic_json(payload),
        sensitivity=decision.sensitivity,
    )


def _maximum_sensitivity(values: Sequence[RecordSensitivity]) -> RecordSensitivity:
    if not values:
        return "public"
    return max(values, key=lambda value: _SENSITIVITY_RANK[value])


def _context_operation_id(
    operation_id: str,
    snapshot: SelectedWritingContextSnapshot,
) -> str:
    digest = hashlib.sha256(
        f"{operation_id}\0{snapshot.kind}\0{snapshot.record_id}\0{snapshot.revision}".encode()
    ).hexdigest()[:32]
    return f"imp065.context.{snapshot.kind}.{digest}"


def _sha256_text(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"


def _deterministic_json(payload: dict[str, object]) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        allow_nan=False,
        separators=(",", ":"),
    )
