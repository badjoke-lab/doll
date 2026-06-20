"""Non-secret contract types for bounded credential-bearing operations."""

from __future__ import annotations

import math
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal, Protocol, runtime_checkable

from doll.secret_material import SecretStoreCancellationToken
from doll.secret_policy import SecretReferenceMetadata
from doll.secret_store import MAX_SECRET_STORE_TIMEOUT_SECONDS, SecretStoreUserPresencePolicy

type CredentialActorType = Literal["user", "system", "model", "runtime", "capability"]
type CredentialAuditPhase = Literal["attempt", "result"]
type CredentialAuditResult = Literal["success", "denied", "failed", "cancelled", "partial"]
type CredentialCompletion = Literal["not_started", "completed", "unknown"]
type CredentialFailureCode = Literal[
    "adapter_failure",
    "adapter_not_configured",
    "audit_failure",
    "authorization_consumed",
    "authorization_expired",
    "authorization_mismatch",
    "authorization_missing",
    "cancelled",
    "destination_out_of_scope",
    "handler_failure",
    "handler_mismatch",
    "handler_not_registered",
    "handler_result",
    "invalid_reference_state",
    "locked",
    "malformed_handler_result",
    "not_found",
    "operation_out_of_scope",
    "permission_denied",
    "reference_revoked",
    "store_unavailable",
    "timeout",
    "unsupported_operation",
    "user_presence_required",
    "user_presence_unavailable",
]
type CredentialRiskTier = Literal["tier3"]

DEFAULT_CREDENTIAL_AUTHORIZATION_TTL_SECONDS = 60.0
MAX_CREDENTIAL_AUTHORIZATION_TTL_SECONDS = 300.0

_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_RESULT_CODE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,79}$")
_DESTINATION_PATTERN = re.compile(
    r"^(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)*"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?::[0-9]{1,5})?$"
)
_ALLOWED_ACTOR_TYPES = frozenset({"user", "system", "model", "runtime", "capability"})
_ALLOWED_AUDIT_PHASES = frozenset({"attempt", "result"})
_ALLOWED_AUDIT_RESULTS = frozenset({"success", "denied", "failed", "cancelled", "partial"})
_ALLOWED_COMPLETIONS = frozenset({"not_started", "completed", "unknown"})
_ALLOWED_FAILURE_CODES = frozenset(
    {
        "adapter_failure",
        "adapter_not_configured",
        "audit_failure",
        "authorization_consumed",
        "authorization_expired",
        "authorization_mismatch",
        "authorization_missing",
        "cancelled",
        "destination_out_of_scope",
        "handler_failure",
        "handler_mismatch",
        "handler_not_registered",
        "handler_result",
        "invalid_reference_state",
        "locked",
        "malformed_handler_result",
        "not_found",
        "operation_out_of_scope",
        "permission_denied",
        "reference_revoked",
        "store_unavailable",
        "timeout",
        "unsupported_operation",
        "user_presence_required",
        "user_presence_unavailable",
    }
)
_ALLOWED_RISK_TIERS = frozenset({"tier3"})
_ALLOWED_USER_PRESENCE = frozenset({"forbid", "allow", "require"})


class CredentialBrokerContractError(RuntimeError):
    """Raised when a caller or trusted component violates the broker contract."""


@dataclass(frozen=True, slots=True)
class CredentialUseIntent:
    """Exact non-secret operation proposed to the Credential Broker."""

    operation_id: str
    capability_id: str
    capability_version: int
    actor_type: CredentialActorType
    reference: SecretReferenceMetadata
    operation_scope: str
    destination: str
    actor_id: str | None = None
    risk_tier: CredentialRiskTier = "tier3"
    timeout_seconds: float = 30.0
    user_presence: SecretStoreUserPresencePolicy = "forbid"
    cancellation: SecretStoreCancellationToken = field(
        default_factory=SecretStoreCancellationToken,
        repr=False,
    )

    def __post_init__(self) -> None:
        _validate_token("operation ID", self.operation_id)
        _validate_token("capability ID", self.capability_id)
        _validate_version(self.capability_version)
        if not isinstance(self.actor_type, str) or self.actor_type not in _ALLOWED_ACTOR_TYPES:
            raise CredentialBrokerContractError("invalid credential actor type")
        if self.actor_id is not None:
            _validate_token("actor ID", self.actor_id)
        if type(self.reference) is not SecretReferenceMetadata:
            raise CredentialBrokerContractError("credential intent requires a SecretReference")
        _validate_token("operation scope", self.operation_scope)
        _validate_destination(self.destination)
        if not isinstance(self.risk_tier, str) or self.risk_tier not in _ALLOWED_RISK_TIERS:
            raise CredentialBrokerContractError("credential operations require Tier 3 risk")
        _validate_timeout(self.timeout_seconds)
        if (
            not isinstance(self.user_presence, str)
            or self.user_presence not in _ALLOWED_USER_PRESENCE
        ):
            raise CredentialBrokerContractError("invalid credential user-presence policy")
        if not isinstance(self.cancellation, SecretStoreCancellationToken):
            raise CredentialBrokerContractError("invalid credential cancellation token")


@dataclass(frozen=True, slots=True)
class CredentialAuthorizationGrant:
    """Non-secret exact-binding token issued by a trusted in-memory authority."""

    grant_id: str
    operation_id: str
    capability_id: str
    capability_version: int
    reference_id: str
    operation_scope: str
    destination: str
    risk_tier: CredentialRiskTier
    expires_at_monotonic: float

    def __post_init__(self) -> None:
        _validate_token("authorization grant ID", self.grant_id)
        _validate_token("operation ID", self.operation_id)
        _validate_token("capability ID", self.capability_id)
        _validate_version(self.capability_version)
        _validate_token("reference ID", self.reference_id)
        _validate_token("operation scope", self.operation_scope)
        _validate_destination(self.destination)
        if not isinstance(self.risk_tier, str) or self.risk_tier not in _ALLOWED_RISK_TIERS:
            raise CredentialBrokerContractError("invalid authorization risk tier")
        _validate_monotonic("authorization expiry", self.expires_at_monotonic)


@dataclass(frozen=True, slots=True)
class CredentialHandlerContext:
    """Bounded execution context supplied only to a registered trusted handler."""

    operation_id: str
    capability_id: str
    capability_version: int
    reference_id: str
    operation_scope: str
    destination: str
    risk_tier: CredentialRiskTier
    deadline_monotonic: float
    cancellation: SecretStoreCancellationToken = field(repr=False)

    def __post_init__(self) -> None:
        _validate_token("operation ID", self.operation_id)
        _validate_token("capability ID", self.capability_id)
        _validate_version(self.capability_version)
        _validate_token("reference ID", self.reference_id)
        _validate_token("operation scope", self.operation_scope)
        _validate_destination(self.destination)
        if not isinstance(self.risk_tier, str) or self.risk_tier not in _ALLOWED_RISK_TIERS:
            raise CredentialBrokerContractError("invalid handler risk tier")
        _validate_monotonic("handler deadline", self.deadline_monotonic)
        if not isinstance(self.cancellation, SecretStoreCancellationToken):
            raise CredentialBrokerContractError("invalid handler cancellation token")


@dataclass(frozen=True, slots=True)
class CredentialHandlerResult:
    """Closed non-secret result returned by one trusted credential handler."""

    succeeded: bool
    result_code: str
    completion: CredentialCompletion

    def __post_init__(self) -> None:
        if not isinstance(self.succeeded, bool):
            raise CredentialBrokerContractError("invalid credential handler success state")
        _validate_result_code(self.result_code)
        _validate_completion(self.completion)
        if self.succeeded and self.completion != "completed":
            raise CredentialBrokerContractError("successful handler result must be completed")
        if not self.succeeded and self.completion == "not_started":
            raise CredentialBrokerContractError(
                "invoked handler result cannot claim that execution never started"
            )


@dataclass(frozen=True, slots=True)
class CredentialBrokerResult:
    """Bounded non-secret result returned to models and ordinary callers."""

    operation_id: str
    capability_id: str
    capability_version: int
    reference_id: str
    operation_scope: str
    destination: str
    succeeded: bool
    failure_code: CredentialFailureCode | None
    completion: CredentialCompletion
    handler_result_code: str | None = None

    def __post_init__(self) -> None:
        _validate_token("operation ID", self.operation_id)
        _validate_token("capability ID", self.capability_id)
        _validate_version(self.capability_version)
        _validate_token("reference ID", self.reference_id)
        _validate_token("operation scope", self.operation_scope)
        _validate_destination(self.destination)
        if not isinstance(self.succeeded, bool):
            raise CredentialBrokerContractError("invalid broker success state")
        _validate_completion(self.completion)
        if self.failure_code is not None and (
            not isinstance(self.failure_code, str)
            or self.failure_code not in _ALLOWED_FAILURE_CODES
        ):
            raise CredentialBrokerContractError("invalid broker failure code")
        if self.handler_result_code is not None:
            _validate_result_code(self.handler_result_code)
        if self.succeeded:
            if (
                self.failure_code is not None
                or self.completion != "completed"
                or self.handler_result_code is None
            ):
                raise CredentialBrokerContractError("invalid successful broker result")
        elif self.failure_code is None:
            raise CredentialBrokerContractError("failed broker result requires a failure code")


@dataclass(frozen=True, slots=True)
class CredentialAuditEvent:
    """Secret-free audit event emitted before and after broker execution."""

    phase: CredentialAuditPhase
    operation_id: str
    actor_type: CredentialActorType
    capability_id: str
    capability_version: int
    reference_id: str
    credential_class: str
    operation_scope: str
    destination: str
    risk_tier: CredentialRiskTier
    result: CredentialAuditResult
    actor_id: str | None = None
    failure_code: CredentialFailureCode | None = None
    completion: CredentialCompletion | None = None
    handler_result_code: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.phase, str) or self.phase not in _ALLOWED_AUDIT_PHASES:
            raise CredentialBrokerContractError("invalid credential audit phase")
        _validate_token("operation ID", self.operation_id)
        if not isinstance(self.actor_type, str) or self.actor_type not in _ALLOWED_ACTOR_TYPES:
            raise CredentialBrokerContractError("invalid credential audit actor")
        if self.actor_id is not None:
            _validate_token("actor ID", self.actor_id)
        _validate_token("capability ID", self.capability_id)
        _validate_version(self.capability_version)
        _validate_token("reference ID", self.reference_id)
        _validate_token("credential class", self.credential_class)
        _validate_token("operation scope", self.operation_scope)
        _validate_destination(self.destination)
        if not isinstance(self.risk_tier, str) or self.risk_tier not in _ALLOWED_RISK_TIERS:
            raise CredentialBrokerContractError("invalid credential audit risk tier")
        if not isinstance(self.result, str) or self.result not in _ALLOWED_AUDIT_RESULTS:
            raise CredentialBrokerContractError("invalid credential audit result")
        if self.failure_code is not None and (
            not isinstance(self.failure_code, str)
            or self.failure_code not in _ALLOWED_FAILURE_CODES
        ):
            raise CredentialBrokerContractError("invalid credential audit failure code")
        if self.completion is not None:
            _validate_completion(self.completion)
        if self.handler_result_code is not None:
            _validate_result_code(self.handler_result_code)
        if self.phase == "attempt":
            if (
                self.result != "success"
                or self.failure_code is not None
                or self.completion is not None
                or self.handler_result_code is not None
            ):
                raise CredentialBrokerContractError("invalid credential attempt audit event")
        elif self.completion is None:
            raise CredentialBrokerContractError("credential result audit requires completion")


@runtime_checkable
class CredentialOperationHandler(Protocol):
    """Trusted bounded operation that may receive a transient credential view."""

    @property
    def capability_id(self) -> str: ...

    @property
    def capability_version(self) -> int: ...

    @property
    def operation_scope(self) -> str: ...

    @property
    def risk_tier(self) -> CredentialRiskTier: ...

    def execute(
        self,
        context: CredentialHandlerContext,
        credential: memoryview,
    ) -> CredentialHandlerResult: ...


@runtime_checkable
class CredentialAuditSink(Protocol):
    """Trusted secret-free audit sink required by the broker."""

    def record(self, event: CredentialAuditEvent) -> None: ...


class CredentialHandlerRegistry:
    """Immutable exact-version registry for trusted credential handlers."""

    __slots__ = ("_handlers",)

    def __init__(self, handlers: Iterable[CredentialOperationHandler] = ()) -> None:
        registered: dict[tuple[str, int], CredentialOperationHandler] = {}
        for handler in handlers:
            try:
                if not isinstance(handler, CredentialOperationHandler):
                    raise TypeError
                capability_id = _validate_token("handler capability ID", handler.capability_id)
                capability_version = _validate_version(handler.capability_version)
                _validate_token("handler operation scope", handler.operation_scope)
                if "*" in handler.operation_scope:
                    raise CredentialBrokerContractError(
                        "credential handler operation scope must be exact"
                    )
                if handler.risk_tier != "tier3":
                    raise CredentialBrokerContractError(
                        "credential handlers must use Tier 3 risk"
                    )
            except Exception:
                raise CredentialBrokerContractError(
                    "invalid credential handler registration"
                ) from None
            key = (capability_id, capability_version)
            if key in registered:
                raise CredentialBrokerContractError("duplicate credential handler registration")
            registered[key] = handler
        self._handlers = MappingProxyType(registered)

    @property
    def handler_keys(self) -> tuple[tuple[str, int], ...]:
        return tuple(sorted(self._handlers))

    def get(self, capability_id: str, capability_version: int) -> CredentialOperationHandler | None:
        safe_id = _validate_token("capability ID", capability_id)
        safe_version = _validate_version(capability_version)
        return self._handlers.get((safe_id, safe_version))

    def __repr__(self) -> str:
        return f"<CredentialHandlerRegistry handlers={self.handler_keys!r}>"


def _validate_token(name: str, value: str) -> str:
    if not isinstance(value, str) or _TOKEN_PATTERN.fullmatch(value) is None:
        raise CredentialBrokerContractError(f"invalid {name}")
    if "*" in value:
        raise CredentialBrokerContractError(f"{name} must be exact")
    return value


def _validate_result_code(value: str) -> str:
    if not isinstance(value, str) or _RESULT_CODE_PATTERN.fullmatch(value) is None:
        raise CredentialBrokerContractError("invalid credential result code")
    return value


def _validate_destination(value: str) -> str:
    if not isinstance(value, str) or _DESTINATION_PATTERN.fullmatch(value) is None:
        raise CredentialBrokerContractError("invalid credential destination")
    if "*" in value:
        raise CredentialBrokerContractError("credential destination must be exact")
    if ":" in value:
        port_text = value.rsplit(":", 1)[1]
        if not port_text.isdigit() or not 1 <= int(port_text) <= 65535:
            raise CredentialBrokerContractError("invalid credential destination port")
    return value.lower()


def _validate_version(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 9999:
        raise CredentialBrokerContractError("invalid credential capability version")
    return value


def _validate_timeout(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise CredentialBrokerContractError("invalid credential timeout")
    timeout = float(value)
    if not math.isfinite(timeout) or timeout <= 0 or timeout > MAX_SECRET_STORE_TIMEOUT_SECONDS:
        raise CredentialBrokerContractError("invalid credential timeout")
    return timeout


def _validate_monotonic(name: str, value: float) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, int | float)
        or not math.isfinite(float(value))
        or float(value) < 0
    ):
        raise CredentialBrokerContractError(f"invalid {name}")
    return float(value)


def _validate_completion(value: CredentialCompletion) -> CredentialCompletion:
    if not isinstance(value, str) or value not in _ALLOWED_COMPLETIONS:
        raise CredentialBrokerContractError("invalid credential completion state")
    return value


__all__ = [
    "DEFAULT_CREDENTIAL_AUTHORIZATION_TTL_SECONDS",
    "MAX_CREDENTIAL_AUTHORIZATION_TTL_SECONDS",
    "CredentialActorType",
    "CredentialAuditEvent",
    "CredentialAuditPhase",
    "CredentialAuditResult",
    "CredentialAuditSink",
    "CredentialAuthorizationGrant",
    "CredentialBrokerContractError",
    "CredentialBrokerResult",
    "CredentialCompletion",
    "CredentialFailureCode",
    "CredentialHandlerContext",
    "CredentialHandlerRegistry",
    "CredentialHandlerResult",
    "CredentialOperationHandler",
    "CredentialRiskTier",
    "CredentialUseIntent",
]
