"""Explicit local-only Ollama chat capture into the IMP-055 source format."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, cast
from uuid import NAMESPACE_URL, UUID, uuid5

from doll.ollama_adapter import (
    MAX_OLLAMA_JSON_BYTES,
    LoopbackOllamaTransport,
    OllamaAdapterConfig,
    OllamaHttpResponse,
    OllamaRuntimeAdapter,
    OllamaTransport,
    OllamaTransportFailure,
)
from doll.ollama_session_import import (
    OllamaSessionImportError,
    OllamaSessionSourceAdapter,
    OllamaSessionStageResult,
)
from doll.portability import PortabilityContractError
from doll.runtime_adapter import (
    MAX_RUNTIME_OUTPUT_CHARS,
    RuntimeAdapterContext,
    RuntimeAdapterFailure,
    RuntimeContractError,
    RuntimeFailureCode,
)

OllamaChatFinishReason = Literal["stop", "length"]

_MAX_CAPTURE_MESSAGES = 4_096
_MAX_IDENTIFIER_LENGTH = 256
_MAX_TITLE_LENGTH = 4_096
_MAX_USER_TEXT_CHARS = 262_144
_MODEL_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_VERSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+\-]{0,127}$")
_ALLOWED_HISTORY_ROLES = frozenset({"user", "assistant", "system", "tool"})
_ALLOWED_RESPONSE_MESSAGE_KEYS = frozenset({"role", "content", "images", "tool_calls", "thinking"})


class OllamaChatCaptureError(ValueError):
    """Raised when caller input or a retained source bundle is invalid."""


class OllamaChatCaptureFailure(RuntimeError):
    """Bounded live-runtime failure without prompt, response, or native model detail."""

    __slots__ = ("code",)

    def __init__(self, code: RuntimeFailureCode) -> None:
        self.code = code
        super().__init__(f"Ollama chat capture failure: {code}")


@dataclass(frozen=True, slots=True)
class OllamaChatCaptureRequest:
    """One explicit text turn to start or append to a retained session bundle."""

    model_id: str
    source_environment_id: str
    conversation_id: str
    user_message_id: str
    assistant_message_id: str
    user_text: str = field(repr=False)
    user_created_at: str
    exported_at: str
    existing_bundle: bytes | None = field(default=None, repr=False)
    title: str | None = None
    conversation_created_at: str | None = None
    max_output_chars: int = MAX_RUNTIME_OUTPUT_CHARS

    def __post_init__(self) -> None:
        object.__setattr__(self, "model_id", _model_id(self.model_id))
        object.__setattr__(
            self,
            "source_environment_id",
            _canonical_uuid(self.source_environment_id, "source environment ID"),
        )
        object.__setattr__(
            self,
            "conversation_id",
            _identifier(self.conversation_id, "conversation ID"),
        )
        object.__setattr__(
            self,
            "user_message_id",
            _identifier(self.user_message_id, "user message ID"),
        )
        object.__setattr__(
            self,
            "assistant_message_id",
            _identifier(self.assistant_message_id, "assistant message ID"),
        )
        if self.user_message_id == self.assistant_message_id:
            raise OllamaChatCaptureError("capture message identifiers must differ")
        object.__setattr__(
            self,
            "user_text",
            _bounded_text(
                self.user_text,
                "user text",
                _MAX_USER_TEXT_CHARS,
                allow_blank=False,
            ),
        )
        user_time = _timestamp(self.user_created_at, "user message timestamp")
        exported_time = _timestamp(self.exported_at, "export timestamp")
        if exported_time < user_time:
            raise OllamaChatCaptureError("export timestamp precedes user message")
        if (
            isinstance(self.max_output_chars, bool)
            or not isinstance(self.max_output_chars, int)
            or not 1 <= self.max_output_chars <= MAX_RUNTIME_OUTPUT_CHARS
        ):
            raise OllamaChatCaptureError("invalid maximum captured output size")
        if self.existing_bundle is None:
            if self.conversation_created_at is None:
                raise OllamaChatCaptureError(
                    "new capture requires a conversation creation timestamp"
                )
            created_time = _timestamp(
                self.conversation_created_at,
                "conversation creation timestamp",
            )
            if created_time > user_time:
                raise OllamaChatCaptureError(
                    "conversation creation timestamp follows first message"
                )
            if self.title is not None:
                object.__setattr__(
                    self,
                    "title",
                    _bounded_text(
                        self.title,
                        "conversation title",
                        _MAX_TITLE_LENGTH,
                        allow_blank=True,
                    ),
                )
        else:
            if not isinstance(self.existing_bundle, bytes) or not self.existing_bundle:
                raise OllamaChatCaptureError("existing bundle must be non-empty bytes")
            if self.title is not None or self.conversation_created_at is not None:
                raise OllamaChatCaptureError(
                    "append capture cannot replace conversation title or creation time"
                )


@dataclass(frozen=True, slots=True)
class OllamaChatCaptureResult:
    """Bounded capture result; source bytes stay hidden from representation."""

    operation_id: str
    model_id: str
    runtime_version: str
    source_root_hash: str
    conversation_count: int
    message_count: int
    finish_reason: OllamaChatFinishReason
    bundle_bytes: bytes = field(repr=False)

    def canonical_summary(self) -> dict[str, object]:
        return {
            "operation_id": self.operation_id,
            "model_id": self.model_id,
            "runtime_version": self.runtime_version,
            "source_root_hash": self.source_root_hash,
            "conversation_count": self.conversation_count,
            "message_count": self.message_count,
            "finish_reason": self.finish_reason,
        }


class OllamaChatCaptureService:
    """Capture explicit text turns through fixed loopback and return source bytes."""

    __slots__ = ("_config", "_runtime", "_source_adapter", "_transport")

    def __init__(
        self,
        config: OllamaAdapterConfig,
        *,
        transport: OllamaTransport | None = None,
        source_adapter: OllamaSessionSourceAdapter | None = None,
    ) -> None:
        if not isinstance(config, OllamaAdapterConfig):
            raise OllamaChatCaptureError("invalid Ollama capture configuration")
        if not config.local_only_confirmed:
            raise OllamaChatCaptureError("Ollama local-only capture is not confirmed")
        candidate = transport if transport is not None else LoopbackOllamaTransport(config.endpoint)
        try:
            runtime = OllamaRuntimeAdapter(config, transport=candidate)
        except RuntimeContractError as exc:
            raise OllamaChatCaptureError("invalid Ollama capture transport") from exc
        self._config = config
        self._transport = candidate
        self._runtime = runtime
        self._source_adapter = source_adapter or OllamaSessionSourceAdapter()
        if not isinstance(self._source_adapter, OllamaSessionSourceAdapter):
            raise OllamaChatCaptureError("invalid Ollama session source adapter")

    def capture(
        self,
        request: OllamaChatCaptureRequest,
        context: RuntimeAdapterContext,
    ) -> OllamaChatCaptureResult:
        """Capture one explicit user and assistant turn without writing Doll State."""

        if not isinstance(request, OllamaChatCaptureRequest):
            raise OllamaChatCaptureError("invalid Ollama chat capture request")
        if not isinstance(context, RuntimeAdapterContext):
            raise OllamaChatCaptureError("invalid Ollama chat capture context")

        document, conversation, messages = self._prepare_document(request)
        native_model = self._resolve_local_model(request.model_id, context)
        runtime_version = self._read_runtime_version(context)
        existing_version = document.get("runtime_version")
        if existing_version is not None and existing_version != runtime_version:
            raise OllamaChatCaptureError(
                "existing session runtime version differs from current runtime"
            )

        request_messages = [{"role": item["role"], "content": item["content"]} for item in messages]
        request_messages.append({"role": "user", "content": request.user_text})
        chat_body = _encode_chat_request(native_model, request_messages)
        response = self._request_json(
            "POST",
            "/api/chat",
            body=chat_body,
            context=context,
        )
        if response.status_code == 404:
            raise OllamaChatCaptureFailure("model_not_found")
        if response.status_code != 200:
            raise OllamaChatCaptureFailure("adapter_failure")
        assistant_text, assistant_time, finish_reason = _parse_chat_response(
            response.body,
            expected_model=native_model,
            maximum_chars=request.max_output_chars,
        )

        parent_ids = [messages[-1]["message_id"]] if messages else []
        messages.append(
            {
                "message_id": request.user_message_id,
                "role": "user",
                "content": request.user_text,
                "created_at": request.user_created_at,
                "parent_message_ids": parent_ids,
                "model": None,
                "attachments": [],
                "tool_calls": [],
            }
        )
        messages.append(
            {
                "message_id": request.assistant_message_id,
                "role": "assistant",
                "content": assistant_text,
                "created_at": assistant_time,
                "parent_message_ids": [request.user_message_id],
                "model": native_model,
                "attachments": [],
                "tool_calls": [],
            }
        )
        conversation["messages"] = messages
        document["runtime_version"] = runtime_version
        document["exported_at"] = request.exported_at
        bundle_bytes = _encode_bundle(document)
        staged = self._validate_bundle(bundle_bytes, request.exported_at)
        if staged.source_environment.environment_id != request.source_environment_id:
            raise OllamaChatCaptureError("captured source environment identity changed")
        source_root_hash = hashlib.sha256(bundle_bytes).hexdigest()
        if staged.inventory.source_root_hash != source_root_hash:
            raise OllamaChatCaptureError("captured source hash validation failed")
        return OllamaChatCaptureResult(
            operation_id=context.operation_id,
            model_id=request.model_id,
            runtime_version=runtime_version,
            source_root_hash=source_root_hash,
            conversation_count=staged.inventory.conversation_count,
            message_count=staged.inventory.message_count,
            finish_reason=finish_reason,
            bundle_bytes=bundle_bytes,
        )

    def _prepare_document(
        self,
        request: OllamaChatCaptureRequest,
    ) -> tuple[dict[str, object], dict[str, object], list[dict[str, object]]]:
        if request.existing_bundle is None:
            conversation: dict[str, object] = {
                "conversation_id": request.conversation_id,
                "title": request.title,
                "created_at": request.conversation_created_at,
                "messages": [],
            }
            document: dict[str, object] = {
                "format": "ollama-api-chat-session",
                "format_version": "1",
                "source_environment_id": request.source_environment_id,
                "runtime_version": None,
                "exported_at": request.exported_at,
                "conversations": [conversation],
            }
            return document, conversation, []

        staged = self._validate_bundle(request.existing_bundle, request.user_created_at)
        if staged.source_environment.environment_id != request.source_environment_id:
            raise OllamaChatCaptureError("existing source environment identity mismatch")
        document = _load_json_object(request.existing_bundle, "existing bundle")
        raw_conversations = document.get("conversations")
        if not isinstance(raw_conversations, list):
            raise OllamaChatCaptureError("existing conversation collection is invalid")
        matches = [
            item
            for item in raw_conversations
            if isinstance(item, dict) and item.get("conversation_id") == request.conversation_id
        ]
        if len(matches) != 1:
            raise OllamaChatCaptureError(
                "existing bundle must contain exactly one selected conversation"
            )
        conversation = cast(dict[str, object], matches[0])
        raw_messages = conversation.get("messages")
        if not isinstance(raw_messages, list):
            raise OllamaChatCaptureError("existing selected conversation messages are invalid")
        messages = [_history_message(item, index) for index, item in enumerate(raw_messages)]
        if len(messages) > _MAX_CAPTURE_MESSAGES - 2:
            raise OllamaChatCaptureError("existing chat history exceeds capture limit")
        _validate_linear_history(messages)
        identifiers = {cast(str, item["message_id"]) for item in messages}
        if request.user_message_id in identifiers or request.assistant_message_id in identifiers:
            raise OllamaChatCaptureError("capture message identifier already exists")
        return document, conversation, messages

    def _resolve_local_model(
        self,
        model_id: str,
        context: RuntimeAdapterContext,
    ) -> str:
        try:
            inventory = self._runtime.inventory(context)
        except RuntimeAdapterFailure as exc:
            raise OllamaChatCaptureFailure(exc.code) from None
        matches = [model for model in inventory.models if model.model_id == model_id]
        if len(matches) != 1 or not matches[0].available:
            raise OllamaChatCaptureFailure("model_not_found")
        return matches[0].display_name

    def _read_runtime_version(self, context: RuntimeAdapterContext) -> str:
        response = self._request_json(
            "GET",
            "/api/version",
            body=None,
            context=context,
        )
        if response.status_code != 200:
            raise OllamaChatCaptureFailure("runtime_unavailable")
        try:
            document = _load_json_object(response.body, "runtime version response")
        except OllamaChatCaptureError:
            raise OllamaChatCaptureFailure("invalid_response") from None
        value = document.get("version")
        if not isinstance(value, str) or _VERSION_PATTERN.fullmatch(value) is None:
            raise OllamaChatCaptureFailure("invalid_response")
        return value

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        body: bytes | None,
        context: RuntimeAdapterContext,
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
            raise OllamaChatCaptureFailure(_transport_failure_code(exc)) from None
        except RuntimeContractError:
            raise OllamaChatCaptureFailure("adapter_failure") from None

    def _validate_bundle(
        self,
        source_bytes: bytes,
        started_at: str,
    ) -> OllamaSessionStageResult:
        try:
            return self._source_adapter.stage(
                source_bytes,
                import_batch_id=_validation_batch_id(source_bytes),
                started_at=started_at,
            )
        except (OllamaSessionImportError, PortabilityContractError) as exc:
            raise OllamaChatCaptureError("Ollama session bundle validation failed") from exc


def _history_message(value: object, index: int) -> dict[str, object]:
    if not isinstance(value, dict):
        raise OllamaChatCaptureError(f"existing history message {index} is invalid")
    message = cast(dict[str, object], value)
    message_id = message.get("message_id")
    role = message.get("role")
    content = message.get("content")
    parents = message.get("parent_message_ids")
    attachments = message.get("attachments")
    tool_calls = message.get("tool_calls")
    if not isinstance(message_id, str):
        raise OllamaChatCaptureError("existing history message identity is invalid")
    _identifier(message_id, "existing message ID")
    if role not in _ALLOWED_HISTORY_ROLES:
        raise OllamaChatCaptureError("existing history role is unsupported for live capture")
    if not isinstance(content, str) or len(content) > _MAX_USER_TEXT_CHARS:
        raise OllamaChatCaptureError("existing history content is invalid")
    if not isinstance(parents, list) or not all(isinstance(item, str) for item in parents):
        raise OllamaChatCaptureError("existing history parent relationship is invalid")
    if attachments != [] or tool_calls != []:
        raise OllamaChatCaptureError(
            "attachment or tool-call history is unsupported for text capture"
        )
    return message


def _validate_linear_history(messages: list[dict[str, object]]) -> None:
    identifiers: set[str] = set()
    previous: str | None = None
    for message in messages:
        message_id = cast(str, message["message_id"])
        if message_id in identifiers:
            raise OllamaChatCaptureError("existing history contains a duplicate message ID")
        identifiers.add(message_id)
        parents = cast(list[str], message["parent_message_ids"])
        expected = [] if previous is None else [previous]
        if parents != expected:
            raise OllamaChatCaptureError("existing history is not one linear conversation")
        previous = message_id


def _encode_chat_request(native_model: str, messages: list[dict[str, object]]) -> bytes:
    if not messages or len(messages) > _MAX_CAPTURE_MESSAGES:
        raise OllamaChatCaptureError("chat request message count is invalid")
    encoded = json.dumps(
        {"model": native_model, "messages": messages, "stream": False},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    if len(encoded) > MAX_OLLAMA_JSON_BYTES:
        raise OllamaChatCaptureError("chat request exceeds the Ollama request limit")
    return encoded


def _parse_chat_response(
    raw: bytes,
    *,
    expected_model: str,
    maximum_chars: int,
) -> tuple[str, str, OllamaChatFinishReason]:
    try:
        document = _load_json_object(raw, "chat response")
    except OllamaChatCaptureError:
        raise OllamaChatCaptureFailure("invalid_response") from None
    if document.get("model") != expected_model:
        raise OllamaChatCaptureFailure("invalid_response")
    created_at = document.get("created_at")
    if not isinstance(created_at, str):
        raise OllamaChatCaptureFailure("invalid_response")
    try:
        _timestamp(created_at, "assistant response timestamp")
    except OllamaChatCaptureError:
        raise OllamaChatCaptureFailure("invalid_response") from None
    if document.get("done") is not True:
        raise OllamaChatCaptureFailure("invalid_response")
    reason = document.get("done_reason")
    if reason is None or reason == "stop":
        finish_reason: OllamaChatFinishReason = "stop"
    elif reason == "length":
        finish_reason = "length"
    else:
        raise OllamaChatCaptureFailure("invalid_response")
    raw_message = document.get("message")
    if not isinstance(raw_message, dict):
        raise OllamaChatCaptureFailure("invalid_response")
    message = cast(dict[str, object], raw_message)
    if not set(message).issubset(_ALLOWED_RESPONSE_MESSAGE_KEYS):
        raise OllamaChatCaptureFailure("invalid_response")
    if message.get("role") != "assistant":
        raise OllamaChatCaptureFailure("invalid_response")
    content = message.get("content")
    if (
        not isinstance(content, str)
        or not content.strip()
        or "\x00" in content
        or len(content) > maximum_chars
    ):
        code: RuntimeFailureCode = (
            "resource_limit"
            if isinstance(content, str) and len(content) > maximum_chars
            else "invalid_response"
        )
        raise OllamaChatCaptureFailure(code)
    for key in ("images", "tool_calls", "thinking"):
        value = message.get(key)
        if value not in (None, "", []):
            raise OllamaChatCaptureFailure("invalid_response")
    return content, created_at, finish_reason


def _load_json_object(raw: bytes, label: str) -> dict[str, object]:
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_OLLAMA_JSON_BYTES:
        raise OllamaChatCaptureError(f"{label} byte boundary is invalid")
    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=_object_without_duplicates,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, OllamaChatCaptureError, RecursionError):
        raise OllamaChatCaptureError(f"{label} is invalid JSON") from None
    if not isinstance(value, dict):
        raise OllamaChatCaptureError(f"{label} must be a JSON object")
    return cast(dict[str, object], value)


def _object_without_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise OllamaChatCaptureError("JSON object contains a duplicate key")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> object:
    del value
    raise OllamaChatCaptureError("non-standard JSON constant is unsupported")


def _encode_bundle(document: dict[str, object]) -> bytes:
    try:
        encoded = json.dumps(
            document,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, RecursionError) as exc:
        raise OllamaChatCaptureError("captured bundle is not serializable") from exc
    if len(encoded) > 10 * 1024 * 1024:
        raise OllamaChatCaptureError("captured bundle exceeds source adapter limit")
    return encoded


def _validation_batch_id(source_bytes: bytes) -> str:
    digest = hashlib.sha256(source_bytes).hexdigest()
    return str(uuid5(NAMESPACE_URL, f"doll:ollama-chat-capture:{digest}"))


def _transport_failure_code(exc: OllamaTransportFailure) -> RuntimeFailureCode:
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


def _canonical_uuid(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise OllamaChatCaptureError(f"{label} must be text")
    try:
        canonical = str(UUID(value))
    except (ValueError, AttributeError) as exc:
        raise OllamaChatCaptureError(f"{label} is invalid") from exc
    if canonical != value:
        raise OllamaChatCaptureError(f"{label} must use canonical UUID text")
    return canonical


def _identifier(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > _MAX_IDENTIFIER_LENGTH
        or any(ord(character) < 32 for character in value)
    ):
        raise OllamaChatCaptureError(f"{label} is invalid")
    return value


def _model_id(value: object) -> str:
    if not isinstance(value, str) or _MODEL_ID_PATTERN.fullmatch(value) is None:
        raise OllamaChatCaptureError("opaque model ID is invalid")
    return value


def _bounded_text(
    value: object,
    label: str,
    maximum: int,
    *,
    allow_blank: bool,
) -> str:
    if not isinstance(value, str) or len(value) > maximum or "\x00" in value:
        raise OllamaChatCaptureError(f"{label} is invalid")
    if not allow_blank and not value.strip():
        raise OllamaChatCaptureError(f"{label} must not be blank")
    return value


def _timestamp(value: object, label: str) -> datetime:
    if not isinstance(value, str):
        raise OllamaChatCaptureError(f"{label} must be text")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
        finite = math.isfinite(parsed.timestamp())
    except (ValueError, OverflowError, OSError) as exc:
        raise OllamaChatCaptureError(f"{label} is invalid") from exc
    if parsed.tzinfo is None or not finite:
        raise OllamaChatCaptureError(f"{label} must include a valid timezone")
    return parsed


__all__ = [
    "OllamaChatCaptureError",
    "OllamaChatCaptureFailure",
    "OllamaChatCaptureRequest",
    "OllamaChatCaptureResult",
    "OllamaChatCaptureService",
    "OllamaChatFinishReason",
]
