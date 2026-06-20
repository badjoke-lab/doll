"""Append-oriented, secret-safe audit service."""

from __future__ import annotations

import json
import math
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Literal, cast
from uuid import UUID, uuid4

from doll.secret_detection import redact_text
from doll.sensitive_fields import (
    is_private_environment_field_name,
    is_secret_field_name,
)
from doll.state import ReadOnlyStateError, StateCorruptError, StateError, _utc_now

if TYPE_CHECKING:
    from doll.state_repository import StateRepository

AuditActorType = Literal["user", "system", "model", "runtime", "capability", "migration"]
AuditResult = Literal["success", "denied", "failed", "cancelled", "partial"]

_ALLOWED_ACTOR_TYPES = frozenset({"user", "system", "model", "runtime", "capability", "migration"})
_ALLOWED_RESULTS = frozenset({"success", "denied", "failed", "cancelled", "partial"})
_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
_POSIX_PATH_PATTERN = re.compile(r"(?<![:/\w])/(?:[^/\s]+/)*[^/\s]+")
_WINDOWS_PATH_PATTERN = re.compile(r"(?i)\b[A-Z]:\\(?:[^\\\s]+\\)*[^\\\s]+")
_PRIVATE_ENVIRONMENT_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b(?P<label>username|user_name|os_user|login_name|hostname|host_name|"
    r"machine_name|computer_name|cwd|current_working_directory|home_dir|home_directory)"
    r"\s*[:=]\s*(?P<value>[^\s,;]{1,2048})"
)

AUDIT_SCHEMA_VERSION = 2

MAX_ACTION_LENGTH = 120
MAX_IDENTIFIER_LENGTH = 200
MAX_SUMMARY_LENGTH = 500
MAX_ERROR_CLASS_LENGTH = 120
MAX_METADATA_BYTES = 8192
MAX_METADATA_STRING_LENGTH = 4096
MAX_METADATA_DEPTH = 6
MAX_METADATA_ITEMS = 256
MAX_AUDIT_LIMIT = 200


class AuditError(StateError):
    """Base class for audit service failures."""


class AuditValidationError(AuditError):
    """Raised when an audit event contains unsafe or invalid data."""


@dataclass(frozen=True, slots=True)
class AuditEvent:
    """One immutable audit event returned from the local repository."""

    sequence: int
    event_id: str
    operation_id: str
    occurred_at: str
    actor_type: AuditActorType
    actor_id: str | None
    action: str
    target_type: str | None
    target_id: str | None
    result: AuditResult
    summary: str | None
    error_class: str | None
    metadata: dict[str, object]


@dataclass(slots=True)
class _MetadataState:
    items_seen: int = 0
    active_container_ids: set[int] = field(default_factory=set)


@dataclass(slots=True)
class AuditService:
    """Append and inspect audit events through an open state repository."""

    repository: StateRepository

    def _require_audit_schema(self) -> None:
        if self.repository.status().schema_version < AUDIT_SCHEMA_VERSION:
            raise AuditError(
                "audit schema is unavailable; open the state repository in writable mode to migrate"
            )

    def append(
        self,
        *,
        action: str,
        result: AuditResult,
        actor_type: AuditActorType = "system",
        operation_id: str | None = None,
        actor_id: str | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        summary: str | None = None,
        error: BaseException | None = None,
        metadata: dict[str, object] | None = None,
    ) -> AuditEvent:
        """Append one sanitized audit event and advance the authoritative state revision."""

        if self.repository.read_only:
            raise ReadOnlyStateError("state repository is open in read-only mode")
        self._require_audit_schema()

        safe_operation_id = operation_id or str(uuid4())
        safe_action = _validate_token("action", action, MAX_ACTION_LENGTH)
        safe_operation_id = _validate_token(
            "operation ID", safe_operation_id, MAX_IDENTIFIER_LENGTH
        )
        if actor_type not in _ALLOWED_ACTOR_TYPES:
            raise AuditValidationError(f"invalid audit actor type: {actor_type}")
        if result not in _ALLOWED_RESULTS:
            raise AuditValidationError(f"invalid audit result: {result}")
        safe_actor_id = _validate_optional_identifier("actor ID", actor_id)
        safe_target_type = (
            _validate_token("target type", target_type, MAX_ACTION_LENGTH)
            if target_type is not None
            else None
        )
        safe_target_id = _validate_optional_identifier("target ID", target_id)
        safe_summary = _sanitize_summary(summary)
        error_class = _safe_error_class(error)
        metadata_json = _serialize_metadata_for_write(metadata or {})

        event_id = str(uuid4())
        occurred_at = _utc_now()
        connection = self.repository.connection
        connection.execute("BEGIN IMMEDIATE")
        try:
            connection.execute(
                """
                INSERT INTO audit_events (
                    event_id,
                    operation_id,
                    occurred_at,
                    actor_type,
                    actor_id,
                    action,
                    target_type,
                    target_id,
                    result,
                    summary,
                    error_class,
                    metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    safe_operation_id,
                    occurred_at,
                    actor_type,
                    safe_actor_id,
                    safe_action,
                    safe_target_type,
                    safe_target_id,
                    result,
                    safe_summary,
                    error_class,
                    metadata_json,
                ),
            )
            state_revision = self.repository._commit_state_revision()
            connection.execute("COMMIT")
        except sqlite3.DatabaseError as exc:
            connection.execute("ROLLBACK")
            raise StateCorruptError("audit event could not be appended") from exc
        except BaseException:
            connection.execute("ROLLBACK")
            raise

        self.repository._sync_after_commit(state_revision)
        return self.get(event_id)

    def get(self, event_id: str) -> AuditEvent:
        """Return one audit event by its globally unique ID."""

        self._require_audit_schema()
        safe_event_id = _validate_token("event ID", event_id, MAX_IDENTIFIER_LENGTH)
        try:
            row = self.repository.connection.execute(
                """
            SELECT
                sequence,
                event_id,
                operation_id,
                occurred_at,
                actor_type,
                actor_id,
                action,
                target_type,
                target_id,
                result,
                summary,
                error_class,
                metadata_json
            FROM audit_events
            WHERE event_id = ?
            """,
                (safe_event_id,),
            ).fetchone()
        except sqlite3.DatabaseError as exc:
            raise StateCorruptError("audit events are unreadable") from exc
        if row is None:
            raise KeyError(event_id)
        return _event_from_row(cast(sqlite3.Row, row))

    def list(
        self,
        *,
        operation_id: str | None = None,
        action: str | None = None,
        actor_type: AuditActorType | None = None,
        result: AuditResult | None = None,
        limit: int = 50,
    ) -> tuple[AuditEvent, ...]:
        """Return newest audit events matching validated filters."""

        self._require_audit_schema()
        if limit < 1 or limit > MAX_AUDIT_LIMIT:
            raise AuditValidationError(f"audit limit must be between 1 and {MAX_AUDIT_LIMIT}")
        clauses: list[str] = []
        parameters: list[object] = []
        if operation_id is not None:
            clauses.append("operation_id = ?")
            parameters.append(_validate_token("operation ID", operation_id, MAX_IDENTIFIER_LENGTH))
        if action is not None:
            clauses.append("action = ?")
            parameters.append(_validate_token("action", action, MAX_ACTION_LENGTH))
        if actor_type is not None:
            if actor_type not in _ALLOWED_ACTOR_TYPES:
                raise AuditValidationError(f"invalid audit actor type: {actor_type}")
            clauses.append("actor_type = ?")
            parameters.append(actor_type)
        if result is not None:
            if result not in _ALLOWED_RESULTS:
                raise AuditValidationError(f"invalid audit result: {result}")
            clauses.append("result = ?")
            parameters.append(result)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        parameters.append(limit)
        try:
            rows = self.repository.connection.execute(
                f"""
            SELECT
                sequence,
                event_id,
                operation_id,
                occurred_at,
                actor_type,
                actor_id,
                action,
                target_type,
                target_id,
                result,
                summary,
                error_class,
                metadata_json
            FROM audit_events
                {where}
                ORDER BY sequence DESC
                LIMIT ?
                """,
                tuple(parameters),
            ).fetchall()
        except sqlite3.DatabaseError as exc:
            raise StateCorruptError("audit events are unreadable") from exc
        return tuple(_event_from_row(cast(sqlite3.Row, row)) for row in rows)


def _validate_token(name: str, value: str, maximum: int) -> str:
    normalized = value.strip()
    if not normalized:
        raise AuditValidationError(f"{name} must not be blank")
    if len(normalized) > maximum:
        raise AuditValidationError(f"{name} exceeds {maximum} characters")
    if not _TOKEN_PATTERN.fullmatch(normalized):
        raise AuditValidationError(f"{name} contains unsupported characters")
    _reject_unsafe_identifier_text(normalized)
    return normalized


def _validate_optional_identifier(name: str, value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.split())
    if not normalized:
        raise AuditValidationError(f"{name} must not be blank")
    if len(normalized) > MAX_IDENTIFIER_LENGTH:
        raise AuditValidationError(f"{name} exceeds {MAX_IDENTIFIER_LENGTH} characters")
    if any(ord(character) < 32 for character in normalized):
        raise AuditValidationError(f"{name} contains control characters")
    _reject_unsafe_identifier_text(normalized)
    return normalized


def _sanitize_summary(summary: str | None) -> str | None:
    if summary is None:
        return None
    normalized = " ".join(summary.split())
    if not normalized:
        return None
    if len(normalized) > MAX_SUMMARY_LENGTH:
        raise AuditValidationError(f"audit summary exceeds {MAX_SUMMARY_LENGTH} characters")
    return _sanitize_free_text(normalized, max_scan_chars=MAX_SUMMARY_LENGTH)


def _validate_stored_summary(summary: str | None) -> str | None:
    sanitized = _sanitize_summary(summary)
    normalized = None if summary is None else (" ".join(summary.split()) or None)
    if sanitized != normalized:
        raise AuditValidationError("audit summary contains unsafe data")
    return sanitized


def _safe_error_class(error: BaseException | None) -> str | None:
    if error is None:
        return None
    error_class = type(error).__name__
    if len(error_class) > MAX_ERROR_CLASS_LENGTH or not _TOKEN_PATTERN.fullmatch(error_class):
        return "Error"
    return error_class


def _serialize_metadata(metadata: dict[str, object]) -> str:
    """Strict compatibility validator used by non-audit record services."""

    sanitized = _sanitize_metadata(metadata)
    if sanitized != metadata:
        raise AuditValidationError("metadata contains unsafe data")
    return _encode_metadata(sanitized)


def _serialize_metadata_for_write(metadata: dict[str, object]) -> str:
    sanitized = _sanitize_metadata(metadata)
    return _encode_metadata(sanitized)


def _validate_stored_metadata(metadata: dict[str, object]) -> dict[str, object]:
    sanitized = _sanitize_metadata(metadata)
    if sanitized != metadata:
        raise AuditValidationError("audit metadata contains unsafe data")
    _encode_metadata(sanitized)
    return sanitized


def _sanitize_metadata(metadata: dict[str, object]) -> dict[str, object]:
    state = _MetadataState()
    sanitized = _sanitize_metadata_value(metadata, depth=0, state=state)
    if not isinstance(sanitized, dict):
        raise AuditValidationError("audit metadata is not a JSON object")
    return cast(dict[str, object], sanitized)


def _sanitize_metadata_value(
    value: object,
    *,
    depth: int,
    state: _MetadataState,
) -> object:
    if depth > MAX_METADATA_DEPTH:
        raise AuditValidationError(f"audit metadata exceeds depth {MAX_METADATA_DEPTH}")
    if isinstance(value, dict):
        identity = id(value)
        if identity in state.active_container_ids:
            raise AuditValidationError("audit metadata must not contain cycles")
        state.active_container_ids.add(identity)
        result: dict[str, object] = {}
        try:
            for raw_key, nested in value.items():
                _consume_metadata_item(state)
                if not isinstance(raw_key, str):
                    raise AuditValidationError("audit metadata keys must be strings")
                key = raw_key.strip()
                if not key:
                    raise AuditValidationError("audit metadata keys must not be blank")
                if is_secret_field_name(key):
                    raise AuditValidationError(
                        "audit metadata contains a prohibited secret-like key"
                    )
                if is_private_environment_field_name(key):
                    raise AuditValidationError(
                        "audit metadata contains a prohibited private-environment key"
                    )
                _reject_unsafe_identifier_text(key)
                result[key] = _sanitize_metadata_value(nested, depth=depth + 1, state=state)
        finally:
            state.active_container_ids.remove(identity)
        return result
    if isinstance(value, list):
        identity = id(value)
        if identity in state.active_container_ids:
            raise AuditValidationError("audit metadata must not contain cycles")
        state.active_container_ids.add(identity)
        result_list: list[object] = []
        try:
            for nested in value:
                _consume_metadata_item(state)
                result_list.append(
                    _sanitize_metadata_value(nested, depth=depth + 1, state=state)
                )
        finally:
            state.active_container_ids.remove(identity)
        return result_list
    if isinstance(value, str):
        return _sanitize_free_text(value, max_scan_chars=MAX_METADATA_STRING_LENGTH)
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise AuditValidationError("audit metadata numbers must be finite")
        return value
    raise AuditValidationError("audit metadata must be JSON-compatible")


def _consume_metadata_item(state: _MetadataState) -> None:
    if state.items_seen >= MAX_METADATA_ITEMS:
        raise AuditValidationError(f"audit metadata exceeds {MAX_METADATA_ITEMS} items")
    state.items_seen += 1


def _encode_metadata(metadata: dict[str, object]) -> str:
    try:
        encoded = json.dumps(
            metadata,
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise AuditValidationError("audit metadata must be JSON-compatible") from exc
    if len(encoded.encode("utf-8")) > MAX_METADATA_BYTES:
        raise AuditValidationError(f"audit metadata exceeds {MAX_METADATA_BYTES} bytes")
    return encoded


def _sanitize_free_text(value: str, *, max_scan_chars: int) -> str:
    normalized = " ".join(value.split())
    redacted = redact_text(normalized, max_scan_chars=max_scan_chars).redacted_text
    redacted = _PRIVATE_ENVIRONMENT_ASSIGNMENT_PATTERN.sub(
        lambda match: f"{match.group('label')}=[REDACTED:private_environment]",
        redacted,
    )
    redacted = _POSIX_PATH_PATTERN.sub("[REDACTED:private_path]", redacted)
    return _WINDOWS_PATH_PATTERN.sub("[REDACTED:private_path]", redacted)


def _reject_unsafe_identifier_text(value: str) -> None:
    sanitized = _sanitize_free_text(value, max_scan_chars=max(len(value), 1))
    if sanitized != value:
        raise AuditValidationError("audit identifier contains secret or private-environment data")


def _reject_secret_text(value: str) -> None:
    """Strict compatibility validator for callers that cannot accept redaction."""

    normalized = " ".join(value.split())
    redacted = redact_text(normalized, max_scan_chars=max(len(normalized), 1)).redacted_text
    if redacted != normalized:
        raise AuditValidationError("audit data appears to contain secret material")


def _reject_local_path(value: str) -> None:
    """Strict compatibility validator for portable package and record metadata."""

    if "file://" in value or _POSIX_PATH_PATTERN.search(value):
        raise AuditValidationError("audit data must not contain a local absolute path")
    if _WINDOWS_PATH_PATTERN.search(value):
        raise AuditValidationError("audit data must not contain a local absolute path")


def _reject_nonstandard_json(value: str) -> object:
    raise ValueError(f"non-standard JSON constant: {value}")


def _validate_utc_timestamp(value: str) -> str:
    if not value.endswith("Z"):
        raise AuditValidationError("audit timestamp must use UTC Z notation")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise AuditValidationError("audit timestamp is invalid") from exc
    if parsed.utcoffset() != timedelta(0):
        raise AuditValidationError("audit timestamp must be UTC")
    return value


def _event_from_row(row: sqlite3.Row) -> AuditEvent:
    try:
        sequence = cast(int, row["sequence"])
        if sequence < 1:
            raise AuditValidationError("audit sequence must be positive")
        event_id = cast(str, row["event_id"])
        UUID(event_id)
        operation_id = _validate_token(
            "operation ID", cast(str, row["operation_id"]), MAX_IDENTIFIER_LENGTH
        )
        occurred_at = _validate_utc_timestamp(cast(str, row["occurred_at"]))
        actor_type_value = cast(str, row["actor_type"])
        if actor_type_value not in _ALLOWED_ACTOR_TYPES:
            raise AuditValidationError("audit actor type is invalid")
        actor_id = _validate_optional_identifier("actor ID", cast(str | None, row["actor_id"]))
        action = _validate_token("action", cast(str, row["action"]), MAX_ACTION_LENGTH)
        target_type_value = cast(str | None, row["target_type"])
        target_type = (
            _validate_token("target type", target_type_value, MAX_ACTION_LENGTH)
            if target_type_value is not None
            else None
        )
        target_id = _validate_optional_identifier("target ID", cast(str | None, row["target_id"]))
        result_value = cast(str, row["result"])
        if result_value not in _ALLOWED_RESULTS:
            raise AuditValidationError("audit result is invalid")
        summary = _validate_stored_summary(cast(str | None, row["summary"]))
        error_class_value = cast(str | None, row["error_class"])
        error_class = (
            _validate_token("error class", error_class_value, MAX_ERROR_CLASS_LENGTH)
            if error_class_value is not None
            else None
        )
        metadata_value = json.loads(
            cast(str, row["metadata_json"]),
            parse_constant=_reject_nonstandard_json,
        )
        if not isinstance(metadata_value, dict):
            raise AuditValidationError("audit metadata is not a JSON object")
        metadata = _validate_stored_metadata(cast(dict[str, object], metadata_value))
    except (
        AuditValidationError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        raise StateCorruptError("audit event contains invalid data") from exc

    return AuditEvent(
        sequence=sequence,
        event_id=event_id,
        operation_id=operation_id,
        occurred_at=occurred_at,
        actor_type=cast(AuditActorType, actor_type_value),
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        result=cast(AuditResult, result_value),
        summary=summary,
        error_class=error_class,
        metadata=metadata,
    )
