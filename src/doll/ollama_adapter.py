"""Local-only Ollama adapter for the runtime-independent model boundary."""

from __future__ import annotations

import hashlib
import http.client
import json
import math
import re
import time
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Protocol, cast

from doll.runtime_adapter import (
    MAX_RUNTIME_MODELS,
    MAX_RUNTIME_STREAM_EVENTS,
    RuntimeAdapterContext,
    RuntimeAdapterDeclaration,
    RuntimeAdapterFailure,
    RuntimeAdapterResponse,
    RuntimeContractError,
    RuntimeFailureCode,
    RuntimeFinishReason,
    RuntimeGenerationRequest,
    RuntimeHealth,
    RuntimeInventorySnapshot,
    RuntimeModelInfo,
    RuntimeStreamEvent,
)

OLLAMA_ADAPTER_ID = "ollama.local"
OLLAMA_ADAPTER_VERSION = "1.0.0"
OLLAMA_RUNTIME_ID = "runtime.ollama.local"
OLLAMA_LOOPBACK_HOST = "127.0.0.1"
OLLAMA_DEFAULT_PORT = 11434
MAX_OLLAMA_JSON_BYTES = 4 * 1024 * 1024
MAX_OLLAMA_STREAM_BYTES = 16 * 1024 * 1024
MAX_OLLAMA_STREAM_LINE_BYTES = 1024 * 1024
MAX_OLLAMA_VERSION_CHARS = 128
MAX_OLLAMA_NATIVE_MODEL_NAME_CHARS = 256

_CLOUD_TAG_PATTERN = re.compile(r"(?:^|[-_.])cloud$", re.IGNORECASE)
_HEX_DIGEST_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")
_MODEL_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/:+\-]{0,255}$")
_VERSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+\-]{0,127}$")


class OllamaTransportFailure(RuntimeError):
    """Closed local transport failure without endpoint or provider detail."""

    __slots__ = ("code", "status_code")

    def __init__(self, code: str, *, status_code: int | None = None) -> None:
        if code not in {
            "cancelled",
            "failure",
            "invalid_response",
            "resource_limit",
            "timeout",
        }:
            raise ValueError("invalid Ollama transport failure code")
        if status_code is not None and (
            isinstance(status_code, bool)
            or not isinstance(status_code, int)
            or not 100 <= status_code <= 599
        ):
            raise ValueError("invalid Ollama HTTP status")
        self.code = code
        self.status_code = status_code
        super().__init__(f"Ollama transport failure: {code}")


@dataclass(frozen=True, slots=True)
class OllamaEndpoint:
    """Fixed IPv4 loopback endpoint; remote hosts are not representable."""

    port: int = OLLAMA_DEFAULT_PORT
    host: str = field(default=OLLAMA_LOOPBACK_HOST, init=False)

    def __post_init__(self) -> None:
        if (
            isinstance(self.port, bool)
            or not isinstance(self.port, int)
            or not 1 <= self.port <= 65535
        ):
            raise RuntimeContractError("invalid Ollama loopback port")


@dataclass(frozen=True, slots=True)
class OllamaAdapterConfig:
    """Fail-closed local-only configuration for the concrete adapter."""

    endpoint: OllamaEndpoint = field(default_factory=OllamaEndpoint)
    local_only_confirmed: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.endpoint, OllamaEndpoint):
            raise RuntimeContractError("invalid Ollama endpoint")
        if not isinstance(self.local_only_confirmed, bool):
            raise RuntimeContractError("Ollama local-only confirmation must be boolean")


@dataclass(frozen=True, slots=True)
class OllamaHttpResponse:
    """Bounded non-streaming local HTTP response."""

    status_code: int
    body: bytes = field(repr=False)

    def __post_init__(self) -> None:
        if (
            isinstance(self.status_code, bool)
            or not isinstance(self.status_code, int)
            or not 100 <= self.status_code <= 599
        ):
            raise RuntimeContractError("invalid Ollama HTTP response status")
        if not isinstance(self.body, bytes):
            raise RuntimeContractError("invalid Ollama HTTP response body")


class OllamaTransport(Protocol):
    """Injectable transport constrained to the configured loopback endpoint."""

    endpoint: OllamaEndpoint

    def request_json(
        self,
        method: str,
        path: str,
        *,
        body: bytes | None,
        context: RuntimeAdapterContext | None,
        maximum_bytes: int,
    ) -> OllamaHttpResponse: ...

    def stream_ndjson(
        self,
        path: str,
        *,
        body: bytes,
        context: RuntimeAdapterContext,
        maximum_bytes: int,
        maximum_line_bytes: int,
    ) -> Iterable[bytes]: ...


class LoopbackOllamaTransport:
    """Direct HTTP/1.1 transport with no proxy, redirect, credential, or remote host path."""

    __slots__ = ("endpoint",)

    def __init__(self, endpoint: OllamaEndpoint | None = None) -> None:
        self.endpoint = endpoint if endpoint is not None else OllamaEndpoint()
        if not isinstance(self.endpoint, OllamaEndpoint):
            raise RuntimeContractError("invalid Ollama transport endpoint")

    def request_json(
        self,
        method: str,
        path: str,
        *,
        body: bytes | None,
        context: RuntimeAdapterContext | None,
        maximum_bytes: int,
    ) -> OllamaHttpResponse:
        _validate_http_request(method, path, body, maximum_bytes)
        if maximum_bytes > MAX_OLLAMA_JSON_BYTES:
            raise RuntimeContractError("Ollama JSON response limit is too large")
        timeout = _remaining_timeout(context)
        connection = http.client.HTTPConnection(
            OLLAMA_LOOPBACK_HOST,
            self.endpoint.port,
            timeout=timeout,
        )
        try:
            connection.request(method, path, body=body, headers=_headers(body is not None))
            response = connection.getresponse()
            payload = response.read(maximum_bytes + 1)
            if len(payload) > maximum_bytes:
                raise OllamaTransportFailure("resource_limit")
            return OllamaHttpResponse(response.status, payload)
        except OllamaTransportFailure:
            raise
        except TimeoutError:
            raise OllamaTransportFailure("timeout") from None
        except (OSError, http.client.HTTPException):
            raise OllamaTransportFailure("failure") from None
        finally:
            connection.close()

    def stream_ndjson(
        self,
        path: str,
        *,
        body: bytes,
        context: RuntimeAdapterContext,
        maximum_bytes: int,
        maximum_line_bytes: int,
    ) -> Iterable[bytes]:
        _validate_http_request("POST", path, body, maximum_bytes)
        if maximum_bytes > MAX_OLLAMA_STREAM_BYTES:
            raise RuntimeContractError("Ollama stream response limit is too large")
        _validate_positive_limit("Ollama stream line", maximum_line_bytes)
        if maximum_line_bytes > MAX_OLLAMA_STREAM_LINE_BYTES:
            raise RuntimeContractError("Ollama stream line limit is too large")
        return self._stream(
            path,
            body=body,
            context=context,
            maximum_bytes=maximum_bytes,
            maximum_line_bytes=maximum_line_bytes,
        )

    def _stream(
        self,
        path: str,
        *,
        body: bytes,
        context: RuntimeAdapterContext,
        maximum_bytes: int,
        maximum_line_bytes: int,
    ) -> Iterator[bytes]:
        timeout = _remaining_timeout(context)
        connection = http.client.HTTPConnection(
            OLLAMA_LOOPBACK_HOST,
            self.endpoint.port,
            timeout=timeout,
        )
        try:
            connection.request("POST", path, body=body, headers=_headers(True))
            response = connection.getresponse()
            if response.status != 200:
                raise OllamaTransportFailure("failure", status_code=response.status)
            total = 0
            while True:
                _raise_transport_context(context)
                line = response.readline(maximum_line_bytes + 1)
                if not line:
                    break
                if len(line) > maximum_line_bytes:
                    raise OllamaTransportFailure("resource_limit")
                total += len(line)
                if total > maximum_bytes:
                    raise OllamaTransportFailure("resource_limit")
                yield line
        except OllamaTransportFailure:
            raise
        except TimeoutError:
            raise OllamaTransportFailure("timeout") from None
        except (OSError, http.client.HTTPException):
            raise OllamaTransportFailure("failure") from None
        finally:
            connection.close()


class OllamaRuntimeAdapter:
    """Concrete local-only Ollama implementation of the IMP-048 contract."""

    adapter_id = OLLAMA_ADAPTER_ID
    __slots__ = ("_config", "_transport")

    def __init__(
        self,
        config: OllamaAdapterConfig | None = None,
        *,
        transport: OllamaTransport | None = None,
    ) -> None:
        self._config = config if config is not None else OllamaAdapterConfig()
        if not isinstance(self._config, OllamaAdapterConfig):
            raise RuntimeContractError("invalid Ollama adapter configuration")
        candidate = (
            transport if transport is not None else LoopbackOllamaTransport(self._config.endpoint)
        )
        try:
            endpoint = candidate.endpoint
        except Exception:
            raise RuntimeContractError("invalid Ollama transport endpoint") from None
        if not isinstance(endpoint, OllamaEndpoint):
            raise RuntimeContractError("invalid Ollama transport endpoint")
        if endpoint != self._config.endpoint:
            raise RuntimeContractError("Ollama transport endpoint mismatch")
        self._transport = candidate

    def declaration(self) -> RuntimeAdapterDeclaration:
        return RuntimeAdapterDeclaration(
            adapter_id=self.adapter_id,
            adapter_version=OLLAMA_ADAPTER_VERSION,
            runtime_class="ollama.local",
            connection_kind="local_socket",
            supported_operations=("generate", "inventory", "stream"),
        )

    def health(self) -> RuntimeHealth:
        if not self._config.local_only_confirmed:
            return RuntimeHealth(
                self.adapter_id,
                None,
                "unavailable",
                "adapter_not_configured",
            )
        try:
            response = self._transport.request_json(
                "GET",
                "/api/version",
                body=None,
                context=None,
                maximum_bytes=MAX_OLLAMA_JSON_BYTES,
            )
            if response.status_code != 200:
                return RuntimeHealth(
                    self.adapter_id,
                    None,
                    "unavailable",
                    "runtime_unavailable",
                )
            payload = _load_json_object(response.body)
            _validate_version(payload.get("version"))
        except Exception:
            return RuntimeHealth(
                self.adapter_id,
                None,
                "unavailable",
                "runtime_unavailable",
            )
        return RuntimeHealth(self.adapter_id, OLLAMA_RUNTIME_ID, "ready")

    def inventory(self, context: RuntimeAdapterContext) -> RuntimeInventorySnapshot:
        self._require_local_only(context)
        response = self._request_json(
            "GET",
            "/api/tags",
            body=None,
            context=context,
            maximum_bytes=MAX_OLLAMA_JSON_BYTES,
        )
        if response.status_code != 200:
            raise RuntimeAdapterFailure("runtime_unavailable")
        models, _ = _parse_inventory(response.body)
        return RuntimeInventorySnapshot(OLLAMA_RUNTIME_ID, models)

    def generate(
        self,
        request: RuntimeGenerationRequest,
        context: RuntimeAdapterContext,
    ) -> RuntimeAdapterResponse:
        self._require_generation(request, context)
        native_name = self._resolve_native_model(request.model_id, context)
        payload = _encode_generate_request(native_name, request.input_text, stream=False)
        response = self._request_json(
            "POST",
            "/api/generate",
            body=payload,
            context=context,
            maximum_bytes=MAX_OLLAMA_JSON_BYTES,
        )
        if response.status_code == 404:
            raise RuntimeAdapterFailure("model_not_found")
        if response.status_code != 200:
            raise RuntimeAdapterFailure("adapter_failure")
        document = _load_json_object(response.body)
        _validate_response_model(document.get("model"), native_name)
        if document.get("done") is not True:
            raise RuntimeAdapterFailure("invalid_response")
        output = document.get("response")
        if not isinstance(output, str) or len(output) > request.max_output_chars:
            raise RuntimeAdapterFailure(
                "resource_limit" if isinstance(output, str) else "invalid_response"
            )
        return RuntimeAdapterResponse(
            OLLAMA_RUNTIME_ID,
            request.model_id,
            output,
            _finish_reason(document.get("done_reason")),
        )

    def stream(
        self,
        request: RuntimeGenerationRequest,
        context: RuntimeAdapterContext,
    ) -> Iterable[RuntimeStreamEvent]:
        self._require_generation(request, context)
        native_name = self._resolve_native_model(request.model_id, context)
        payload = _encode_generate_request(native_name, request.input_text, stream=True)
        return self._stream_events(request, context, native_name, payload)

    def _stream_events(
        self,
        request: RuntimeGenerationRequest,
        context: RuntimeAdapterContext,
        native_name: str,
        payload: bytes,
    ) -> Iterator[RuntimeStreamEvent]:
        sequence = 0
        total_chars = 0
        done = False
        try:
            lines = self._transport.stream_ndjson(
                "/api/generate",
                body=payload,
                context=context,
                maximum_bytes=MAX_OLLAMA_STREAM_BYTES,
                maximum_line_bytes=MAX_OLLAMA_STREAM_LINE_BYTES,
            )
            if isinstance(lines, bytes | str) or not isinstance(lines, Iterable):
                raise RuntimeAdapterFailure("invalid_response")
            yield RuntimeStreamEvent(request.operation_id, sequence, "start")
            sequence += 1
            for raw_line in lines:
                _raise_transport_context(context)
                if done:
                    raise RuntimeAdapterFailure("invalid_response")
                if sequence >= MAX_RUNTIME_STREAM_EVENTS:
                    raise RuntimeAdapterFailure("resource_limit")
                document = _load_json_line(raw_line)
                if "error" in document:
                    raise RuntimeAdapterFailure("adapter_failure")
                _validate_response_model(document.get("model"), native_name)
                chunk = document.get("response")
                if not isinstance(chunk, str):
                    raise RuntimeAdapterFailure("invalid_response")
                if chunk:
                    total_chars += len(chunk)
                    if total_chars > request.max_output_chars:
                        raise RuntimeAdapterFailure("resource_limit")
                    yield RuntimeStreamEvent(
                        request.operation_id,
                        sequence,
                        "delta",
                        text=chunk,
                    )
                    sequence += 1
                marker = document.get("done")
                if marker is True:
                    if done:
                        raise RuntimeAdapterFailure("invalid_response")
                    done = True
                    yield RuntimeStreamEvent(
                        request.operation_id,
                        sequence,
                        "complete",
                        finish_reason=_finish_reason(document.get("done_reason")),
                    )
                    sequence += 1
                elif marker is not False:
                    raise RuntimeAdapterFailure("invalid_response")
            if not done:
                raise RuntimeAdapterFailure("invalid_response")
        except OllamaTransportFailure as exc:
            raise RuntimeAdapterFailure(_map_transport_failure(exc)) from None

    def _resolve_native_model(self, model_id: str, context: RuntimeAdapterContext) -> str:
        response = self._request_json(
            "GET",
            "/api/tags",
            body=None,
            context=context,
            maximum_bytes=MAX_OLLAMA_JSON_BYTES,
        )
        if response.status_code != 200:
            raise RuntimeAdapterFailure("runtime_unavailable")
        _, mapping = _parse_inventory(response.body)
        native_name = mapping.get(model_id)
        if native_name is None:
            raise RuntimeAdapterFailure("model_not_found")
        return native_name

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        body: bytes | None,
        context: RuntimeAdapterContext,
        maximum_bytes: int,
    ) -> OllamaHttpResponse:
        try:
            response = self._transport.request_json(
                method,
                path,
                body=body,
                context=context,
                maximum_bytes=maximum_bytes,
            )
        except OllamaTransportFailure as exc:
            raise RuntimeAdapterFailure(_map_transport_failure(exc)) from None
        if not isinstance(response, OllamaHttpResponse):
            raise RuntimeAdapterFailure("invalid_response")
        _raise_adapter_context(context)
        return response

    def _require_local_only(self, context: RuntimeAdapterContext) -> None:
        if not self._config.local_only_confirmed:
            raise RuntimeAdapterFailure("adapter_not_configured")
        _raise_adapter_context(context)

    def _require_generation(
        self,
        request: RuntimeGenerationRequest,
        context: RuntimeAdapterContext,
    ) -> None:
        if not isinstance(request, RuntimeGenerationRequest):
            raise RuntimeContractError("Ollama generation requires a validated request")
        if not isinstance(context, RuntimeAdapterContext):
            raise RuntimeContractError("Ollama generation requires a validated context")
        self._require_local_only(context)


def ollama_model_id(native_name: str) -> str:
    """Return a deterministic opaque Doll-facing identifier for one local model name."""

    normalized = _validate_native_model_name(native_name)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return f"ollama.model.{digest}"


def is_ollama_cloud_model(native_name: str) -> bool:
    """Recognize Ollama cloud tags documented with a terminal ``cloud`` marker."""

    normalized = _validate_native_model_name(native_name)
    tag = normalized.rsplit(":", 1)[-1]
    return _CLOUD_TAG_PATTERN.search(tag) is not None


def _parse_inventory(
    body: bytes,
) -> tuple[tuple[RuntimeModelInfo, ...], Mapping[str, str]]:
    document = _load_json_object(body)
    raw_models = document.get("models")
    if not isinstance(raw_models, list):
        raise RuntimeAdapterFailure("invalid_response")
    if len(raw_models) > MAX_RUNTIME_MODELS:
        raise RuntimeAdapterFailure("resource_limit")
    entries: list[RuntimeModelInfo] = []
    mapping: dict[str, str] = {}
    native_names: set[str] = set()
    for raw_model in raw_models:
        if not isinstance(raw_model, dict):
            raise RuntimeAdapterFailure("invalid_response")
        name_value = raw_model.get("name")
        model_value = raw_model.get("model")
        if name_value is not None and model_value is not None and name_value != model_value:
            raise RuntimeAdapterFailure("invalid_response")
        native_name = _validate_native_model_name(
            name_value if name_value is not None else model_value
        )
        if is_ollama_cloud_model(native_name):
            continue
        if native_name in native_names:
            raise RuntimeAdapterFailure("invalid_response")
        native_names.add(native_name)
        model_id = ollama_model_id(native_name)
        if model_id in mapping:
            raise RuntimeAdapterFailure("invalid_response")
        revision = _normalize_digest(raw_model.get("digest"))
        entry = RuntimeModelInfo(
            model_id=model_id,
            display_name=native_name,
            revision=revision,
            features=("text",),
        )
        entries.append(entry)
        mapping[model_id] = native_name
    entries.sort(key=lambda item: item.model_id)
    return tuple(entries), MappingProxyType(mapping)


def _normalize_digest(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise RuntimeAdapterFailure("invalid_response")
    digest = value.removeprefix("sha256:")
    if _HEX_DIGEST_PATTERN.fullmatch(digest) is None:
        raise RuntimeAdapterFailure("invalid_response")
    return f"sha256-{digest.lower()}"


def _validate_native_model_name(value: object) -> str:
    if not isinstance(value, str) or _MODEL_NAME_PATTERN.fullmatch(value) is None:
        raise RuntimeAdapterFailure("invalid_response")
    return value


def _validate_version(value: object) -> str:
    if not isinstance(value, str) or _VERSION_PATTERN.fullmatch(value) is None:
        raise RuntimeContractError("invalid Ollama version response")
    return value


def _validate_response_model(value: object, expected: str) -> None:
    if not isinstance(value, str) or value != expected:
        raise RuntimeAdapterFailure("invalid_response")


def _finish_reason(value: object) -> RuntimeFinishReason:
    if value is None or value == "stop":
        return "stop"
    if value == "length":
        return "length"
    raise RuntimeAdapterFailure("invalid_response")


def _encode_generate_request(native_name: str, prompt: str, *, stream: bool) -> bytes:
    document = {"model": native_name, "prompt": prompt, "stream": stream}
    encoded = json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(encoded) > MAX_OLLAMA_JSON_BYTES:
        raise RuntimeAdapterFailure("resource_limit")
    return encoded


def _load_json_object(raw: bytes) -> dict[str, object]:
    if not isinstance(raw, bytes) or len(raw) > MAX_OLLAMA_JSON_BYTES:
        raise RuntimeAdapterFailure("resource_limit")
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_object_without_duplicates,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RuntimeContractError):
        raise RuntimeAdapterFailure("invalid_response") from None
    if not isinstance(value, dict):
        raise RuntimeAdapterFailure("invalid_response")
    return cast(dict[str, object], value)


def _load_json_line(raw: object) -> dict[str, object]:
    if not isinstance(raw, bytes):
        raise RuntimeAdapterFailure("invalid_response")
    if len(raw) > MAX_OLLAMA_STREAM_LINE_BYTES:
        raise RuntimeAdapterFailure("resource_limit")
    stripped = raw.strip()
    if not stripped:
        raise RuntimeAdapterFailure("invalid_response")
    return _load_json_object(stripped)


def _object_without_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise RuntimeContractError("duplicate JSON key")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> object:
    del value
    raise RuntimeContractError("invalid JSON constant")


def _map_transport_failure(exc: OllamaTransportFailure) -> RuntimeFailureCode:
    if exc.status_code == 404:
        return "model_not_found"
    if exc.code == "cancelled":
        return "cancelled"
    if exc.code == "timeout":
        return "timeout"
    if exc.code == "resource_limit":
        return "resource_limit"
    if exc.code == "invalid_response":
        return "invalid_response"
    return "adapter_failure"


def _validate_http_request(
    method: str,
    path: str,
    body: bytes | None,
    maximum_bytes: int,
) -> None:
    expected_method = {
        "/api/version": "GET",
        "/api/tags": "GET",
        "/api/generate": "POST",
    }.get(path)
    if expected_method is None:
        raise RuntimeContractError("unsupported Ollama API path")
    if method != expected_method:
        raise RuntimeContractError("unsupported Ollama HTTP method for path")
    if expected_method == "GET" and body is not None:
        raise RuntimeContractError("Ollama GET request cannot have a body")
    if expected_method == "POST" and (not isinstance(body, bytes) or not body):
        raise RuntimeContractError("Ollama POST request requires a body")
    if isinstance(body, bytes) and len(body) > MAX_OLLAMA_JSON_BYTES:
        raise RuntimeContractError("Ollama request body is too large")
    _validate_positive_limit("Ollama response", maximum_bytes)


def _validate_positive_limit(label: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise RuntimeContractError(f"invalid {label} size limit")


def _headers(has_body: bool) -> dict[str, str]:
    headers = {
        "Accept": "application/json, application/x-ndjson",
        "Connection": "close",
        "User-Agent": "doll-local-runtime/1",
    }
    if has_body:
        headers["Content-Type"] = "application/json"
    return headers


def _remaining_timeout(context: RuntimeAdapterContext | None) -> float:
    if context is None:
        return 2.0
    _raise_transport_context(context)
    deadline = float(context.deadline_monotonic)
    remaining = deadline - time.monotonic()
    if not math.isfinite(remaining) or remaining <= 0:
        raise OllamaTransportFailure("timeout")
    return min(remaining, 60.0)


def _context_failure(context: RuntimeAdapterContext) -> RuntimeFailureCode | None:
    if not isinstance(context, RuntimeAdapterContext):
        raise RuntimeContractError("invalid Ollama runtime context")
    if context.cancellation.is_cancelled:
        return "cancelled"
    if time.monotonic() >= context.deadline_monotonic:
        return "timeout"
    return None


def _raise_transport_context(context: RuntimeAdapterContext) -> None:
    failure = _context_failure(context)
    if failure is not None:
        raise OllamaTransportFailure(failure)


def _raise_adapter_context(context: RuntimeAdapterContext) -> None:
    failure = _context_failure(context)
    if failure is not None:
        raise RuntimeAdapterFailure(failure)


__all__ = [
    "MAX_OLLAMA_JSON_BYTES",
    "MAX_OLLAMA_NATIVE_MODEL_NAME_CHARS",
    "MAX_OLLAMA_STREAM_BYTES",
    "MAX_OLLAMA_STREAM_LINE_BYTES",
    "MAX_OLLAMA_VERSION_CHARS",
    "OLLAMA_ADAPTER_ID",
    "OLLAMA_ADAPTER_VERSION",
    "OLLAMA_DEFAULT_PORT",
    "OLLAMA_LOOPBACK_HOST",
    "OLLAMA_RUNTIME_ID",
    "LoopbackOllamaTransport",
    "OllamaAdapterConfig",
    "OllamaEndpoint",
    "OllamaHttpResponse",
    "OllamaRuntimeAdapter",
    "OllamaTransport",
    "OllamaTransportFailure",
    "is_ollama_cloud_model",
    "ollama_model_id",
]
