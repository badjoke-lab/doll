"""Public state repository contracts for doll."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import UUID

STATE_DATABASE_NAME = "doll-state.sqlite3"
CURRENT_SCHEMA_VERSION = 2

RecordStatus = Literal["active", "archived", "superseded", "deleted", "invalid"]
RecordProvenance = Literal[
    "user-created",
    "user-confirmed",
    "imported",
    "model-proposed",
    "system-generated",
    "migrated",
    "restored",
]
RecordSensitivity = Literal["public", "internal", "personal", "sensitive", "secret"]
ConversationEventKind = Literal[
    "user_message",
    "assistant_message",
    "system_context_snapshot",
    "model_runtime_change",
    "tool_request",
    "tool_result",
    "attachment_reference",
    "branch_creation",
    "edit_regeneration",
    "citation_reference",
    "error",
    "imported_unknown_event",
]
ConversationActorType = Literal[
    "user",
    "assistant",
    "system",
    "model",
    "runtime",
    "tool",
    "importer",
    "unknown",
]
ConversationOriginClass = Literal[
    "current_user_instruction",
    "external_content",
    "imported_data",
    "tool_result",
    "runtime_output",
    "model_proposal",
    "unknown",
]

_ALLOWED_STATUSES = frozenset(
    {"active", "archived", "superseded", "deleted", "invalid"}
)
_ALLOWED_PROVENANCE = frozenset(
    {
        "user-created",
        "user-confirmed",
        "imported",
        "model-proposed",
        "system-generated",
        "migrated",
        "restored",
    }
)
_ALLOWED_SENSITIVITY = frozenset(
    {"public", "internal", "personal", "sensitive", "secret"}
)
_ALLOWED_CONVERSATION_EVENT_KINDS = frozenset(
    {
        "user_message",
        "assistant_message",
        "system_context_snapshot",
        "model_runtime_change",
        "tool_request",
        "tool_result",
        "attachment_reference",
        "branch_creation",
        "edit_regeneration",
        "citation_reference",
        "error",
        "imported_unknown_event",
    }
)
_ALLOWED_CONVERSATION_ACTORS = frozenset(
    {
        "user",
        "assistant",
        "system",
        "model",
        "runtime",
        "tool",
        "importer",
        "unknown",
    }
)
_ALLOWED_CONVERSATION_ORIGINS = frozenset(
    {
        "current_user_instruction",
        "external_content",
        "imported_data",
        "tool_result",
        "runtime_output",
        "model_proposal",
        "unknown",
    }
)
_EXTENSION_KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,127}$")
_MAX_CONVERSATION_TITLE = 240
_MAX_CONVERSATION_IDENTIFIER = 1024
_MAX_CONVERSATION_CONTENT_REFERENCE = 2048
_MAX_CONVERSATION_PARENTS = 64
_MAX_CONVERSATION_EXTENSIONS = 64


class StateError(RuntimeError):
    """Base class for state repository failures."""


class StateExistsError(StateError):
    """Raised when a state database already exists."""


class StateNotInitializedError(StateError):
    """Raised when an initialized workspace has no state database."""


class StateCorruptError(StateError):
    """Raised when required state metadata is missing or inconsistent."""


class FutureSchemaVersionError(StateError):
    """Raised when the database schema is newer than this doll version supports."""


class MigrationError(StateError):
    """Raised when a schema migration fails and is rolled back."""


class ReadOnlyStateError(StateError):
    """Raised when a write is attempted through a read-only repository."""


class StaleRevisionError(StateError):
    """Raised when an update uses an outdated record revision."""


class StateRevisionMismatchError(StateError):
    """Raised when workspace and database revisions cannot be safely reconciled."""


class RecordValidationError(StateError):
    """Raised when a common record envelope field is invalid."""


class ConversationValidationError(RecordValidationError):
    """Raised when a canonical conversation contract is invalid."""


@dataclass(frozen=True, slots=True)
class Migration:
    """One deterministic schema transition."""

    migration_id: str
    from_version: int
    to_version: int
    statements: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class StateStatus:
    """Inspectable repository status with no identifying host data."""

    workspace_id: str
    schema_version: int
    state_revision: int
    record_count: int
    read_only: bool
    database_path: Path


@dataclass(frozen=True, slots=True)
class RecordEnvelope:
    """Physical foundation for authoritative doll records."""

    id: str
    record_type: str
    schema_version: int
    created_at: str
    updated_at: str
    revision: int
    status: RecordStatus
    provenance: RecordProvenance
    sensitivity: RecordSensitivity
    title: str | None
    metadata: dict[str, object]


@dataclass(frozen=True, slots=True)
class ConversationRecord:
    """Canonical conversation container independent of provider-native objects."""

    conversation_id: str
    title: str | None = None
    source_environment_id: str | None = None
    source_conversation_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "conversation_id",
            _validate_conversation_uuid(
                "conversation identifier",
                self.conversation_id,
            ),
        )
        object.__setattr__(
            self,
            "title",
            _validate_conversation_text(
                "conversation title",
                self.title,
                _MAX_CONVERSATION_TITLE,
            ),
        )
        object.__setattr__(
            self,
            "source_environment_id",
            _validate_conversation_text(
                "source environment identifier",
                self.source_environment_id,
                _MAX_CONVERSATION_IDENTIFIER,
            ),
        )
        object.__setattr__(
            self,
            "source_conversation_id",
            _validate_conversation_text(
                "source conversation identifier",
                self.source_conversation_id,
                _MAX_CONVERSATION_IDENTIFIER,
            ),
        )

    def canonical_metadata(self) -> dict[str, object]:
        return {
            "source_environment_id": self.source_environment_id,
            "source_conversation_id": self.source_conversation_id,
        }


@dataclass(frozen=True, slots=True)
class ConversationEventRecord:
    """Canonical event preserving graph relationships and source attribution."""

    event_id: str
    conversation_id: str
    event_kind: ConversationEventKind
    actor_type: ConversationActorType
    origin_class: ConversationOriginClass
    parent_event_ids: tuple[str, ...] = ()
    sequence_hint: int | None = None
    content_reference: str | None = None
    occurred_at: str | None = None
    source_event_kind: str | None = None
    source_environment_id: str | None = None
    source_object_id: str | None = None
    provider_id: str | None = None
    application_id: str | None = None
    interface_id: str | None = None
    model_manifest_id: str | None = None
    runtime_adapter_id: str | None = None
    operation_id: str | None = None
    extensions: dict[str, object] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "event_id",
            _validate_conversation_uuid("event identifier", self.event_id),
        )
        object.__setattr__(
            self,
            "conversation_id",
            _validate_conversation_uuid(
                "conversation identifier",
                self.conversation_id,
            ),
        )
        if self.event_kind not in _ALLOWED_CONVERSATION_EVENT_KINDS:
            raise ConversationValidationError("event kind is invalid")
        if self.actor_type not in _ALLOWED_CONVERSATION_ACTORS:
            raise ConversationValidationError("actor type is invalid")
        if self.origin_class not in _ALLOWED_CONVERSATION_ORIGINS:
            raise ConversationValidationError("origin class is invalid")

        parents = _validate_conversation_parents(
            self.event_id,
            self.parent_event_ids,
        )
        object.__setattr__(self, "parent_event_ids", parents)

        if self.sequence_hint is not None and (
            isinstance(self.sequence_hint, bool)
            or not isinstance(self.sequence_hint, int)
            or self.sequence_hint < 0
        ):
            raise ConversationValidationError(
                "sequence hint must be a non-negative integer"
            )

        object.__setattr__(
            self,
            "content_reference",
            _validate_conversation_text(
                "content reference",
                self.content_reference,
                _MAX_CONVERSATION_CONTENT_REFERENCE,
            ),
        )
        object.__setattr__(
            self,
            "occurred_at",
            _validate_conversation_timestamp(
                "occurred at",
                self.occurred_at,
            ),
        )

        for field_name in (
            "source_event_kind",
            "source_environment_id",
            "source_object_id",
            "provider_id",
            "application_id",
            "interface_id",
            "model_manifest_id",
            "runtime_adapter_id",
            "operation_id",
        ):
            object.__setattr__(
                self,
                field_name,
                _validate_conversation_text(
                    field_name.replace("_", " "),
                    getattr(self, field_name),
                    _MAX_CONVERSATION_IDENTIFIER,
                ),
            )

        if (
            self.event_kind == "imported_unknown_event"
            and self.source_event_kind is None
        ):
            raise ConversationValidationError(
                "imported unknown event requires a source event kind"
            )

        object.__setattr__(
            self,
            "extensions",
            _validate_conversation_extensions(self.extensions or {}),
        )

    def canonical_metadata(self) -> dict[str, object]:
        return {
            "conversation_id": self.conversation_id,
            "event_kind": self.event_kind,
            "actor_type": self.actor_type,
            "origin_class": self.origin_class,
            "parent_event_ids": list(self.parent_event_ids),
            "sequence_hint": self.sequence_hint,
            "content_reference": self.content_reference,
            "occurred_at": self.occurred_at,
            "source_event_kind": self.source_event_kind,
            "source_environment_id": self.source_environment_id,
            "source_object_id": self.source_object_id,
            "provider_id": self.provider_id,
            "application_id": self.application_id,
            "interface_id": self.interface_id,
            "model_manifest_id": self.model_manifest_id,
            "runtime_adapter_id": self.runtime_adapter_id,
            "operation_id": self.operation_id,
            "extensions": self.extensions,
        }


def _validate_conversation_uuid(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise ConversationValidationError(f"{name} must be text")
    try:
        return str(UUID(value))
    except (ValueError, AttributeError) as exc:
        raise ConversationValidationError(f"{name} is invalid") from exc


def _validate_conversation_text(
    name: str,
    value: object,
    maximum: int,
) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ConversationValidationError(f"{name} must be text")
    normalized = value.strip()
    if not normalized:
        raise ConversationValidationError(f"{name} must not be blank")
    if len(normalized) > maximum:
        raise ConversationValidationError(f"{name} exceeds the maximum length")
    if any(
        ord(character) < 32 or ord(character) == 127
        for character in normalized
    ):
        raise ConversationValidationError(
            f"{name} contains a control character"
        )
    return normalized


def _validate_conversation_timestamp(
    name: str,
    value: object,
) -> str | None:
    normalized = _validate_conversation_text(
        name,
        value,
        _MAX_CONVERSATION_IDENTIFIER,
    )
    if normalized is None:
        return None
    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ConversationValidationError(f"{name} is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ConversationValidationError(f"{name} must be timezone-aware")
    return normalized


def _validate_conversation_parents(
    event_id: str,
    value: object,
) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise ConversationValidationError(
            "parent event identifiers must be a tuple"
        )
    if len(value) > _MAX_CONVERSATION_PARENTS:
        raise ConversationValidationError(
            "too many parent event identifiers"
        )
    parents = tuple(
        _validate_conversation_uuid(
            "parent event identifier",
            parent,
        )
        for parent in value
    )
    if event_id in parents:
        raise ConversationValidationError("event cannot be its own parent")
    if len(parents) != len(set(parents)):
        raise ConversationValidationError(
            "parent event identifiers must be unique"
        )
    return parents


def _validate_conversation_extensions(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or not all(
        isinstance(key, str) for key in value
    ):
        raise ConversationValidationError(
            "extensions must be a string-keyed object"
        )
    if len(value) > _MAX_CONVERSATION_EXTENSIONS:
        raise ConversationValidationError("too many extensions")

    normalized: dict[str, object] = {}
    for key, item in value.items():
        normalized_key = key.strip().lower()
        if not _EXTENSION_KEY_PATTERN.fullmatch(normalized_key):
            raise ConversationValidationError("extension key is invalid")
        normalized[normalized_key] = item

    try:
        json.dumps(
            normalized,
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ConversationValidationError(
            "extensions must be JSON-compatible"
        ) from exc
    return normalized


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


from doll.state_migrations import MIGRATIONS, apply_migrations  # noqa: E402
from doll.state_repository import StateRepository  # noqa: E402
from doll.state_schema import initialize_state_repository, open_state_repository  # noqa: E402

__all__ = [
    "CURRENT_SCHEMA_VERSION",
    "MIGRATIONS",
    "STATE_DATABASE_NAME",
    "ConversationActorType",
    "ConversationEventKind",
    "ConversationEventRecord",
    "ConversationOriginClass",
    "ConversationRecord",
    "ConversationValidationError",
    "FutureSchemaVersionError",
    "Migration",
    "MigrationError",
    "ReadOnlyStateError",
    "RecordEnvelope",
    "RecordProvenance",
    "RecordSensitivity",
    "RecordStatus",
    "RecordValidationError",
    "StaleRevisionError",
    "StateCorruptError",
    "StateError",
    "StateExistsError",
    "StateNotInitializedError",
    "StateRepository",
    "StateRevisionMismatchError",
    "StateStatus",
    "apply_migrations",
    "initialize_state_repository",
    "open_state_repository",
]
