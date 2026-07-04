"""Offline source adapter for selected ChatGPT conversations.json history."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import cast

from doll.generic_import import GenericImportStager, GenericImportStageResult
from doll.portability import (
    AdapterResourceLimits,
    PortabilityContractError,
    SourceAdapterContract,
    SourceEnvironmentRecord,
)

_FORMAT_NAME = "chatgpt-conversations-json"
_FORMAT_VERSION = "observed-v1"
_SOURCE_ENVIRONMENT_CLASS = "cloud-ai-history-export"
_ADAPTER_ID = "chatgpt-conversations"
_ADAPTER_VERSION = "1.0.0"

_ROLE_TO_SOURCE_TYPE = {
    "user": "user-message",
    "assistant": "assistant-message",
    "system": "system-message",
    "tool": "tool-result",
}
_CONVERSATION_KEYS = frozenset(
    {
        "id",
        "conversation_id",
        "title",
        "create_time",
        "update_time",
        "mapping",
        "current_node",
        "conversation_template_id",
        "gizmo_id",
        "is_archived",
        "is_starred",
        "safe_urls",
        "blocked_urls",
        "default_model_slug",
        "conversation_origin",
        "voice",
        "async_status",
        "disabled_tool_ids",
        "is_do_not_remember",
        "project_id",
        "sugar_item_id",
        "sugar_item_visible",
        "context_scopes",
        "moderation_results",
        "plugin_ids",
    }
)
_NODE_KEYS = frozenset({"id", "message", "parent", "children"})
_MESSAGE_KEYS = frozenset(
    {
        "id",
        "author",
        "create_time",
        "update_time",
        "content",
        "status",
        "end_turn",
        "weight",
        "metadata",
        "recipient",
        "channel",
    }
)
_AUTHOR_KEYS = frozenset({"role", "name", "metadata"})
_CONTENT_KEYS = frozenset(
    {
        "content_type",
        "parts",
        "text",
        "result",
        "language",
        "response_format_name",
    }
)
_IDENTIFIER_PATTERN = re.compile(r"^[^\x00-\x1f\x7f]{1,256}$")
_MAX_TEXT_LENGTH = 1_048_576
_MAX_SELECTION_COUNT = 1_000


class ChatGPTExportImportError(PortabilityContractError):
    """Raised when ChatGPT conversation export bytes cannot be staged safely."""


@dataclass(frozen=True, slots=True)
class ChatGPTExportInventory:
    """Content-free inventory for one supplied conversations.json file."""

    source_root_hash: str
    format_version: str
    conversation_count: int
    selected_conversation_count: int
    node_count: int
    message_count: int
    selected_message_count: int
    supported_message_count: int
    unsupported_message_count: int
    attachment_reference_count: int
    malformed_object_count: int
    unknown_field_count: int
    source_object_count: int

    def canonical_summary(self) -> dict[str, object]:
        return {
            "source_root_hash": self.source_root_hash,
            "format_version": self.format_version,
            "conversation_count": self.conversation_count,
            "selected_conversation_count": self.selected_conversation_count,
            "node_count": self.node_count,
            "message_count": self.message_count,
            "selected_message_count": self.selected_message_count,
            "supported_message_count": self.supported_message_count,
            "unsupported_message_count": self.unsupported_message_count,
            "attachment_reference_count": self.attachment_reference_count,
            "malformed_object_count": self.malformed_object_count,
            "unknown_field_count": self.unknown_field_count,
            "source_object_count": self.source_object_count,
        }


@dataclass(frozen=True, slots=True)
class ChatGPTExportStageResult:
    """Source-specific inventory plus the accepted generic staging result."""

    source_environment: SourceEnvironmentRecord
    inventory: ChatGPTExportInventory
    stage_result: GenericImportStageResult

    def canonical_summary(self) -> dict[str, object]:
        return {
            "source_environment": self.source_environment.canonical_metadata(),
            "inventory": self.inventory.canonical_summary(),
            "stage_result": self.stage_result.canonical_summary(),
        }


@dataclass(frozen=True, slots=True)
class _ConversationCounts:
    node_count: int = 0
    message_count: int = 0
    selected_message_count: int = 0
    supported_message_count: int = 0
    unsupported_message_count: int = 0
    attachment_reference_count: int = 0
    malformed_object_count: int = 0
    unknown_field_count: int = 0

    def add(self, other: _ConversationCounts) -> _ConversationCounts:
        return _ConversationCounts(
            node_count=self.node_count + other.node_count,
            message_count=self.message_count + other.message_count,
            selected_message_count=self.selected_message_count + other.selected_message_count,
            supported_message_count=self.supported_message_count + other.supported_message_count,
            unsupported_message_count=(
                self.unsupported_message_count + other.unsupported_message_count
            ),
            attachment_reference_count=(
                self.attachment_reference_count + other.attachment_reference_count
            ),
            malformed_object_count=self.malformed_object_count + other.malformed_object_count,
            unknown_field_count=self.unknown_field_count + other.unknown_field_count,
        )


def chatgpt_export_source_contract(
    *,
    max_input_bytes: int = 16 * 1024 * 1024,
    max_object_count: int = 100_000,
    max_attachment_bytes: int = 64 * 1024,
    max_nesting_depth: int = 96,
) -> SourceAdapterContract:
    """Return the fixed offline source contract for one conversations.json file."""

    return SourceAdapterContract(
        adapter_id=_ADAPTER_ID,
        adapter_version=_ADAPTER_VERSION,
        source_environment_class=_SOURCE_ENVIRONMENT_CLASS,
        supported_source_versions=(_FORMAT_VERSION,),
        supported_event_types=(
            "conversation",
            "user-message",
            "assistant-message",
            "system-message",
            "tool-result",
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
            "conflicting-duplicate",
            "cyclic-parent-relationship",
            "malformed-object",
            "missing-parent-dependency",
            "unsupported-source-type",
        ),
    )


@dataclass(frozen=True, slots=True)
class ChatGPTExportSourceAdapter:
    """Parse one caller-provided ChatGPT conversations.json file without I/O."""

    contract: SourceAdapterContract = field(default_factory=chatgpt_export_source_contract)

    def __post_init__(self) -> None:
        if (
            self.contract.adapter_id != _ADAPTER_ID
            or self.contract.adapter_version != _ADAPTER_VERSION
            or self.contract.source_environment_class != _SOURCE_ENVIRONMENT_CLASS
            or self.contract.network_behavior != "none"
        ):
            raise ChatGPTExportImportError("ChatGPT export adapter contract is incompatible")

    def stage(
        self,
        source_bytes: bytes,
        *,
        source_environment_id: str,
        selected_conversation_ids: tuple[str, ...],
        import_batch_id: str,
        started_at: str,
        observed_at: str,
    ) -> ChatGPTExportStageResult:
        """Inventory all conversations and stage only an explicit selected set."""

        if not isinstance(source_bytes, bytes):
            raise ChatGPTExportImportError("source bytes must be bytes")
        if not source_bytes:
            raise ChatGPTExportImportError("source input must not be empty")
        if len(source_bytes) > self.contract.resource_limits.max_input_bytes:
            raise ChatGPTExportImportError("source input exceeds adapter byte limit")
        selected = _selected_ids(selected_conversation_ids)
        root = _load_root(source_bytes)
        try:
            depth = _json_depth(root)
        except RecursionError as exc:
            raise ChatGPTExportImportError("source nesting exceeds safe parser depth") from exc
        if depth > self.contract.resource_limits.max_nesting_depth:
            raise ChatGPTExportImportError("source nesting exceeds adapter limit")
        if len(root) > self.contract.resource_limits.max_object_count:
            raise ChatGPTExportImportError("conversation count exceeds adapter object limit")

        source_root_hash = hashlib.sha256(source_bytes).hexdigest()
        objects: list[dict[str, object]] = []
        counts = _ConversationCounts()
        found: set[str] = set()
        for index, raw_conversation in enumerate(root):
            conversation, conversation_id = _conversation_identity(raw_conversation, index)
            selected_here = conversation_id in selected
            if selected_here:
                found.add(conversation_id)
                mapped, item_counts = self._map_conversation(conversation, conversation_id, index)
                objects.extend(mapped)
            else:
                item_counts = _inventory_conversation(conversation)
            counts = counts.add(item_counts)

        missing = sorted(selected - found)
        if missing:
            raise ChatGPTExportImportError("one or more selected conversation ids were not found")
        if len(objects) > self.contract.resource_limits.max_object_count:
            raise ChatGPTExportImportError("source object count exceeds adapter limit")

        source_environment = SourceEnvironmentRecord(
            environment_id=source_environment_id,
            environment_class=_SOURCE_ENVIRONMENT_CLASS,
            provider_id="openai",
            application_id="chatgpt",
            interface_id="chatgpt.export",
            runtime_id=None,
            export_format=_FORMAT_NAME,
            export_version=_FORMAT_VERSION,
            observed_at=_timestamp(observed_at, "observed at"),
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
                "source_environment_id": source_environment_id,
                "objects": objects,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        staging_contract = replace(
            self.contract,
            supported_source_versions=("1",),
        )
        staged = GenericImportStager(staging_contract, intermediate_environment).stage(
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
        inventory = ChatGPTExportInventory(
            source_root_hash=source_root_hash,
            format_version=_FORMAT_VERSION,
            conversation_count=len(root),
            selected_conversation_count=len(selected),
            node_count=counts.node_count,
            message_count=counts.message_count,
            selected_message_count=counts.selected_message_count,
            supported_message_count=counts.supported_message_count,
            unsupported_message_count=counts.unsupported_message_count,
            attachment_reference_count=counts.attachment_reference_count,
            malformed_object_count=counts.malformed_object_count,
            unknown_field_count=counts.unknown_field_count,
            source_object_count=len(objects),
        )
        return ChatGPTExportStageResult(
            source_environment=source_environment,
            inventory=inventory,
            stage_result=native_stage,
        )

    def _map_conversation(
        self,
        conversation: dict[str, object],
        native_conversation_id: str,
        conversation_index: int,
    ) -> tuple[list[dict[str, object]], _ConversationCounts]:
        conversation_id = f"conversation:{native_conversation_id}"
        title = _optional_text(conversation.get("title"), "conversation title", maximum=4096)
        created_at = _optional_timestamp(
            conversation.get("create_time"), "conversation create time"
        )
        mapping_value = conversation.get("mapping")
        mapping = _object(mapping_value, "conversation mapping")
        unknown_conversation = sorted(set(conversation) - _CONVERSATION_KEYS)

        objects: list[dict[str, object]] = [
            _generic_object(
                conversation_id,
                "conversation",
                {
                    "title": title,
                    "occurred_at": created_at,
                    "source_conversation_id": native_conversation_id,
                    "source_current_node": _optional_identifier(
                        conversation.get("current_node"), "current node"
                    ),
                },
            )
        ]
        counts = _ConversationCounts(
            node_count=len(mapping),
            unknown_field_count=len(unknown_conversation),
        )
        if unknown_conversation:
            objects.append(
                _unsupported_object(
                    f"unknown-fields:{native_conversation_id}:conversation",
                    "conversation",
                    unknown_conversation,
                    parent=conversation_id,
                )
            )

        message_nodes = {
            node_id
            for node_id, raw_node in mapping.items()
            if isinstance(node_id, str)
            and isinstance(raw_node, dict)
            and isinstance(raw_node.get("message"), dict)
        }
        for node_index, node_id in enumerate(sorted(mapping)):
            if not isinstance(node_id, str):
                raise ChatGPTExportImportError("conversation mapping key must be text")
            raw_node = mapping[node_id]
            node = _object(raw_node, f"conversation node {node_index}")
            message = node.get("message")
            if message is None:
                counts = counts.add(
                    _ConversationCounts(
                        malformed_object_count=(0 if frozenset(node) <= _NODE_KEYS else 1),
                        unknown_field_count=len(set(node) - _NODE_KEYS),
                    )
                )
                if set(node) - _NODE_KEYS:
                    objects.append(
                        _unsupported_object(
                            f"unknown-fields:{native_conversation_id}:{node_id}:node",
                            "node",
                            sorted(set(node) - _NODE_KEYS),
                            parent=conversation_id,
                        )
                    )
                continue
            try:
                parent = _nearest_message_parent(
                    mapping,
                    node,
                    native_conversation_id=native_conversation_id,
                    conversation_id=conversation_id,
                    message_nodes=message_nodes,
                )
                mapped, item_counts = self._map_message(
                    message,
                    node,
                    native_conversation_id=native_conversation_id,
                    conversation_id=conversation_id,
                    node_id=node_id,
                    node_index=node_index,
                    parent=parent,
                )
            except ChatGPTExportImportError as exc:
                mapped = [
                    _generic_object(
                        f"malformed:{native_conversation_id}:{node_id}",
                        "chatgpt-malformed-message",
                        {
                            "source_node_id": node_id,
                            "reason": str(exc),
                        },
                        parents=[conversation_id],
                    )
                ]
                item_counts = _ConversationCounts(
                    message_count=1,
                    selected_message_count=1,
                    unsupported_message_count=1,
                    malformed_object_count=1,
                )
            objects.extend(mapped)
            counts = counts.add(item_counts)
        return objects, counts

    def _map_message(
        self,
        raw_message: object,
        node: dict[str, object],
        *,
        native_conversation_id: str,
        conversation_id: str,
        node_id: str,
        node_index: int,
        parent: str,
    ) -> tuple[list[dict[str, object]], _ConversationCounts]:
        message = _object(raw_message, f"message node {node_index}")
        message_id = f"message:{native_conversation_id}:{_identifier(node_id, 'node id')}"
        native_message_id = _optional_identifier(message.get("id"), "message id")
        author = _object(message.get("author"), "message author")
        role = _text(author.get("role"), "message role", maximum=64)
        content = _object(message.get("content"), "message content")
        content_type = _text(content.get("content_type"), "content type", maximum=128)
        occurred_at = _optional_timestamp(message.get("create_time"), "message create time")
        unknown_fields = (
            sorted(set(node) - _NODE_KEYS)
            + [f"message.{item}" for item in sorted(set(message) - _MESSAGE_KEYS)]
            + [f"author.{item}" for item in sorted(set(author) - _AUTHOR_KEYS)]
            + [f"content.{item}" for item in sorted(set(content) - _CONTENT_KEYS)]
        )
        attachment_count = _attachment_reference_count(content) + _attachment_reference_count(
            message.get("metadata")
        )
        source_type = _ROLE_TO_SOURCE_TYPE.get(role)
        objects: list[dict[str, object]] = []
        supported = source_type is not None and content_type == "text"
        if supported:
            parts = _list(content.get("parts"), "message content parts")
            if not all(isinstance(part, str) for part in parts):
                supported = False
            else:
                text = "\n".join(cast(list[str], parts))
                if len(text) > _MAX_TEXT_LENGTH:
                    raise ChatGPTExportImportError("message text exceeds adapter limit")
                objects.append(
                    _generic_object(
                        message_id,
                        cast(str, source_type),
                        {
                            "text": text,
                            "occurred_at": occurred_at,
                            "sequence_hint": node_index + 1,
                            "source_role": role,
                            "source_author_name": _optional_text(
                                author.get("name"), "author name", maximum=256
                            ),
                            "source_message_id": native_message_id,
                            "source_node_id": node_id,
                            "source_status": _optional_text(
                                message.get("status"), "message status", maximum=128
                            ),
                            "source_model": _optional_text(
                                _metadata_value(message.get("metadata"), "model_slug"),
                                "source model",
                                maximum=256,
                            ),
                            "source_content_type": content_type,
                        },
                        parents=[parent],
                    )
                )
        if not supported:
            objects.append(
                _generic_object(
                    f"unsupported:{native_conversation_id}:{node_id}",
                    "chatgpt-unsupported-message",
                    {
                        "occurred_at": occurred_at,
                        "source_role": role,
                        "source_node_id": node_id,
                        "source_message_id": native_message_id,
                        "source_content_type": content_type,
                        "attachment_reference_count": attachment_count,
                    },
                    parents=[parent],
                )
            )
        if attachment_count:
            objects.append(
                _generic_object(
                    f"attachment-reference:{native_conversation_id}:{node_id}",
                    "chatgpt-attachment-reference",
                    {
                        "source_node_id": node_id,
                        "attachment_reference_count": attachment_count,
                    },
                    parents=[message_id if supported else conversation_id],
                )
            )
        if unknown_fields:
            objects.append(
                _unsupported_object(
                    f"unknown-fields:{native_conversation_id}:{node_id}:message",
                    "message",
                    unknown_fields,
                    parent=message_id if supported else conversation_id,
                )
            )
        return objects, _ConversationCounts(
            message_count=1,
            selected_message_count=1,
            supported_message_count=1 if supported else 0,
            unsupported_message_count=0 if supported else 1,
            attachment_reference_count=attachment_count,
            malformed_object_count=0,
            unknown_field_count=len(unknown_fields),
        )


def _inventory_conversation(conversation: dict[str, object]) -> _ConversationCounts:
    mapping = _object(conversation.get("mapping"), "conversation mapping")
    message_count = 0
    attachment_count = 0
    malformed = 0
    unknown = len(set(conversation) - _CONVERSATION_KEYS)
    for raw_node in mapping.values():
        if not isinstance(raw_node, dict):
            malformed += 1
            continue
        unknown += len(set(raw_node) - _NODE_KEYS)
        raw_message = raw_node.get("message")
        if raw_message is None:
            continue
        if not isinstance(raw_message, dict):
            malformed += 1
            continue
        message_count += 1
        unknown += len(set(raw_message) - _MESSAGE_KEYS)
        raw_author = raw_message.get("author")
        if isinstance(raw_author, dict):
            unknown += len(set(raw_author) - _AUTHOR_KEYS)
        else:
            malformed += 1
        raw_content = raw_message.get("content")
        if isinstance(raw_content, dict):
            unknown += len(set(raw_content) - _CONTENT_KEYS)
            attachment_count += _attachment_reference_count(raw_content)
        else:
            malformed += 1
        attachment_count += _attachment_reference_count(raw_message.get("metadata"))
    return _ConversationCounts(
        node_count=len(mapping),
        message_count=message_count,
        attachment_reference_count=attachment_count,
        malformed_object_count=malformed,
        unknown_field_count=unknown,
    )


def _conversation_identity(
    raw_conversation: object,
    index: int,
) -> tuple[dict[str, object], str]:
    conversation = _object(raw_conversation, f"conversation {index}")
    first = conversation.get("id")
    second = conversation.get("conversation_id")
    if first is None and second is None:
        raise ChatGPTExportImportError("conversation id is missing")
    if first is not None and second is not None and first != second:
        raise ChatGPTExportImportError("conversation identifiers conflict")
    return conversation, _identifier(first if first is not None else second, "conversation id")


def _nearest_message_parent(
    mapping: dict[str, object],
    node: dict[str, object],
    *,
    native_conversation_id: str,
    conversation_id: str,
    message_nodes: set[str],
) -> str:
    current = node.get("parent")
    visited: set[str] = set()
    while current is not None:
        parent_id = _identifier(current, "parent node id")
        if parent_id in visited:
            return f"message:{native_conversation_id}:{parent_id}"
        visited.add(parent_id)
        if parent_id in message_nodes:
            return f"message:{native_conversation_id}:{parent_id}"
        raw_parent = mapping.get(parent_id)
        if raw_parent is None:
            return f"message:{native_conversation_id}:{parent_id}"
        parent = _object(raw_parent, "parent node")
        current = parent.get("parent")
    return conversation_id


def _unsupported_object(
    source_object_id: str,
    scope: str,
    field_names: list[str],
    *,
    parent: str,
) -> dict[str, object]:
    return _generic_object(
        source_object_id,
        "chatgpt-unknown-provider-fields",
        {
            "scope": scope,
            "field_names": field_names,
            "field_count": len(field_names),
        },
        parents=[parent],
    )


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


def _selected_ids(value: tuple[str, ...]) -> set[str]:
    if not isinstance(value, tuple) or not value or len(value) > _MAX_SELECTION_COUNT:
        raise ChatGPTExportImportError("selected conversation ids are invalid")
    selected = {_identifier(item, "selected conversation id") for item in value}
    if len(selected) != len(value):
        raise ChatGPTExportImportError("selected conversation ids contain duplicates")
    return selected


def _load_root(source_bytes: bytes) -> list[object]:
    try:
        text = source_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ChatGPTExportImportError("source input is not valid UTF-8") from exc
    try:
        value = json.loads(
            text,
            object_pairs_hook=_pairs_without_duplicates,
            parse_constant=_reject_json_constant,
        )
    except (json.JSONDecodeError, ChatGPTExportImportError) as exc:
        raise ChatGPTExportImportError("source input is not valid JSON") from exc
    return _list(value, "source root")


def _pairs_without_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ChatGPTExportImportError("source JSON contains a duplicate object key")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> object:
    raise ChatGPTExportImportError(f"source JSON constant {value!r} is unsupported")


def _json_depth(value: object) -> int:
    if isinstance(value, dict):
        return 1 + max((_json_depth(item) for item in value.values()), default=0)
    if isinstance(value, list):
        return 1 + max((_json_depth(item) for item in value), default=0)
    return 1


def _object(value: object, name: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ChatGPTExportImportError(f"{name} must be an object")
    return cast(dict[str, object], value)


def _list(value: object, name: str) -> list[object]:
    if not isinstance(value, list):
        raise ChatGPTExportImportError(f"{name} must be a list")
    return value


def _identifier(value: object, name: str) -> str:
    text = _text(value, name, maximum=256)
    if not _IDENTIFIER_PATTERN.fullmatch(text):
        raise ChatGPTExportImportError(f"{name} is invalid")
    return text


def _optional_identifier(value: object, name: str) -> str | None:
    if value is None:
        return None
    return _identifier(value, name)


def _text(value: object, name: str, *, maximum: int) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise ChatGPTExportImportError(f"{name} must be bounded non-empty text")
    return value


def _optional_text(value: object, name: str, *, maximum: int) -> str | None:
    if value is None:
        return None
    return _text(value, name, maximum=maximum)


def _timestamp(value: object, name: str) -> str:
    result = _optional_timestamp(value, name)
    if result is None:
        raise ChatGPTExportImportError(f"{name} is required")
    return result


def _optional_timestamp(value: object, name: str) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ChatGPTExportImportError(f"{name} is invalid")
    if isinstance(value, (int, float)):
        numeric = float(value)
        if not math.isfinite(numeric) or numeric < 0:
            raise ChatGPTExportImportError(f"{name} is invalid")
        try:
            return datetime.fromtimestamp(numeric, tz=UTC).isoformat().replace("+00:00", "Z")
        except (OverflowError, OSError, ValueError) as exc:
            raise ChatGPTExportImportError(f"{name} is invalid") from exc
    if not isinstance(value, str) or not value:
        raise ChatGPTExportImportError(f"{name} is invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ChatGPTExportImportError(f"{name} is invalid") from exc
    if parsed.tzinfo is None:
        raise ChatGPTExportImportError(f"{name} must include a timezone")
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _metadata_value(value: object, key: str) -> object:
    if not isinstance(value, dict) or not all(isinstance(item, str) for item in value):
        return None
    return cast(dict[str, object], value).get(key)


def _attachment_reference_count(value: object) -> int:
    if isinstance(value, dict):
        mapping = cast(dict[object, object], value)
        count = sum(
            1
            for key in mapping
            if key in {"asset_pointer", "file_id", "attachment_id", "image_asset_pointer"}
        )
        return count + sum(_attachment_reference_count(item) for item in mapping.values())
    if isinstance(value, list):
        return sum(_attachment_reference_count(item) for item in value)
    return 0
