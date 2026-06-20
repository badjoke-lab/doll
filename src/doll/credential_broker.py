"""Model-independent bounded Credential Broker."""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock
from typing import cast
from uuid import uuid4

from doll.audit import AuditActorType, AuditResult, AuditService
from doll.credential_broker_contract import (
    DEFAULT_CREDENTIAL_AUTHORIZATION_TTL_SECONDS,
    MAX_CREDENTIAL_AUTHORIZATION_TTL_SECONDS,
    CredentialAuditEvent,
    CredentialAuditSink,
    CredentialAuthorizationGrant,
    CredentialBrokerContractError,
    CredentialBrokerResult,
    CredentialCompletion,
    CredentialFailureCode,
    CredentialHandlerContext,
    CredentialHandlerRegistry,
    CredentialHandlerResult,
    CredentialOperationHandler,
    CredentialUseIntent,
)
from doll.secret_policy import (
    SecretReferenceMetadata,
    SecretReferenceValidationError,
    validate_secret_reference_metadata,
)
from doll.secret_store import (
    ExternalSecretStore,
    SecretStoreFailureCode,
    SecretStoreRequest,
)


@dataclass(slots=True)
class _AuthorizationState:
    grant: CredentialAuthorizationGrant
    intent_signature: tuple[object, ...]
    consumed: bool = False


class CredentialAuthorizationAuthority:
    """Trusted in-memory issuer for exact, expiring, one-time authorization grants."""

    __slots__ = ("_clock", "_id_factory", "_lock", "_states")

    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.monotonic,
        id_factory: Callable[[], str] = lambda: uuid4().hex,
    ) -> None:
        if not callable(clock):
            raise CredentialBrokerContractError("invalid authorization clock")
        if not callable(id_factory):
            raise CredentialBrokerContractError("invalid authorization ID factory")
        self._clock = clock
        self._id_factory = id_factory
        self._lock = Lock()
        self._states: dict[str, _AuthorizationState] = {}

    def issue(
        self,
        intent: CredentialUseIntent,
        *,
        ttl_seconds: float = DEFAULT_CREDENTIAL_AUTHORIZATION_TTL_SECONDS,
    ) -> CredentialAuthorizationGrant:
        """Issue one exact grant through a trusted user-controlled management path."""

        _require_intent(intent)
        ttl = _validate_authorization_ttl(ttl_seconds)
        now = self._now()
        try:
            grant_id = self._id_factory()
        except Exception:
            raise CredentialBrokerContractError("authorization ID generation failed") from None
        grant = CredentialAuthorizationGrant(
            grant_id=grant_id,
            operation_id=intent.operation_id,
            capability_id=intent.capability_id,
            capability_version=intent.capability_version,
            reference_id=intent.reference.reference_id,
            operation_scope=intent.operation_scope,
            destination=intent.destination,
            risk_tier=intent.risk_tier,
            expires_at_monotonic=now + ttl,
        )
        state = _AuthorizationState(grant=grant, intent_signature=_intent_signature(intent))
        with self._lock:
            if grant.grant_id in self._states:
                raise CredentialBrokerContractError("duplicate authorization grant ID")
            self._states[grant.grant_id] = state
        return grant

    def consume(
        self,
        grant: CredentialAuthorizationGrant | None,
        intent: CredentialUseIntent,
    ) -> CredentialFailureCode | None:
        """Consume one exact grant or return a closed non-secret denial code."""

        _require_intent(intent)
        if not isinstance(grant, CredentialAuthorizationGrant):
            return "authorization_missing"
        now = self._now()
        with self._lock:
            state = self._states.get(grant.grant_id)
            if state is None or state.grant != grant:
                return "authorization_missing"
            if state.consumed:
                return "authorization_consumed"
            if now >= state.grant.expires_at_monotonic:
                state.consumed = True
                return "authorization_expired"
            if state.intent_signature != _intent_signature(intent):
                return "authorization_mismatch"
            state.consumed = True
            return None

    def _now(self) -> float:
        return _safe_clock_value(self._clock, "authorization clock")


class AuditServiceCredentialAuditSink:
    """Adapter that writes secret-free broker events through AuditService."""

    __slots__ = ("_audit",)

    def __init__(self, audit: AuditService) -> None:
        if not isinstance(audit, AuditService):
            raise CredentialBrokerContractError("invalid credential audit service")
        self._audit = audit

    def record(self, event: CredentialAuditEvent) -> None:
        if not isinstance(event, CredentialAuditEvent):
            raise CredentialBrokerContractError("invalid credential audit event")
        metadata: dict[str, object] = {
            "capability_id": event.capability_id,
            "capability_version": event.capability_version,
            "credential_class": event.credential_class,
            "destination": event.destination,
            "operation_scope": event.operation_scope,
            "risk_tier": event.risk_tier,
        }
        if event.failure_code is not None:
            metadata["failure_code"] = event.failure_code
        if event.completion is not None:
            metadata["completion"] = event.completion
        if event.handler_result_code is not None:
            metadata["handler_result_code"] = event.handler_result_code
        self._audit.append(
            action=f"credential.use.{event.phase}",
            result=event.result,
            actor_type=cast(AuditActorType, event.actor_type),
            operation_id=event.operation_id,
            actor_id=event.actor_id,
            target_type="secret_reference",
            target_id=event.reference_id,
            metadata=metadata,
        )


class CredentialBroker:
    """Only normal runtime path permitted to use externally stored credentials."""

    __slots__ = ("_audit", "_authorizations", "_clock", "_handlers", "_store")

    def __init__(
        self,
        *,
        store: ExternalSecretStore,
        handlers: CredentialHandlerRegistry,
        authorizations: CredentialAuthorizationAuthority,
        audit: CredentialAuditSink,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not isinstance(store, ExternalSecretStore):
            raise CredentialBrokerContractError("invalid external secret store")
        if not isinstance(handlers, CredentialHandlerRegistry):
            raise CredentialBrokerContractError("invalid credential handler registry")
        if not isinstance(authorizations, CredentialAuthorizationAuthority):
            raise CredentialBrokerContractError("invalid credential authorization authority")
        if not isinstance(audit, CredentialAuditSink):
            raise CredentialBrokerContractError("invalid credential audit sink")
        if not callable(clock):
            raise CredentialBrokerContractError("invalid credential broker clock")
        self._store = store
        self._handlers = handlers
        self._authorizations = authorizations
        self._audit = audit
        self._clock = clock

    def execute(
        self,
        intent: CredentialUseIntent,
        grant: CredentialAuthorizationGrant | None,
    ) -> CredentialBrokerResult:
        """Perform one exact credential-bearing operation and return no credential value."""

        _require_intent(intent)
        _require_validated_reference(intent.reference)
        deadline = self._now() + float(intent.timeout_seconds)
        if not self._record_attempt(intent):
            return self._result(intent, "audit_failure", "not_started")

        preflight = self._preflight(intent, grant, deadline)
        if isinstance(preflight, CredentialBrokerResult):
            return self._record_terminal(intent, preflight)
        handler = preflight

        remaining = deadline - self._now()
        if remaining <= 0:
            return self._record_terminal(
                intent,
                self._result(intent, "timeout", "not_started"),
            )
        lookup = self._store.lookup(
            intent.reference,
            SecretStoreRequest(
                operation_id=intent.operation_id,
                timeout_seconds=remaining,
                user_presence=intent.user_presence,
                cancellation=intent.cancellation,
            ),
        )
        if not lookup.succeeded:
            code = _map_store_failure(lookup.result.failure_code)
            lookup.close()
            return self._record_terminal(
                intent,
                self._result(intent, code, "not_started"),
            )

        with lookup:
            material = lookup.material
            if material is None or material.is_closed:
                return self._record_terminal(
                    intent,
                    self._result(intent, "adapter_failure", "not_started"),
                )
            if intent.cancellation.is_cancelled:
                return self._record_terminal(
                    intent,
                    self._result(intent, "cancelled", "not_started"),
                )
            if self._now() >= deadline:
                return self._record_terminal(
                    intent,
                    self._result(intent, "timeout", "not_started"),
                )
            context = CredentialHandlerContext(
                operation_id=intent.operation_id,
                capability_id=intent.capability_id,
                capability_version=intent.capability_version,
                reference_id=intent.reference.reference_id,
                operation_scope=intent.operation_scope,
                destination=intent.destination,
                risk_tier=intent.risk_tier,
                deadline_monotonic=deadline,
                cancellation=intent.cancellation,
            )
            try:
                with material.borrow() as credential:
                    handler_result = handler.execute(context, credential)
            except Exception:
                result = self._result(intent, "handler_failure", "unknown")
            else:
                result = self._result_from_handler(intent, handler_result)

        if intent.cancellation.is_cancelled:
            result = self._result(
                intent,
                "cancelled",
                "unknown",
                handler_result_code=result.handler_result_code,
            )
        elif self._now() >= deadline:
            result = self._result(
                intent,
                "timeout",
                "unknown",
                handler_result_code=result.handler_result_code,
            )
        return self._record_terminal(intent, result)

    def _preflight(
        self,
        intent: CredentialUseIntent,
        grant: CredentialAuthorizationGrant | None,
        deadline: float,
    ) -> CredentialOperationHandler | CredentialBrokerResult:
        if intent.cancellation.is_cancelled:
            return self._result(intent, "cancelled", "not_started")
        if self._now() >= deadline:
            return self._result(intent, "timeout", "not_started")
        if intent.reference.status != "active":
            return self._result(intent, "invalid_reference_state", "not_started")
        if intent.operation_scope not in intent.reference.allowed_operation_scope:
            return self._result(intent, "operation_out_of_scope", "not_started")
        if intent.destination not in intent.reference.allowed_destination_scope:
            return self._result(intent, "destination_out_of_scope", "not_started")
        handler = self._handlers.get(intent.capability_id, intent.capability_version)
        if handler is None:
            return self._result(intent, "handler_not_registered", "not_started")
        try:
            if (
                handler.capability_id != intent.capability_id
                or handler.capability_version != intent.capability_version
                or handler.operation_scope != intent.operation_scope
                or handler.risk_tier != "tier3"
            ):
                return self._result(intent, "handler_mismatch", "not_started")
        except Exception:
            return self._result(intent, "handler_mismatch", "not_started")
        authorization_failure = self._authorizations.consume(grant, intent)
        if authorization_failure is not None:
            return self._result(intent, authorization_failure, "not_started")
        if intent.cancellation.is_cancelled:
            return self._result(intent, "cancelled", "not_started")
        if self._now() >= deadline:
            return self._result(intent, "timeout", "not_started")
        return handler

    def _result_from_handler(
        self,
        intent: CredentialUseIntent,
        result: object,
    ) -> CredentialBrokerResult:
        if type(result) is not CredentialHandlerResult:
            return self._result(intent, "malformed_handler_result", "unknown")
        handler_result = result
        if handler_result.succeeded:
            return CredentialBrokerResult(
                operation_id=intent.operation_id,
                capability_id=intent.capability_id,
                capability_version=intent.capability_version,
                reference_id=intent.reference.reference_id,
                operation_scope=intent.operation_scope,
                destination=intent.destination,
                succeeded=True,
                failure_code=None,
                completion="completed",
                handler_result_code=handler_result.result_code,
            )
        return self._result(
            intent,
            "handler_result",
            handler_result.completion,
            handler_result_code=handler_result.result_code,
        )

    def _record_attempt(self, intent: CredentialUseIntent) -> bool:
        event = CredentialAuditEvent(
            phase="attempt",
            operation_id=intent.operation_id,
            actor_type=intent.actor_type,
            actor_id=intent.actor_id,
            capability_id=intent.capability_id,
            capability_version=intent.capability_version,
            reference_id=intent.reference.reference_id,
            credential_class=intent.reference.credential_class,
            operation_scope=intent.operation_scope,
            destination=intent.destination,
            risk_tier=intent.risk_tier,
            result="success",
        )
        try:
            self._audit.record(event)
        except Exception:
            return False
        return True

    def _record_terminal(
        self,
        intent: CredentialUseIntent,
        result: CredentialBrokerResult,
    ) -> CredentialBrokerResult:
        event = CredentialAuditEvent(
            phase="result",
            operation_id=intent.operation_id,
            actor_type=intent.actor_type,
            actor_id=intent.actor_id,
            capability_id=intent.capability_id,
            capability_version=intent.capability_version,
            reference_id=intent.reference.reference_id,
            credential_class=intent.reference.credential_class,
            operation_scope=intent.operation_scope,
            destination=intent.destination,
            risk_tier=intent.risk_tier,
            result=_audit_result(result),
            failure_code=result.failure_code,
            completion=result.completion,
            handler_result_code=result.handler_result_code,
        )
        try:
            self._audit.record(event)
        except Exception:
            return self._result(
                intent,
                "audit_failure",
                result.completion,
                handler_result_code=result.handler_result_code,
            )
        return result

    def _result(
        self,
        intent: CredentialUseIntent,
        failure_code: CredentialFailureCode,
        completion: CredentialCompletion,
        *,
        handler_result_code: str | None = None,
    ) -> CredentialBrokerResult:
        return CredentialBrokerResult(
            operation_id=intent.operation_id,
            capability_id=intent.capability_id,
            capability_version=intent.capability_version,
            reference_id=intent.reference.reference_id,
            operation_scope=intent.operation_scope,
            destination=intent.destination,
            succeeded=False,
            failure_code=failure_code,
            completion=completion,
            handler_result_code=handler_result_code,
        )

    def _now(self) -> float:
        return _safe_clock_value(self._clock, "credential broker clock")


def _require_intent(intent: CredentialUseIntent) -> None:
    if type(intent) is not CredentialUseIntent:
        raise CredentialBrokerContractError("credential broker requires a validated intent")


def _require_validated_reference(reference: SecretReferenceMetadata) -> None:
    if type(reference) is not SecretReferenceMetadata:
        raise CredentialBrokerContractError("credential broker requires a SecretReference")
    try:
        validated = validate_secret_reference_metadata(reference.as_record_metadata())
    except (SecretReferenceValidationError, TypeError, ValueError):
        raise CredentialBrokerContractError(
            "credential broker requires a validated SecretReference"
        ) from None
    if validated != reference:
        raise CredentialBrokerContractError(
            "credential broker requires a validated SecretReference"
        )


def _intent_signature(intent: CredentialUseIntent) -> tuple[object, ...]:
    return (
        intent.operation_id,
        intent.capability_id,
        intent.capability_version,
        intent.actor_type,
        intent.actor_id,
        intent.reference,
        intent.operation_scope,
        intent.destination,
        intent.risk_tier,
        float(intent.timeout_seconds),
        intent.user_presence,
        id(intent.cancellation),
    )


def _validate_authorization_ttl(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise CredentialBrokerContractError("invalid authorization TTL")
    ttl = float(value)
    if not math.isfinite(ttl) or ttl <= 0 or ttl > MAX_CREDENTIAL_AUTHORIZATION_TTL_SECONDS:
        raise CredentialBrokerContractError("invalid authorization TTL")
    return ttl


def _safe_clock_value(clock: Callable[[], float], name: str) -> float:
    try:
        raw = clock()
    except Exception:
        raise CredentialBrokerContractError(f"{name} failed") from None
    if isinstance(raw, bool) or not isinstance(raw, int | float):
        raise CredentialBrokerContractError(f"{name} failed")
    value = float(raw)
    if not math.isfinite(value) or value < 0:
        raise CredentialBrokerContractError(f"{name} failed")
    return value


def _map_store_failure(code: SecretStoreFailureCode | None) -> CredentialFailureCode:
    mapped = {
        "adapter_failure",
        "adapter_not_configured",
        "cancelled",
        "invalid_reference_state",
        "locked",
        "not_found",
        "permission_denied",
        "reference_revoked",
        "store_unavailable",
        "timeout",
        "unsupported_operation",
        "user_presence_required",
        "user_presence_unavailable",
    }
    return cast(CredentialFailureCode, code) if code in mapped else "adapter_failure"


def _audit_result(result: CredentialBrokerResult) -> AuditResult:
    if result.succeeded:
        return "success"
    if result.failure_code == "cancelled":
        return "cancelled"
    if result.completion == "unknown":
        return "partial"
    if result.failure_code in {
        "authorization_consumed",
        "authorization_expired",
        "authorization_mismatch",
        "authorization_missing",
        "destination_out_of_scope",
        "handler_mismatch",
        "handler_not_registered",
        "invalid_reference_state",
        "operation_out_of_scope",
        "permission_denied",
        "reference_revoked",
        "user_presence_required",
        "user_presence_unavailable",
    }:
        return "denied"
    return "failed"


__all__ = [
    "AuditServiceCredentialAuditSink",
    "CredentialAuthorizationAuthority",
    "CredentialBroker",
]
