from __future__ import annotations

import http.client as http_client
import json
import time
from collections.abc import Iterable, Iterator
from dataclasses import replace
from typing import Any, ClassVar, cast

import pytest

import doll.ollama_adapter as ollama
from doll.ollama_adapter import (
    MAX_OLLAMA_JSON_BYTES,
    MAX_OLLAMA_STREAM_BYTES,
    MAX_OLLAMA_STREAM_LINE_BYTES,
    OLLAMA_ADAPTER_ID,
    OLLAMA_ADAPTER_VERSION,
    OLLAMA_DEFAULT_PORT,
    OLLAMA_LOOPBACK_HOST,
    OLLAMA_RUNTIME_ID,
    LoopbackOllamaTransport,
    OllamaAdapterConfig,
    OllamaEndpoint,
    OllamaHttpResponse,
    OllamaRuntimeAdapter,
    OllamaTransportFailure,
    is_ollama_cloud_model,
    ollama_model_id,
)
from doll.runtime_adapter import (
    MAX_RUNTIME_MODELS,
    LocalRuntimeBoundary,
    RuntimeAdapterContext,
    RuntimeAdapterFailure,
    RuntimeAdapterRegistry,
    RuntimeCancellationToken,
    RuntimeContractError,
    RuntimeGenerationRequest,
)

DIGEST_A = "a" * 64
DIGEST_B = "b" * 64
LOCAL_NAME = "gemma3:4b"
LOCAL_ID = ollama_model_id(LOCAL_NAME)


def encode(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def context(
    *,
    operation_id: str = "operation-1",
    timeout_seconds: float = 30.0,
    cancellation: RuntimeCancellationToken | None = None,
) -> RuntimeAdapterContext:
    return RuntimeAdapterContext(
        operation_id,
        time.monotonic() + timeout_seconds,
        cancellation or RuntimeCancellationToken(),
    )


def request(
    *,
    model_id: str = LOCAL_ID,
    text: str = "local prompt",
    max_output_chars: int = 1024,
    cancellation: RuntimeCancellationToken | None = None,
) -> RuntimeGenerationRequest:
    return RuntimeGenerationRequest(
        operation_id="operation-1",
        model_id=model_id,
        input_text=text,
        max_output_chars=max_output_chars,
        timeout_seconds=30.0,
        cancellation=cancellation or RuntimeCancellationToken(),
    )


def tags_payload(*models: object) -> bytes:
    return encode({"models": list(models)})


def local_model(
    name: str = LOCAL_NAME,
    *,
    digest: object = f"sha256:{DIGEST_A}",
) -> dict[str, object]:
    return {
        "name": name,
        "model": name,
        "modified_at": "2026-06-26T00:00:00Z",
        "size": 1,
        "digest": digest,
        "details": {"format": "gguf"},
    }


class FakeTransport:
    def __init__(self, endpoint: OllamaEndpoint | None = None) -> None:
        self.endpoint = endpoint or OllamaEndpoint()
        self.responses: list[object] = []
        self.streams: list[object] = []
        self.requests: list[tuple[str, str, bytes | None, int]] = []
        self.stream_requests: list[tuple[str, bytes, int, int]] = []

    def request_json(
        self,
        method: str,
        path: str,
        *,
        body: bytes | None,
        context: RuntimeAdapterContext | None,
        maximum_bytes: int,
    ) -> OllamaHttpResponse:
        del context
        self.requests.append((method, path, body, maximum_bytes))
        if not self.responses:
            raise AssertionError("unexpected request")
        value = self.responses.pop(0)
        if isinstance(value, BaseException):
            raise value
        return cast(OllamaHttpResponse, value)

    def stream_ndjson(
        self,
        path: str,
        *,
        body: bytes,
        context: RuntimeAdapterContext,
        maximum_bytes: int,
        maximum_line_bytes: int,
    ) -> Iterable[bytes]:
        del context
        self.stream_requests.append((path, body, maximum_bytes, maximum_line_bytes))
        if not self.streams:
            raise AssertionError("unexpected stream")
        value = self.streams.pop(0)
        if isinstance(value, BaseException):
            raise value
        return cast(Iterable[bytes], value)


def confirmed_adapter(
    transport: FakeTransport | None = None,
) -> tuple[OllamaRuntimeAdapter, FakeTransport]:
    fake = transport or FakeTransport()
    adapter = OllamaRuntimeAdapter(
        OllamaAdapterConfig(local_only_confirmed=True),
        transport=fake,
    )
    return adapter, fake


def ready_transport(fake: FakeTransport) -> None:
    fake.responses.append(OllamaHttpResponse(200, encode({"version": "0.12.6"})))


def inventory_transport(fake: FakeTransport, *models: object) -> None:
    fake.responses.append(OllamaHttpResponse(200, tags_payload(*models)))


def test_configuration_declaration_and_fail_closed_health() -> None:
    endpoint = OllamaEndpoint()
    assert endpoint.host == OLLAMA_LOOPBACK_HOST
    assert endpoint.port == OLLAMA_DEFAULT_PORT
    assert replace(endpoint).host == OLLAMA_LOOPBACK_HOST

    for invalid in (True, 0, -1, 65536, 1.5, "11434"):
        with pytest.raises(RuntimeContractError, match="loopback port"):
            OllamaEndpoint(cast(int, invalid))

    with pytest.raises(RuntimeContractError, match="endpoint"):
        OllamaAdapterConfig(endpoint=cast(OllamaEndpoint, object()))
    with pytest.raises(RuntimeContractError, match="confirmation"):
        OllamaAdapterConfig(local_only_confirmed=cast(bool, 1))
    with pytest.raises(RuntimeContractError, match="configuration"):
        OllamaRuntimeAdapter(cast(OllamaAdapterConfig, object()))

    adapter = OllamaRuntimeAdapter()
    declaration = adapter.declaration()
    assert declaration.adapter_id == OLLAMA_ADAPTER_ID
    assert declaration.adapter_version == OLLAMA_ADAPTER_VERSION
    assert declaration.runtime_class == "ollama.local"
    assert declaration.connection_kind == "local_socket"
    assert declaration.supported_operations == ("generate", "inventory", "stream")
    assert declaration.offline_capable is True
    assert declaration.cloud_fallback is False
    assert declaration.automatic_download is False

    health = adapter.health()
    assert health.state == "unavailable"
    assert health.runtime_id is None
    assert health.failure_code == "adapter_not_configured"


def test_transport_and_response_contracts_are_bounded() -> None:
    failure = OllamaTransportFailure("failure", status_code=503)
    assert failure.code == "failure"
    assert failure.status_code == 503
    assert "503" not in str(failure)
    for code in ("unknown", "runtime_unavailable"):
        with pytest.raises(ValueError, match="transport failure code"):
            OllamaTransportFailure(code)
    for status in (True, 99, 600, 200.0):
        with pytest.raises(ValueError, match="HTTP status"):
            OllamaTransportFailure("failure", status_code=cast(int, status))

    response = OllamaHttpResponse(200, b"secret-body")
    assert "secret-body" not in repr(response)
    for status in (True, 99, 600, 200.0):
        with pytest.raises(RuntimeContractError, match="response status"):
            OllamaHttpResponse(cast(int, status), b"{}")
    with pytest.raises(RuntimeContractError, match="response body"):
        OllamaHttpResponse(200, cast(bytes, "{}"))

    endpoint = OllamaEndpoint(12000)
    with pytest.raises(RuntimeContractError, match="endpoint mismatch"):
        OllamaRuntimeAdapter(
            OllamaAdapterConfig(endpoint=endpoint, local_only_confirmed=True),
            transport=FakeTransport(OllamaEndpoint(12001)),
        )

    class MissingEndpoint:
        pass

    with pytest.raises(RuntimeContractError, match="transport endpoint"):
        OllamaRuntimeAdapter(
            OllamaAdapterConfig(local_only_confirmed=True),
            transport=cast(Any, MissingEndpoint()),
        )


def test_opaque_model_ids_and_cloud_markers() -> None:
    identifier = ollama_model_id("library/gemma3:4b")
    assert identifier.startswith("ollama.model.")
    assert len(identifier) == len("ollama.model.") + 64
    assert identifier == ollama_model_id("library/gemma3:4b")
    assert identifier != ollama_model_id("library/gemma3:12b")
    assert "gemma3" not in identifier

    for name in (
        "gpt-oss:120b-cloud",
        "model:cloud",
        "namespace/model.cloud",
        "namespace/model_cloud",
        "MODEL:CLOUD",
    ):
        assert is_ollama_cloud_model(name) is True
    for name in ("cloudy:model", "model:cloud-local", "model:local", "cloud/model:7b"):
        assert is_ollama_cloud_model(name) is False

    for invalid in ("", " bad", "bad name", "bad\nname", "x" * 257, 1):
        with pytest.raises(RuntimeAdapterFailure, match="invalid_response"):
            ollama_model_id(cast(str, invalid))


def test_health_normalizes_only_confirmed_local_version() -> None:
    adapter, fake = confirmed_adapter()
    ready_transport(fake)
    health = adapter.health()
    assert health.state == "ready"
    assert health.runtime_id == OLLAMA_RUNTIME_ID
    assert health.failure_code is None
    assert fake.requests == [("GET", "/api/version", None, MAX_OLLAMA_JSON_BYTES)]

    bad_responses: tuple[object, ...] = (
        OllamaHttpResponse(503, b"private provider body"),
        OllamaHttpResponse(200, b"not-json"),
        OllamaHttpResponse(200, encode([])),
        OllamaHttpResponse(200, encode({})),
        OllamaHttpResponse(200, encode({"version": "bad version"})),
        OllamaHttpResponse(200, b'{"version":"1","version":"2"}'),
        OllamaHttpResponse(200, b'{"version":NaN}'),
        OllamaTransportFailure("failure"),
        object(),
    )
    for value in bad_responses:
        adapter, fake = confirmed_adapter()
        fake.responses.append(value)
        health = adapter.health()
        assert health.state == "unavailable"
        assert health.runtime_id is None
        assert health.failure_code == "runtime_unavailable"
        assert "private provider body" not in repr(health)


def test_inventory_filters_cloud_models_and_normalizes_identity() -> None:
    adapter, fake = confirmed_adapter()
    inventory_transport(
        fake,
        local_model("zeta:7b", digest=f"sha256:{DIGEST_B}"),
        local_model("gpt-oss:120b-cloud"),
        local_model("alpha:3b", digest=DIGEST_A.upper()),
        {"model": "beta:1b", "digest": None},
    )
    snapshot = adapter.inventory(context())
    assert snapshot.runtime_id == OLLAMA_RUNTIME_ID
    assert tuple(model.model_id for model in snapshot.models) == tuple(
        sorted(
            (
                ollama_model_id("zeta:7b"),
                ollama_model_id("alpha:3b"),
                ollama_model_id("beta:1b"),
            )
        )
    )
    by_name = {model.display_name: model for model in snapshot.models}
    assert "gpt-oss:120b-cloud" not in by_name
    assert by_name["zeta:7b"].revision == f"sha256-{DIGEST_B}"
    assert by_name["alpha:3b"].revision == f"sha256-{DIGEST_A}"
    assert by_name["beta:1b"].revision is None
    assert all(model.features == ("text",) for model in snapshot.models)
    assert all(model.available is True for model in snapshot.models)

    adapter, fake = confirmed_adapter()
    inventory_transport(fake, local_model("only:cloud"))
    assert adapter.inventory(context()).models == ()


def test_inventory_rejects_malformed_or_oversized_responses() -> None:
    malformed: tuple[tuple[bytes, str], ...] = (
        (encode({}), "invalid_response"),
        (encode({"models": {}}), "invalid_response"),
        (encode({"models": [1]}), "invalid_response"),
        (tags_payload({}), "invalid_response"),
        (
            tags_payload({"name": "a:1", "model": "b:1", "digest": None}),
            "invalid_response",
        ),
        (tags_payload(local_model("bad name")), "invalid_response"),
        (tags_payload(local_model(digest=1)), "invalid_response"),
        (tags_payload(local_model(digest="sha256:short")), "invalid_response"),
        (tags_payload(local_model(), local_model()), "invalid_response"),
        (b'{"models":[],"models":[]}', "invalid_response"),
        (b'{"models":NaN}', "invalid_response"),
    )
    for body, code in malformed:
        adapter, fake = confirmed_adapter()
        fake.responses.append(OllamaHttpResponse(200, body))
        with pytest.raises(RuntimeAdapterFailure) as exc:
            adapter.inventory(context())
        assert exc.value.code == code

    adapter, fake = confirmed_adapter()
    too_many = tuple(
        {"name": f"model-{index}:1b", "model": f"model-{index}:1b", "digest": None}
        for index in range(MAX_RUNTIME_MODELS + 1)
    )
    inventory_transport(fake, *too_many)
    with pytest.raises(RuntimeAdapterFailure) as exc:
        adapter.inventory(context())
    assert exc.value.code == "resource_limit"

    adapter, fake = confirmed_adapter()
    fake.responses.append(OllamaHttpResponse(500, b"secret provider detail"))
    with pytest.raises(RuntimeAdapterFailure) as exc:
        adapter.inventory(context())
    assert exc.value.code == "runtime_unavailable"
    assert "secret provider detail" not in str(exc.value)

    for failure, expected in (
        (OllamaTransportFailure("cancelled"), "cancelled"),
        (OllamaTransportFailure("timeout"), "timeout"),
        (OllamaTransportFailure("resource_limit"), "resource_limit"),
        (OllamaTransportFailure("invalid_response"), "invalid_response"),
        (OllamaTransportFailure("failure"), "adapter_failure"),
    ):
        adapter, fake = confirmed_adapter()
        fake.responses.append(failure)
        with pytest.raises(RuntimeAdapterFailure) as exc:
            adapter.inventory(context())
        assert exc.value.code == expected


def test_generation_resolves_current_local_inventory_and_maps_response() -> None:
    adapter, fake = confirmed_adapter()
    inventory_transport(fake, local_model())
    fake.responses.append(
        OllamaHttpResponse(
            200,
            encode(
                {
                    "model": LOCAL_NAME,
                    "response": "local answer",
                    "done": True,
                    "done_reason": "length",
                }
            ),
        )
    )
    result = adapter.generate(request(), context())
    assert result.runtime_id == OLLAMA_RUNTIME_ID
    assert result.model_id == LOCAL_ID
    assert result.output_text == "local answer"
    assert result.finish_reason == "length"
    assert "local answer" not in repr(result)

    assert fake.requests[0][:2] == ("GET", "/api/tags")
    method, path, body, maximum = fake.requests[1]
    assert method == "POST"
    assert path == "/api/generate"
    assert maximum == MAX_OLLAMA_JSON_BYTES
    assert json.loads(cast(bytes, body)) == {
        "model": LOCAL_NAME,
        "prompt": "local prompt",
        "stream": False,
    }


def test_generation_rejects_cloud_missing_http_and_malformed_results() -> None:
    adapter, fake = confirmed_adapter()
    inventory_transport(fake, local_model("gpt-oss:120b-cloud"))
    with pytest.raises(RuntimeAdapterFailure) as exc:
        adapter.generate(request(model_id=ollama_model_id("gpt-oss:120b-cloud")), context())
    assert exc.value.code == "model_not_found"
    assert len(fake.requests) == 1

    adapter, fake = confirmed_adapter()
    inventory_transport(fake, local_model())
    fake.responses.append(OllamaHttpResponse(404, b"private missing detail"))
    with pytest.raises(RuntimeAdapterFailure) as exc:
        adapter.generate(request(), context())
    assert exc.value.code == "model_not_found"
    assert "private missing detail" not in str(exc.value)

    adapter, fake = confirmed_adapter()
    inventory_transport(fake, local_model())
    fake.responses.append(OllamaHttpResponse(503, b"private overload detail"))
    with pytest.raises(RuntimeAdapterFailure) as exc:
        adapter.generate(request(), context())
    assert exc.value.code == "adapter_failure"

    invalid_documents: tuple[tuple[object, str], ...] = (
        ([], "invalid_response"),
        ({"model": "other:1b", "response": "x", "done": True}, "invalid_response"),
        ({"model": LOCAL_NAME, "response": "x", "done": False}, "invalid_response"),
        ({"model": LOCAL_NAME, "response": 1, "done": True}, "invalid_response"),
        (
            {
                "model": LOCAL_NAME,
                "response": "x",
                "done": True,
                "done_reason": "unknown",
            },
            "invalid_response",
        ),
    )
    for document, expected in invalid_documents:
        adapter, fake = confirmed_adapter()
        inventory_transport(fake, local_model())
        fake.responses.append(OllamaHttpResponse(200, encode(document)))
        with pytest.raises(RuntimeAdapterFailure) as exc:
            adapter.generate(request(), context())
        assert exc.value.code == expected

    adapter, fake = confirmed_adapter()
    inventory_transport(fake, local_model())
    fake.responses.append(
        OllamaHttpResponse(
            200,
            encode({"model": LOCAL_NAME, "response": "toolong", "done": True}),
        )
    )
    with pytest.raises(RuntimeAdapterFailure) as exc:
        adapter.generate(request(max_output_chars=3), context())
    assert exc.value.code == "resource_limit"


def test_generation_honors_fail_closed_cancellation_and_timeout() -> None:
    adapter = OllamaRuntimeAdapter()
    with pytest.raises(RuntimeAdapterFailure) as exc:
        adapter.generate(request(), context())
    assert exc.value.code == "adapter_not_configured"

    adapter, fake = confirmed_adapter()
    token = RuntimeCancellationToken()
    token.cancel()
    with pytest.raises(RuntimeAdapterFailure) as exc:
        adapter.generate(request(cancellation=token), context(cancellation=token))
    assert exc.value.code == "cancelled"
    assert fake.requests == []

    adapter, fake = confirmed_adapter()
    expired = RuntimeAdapterContext("operation-1", time.monotonic() - 1, RuntimeCancellationToken())
    with pytest.raises(RuntimeAdapterFailure) as exc:
        adapter.generate(request(), expired)
    assert exc.value.code == "timeout"
    assert fake.requests == []

    adapter, _ = confirmed_adapter()
    with pytest.raises(RuntimeContractError, match="validated request"):
        adapter.generate(cast(RuntimeGenerationRequest, object()), context())
    with pytest.raises(RuntimeContractError, match="validated context"):
        adapter.generate(request(), cast(RuntimeAdapterContext, object()))


def test_stream_maps_ndjson_to_ordered_contract_events() -> None:
    adapter, fake = confirmed_adapter()
    inventory_transport(fake, local_model())
    fake.streams.append(
        (
            encode({"model": LOCAL_NAME, "response": "hello ", "done": False}) + b"\n",
            encode({"model": LOCAL_NAME, "response": "world", "done": False}) + b"\n",
            encode(
                {
                    "model": LOCAL_NAME,
                    "response": "",
                    "done": True,
                    "done_reason": "stop",
                }
            )
            + b"\n",
        )
    )
    events = tuple(adapter.stream(request(), context()))
    assert [(event.sequence, event.kind) for event in events] == [
        (0, "start"),
        (1, "delta"),
        (2, "delta"),
        (3, "complete"),
    ]
    assert "".join(event.text or "" for event in events) == "hello world"
    assert events[-1].finish_reason == "stop"
    assert all("hello" not in repr(event) for event in events)

    path, body, maximum, line_maximum = fake.stream_requests[0]
    assert path == "/api/generate"
    assert maximum == MAX_OLLAMA_STREAM_BYTES
    assert line_maximum == MAX_OLLAMA_STREAM_LINE_BYTES
    assert json.loads(body) == {
        "model": LOCAL_NAME,
        "prompt": "local prompt",
        "stream": True,
    }


def test_stream_rejects_provider_error_malformed_transcripts_and_limits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cases: tuple[tuple[object, str], ...] = (
        ((encode({"error": "private detail"}) + b"\n",), "adapter_failure"),
        (
            (encode({"model": "other:1b", "response": "x", "done": False}) + b"\n",),
            "invalid_response",
        ),
        (
            (encode({"model": LOCAL_NAME, "response": 1, "done": False}) + b"\n",),
            "invalid_response",
        ),
        ((encode({"model": LOCAL_NAME, "response": "x"}) + b"\n",), "invalid_response"),
        (
            (
                encode(
                    {
                        "model": LOCAL_NAME,
                        "response": "",
                        "done": True,
                        "done_reason": "bad",
                    }
                )
                + b"\n",
            ),
            "invalid_response",
        ),
        (
            (encode({"model": LOCAL_NAME, "response": "x", "done": False}) + b"\n",),
            "invalid_response",
        ),
        ((b"\n",), "invalid_response"),
        ((b"not-json\n",), "invalid_response"),
        (
            (b'{"model":"gemma3:4b","response":"x","response":"y","done":false}\n',),
            "invalid_response",
        ),
        ((cast(bytes, "not-bytes"),), "invalid_response"),
        (b"not-an-iterable", "invalid_response"),
        (object(), "invalid_response"),
    )
    for stream_value, expected in cases:
        adapter, fake = confirmed_adapter()
        inventory_transport(fake, local_model())
        fake.streams.append(stream_value)
        iterator = adapter.stream(request(), context())
        with pytest.raises(RuntimeAdapterFailure) as exc:
            tuple(iterator)
        assert exc.value.code == expected
        assert "private detail" not in str(exc.value)

    adapter, fake = confirmed_adapter()
    inventory_transport(fake, local_model())
    fake.streams.append(
        (
            encode({"model": LOCAL_NAME, "response": "abcd", "done": False}) + b"\n",
            encode({"model": LOCAL_NAME, "response": "", "done": True}) + b"\n",
        )
    )
    with pytest.raises(RuntimeAdapterFailure) as exc:
        tuple(adapter.stream(request(max_output_chars=3), context()))
    assert exc.value.code == "resource_limit"

    adapter, fake = confirmed_adapter()
    inventory_transport(fake, local_model())
    monkeypatch.setattr(ollama, "MAX_RUNTIME_STREAM_EVENTS", 2)
    fake.streams.append(
        (
            encode({"model": LOCAL_NAME, "response": "a", "done": False}) + b"\n",
            encode({"model": LOCAL_NAME, "response": "b", "done": False}) + b"\n",
        )
    )
    with pytest.raises(RuntimeAdapterFailure) as exc:
        tuple(adapter.stream(request(), context()))
    assert exc.value.code == "resource_limit"


def test_stream_detects_extra_data_and_maps_transport_failures() -> None:
    adapter, fake = confirmed_adapter()
    inventory_transport(fake, local_model())
    fake.streams.append(
        (
            encode({"model": LOCAL_NAME, "response": "", "done": True}) + b"\n",
            encode({"model": LOCAL_NAME, "response": "extra", "done": False}) + b"\n",
        )
    )
    with pytest.raises(RuntimeAdapterFailure) as exc:
        tuple(adapter.stream(request(), context()))
    assert exc.value.code == "invalid_response"

    for failure, expected in (
        (OllamaTransportFailure("cancelled"), "cancelled"),
        (OllamaTransportFailure("timeout"), "timeout"),
        (OllamaTransportFailure("resource_limit"), "resource_limit"),
        (OllamaTransportFailure("invalid_response"), "invalid_response"),
        (OllamaTransportFailure("failure"), "adapter_failure"),
    ):
        adapter, fake = confirmed_adapter()
        inventory_transport(fake, local_model())
        fake.streams.append(failure)
        with pytest.raises(RuntimeAdapterFailure) as exc:
            tuple(adapter.stream(request(), context()))
        assert exc.value.code == expected


def test_stream_observes_cooperative_cancellation_between_lines() -> None:
    token = RuntimeCancellationToken()

    def cancelling_lines() -> Iterator[bytes]:
        yield encode({"model": LOCAL_NAME, "response": "first", "done": False}) + b"\n"
        token.cancel()
        yield encode({"model": LOCAL_NAME, "response": "second", "done": False}) + b"\n"

    adapter, fake = confirmed_adapter()
    inventory_transport(fake, local_model())
    fake.streams.append(cancelling_lines())
    with pytest.raises(RuntimeAdapterFailure) as exc:
        tuple(adapter.stream(request(cancellation=token), context(cancellation=token)))
    assert exc.value.code == "cancelled"


def test_adapter_works_through_runtime_boundary_without_state_authority() -> None:
    adapter, fake = confirmed_adapter()
    ready_transport(fake)
    ready_transport(fake)
    inventory_transport(fake, local_model())
    ready_transport(fake)
    inventory_transport(fake, local_model())
    fake.responses.append(
        OllamaHttpResponse(
            200,
            encode({"model": LOCAL_NAME, "response": "bounded", "done": True}),
        )
    )
    boundary = LocalRuntimeBoundary(RuntimeAdapterRegistry((adapter,)))

    health = boundary.health(OLLAMA_ADAPTER_ID)
    assert health.state == "ready"
    inventory = boundary.inventory(OLLAMA_ADAPTER_ID, operation_id="inventory-1")
    assert inventory.succeeded is True
    assert inventory.models[0].model_id == LOCAL_ID
    generation = boundary.generate(OLLAMA_ADAPTER_ID, request())
    assert generation.outcome == "completed"
    assert generation.output_text == "bounded"


class FakeHttpResponse:
    def __init__(
        self,
        status: int,
        body: bytes = b"",
        *,
        lines: Iterable[bytes] = (),
        read_error: BaseException | None = None,
    ) -> None:
        self.status = status
        self._body = body
        self._lines = iter(lines)
        self._read_error = read_error

    def read(self, amount: int) -> bytes:
        if self._read_error is not None:
            raise self._read_error
        return self._body[:amount]

    def readline(self, amount: int) -> bytes:
        try:
            return next(self._lines)[:amount]
        except StopIteration:
            return b""


class FakeConnection:
    instances: ClassVar[list[FakeConnection]] = []
    response: object = FakeHttpResponse(200, b"{}")
    request_error: BaseException | None = None

    def __init__(self, host: str, port: int, *, timeout: float) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.request_args: tuple[str, str, bytes | None, dict[str, str]] | None = None
        self.closed = False
        type(self).instances.append(self)

    def request(
        self,
        method: str,
        path: str,
        *,
        body: bytes | None,
        headers: dict[str, str],
    ) -> None:
        self.request_args = (method, path, body, headers)
        error = type(self).request_error
        if error is not None:
            raise error

    def getresponse(self) -> FakeHttpResponse:
        value = type(self).response
        if isinstance(value, BaseException):
            raise value
        return cast(FakeHttpResponse, value)

    def close(self) -> None:
        self.closed = True


def install_fake_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeConnection.instances = []
    FakeConnection.response = FakeHttpResponse(200, b"{}")
    FakeConnection.request_error = None
    monkeypatch.setattr(http_client, "HTTPConnection", FakeConnection)


def test_loopback_transport_uses_fixed_direct_endpoint_and_safe_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_fake_connection(monkeypatch)
    FakeConnection.response = FakeHttpResponse(200, b'{"version":"0.12.6"}')
    transport = LoopbackOllamaTransport(OllamaEndpoint(12000))
    response = transport.request_json(
        "GET",
        "/api/version",
        body=None,
        context=None,
        maximum_bytes=1024,
    )
    assert response.status_code == 200
    connection = FakeConnection.instances[0]
    assert connection.host == OLLAMA_LOOPBACK_HOST
    assert connection.port == 12000
    assert connection.timeout == 2.0
    assert connection.closed is True
    assert connection.request_args is not None
    method, path, body, headers = connection.request_args
    assert (method, path, body) == ("GET", "/api/version", None)
    assert "Authorization" not in headers
    assert headers["Connection"] == "close"
    assert "Content-Type" not in headers

    FakeConnection.response = FakeHttpResponse(200, b"{}")
    transport.request_json(
        "POST",
        "/api/generate",
        body=b"{}",
        context=context(),
        maximum_bytes=1024,
    )
    headers = cast(
        tuple[str, str, bytes | None, dict[str, str]],
        FakeConnection.instances[-1].request_args,
    )[3]
    assert headers["Content-Type"] == "application/json"
    assert "Authorization" not in headers


def test_loopback_transport_validates_paths_sizes_failures_and_closure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_fake_connection(monkeypatch)
    transport = LoopbackOllamaTransport()
    invalid_calls: tuple[dict[str, object], ...] = (
        {"method": "DELETE"},
        {"path": "/api/pull"},
        {"method": "GET", "body": b"{}"},
        {"method": "POST", "body": None},
        {"maximum_bytes": 0},
        {"maximum_bytes": True},
        {"maximum_bytes": MAX_OLLAMA_JSON_BYTES + 1},
    )
    base: dict[str, object] = {
        "method": "GET",
        "path": "/api/version",
        "body": None,
        "context": None,
        "maximum_bytes": 1024,
    }
    for change in invalid_calls:
        with pytest.raises(RuntimeContractError):
            transport.request_json(**(base | change))  # type: ignore[arg-type]

    with pytest.raises(RuntimeContractError, match="request body"):
        transport.request_json(
            "POST",
            "/api/generate",
            body=b"x" * (MAX_OLLAMA_JSON_BYTES + 1),
            context=context(),
            maximum_bytes=1024,
        )

    FakeConnection.response = FakeHttpResponse(200, b"abcd")
    with pytest.raises(OllamaTransportFailure) as exc:
        transport.request_json(
            "GET",
            "/api/version",
            body=None,
            context=None,
            maximum_bytes=3,
        )
    assert exc.value.code == "resource_limit"
    assert FakeConnection.instances[-1].closed is True

    for error, expected in (
        (TimeoutError("private"), "timeout"),
        (OSError("private path"), "failure"),
        (http_client.HTTPException("private"), "failure"),
    ):
        FakeConnection.request_error = error
        with pytest.raises(OllamaTransportFailure) as exc:
            transport.request_json(
                "GET",
                "/api/version",
                body=None,
                context=None,
                maximum_bytes=1024,
            )
        assert exc.value.code == expected
        assert "private" not in str(exc.value)
        assert FakeConnection.instances[-1].closed is True
        FakeConnection.request_error = None


def test_loopback_streaming_transport_bounds_status_lines_and_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_fake_connection(monkeypatch)
    transport = LoopbackOllamaTransport()

    FakeConnection.response = FakeHttpResponse(503, lines=(b"private\n",))
    with pytest.raises(OllamaTransportFailure) as exc:
        tuple(
            transport.stream_ndjson(
                "/api/generate",
                body=b"{}",
                context=context(),
                maximum_bytes=1024,
                maximum_line_bytes=128,
            )
        )
    assert exc.value.code == "failure"
    assert exc.value.status_code == 503
    assert "private" not in str(exc.value)

    FakeConnection.response = FakeHttpResponse(200, lines=(b"abc\n", b"def\n"))
    assert tuple(
        transport.stream_ndjson(
            "/api/generate",
            body=b"{}",
            context=context(),
            maximum_bytes=1024,
            maximum_line_bytes=128,
        )
    ) == (b"abc\n", b"def\n")
    assert FakeConnection.instances[-1].closed is True

    for maximum, line_maximum in (
        (0, 10),
        (MAX_OLLAMA_STREAM_BYTES + 1, 10),
        (10, 0),
        (10, MAX_OLLAMA_STREAM_LINE_BYTES + 1),
    ):
        with pytest.raises(RuntimeContractError):
            transport.stream_ndjson(
                "/api/generate",
                body=b"{}",
                context=context(),
                maximum_bytes=maximum,
                maximum_line_bytes=line_maximum,
            )

    FakeConnection.response = FakeHttpResponse(200, lines=(b"abcd",))
    with pytest.raises(OllamaTransportFailure) as exc:
        tuple(
            transport.stream_ndjson(
                "/api/generate",
                body=b"{}",
                context=context(),
                maximum_bytes=1024,
                maximum_line_bytes=3,
            )
        )
    assert exc.value.code == "resource_limit"

    FakeConnection.response = FakeHttpResponse(200, lines=(b"abc", b"def"))
    with pytest.raises(OllamaTransportFailure) as exc:
        tuple(
            transport.stream_ndjson(
                "/api/generate",
                body=b"{}",
                context=context(),
                maximum_bytes=5,
                maximum_line_bytes=3,
            )
        )
    assert exc.value.code == "resource_limit"

    token = RuntimeCancellationToken()
    token.cancel()
    with pytest.raises(OllamaTransportFailure) as exc:
        tuple(
            transport.stream_ndjson(
                "/api/generate",
                body=b"{}",
                context=context(cancellation=token),
                maximum_bytes=1024,
                maximum_line_bytes=128,
            )
        )
    assert exc.value.code == "cancelled"
    assert len(FakeConnection.instances) >= 1
