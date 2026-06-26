from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from typing import Any, cast

import pytest

from doll.runtime_adapter import (
    DEFAULT_RUNTIME_TIMEOUT_SECONDS,
    MAX_RUNTIME_CONTEXT_WINDOW,
    MAX_RUNTIME_FEATURES,
    MAX_RUNTIME_INPUT_CHARS,
    MAX_RUNTIME_MODELS,
    MAX_RUNTIME_OUTPUT_CHARS,
    MAX_RUNTIME_STREAM_EVENTS,
    MAX_RUNTIME_TIMEOUT_SECONDS,
    LocalRuntimeBoundary,
    RuntimeAdapterContext,
    RuntimeAdapterDeclaration,
    RuntimeAdapterFailure,
    RuntimeAdapterRegistry,
    RuntimeAdapterResponse,
    RuntimeCancellationToken,
    RuntimeConnectionKind,
    RuntimeContractError,
    RuntimeFailureCode,
    RuntimeFinishReason,
    RuntimeGenerationOutcome,
    RuntimeGenerationRequest,
    RuntimeGenerationResult,
    RuntimeHealth,
    RuntimeHealthState,
    RuntimeInventoryResult,
    RuntimeInventorySnapshot,
    RuntimeModelInfo,
    RuntimeOperation,
    RuntimeStreamEvent,
    RuntimeStreamEventKind,
    RuntimeStreamResult,
)


class MutableClock:
    def __init__(self, value: float = 10.0) -> None:
        self.value = value
        self.fail = False

    def __call__(self) -> float:
        if self.fail:
            raise RuntimeError("private clock detail")
        return self.value


class SyntheticAdapter:
    adapter_id = "test.runtime"

    def __init__(self) -> None:
        self.declaration_value: object = RuntimeAdapterDeclaration(
            adapter_id=self.adapter_id,
            adapter_version="1.0.0",
            runtime_class="test.local",
            connection_kind="in_process",
            supported_operations=("generate", "inventory", "stream"),
        )
        self.health_value: object = RuntimeHealth(
            self.adapter_id,
            "runtime.synthetic",
            "ready",
        )
        self.inventory_value: object = RuntimeInventorySnapshot(
            "runtime.synthetic",
            (
                RuntimeModelInfo(
                    "model.a",
                    "Synthetic A",
                    revision="r1",
                    context_window=4096,
                    features=("chat", "text"),
                ),
                RuntimeModelInfo("model.b", "Synthetic B", available=False),
            ),
        )
        self.generate_value: object = RuntimeAdapterResponse(
            "runtime.synthetic",
            "model.a",
            "synthetic output",
        )
        self.stream_value: object = (
            RuntimeStreamEvent("operation-1", 0, "start"),
            RuntimeStreamEvent("operation-1", 1, "delta", text="synthetic "),
            RuntimeStreamEvent("operation-1", 2, "delta", text="stream"),
            RuntimeStreamEvent("operation-1", 3, "complete", finish_reason="stop"),
        )
        self.raise_declaration: BaseException | None = None
        self.raise_health: BaseException | None = None
        self.raise_inventory: BaseException | None = None
        self.raise_generate: BaseException | None = None
        self.raise_stream: BaseException | None = None

    def declaration(self) -> RuntimeAdapterDeclaration:
        if self.raise_declaration is not None:
            raise self.raise_declaration
        return cast(RuntimeAdapterDeclaration, self.declaration_value)

    def health(self) -> RuntimeHealth:
        if self.raise_health is not None:
            raise self.raise_health
        return cast(RuntimeHealth, self.health_value)

    def inventory(self, context: RuntimeAdapterContext) -> RuntimeInventorySnapshot:
        del context
        if self.raise_inventory is not None:
            raise self.raise_inventory
        return cast(RuntimeInventorySnapshot, self.inventory_value)

    def generate(
        self,
        request: RuntimeGenerationRequest,
        context: RuntimeAdapterContext,
    ) -> RuntimeAdapterResponse:
        del request, context
        if self.raise_generate is not None:
            raise self.raise_generate
        return cast(RuntimeAdapterResponse, self.generate_value)

    def stream(
        self,
        request: RuntimeGenerationRequest,
        context: RuntimeAdapterContext,
    ) -> Iterable[RuntimeStreamEvent]:
        del request, context
        if self.raise_stream is not None:
            raise self.raise_stream
        return cast(Iterable[RuntimeStreamEvent], self.stream_value)


def request(
    *,
    operation_id: str = "operation-1",
    model_id: str = "model.a",
    text: str = "synthetic input",
    max_output_chars: int = MAX_RUNTIME_OUTPUT_CHARS,
    timeout_seconds: float = DEFAULT_RUNTIME_TIMEOUT_SECONDS,
    cancellation: RuntimeCancellationToken | None = None,
) -> RuntimeGenerationRequest:
    return RuntimeGenerationRequest(
        operation_id=operation_id,
        model_id=model_id,
        input_text=text,
        max_output_chars=max_output_chars,
        timeout_seconds=timeout_seconds,
        cancellation=cancellation or RuntimeCancellationToken(),
    )


def boundary(
    adapter: SyntheticAdapter | None = None,
    *,
    clock: MutableClock | None = None,
) -> LocalRuntimeBoundary:
    registry = RuntimeAdapterRegistry(() if adapter is None else (adapter,))
    return LocalRuntimeBoundary(registry, clock=clock or MutableClock())


def test_declaration_is_deterministic_local_only_and_closed() -> None:
    declaration = RuntimeAdapterDeclaration(
        "test.adapter",
        "1.2.3",
        "runtime.local",
        "local_socket",
        ("generate", "inventory", "stream"),
    )
    assert declaration.canonical_payload() == {
        "adapter_id": "test.adapter",
        "adapter_version": "1.2.3",
        "runtime_class": "runtime.local",
        "connection_kind": "local_socket",
        "supported_operations": ["generate", "inventory", "stream"],
        "offline_capable": True,
        "cloud_fallback": False,
        "automatic_download": False,
    }
    assert declaration.fingerprint.startswith("sha256:")
    assert declaration.fingerprint == replace(declaration).fingerprint

    invalid: tuple[dict[str, object], ...] = (
        {"adapter_id": "Bad Adapter"},
        {"adapter_version": "bad version"},
        {"runtime_class": "Bad Runtime"},
        {"connection_kind": "remote"},
        {"supported_operations": []},
        {"supported_operations": ()},
        {"supported_operations": ("unknown",)},
        {"supported_operations": ("inventory", "inventory")},
        {"supported_operations": ("stream", "generate")},
        {"offline_capable": False},
        {"offline_capable": 1},
        {"cloud_fallback": True},
        {"cloud_fallback": 0},
        {"automatic_download": True},
        {"automatic_download": "false"},
    )
    base: dict[str, object] = {
        "adapter_id": "test.adapter",
        "adapter_version": "1.0",
        "runtime_class": "runtime.local",
        "connection_kind": "local_process",
        "supported_operations": ("generate",),
    }
    for change in invalid:
        with pytest.raises(RuntimeContractError):
            RuntimeAdapterDeclaration(**(base | change))  # type: ignore[arg-type]


def test_cancellation_request_context_and_adapter_failure_are_bounded() -> None:
    token = RuntimeCancellationToken()
    generation = request(cancellation=token)
    assert "synthetic input" not in repr(generation)
    assert "cancellation" not in repr(generation)
    assert repr(token) == "<RuntimeCancellationToken active>"
    token.cancel()
    assert token.is_cancelled is True
    assert repr(token) == "<RuntimeCancellationToken cancelled>"

    context = RuntimeAdapterContext("operation-1", 20.0, token)
    assert "cancellation" not in repr(context)
    failure = RuntimeAdapterFailure("model_not_found")
    assert failure.code == "model_not_found"
    assert str(failure) == "runtime adapter failure: model_not_found"
    with pytest.raises(RuntimeContractError, match="failure code"):
        RuntimeAdapterFailure(cast(RuntimeFailureCode, "invented"))

    invalid_requests: tuple[dict[str, Any], ...] = (
        {"operation_id": "bad id"},
        {"model_id": "Bad Model"},
        {"input_text": ""},
        {"input_text": "x" * (MAX_RUNTIME_INPUT_CHARS + 1)},
        {"input_text": 1},
        {"max_output_chars": 0},
        {"max_output_chars": True},
        {"max_output_chars": MAX_RUNTIME_OUTPUT_CHARS + 1},
        {"timeout_seconds": 0},
        {"timeout_seconds": True},
        {"timeout_seconds": float("inf")},
        {"timeout_seconds": MAX_RUNTIME_TIMEOUT_SECONDS + 1},
        {"cancellation": object()},
    )
    for change in invalid_requests:
        with pytest.raises(RuntimeContractError):
            RuntimeGenerationRequest(
                **(
                    {
                        "operation_id": "operation-1",
                        "model_id": "model.a",
                        "input_text": "text",
                    }
                    | change
                )
            )

    invalid_contexts: tuple[tuple[object, object, object], ...] = (
        ("bad id", 1.0, token),
        ("operation-1", True, token),
        ("operation-1", float("nan"), token),
        ("operation-1", 1.0, object()),
    )
    for operation_id, deadline, cancellation in invalid_contexts:
        with pytest.raises(RuntimeContractError):
            RuntimeAdapterContext(
                cast(str, operation_id),
                cast(float, deadline),
                cast(RuntimeCancellationToken, cancellation),
            )


def test_health_model_and_inventory_contracts() -> None:
    model = RuntimeModelInfo(
        "model.a",
        "Model A",
        revision="rev-1",
        context_window=8192,
        features=("chat", "text"),
    )
    assert model.canonical_payload()["features"] == ["chat", "text"]
    assert RuntimeHealth("test.adapter", "runtime.local", "ready").state == "ready"
    assert (
        RuntimeHealth("test.adapter", "runtime.local", "degraded", "adapter_failure").state
        == "degraded"
    )
    assert (
        RuntimeHealth("test.adapter", None, "unavailable", "runtime_unavailable").runtime_id is None
    )

    invalid_health: tuple[tuple[object, object, object, object], ...] = (
        ("Bad Adapter", "runtime.local", "ready", None),
        ("test.adapter", "Bad Runtime", "ready", None),
        ("test.adapter", "runtime.local", "unknown", None),
        ("test.adapter", None, "ready", None),
        ("test.adapter", "runtime.local", "ready", "adapter_failure"),
        ("test.adapter", "runtime.local", "degraded", None),
        ("test.adapter", None, "unavailable", "invented"),
    )
    for adapter_id, runtime_id, state, code in invalid_health:
        with pytest.raises(RuntimeContractError):
            RuntimeHealth(
                cast(str, adapter_id),
                cast(str | None, runtime_id),
                cast(RuntimeHealthState, state),
                cast(RuntimeFailureCode | None, code),
            )

    invalid_models: tuple[dict[str, object], ...] = (
        {"model_id": "Bad Model"},
        {"display_name": ""},
        {"display_name": "x" * 257},
        {"display_name": "bad\nname"},
        {"revision": "bad revision"},
        {"context_window": 0},
        {"context_window": True},
        {"context_window": MAX_RUNTIME_CONTEXT_WINDOW + 1},
        {"features": ["chat"]},
        {"features": ("Bad Feature",)},
        {"features": ("chat", "chat")},
        {"features": ("text", "chat")},
        {"features": tuple(f"feature-{index}" for index in range(MAX_RUNTIME_FEATURES + 1))},
        {"available": 1},
    )
    base: dict[str, object] = {"model_id": "model.a", "display_name": "Model A"}
    for change in invalid_models:
        with pytest.raises(RuntimeContractError):
            RuntimeModelInfo(**(base | change))  # type: ignore[arg-type]

    models = (model, RuntimeModelInfo("model.b", "Model B"))
    snapshot = RuntimeInventorySnapshot("runtime.local", models)
    success = RuntimeInventoryResult("test.adapter", snapshot.runtime_id, True, models)
    failure = RuntimeInventoryResult(
        "test.adapter",
        None,
        False,
        failure_code="adapter_not_configured",
    )
    assert success.succeeded is True
    assert failure.succeeded is False

    invalid_inventory: tuple[dict[str, object], ...] = (
        {"runtime_id": "Bad Runtime"},
        {"models": [model]},
        {"models": (RuntimeModelInfo("model.b", "B"), model)},
        {"models": (model, model)},
        {"models": (object(),)},
        {"models": tuple(RuntimeModelInfo(f"m-{i}", "M") for i in range(MAX_RUNTIME_MODELS + 1))},
    )
    for change in invalid_inventory:
        with pytest.raises(RuntimeContractError):
            RuntimeInventorySnapshot(**({"runtime_id": "runtime.local", "models": ()} | change))  # type: ignore[arg-type]

    invalid_results: tuple[dict[str, object], ...] = (
        {"adapter_id": "Bad Adapter"},
        {"runtime_id": "Bad Runtime"},
        {"succeeded": 1},
        {"models": [model]},
        {"failure_code": "invented"},
        {"succeeded": True, "runtime_id": None},
        {"succeeded": True, "failure_code": "adapter_failure"},
        {"succeeded": False, "models": (model,), "failure_code": "adapter_failure"},
        {"succeeded": False, "failure_code": None},
    )
    result_base: dict[str, object] = {
        "adapter_id": "test.adapter",
        "runtime_id": "runtime.local",
        "succeeded": True,
        "models": (),
        "failure_code": None,
    }
    for change in invalid_results:
        with pytest.raises(RuntimeContractError):
            RuntimeInventoryResult(**(result_base | change))  # type: ignore[arg-type]


def test_response_generation_and_stream_event_invariants() -> None:
    response = RuntimeAdapterResponse("runtime.local", "model.a", "secret-like output")
    assert "secret-like output" not in repr(response)
    completed = RuntimeGenerationResult(
        "operation-1",
        "test.adapter",
        "runtime.local",
        "model.a",
        "completed",
        "output",
        "stop",
    )
    failed = RuntimeGenerationResult(
        "operation-1",
        "test.adapter",
        None,
        "model.a",
        "failed",
        failure_code="adapter_failure",
    )
    assert completed.output_text == "output"
    assert failed.failure_code == "adapter_failure"
    assert "output" not in repr(completed)

    invalid_responses: tuple[dict[str, Any], ...] = (
        {"runtime_id": "Bad Runtime"},
        {"model_id": "Bad Model"},
        {"output_text": 1},
        {"output_text": "x" * (MAX_RUNTIME_OUTPUT_CHARS + 1)},
        {"finish_reason": "unknown"},
    )
    for change in invalid_responses:
        with pytest.raises(RuntimeContractError):
            RuntimeAdapterResponse(
                **(
                    {
                        "runtime_id": "runtime.local",
                        "model_id": "model.a",
                        "output_text": "output",
                    }
                    | change
                )
            )

    invalid_results: tuple[dict[str, object], ...] = (
        {"operation_id": "bad id"},
        {"adapter_id": "Bad Adapter"},
        {"runtime_id": "Bad Runtime"},
        {"model_id": "Bad Model"},
        {"outcome": "unknown"},
        {"output_text": 1},
        {"finish_reason": "unknown"},
        {"failure_code": "unknown"},
        {"outcome": "completed", "runtime_id": None},
        {"outcome": "completed", "output_text": None},
        {"outcome": "completed", "finish_reason": None},
        {"outcome": "completed", "failure_code": "adapter_failure"},
        {"outcome": "failed", "output_text": "partial", "failure_code": "adapter_failure"},
        {"outcome": "failed", "finish_reason": "stop", "failure_code": "adapter_failure"},
        {"outcome": "failed", "failure_code": None},
        {"outcome": "cancelled", "failure_code": "timeout"},
        {"outcome": "timeout", "failure_code": "cancelled"},
    )
    result_base: dict[str, object] = {
        "operation_id": "operation-1",
        "adapter_id": "test.adapter",
        "runtime_id": "runtime.local",
        "model_id": "model.a",
        "outcome": "completed",
        "output_text": "output",
        "finish_reason": "stop",
        "failure_code": None,
    }
    for change in invalid_results:
        with pytest.raises(RuntimeContractError):
            RuntimeGenerationResult(**(result_base | change))  # type: ignore[arg-type]

    events = (
        RuntimeStreamEvent("operation-1", 0, "start"),
        RuntimeStreamEvent("operation-1", 1, "delta", text="hello"),
        RuntimeStreamEvent("operation-1", 2, "complete", finish_reason="stop"),
    )
    transcript = RuntimeStreamResult(
        "operation-1",
        "test.adapter",
        "runtime.local",
        "model.a",
        "completed",
        events,
    )
    assert transcript.output_text == "hello"
    assert "hello" not in repr(events[1])

    invalid_events: tuple[tuple[object, ...], ...] = (
        ("bad id", 0, "start", None, None, None),
        ("operation-1", True, "start", None, None, None),
        ("operation-1", -1, "start", None, None, None),
        ("operation-1", 0, "unknown", None, None, None),
        ("operation-1", 0, "start", "text", None, None),
        ("operation-1", 1, "start", None, None, None),
        ("operation-1", 1, "delta", None, None, None),
        ("operation-1", 1, "delta", "", None, None),
        ("operation-1", 1, "delta", "text", "stop", None),
        ("operation-1", 1, "delta", "text", None, "adapter_failure"),
        ("operation-1", 1, "complete", "text", "stop", None),
        ("operation-1", 1, "complete", None, None, None),
        ("operation-1", 1, "complete", None, "unknown", None),
        ("operation-1", 1, "error", "text", None, "adapter_failure"),
        ("operation-1", 1, "error", None, "stop", "adapter_failure"),
        ("operation-1", 1, "error", None, None, None),
        ("operation-1", 1, "error", None, None, "unknown"),
        ("operation-1", 1, "cancelled", "text", None, "cancelled"),
        ("operation-1", 1, "cancelled", None, "stop", "cancelled"),
        ("operation-1", 1, "cancelled", None, None, "timeout"),
    )
    for operation_id, sequence, kind, text, finish, code in invalid_events:
        with pytest.raises(RuntimeContractError):
            RuntimeStreamEvent(
                cast(str, operation_id),
                cast(int, sequence),
                cast(RuntimeStreamEventKind, kind),
                cast(str | None, text),
                cast(RuntimeFinishReason | None, finish),
                cast(RuntimeFailureCode | None, code),
            )


def test_stream_result_rejects_malformed_transcripts() -> None:
    start = RuntimeStreamEvent("operation-1", 0, "start")
    delta = RuntimeStreamEvent("operation-1", 1, "delta", text="x")
    complete = RuntimeStreamEvent("operation-1", 2, "complete", finish_reason="stop")
    error = RuntimeStreamEvent("operation-1", 2, "error", failure_code="adapter_failure")
    cancelled = RuntimeStreamEvent("operation-1", 2, "cancelled", failure_code="cancelled")

    invalid: tuple[dict[str, object], ...] = (
        {"operation_id": "bad id"},
        {"adapter_id": "Bad Adapter"},
        {"runtime_id": "Bad Runtime"},
        {"model_id": "Bad Model"},
        {"outcome": "unknown"},
        {"events": [start, complete]},
        {"events": ()},
        {"events": (delta, complete)},
        {"events": (start, RuntimeStreamEvent("operation-2", 1, "delta", text="x"), complete)},
        {"events": (start, RuntimeStreamEvent("operation-1", 2, "delta", text="x"), complete)},
        {
            "events": (
                start,
                complete,
                RuntimeStreamEvent("operation-1", 2, "error", failure_code="adapter_failure"),
            )
        },
        {"events": (start, delta, error), "outcome": "completed"},
        {"events": (start, delta, complete), "runtime_id": None},
        {"events": (start, delta, complete), "failure_code": "adapter_failure"},
        {"events": (start, delta, complete), "outcome": "failed", "failure_code": None},
        {"events": (start, delta, error), "outcome": "failed", "failure_code": "timeout"},
        {"events": (start, delta, cancelled), "outcome": "cancelled", "failure_code": "timeout"},
        {"events": (start, delta, error), "outcome": "timeout", "failure_code": "cancelled"},
        {"events": (start, delta, complete), "failure_code": "unknown"},
        {"events": tuple(start for _ in range(MAX_RUNTIME_STREAM_EVENTS + 1))},
    )
    base: dict[str, object] = {
        "operation_id": "operation-1",
        "adapter_id": "test.adapter",
        "runtime_id": "runtime.local",
        "model_id": "model.a",
        "outcome": "completed",
        "events": (start, delta, complete),
        "failure_code": None,
    }
    for change in invalid:
        with pytest.raises(RuntimeContractError):
            RuntimeStreamResult(**(base | change))  # type: ignore[arg-type]

    oversized = (
        start,
        RuntimeStreamEvent("operation-1", 1, "delta", text="x" * MAX_RUNTIME_OUTPUT_CHARS),
        RuntimeStreamEvent("operation-1", 2, "delta", text="x"),
        RuntimeStreamEvent("operation-1", 3, "complete", finish_reason="stop"),
    )
    with pytest.raises(RuntimeContractError, match="output limit"):
        RuntimeStreamResult(
            "operation-1",
            "test.adapter",
            "runtime.local",
            "model.a",
            "completed",
            oversized,
        )


def test_registry_and_boundary_declaration_and_health_are_failure_isolated() -> None:
    adapter = SyntheticAdapter()
    registry = RuntimeAdapterRegistry((adapter,))
    assert registry.adapter_ids == ("test.runtime",)
    assert registry.get("test.runtime") is adapter
    assert "test.runtime" in repr(registry)
    with pytest.raises(RuntimeContractError, match="duplicate"):
        RuntimeAdapterRegistry((adapter, adapter))
    with pytest.raises(RuntimeContractError, match="registration"):
        RuntimeAdapterRegistry((cast(SyntheticAdapter, object()),))
    invalid_id = SyntheticAdapter()
    invalid_id.adapter_id = "Bad Adapter"
    with pytest.raises(RuntimeContractError, match="registration"):
        RuntimeAdapterRegistry((invalid_id,))
    mismatch = SyntheticAdapter()
    mismatch.declaration_value = replace(
        cast(RuntimeAdapterDeclaration, mismatch.declaration_value), adapter_id="other.adapter"
    )
    with pytest.raises(RuntimeContractError, match="registration"):
        RuntimeAdapterRegistry((mismatch,))
    raising = SyntheticAdapter()
    raising.raise_declaration = RuntimeError("private detail")
    with pytest.raises(RuntimeContractError, match="registration"):
        RuntimeAdapterRegistry((raising,))
    with pytest.raises(RuntimeContractError):
        registry.get("Bad Adapter")

    runtime = LocalRuntimeBoundary(registry, clock=MutableClock())
    assert runtime.declaration("test.runtime") == adapter.declaration_value
    assert runtime.health("test.runtime").state == "ready"
    assert runtime.declaration("missing.adapter") is None
    missing = runtime.health("missing.adapter")
    assert missing.state == "unavailable"
    assert missing.failure_code == "adapter_not_configured"

    adapter.raise_declaration = RuntimeError("/Users/private/token")
    assert runtime.declaration("test.runtime") is None
    assert runtime.health("test.runtime").failure_code == "adapter_failure"
    adapter.raise_declaration = None
    adapter.raise_health = RuntimeError("private detail")
    assert runtime.health("test.runtime").failure_code == "adapter_failure"
    adapter.raise_health = None
    adapter.health_value = object()
    assert runtime.health("test.runtime").failure_code == "adapter_failure"
    adapter.health_value = RuntimeHealth("other.adapter", "runtime.synthetic", "ready")
    assert runtime.health("test.runtime").failure_code == "adapter_failure"
    adapter.health_value = RuntimeHealth("test.runtime", "runtime.synthetic", "ready")
    adapter.declaration_value = object()
    assert runtime.declaration("test.runtime") is None
    assert runtime.health("test.runtime").failure_code == "adapter_failure"

    with pytest.raises(RuntimeContractError, match="registry"):
        LocalRuntimeBoundary(cast(RuntimeAdapterRegistry, object()))
    with pytest.raises(RuntimeContractError, match="clock"):
        LocalRuntimeBoundary(clock=cast(object, 1))  # type: ignore[arg-type]


def test_inventory_success_failure_cancellation_timeout_and_validation() -> None:
    adapter = SyntheticAdapter()
    clock = MutableClock()
    runtime = boundary(adapter, clock=clock)
    success = runtime.inventory("test.runtime", operation_id="inventory-1")
    assert success.succeeded is True
    assert success.runtime_id == "runtime.synthetic"
    assert [model.model_id for model in success.models] == ["model.a", "model.b"]

    missing = boundary().inventory("missing.adapter", operation_id="inventory-1")
    assert missing.failure_code == "adapter_not_configured"

    token = RuntimeCancellationToken()
    token.cancel()
    cancelled = runtime.inventory(
        "test.runtime",
        operation_id="inventory-1",
        cancellation=token,
    )
    assert cancelled.failure_code == "cancelled"

    adapter.declaration_value = replace(
        cast(RuntimeAdapterDeclaration, adapter.declaration_value),
        supported_operations=("generate", "stream"),
    )
    assert runtime.inventory("test.runtime", operation_id="inventory-1").failure_code == (
        "unsupported_operation"
    )
    adapter.declaration_value = RuntimeAdapterDeclaration(
        "test.runtime",
        "1.0",
        "test.local",
        "in_process",
        ("generate", "inventory", "stream"),
    )

    adapter.health_value = RuntimeHealth("test.runtime", None, "unavailable", "runtime_unavailable")
    assert runtime.inventory("test.runtime", operation_id="inventory-1").failure_code == (
        "runtime_unavailable"
    )
    adapter.health_value = RuntimeHealth(
        "test.runtime", "runtime.synthetic", "degraded", "adapter_failure"
    )
    assert runtime.inventory("test.runtime", operation_id="inventory-1").succeeded is True
    adapter.health_value = RuntimeHealth("test.runtime", "runtime.synthetic", "ready")

    adapter.raise_inventory = RuntimeAdapterFailure("model_not_found")
    assert runtime.inventory("test.runtime", operation_id="inventory-1").failure_code == (
        "model_not_found"
    )
    adapter.raise_inventory = RuntimeError("private detail")
    assert runtime.inventory("test.runtime", operation_id="inventory-1").failure_code == (
        "adapter_failure"
    )
    adapter.raise_inventory = None
    adapter.inventory_value = object()
    assert runtime.inventory("test.runtime", operation_id="inventory-1").failure_code == (
        "invalid_response"
    )
    adapter.inventory_value = RuntimeInventorySnapshot("other.runtime", ())
    assert runtime.inventory("test.runtime", operation_id="inventory-1").failure_code == (
        "invalid_response"
    )

    adapter.inventory_value = RuntimeInventorySnapshot("runtime.synthetic", ())
    clock.value = 10.0

    class AdvancingAdapter(SyntheticAdapter):
        def inventory(self, context: RuntimeAdapterContext) -> RuntimeInventorySnapshot:
            clock.value = context.deadline_monotonic
            return RuntimeInventorySnapshot("runtime.synthetic", ())

    timed = boundary(AdvancingAdapter(), clock=clock).inventory(
        "test.runtime", operation_id="inventory-1", timeout_seconds=1
    )
    assert timed.failure_code == "timeout"

    with pytest.raises(RuntimeContractError):
        runtime.inventory("test.runtime", operation_id="bad id")
    with pytest.raises(RuntimeContractError):
        runtime.inventory("test.runtime", operation_id="inventory-1", timeout_seconds=0)
    with pytest.raises(RuntimeContractError):
        runtime.inventory(
            "test.runtime",
            operation_id="inventory-1",
            cancellation=cast(RuntimeCancellationToken, object()),
        )


def test_generation_success_and_all_normalized_failures() -> None:
    adapter = SyntheticAdapter()
    clock = MutableClock()
    runtime = boundary(adapter, clock=clock)
    success = runtime.generate("test.runtime", request())
    assert success.outcome == "completed"
    assert success.output_text == "synthetic output"
    assert success.finish_reason == "stop"

    missing = boundary().generate("missing.adapter", request())
    assert missing.outcome == "failed"
    assert missing.failure_code == "adapter_not_configured"

    token = RuntimeCancellationToken()
    token.cancel()
    cancelled = runtime.generate("test.runtime", request(cancellation=token))
    assert cancelled.outcome == "cancelled"
    assert cancelled.failure_code == "cancelled"

    adapter.raise_generate = RuntimeAdapterFailure("model_not_found")
    assert runtime.generate("test.runtime", request()).failure_code == "model_not_found"
    adapter.raise_generate = RuntimeError("/home/private/credential")
    assert runtime.generate("test.runtime", request()).failure_code == "adapter_failure"
    adapter.raise_generate = None

    malformed: tuple[object, ...] = (
        object(),
        RuntimeAdapterResponse("other.runtime", "model.a", "output"),
        RuntimeAdapterResponse("runtime.synthetic", "model.b", "output"),
        RuntimeAdapterResponse("runtime.synthetic", "model.a", "too long"),
    )
    requests = (request(), request(), request(), request(max_output_chars=3))
    for value, generation_request in zip(malformed, requests, strict=True):
        adapter.generate_value = value
        result = runtime.generate("test.runtime", generation_request)
        assert result.failure_code == "invalid_response"

    class CancellingAdapter(SyntheticAdapter):
        def generate(
            self,
            generation_request: RuntimeGenerationRequest,
            context: RuntimeAdapterContext,
        ) -> RuntimeAdapterResponse:
            del context
            generation_request.cancellation.cancel()
            return RuntimeAdapterResponse("runtime.synthetic", "model.a", "output")

    result = boundary(CancellingAdapter()).generate("test.runtime", request())
    assert result.outcome == "cancelled"

    class TimingAdapter(SyntheticAdapter):
        def generate(
            self,
            generation_request: RuntimeGenerationRequest,
            context: RuntimeAdapterContext,
        ) -> RuntimeAdapterResponse:
            del generation_request
            clock.value = context.deadline_monotonic
            return RuntimeAdapterResponse("runtime.synthetic", "model.a", "output")

    clock.value = 10.0
    result = boundary(TimingAdapter(), clock=clock).generate(
        "test.runtime", request(timeout_seconds=1)
    )
    assert result.outcome == "timeout"
    assert result.failure_code == "timeout"

    with pytest.raises(RuntimeContractError, match="validated"):
        runtime.generate("test.runtime", cast(RuntimeGenerationRequest, object()))


def test_stream_success_and_failure_normalization() -> None:
    adapter = SyntheticAdapter()
    runtime = boundary(adapter)
    success = runtime.stream("test.runtime", request())
    assert success.outcome == "completed"
    assert success.output_text == "synthetic stream"
    assert success.events[-1].kind == "complete"

    missing = boundary().stream("missing.adapter", request())
    assert missing.failure_code == "adapter_not_configured"
    assert [event.kind for event in missing.events] == ["start", "error"]

    token = RuntimeCancellationToken()
    token.cancel()
    cancelled = runtime.stream("test.runtime", request(cancellation=token))
    assert cancelled.outcome == "cancelled"
    assert cancelled.events[-1].kind == "cancelled"

    adapter.raise_stream = RuntimeAdapterFailure("model_not_found")
    expected = runtime.stream("test.runtime", request())
    assert expected.failure_code == "model_not_found"
    adapter.raise_stream = RuntimeError("private detail")
    generic = runtime.stream("test.runtime", request())
    assert generic.failure_code == "adapter_failure"
    adapter.raise_stream = None

    invalid_streams: tuple[object, ...] = (
        "not-an-event-stream",
        object(),
        (object(),),
        (
            RuntimeStreamEvent("operation-1", 0, "start"),
            RuntimeStreamEvent("operation-2", 1, "delta", text="x"),
        ),
        (
            RuntimeStreamEvent("operation-1", 0, "start"),
            RuntimeStreamEvent("operation-1", 2, "delta", text="x"),
        ),
        (
            RuntimeStreamEvent("operation-1", 0, "start"),
            RuntimeStreamEvent("operation-1", 1, "complete", finish_reason="stop"),
            RuntimeStreamEvent("operation-1", 2, "delta", text="late"),
        ),
        (
            RuntimeStreamEvent("operation-1", 0, "start"),
            RuntimeStreamEvent("operation-1", 1, "delta", text="x"),
        ),
    )
    for value in invalid_streams:
        adapter.stream_value = value
        result = runtime.stream("test.runtime", request())
        assert result.outcome == "failed"
        assert result.failure_code in {"adapter_failure", "invalid_response"}
        assert result.events[-1].kind == "error"

    adapter.stream_value = (
        RuntimeStreamEvent("operation-1", 0, "start"),
        RuntimeStreamEvent("operation-1", 1, "delta", text="abcd"),
        RuntimeStreamEvent("operation-1", 2, "complete", finish_reason="stop"),
    )
    limited = runtime.stream("test.runtime", request(max_output_chars=3))
    assert limited.failure_code == "resource_limit"

    class CancellingStreamAdapter(SyntheticAdapter):
        def stream(
            self,
            generation_request: RuntimeGenerationRequest,
            context: RuntimeAdapterContext,
        ) -> Iterable[RuntimeStreamEvent]:
            del context
            yield RuntimeStreamEvent(generation_request.operation_id, 0, "start")
            generation_request.cancellation.cancel()
            yield RuntimeStreamEvent(generation_request.operation_id, 1, "delta", text="hidden")

    cancelled_during = boundary(CancellingStreamAdapter()).stream("test.runtime", request())
    assert cancelled_during.outcome == "cancelled"
    assert cancelled_during.output_text == ""

    clock = MutableClock()

    class TimingStreamAdapter(SyntheticAdapter):
        def stream(
            self,
            generation_request: RuntimeGenerationRequest,
            context: RuntimeAdapterContext,
        ) -> Iterable[RuntimeStreamEvent]:
            yield RuntimeStreamEvent(generation_request.operation_id, 0, "start")
            clock.value = context.deadline_monotonic
            yield RuntimeStreamEvent(generation_request.operation_id, 1, "delta", text="hidden")

    timed = boundary(TimingStreamAdapter(), clock=clock).stream(
        "test.runtime", request(timeout_seconds=1)
    )
    assert timed.outcome == "timeout"
    assert timed.output_text == ""

    with pytest.raises(RuntimeContractError, match="validated"):
        runtime.stream("test.runtime", cast(RuntimeGenerationRequest, object()))


def test_stream_event_limit_and_adapter_exception_after_prefix() -> None:
    class TooManyEventsAdapter(SyntheticAdapter):
        def stream(
            self,
            request_value: RuntimeGenerationRequest,
            context: RuntimeAdapterContext,
        ) -> Iterable[RuntimeStreamEvent]:
            del context
            yield RuntimeStreamEvent(request_value.operation_id, 0, "start")
            for sequence in range(1, MAX_RUNTIME_STREAM_EVENTS + 1):
                yield RuntimeStreamEvent(request_value.operation_id, sequence, "delta", text="x")

    result = boundary(TooManyEventsAdapter()).stream("test.runtime", request())
    assert result.failure_code == "resource_limit"
    assert len(result.events) == MAX_RUNTIME_STREAM_EVENTS
    assert result.events[-1].kind == "error"

    class PartialFailureAdapter(SyntheticAdapter):
        def stream(
            self,
            request_value: RuntimeGenerationRequest,
            context: RuntimeAdapterContext,
        ) -> Iterable[RuntimeStreamEvent]:
            del context
            yield RuntimeStreamEvent(request_value.operation_id, 0, "start")
            yield RuntimeStreamEvent(request_value.operation_id, 1, "delta", text="partial")
            raise RuntimeAdapterFailure("adapter_failure")

    partial = boundary(PartialFailureAdapter()).stream("test.runtime", request())
    assert partial.output_text == "partial"
    assert partial.failure_code == "adapter_failure"
    assert partial.events[-1].kind == "error"


def test_boundary_clock_is_validated_without_leaking_exception_detail() -> None:
    clock = MutableClock(float("nan"))
    runtime = boundary(SyntheticAdapter(), clock=clock)
    with pytest.raises(RuntimeContractError, match="invalid value"):
        runtime.inventory("test.runtime", operation_id="inventory-1")
    clock.value = 10.0
    clock.fail = True
    with pytest.raises(RuntimeContractError, match="clock failed") as exc_info:
        runtime.inventory("test.runtime", operation_id="inventory-1")
    assert "private clock detail" not in str(exc_info.value)


def test_literal_types_accept_the_closed_values() -> None:
    operation: RuntimeOperation = "generate"
    connection: RuntimeConnectionKind = "local_socket"
    state: RuntimeHealthState = "ready"
    finish: RuntimeFinishReason = "length"
    outcome: RuntimeGenerationOutcome = "completed"
    kind: RuntimeStreamEventKind = "delta"
    assert (operation, connection, state, finish, outcome, kind) == (
        "generate",
        "local_socket",
        "ready",
        "length",
        "completed",
        "delta",
    )
