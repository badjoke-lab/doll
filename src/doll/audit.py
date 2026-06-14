"""Append-oriented, secret-safe audit service."""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, cast
from uuid import uuid4

from doll.state import ReadOnlyStateError, StateCorruptError, StateError, _utc_now

if TYPE_CHECKING:
    from doll.state_repository import StateRepository

AuditActorType = Literal["user", "system", "model", "runtime", "capability", "migration"]
AuditResult = Literal["success", "denied", "failed", "cancelled", "partial"]

_ALLOWED_ACTOR_TYPES = frozenset({"user", "system", "model", "runtime", "capability", "migration"})
_ALLOWED_RESULTS = frozenset({"success", "denied", "failed", "cancelled", "partial"})
_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
_SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b(?:password|passwd|secret|api[_ -]?key|access[_ -]?token|refresh[_ -]?token|"
    r"authorization|cookie|private[_ -]?key|recovery[_ -]?phrase|seed[_ -]?phrase|mnemonic)"
    r"\b\s*[:=]\s*\S+"
)
_JWT_PATTERN = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")
_WINDOWS_PATH_PATTERN = re.compile(r"(?i)\b[A-Z]:\\")
_SECRET_KEYS = frozenset(
    {
        "password",
        "passwd",
        "secret",
        "api_key",
        "apikey",
        "access_token",
        "refresh_token",
        "authorization",
        "cookie",
        "session_cookie",
        "private_key",
        "recovery_phrase",
        "seed_phrase",
        "mnemonic",
        "credential",
        "credentials",
    }
)

MAX_ACTION_LENGTH = 120
MAX_IDENTIFIER_LENGTH = 200
MAX_SUMMARY_LENGTH = 500
MAX_ERROR_CLASS_LENGTH = 120
MAX_METADATA_BYTES = 8192
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
class AuditService:
    """Append and inspect audit events through an open state repository."""

    repository: StateRepository

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
        """Append one audit event and advance the authoritative state revision."""

        if self.repository.read_only:
            raise ReadOnlyStateError("state repository is open in read-only mode")

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
        safe_summary = _validate_summary(summary)
        error_class = _safe_error_class(error)
        metadata_json = _serialize_metadata(metadata or {})

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
        except BaseException:
            connection.execute("ROLLBACK")
            raise

        self.repository._sync_after_commit(state_revision)
        return self.get(event_id)

    def get(self, event_id: str) -> AuditEvent:
        """Return one audit event by its globally unique ID."""

        safe_event_id = _validate_token("event ID", event_id, MAX_IDENTIFIER_LENGTH)
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

        if limit < 1 or limit > MAX_AUDIT_LIMIT:
            raise AuditValidationError(
                f"audit limit must be between 1 and {MAX_AUDIT_LIMIT}"
            )
        clauses: list[str] = []
        parameters: list[object] = []
        if operation_id is not None:
            clauses.append("operation_id = ?")
            parameters.append(
                _validate_token("operation ID", operation_id, MAX_IDENTIFIER_LENGTH)
            )
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
        return tuple(_event_from_row(cast(sqlite3.Row, row)) for row in rows)


def _validate_token(name: str, value: str, maximum: int) -> str:
    normalized = value.strip()
    if not normalized:
        raise AuditValidationError(f"{name} must not be blank")
    if len(normalized) > maximum:
        raise AuditValidationError(f"{name} exceeds {maximum} characters")
    if not _TOKEN_PATTERN.fullmatch(normalized):
        raise AuditValidationError(f"{name} contains unsupported characters")
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
    return normalized


def _validate_summary(summary: str | None) -> str | None:
    if summary is None:
        return None
    normalized = " ".join(summary.split())
    if not normalized:
        return None
    if len(normalized) > MAX_SUMMARY_LENGTH:
        raise AuditValidationError(f"audit summary exceeds {MAX_SUMMARY_LENGTH} characters")
    _reject_secret_text(normalized)
    if "file://" in normalized or "/Users/" in normalized or "/home/" in normalized:
        raise AuditValidationError("audit summary must not contain a local absolute path")
    if _WINDOWS_PATH_PATTERN.search(normalized):
        raise AuditValidationError("audit summary must not contain a local absolute path")
    return normalized


def _safe_error_class(error: BaseException | None) -> str | None:
    if error is None:
        return None
    error_class = type(error).__name__
    if len(error_class) > MAX_ERROR_CLASS_LENGTH or not _TOKEN_PATTERN.fullmatch(error_class):
        return "Error"
    return error_class


def _serialize_metadata(metadata: dict[str, object]) -> str:
    _validate_metadata_value(metadata)
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


def _validate_metadata_value(value: object) -> None:
    if isinstance(value, dict):
        for raw_key, nested in value.items():
            if not isinstance(raw_key, str):
                raise AuditValidationError("audit metadata keys must be strings")
            normalized_key = raw_key.strip().lower().replace("-", "_").replace(" ", "_")
            if normalized_key in _SECRET_KEYS:
                raise AuditValidationError(
                    f"audit metadata contains a prohibited secret-like key: {raw_key}"
                )
            _validate_metadata_value(nested)
        return
    if isinstance(value, list):
        for nested in value:
            _validate_metadata_value(nested)
        return
    if isinstance(value, str):
        _reject_secret_text(value)
        return
    if value is None or isinstance(value, (bool, int, float)):
        return
    raise AuditValidationError("audit metadata must be JSON-compatible")


def _reject_secret_text(value: str) -> None:
    if "-----BEGIN" in value and "PRIVATE KEY-----" in value:
        raise AuditValidationError("audit data appears to contain private key material")
    if _SECRET_ASSIGNMENT_PATTERN.search(value) or _JWT_PATTERN.search(value):
        raise AuditValidationError("audit data appears to contain secret material")


def _reject_nonstandard_json(value: str) -> object:
    raise ValueError(f"non-standard JSON constant: {value}")


def _event_from_row(row: sqlite3.Row) -> AuditEvent:
    try:
        metadata_value = json.loads(
            cast(str, row["metadata_json"]),
            parse_constant=_reject_nonstandard_json,
        )
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise StateCorruptError("audit metadata is not valid JSON") from exc
    if not isinstance(metadata_value, dict):
        raise StateCorruptError("audit metadata is not a JSON object")
    return AuditEvent(
        sequence=cast(int, row["sequence"]),
        event_id=cast(str, row["event_id"]),
        operation_id=cast(str, row["operation_id"]),
        occurred_at=cast(str, row["occurred_at"]),
        actor_type=cast(AuditActorType, row["actor_type"]),
        actor_id=cast(str | None, row["actor_id"]),
        action=cast(str, row["action"]),
        target_type=cast(str | None, row["target_type"]),
        target_id=cast(str | None, row["target_id"]),
        result=cast(AuditResult, row["result"]),
        summary=cast(str | None, row["summary"]),
        error_class=cast(str | None, row["error_class"]),
        metadata=cast(dict[str, object], metadata_value),
    )
