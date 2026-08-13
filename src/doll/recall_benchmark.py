"""Deterministic synthetic usefulness benchmark for local memory recall."""

from __future__ import annotations

import json
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Literal, cast

from doll.memory import ConfirmedMemoryService
from doll.recall_index import RecallIndexError, inspect_memory_lexical_index, query_memory_lexical_index
from doll.recall_state import (
    DEFAULT_RECALL_ALGORITHM_ID,
    RECALL_ALGORITHM_VERSION,
    derive_memory_recall_state,
)
from doll.state import RecordSensitivity
from doll.state_repository import StateRepository

RecallBenchmarkClassification = Literal["lexical", "semantic_opportunity", "exclusion"]

RECALL_BENCHMARK_REPORT_SCHEMA_VERSION = 1
RECALL_BENCHMARK_CORPUS_SCHEMA_VERSION = 1


class RecallBenchmarkError(RuntimeError):
    """Base class for deterministic recall benchmark failures."""


class RecallBenchmarkValidationError(RecallBenchmarkError):
    """Raised when a benchmark corpus or repository boundary is invalid."""


@dataclass(frozen=True, slots=True)
class RecallBenchmarkMemorySpec:
    label: str
    subject: str
    content: str
    source_reference: str | None
    sensitivity: RecordSensitivity
    archived: bool


@dataclass(frozen=True, slots=True)
class RecallBenchmarkCaseSpec:
    case_id: str
    classification: RecallBenchmarkClassification
    query: str
    expected_label: str | None
    index_compatible: bool


@dataclass(frozen=True, slots=True)
class RecallBenchmarkCorpus:
    corpus_id: str
    memories: tuple[RecallBenchmarkMemorySpec, ...]
    cases: tuple[RecallBenchmarkCaseSpec, ...]


@dataclass(frozen=True, slots=True)
class RecallBenchmarkBindings:
    """Ephemeral mapping from stable synthetic labels to generated MemoryRecord IDs."""

    label_to_memory_id: dict[str, str]

    def memory_id_to_label(self) -> dict[str, str]:
        return {memory_id: label for label, memory_id in self.label_to_memory_id.items()}


@dataclass(frozen=True, slots=True)
class RecallBenchmarkCaseResult:
    case_id: str
    classification: RecallBenchmarkClassification
    query: str
    expected_label: str | None
    index_compatible: bool
    returned_labels: tuple[str, ...]
    returned_memory_ids: tuple[str, ...]
    expected_rank: int | None
    index_returned_labels: tuple[str, ...]
    index_returned_memory_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "classification": self.classification,
            "query": self.query,
            "expected_label": self.expected_label,
            "index_compatible": self.index_compatible,
            "returned_labels": list(self.returned_labels),
            "returned_memory_ids": list(self.returned_memory_ids),
            "expected_rank": self.expected_rank,
            "index_returned_labels": list(self.index_returned_labels),
            "index_returned_memory_ids": list(self.index_returned_memory_ids),
        }

    def logical_dict(self) -> dict[str, object]:
        """Return stable evidence that excludes generated UUIDs."""

        return {
            "case_id": self.case_id,
            "classification": self.classification,
            "query": self.query,
            "expected_label": self.expected_label,
            "index_compatible": self.index_compatible,
            "returned_labels": list(self.returned_labels),
            "expected_rank": self.expected_rank,
            "index_returned_labels": list(self.index_returned_labels),
        }


@dataclass(frozen=True, slots=True)
class RecallBenchmarkReport:
    corpus_id: str
    source_state_revision: int
    recall_algorithm_id: str
    recall_algorithm_version: str
    index_status: str
    index_error_type: str | None
    lexical_case_count: int
    lexical_recall_at_1: str
    lexical_recall_at_3: str
    lexical_mrr: str
    semantic_opportunity_case_count: int
    semantic_opportunity_miss_count: int
    semantic_opportunity_miss_rate: str
    exclusion_case_count: int
    exclusion_pass_count: int
    index_compatible_lexical_case_count: int
    index_coverage: str | None
    cases: tuple[RecallBenchmarkCaseResult, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": RECALL_BENCHMARK_REPORT_SCHEMA_VERSION,
            "corpus_id": self.corpus_id,
            "source_state_revision": self.source_state_revision,
            "recall_algorithm_id": self.recall_algorithm_id,
            "recall_algorithm_version": self.recall_algorithm_version,
            "index_status": self.index_status,
            "index_error_type": self.index_error_type,
            "lexical_case_count": self.lexical_case_count,
            "lexical_recall_at_1": self.lexical_recall_at_1,
            "lexical_recall_at_3": self.lexical_recall_at_3,
            "lexical_mrr": self.lexical_mrr,
            "semantic_opportunity_case_count": self.semantic_opportunity_case_count,
            "semantic_opportunity_miss_count": self.semantic_opportunity_miss_count,
            "semantic_opportunity_miss_rate": self.semantic_opportunity_miss_rate,
            "exclusion_case_count": self.exclusion_case_count,
            "exclusion_pass_count": self.exclusion_pass_count,
            "index_compatible_lexical_case_count": self.index_compatible_lexical_case_count,
            "index_coverage": self.index_coverage,
            "cases": [case.to_dict() for case in self.cases],
        }

    def logical_dict(self) -> dict[str, object]:
        """Return deterministic logical evidence independent of generated MemoryRecord IDs."""

        payload = self.to_dict()
        payload["cases"] = [case.logical_dict() for case in self.cases]
        return payload


def load_recall_benchmark_corpus(path: Path) -> RecallBenchmarkCorpus:
    """Load and strictly validate one versioned synthetic benchmark corpus."""

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RecallBenchmarkValidationError("recall benchmark corpus is unreadable") from exc
    root = _require_object(value, "benchmark corpus")
    if _require_int(root, "schema_version") != RECALL_BENCHMARK_CORPUS_SCHEMA_VERSION:
        raise RecallBenchmarkValidationError("unsupported recall benchmark corpus schema")
    corpus_id = _require_string(root, "corpus_id")
    memories = tuple(_parse_memory(item) for item in _require_object_list(root, "memories"))
    cases = tuple(_parse_case(item) for item in _require_object_list(root, "cases"))
    if not memories or not cases:
        raise RecallBenchmarkValidationError("recall benchmark corpus must contain memories and cases")
    labels = [memory.label for memory in memories]
    if len(labels) != len(set(labels)):
        raise RecallBenchmarkValidationError("recall benchmark memory labels must be unique")
    case_ids = [case.case_id for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise RecallBenchmarkValidationError("recall benchmark case IDs must be unique")
    label_set = set(labels)
    for case in cases:
        if case.classification == "exclusion":
            if case.expected_label is not None:
                raise RecallBenchmarkValidationError("exclusion cases must not declare an expected label")
        elif case.expected_label not in label_set:
            raise RecallBenchmarkValidationError("benchmark case references an unknown memory label")
    return RecallBenchmarkCorpus(corpus_id=corpus_id, memories=memories, cases=cases)


def populate_synthetic_recall_benchmark(
    repository: StateRepository,
    corpus: RecallBenchmarkCorpus,
) -> RecallBenchmarkBindings:
    """Populate an explicitly disposable writable workspace with fabricated memories only."""

    if repository.read_only:
        raise RecallBenchmarkValidationError("benchmark population requires a writable repository")
    existing = repository.connection.execute(
        "SELECT COUNT(*) FROM records WHERE record_type = 'memory'"
    ).fetchone()
    if existing is None or cast(int, existing[0]) != 0:
        raise RecallBenchmarkValidationError("benchmark workspace must not contain existing memory")
    service = ConfirmedMemoryService(repository)
    label_to_memory_id: dict[str, str] = {}
    for spec in corpus.memories:
        memory = service.create(
            subject=spec.subject,
            content=spec.content,
            source_reference=spec.source_reference,
            sensitivity=spec.sensitivity,
        )
        if spec.archived:
            memory = service.archive(memory.record_id, expected_revision=memory.revision)
        label_to_memory_id[spec.label] = memory.record_id
    return RecallBenchmarkBindings(label_to_memory_id=label_to_memory_id)


def run_recall_benchmark(
    repository: StateRepository,
    corpus: RecallBenchmarkCorpus,
    bindings: RecallBenchmarkBindings,
) -> RecallBenchmarkReport:
    """Measure current production lexical recall without mutating authoritative state."""

    if not repository.read_only:
        raise RecallBenchmarkValidationError("recall benchmark requires a read-only repository")
    id_to_label = bindings.memory_id_to_label()
    if set(bindings.label_to_memory_id) != {memory.label for memory in corpus.memories}:
        raise RecallBenchmarkValidationError("benchmark bindings do not match the corpus")

    index_status = "available"
    index_error_type: str | None = None
    try:
        inspect_memory_lexical_index(repository)
    except RecallIndexError as exc:
        index_status = "unavailable"
        index_error_type = type(exc).__name__

    results: list[RecallBenchmarkCaseResult] = []
    for case in corpus.cases:
        scan = derive_memory_recall_state(repository, case.query)
        returned_ids = tuple(state.memory_id for state in scan.states)
        returned_labels = tuple(id_to_label.get(memory_id, "<unknown>") for memory_id in returned_ids)
        expected_rank = _expected_rank(returned_labels, case.expected_label)
        index_ids: tuple[str, ...] = ()
        index_labels: tuple[str, ...] = ()
        if index_status == "available":
            indexed = query_memory_lexical_index(repository, case.query)
            index_ids = tuple(hit.memory_id for hit in indexed.hits)
            index_labels = tuple(id_to_label.get(memory_id, "<unknown>") for memory_id in index_ids)
        results.append(
            RecallBenchmarkCaseResult(
                case_id=case.case_id,
                classification=case.classification,
                query=case.query,
                expected_label=case.expected_label,
                index_compatible=case.index_compatible,
                returned_labels=returned_labels,
                returned_memory_ids=returned_ids,
                expected_rank=expected_rank,
                index_returned_labels=index_labels,
                index_returned_memory_ids=index_ids,
            )
        )

    lexical = tuple(result for result in results if result.classification == "lexical")
    semantic = tuple(
        result for result in results if result.classification == "semantic_opportunity"
    )
    exclusions = tuple(result for result in results if result.classification == "exclusion")
    index_compatible = tuple(result for result in lexical if result.index_compatible)
    reciprocal_rank = sum(
        (Fraction(1, result.expected_rank) if result.expected_rank is not None else Fraction(0, 1))
        for result in lexical
    )
    index_coverage: str | None = None
    if index_status == "available":
        index_hits = sum(
            1
            for result in index_compatible
            if result.expected_label is not None
            and result.expected_label in result.index_returned_labels
        )
        index_coverage = _ratio(index_hits, len(index_compatible))

    return RecallBenchmarkReport(
        corpus_id=corpus.corpus_id,
        source_state_revision=repository.status().state_revision,
        recall_algorithm_id=DEFAULT_RECALL_ALGORITHM_ID,
        recall_algorithm_version=RECALL_ALGORITHM_VERSION,
        index_status=index_status,
        index_error_type=index_error_type,
        lexical_case_count=len(lexical),
        lexical_recall_at_1=_ratio(
            sum(result.expected_rank == 1 for result in lexical),
            len(lexical),
        ),
        lexical_recall_at_3=_ratio(
            sum(
                result.expected_rank is not None and result.expected_rank <= 3
                for result in lexical
            ),
            len(lexical),
        ),
        lexical_mrr=_fraction(reciprocal_rank, len(lexical)),
        semantic_opportunity_case_count=len(semantic),
        semantic_opportunity_miss_count=sum(result.expected_rank is None for result in semantic),
        semantic_opportunity_miss_rate=_ratio(
            sum(result.expected_rank is None for result in semantic),
            len(semantic),
        ),
        exclusion_case_count=len(exclusions),
        exclusion_pass_count=sum(not result.returned_labels for result in exclusions),
        index_compatible_lexical_case_count=len(index_compatible),
        index_coverage=index_coverage,
        cases=tuple(results),
    )


def _expected_rank(returned_labels: tuple[str, ...], expected_label: str | None) -> int | None:
    if expected_label is None:
        return None
    try:
        return returned_labels.index(expected_label) + 1
    except ValueError:
        return None


def _ratio(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return "0/0"
    return str(Fraction(numerator, denominator))


def _fraction(total: Fraction, count: int) -> str:
    if count == 0:
        return "0/0"
    return str(total / count)


def _parse_memory(value: dict[str, object]) -> RecallBenchmarkMemorySpec:
    sensitivity_value = value.get("sensitivity", "personal")
    if sensitivity_value not in {"public", "internal", "personal", "sensitive", "secret"}:
        raise RecallBenchmarkValidationError("benchmark memory sensitivity is invalid")
    archived = value.get("archived", False)
    if not isinstance(archived, bool):
        raise RecallBenchmarkValidationError("benchmark memory archived flag must be boolean")
    return RecallBenchmarkMemorySpec(
        label=_require_string(value, "label"),
        subject=_require_string(value, "subject"),
        content=_require_string(value, "content"),
        source_reference=_optional_string(value, "source_reference"),
        sensitivity=cast(RecordSensitivity, sensitivity_value),
        archived=archived,
    )


def _parse_case(value: dict[str, object]) -> RecallBenchmarkCaseSpec:
    classification = _require_string(value, "classification")
    if classification not in {"lexical", "semantic_opportunity", "exclusion"}:
        raise RecallBenchmarkValidationError("benchmark case classification is invalid")
    index_compatible = value.get("index_compatible")
    if not isinstance(index_compatible, bool):
        raise RecallBenchmarkValidationError("benchmark case index_compatible must be boolean")
    return RecallBenchmarkCaseSpec(
        case_id=_require_string(value, "case_id"),
        classification=cast(RecallBenchmarkClassification, classification),
        query=_require_string(value, "query"),
        expected_label=_optional_string(value, "expected_label"),
        index_compatible=index_compatible,
    )


def _require_object(value: object, name: str) -> dict[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise RecallBenchmarkValidationError(f"{name} must be an object")
    return cast(dict[str, object], value)


def _require_object_list(value: dict[str, object], key: str) -> tuple[dict[str, object], ...]:
    raw = value.get(key)
    if not isinstance(raw, list):
        raise RecallBenchmarkValidationError(f"benchmark corpus {key} must be a list")
    return tuple(_require_object(item, f"benchmark corpus {key} item") for item in raw)


def _require_string(value: dict[str, object], key: str) -> str:
    raw = value.get(key)
    if not isinstance(raw, str) or not raw.strip():
        raise RecallBenchmarkValidationError(f"benchmark {key} must be non-empty text")
    return raw.strip()


def _optional_string(value: dict[str, object], key: str) -> str | None:
    raw = value.get(key)
    if raw is None:
        return None
    if not isinstance(raw, str) or not raw.strip():
        raise RecallBenchmarkValidationError(f"benchmark {key} must be text or null")
    return raw.strip()


def _require_int(value: dict[str, object], key: str) -> int:
    raw = value.get(key)
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise RecallBenchmarkValidationError(f"benchmark {key} must be an integer")
    return raw


__all__ = [
    "RECALL_BENCHMARK_CORPUS_SCHEMA_VERSION",
    "RECALL_BENCHMARK_REPORT_SCHEMA_VERSION",
    "RecallBenchmarkBindings",
    "RecallBenchmarkCaseResult",
    "RecallBenchmarkCaseSpec",
    "RecallBenchmarkClassification",
    "RecallBenchmarkCorpus",
    "RecallBenchmarkError",
    "RecallBenchmarkMemorySpec",
    "RecallBenchmarkReport",
    "RecallBenchmarkValidationError",
    "load_recall_benchmark_corpus",
    "populate_synthetic_recall_benchmark",
    "run_recall_benchmark",
]
