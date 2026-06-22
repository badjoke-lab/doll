"""Append-only fresh exact confirmation authority for Tier 3 operations."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal, cast
from uuid import uuid4

from doll._confirmation_types import (
    DEFAULT_CONFIRMATION_TTL_SECONDS,
    MAX_CONFIRMATION_EVENTS,
    MAX_CONFIRMATION_ID_LENGTH,
    ConfirmationConsumeActor,
    ConfirmationCorruptError,
    ConfirmationDecisionValue,
    ConfirmationInfo,
    ConfirmationMutationActor,
    ConfirmationPreview,
    ConfirmationResolution,
    ConfirmationUnavailableError,
    ConfirmationValidationError,
    ForbiddenConfirmationMutationError,
    confirmation_fingerprint,
    format_utc,
    require_user_management,
    safe_now,
    validate_preview,
    validate_token,
    validate_ttl,
)
from doll._confirmation_validation import (
    confirmation_metadata,
    resolution_from_events,
    validated_high_risk_binding,
)
from doll.audit import (
    AuditActorType,
    AuditEvent,
    _event_from_row,
    _serialize_metadata_for_write,
)
from doll.capabilities import (
    CapabilityRegistry,
    CapabilityRequest,
    _validate_request_envelope,
)
from doll.instruction_origin import InstructionOriginClass
from doll.state import StateCorruptError, StateError, _utc_now
from doll.state_repository import StateRepository

_ALLOWED_CONSUME_ACTORS = frozenset({"capability", "system"})

__all__ = [
    "ConfirmationConsumeActor",
    "ConfirmationCorruptError",
    "ConfirmationDecisionValue",
    "ConfirmationInfo",
    "ConfirmationMutationActor",
    "ConfirmationPreview",
    "ConfirmationResolution",
    "ConfirmationService",
    "ConfirmationUnavailableError",
    "ConfirmationValidationError",
    "ForbiddenConfirmationMutationError",
    "confirmation_fingerprint",
]


@dataclass(slots=True)
class ConfirmationService:
    """Trusted append-only ledger for exact Tier 3 user decisions."""

    repository: StateRepository
    clock: Callable[[], datetime] = lambda: datetime.now(UTC)
    id_factory: Callable[[], str] = lambda: uuid4().hex

    def issue(
        self,
        request: CapabilityRequest,
        *,
        registry: CapabilityRegistry,
        preview: ConfirmationPreview,
        decision: ConfirmationDecisionValue,
        ttl_seconds: int = DEFAULT_CONFIRMATION_TTL_SECONDS,
        actor_type: ConfirmationMutationActor = "user",
        origin_class: InstructionOriginClass = "user_management_action",
    ) -> ConfirmationInfo:
        """Append one fresh exact user decision for a release-available Tier 3 request."""

        require_user_management(actor_type, origin_class)
        self._require_writable()
        envelope, definition, destination = validated_high_risk_binding(
            request, registry
        )
        safe_preview = validate_preview(preview)
        if decision not in {"approved", "denied"}:
            raise ConfirmationValidationError(
                "confirmation decision must be approved or denied"
            )
        ttl = validate_ttl(ttl_seconds)
        expires_at = safe_now(self.clock) + timedelta(seconds=ttl)
        fingerprint = confirmation_fingerprint(
            envelope,
            registry_fingerprint=registry.fingerprint,
            normalized_destination=destination,
            credential_class=safe_preview.credential_class,
        )
        try:
            confirmation_id = validate_token(
                "confirmation ID", self.id_factory(), MAX_CONFIRMATION_ID_LENGTH
            )
        except Exception:
            raise ConfirmationValidationError(
                "confirmation ID generation failed"
            ) from None
        metadata = confirmation_metadata(
            confirmation_id=confirmation_id,
            request=envelope,
            definition=definition,
            request_fingerprint=fingerprint,
            registry_fingerprint=registry.fingerprint,
            destination=destination,
            decision=decision,
            expires_at=format_utc(expires_at),
            preview=safe_preview,
        )
        result: Literal["success", "denied"] = (
            "success" if decision == "approved" else "denied"
        )
        self._append_unique_issue(
            confirmation_id=confirmation_id,
            operation_id=envelope.operation_id,
            result=result,
            metadata=metadata,
        )
        resolution = self.resolve(
            confirmation_id,
            envelope,
            registry_fingerprint=registry.fingerprint,
            normalized_destination=destination,
            credential_class=safe_preview.credential_class,
        )
        if resolution.info is None:
            raise ConfirmationCorruptError("issued confirmation could not be reloaded")
        return resolution.info

    def resolve(
        self,
        confirmation_id: str | None,
        request: CapabilityRequest,
        *,
        registry_fingerprint: str,
        normalized_destination: str | None,
        credential_class: str | None = None,
    ) -> ConfirmationResolution:
        """Resolve exact append-only confirmation state without consuming it."""

        envelope = _validate_request_envelope(request)
        fingerprint = confirmation_fingerprint(
            envelope,
            registry_fingerprint=registry_fingerprint,
            normalized_destination=normalized_destination,
            credential_class=credential_class,
        )
        if confirmation_id is None:
            return ConfirmationResolution(None, "missing", fingerprint, None)
        safe_id = validate_token(
            "confirmation ID", confirmation_id, MAX_CONFIRMATION_ID_LENGTH
        )
        try:
            return resolution_from_events(
                safe_id,
                self._events(safe_id),
                expected_operation_id=envelope.operation_id,
                expected_fingerprint=fingerprint,
                now=safe_now(self.clock),
            )
        except ConfirmationCorruptError:
            return ConfirmationResolution(safe_id, "corrupt", fingerprint, None)

    def consume(
        self,
        confirmation_id: str,
        request: CapabilityRequest,
        *,
        registry_fingerprint: str,
        normalized_destination: str | None,
        credential_class: str | None = None,
        actor_type: ConfirmationConsumeActor = "capability",
    ) -> ConfirmationInfo:
        """Atomically consume one exact confirmation for a future execution boundary."""

        if actor_type not in _ALLOWED_CONSUME_ACTORS:
            raise ForbiddenConfirmationMutationError(
                "only the capability broker or core system may consume confirmation"
            )
        self._require_writable()
        envelope = _validate_request_envelope(request)
        safe_id = validate_token(
            "confirmation ID", confirmation_id, MAX_CONFIRMATION_ID_LENGTH
        )
        fingerprint = confirmation_fingerprint(
            envelope,
            registry_fingerprint=registry_fingerprint,
            normalized_destination=normalized_destination,
            credential_class=credential_class,
        )
        connection = self.repository.connection
        connection.execute("BEGIN IMMEDIATE")
        try:
            resolution = resolution_from_events(
                safe_id,
                self._events(safe_id),
                expected_operation_id=envelope.operation_id,
                expected_fingerprint=fingerprint,
                now=safe_now(self.clock),
            )
            if not resolution.approved or resolution.info is None:
                raise ConfirmationUnavailableError(
                    f"confirmation cannot be consumed: {resolution.reason}"
                )
            _insert_confirmation_event(
                self.repository,
                confirmation_id=safe_id,
                operation_id=envelope.operation_id,
                action="confirmation.consume",
                result="success",
                actor_type=cast(AuditActorType, actor_type),
                metadata={
                    "confirmation_id": safe_id,
                    "request_fingerprint": fingerprint,
                    "capability_id": envelope.capability_id,
                    "capability_version": envelope.capability_version,
                    "risk_tier": 3,
                },
            )
            state_revision = self.repository._commit_state_revision()
            connection.execute("COMMIT")
        except BaseException:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        self.repository._sync_after_commit(state_revision)
        return resolution.info

    def revoke(
        self,
        confirmation_id: str,
        *,
        operation_id: str,
        actor_type: ConfirmationMutationActor = "user",
        origin_class: InstructionOriginClass = "user_management_action",
    ) -> None:
        """Append a trusted user revocation without rewriting history."""

        require_user_management(actor_type, origin_class)
        self._require_writable()
        safe_id = validate_token(
            "confirmation ID", confirmation_id, MAX_CONFIRMATION_ID_LENGTH
        )
        safe_operation = validate_token("operation ID", operation_id, 200)
        connection = self.repository.connection
        connection.execute("BEGIN IMMEDIATE")
        try:
            events = self._events(safe_id)
            if not events:
                raise KeyError(safe_id)
            if any(event.action == "confirmation.revoke" for event in events):
                raise ConfirmationUnavailableError("confirmation is already revoked")
            _insert_confirmation_event(
                self.repository,
                confirmation_id=safe_id,
                operation_id=safe_operation,
                action="confirmation.revoke",
                result="success",
                actor_type="user",
                metadata={"confirmation_id": safe_id},
            )
            state_revision = self.repository._commit_state_revision()
            connection.execute("COMMIT")
        except BaseException:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        self.repository._sync_after_commit(state_revision)

    def _append_unique_issue(
        self,
        *,
        confirmation_id: str,
        operation_id: str,
        result: Literal["success", "denied"],
        metadata: dict[str, object],
    ) -> None:
        connection = self.repository.connection
        connection.execute("BEGIN IMMEDIATE")
        try:
            if self._events(confirmation_id):
                raise ConfirmationValidationError("duplicate confirmation ID")
            _insert_confirmation_event(
                self.repository,
                confirmation_id=confirmation_id,
                operation_id=operation_id,
                action="confirmation.issue",
                result=result,
                actor_type="user",
                metadata=metadata,
            )
            state_revision = self.repository._commit_state_revision()
            connection.execute("COMMIT")
        except BaseException:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        self.repository._sync_after_commit(state_revision)

    def _events(self, confirmation_id: str) -> tuple[AuditEvent, ...]:
        try:
            rows = self.repository.connection.execute(
                """
                SELECT sequence, event_id, operation_id, occurred_at, actor_type, actor_id,
                       action, target_type, target_id, result, summary, error_class, metadata_json
                FROM audit_events
                WHERE target_type = 'confirmation' AND target_id = ?
                  AND action IN ('confirmation.issue', 'confirmation.consume',
                                 'confirmation.revoke')
                ORDER BY sequence ASC
                LIMIT ?
                """,
                (confirmation_id, MAX_CONFIRMATION_EVENTS + 1),
            ).fetchall()
        except sqlite3.DatabaseError as exc:
            raise ConfirmationCorruptError(
                "confirmation history is unreadable"
            ) from exc
        if len(rows) > MAX_CONFIRMATION_EVENTS:
            raise ConfirmationCorruptError(
                "confirmation history exceeds the event limit"
            )
        try:
            return tuple(_event_from_row(cast(sqlite3.Row, row)) for row in rows)
        except StateError as exc:
            raise ConfirmationCorruptError("confirmation history is malformed") from exc

    def _require_writable(self) -> None:
        if self.repository.read_only:
            raise ConfirmationValidationError("confirmation ledger is read-only")


def _insert_confirmation_event(
    repository: StateRepository,
    *,
    confirmation_id: str,
    operation_id: str,
    action: str,
    result: Literal["success", "denied"],
    actor_type: AuditActorType,
    metadata: dict[str, object],
) -> None:
    try:
        repository.connection.execute(
            """
            INSERT INTO audit_events (
                event_id, operation_id, occurred_at, actor_type, actor_id, action,
                target_type, target_id, result, summary, error_class, metadata_json
            ) VALUES (?, ?, ?, ?, NULL, ?, 'confirmation', ?, ?, ?, NULL, ?)
            """,
            (
                str(uuid4()),
                validate_token("operation ID", operation_id, 200),
                _utc_now(),
                actor_type,
                action,
                confirmation_id,
                result,
                "High-risk confirmation decision recorded",
                _serialize_metadata_for_write(metadata),
            ),
        )
    except sqlite3.DatabaseError as exc:
        raise StateCorruptError("confirmation event could not be appended") from exc
