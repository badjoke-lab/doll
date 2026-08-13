from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from doll import state, workspace
from doll.memory import ConfirmedMemoryService
from doll.ollama_adapter import OllamaEndpoint, OllamaHttpResponse
from doll.recall_benchmark import load_recall_benchmark_corpus, populate_synthetic_recall_benchmark
from doll.recall_state import derive_memory_recall_state
from doll.runtime_adapter import RuntimeAdapterContext
from doll.semantic_candidate import (
    MAX_SEMANTIC_VECTOR_DIMENSIONS,
    OllamaSemanticEmbeddingClient,
    SemanticCandidateConfig,
    SemanticCandidateResponseError,
    SemanticCandidateUnavailableError,
    SemanticCandidateValidationError,
    evaluate_semantic_benchmark,
    rank_semantic_memories,
)

_CORPUS_PATH = (
    Path(__file__).parents[1] / "docs" / "testing" / "imp-087-memory-recall-benchmark-corpus.json"
)

Vectorizer = Callable[[str], list[float]]


class FakeEmbeddingTransport:
    def __init__(
        self,
        vectorizer: Vectorizer,
        *,
        endpoint: OllamaEndpoint | None = None,
        embed_payload: object | None = None,
        embed_status: int = 200,
    ) -> None:
        self.endpoint = endpoint or OllamaEndpoint()
        self.vectorizer = vectorizer
        self.embed_payload = embed_payload
        self.embed_status = embed_status
        self.calls: list[tuple[str, str, bytes | None]] = []

    def request_json(
        self,
        method: str,
        path: str,
        *,
        body: bytes | None,
        context: RuntimeAdapterContext | None,
        maximum_bytes: int,
    ) -> OllamaHttpResponse:
        del context, maximum_bytes
        self.calls.append((method, path, body))
        if path == "/api/version":
            return OllamaHttpResponse(200, b'{"version":"0.11.10"}')
        if path == "/api/tags":
            digest = "a" * 64
            return OllamaHttpResponse(
                200,
                json.dumps(
                    {
                        "models": [
                            {
                                "name": "embeddinggemma",
                                "model": "embeddinggemma",
                                "digest": f"sha256:{digest}",
                            }
                        ]
                    },
                    separators=(",", ":"),
                ).encode("utf-8"),
            )
        if path != "/api/embed":
            raise AssertionError(f"unexpected fake transport path: {path}")
        if self.embed_payload is not None:
            payload = self.embed_payload
        else:
            assert body is not None
            request = json.loads(body.decode("utf-8"))
            assert request["model"] == "embeddinggemma"
            assert request["truncate"] is False
            payload = {
                "model": "embeddinggemma",
                "embeddings": [self.vectorizer(text) for text in request["input"]],
            }
        return OllamaHttpResponse(
            self.embed_status,
            json.dumps(payload, separators=(",", ":"), allow_nan=True).encode("utf-8"),
        )

    def stream_ndjson(self, *args: object, **kwargs: object) -> tuple[bytes, ...]:
        del args, kwargs
        raise AssertionError("semantic candidate must never use streaming")


def _client(transport: FakeEmbeddingTransport) -> OllamaSemanticEmbeddingClient:
    return OllamaSemanticEmbeddingClient(
        SemanticCandidateConfig(model_name="embeddinggemma", local_only_confirmed=True),
        transport=transport,
    )


def _initialized_workspace(root: Path) -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(root)
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def test_imp_088_embed_uses_only_explicit_loopback_api_and_identity(tmp_path: Path) -> None:
    del tmp_path
    transport = FakeEmbeddingTransport(lambda text: [1.0, float(len(text) + 1)])
    client = _client(transport)

    batch = client.embed(("alpha", "beta"))
    identity = client.inspect_identity()

    assert batch.model_name == "embeddinggemma"
    assert batch.dimensions == 2
    assert len(batch.vectors) == 2
    assert identity.model_name == "embeddinggemma"
    assert identity.model_revision == f"sha256-{'a' * 64}"
    assert identity.ollama_version == "0.11.10"
    assert [path for _, path, _ in transport.calls] == ["/api/embed", "/api/version", "/api/tags"]
    assert all(path != "/api/pull" for _, path, _ in transport.calls)
    embed_body = json.loads(transport.calls[0][2].decode("utf-8"))  # type: ignore[union-attr]
    assert embed_body == {
        "model": "embeddinggemma",
        "input": ["alpha", "beta"],
        "truncate": False,
    }


def test_imp_088_requires_explicit_local_only_and_exact_endpoint() -> None:
    transport = FakeEmbeddingTransport(lambda text: [1.0, float(len(text) + 1)])
    client = OllamaSemanticEmbeddingClient(
        SemanticCandidateConfig(model_name="embeddinggemma", local_only_confirmed=False),
        transport=transport,
    )
    with pytest.raises(SemanticCandidateValidationError):
        client.embed(("alpha",))

    mismatched = FakeEmbeddingTransport(
        lambda text: [1.0, float(len(text) + 1)],
        endpoint=OllamaEndpoint(port=11435),
    )
    with pytest.raises(SemanticCandidateValidationError):
        OllamaSemanticEmbeddingClient(
            SemanticCandidateConfig(model_name="embeddinggemma", local_only_confirmed=True),
            transport=mismatched,
        )

    with pytest.raises(SemanticCandidateValidationError):
        SemanticCandidateConfig(model_name="embeddinggemma:cloud", local_only_confirmed=True)


def test_imp_088_unavailable_model_fails_closed_without_fallback() -> None:
    transport = FakeEmbeddingTransport(
        lambda text: [1.0, float(len(text) + 1)],
        embed_status=404,
    )
    with pytest.raises(SemanticCandidateUnavailableError):
        _client(transport).embed(("alpha",))
    assert [path for _, path, _ in transport.calls] == ["/api/embed"]


@pytest.mark.parametrize(
    "payload",
    [
        {"model": "wrong", "embeddings": [[1.0, 0.0]]},
        {"model": "embeddinggemma", "embeddings": []},
        {"model": "embeddinggemma", "embeddings": [[1.0], [1.0]]},
        {"model": "embeddinggemma", "embeddings": [[]]},
        {"model": "embeddinggemma", "embeddings": [[0.0, 0.0]]},
        {"model": "embeddinggemma", "embeddings": [[True, 1.0]]},
        {"model": "embeddinggemma", "embeddings": [[float("nan"), 1.0]]},
        {"model": "embeddinggemma", "embeddings": [[1.0] * (MAX_SEMANTIC_VECTOR_DIMENSIONS + 1)]},
    ],
)
def test_imp_088_malformed_vectors_fail_closed(payload: object) -> None:
    transport = FakeEmbeddingTransport(lambda text: [1.0], embed_payload=payload)
    with pytest.raises(SemanticCandidateResponseError):
        _client(transport).embed(("alpha",))


def test_imp_088_rank_is_read_only_deterministic_and_excludes_secret_archived(
    tmp_path: Path,
) -> None:
    initialized = _initialized_workspace(tmp_path / "workspace")
    with state.open_state_repository(initialized.root) as repository:
        service = ConfirmedMemoryService(repository)
        preferred = service.create(subject="alpha preferred", content="target")
        tied = service.create(subject="alpha tied", content="target")
        secret = service.create(
            subject="alpha secret",
            content="target",
            sensitivity="secret",
        )
        archived = service.create(subject="alpha archived", content="target")
        service.archive(archived.record_id, expected_revision=archived.revision)
        state_revision_before = repository.status().state_revision
        record_count_before = repository.status().record_count

    def vectorizer(text: str) -> list[float]:
        if text == "alpha":
            return [1.0, 0.0]
        if "preferred" in text:
            return [1.0, 0.0]
        if "tied" in text:
            return [1.0, 0.0]
        return [0.0, 1.0]

    client = _client(FakeEmbeddingTransport(vectorizer))
    with state.open_state_repository(
        initialized.root,
        read_only=True,
        immutable=True,
    ) as repository:
        first = rank_semantic_memories(repository, "alpha", client)
        second = rank_semantic_memories(repository, "alpha", client)
        returned = {item.memory_id for item in first.states}
        assert first.to_dict() == second.to_dict()
        assert preferred.record_id in returned
        assert tied.record_id in returned
        assert secret.record_id not in returned
        assert archived.record_id not in returned
        tied_expected = sorted((preferred.record_id, tied.record_id))
        tied_actual = [
            item.memory_id
            for item in first.states
            if item.memory_id in {preferred.record_id, tied.record_id}
        ]
        assert tied_actual == tied_expected
        assert repository.status().state_revision == state_revision_before
        assert repository.status().record_count == record_count_before


def test_imp_088_synthetic_benchmark_math_can_pass_without_changing_lexical_fallback(
    tmp_path: Path,
) -> None:
    corpus = load_recall_benchmark_corpus(_CORPUS_PATH)
    initialized = _initialized_workspace(tmp_path / "workspace")
    with state.open_state_repository(initialized.root) as repository:
        bindings = populate_synthetic_recall_benchmark(repository, corpus)
        state_revision_before = repository.status().state_revision
        record_count_before = repository.status().record_count

    dimensions = len([case for case in corpus.cases if case.classification != "exclusion"]) + 1
    text_vectors: dict[str, list[float]] = {}
    active_memories = {
        memory.label: f"{memory.subject}\n{memory.content}"
        for memory in corpus.memories
        if not memory.archived and memory.sensitivity != "secret"
    }
    for index, case in enumerate(
        case for case in corpus.cases if case.classification != "exclusion"
    ):
        vector = [0.0] * dimensions
        vector[index] = 1.0
        text_vectors[case.query] = vector
        assert case.expected_label is not None
        text_vectors[active_memories[case.expected_label]] = vector
    fallback = [0.0] * dimensions
    fallback[-1] = 1.0

    client = _client(FakeEmbeddingTransport(lambda text: text_vectors.get(text, fallback)))
    with state.open_state_repository(
        initialized.root,
        read_only=True,
        immutable=True,
    ) as repository:
        lexical_before = derive_memory_recall_state(repository, "alpha beta").to_dict()
        report = evaluate_semantic_benchmark(
            repository,
            corpus,
            bindings,
            client,
            evidence_kind="synthetic",
        )
        lexical_after = derive_memory_recall_state(repository, "alpha beta").to_dict()

        assert report.evidence_kind == "synthetic"
        assert report.lexical_case_count == 6
        assert report.lexical_recall_at_1 == "1"
        assert report.lexical_recall_at_3 == "1"
        assert report.semantic_opportunity_case_count == 2
        assert report.semantic_opportunity_hit_count == 2
        assert report.semantic_opportunity_hit_rate == "1"
        assert report.exclusion_target_count == 2
        assert report.exclusion_pass_count == 2
        assert report.lexical_fallback_available is True
        assert report.usefulness_gate_passed is True
        assert lexical_before == lexical_after
        assert repository.status().state_revision == state_revision_before
        assert repository.status().record_count == record_count_before
