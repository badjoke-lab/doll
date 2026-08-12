"""Derived, rebuildable recall state over confirmed local memory."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, cast

from doll.local_search import LOCAL_SEARCH_MODE, LocalSearchHit, search_local_state
from doll.memory import ConfirmedMemoryService
from doll.state_repository import StateRepository

RecallAlgorithmId = Literal[
    "local-search-order",
    "bounded-field-count-rerank",
]

RECALL_STATE_REPORT_SCHEMA_VERSION = 1
DEFAULT_RECALL_ALGORITHM_ID: RecallAlgorithmId = "local-search-order"
RECALL_ALGORITHM_VERSION = "1"
_SUPPORTED_ALGORITHMS: frozenset[str] = frozenset(
    {
        DEFAULT_RECALL_ALGORITHM_ID,
        "bounded-field-count-rerank",
    }
)


class RecallStateError(RuntimeError):
    """Base class for derived recall-state failures."""


class RecallStateValidationError(RecallStateError):
    """Raised when recall derivation is requested through an unsafe boundary."""


@dataclass(frozen=True, slots=True)
class RecallState:
    """One non-authoritative recall result bound to authoritative memory revisions."""

    memory_id: str
    memory_revision: int
    source_state_revision: int
    algorithm_id: RecallAlgorithmId
    algorithm_version: str
    lexical_score: int
    rank: int

    def to_dict(self) -> dict[str, object]:
        return {
            "memory_id": self.memory_id,
            "memory_revision": self.memory_revision,
            "source_state_revision": self.source_state_revision,
            "algorithm_id": self.algorithm_id,
            "algorithm_version": self.algorithm_version,
            "lexical_score": self.lexical_score,
            "rank": self.rank,
        }


@dataclass(frozen=True, slots=True)
class RecallStateReport:
    """Deterministic ephemeral recall output for one bounded local-memory query."""

    source_state_revision: int
    algorithm_id: RecallAlgorithmId
    algorithm_version: str
    search_mode: str
    scanned_records: int
    scan_truncated: bool
    states: tuple[RecallState, ...]

    @property
    def result_count(self) -> int:
        return len(self.states)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": RECALL_STATE_REPORT_SCHEMA_VERSION,
            "source_state_revision": self.source_state_revision,
            "algorithm_id": self.algorithm_id,
            "algorithm_version": self.algorithm_version,
            "search_mode": self.search_mode,
            "scanned_records": self.scanned_records,
            "scan_truncated": self.scan_truncated,
            "result_count": self.result_count,
            "states": [state.to_dict() for state in self.states],
        }


@dataclass(frozen=True, slots=True)
class _RecallCandidate:
    memory_id: str
    memory_revision: int
    source_rank: int
    lexical_score: int


def derive_memory_recall_state(
    repository: StateRepository,
    query: str,
    *,
    limit: int = 20,
    algorithm_id: RecallAlgorithmId = DEFAULT_RECALL_ALGORITHM_ID,
) -> RecallStateReport:
    """Derive recall state without mutating authoritative memory or Doll State."""

    if not repository.read_only:
        raise RecallStateValidationError("recall derivation requires a read-only repository")
    resolved_algorithm = _validate_algorithm_id(algorithm_id)
    source_state_revision = repository.status().state_revision
    search_report = search_local_state(
        repository,
        query,
        record_type="memory",
        limit=limit,
    )
    memory_service = ConfirmedMemoryService(repository)
    candidates = tuple(
        _candidate_from_hit(memory_service, hit, source_rank)
        for source_rank, hit in enumerate(search_report.hits, start=1)
    )

    if resolved_algorithm == "bounded-field-count-rerank":
        ordered = tuple(
            sorted(
                candidates,
                key=lambda candidate: (
                    -candidate.lexical_score,
                    candidate.source_rank,
                    candidate.memory_id,
                ),
            )
        )
    else:
        ordered = candidates

    states = tuple(
        RecallState(
            memory_id=candidate.memory_id,
            memory_revision=candidate.memory_revision,
            source_state_revision=source_state_revision,
            algorithm_id=resolved_algorithm,
            algorithm_version=RECALL_ALGORITHM_VERSION,
            lexical_score=candidate.lexical_score,
            rank=rank,
        )
        for rank, candidate in enumerate(ordered, start=1)
    )
    return RecallStateReport(
        source_state_revision=source_state_revision,
        algorithm_id=resolved_algorithm,
        algorithm_version=RECALL_ALGORITHM_VERSION,
        search_mode=LOCAL_SEARCH_MODE,
        scanned_records=search_report.scanned_records,
        scan_truncated=search_report.scan_truncated,
        states=states,
    )


def _candidate_from_hit(
    memory_service: ConfirmedMemoryService,
    hit: LocalSearchHit,
    source_rank: int,
) -> _RecallCandidate:
    memory = memory_service.get(hit.record_id)
    return _RecallCandidate(
        memory_id=memory.record_id,
        memory_revision=memory.revision,
        source_rank=source_rank,
        lexical_score=len(hit.matches),
    )


def _validate_algorithm_id(algorithm_id: object) -> RecallAlgorithmId:
    if not isinstance(algorithm_id, str) or algorithm_id not in _SUPPORTED_ALGORITHMS:
        raise RecallStateValidationError("unsupported recall algorithm")
    return cast(RecallAlgorithmId, algorithm_id)
