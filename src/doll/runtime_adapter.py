"""Runtime-independent local model adapter contract and failure-isolating boundary."""

from __future__ import annotations

import hashlib
import json
import math
import re
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from threading import Event
from types import MappingProxyType
from typing import Literal, Protocol, runtime_checkable

RuntimeOperation = Literal["inventory", "generate", "stream"]
RuntimeConnectionKind = Literal["in_process", "local_process", "local_socket"]
RuntimeHealthState = Literal["ready", "degraded", "unavailable"]
RuntimeFinishReason = Literal["stop", "length"]
RuntimeGenerationOutcome = Literal["completed", "failed", "cancelled", "timeout"]
RuntimeStreamEventKind = Literal["start", "delta", "complete", "error", "cancelled"]
RuntimeFailureCode = Literal[
    "adapter_not_configured",
    "adapter_failure",
    "cancelled",
    "invalid_response",
    "model_not_found",
    "resource_limit",
    "runtime_unavailable",
    "timeout",
    "unsupported_operation",
]

DEFAULT_RUNTIME_TIMEOUT_SECONDS = 60.0
MAX_RUNTIME_TIMEOUT_SECONDS = 600.0
MAX_RUNTIME_INPUT_CHARS = 262_144
MAX_RUNTIME_OUTPUT_CHARS = 262_144
MAX_RUNTIME_MODELS = 1_024
MAX_RUNTIME_FEATURES = 128
MAX_RUNTIME_STREAM_EVENTS = 16_384
MAX_RUNTIME_CONTEXT_WINDOW = 2**31 - 1

_IDENTIFIER_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_VERSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+\-]{0,127}$")
_OPERATION_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_ALLOWED_OPERATIONS = frozenset({"inventory", "generate", "stream"})
_ALLOWED_CONNECTION_KINDS = frozenset({"in_process", "local_process", "local_socket"})
_ALLOWED_HEALTH_STATES = frozenset({"ready", "degraded", "unavailable"})
_ALLOWED_FINISH_REASONS = frozenset({"stop", "length"})
_ALLOWED_OUTCOMES = frozenset({"completed", "failed", "cancelled", "timeout"})
_ALLOWED_STREAM_KINDS = frozenset({"start", "delta", "complete", "error", "cancelled"})
_ALLOWED_FAILURE_CODES = frozenset(
    {
        "adapter_not_configured",
        "adapter_failure",
        "cancelled",
        "invalid_response",
        "model_not_found",
        "resource_limit",
        "runtime_unavailable",
        "timeout",
        "unsupported_operation",
    }
)


class RuntimeContractError(ValueError):
    """Raised when caller or adapter data violates the runtime contract."""


class RuntimeAdapterFailure(RuntimeError):
    """Closed adapter failure that carries no provider detail or private data."""

    def __init__(self, code: RuntimeFailureCode) -> None:
        _validate_failure_code(code)
        self.code = code
        super().__init__(f"runtime adapter failure: {code}")


class RuntimeCancellationToken:
    """Thread-safe cooperative cancellation without adapter-owned state."""

    __slots__ = ("_event",)

    def __init__(self) -> None:
        self._event = Event()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def cancel(self) -> None:
        self._event.set()

    def __repr__(self) -> str:
        state = "cancelled" if self.is_cancelled else "active"
        return f"<RuntimeCancellationToken {state}>"


@dataclass(frozen=True, slots=True)
class RuntimeAdapterDeclaration:
    """Declarative, non-authoritative properties of one local runtime adapter."""

    adapter_id: str
    adapter_version: str
    runtime_class: str
    connection_kind: RuntimeConnectionKind
    supported_operations: tuple[RuntimeOperation, ...]
    offline_capable: bool = True
    cloud_fallback: bool = False
    automatic_download: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "adapter_id", _validate_identifier("adapter ID", self.adapter_id))
        object.__setattr__(
            self,
            "adapter_version",
            _validate_version("adapter version", self.adapter_version),
        )
        object.__setattr__(
            self,
            "runtime_class",
            _validate_identifier("runtime class", self.runtime_class),
        )
        if (
            not isinstance(self.connection_kind, str)
            or self.connection_kind not in _ALLOWED_CONNECTION_KINDS
        ):
            raise RuntimeContractError("invalid runtime connection kind")
        object.__setattr__(
            self,
            "supported_operations",
            _validate_operations(self.supported_operations),
        )
        for name in ("offline_capable", "cloud_fallback", "automatic_download"):
            if not isinstance(getattr(self, name), bool):
                raise RuntimeContractError(f"{name.replace('_', ' ')} must be boolean")
        if not self.offline_capable:
            raise RuntimeContractError("local runtime adapter must be offline capable")
        if self.cloud_fallback:
            raise RuntimeContractError("local runtime adapter cannot declare cloud fallback")
        if self.automatic_download:
            raise RuntimeContractError("local runtime adapter cannot declare automatic download")

    def canonical_payload(self) -> dict[str, object]:
        return {
            "adapter_id": self.adapter_id,
            "adapter_version": self.adapter_version,
            "runtime_class": self.runtime_class,
            "connection_kind": self.connection_kind,
            "supported_operations": list(self.supported_operations),
            "offline_capable": self.offline_capable,
            "cloud_fallback": self.cloud_fallback,
            "automatic_download": self.automatic_download,
        }

    @property
    def fingerprint(self) -> str:
        encoded = json.dumps(
            self.canonical_payload(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


@dataclass(frozen=True, slots=True)
class RuntimeHealth:
    """Bounded runtime availability without provider-specific diagnostics."""

    adapter_id: str
    runtime_id: str | None
    state: RuntimeHealthState
    failure_code: RuntimeFailureCode | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "adapter_id", _validate_identifier("adapter ID", self.adapter_id))
        if self.runtime_id is not None:
            object.__setattr__(
                self,
                "runtime_id",
                _validate_identifier("runtime ID", self.runtime_id),
            )
        if not isinstance(self.state, str) or self.state not in _ALLOWED_HEALTH_STATES:
            raise RuntimeContractError("invalid runtime health state")
        if self.failure_code is not None:
            _validate_failure_code(self.failure_code)
        if self.state == "ready":
            if self.runtime_id is None or self.failure_code is not None:
                raise RuntimeContractError("invalid ready runtime health")
        elif self.failure_code is None:
            raise RuntimeContractError("non-ready runtime health requires a failure code")


@dataclass(frozen=True, slots=True)
class RuntimeModelInfo:
    """Normalized local model inventory entry; features are descriptive only."""

    model_id: str
    display_name: str
    revision: str | None = None
    context_window: int | None = None
    features: tuple[str, ...] = ()
    available: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "model_id", _validate_identifier("model ID", self.model_id))
        object.__setattr__(
            self,
            "display_name",
            _validate_text("model display name", self.display_name, 256, allow_empty=False),
        )
        if self.revision is not None:
            object.__setattr__(
                self,
                "revision",
                _validate_version("model revision", self.revision),
            )
        if self.context_window is not None and (
            isinstance(self.context_window, bool)
            or not isinstance(self.context_window, int)
            or not 1 <= self.context_window <= MAX_RUNTIME_CONTEXT_WINDOW
        ):
            raise RuntimeContractError("invalid model context window")
        object.__setattr__(self, "features", _validate_features(self.features))
        if not isinstance(self.available, bool):
            raise RuntimeContractError("model availability must be boolean")

    def canonical_payload(self) -> dict[str, object]:
        return {
            "model_id": self.model_id,
            "display_name": self.display_name,
            "revision": self.revision,
            "context_window": self.context_window,
            "features": list(self.features),
            "available": self.available,
        }


@dataclass(frozen=True, slots=True)
class RuntimeInventorySnapshot:
    """Adapter-produced inventory snapshot validated before it leaves the boundary."""

    runtime_id: str
    models: tuple[RuntimeModelInfo, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "runtime_id", _validate_identifier("runtime ID", self.runtime_id))
        object.__setattr__(self, "models", _validate_models(self.models))


@dataclass(frozen=True, slots=True)
class RuntimeInventoryResult:
    """Normalized success or failure result for model inventory inspection."""

    adapter_id: str
    runtime_id: str | None
    succeeded: bool
    models: tuple[RuntimeModelInfo, ...] = ()
    failure_code: RuntimeFailureCode | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "adapter_id", _validate_identifier("adapter ID", self.adapter_id))
        if self.runtime_id is not None:
            object.__setattr__(
                self,
                "runtime_id",
                _validate_identifier("runtime ID", self.runtime_id),
            )
        if not isinstance(self.succeeded, bool):
            raise RuntimeContractError("inventory success state must be boolean")
        object.__setattr__(self, "models", _validate_models(self.models))
        if self.failure_code is not None:
            _validate_failure_code(self.failure_code)
        if self.succeeded:
            if self.runtime_id is None or self.failure_code is not None:
                raise RuntimeContractError("invalid successful inventory result")
        elif self.models or self.failure_code is None:
            raise RuntimeContractError("invalid failed inventory result")


@dataclass(frozen=True, slots=True)
class RuntimeGenerationRequest:
    """Bounded model input; text is transient and hidden from representation."""

    operation_id: str
    model_id: str
    input_text: str = field(repr=False)
    max_output_chars: int = MAX_RUNTIME_OUTPUT_CHARS
    timeout_seconds: float = DEFAULT_RUNTIME_TIMEOUT_SECONDS
    cancellation: RuntimeCancellationToken = field(
        default_factory=RuntimeCancellationToken,
        repr=False,
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "operation_id",
            _validate_operation_id(self.operation_id),
        )
        object.__setattr__(self, "model_id", _validate_identifier("model ID", self.model_id))
        object.__setattr__(
            self,
            "input_text",
            _validate_text(
                "runtime input",
                self.input_text,
                MAX_RUNTIME_INPUT_CHARS,
                allow_empty=False,
                allow_controls=True,
            ),
        )
        if (
            isinstance(self.max_output_chars, bool)
            or not isinstance(self.max_output_chars, int)
            or not 1 <= self.max_output_chars <= MAX_RUNTIME_OUTPUT_CHARS
        ):
            raise RuntimeContractError("invalid maximum output size")
        if isinstance(self.timeout_seconds, bool) or not isinstance(
            self.timeout_seconds, int | float
        ):
            raise RuntimeContractError("invalid runtime timeout")
        timeout = float(self.timeout_seconds)
        if not math.isfinite(timeout) or not 0 < timeout <= MAX_RUNTIME_TIMEOUT_SECONDS:
            raise RuntimeContractError("invalid runtime timeout")
        if not isinstance(self.cancellation, RuntimeCancellationToken):
            raise RuntimeContractError("invalid runtime cancellation token")


@dataclass(frozen=True, slots=True)
class RuntimeAdapterContext:
    """Trusted per-operation deadline and cooperative cancellation context."""

    operation_id: str
    deadline_monotonic: float
    cancellation: RuntimeCancellationToken = field(repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "operation_id",
            _validate_operation_id(self.operation_id),
        )
        if (
            isinstance(self.deadline_monotonic, bool)
            or not isinstance(self.deadline_monotonic, int | float)
            or not math.isfinite(float(self.deadline_monotonic))
        ):
            raise RuntimeContractError("invalid runtime deadline")
        if not isinstance(self.cancellation, RuntimeCancellationToken):
            raise RuntimeContractError("invalid runtime cancellation token")


@dataclass(frozen=True, slots=True)
class RuntimeAdapterResponse:
    """Successful adapter generation response before boundary normalization."""

    runtime_id: str
    model_id: str
    output_text: str = field(repr=False)
    finish_reason: RuntimeFinishReason = "stop"

    def __post_init__(self) -> None:
        object.__setattr__(self, "runtime_id", _validate_identifier("runtime ID", self.runtime_id))
        object.__setattr__(self, "model_id", _validate_identifier("model ID", self.model_id))
        object.__setattr__(
            self,
            "output_text",
            _validate_text(
                "runtime output",
                self.output_text,
                MAX_RUNTIME_OUTPUT_CHARS,
                allow_empty=True,
                allow_controls=True,
            ),
        )
        if (
            not isinstance(self.finish_reason, str)
            or self.finish_reason not in _ALLOWED_FINISH_REASONS
        ):
            raise RuntimeContractError("invalid runtime finish reason")


@dataclass(frozen=True, slots=True)
class RuntimeGenerationResult:
    """Normalized generation result with closed failure semantics."""

    operation_id: str
    adapter_id: str
    runtime_id: str | None
    model_id: str
    outcome: RuntimeGenerationOutcome
    output_text: str | None = field(default=None, repr=False)
    finish_reason: RuntimeFinishReason | None = None
    failure_code: RuntimeFailureCode | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "operation_id", _validate_operation_id(self.operation_id))
        object.__setattr__(self, "adapter_id", _validate_identifier("adapter ID", self.adapter_id))
        if self.runtime_id is not None:
            object.__setattr__(
                self,
                "runtime_id",
                _validate_identifier("runtime ID", self.runtime_id),
            )
        object.__setattr__(self, "model_id", _validate_identifier("model ID", self.model_id))
        if not isinstance(self.outcome, str) or self.outcome not in _ALLOWED_OUTCOMES:
            raise RuntimeContractError("invalid generation outcome")
        if self.output_text is not None:
            object.__setattr__(
                self,
                "output_text",
                _validate_text(
                    "runtime output",
                    self.output_text,
                    MAX_RUNTIME_OUTPUT_CHARS,
                    allow_empty=True,
                    allow_controls=True,
                ),
            )
        if self.finish_reason is not None and (
            not isinstance(self.finish_reason, str)
            or self.finish_reason not in _ALLOWED_FINISH_REASONS
        ):
            raise RuntimeContractError("invalid generation finish reason")
        if self.failure_code is not None:
            _validate_failure_code(self.failure_code)
        if self.outcome == "completed":
            if (
                self.runtime_id is None
                or self.output_text is None
                or self.finish_reason is None
                or self.failure_code is not None
            ):
                raise RuntimeContractError("invalid completed generation result")
        else:
            expected = "cancelled" if self.outcome == "cancelled" else self.outcome
            if (
                self.output_text is not None
                or self.finish_reason is not None
                or self.failure_code is None
            ):
                raise RuntimeContractError("invalid failed generation result")
            if expected in {"cancelled", "timeout"} and self.failure_code != expected:
                raise RuntimeContractError("generation outcome and failure code disagree")


@dataclass(frozen=True, slots=True)
class RuntimeStreamEvent:
    """One ordered streaming event; text payload is hidden from representation."""

    operation_id: str
    sequence: int
    kind: RuntimeStreamEventKind
    text: str | None = field(default=None, repr=False)
    finish_reason: RuntimeFinishReason | None = None
    failure_code: RuntimeFailureCode | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "operation_id", _validate_operation_id(self.operation_id))
        if (
            isinstance(self.sequence, bool)
            or not isinstance(self.sequence, int)
            or self.sequence < 0
        ):
            raise RuntimeContractError("invalid stream sequence")
        if not isinstance(self.kind, str) or self.kind not in _ALLOWED_STREAM_KINDS:
            raise RuntimeContractError("invalid stream event kind")
        if self.text is not None:
            object.__setattr__(
                self,
                "text",
                _validate_text(
                    "stream text",
                    self.text,
                    MAX_RUNTIME_OUTPUT_CHARS,
                    allow_empty=False,
                    allow_controls=True,
                ),
            )
        if self.finish_reason is not None and (
            not isinstance(self.finish_reason, str)
            or self.finish_reason not in _ALLOWED_FINISH_REASONS
        ):
            raise RuntimeContractError("invalid stream finish reason")
        if self.failure_code is not None:
            _validate_failure_code(self.failure_code)
        if self.kind == "start":
            if self.sequence != 0 or any(
                value is not None for value in (self.text, self.finish_reason, self.failure_code)
            ):
                raise RuntimeContractError("invalid stream start event")
        elif self.kind == "delta":
            if self.text is None or self.finish_reason is not None or self.failure_code is not None:
                raise RuntimeContractError("invalid stream delta event")
        elif self.kind == "complete":
            if self.text is not None or self.finish_reason is None or self.failure_code is not None:
                raise RuntimeContractError("invalid stream completion event")
        elif self.kind == "error":
            if self.text is not None or self.finish_reason is not None or self.failure_code is None:
                raise RuntimeContractError("invalid stream error event")
        elif (
            self.text is not None
            or self.finish_reason is not None
            or self.failure_code != "cancelled"
        ):
            raise RuntimeContractError("invalid stream cancellation event")


@dataclass(frozen=True, slots=True)
class RuntimeStreamResult:
    """Bounded validated transcript of one adapter streaming operation."""

    operation_id: str
    adapter_id: str
    runtime_id: str | None
    model_id: str
    outcome: RuntimeGenerationOutcome
    events: tuple[RuntimeStreamEvent, ...]
    failure_code: RuntimeFailureCode | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "operation_id", _validate_operation_id(self.operation_id))
        object.__setattr__(self, "adapter_id", _validate_identifier("adapter ID", self.adapter_id))
        if self.runtime_id is not None:
            object.__setattr__(
                self,
                "runtime_id",
                _validate_identifier("runtime ID", self.runtime_id),
            )
        object.__setattr__(self, "model_id", _validate_identifier("model ID", self.model_id))
        if not isinstance(self.outcome, str) or self.outcome not in _ALLOWED_OUTCOMES:
            raise RuntimeContractError("invalid stream outcome")
        if not isinstance(self.events, tuple):
            raise RuntimeContractError("stream events must use a tuple")
        if len(self.events) > MAX_RUNTIME_STREAM_EVENTS:
            raise RuntimeContractError("stream event limit exceeded")
        if self.failure_code is not None:
            _validate_failure_code(self.failure_code)
        _validate_stream_transcript(
            self.operation_id,
            self.outcome,
            self.events,
            self.failure_code,
            self.runtime_id,
        )

    @property
    def output_text(self) -> str:
        return "".join(event.text or "" for event in self.events if event.kind == "delta")


@runtime_checkable
class RuntimeAdapter(Protocol):
    """Replaceable local runtime adapter with no Doll authority-bearing dependencies."""

    adapter_id: str

    def declaration(self) -> RuntimeAdapterDeclaration: ...

    def health(self) -> RuntimeHealth: ...

    def inventory(self, context: RuntimeAdapterContext) -> RuntimeInventorySnapshot: ...

    def generate(
        self,
        request: RuntimeGenerationRequest,
        context: RuntimeAdapterContext,
    ) -> RuntimeAdapterResponse: ...

    def stream(
        self,
        request: RuntimeGenerationRequest,
        context: RuntimeAdapterContext,
    ) -> Iterable[RuntimeStreamEvent]: ...


class RuntimeAdapterRegistry:
    """Immutable local adapter registry; an empty registry is a valid offline state."""

    __slots__ = ("_adapters",)

    def __init__(self, adapters: Iterable[RuntimeAdapter] = ()) -> None:
        registered: dict[str, RuntimeAdapter] = {}
        for adapter in adapters:
            try:
                if not isinstance(adapter, RuntimeAdapter):
                    raise TypeError
                adapter_id = _validate_identifier("adapter ID", adapter.adapter_id)
                declaration = adapter.declaration()
                if (
                    not isinstance(declaration, RuntimeAdapterDeclaration)
                    or declaration.adapter_id != adapter_id
                ):
                    raise TypeError
            except Exception:
                raise RuntimeContractError("invalid runtime adapter registration") from None
            if adapter_id in registered:
                raise RuntimeContractError("duplicate runtime adapter ID")
            registered[adapter_id] = adapter
        self._adapters = MappingProxyType(registered)

    @property
    def adapter_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._adapters))

    def get(self, adapter_id: str) -> RuntimeAdapter | None:
        return self._adapters.get(_validate_identifier("adapter ID", adapter_id))

    def __repr__(self) -> str:
        return f"<RuntimeAdapterRegistry adapters={self.adapter_ids!r}>"


class LocalRuntimeBoundary:
    """Failure-isolating facade that never gives adapters authoritative Doll services."""

    __slots__ = ("_clock", "_registry")

    def __init__(
        self,
        registry: RuntimeAdapterRegistry | None = None,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if registry is not None and not isinstance(registry, RuntimeAdapterRegistry):
            raise RuntimeContractError("invalid runtime adapter registry")
        if not callable(clock):
            raise RuntimeContractError("invalid runtime clock")
        self._registry = registry if registry is not None else RuntimeAdapterRegistry()
        self._clock = clock

    def declaration(self, adapter_id: str) -> RuntimeAdapterDeclaration | None:
        adapter = self._registry.get(adapter_id)
        if adapter is None:
            return None
        try:
            declaration = adapter.declaration()
        except Exception:
            return None
        if (
            not isinstance(declaration, RuntimeAdapterDeclaration)
            or declaration.adapter_id != adapter_id
        ):
            return None
        return declaration

    def health(self, adapter_id: str) -> RuntimeHealth:
        normalized = _validate_identifier("adapter ID", adapter_id)
        adapter = self._registry.get(normalized)
        if adapter is None:
            return _unavailable_health(normalized, "adapter_not_configured")
        return self._safe_health(normalized, adapter)

    def inventory(
        self,
        adapter_id: str,
        *,
        operation_id: str,
        timeout_seconds: float = DEFAULT_RUNTIME_TIMEOUT_SECONDS,
        cancellation: RuntimeCancellationToken | None = None,
    ) -> RuntimeInventoryResult:
        normalized = _validate_identifier("adapter ID", adapter_id)
        token = cancellation if cancellation is not None else RuntimeCancellationToken()
        context = self._context(operation_id, timeout_seconds, token)
        prepared = self._prepare(normalized, "inventory", context)
        if not isinstance(prepared, tuple):
            return RuntimeInventoryResult(normalized, None, False, failure_code=prepared)
        adapter, health = prepared
        try:
            snapshot = adapter.inventory(context)
        except RuntimeAdapterFailure as exc:
            return RuntimeInventoryResult(
                normalized, health.runtime_id, False, failure_code=exc.code
            )
        except Exception:
            return RuntimeInventoryResult(
                normalized,
                health.runtime_id,
                False,
                failure_code="adapter_failure",
            )
        if (
            not isinstance(snapshot, RuntimeInventorySnapshot)
            or snapshot.runtime_id != health.runtime_id
        ):
            return RuntimeInventoryResult(
                normalized,
                health.runtime_id,
                False,
                failure_code="invalid_response",
            )
        post_failure = self._post_failure(context)
        if post_failure is not None:
            return RuntimeInventoryResult(
                normalized,
                health.runtime_id,
                False,
                failure_code=post_failure,
            )
        return RuntimeInventoryResult(normalized, snapshot.runtime_id, True, snapshot.models)

    def generate(
        self,
        adapter_id: str,
        request: RuntimeGenerationRequest,
    ) -> RuntimeGenerationResult:
        normalized = _validate_identifier("adapter ID", adapter_id)
        if not isinstance(request, RuntimeGenerationRequest):
            raise RuntimeContractError("generation requires a validated runtime request")
        context = self._context(
            request.operation_id,
            request.timeout_seconds,
            request.cancellation,
        )
        prepared = self._prepare(normalized, "generate", context)
        if not isinstance(prepared, tuple):
            return self._generation_failure(normalized, request, None, prepared)
        adapter, health = prepared
        try:
            response = adapter.generate(request, context)
        except RuntimeAdapterFailure as exc:
            return self._generation_failure(normalized, request, health.runtime_id, exc.code)
        except Exception:
            return self._generation_failure(
                normalized,
                request,
                health.runtime_id,
                "adapter_failure",
            )
        if (
            not isinstance(response, RuntimeAdapterResponse)
            or response.runtime_id != health.runtime_id
            or response.model_id != request.model_id
            or len(response.output_text) > request.max_output_chars
        ):
            return self._generation_failure(
                normalized,
                request,
                health.runtime_id,
                "invalid_response",
            )
        post_failure = self._post_failure(context)
        if post_failure is not None:
            return self._generation_failure(
                normalized,
                request,
                health.runtime_id,
                post_failure,
            )
        return RuntimeGenerationResult(
            operation_id=request.operation_id,
            adapter_id=normalized,
            runtime_id=response.runtime_id,
            model_id=request.model_id,
            outcome="completed",
            output_text=response.output_text,
            finish_reason=response.finish_reason,
        )

    def stream(
        self,
        adapter_id: str,
        request: RuntimeGenerationRequest,
    ) -> RuntimeStreamResult:
        normalized = _validate_identifier("adapter ID", adapter_id)
        if not isinstance(request, RuntimeGenerationRequest):
            raise RuntimeContractError("streaming requires a validated runtime request")
        context = self._context(
            request.operation_id,
            request.timeout_seconds,
            request.cancellation,
        )
        prepared = self._prepare(normalized, "stream", context)
        if not isinstance(prepared, tuple):
            return self._stream_failure(normalized, request, None, prepared)
        adapter, health = prepared
        events: list[RuntimeStreamEvent] = []
        total_chars = 0
        try:
            stream = adapter.stream(request, context)
            if isinstance(stream, str | bytes) or not isinstance(stream, Iterable):
                raise RuntimeContractError("invalid stream iterable")
            for event in stream:
                failure = self._post_failure(context)
                if failure is not None:
                    return self._stream_failure(
                        normalized,
                        request,
                        health.runtime_id,
                        failure,
                        tuple(events),
                    )
                if not isinstance(event, RuntimeStreamEvent):
                    raise RuntimeContractError("invalid stream event")
                if event.operation_id != request.operation_id or event.sequence != len(events):
                    raise RuntimeContractError("invalid stream ordering")
                events.append(event)
                if len(events) > MAX_RUNTIME_STREAM_EVENTS:
                    return self._stream_failure(
                        normalized,
                        request,
                        health.runtime_id,
                        "resource_limit",
                        tuple(events[:-1]),
                    )
                total_chars += len(event.text or "")
                if total_chars > request.max_output_chars:
                    return self._stream_failure(
                        normalized,
                        request,
                        health.runtime_id,
                        "resource_limit",
                        tuple(events[:-1]),
                    )
            post_failure = self._post_failure(context)
            if post_failure is not None:
                return self._stream_failure(
                    normalized,
                    request,
                    health.runtime_id,
                    post_failure,
                    tuple(events),
                )
            return RuntimeStreamResult(
                operation_id=request.operation_id,
                adapter_id=normalized,
                runtime_id=health.runtime_id,
                model_id=request.model_id,
                outcome="completed",
                events=tuple(events),
            )
        except RuntimeAdapterFailure as exc:
            return self._stream_failure(
                normalized,
                request,
                health.runtime_id,
                exc.code,
                tuple(events),
            )
        except Exception:
            return self._stream_failure(
                normalized,
                request,
                health.runtime_id,
                "invalid_response" if events else "adapter_failure",
                tuple(events),
            )

    def _context(
        self,
        operation_id: str,
        timeout_seconds: float,
        cancellation: RuntimeCancellationToken,
    ) -> RuntimeAdapterContext:
        operation = _validate_operation_id(operation_id)
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, int | float):
            raise RuntimeContractError("invalid runtime timeout")
        timeout = float(timeout_seconds)
        if not math.isfinite(timeout) or not 0 < timeout <= MAX_RUNTIME_TIMEOUT_SECONDS:
            raise RuntimeContractError("invalid runtime timeout")
        if not isinstance(cancellation, RuntimeCancellationToken):
            raise RuntimeContractError("invalid runtime cancellation token")
        return RuntimeAdapterContext(operation, self._now() + timeout, cancellation)

    def _prepare(
        self,
        adapter_id: str,
        operation: RuntimeOperation,
        context: RuntimeAdapterContext,
    ) -> tuple[RuntimeAdapter, RuntimeHealth] | RuntimeFailureCode:
        if context.cancellation.is_cancelled:
            return "cancelled"
        if self._now() >= context.deadline_monotonic:
            return "timeout"
        adapter = self._registry.get(adapter_id)
        if adapter is None:
            return "adapter_not_configured"
        declaration = self.declaration(adapter_id)
        if declaration is None:
            return "adapter_failure"
        if operation not in declaration.supported_operations:
            return "unsupported_operation"
        health = self._safe_health(adapter_id, adapter)
        if health.state == "unavailable":
            return health.failure_code or "runtime_unavailable"
        post_failure = self._post_failure(context)
        if post_failure is not None:
            return post_failure
        return adapter, health

    def _safe_health(self, adapter_id: str, adapter: RuntimeAdapter) -> RuntimeHealth:
        try:
            declaration = adapter.declaration()
            health = adapter.health()
        except Exception:
            return _unavailable_health(adapter_id, "adapter_failure")
        if (
            not isinstance(declaration, RuntimeAdapterDeclaration)
            or declaration.adapter_id != adapter_id
            or not isinstance(health, RuntimeHealth)
            or health.adapter_id != adapter_id
        ):
            return _unavailable_health(adapter_id, "adapter_failure")
        return health

    def _post_failure(self, context: RuntimeAdapterContext) -> RuntimeFailureCode | None:
        if context.cancellation.is_cancelled:
            return "cancelled"
        if self._now() >= context.deadline_monotonic:
            return "timeout"
        return None

    def _generation_failure(
        self,
        adapter_id: str,
        request: RuntimeGenerationRequest,
        runtime_id: str | None,
        code: RuntimeFailureCode,
    ) -> RuntimeGenerationResult:
        outcome: RuntimeGenerationOutcome
        if code == "cancelled":
            outcome = "cancelled"
        elif code == "timeout":
            outcome = "timeout"
        else:
            outcome = "failed"
        return RuntimeGenerationResult(
            operation_id=request.operation_id,
            adapter_id=adapter_id,
            runtime_id=runtime_id,
            model_id=request.model_id,
            outcome=outcome,
            failure_code=code,
        )

    def _stream_failure(
        self,
        adapter_id: str,
        request: RuntimeGenerationRequest,
        runtime_id: str | None,
        code: RuntimeFailureCode,
        events: tuple[RuntimeStreamEvent, ...] = (),
    ) -> RuntimeStreamResult:
        outcome: RuntimeGenerationOutcome
        kind: RuntimeStreamEventKind
        if code == "cancelled":
            outcome = "cancelled"
            kind = "cancelled"
        elif code == "timeout":
            outcome = "timeout"
            kind = "error"
        else:
            outcome = "failed"
            kind = "error"
        safe_events = _prefix_before_terminal(events)[: MAX_RUNTIME_STREAM_EVENTS - 1]
        if not safe_events:
            safe_events = (RuntimeStreamEvent(request.operation_id, 0, "start"),)
        terminal = RuntimeStreamEvent(
            request.operation_id,
            len(safe_events),
            kind,
            failure_code=code,
        )
        return RuntimeStreamResult(
            operation_id=request.operation_id,
            adapter_id=adapter_id,
            runtime_id=runtime_id,
            model_id=request.model_id,
            outcome=outcome,
            events=(*safe_events, terminal),
            failure_code=code,
        )

    def _now(self) -> float:
        try:
            value = self._clock()
        except Exception:
            raise RuntimeContractError("runtime clock failed") from None
        if (
            isinstance(value, bool)
            or not isinstance(value, int | float)
            or not math.isfinite(value)
        ):
            raise RuntimeContractError("runtime clock returned an invalid value")
        return float(value)


def _validate_identifier(label: str, value: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER_PATTERN.fullmatch(value) is None:
        raise RuntimeContractError(f"invalid {label}")
    return value


def _validate_version(label: str, value: str) -> str:
    if not isinstance(value, str) or _VERSION_PATTERN.fullmatch(value) is None:
        raise RuntimeContractError(f"invalid {label}")
    return value


def _validate_operation_id(value: str) -> str:
    if not isinstance(value, str) or _OPERATION_ID_PATTERN.fullmatch(value) is None:
        raise RuntimeContractError("invalid runtime operation ID")
    return value


def _validate_failure_code(value: str) -> None:
    if not isinstance(value, str) or value not in _ALLOWED_FAILURE_CODES:
        raise RuntimeContractError("invalid runtime failure code")


def _validate_operations(values: tuple[RuntimeOperation, ...]) -> tuple[RuntimeOperation, ...]:
    if not isinstance(values, tuple) or not values:
        raise RuntimeContractError("runtime operations must use a non-empty tuple")
    if any(not isinstance(value, str) or value not in _ALLOWED_OPERATIONS for value in values):
        raise RuntimeContractError("invalid runtime operation")
    if len(set(values)) != len(values) or values != tuple(sorted(values)):
        raise RuntimeContractError("runtime operations must be unique and sorted")
    return values


def _validate_features(values: tuple[str, ...]) -> tuple[str, ...]:
    if not isinstance(values, tuple):
        raise RuntimeContractError("model features must use a tuple")
    if len(values) > MAX_RUNTIME_FEATURES:
        raise RuntimeContractError("model feature limit exceeded")
    normalized = tuple(_validate_identifier("model feature", value) for value in values)
    if len(set(normalized)) != len(normalized) or normalized != tuple(sorted(normalized)):
        raise RuntimeContractError("model features must be unique and sorted")
    return normalized


def _validate_models(values: tuple[RuntimeModelInfo, ...]) -> tuple[RuntimeModelInfo, ...]:
    if not isinstance(values, tuple):
        raise RuntimeContractError("runtime models must use a tuple")
    if len(values) > MAX_RUNTIME_MODELS:
        raise RuntimeContractError("runtime model limit exceeded")
    if any(not isinstance(value, RuntimeModelInfo) for value in values):
        raise RuntimeContractError("invalid runtime model entry")
    identifiers = tuple(value.model_id for value in values)
    if len(set(identifiers)) != len(identifiers) or identifiers != tuple(sorted(identifiers)):
        raise RuntimeContractError("runtime models must be unique and sorted")
    return values


def _validate_text(
    label: str,
    value: str,
    maximum: int,
    *,
    allow_empty: bool,
    allow_controls: bool = False,
) -> str:
    if not isinstance(value, str):
        raise RuntimeContractError(f"{label} must be text")
    if not allow_empty and not value:
        raise RuntimeContractError(f"{label} must not be empty")
    if len(value) > maximum:
        raise RuntimeContractError(f"{label} exceeds the accepted size limit")
    if "\x00" in value or (not allow_controls and any(ord(char) < 32 for char in value)):
        raise RuntimeContractError(f"{label} contains invalid control characters")
    return value


def _validate_stream_transcript(
    operation_id: str,
    outcome: RuntimeGenerationOutcome,
    events: tuple[RuntimeStreamEvent, ...],
    failure_code: RuntimeFailureCode | None,
    runtime_id: str | None,
) -> None:
    if not events or events[0].kind != "start":
        raise RuntimeContractError("stream transcript must start with a start event")
    for sequence, event in enumerate(events):
        if not isinstance(event, RuntimeStreamEvent):
            raise RuntimeContractError("invalid stream transcript event")
        if event.operation_id != operation_id or event.sequence != sequence:
            raise RuntimeContractError("invalid stream transcript ordering")
    terminal = events[-1]
    if any(event.kind in {"complete", "error", "cancelled"} for event in events[:-1]):
        raise RuntimeContractError("stream transcript contains an early terminal event")
    total = sum(len(event.text or "") for event in events)
    if total > MAX_RUNTIME_OUTPUT_CHARS:
        raise RuntimeContractError("stream transcript output limit exceeded")
    if outcome == "completed":
        if runtime_id is None or terminal.kind != "complete" or failure_code is not None:
            raise RuntimeContractError("invalid completed stream result")
    else:
        expected_kind = "cancelled" if outcome == "cancelled" else "error"
        expected_code = "cancelled" if outcome == "cancelled" else outcome
        if terminal.kind != expected_kind or failure_code is None:
            raise RuntimeContractError("invalid failed stream result")
        if outcome in {"cancelled", "timeout"} and failure_code != expected_code:
            raise RuntimeContractError("stream outcome and failure code disagree")
        if terminal.failure_code != failure_code:
            raise RuntimeContractError("stream terminal and result failure codes disagree")


def _prefix_before_terminal(
    events: tuple[RuntimeStreamEvent, ...],
) -> tuple[RuntimeStreamEvent, ...]:
    prefix: list[RuntimeStreamEvent] = []
    for event in events:
        if event.kind in {"complete", "error", "cancelled"}:
            break
        prefix.append(event)
    return tuple(prefix)


def _unavailable_health(adapter_id: str, code: RuntimeFailureCode) -> RuntimeHealth:
    return RuntimeHealth(adapter_id, None, "unavailable", code)


__all__ = [
    "DEFAULT_RUNTIME_TIMEOUT_SECONDS",
    "MAX_RUNTIME_CONTEXT_WINDOW",
    "MAX_RUNTIME_FEATURES",
    "MAX_RUNTIME_INPUT_CHARS",
    "MAX_RUNTIME_MODELS",
    "MAX_RUNTIME_OUTPUT_CHARS",
    "MAX_RUNTIME_STREAM_EVENTS",
    "MAX_RUNTIME_TIMEOUT_SECONDS",
    "LocalRuntimeBoundary",
    "RuntimeAdapter",
    "RuntimeAdapterContext",
    "RuntimeAdapterDeclaration",
    "RuntimeAdapterFailure",
    "RuntimeAdapterRegistry",
    "RuntimeAdapterResponse",
    "RuntimeCancellationToken",
    "RuntimeConnectionKind",
    "RuntimeContractError",
    "RuntimeFailureCode",
    "RuntimeFinishReason",
    "RuntimeGenerationOutcome",
    "RuntimeGenerationRequest",
    "RuntimeGenerationResult",
    "RuntimeHealth",
    "RuntimeHealthState",
    "RuntimeInventoryResult",
    "RuntimeInventorySnapshot",
    "RuntimeModelInfo",
    "RuntimeOperation",
    "RuntimeStreamEvent",
    "RuntimeStreamEventKind",
    "RuntimeStreamResult",
]
