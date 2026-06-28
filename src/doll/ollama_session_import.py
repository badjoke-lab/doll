"""Offline source adapter for client-retained Ollama API chat sessions."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import cast

from doll.generic_import import GenericImportStageResult, GenericImportStager
from doll.portability import (
    AdapterResourceLimits,
    PortabilityContractError,
    SourceAdapterContract,
    SourceEnvironmentRecord,
)

_FORMAT_NAME = "ollama-api-chat-session"
_FORMAT_VERSION = "1"
_SOURCE_ENVIRONMENT_CLASS = "local-ai-runtime-session"
_ADAPTER_ID = "ollama-api-session"
_ADAPTER_VERSION = "1.0.0"

_ROOT_KEYS = frozenset(
    {
        "format",
        "format_version",
        "source_environment_id",
        "runtime_version",
        "exported_at",
        "conversations",
    }
)
_CONVERSATION_KEYS = frozenset({"conversation_id", "title", "created_at", "messages"})
_MESSAGE_KEYS = frozenset(
    {
        "message_id",
        "role",
        "content",
        "created_at",
        "parent_message_ids",
        "model",
        "attachments",
        "tool_calls",
    }
)
_ATTACHMENT_KEYS = frozenset(
    {"attachment_id", "name", "media_type", "size_bytes", "sha256"}
)
_TOOL_CALL_KEYS = frozenset({"tool_call_id", "name", "arguments"})
_ROLE_TO_SOURCE_TYPE = {
    "user": "user-message",
    "assistant": "assistant-message",
    "system": "system-message",
    "tool": "tool-result",
}
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_MAX_IDENTIFIER_LENGTH = 256
_MAX_TEXT_LENGTH = 1_048_576


class OllamaSessionImportError(PortabilityContractError):
    """Raised when an Ollama session bundle cannot be parsed safely."""


@dataclass(frozen=True, slots=True)
class OllamaSessionInventory:
    """Content-free inventory for one caller-retained Ollama session bundle."""

    source_root_hash: str
    format_version: str
    runtime_version: str | None
    conversation_count: int
    message_count: int
    attachment_count: int
    tool_call_count: int
    source_object_count: int

    def canonical_summary(self) -> dict[str, object]:
        return {
            "source_root_hash": self.source_root_hash,
            "format_version": self.format_version,
            "runtime_version": self.runtime_version,
            "conversation_count": self.conversation_count,
            "message_count": self.message_count,
            "attachment_count": self.attachment_count,
            "tool_call_count": self.tool_call_count,
            "source_object_count": self.source_object_count,
        }


@dataclass(frozen=True, slots=True)
class OllamaSessionStageResult:
    """Source-specific inventory plus the accepted generic staging result."""

    source_environment: SourceEnvironmentRecord
    inventory: OllamaSessionInventory
    stage_result: GenericImportStageResult

    def canonical_summary(self) -> dict[str, object]:
        return {
            "source_environment": self.source_environment.canonical_metadata(),
            "inventory": self.inventory.canonical_summary(),
            "stage_result": self.stage_result.canonical_summary(),
        }


def ollama_session_source_contract(
    *,
    max_input_bytes: int = 10 * 1024 * 1024,
    max_object_count: int = 20_000,
    max_attachment_bytes: int = 64 * 1024,
    max_nesting_depth: int = 64,
) -> SourceAdapterContract:
    """Return the fixed offline source contract for Ollama API session bundles."""

    return SourceAdapterContract(
        adapter_id=_ADAPTER_ID,
        adapter_version=_ADAPTER_VERSION,
        source_environment_class=_SOURCE_ENVIRONMENT_CLASS,
        supported_source_versions=(_FORMAT_VERSION,),
        supported_event_types=(
            "user-message",
            "assistant-message",
            "system-message",
            "tool-result",
            "tool-request",
        ),
        attachment_behavior="metadata_only",
        branch_behavior="preserve",
        resource_limits=AdapterResourceLimits(
            max_input_bytes=max_input_bytes,
            max_object_count=max_object_count,
            max_attachment_bytes=max_attachment_bytes,
            max_nesting_depth=max_nesting_depth,
        ),
        network_behavior="none",
        loss_categories=(
            "attachment-metadata-only",
            "attachment-byte-limit",
            "conflicting-duplicate",
            "cyclic-parent-relationship",
            "malformed-object",
            "missing-parent-dependency",
            "unsupported-source-type",
        ),
    )


@dataclass(frozen=True, slots=True)
class OllamaSessionSourceAdapter:
    """Parse caller-provided Ollama API session JSON without I/O or execution."""

    contract: SourceAdapterContract = field(default_factory=ollama_session_source_contract)

    def __post_init__(self) -> None:
        if (
            self.contract.adapter_id != _ADAPTER_ID
            or self.contract.adapter_version != _ADAPTER_VERSION
            or self.contract.source_environment_class != _SOURCE_ENVIRONMENT_CLASS
            or self.contract.network_behavior != "none"
        ):
            raise OllamaSessionImportError("Ollama session adapter contract is incompatible")

    def stage(
        self,
        source_bytes: bytes,
        *,
        import_batch_id: str,
        started_at: str,
    ) -> OllamaSessionStageResult:
        """Inventory and stage one exact source bundle without writing Doll State."""

        if not isinstance(source_bytes, bytes):
            raise OllamaSessionImportError("source bytes must be bytes")
        if not source_bytes:
            raise OllamaSessionImportError("source input must not be empty")
        if len(source_bytes) > self.contract.resource_limits.max_input_bytes:
            raise OllamaSessionImportError("source input exceeds adapter byte limit")

        source_root_hash = hashlib.sha256(source_bytes).hexdigest()
        root = _load_root(source_bytes)
        _require_exact_keys(root, _ROOT_KEYS, "source root")
        if root["format"] != _FORMAT_NAME:
            raise OllamaSessionImportError("source format is unsupported")
        if root["format_version"] not in self.contract.supported_source_versions:
            raise OllamaSessionImportError("source format version is unsupported")

        environment_id = _text(root["source_environment_id"], "source environment id")
        runtime_version = _optional_text(root["runtime_version"], "runtime version")
        exported_at = _timestamp(root["exported_at"], "exported at")
        conversations = _list(root["conversations"], "conversations")

        objects: list[object] = []
        message_count = 0
        attachment_count = 0
        tool_call_count = 0
        for conversation_index, raw_conversation in enumerate(conversations):
            mapped, counts = self._map_conversation(
                raw_conversation,
                conversation_index,
                runtime_version=runtime_version,
            )
            objects.extend(mapped)
            message_count += counts[0]
            attachment_count += counts[1]
            tool_call_count += counts[2]

        if len(objects) > self.contract.resource_limits.max_object_count:
            raise OllamaSessionImportError("source object count exceeds adapter limit")

        source_environment = SourceEnvironmentRecord(
            environment_id=environment_id,
            environment_class=_SOURCE_ENVIRONMENT_CLASS,
            provider_id=None,
            application_id="ollama",
            interface_id="ollama.api",
            runtime_id="ollama.local",
            export_format=_FORMAT_NAME,
            export_version=_FORMAT_VERSION,
            observed_at=exported_at,
        )
        intermediate_environment = replace(
            source_environment,
            export_format=None,
            export_version=None,
        )
        generic_bytes = json.dumps(
            {
                "format": "doll-generic-import",
                "format_version": "1",
                "source_environment_id": environment_id,
                "objects": objects,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        staged = GenericImportStager(self.contract, intermediate_environment).stage(
            generic_bytes,
            source_format="json",
            import_batch_id=import_batch_id,
            started_at=started_at,
        )
        native_batch = replace(staged.import_batch, source_root_hash=source_root_hash)
        native_stage = replace(
            staged,
            source_root_hash=source_root_hash,
            import_batch=native_batch,
        )
        inventory = OllamaSessionInventory(
            source_root_hash=source_root_hash,
            format_version=_FORMAT_VERSION,
            runtime_version=runtime_version,
            conversation_count=len(conversations),
            message_count=message_count,
            attachment_count=attachment_count,
            tool_call_count=tool_call_count,
            source_object_count=len(objects),
        )
        return OllamaSessionStageResult(
            source_environment=source_environment,
            inventory=inventory,
            stage_result=native_stage,
        )

    def _map_conversation(
        self,
        raw_conversation: object,
        conversation_index: int,
        *,
        runtime_version: str | None,
    ) -> tuple[list[object], tuple[int, int, int]]:
        conversation = _object(raw_conversation, f"conversation {conversation_index}")
        _require_exact_keys(conversation, _CONVERSATION_KEYS, "conversation")
        native_conversation_id = _identifier(
            conversation["conversation_id"], "conversation id"
        )
        conversation_id = f"conversation:{native_conversation_id}"
        title = _optional_text(conversation["title"], "conversation title")
        created_at = _optional_timestamp(conversation["created_at"], "conversation created at")
        messages = _list(conversation["messages"], "conversation messages")

        objects: list[object] = [
            _generic_object(
                conversation_id,
                "conversation",
                {
                    "title": title,
                    "occurred_at": created_at,
                    "source_conversation_id": native_conversation_id,
                    "source_runtime_version": runtime_version,
                },
            )
        ]
        attachment_count = 0
        tool_call_count = 0
        for message_index, raw_message in enumerate(messages):
            mapped, nested_counts = self._map_message(
                raw_message,
                native_conversation_id=native_conversation_id,
                conversation_id=conversation_id,
                message_index=message_index,
            )
            objects.extend(mapped)
            attachment_count += nested_counts[0]
            tool_call_count += nested_counts[1]
        return objects, (len(messages), attachment_count, tool_call_count)

    def _map_message(
        self,
        raw_message: object,
        *,
        native_conversation_id: str,
        conversation_id: str,
        message_index: int,
    ) -> tuple[list[object], tuple[int, int]]:
        message = _object(raw_message, f"message {message_index}")
        _require_exact_keys(message, _MESSAGE_KEYS, "message")
        native_message_id = _identifier(message["message_id"], "message id")
        message_id = f"message:{native_conversation_id}:{native_message_id}"
        role = _text(message["role"], "message role")
        content = _text(message["content"], "message content", allow_empty=True)
        created_at = _optional_timestamp(message["created_at"], "message created at")
        model = _optional_text(message["model"], "message model")
        parent_ids = tuple(
            _identifier(item, "parent message id")
            for item in _list(message["parent_message_ids"], "parent message ids")
        )
        parents = (
            [f"message:{native_conversation_id}:{parent_id}" for parent_id in parent_ids]
            if parent_ids
            else [conversation_id]
        )
        source_type = _ROLE_TO_SOURCE_TYPE.get(role, "ollama-unsupported-role")
        objects: list[object] = [
            _generic_object(
                message_id,
                source_type,
                {
                    "text": content,
                    "occurred_at": created_at,
                    "sequence_hint": message_index + 1,
                    "source_role": role,
                    "source_model": model,
                    "source_message_id": native_message_id,
                },
                parents=parents,
            )
        ]

        tool_calls = _list(message["tool_calls"], "tool calls")
        for tool_index, raw_tool_call in enumerate(tool_calls):
            tool_call = _object(raw_tool_call, f"tool call {tool_index}")
            _require_exact_keys(tool_call, _TOOL_CALL_KEYS, "tool call")
            native_tool_id = _identifier(tool_call["tool_call_id"], "tool call id")
            tool_id = (
                f"tool-call:{native_conversation_id}:{native_message_id}:{native_tool_id}"
            )
            name = _text(tool_call["name"], "tool call name")
            arguments = _object(tool_call["arguments"], "tool call arguments")
            objects.append(
                _generic_object(
                    tool_id,
                    "tool-request",
                    {
                        "name": name,
                        "arguments": arguments,
                        "occurred_at": created_at,
                        "source_tool_call_id": native_tool_id,
                    },
                    parents=[message_id],
                )
            )

        attachments = _list(message["attachments"], "attachments")
        for attachment_index, raw_attachment in enumerate(attachments):
            attachment = _object(raw_attachment, f"attachment {attachment_index}")
            _require_exact_keys(attachment, _ATTACHMENT_KEYS, "attachment")
            native_attachment_id = _identifier(
                attachment["attachment_id"], "attachment id"
            )
            attachment_id = (
                f"attachment:{native_conversation_id}:{native_message_id}:"
                f"{native_attachment_id}"
            )
            name = _text(attachment["name"], "attachment name")
            media_type = _optional_text(attachment["media_type"], "attachment media type")
            size_bytes = _nonnegative_int(attachment["size_bytes"], "attachment size")
            sha256 = _optional_sha256(attachment["sha256"], "attachment SHA-256")
            objects.append(
                _generic_object(
                    attachment_id,
                    "attachment",
                    {
                        "name": name,
                        "media_type": media_type,
                        "size_bytes": size_bytes,
                        "sha256": sha256,
                        "occurred_at": created_at,
                        "source_attachment_id": native_attachment_id,
                    },
                    parents=[message_id],
                )
            )
        return objects, (len(attachments), len(tool_calls))


def _load_root(source_bytes: bytes) -> dict[str, object]:
    try:
        text = source_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise OllamaSessionImportError("source input is not valid UTF-8") from exc
    try:
        value = json.loads(
            text,
            object_pairs_hook=_pairs_without_duplicates,
            parse_constant=_reject_json_constant,
        )
    except (json.JSONDecodeError, OllamaSessionImportError) as exc:
        raise OllamaSessionImportError("source input is not valid canonical JSON") from exc
    return _object(value, "source root")


def _pairs_without_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise OllamaSessionImportError("source JSON contains a duplicate object key")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> object:
    raise OllamaSessionImportError(f"source JSON constant {value!r} is unsupported")


def _require_exact_keys(
    value: dict[str, object],
    expected: frozenset[str],
    name: str,
) -> None:
    if frozenset(value) != expected:
        raise OllamaSessionImportError(f"{name} shape is invalid")


def _generic_object(
    source_object_id: str,
    source_type: str,
    payload: dict[str, object],
    *,
    parents: list[str] | None = None,
) -> dict[str, object]:
    return {
        "source_object_id": source_object_id,
        "source_type": source_type,
        "parent_source_object_ids": parents or [],
        "payload": payload,
    }


def _object(value: object, name: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise OllamaSessionImportError(f"{name} must be an object")
    return cast(dict[str, object], value)


def _list(value: object, name: str) -> list[object]:
    if not isinstance(value, list):
        raise OllamaSessionImportError(f"{name} must be a list")
    return cast(list[object], value)


def _text(
    value: object,
    name: str,
    *,
    allow_empty: bool = False,
) -> str:
    if not isinstance(value, str):
        raise OllamaSessionImportError(f"{name} must be text")
    if (not allow_empty and not value) or len(value) > _MAX_TEXT_LENGTH:
        raise OllamaSessionImportError(f"{name} is outside the supported length")
    return value


def _optional_text(value: object, name: str) -> str | None:
    if value is None:
        return None
    return _text(value, name)


def _identifier(value: object, name: str) -> str:
    text = _text(value, name)
    if len(text) > _MAX_IDENTIFIER_LENGTH or any(ord(character) < 32 for character in text):
        raise OllamaSessionImportError(f"{name} is invalid")
    return text


def _timestamp(value: object, name: str) -> str:
    text = _text(value, name)
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise OllamaSessionImportError(f"{name} is invalid") from exc
    if parsed.tzinfo is None:
        raise OllamaSessionImportError(f"{name} must include a timezone")
    return text


def _optional_timestamp(value: object, name: str) -> str | None:
    if value is None:
        return None
    return _timestamp(value, name)


def _nonnegative_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise OllamaSessionImportError(f"{name} must be a non-negative integer")
    return value


def _optional_sha256(value: object, name: str) -> str | None:
    if value is None:
        return None
    text = _text(value, name)
    if _SHA256_PATTERN.fullmatch(text) is None:
        raise OllamaSessionImportError(f"{name} is invalid")
    return text
