"""Opt-in local semantic-recall candidate for bounded usefulness experiments."""

from __future__ import annotations

import json
import math
import re
import time
from dataclasses import dataclass, field
from typing import Literal, cast
from uuid import uuid4

from doll.memory import MAX_MEMORY_LIMIT, ConfirmedMemoryInfo, ConfirmedMemoryService
from doll.ollama_adapter import (
    MAX_OLLAMA_JSON_BYTES,
    LoopbackOllamaTransport,
    OllamaEndpoint,
    OllamaHttpResponse,
    OllamaTransport,
    OllamaTransportFailure,
)
from doll.recall_benchmark import RecallBenchmarkBindings, RecallBenchmarkCorpus
from doll.recall_state import derive_memory_recall_state
from doll.runtime_adapter import RuntimeAdapterContext, RuntimeCancellationToken
from doll.state_repository import StateRepository

SemanticEvidenceKind = Literal["synthetic", "real_model"]

SEMANTIC_CANDIDATE_REPORT_SCHEMA_VERSION = 1
SEMANTIC_CANDIDATE_POLICY_ID = "confirmed-memory-subject-content-cosine"
SEMANTIC_CANDIDATE_POLICY_VERSION = "1"
MAX_SEMANTIC_MEMORIES = 64
MAX_SEMANTIC_INPUTS = MAX_SEMANTIC_MEMORIES + 1
MAX_SEMANTIC_INPUT_CHARS = 6_241
MAX_SEMANTIC_QUERY_CHARS = 240
MAX_SEMANTIC_VECTOR_DIMENSIONS = 1_024
MAX_SEMANTIC_RESULT_LIMIT = 64
MAX_SEMANTIC_TIMEOUT_SECONDS = 60.0
_MODEL_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/:+\-]{0,255}$")
_CLOUD_TAG_PATTERN = re.compile(r"(?:^|[-_.])cloud$", re.IGNORECASE)
_HEX_DIGEST_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")
_VERSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+\-]{0,127}$")


class SemanticCandidateError(RuntimeError):
    """Base class for experimental semantic-candidate failures."""


class SemanticCandidateValidationError(SemanticCandidateError):
    """Raised when an experiment request crosses an accepted boundary."""


class SemanticCandidateUnavailableError(SemanticCandidateError):
    """Raised when the explicitly requested local candidate is unavailable."""


class SemanticCandidateResponseError(SemanticCandidateError):
    """Raised when local embedding output is malformed or unsafe."""


@dataclass(frozen=True, slots=True)
class SemanticCandidateConfig:
    """Explicit local-only configuration; there is no download or fallback field."""

    model_name: str
    local_only_confirmed: bool = False
    endpoint: OllamaEndpoint = field(default_factory=OllamaEndpoint)

    def __post_init__(self) -> None:
        object.__setattr__(self, "model_name", _validate_model_name(self.model_name))
        if not isinstance(self.local_only_confirmed, bool):
            raise SemanticCandidateValidationError("local-only confirmation must be boolean")
        if not isinstance(self.endpoint, OllamaEndpoint):
            raise SemanticCandidateValidationError("semantic candidate endpoint is invalid")


@dataclass(frozen=True, slots=True)
class SemanticModelIdentity:
    model_name: str
    model_revision: str | None
    ollama_version: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "model_name": self.model_name,
            "model_revision": self.model_revision,
            "ollama_version": self.ollama_version,
        }


@dataclass(frozen=True, slots=True)
class SemanticEmbeddingBatch:
    model_name: str
    vectors: tuple[tuple[float, ...], ...]

    @property
    def dimensions(self) -> int:
        return len(self.vectors[0]) if self.vectors else 0


@dataclass(frozen=True, slots=True)
class SemanticRecallState:
    memory_id: str
    memory_revision: int
    source_state_revision: int
    policy_id: str
    policy_version: str
    model_name: str
    cosine_score: float
    rank: int

    def to_dict(self) -> dict[str, object]:
        return {
            "memory_id": self.memory_id,
            "memory_revision": self.memory_revision,
            "source_state_revision": self.source_state_revision,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "model_name": self.model_name,
            "cosine_score": self.cosine_score,
            "rank": self.rank,
        }


@dataclass(frozen=True, slots=True)
class SemanticRecallReport:
    source_state_revision: int
    policy_id: str
    policy_version: str
    model_name: str
    vector_dimensions: int
    scanned_memories: int
    scan_truncated: bool
    states: tuple[SemanticRecallState, ...]

    @property
    def result_count(self) -> int:
        return len(self.states)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": SEMANTIC_CANDIDATE_REPORT_SCHEMA_VERSION,
            "source_state_revision": self.source_state_revision,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "model_name": self.model_name,
            "vector_dimensions": self.vector_dimensions,
            "scanned_memories": self.scanned_memories,
            "scan_truncated": self.scan_truncated,
            "result_count": self.result_count,
            "states": [state.to_dict() for state in self.states],
        }


@dataclass(frozen=True, slots=True)
class SemanticBenchmarkCaseResult:
    case_id: str
    classification: str
    expected_label: str | None
    returned_labels: tuple[str, ...]
    returned_memory_ids: tuple[str, ...]
    expected_rank: int | None

    def logical_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "classification": self.classification,
            "expected_label": self.expected_label,
            "returned_labels": list(self.returned_labels),
            "expected_rank": self.expected_rank,
        }


@dataclass(frozen=True, slots=True)
class SemanticBenchmarkReport:
    evidence_kind: SemanticEvidenceKind
    model_name: str
    policy_id: str
    policy_version: str
    lexical_case_count: int
    lexical_recall_at_1: str
    lexical_recall_at_3: str
    semantic_opportunity_case_count: int
    semantic_opportunity_hit_count: int
    semantic_opportunity_hit_rate: str
    exclusion_target_count: int
    exclusion_pass_count: int
    lexical_fallback_available: bool
    usefulness_gate_passed: bool
    cases: tuple[SemanticBenchmarkCaseResult, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": SEMANTIC_CANDIDATE_REPORT_SCHEMA_VERSION,
            "evidence_kind": self.evidence_kind,
            "model_name": self.model_name,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "lexical_case_count": self.lexical_case_count,
            "lexical_recall_at_1": self.lexical_recall_at_1,
            "lexical_recall_at_3": self.lexical_recall_at_3,
            "semantic_opportunity_case_count": self.semantic_opportunity_case_count,
            "semantic_opportunity_hit_count": self.semantic_opportunity_hit_count,
            "semantic_opportunity_hit_rate": self.semantic_opportunity_hit_rate,
            "exclusion_target_count": self.exclusion_target_count,
            "exclusion_pass_count": self.exclusion_pass_count,
            "lexical_fallback_available": self.lexical_fallback_available,
            "usefulness_gate_passed": self.usefulness_gate_passed,
            "cases": [case.logical_dict() for case in self.cases],
        }


class OllamaSemanticEmbeddingClient:
    """Bounded `/api/embed` client over doll's existing fixed-loopback transport."""

    __slots__ = ("_config", "_transport")

    def __init__(
        self,
        config: SemanticCandidateConfig,
        *,
        transport: OllamaTransport | None = None,
    ) -> None:
        if not isinstance(config, SemanticCandidateConfig):
            raise SemanticCandidateValidationError("semantic candidate configuration is invalid")
        self._config = config
        candidate = transport if transport is not None else LoopbackOllamaTransport(config.endpoint)
        try:
            endpoint = candidate.endpoint
        except Exception:
            raise SemanticCandidateValidationError("semantic candidate transport is invalid") from None
        if not isinstance(endpoint, OllamaEndpoint) or endpoint != config.endpoint:
            raise SemanticCandidateValidationError("semantic candidate transport endpoint mismatch")
        self._transport = candidate

    @property
    def model_name(self) -> str:
        return self._config.model_name

    def embed(
        self,
        inputs: tuple[str, ...],
        *,
        timeout_seconds: float = MAX_SEMANTIC_TIMEOUT_SECONDS,
    ) -> SemanticEmbeddingBatch:
        if not self._config.local_only_confirmed:
            raise SemanticCandidateValidationError("semantic candidate requires local-only confirmation")
        safe_inputs = _validate_inputs(inputs)
        timeout = _validate_timeout(timeout_seconds)
        body = json.dumps(
            {"model": self.model_name, "input": list(safe_inputs), "truncate": False},
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        if len(body) > MAX_OLLAMA_JSON_BYTES:
            raise SemanticCandidateValidationError("semantic embedding request is too large")
        context = RuntimeAdapterContext(
            operation_id=str(uuid4()),
            deadline_monotonic=time.monotonic() + timeout,
            cancellation=RuntimeCancellationToken(),
        )
        response = self._request("POST", "/api/embed", body=body, context=context)
        if response.status_code == 404:
            raise SemanticCandidateUnavailableError("local embedding model is unavailable")
        if response.status_code != 200:
            raise SemanticCandidateUnavailableError("local embedding runtime rejected the request")
        document = _load_json_object(response.body)
        if document.get("model") != self.model_name:
            raise SemanticCandidateResponseError("embedding response model identity mismatch")
        vectors = _validate_vectors(document.get("embeddings"), len(safe_inputs))
        return SemanticEmbeddingBatch(model_name=self.model_name, vectors=vectors)

    def inspect_identity(self) -> SemanticModelIdentity:
        """Inspect only already-installed local Ollama state; never pull or install anything."""

        if not self._config.local_only_confirmed:
            raise SemanticCandidateValidationError("semantic candidate requires local-only confirmation")
        version_response = self._request("GET", "/api/version", body=None, context=None)
        if version_response.status_code != 200:
            raise SemanticCandidateUnavailableError("local Ollama version is unavailable")
        version_document = _load_json_object(version_response.body)
        ollama_version = _validate_version(version_document.get("version"))
        tags_response = self._request("GET", "/api/tags", body=None, context=None)
        if tags_response.status_code != 200:
            raise SemanticCandidateUnavailableError("local Ollama model inventory is unavailable")
        revision = _find_model_revision(tags_response.body, self.model_name)
        if revision is None:
            raise SemanticCandidateUnavailableError("requested embedding model is not installed locally")
        return SemanticModelIdentity(self.model_name, revision, ollama_version)

    def _request(
        self,
        method: str,
        path: str,
        *,
        body: bytes | None,
        context: RuntimeAdapterContext | None,
    ) -> OllamaHttpResponse:
        try:
            return self._transport.request_json(
                method,
                path,
                body=body,
                context=context,
                maximum_bytes=MAX_OLLAMA_JSON_BYTES,
            )
        except OllamaTransportFailure as exc:
            raise SemanticCandidateUnavailableError("local embedding transport failed") from exc


def rank_semantic_memories(
    repository: StateRepository,
    query: str,
    client: OllamaSemanticEmbeddingClient,
    *,
    limit: int = 20,
) -> SemanticRecallReport:
    """Rank active non-secret confirmed memories in memory without changing Doll State."""

    if not repository.read_only:
        raise SemanticCandidateValidationError("semantic candidate requires a read-only repository")
    safe_query = _validate_query(query)
    safe_limit = _validate_limit(limit)
    source_state_revision = repository.status().state_revision
    memory_service = ConfirmedMemoryService(repository)
    listed = memory_service.list(limit=min(MAX_MEMORY_LIMIT, MAX_SEMANTIC_MEMORIES + 1))
    eligible = tuple(memory for memory in listed if memory.sensitivity != "secret")
    scan_truncated = len(eligible) > MAX_SEMANTIC_MEMORIES
    memories = eligible[:MAX_SEMANTIC_MEMORIES]
    if not memories:
        return SemanticRecallReport(
            source_state_revision=source_state_revision,
            policy_id=SEMANTIC_CANDIDATE_POLICY_ID,
            policy_version=SEMANTIC_CANDIDATE_POLICY_VERSION,
            model_name=client.model_name,
            vector_dimensions=0,
            scanned_memories=0,
            scan_truncated=scan_truncated,
            states=(),
        )
    texts = (safe_query,) + tuple(_memory_retrieval_text(memory) for memory in memories)
    batch = client.embed(texts)
    query_vector = batch.vectors[0]
    candidates = tuple(
        (
            memory,
            _cosine_similarity(query_vector, vector),
        )
        for memory, vector in zip(memories, batch.vectors[1:], strict=True)
    )
    ordered = sorted(candidates, key=lambda item: (-item[1], item[0].record_id))[:safe_limit]
    states = tuple(
        SemanticRecallState(
            memory_id=memory.record_id,
            memory_revision=memory.revision,
            source_state_revision=source_state_revision,
            policy_id=SEMANTIC_CANDIDATE_POLICY_ID,
            policy_version=SEMANTIC_CANDIDATE_POLICY_VERSION,
            model_name=client.model_name,
            cosine_score=score,
            rank=rank,
        )
        for rank, (memory, score) in enumerate(ordered, start=1)
    )
    if repository.status().state_revision != source_state_revision:
        raise SemanticCandidateValidationError("Doll State changed during semantic candidate ranking")
    return SemanticRecallReport(
        source_state_revision=source_state_revision,
        policy_id=SEMANTIC_CANDIDATE_POLICY_ID,
        policy_version=SEMANTIC_CANDIDATE_POLICY_VERSION,
        model_name=client.model_name,
        vector_dimensions=batch.dimensions,
        scanned_memories=len(memories),
        scan_truncated=scan_truncated,
        states=states,
    )


def evaluate_semantic_benchmark(
    repository: StateRepository,
    corpus: RecallBenchmarkCorpus,
    bindings: RecallBenchmarkBindings,
    client: OllamaSemanticEmbeddingClient,
    *,
    evidence_kind: SemanticEvidenceKind,
) -> SemanticBenchmarkReport:
    """Compare one opt-in semantic candidate against the frozen IMP-087 synthetic corpus."""

    if evidence_kind not in {"synthetic", "real_model"}:
        raise SemanticCandidateValidationError("semantic evidence kind is invalid")
    if not repository.read_only:
        raise SemanticCandidateValidationError("semantic benchmark requires a read-only repository")
    id_to_label = bindings.memory_id_to_label()
    excluded_ids = {
        bindings.label_to_memory_id[memory.label]
        for memory in corpus.memories
        if memory.archived or memory.sensitivity == "secret"
    }
    results: list[SemanticBenchmarkCaseResult] = []
    all_returned_ids: set[str] = set()
    for case in corpus.cases:
        if case.classification == "exclusion":
            continue
        report = rank_semantic_memories(repository, case.query, client, limit=3)
        returned_ids = tuple(state.memory_id for state in report.states)
        returned_labels = tuple(id_to_label.get(memory_id, "<unknown>") for memory_id in returned_ids)
        all_returned_ids.update(returned_ids)
        expected_rank = _expected_rank(returned_labels, case.expected_label)
        results.append(
            SemanticBenchmarkCaseResult(
                case_id=case.case_id,
                classification=case.classification,
                expected_label=case.expected_label,
                returned_labels=returned_labels,
                returned_memory_ids=returned_ids,
                expected_rank=expected_rank,
            )
        )
    lexical = tuple(result for result in results if result.classification == "lexical")
    semantic = tuple(
        result for result in results if result.classification == "semantic_opportunity"
    )
    lexical_fallback_available = _verify_lexical_fallback(repository, corpus)
    semantic_hits = sum(result.expected_rank is not None for result in semantic)
    exclusion_pass_count = sum(memory_id not in all_returned_ids for memory_id in excluded_ids)
    lexical_recall_at_3 = _ratio(
        sum(result.expected_rank is not None and result.expected_rank <= 3 for result in lexical),
        len(lexical),
    )
    usefulness_gate_passed = (
        semantic_hits > 0
        and lexical_recall_at_3 == "1"
        and exclusion_pass_count == len(excluded_ids)
        and lexical_fallback_available
    )
    return SemanticBenchmarkReport(
        evidence_kind=evidence_kind,
        model_name=client.model_name,
        policy_id=SEMANTIC_CANDIDATE_POLICY_ID,
        policy_version=SEMANTIC_CANDIDATE_POLICY_VERSION,
        lexical_case_count=len(lexical),
        lexical_recall_at_1=_ratio(
            sum(result.expected_rank == 1 for result in lexical),
            len(lexical),
        ),
        lexical_recall_at_3=lexical_recall_at_3,
        semantic_opportunity_case_count=len(semantic),
        semantic_opportunity_hit_count=semantic_hits,
        semantic_opportunity_hit_rate=_ratio(semantic_hits, len(semantic)),
        exclusion_target_count=len(excluded_ids),
        exclusion_pass_count=exclusion_pass_count,
        lexical_fallback_available=lexical_fallback_available,
        usefulness_gate_passed=usefulness_gate_passed,
        cases=tuple(results),
    )


def _memory_retrieval_text(memory: ConfirmedMemoryInfo) -> str:
    return f"{memory.subject}\n{memory.content}"


def _verify_lexical_fallback(repository: StateRepository, corpus: RecallBenchmarkCorpus) -> bool:
    first = next((case for case in corpus.cases if case.classification == "lexical"), None)
    if first is None:
        return False
    return derive_memory_recall_state(repository, first.query).result_count > 0


def _validate_inputs(inputs: object) -> tuple[str, ...]:
    if not isinstance(inputs, tuple) or not 1 <= len(inputs) <= MAX_SEMANTIC_INPUTS:
        raise SemanticCandidateValidationError("semantic embedding input count is invalid")
    safe: list[str] = []
    for value in inputs:
        if not isinstance(value, str):
            raise SemanticCandidateValidationError("semantic embedding input must be text")
        normalized = value.strip()
        if not normalized or len(normalized) > MAX_SEMANTIC_INPUT_CHARS:
            raise SemanticCandidateValidationError("semantic embedding input size is invalid")
        if any(ord(character) < 32 and character not in {"\n", "\t"} for character in normalized):
            raise SemanticCandidateValidationError("semantic embedding input contains control characters")
        safe.append(normalized)
    return tuple(safe)


def _validate_query(query: object) -> str:
    if not isinstance(query, str):
        raise SemanticCandidateValidationError("semantic query must be text")
    normalized = query.strip()
    if not normalized or len(normalized) > MAX_SEMANTIC_QUERY_CHARS:
        raise SemanticCandidateValidationError("semantic query size is invalid")
    if any(ord(character) < 32 or ord(character) == 127 for character in normalized):
        raise SemanticCandidateValidationError("semantic query contains a control character")
    return normalized


def _validate_limit(limit: object) -> int:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_SEMANTIC_RESULT_LIMIT:
        raise SemanticCandidateValidationError("semantic result limit is invalid")
    return limit


def _validate_timeout(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise SemanticCandidateValidationError("semantic timeout is invalid")
    timeout = float(value)
    if not math.isfinite(timeout) or not 0 < timeout <= MAX_SEMANTIC_TIMEOUT_SECONDS:
        raise SemanticCandidateValidationError("semantic timeout is invalid")
    return timeout


def _validate_model_name(value: object) -> str:
    if not isinstance(value, str) or _MODEL_NAME_PATTERN.fullmatch(value) is None:
        raise SemanticCandidateValidationError("semantic model name is invalid")
    tag = value.rsplit(":", 1)[-1]
    if _CLOUD_TAG_PATTERN.search(tag) is not None:
        raise SemanticCandidateValidationError("cloud-tagged models are not allowed")
    return value


def _validate_vectors(value: object, expected_count: int) -> tuple[tuple[float, ...], ...]:
    if not isinstance(value, list) or len(value) != expected_count:
        raise SemanticCandidateResponseError("embedding vector count is invalid")
    vectors: list[tuple[float, ...]] = []
    dimensions: int | None = None
    for raw_vector in value:
        if not isinstance(raw_vector, list) or not raw_vector:
            raise SemanticCandidateResponseError("embedding vector is invalid")
        if len(raw_vector) > MAX_SEMANTIC_VECTOR_DIMENSIONS:
            raise SemanticCandidateResponseError("embedding vector dimension exceeds the bound")
        vector: list[float] = []
        for raw_number in raw_vector:
            if isinstance(raw_number, bool) or not isinstance(raw_number, int | float):
                raise SemanticCandidateResponseError("embedding vector contains a non-number")
            number = float(raw_number)
            if not math.isfinite(number):
                raise SemanticCandidateResponseError("embedding vector contains a non-finite value")
            vector.append(number)
        if dimensions is None:
            dimensions = len(vector)
        elif len(vector) != dimensions:
            raise SemanticCandidateResponseError("embedding vectors have inconsistent dimensions")
        if math.fsum(number * number for number in vector) <= 0:
            raise SemanticCandidateResponseError("embedding vector norm must be positive")
        vectors.append(tuple(vector))
    return tuple(vectors)


def _cosine_similarity(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    if len(left) != len(right) or not left:
        raise SemanticCandidateResponseError("embedding dimensions do not match")
    numerator = math.fsum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(math.fsum(value * value for value in left))
    right_norm = math.sqrt(math.fsum(value * value for value in right))
    if left_norm <= 0 or right_norm <= 0:
        raise SemanticCandidateResponseError("embedding norm must be positive")
    score = numerator / (left_norm * right_norm)
    if not math.isfinite(score):
        raise SemanticCandidateResponseError("cosine score is non-finite")
    return score


def _load_json_object(raw: object) -> dict[str, object]:
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_OLLAMA_JSON_BYTES:
        raise SemanticCandidateResponseError("semantic candidate response size is invalid")
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_object_without_duplicates,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, SemanticCandidateResponseError):
        raise SemanticCandidateResponseError("semantic candidate response is invalid JSON") from None
    if not isinstance(value, dict):
        raise SemanticCandidateResponseError("semantic candidate response must be an object")
    return cast(dict[str, object], value)


def _object_without_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise SemanticCandidateResponseError("semantic candidate response has duplicate keys")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> object:
    del value
    raise SemanticCandidateResponseError("semantic candidate response has an invalid constant")


def _find_model_revision(body: bytes, model_name: str) -> str | None:
    document = _load_json_object(body)
    models = document.get("models")
    if not isinstance(models, list) or len(models) > 1_000:
        raise SemanticCandidateResponseError("Ollama model inventory is invalid")
    found: str | None = None
    for raw in models:
        if not isinstance(raw, dict):
            raise SemanticCandidateResponseError("Ollama model inventory entry is invalid")
        name = raw.get("name", raw.get("model"))
        if name != model_name:
            continue
        if found is not None:
            raise SemanticCandidateResponseError("Ollama model inventory has duplicate names")
        digest = raw.get("digest")
        if not isinstance(digest, str):
            raise SemanticCandidateResponseError("Ollama model digest is invalid")
        normalized = digest.removeprefix("sha256:")
        if _HEX_DIGEST_PATTERN.fullmatch(normalized) is None:
            raise SemanticCandidateResponseError("Ollama model digest is invalid")
        found = f"sha256-{normalized.lower()}"
    return found


def _validate_version(value: object) -> str:
    if not isinstance(value, str) or _VERSION_PATTERN.fullmatch(value) is None:
        raise SemanticCandidateResponseError("Ollama version response is invalid")
    return value


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
    divisor = math.gcd(numerator, denominator)
    return f"{numerator // divisor}/{denominator // divisor}" if numerator != denominator else "1"


__all__ = [
    "MAX_SEMANTIC_INPUT_CHARS",
    "MAX_SEMANTIC_INPUTS",
    "MAX_SEMANTIC_MEMORIES",
    "MAX_SEMANTIC_RESULT_LIMIT",
    "MAX_SEMANTIC_TIMEOUT_SECONDS",
    "MAX_SEMANTIC_VECTOR_DIMENSIONS",
    "SEMANTIC_CANDIDATE_POLICY_ID",
    "SEMANTIC_CANDIDATE_POLICY_VERSION",
    "OllamaSemanticEmbeddingClient",
    "SemanticBenchmarkCaseResult",
    "SemanticBenchmarkReport",
    "SemanticCandidateConfig",
    "SemanticCandidateError",
    "SemanticCandidateResponseError",
    "SemanticCandidateUnavailableError",
    "SemanticCandidateValidationError",
    "SemanticEmbeddingBatch",
    "SemanticEvidenceKind",
    "SemanticModelIdentity",
    "SemanticRecallReport",
    "SemanticRecallState",
    "evaluate_semantic_benchmark",
    "rank_semantic_memories",
]
