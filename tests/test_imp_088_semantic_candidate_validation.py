from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any, cast

import pytest

from doll import state, workspace
from doll.ollama_adapter import (
    OllamaEndpoint,
    OllamaHttpResponse,
    OllamaTransport,
    OllamaTransportFailure,
)
from doll.recall_benchmark import (
    RecallBenchmarkBindings,
    load_recall_benchmark_corpus,
    populate_synthetic_recall_benchmark,
)
from doll.runtime_adapter import RuntimeAdapterContext
from doll.semantic_candidate import (
    MAX_SEMANTIC_INPUT_CHARS,
    MAX_SEMANTIC_INPUTS,
    MAX_SEMANTIC_RESULT_LIMIT,
    MAX_SEMANTIC_TIMEOUT_SECONDS,
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


class ControlledTransport:
    def __init__(
        self,
        *,
        endpoint: OllamaEndpoint | None = None,
        embed: OllamaHttpResponse | None = None,
        version: OllamaHttpResponse | None = None,
        tags: OllamaHttpResponse | None = None,
        failure: OllamaTransportFailure | None = None,
    ) -> None:
        self.endpoint = endpoint or OllamaEndpoint()
        self.embed_response = embed or OllamaHttpResponse(
            200,
            b'{"model":"embeddinggemma","embeddings":[[1.0,0.0]]}',
        )
        self.version_response = version or OllamaHttpResponse(200, b'{"version":"0.11.10"}')
        self.tags_response = tags or OllamaHttpResponse(
            200,
            (b'{"models":[{"name":"embeddinggemma","digest":"' + (b"a" * 64) + b'"}]}'),
        )
        self.failure = failure
        self.calls: list[str] = []

    def request_json(
        self,
        method: str,
        path: str,
        *,
        body: bytes | None,
        context: RuntimeAdapterContext | None,
        maximum_bytes: int,
    ) -> OllamaHttpResponse:
        del method, body, context, maximum_bytes
        self.calls.append(path)
        if self.failure is not None:
            raise self.failure
        if path == "/api/embed":
            return self.embed_response
        if path == "/api/version":
            return self.version_response
        if path == "/api/tags":
            return self.tags_response
        raise AssertionError(f"unexpected path: {path}")

    def stream_ndjson(
        self,
        path: str,
        *,
        body: bytes,
        context: RuntimeAdapterContext,
        maximum_bytes: int,
        maximum_line_bytes: int,
    ) -> Iterable[bytes]:
        del path, body, context, maximum_bytes, maximum_line_bytes
        raise AssertionError("semantic candidate must not stream")


def _client(transport: ControlledTransport | None = None) -> OllamaSemanticEmbeddingClient:
    candidate = transport or ControlledTransport()
    return OllamaSemanticEmbeddingClient(
        SemanticCandidateConfig(
            model_name="embeddinggemma",
            local_only_confirmed=True,
        ),
        transport=cast(OllamaTransport, candidate),
    )


def _workspace(root: Path) -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(root)
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


@pytest.mark.parametrize(
    "model_name",
    ["", "has space", ":bad", "embeddinggemma:cloud", cast(Any, 7)],
)
def test_imp_088_config_rejects_invalid_model_names(model_name: object) -> None:
    with pytest.raises(SemanticCandidateValidationError):
        SemanticCandidateConfig(
            model_name=cast(str, model_name),
            local_only_confirmed=True,
        )


def test_imp_088_config_and_client_reject_invalid_types() -> None:
    with pytest.raises(SemanticCandidateValidationError):
        SemanticCandidateConfig(
            model_name="embeddinggemma",
            local_only_confirmed=cast(bool, "yes"),
        )
    with pytest.raises(SemanticCandidateValidationError):
        SemanticCandidateConfig(
            model_name="embeddinggemma",
            local_only_confirmed=True,
            endpoint=cast(OllamaEndpoint, object()),
        )
    with pytest.raises(SemanticCandidateValidationError):
        OllamaSemanticEmbeddingClient(cast(SemanticCandidateConfig, object()))
    with pytest.raises(SemanticCandidateValidationError):
        OllamaSemanticEmbeddingClient(
            SemanticCandidateConfig(
                model_name="embeddinggemma",
                local_only_confirmed=True,
            ),
            transport=cast(OllamaTransport, object()),
        )


@pytest.mark.parametrize(
    "inputs",
    [
        cast(Any, []),
        (),
        tuple("x" for _ in range(MAX_SEMANTIC_INPUTS + 1)),
        (cast(Any, 7),),
        ("",),
        ("x" * (MAX_SEMANTIC_INPUT_CHARS + 1),),
        ("bad\x00text",),
    ],
)
def test_imp_088_embed_input_validation_fails_before_transport(inputs: object) -> None:
    transport = ControlledTransport()
    with pytest.raises(SemanticCandidateValidationError):
        _client(transport).embed(cast(tuple[str, ...], inputs))
    assert transport.calls == []


@pytest.mark.parametrize(
    "timeout",
    [cast(Any, True), cast(Any, "1"), 0.0, -1.0, MAX_SEMANTIC_TIMEOUT_SECONDS + 1, float("nan")],
)
def test_imp_088_timeout_validation_fails_before_transport(timeout: object) -> None:
    transport = ControlledTransport()
    with pytest.raises(SemanticCandidateValidationError):
        _client(transport).embed(("alpha",), timeout_seconds=cast(float, timeout))
    assert transport.calls == []


def test_imp_088_transport_and_http_failures_do_not_fallback() -> None:
    transport = ControlledTransport(
        failure=OllamaTransportFailure("failure"),
    )
    with pytest.raises(SemanticCandidateUnavailableError):
        _client(transport).embed(("alpha",))
    assert transport.calls == ["/api/embed"]

    rejected = ControlledTransport(embed=OllamaHttpResponse(500, b'{"error":"no"}'))
    with pytest.raises(SemanticCandidateUnavailableError):
        _client(rejected).embed(("alpha",))
    assert rejected.calls == ["/api/embed"]


@pytest.mark.parametrize(
    "raw",
    [
        b"{",
        b"[]",
        b'{"model":"embeddinggemma","model":"embeddinggemma","embeddings":[[1.0]]}',
        b'{"model":"embeddinggemma","embeddings":[[NaN]]}',
        b'{"model":"embeddinggemma","embeddings":[[1.0],[1.0]]}',
        b'{"model":"embeddinggemma","embeddings":[["x"]]}',
        b'{"model":"embeddinggemma","embeddings":[[1e309]]}',
    ],
)
def test_imp_088_embed_response_validation_fails_closed(raw: bytes) -> None:
    transport = ControlledTransport(embed=OllamaHttpResponse(200, raw))
    with pytest.raises(SemanticCandidateResponseError):
        _client(transport).embed(("alpha",))


def test_imp_088_inconsistent_vector_dimensions_fail_closed() -> None:
    transport = ControlledTransport(
        embed=OllamaHttpResponse(
            200,
            b'{"model":"embeddinggemma","embeddings":[[1.0,0.0],[1.0]]}',
        )
    )
    with pytest.raises(SemanticCandidateResponseError):
        _client(transport).embed(("alpha", "beta"))


@pytest.mark.parametrize(
    ("version", "tags", "error"),
    [
        (OllamaHttpResponse(500, b"{}"), None, SemanticCandidateUnavailableError),
        (
            OllamaHttpResponse(200, b'{"version":"bad version"}'),
            None,
            SemanticCandidateResponseError,
        ),
        (
            None,
            OllamaHttpResponse(500, b"{}"),
            SemanticCandidateUnavailableError,
        ),
        (
            None,
            OllamaHttpResponse(200, b'{"models":[]}'),
            SemanticCandidateUnavailableError,
        ),
        (
            None,
            OllamaHttpResponse(200, b'{"models":{}}'),
            SemanticCandidateResponseError,
        ),
        (
            None,
            OllamaHttpResponse(200, b'{"models":[1]}'),
            SemanticCandidateResponseError,
        ),
        (
            None,
            OllamaHttpResponse(
                200,
                b'{"models":[{"name":"embeddinggemma","digest":7}]}',
            ),
            SemanticCandidateResponseError,
        ),
        (
            None,
            OllamaHttpResponse(
                200,
                b'{"models":[{"name":"embeddinggemma","digest":"bad"}]}',
            ),
            SemanticCandidateResponseError,
        ),
        (
            None,
            OllamaHttpResponse(
                200,
                (
                    b'{"models":['
                    b'{"name":"embeddinggemma","digest":"' + (b"a" * 64) + b'"},'
                    b'{"name":"embeddinggemma","digest":"' + (b"b" * 64) + b'"}]}'
                ),
            ),
            SemanticCandidateResponseError,
        ),
    ],
)
def test_imp_088_identity_inventory_validation_fails_closed(
    version: OllamaHttpResponse | None,
    tags: OllamaHttpResponse | None,
    error: type[Exception],
) -> None:
    transport = ControlledTransport(version=version, tags=tags)
    with pytest.raises(error):
        _client(transport).inspect_identity()


def test_imp_088_identity_requires_local_confirmation() -> None:
    client = OllamaSemanticEmbeddingClient(
        SemanticCandidateConfig(
            model_name="embeddinggemma",
            local_only_confirmed=False,
        ),
        transport=cast(OllamaTransport, ControlledTransport()),
    )
    with pytest.raises(SemanticCandidateValidationError):
        client.inspect_identity()


@pytest.mark.parametrize(
    "query",
    [cast(Any, 7), "", "x" * 241, "bad\nquery"],
)
def test_imp_088_rank_query_validation_fails_closed(tmp_path: Path, query: object) -> None:
    initialized = _workspace(tmp_path / "workspace")
    with state.open_state_repository(
        initialized.root,
        read_only=True,
        immutable=True,
    ) as repository:
        with pytest.raises(SemanticCandidateValidationError):
            rank_semantic_memories(repository, cast(str, query), _client())


@pytest.mark.parametrize("limit", [cast(Any, True), 0, MAX_SEMANTIC_RESULT_LIMIT + 1])
def test_imp_088_rank_limit_validation_fails_closed(tmp_path: Path, limit: object) -> None:
    initialized = _workspace(tmp_path / "workspace")
    with state.open_state_repository(
        initialized.root,
        read_only=True,
        immutable=True,
    ) as repository:
        with pytest.raises(SemanticCandidateValidationError):
            rank_semantic_memories(
                repository,
                "alpha",
                _client(),
                limit=cast(int, limit),
            )


def test_imp_088_rank_requires_read_only_and_handles_empty_memory(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path / "workspace")
    with state.open_state_repository(initialized.root) as repository:
        with pytest.raises(SemanticCandidateValidationError):
            rank_semantic_memories(repository, "alpha", _client())

    with state.open_state_repository(
        initialized.root,
        read_only=True,
        immutable=True,
    ) as repository:
        report = rank_semantic_memories(repository, "alpha", _client())
        assert report.result_count == 0
        assert report.vector_dimensions == 0
        assert report.scanned_memories == 0
        assert report.states == ()


def test_imp_088_benchmark_rejects_invalid_authority_inputs(tmp_path: Path) -> None:
    corpus = load_recall_benchmark_corpus(_CORPUS_PATH)
    initialized = _workspace(tmp_path / "workspace")
    with state.open_state_repository(initialized.root) as repository:
        bindings = populate_synthetic_recall_benchmark(repository, corpus)
        with pytest.raises(SemanticCandidateValidationError):
            evaluate_semantic_benchmark(
                repository,
                corpus,
                bindings,
                _client(),
                evidence_kind="synthetic",
            )

    with state.open_state_repository(
        initialized.root,
        read_only=True,
        immutable=True,
    ) as repository:
        with pytest.raises(SemanticCandidateValidationError):
            evaluate_semantic_benchmark(
                repository,
                corpus,
                bindings,
                _client(),
                evidence_kind=cast(Any, "invalid"),
            )
        with pytest.raises(
            SemanticCandidateValidationError,
            match="semantic benchmark bindings do not match the corpus",
        ):
            evaluate_semantic_benchmark(
                repository,
                corpus,
                RecallBenchmarkBindings(label_to_memory_id={}),
                _client(),
                evidence_kind="synthetic",
            )
