"""Read-only, inspectable context-budget previews over deterministic memory recall."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal, cast

from doll.memory import ConfirmedMemoryInfo, ConfirmedMemoryService
from doll.recall_state import (
    DEFAULT_RECALL_ALGORITHM_ID,
    RECALL_ALGORITHM_VERSION,
    RecallState,
    RecallStateValidationError,
    derive_memory_recall_state,
)
from doll.state import RecordSensitivity, StateError
from doll.state_repository import StateRepository
from doll.writing_context import (
    MAX_SELECTED_CONTEXT_CHARS,
    MAX_SELECTED_MEMORIES,
    SelectedWritingContextError,
    SelectedWritingContextService,
)

MemoryContextBudgetExclusionReason = Literal[
    "not_yet_valid",
    "expired",
    "sensitivity_limit",
    "item_limit",
    "character_budget",
]

MEMORY_CONTEXT_BUDGET_REPORT_SCHEMA_VERSION = 1
MEMORY_CONTEXT_BUDGET_POLICY_ID = "lexical-recall-budget-preview"
MEMORY_CONTEXT_BUDGET_POLICY_VERSION = "1"
MEMORY_CONTEXT_BUDGET_SCOPE = "global-confirmed-memory-only"
MAX_MEMORY_CONTEXT_BUDGET_CANDIDATES = 50

_SENSITIVITY_RANK: dict[RecordSensitivity, int] = {
    "public": 0,
    "internal": 1,
    "personal": 2,
    "sensitive": 3,
    "secret": 4,
}
_SELECTABLE_SENSITIVITIES = frozenset({"public", "internal", "personal", "sensitive"})


class MemoryContextBudgetError(StateError):
    """Base class for memory context-budget preview failures."""


class MemoryContextBudgetValidationError(MemoryContextBudgetError):
    """Raised when a preview request cannot remain within the accepted boundary."""


@dataclass(frozen=True, slots=True)
class MemoryContextBudgetSelection:
    """One recommended memory identifier with inspectable ranking and size evidence."""

    memory_id: str
    memory_revision: int
    recall_rank: int
    lexical_score: int
    sensitivity: RecordSensitivity
    estimated_context_characters: int

    def to_dict(self) -> dict[str, object]:
        return {
            "memory_id": self.memory_id,
            "memory_revision": self.memory_revision,
            "recall_rank": self.recall_rank,
            "lexical_score": self.lexical_score,
            "sensitivity": self.sensitivity,
            "estimated_context_characters": self.estimated_context_characters,
        }


@dataclass(frozen=True, slots=True)
class MemoryContextBudgetExclusion:
    """One bounded explanation for a recalled memory that was not recommended."""

    memory_id: str
    memory_revision: int
    recall_rank: int
    lexical_score: int
    reason: MemoryContextBudgetExclusionReason
    estimated_context_characters: int | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "memory_id": self.memory_id,
            "memory_revision": self.memory_revision,
            "recall_rank": self.recall_rank,
            "lexical_score": self.lexical_score,
            "reason": self.reason,
            "estimated_context_characters": self.estimated_context_characters,
        }


@dataclass(frozen=True, slots=True)
class MemoryContextBudgetReport:
    """Advisory preview only; selected IDs still require the explicit context path."""

    source_state_revision: int
    policy_id: str
    policy_version: str
    recall_algorithm_id: str
    recall_algorithm_version: str
    scope: str
    as_of: str
    memory_enabled: bool
    maximum_sensitivity: RecordSensitivity
    maximum_items: int
    maximum_characters: int
    scanned_records: int
    scan_truncated: bool
    candidate_count: int
    selected_character_count: int
    selections: tuple[MemoryContextBudgetSelection, ...]
    exclusions: tuple[MemoryContextBudgetExclusion, ...]

    @property
    def selected_count(self) -> int:
        return len(self.selections)

    @property
    def selected_memory_ids(self) -> tuple[str, ...]:
        return tuple(selection.memory_id for selection in self.selections)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": MEMORY_CONTEXT_BUDGET_REPORT_SCHEMA_VERSION,
            "source_state_revision": self.source_state_revision,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "recall_algorithm_id": self.recall_algorithm_id,
            "recall_algorithm_version": self.recall_algorithm_version,
            "scope": self.scope,
            "as_of": self.as_of,
            "memory_enabled": self.memory_enabled,
            "maximum_sensitivity": self.maximum_sensitivity,
            "maximum_items": self.maximum_items,
            "maximum_characters": self.maximum_characters,
            "scanned_records": self.scanned_records,
            "scan_truncated": self.scan_truncated,
            "candidate_count": self.candidate_count,
            "selected_count": self.selected_count,
            "selected_character_count": self.selected_character_count,
            "selected_memory_ids": list(self.selected_memory_ids),
            "selections": [selection.to_dict() for selection in self.selections],
            "exclusions": [exclusion.to_dict() for exclusion in self.exclusions],
            "automatic_context_injection": False,
            "requires_explicit_context_materialization": True,
        }


def preview_memory_context_budget(
    repository: StateRepository,
    query: str,
    *,
    as_of: str,
    memory_enabled: bool = True,
    maximum_sensitivity: RecordSensitivity = "personal",
    maximum_items: int = MAX_SELECTED_MEMORIES,
    maximum_characters: int = MAX_SELECTED_CONTEXT_CHARS,
) -> MemoryContextBudgetReport:
    """Recommend bounded memory IDs without creating or injecting context."""

    if not repository.read_only:
        raise MemoryContextBudgetValidationError(
            "memory context-budget preview requires a read-only repository"
        )
    safe_memory_enabled = _validate_memory_enabled(memory_enabled)
    safe_as_of, as_of_value = _validate_as_of(as_of)
    safe_sensitivity = _validate_maximum_sensitivity(maximum_sensitivity)
    safe_maximum_items = _validate_maximum_items(maximum_items)
    safe_maximum_characters = _validate_maximum_characters(maximum_characters)
    source_state_revision = repository.status().state_revision

    if not safe_memory_enabled:
        _require_stable_state(repository, source_state_revision)
        return MemoryContextBudgetReport(
            source_state_revision=source_state_revision,
            policy_id=MEMORY_CONTEXT_BUDGET_POLICY_ID,
            policy_version=MEMORY_CONTEXT_BUDGET_POLICY_VERSION,
            recall_algorithm_id=DEFAULT_RECALL_ALGORITHM_ID,
            recall_algorithm_version=RECALL_ALGORITHM_VERSION,
            scope=MEMORY_CONTEXT_BUDGET_SCOPE,
            as_of=safe_as_of,
            memory_enabled=False,
            maximum_sensitivity=safe_sensitivity,
            maximum_items=safe_maximum_items,
            maximum_characters=safe_maximum_characters,
            scanned_records=0,
            scan_truncated=False,
            candidate_count=0,
            selected_character_count=0,
            selections=(),
            exclusions=(),
        )

    try:
        recall = derive_memory_recall_state(
            repository,
            query,
            limit=MAX_MEMORY_CONTEXT_BUDGET_CANDIDATES,
            algorithm_id=DEFAULT_RECALL_ALGORITHM_ID,
        )
    except RecallStateValidationError as exc:
        raise MemoryContextBudgetValidationError(
            "memory recall preview request is invalid"
        ) from exc
    if recall.source_state_revision != source_state_revision:
        raise MemoryContextBudgetValidationError(
            "Doll State changed before memory context-budget selection"
        )

    memory_service = ConfirmedMemoryService(repository)
    writing_context = SelectedWritingContextService(repository)
    selections: list[MemoryContextBudgetSelection] = []
    exclusions: list[MemoryContextBudgetExclusion] = []
    selected_characters = 0

    for recall_state in recall.states:
        memory = memory_service.get(recall_state.memory_id)
        _require_matching_memory_revision(memory, recall_state.memory_revision)
        validity_reason = _validity_exclusion(memory, as_of_value)
        if validity_reason is not None:
            exclusions.append(_exclusion(recall_state, validity_reason))
            continue
        if not _within_sensitivity(memory.sensitivity, safe_sensitivity):
            exclusions.append(_exclusion(recall_state, "sensitivity_limit"))
            continue
        if len(selections) >= safe_maximum_items:
            exclusions.append(_exclusion(recall_state, "item_limit"))
            continue

        selected_ids = tuple(selection.memory_id for selection in selections)
        try:
            single_plan = writing_context.plan(memory_ids=(memory.record_id,))
            combined_plan = writing_context.plan(memory_ids=(*selected_ids, memory.record_id))
        except SelectedWritingContextError as exc:
            raise MemoryContextBudgetValidationError(
                "recalled memory cannot satisfy the explicit writing-context boundary"
            ) from exc
        estimated_characters = single_plan.character_count
        if combined_plan.character_count > safe_maximum_characters:
            exclusions.append(
                _exclusion(
                    recall_state,
                    "character_budget",
                    estimated_context_characters=estimated_characters,
                )
            )
            continue
        selections.append(
            MemoryContextBudgetSelection(
                memory_id=memory.record_id,
                memory_revision=memory.revision,
                recall_rank=recall_state.rank,
                lexical_score=recall_state.lexical_score,
                sensitivity=memory.sensitivity,
                estimated_context_characters=estimated_characters,
            )
        )
        selected_characters = combined_plan.character_count

    _require_stable_state(repository, source_state_revision)
    return MemoryContextBudgetReport(
        source_state_revision=source_state_revision,
        policy_id=MEMORY_CONTEXT_BUDGET_POLICY_ID,
        policy_version=MEMORY_CONTEXT_BUDGET_POLICY_VERSION,
        recall_algorithm_id=recall.algorithm_id,
        recall_algorithm_version=recall.algorithm_version,
        scope=MEMORY_CONTEXT_BUDGET_SCOPE,
        as_of=safe_as_of,
        memory_enabled=True,
        maximum_sensitivity=safe_sensitivity,
        maximum_items=safe_maximum_items,
        maximum_characters=safe_maximum_characters,
        scanned_records=recall.scanned_records,
        scan_truncated=recall.scan_truncated,
        candidate_count=len(recall.states),
        selected_character_count=selected_characters,
        selections=tuple(selections),
        exclusions=tuple(exclusions),
    )


def _exclusion(
    recall_state: RecallState,
    reason: MemoryContextBudgetExclusionReason,
    *,
    estimated_context_characters: int | None = None,
) -> MemoryContextBudgetExclusion:
    return MemoryContextBudgetExclusion(
        memory_id=recall_state.memory_id,
        memory_revision=recall_state.memory_revision,
        recall_rank=recall_state.rank,
        lexical_score=recall_state.lexical_score,
        reason=reason,
        estimated_context_characters=estimated_context_characters,
    )


def _validity_exclusion(
    memory: ConfirmedMemoryInfo,
    as_of: datetime,
) -> MemoryContextBudgetExclusionReason | None:
    valid_from = _parse_memory_timestamp(memory.valid_from)
    valid_until = _parse_memory_timestamp(memory.valid_until)
    if valid_from is not None and as_of < valid_from:
        return "not_yet_valid"
    if valid_until is not None and as_of > valid_until:
        return "expired"
    return None


def _parse_memory_timestamp(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        return _parse_utc_datetime(value)
    except ValueError as exc:
        raise MemoryContextBudgetValidationError("memory validity timestamp is invalid") from exc


def _validate_as_of(value: object) -> tuple[str, datetime]:
    if not isinstance(value, str) or not value.strip() or len(value) > 64:
        raise MemoryContextBudgetValidationError("as_of must be a bounded UTC timestamp")
    try:
        parsed = _parse_utc_datetime(value)
    except ValueError as exc:
        raise MemoryContextBudgetValidationError("as_of must be a UTC timestamp") from exc
    normalized = parsed.isoformat(timespec="microseconds").replace("+00:00", "Z")
    return normalized, parsed


def _parse_utc_datetime(value: str) -> datetime:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError("timestamp must be UTC")
    return parsed.astimezone(UTC)


def _validate_memory_enabled(value: object) -> bool:
    if not isinstance(value, bool):
        raise MemoryContextBudgetValidationError("memory_enabled must be boolean")
    return value


def _validate_maximum_sensitivity(value: object) -> RecordSensitivity:
    if not isinstance(value, str) or value not in _SELECTABLE_SENSITIVITIES:
        raise MemoryContextBudgetValidationError("maximum_sensitivity is invalid")
    return cast(RecordSensitivity, value)


def _validate_maximum_items(value: object) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 1 <= value <= MAX_SELECTED_MEMORIES
    ):
        raise MemoryContextBudgetValidationError("maximum_items is invalid")
    return value


def _validate_maximum_characters(value: object) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 1 <= value <= MAX_SELECTED_CONTEXT_CHARS
    ):
        raise MemoryContextBudgetValidationError("maximum_characters is invalid")
    return value


def _within_sensitivity(
    memory_sensitivity: RecordSensitivity,
    maximum_sensitivity: RecordSensitivity,
) -> bool:
    if memory_sensitivity == "secret":
        return False
    return _SENSITIVITY_RANK[memory_sensitivity] <= _SENSITIVITY_RANK[maximum_sensitivity]


def _require_matching_memory_revision(memory: ConfirmedMemoryInfo, expected_revision: int) -> None:
    if memory.revision != expected_revision:
        raise MemoryContextBudgetValidationError(
            "authoritative memory changed during context-budget preview"
        )


def _require_stable_state(repository: StateRepository, expected_revision: int) -> None:
    if repository.status().state_revision != expected_revision:
        raise MemoryContextBudgetValidationError("Doll State changed during context-budget preview")
