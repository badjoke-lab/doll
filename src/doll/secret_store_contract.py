"""Non-secret types and adapter protocol for external secret stores."""

from __future__ import annotations

import math
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from types import MappingProxyType, TracebackType
from typing import Literal, Protocol, runtime_checkable

from doll.secret_material import (
    SecretMaterial,
    SecretStoreCancellationToken,
    SecretStoreContractError,
)
from doll.secret_policy import SecretReferenceMetadata

type SecretStoreOperation = Literal["create", "replace", "lookup", "revoke", "delete"]
type SecretStoreAvailability = Literal["available", "unavailable"]
type SecretStoreLockState = Literal["unlocked", "locked", "unknown", "not_applicable"]
type SecretStoreUserPresence = Literal["none", "optional", "required", "unknown"]
type SecretStoreUserPresencePolicy = Literal["forbid", "allow", "require"]
type SecretStoreCompletion = Literal["confirmed", "not_completed", "unknown"]
type SecretStoreFailureCode = Literal[
    "adapter_not_configured",
    "adapter_failure",
    "already_exists",
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
]

DEFAULT_SECRET_STORE_TIMEOUT_SECONDS = 30.0
MAX_SECRET_STORE_TIMEOUT_SECONDS = 300.0

_ADAPTER_CLASS_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,79}$")
_OPERATION_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_REFERENCE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_ALLOWED_OPERATIONS = frozenset({"create", "replace", "lookup", "revoke", "delete"})
_ALLOWED_AVAILABILITY = frozenset({"available", "unavailable"})
_ALLOWED_LOCK_STATES = frozenset({"unlocked", "locked", "unknown", "not_applicable"})
_ALLOWED_USER_PRESENCE = frozenset({"none", "optional", "required", "unknown"})
_ALLOWED_USER_PRESENCE_POLICIES = frozenset({"forbid", "allow", "require"})
_ALLOWED_COMPLETION = frozenset({"confirmed", "not_completed", "unknown"})
_ALLOWED_FAILURE_CODES = frozenset(
    {
        "adapter_not_configured",
        "adapter_failure",
        "already_exists",
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
)
_STATUS_FAILURE_CODES = frozenset(
    {"adapter_not_configured", "adapter_failure", "store_unavailable"}
)


class SecretStoreAdapterFailure(RuntimeError):
    """Safe adapter failure carrying only a closed code and completion state."""

    def __init__(
        self,
        code: SecretStoreFailureCode,
        *,
        completion: SecretStoreCompletion = "not_completed",
    ) -> None:
        if not isinstance(code, str) or code not in _ALLOWED_FAILURE_CODES:
            raise SecretStoreContractError("invalid secret-store adapter failure code")
        if (
            not isinstance(completion, str)
            or completion not in _ALLOWED_COMPLETION
            or completion == "confirmed"
        ):
            raise SecretStoreContractError("invalid secret-store adapter completion state")
        self.code = code
        self.completion = completion
        super().__init__(f"secret-store adapter failure: {code}")


@dataclass(frozen=True, slots=True)
class SecretStoreRequest:
    """Bounded caller-controlled operation requirements."""

    operation_id: str
    timeout_seconds: float = DEFAULT_SECRET_STORE_TIMEOUT_SECONDS
    user_presence: SecretStoreUserPresencePolicy = "forbid"
    cancellation: SecretStoreCancellationToken = field(
        default_factory=SecretStoreCancellationToken,
        repr=False,
    )

    def __post_init__(self) -> None:
        if (
            not isinstance(self.operation_id, str)
            or _OPERATION_ID_PATTERN.fullmatch(self.operation_id) is None
        ):
            raise SecretStoreContractError("invalid secret-store operation ID")
        if isinstance(self.timeout_seconds, bool) or not isinstance(
            self.timeout_seconds, int | float
        ):
            raise SecretStoreContractError("invalid secret-store timeout")
        timeout = float(self.timeout_seconds)
        if not math.isfinite(timeout) or timeout <= 0 or timeout > MAX_SECRET_STORE_TIMEOUT_SECONDS:
            raise SecretStoreContractError("invalid secret-store timeout")
        if (
            not isinstance(self.user_presence, str)
            or self.user_presence not in _ALLOWED_USER_PRESENCE_POLICIES
        ):
            raise SecretStoreContractError("invalid secret-store user-presence policy")
        if not isinstance(self.cancellation, SecretStoreCancellationToken):
            raise SecretStoreContractError("invalid secret-store cancellation token")


@dataclass(frozen=True, slots=True)
class SecretStoreAdapterContext:
    """Trusted adapter context with a monotonic deadline and cooperative cancellation."""

    operation_id: str
    deadline_monotonic: float
    user_presence: SecretStoreUserPresencePolicy
    cancellation: SecretStoreCancellationToken = field(repr=False)

    def __post_init__(self) -> None:
        if (
            not isinstance(self.operation_id, str)
            or _OPERATION_ID_PATTERN.fullmatch(self.operation_id) is None
        ):
            raise SecretStoreContractError("invalid adapter operation ID")
        if (
            isinstance(self.deadline_monotonic, bool)
            or not isinstance(self.deadline_monotonic, int | float)
            or not math.isfinite(self.deadline_monotonic)
        ):
            raise SecretStoreContractError("invalid adapter deadline")
        if (
            not isinstance(self.user_presence, str)
            or self.user_presence not in _ALLOWED_USER_PRESENCE_POLICIES
        ):
            raise SecretStoreContractError("invalid adapter user-presence policy")
        if not isinstance(self.cancellation, SecretStoreCancellationToken):
            raise SecretStoreContractError("invalid adapter cancellation token")


@dataclass(frozen=True, slots=True)
class SecretStoreStatus:
    """Non-secret adapter availability and interaction requirements."""

    adapter_class: str
    availability: SecretStoreAvailability
    lock_state: SecretStoreLockState
    user_presence: SecretStoreUserPresence
    supported_operations: tuple[SecretStoreOperation, ...]
    failure_code: SecretStoreFailureCode | None = None

    def __post_init__(self) -> None:
        validate_adapter_class(self.adapter_class)
        if not isinstance(self.availability, str) or self.availability not in _ALLOWED_AVAILABILITY:
            raise SecretStoreContractError("invalid secret-store availability")
        if not isinstance(self.lock_state, str) or self.lock_state not in _ALLOWED_LOCK_STATES:
            raise SecretStoreContractError("invalid secret-store lock state")
        if (
            not isinstance(self.user_presence, str)
            or self.user_presence not in _ALLOWED_USER_PRESENCE
        ):
            raise SecretStoreContractError("invalid secret-store user-presence state")
        if not isinstance(self.supported_operations, tuple):
            raise SecretStoreContractError("secret-store operations must use a tuple")
        operations = self.supported_operations
        if any(
            not isinstance(operation, str) or operation not in _ALLOWED_OPERATIONS
            for operation in operations
        ):
            raise SecretStoreContractError("invalid secret-store supported operation")
        if len(set(operations)) != len(operations) or operations != tuple(sorted(operations)):
            raise SecretStoreContractError(
                "secret-store supported operations must be unique and sorted"
            )
        if self.failure_code is not None and (
            not isinstance(self.failure_code, str) or self.failure_code not in _STATUS_FAILURE_CODES
        ):
            raise SecretStoreContractError("invalid secret-store status failure code")
        if self.availability == "available" and self.failure_code is not None:
            raise SecretStoreContractError("available secret store must not report a failure code")
        if self.availability == "unavailable":
            if self.failure_code is None:
                raise SecretStoreContractError("unavailable secret store requires a failure code")
            if operations:
                raise SecretStoreContractError(
                    "unavailable secret store must not advertise operations"
                )
            if self.lock_state != "unknown" or self.user_presence != "unknown":
                raise SecretStoreContractError(
                    "unavailable secret store must report unknown interaction state"
                )


@dataclass(frozen=True, slots=True)
class SecretStoreOperationResult:
    """Non-secret lifecycle result with explicit completion certainty."""

    operation: SecretStoreOperation
    reference_id: str
    adapter_class: str
    succeeded: bool
    failure_code: SecretStoreFailureCode | None
    completion: SecretStoreCompletion

    def __post_init__(self) -> None:
        if not isinstance(self.operation, str) or self.operation not in _ALLOWED_OPERATIONS:
            raise SecretStoreContractError("invalid secret-store result operation")
        if (
            not isinstance(self.reference_id, str)
            or _REFERENCE_ID_PATTERN.fullmatch(self.reference_id) is None
        ):
            raise SecretStoreContractError("invalid secret-store result reference")
        validate_adapter_class(self.adapter_class)
        if not isinstance(self.succeeded, bool):
            raise SecretStoreContractError("invalid secret-store success state")
        if not isinstance(self.completion, str) or self.completion not in _ALLOWED_COMPLETION:
            raise SecretStoreContractError("invalid secret-store completion state")
        if self.failure_code is not None and (
            not isinstance(self.failure_code, str)
            or self.failure_code not in _ALLOWED_FAILURE_CODES
        ):
            raise SecretStoreContractError("invalid secret-store result failure code")
        if self.succeeded:
            if self.failure_code is not None or self.completion != "confirmed":
                raise SecretStoreContractError("invalid successful secret-store result")
        elif self.failure_code is None or self.completion == "confirmed":
            raise SecretStoreContractError("invalid failed secret-store result")


@dataclass(slots=True)
class SecretStoreLookupResult:
    """Lookup result that owns transient material and never renders it."""

    result: SecretStoreOperationResult
    material: SecretMaterial | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.result, SecretStoreOperationResult):
            raise SecretStoreContractError("invalid lookup result")
        if self.material is not None and not isinstance(self.material, SecretMaterial):
            raise SecretStoreContractError("invalid lookup material")
        if self.result.operation != "lookup":
            raise SecretStoreContractError("lookup result requires lookup operation")
        if self.result.succeeded:
            if self.material is None or self.material.is_closed:
                raise SecretStoreContractError("successful lookup requires open secret material")
        elif self.material is not None:
            self.material.close()
            self.material = None

    @property
    def succeeded(self) -> bool:
        return self.result.succeeded

    def close(self) -> None:
        if self.material is not None:
            self.material.close()
            self.material = None

    def __enter__(self) -> SecretStoreLookupResult:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc, traceback
        self.close()


@runtime_checkable
class SecretStoreAdapter(Protocol):
    """Authoritative replaceable contract implemented by platform-specific adapters."""

    @property
    def adapter_class(self) -> str: ...

    def status(self) -> SecretStoreStatus: ...

    def create(
        self,
        reference: SecretReferenceMetadata,
        material: SecretMaterial,
        context: SecretStoreAdapterContext,
    ) -> None: ...

    def replace(
        self,
        reference: SecretReferenceMetadata,
        material: SecretMaterial,
        context: SecretStoreAdapterContext,
    ) -> None: ...

    def lookup(
        self,
        reference: SecretReferenceMetadata,
        context: SecretStoreAdapterContext,
    ) -> SecretMaterial: ...

    def revoke(
        self,
        reference: SecretReferenceMetadata,
        context: SecretStoreAdapterContext,
    ) -> None: ...

    def delete(
        self,
        reference: SecretReferenceMetadata,
        context: SecretStoreAdapterContext,
    ) -> None: ...


class SecretStoreRegistry:
    """Immutable adapter registry; absence is valid and keeps core startup available."""

    __slots__ = ("_adapters",)

    def __init__(self, adapters: Iterable[SecretStoreAdapter] = ()) -> None:
        registered: dict[str, SecretStoreAdapter] = {}
        for adapter in adapters:
            try:
                if not isinstance(adapter, SecretStoreAdapter):
                    raise TypeError
                adapter_class = validate_adapter_class(adapter.adapter_class)
            except Exception:
                raise SecretStoreContractError(
                    "invalid secret-store adapter registration"
                ) from None
            if adapter_class in registered:
                raise SecretStoreContractError("duplicate secret-store adapter class")
            registered[adapter_class] = adapter
        self._adapters = MappingProxyType(registered)

    @property
    def adapter_classes(self) -> tuple[str, ...]:
        return tuple(sorted(self._adapters))

    def get(self, adapter_class: str) -> SecretStoreAdapter | None:
        normalized = validate_adapter_class(adapter_class)
        return self._adapters.get(normalized)

    def __repr__(self) -> str:
        return f"<SecretStoreRegistry adapters={self.adapter_classes!r}>"


def validate_adapter_class(value: str) -> str:
    if not isinstance(value, str) or _ADAPTER_CLASS_PATTERN.fullmatch(value) is None:
        raise SecretStoreContractError("invalid secret-store adapter class")
    return value


def unavailable_status(
    adapter_class: str,
    code: Literal["adapter_not_configured", "adapter_failure", "store_unavailable"],
) -> SecretStoreStatus:
    return SecretStoreStatus(
        adapter_class=adapter_class,
        availability="unavailable",
        lock_state="unknown",
        user_presence="unknown",
        supported_operations=(),
        failure_code=code,
    )


__all__ = [
    "DEFAULT_SECRET_STORE_TIMEOUT_SECONDS",
    "MAX_SECRET_STORE_TIMEOUT_SECONDS",
    "SecretStoreAdapter",
    "SecretStoreAdapterContext",
    "SecretStoreAdapterFailure",
    "SecretStoreAvailability",
    "SecretStoreCompletion",
    "SecretStoreFailureCode",
    "SecretStoreLockState",
    "SecretStoreLookupResult",
    "SecretStoreOperation",
    "SecretStoreOperationResult",
    "SecretStoreRegistry",
    "SecretStoreRequest",
    "SecretStoreStatus",
    "SecretStoreUserPresence",
    "SecretStoreUserPresencePolicy",
    "unavailable_status",
    "validate_adapter_class",
]
