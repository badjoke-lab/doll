"""Replaceable, model-independent external secret-store boundary."""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from typing import Literal

from doll.secret_material import (
    MAX_SECRET_MATERIAL_BYTES,
    SecretMaterial,
    SecretMaterialClosedError,
    SecretStoreCancellationToken,
    SecretStoreContractError,
)
from doll.secret_policy import (
    SecretReferenceMetadata,
    SecretReferenceValidationError,
    validate_secret_reference_metadata,
)
from doll.secret_store_contract import (
    DEFAULT_SECRET_STORE_TIMEOUT_SECONDS,
    MAX_SECRET_STORE_TIMEOUT_SECONDS,
    SecretStoreAdapter,
    SecretStoreAdapterContext,
    SecretStoreAdapterFailure,
    SecretStoreAvailability,
    SecretStoreCompletion,
    SecretStoreFailureCode,
    SecretStoreLockState,
    SecretStoreLookupResult,
    SecretStoreOperation,
    SecretStoreOperationResult,
    SecretStoreRegistry,
    SecretStoreRequest,
    SecretStoreStatus,
    SecretStoreUserPresence,
    SecretStoreUserPresencePolicy,
    unavailable_status,
    validate_adapter_class,
)


class ExternalSecretStore:
    """Failure-isolating boundary around registered secret-store adapters."""

    __slots__ = ("_clock", "_registry")

    def __init__(
        self,
        registry: SecretStoreRegistry | None = None,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if registry is not None and not isinstance(registry, SecretStoreRegistry):
            raise SecretStoreContractError("invalid secret-store registry")
        if not callable(clock):
            raise SecretStoreContractError("invalid secret-store clock")
        self._registry = registry if registry is not None else SecretStoreRegistry()
        self._clock = clock

    def status(self, adapter_class: str) -> SecretStoreStatus:
        normalized = validate_adapter_class(adapter_class)
        adapter = self._registry.get(normalized)
        if adapter is None:
            return unavailable_status(normalized, "adapter_not_configured")
        return self._adapter_status(normalized, adapter)

    def create(
        self,
        reference: SecretReferenceMetadata,
        material: SecretMaterial,
        request: SecretStoreRequest,
    ) -> SecretStoreOperationResult:
        return self._write_operation("create", reference, material, request)

    def replace(
        self,
        reference: SecretReferenceMetadata,
        material: SecretMaterial,
        request: SecretStoreRequest,
    ) -> SecretStoreOperationResult:
        return self._write_operation("replace", reference, material, request)

    def lookup(
        self,
        reference: SecretReferenceMetadata,
        request: SecretStoreRequest,
    ) -> SecretStoreLookupResult:
        prepared = self._prepare("lookup", reference, request)
        if isinstance(prepared, SecretStoreOperationResult):
            return SecretStoreLookupResult(prepared)
        adapter, context = prepared
        material: SecretMaterial | None = None
        try:
            material = adapter.lookup(reference, context)
            if not isinstance(material, SecretMaterial) or material.is_closed:
                if isinstance(material, SecretMaterial):
                    material.close()
                return SecretStoreLookupResult(
                    self._failure("lookup", reference, "adapter_failure", "not_completed")
                )
        except SecretStoreAdapterFailure as exc:
            return SecretStoreLookupResult(
                self._failure("lookup", reference, exc.code, "not_completed")
            )
        except Exception:
            return SecretStoreLookupResult(
                self._failure("lookup", reference, "adapter_failure", "not_completed")
            )
        if request.cancellation.is_cancelled:
            material.close()
            return SecretStoreLookupResult(
                self._failure("lookup", reference, "cancelled", "not_completed")
            )
        if self._now() >= context.deadline_monotonic:
            material.close()
            return SecretStoreLookupResult(
                self._failure("lookup", reference, "timeout", "not_completed")
            )
        return SecretStoreLookupResult(self._success("lookup", reference), material)

    def revoke(
        self,
        reference: SecretReferenceMetadata,
        request: SecretStoreRequest,
    ) -> SecretStoreOperationResult:
        return self._no_material_operation("revoke", reference, request)

    def delete(
        self,
        reference: SecretReferenceMetadata,
        request: SecretStoreRequest,
    ) -> SecretStoreOperationResult:
        return self._no_material_operation("delete", reference, request)

    def _write_operation(
        self,
        operation: Literal["create", "replace"],
        reference: SecretReferenceMetadata,
        material: SecretMaterial,
        request: SecretStoreRequest,
    ) -> SecretStoreOperationResult:
        if not isinstance(material, SecretMaterial):
            raise SecretStoreContractError("secret-store write requires SecretMaterial")
        if material.is_closed:
            raise SecretMaterialClosedError("secret material is closed")
        try:
            prepared = self._prepare(operation, reference, request)
            if isinstance(prepared, SecretStoreOperationResult):
                return prepared
            adapter, context = prepared
            try:
                if operation == "create":
                    adapter.create(reference, material, context)
                else:
                    adapter.replace(reference, material, context)
            except SecretStoreAdapterFailure as exc:
                return self._failure(operation, reference, exc.code, exc.completion)
            except Exception:
                return self._failure(operation, reference, "adapter_failure", "unknown")
            return self._post_mutation_result(operation, reference, request, context)
        finally:
            material.close()

    def _no_material_operation(
        self,
        operation: Literal["revoke", "delete"],
        reference: SecretReferenceMetadata,
        request: SecretStoreRequest,
    ) -> SecretStoreOperationResult:
        prepared = self._prepare(operation, reference, request)
        if isinstance(prepared, SecretStoreOperationResult):
            return prepared
        adapter, context = prepared
        try:
            if operation == "revoke":
                adapter.revoke(reference, context)
            else:
                adapter.delete(reference, context)
        except SecretStoreAdapterFailure as exc:
            return self._failure(operation, reference, exc.code, exc.completion)
        except Exception:
            return self._failure(operation, reference, "adapter_failure", "unknown")
        return self._post_mutation_result(operation, reference, request, context)

    def _prepare(
        self,
        operation: SecretStoreOperation,
        reference: SecretReferenceMetadata,
        request: SecretStoreRequest,
    ) -> tuple[SecretStoreAdapter, SecretStoreAdapterContext] | SecretStoreOperationResult:
        _require_validated_reference(reference)
        if not isinstance(request, SecretStoreRequest):
            raise SecretStoreContractError("secret-store operation requires a validated request")
        reference_failure = _reference_state_failure(operation, reference)
        if reference_failure is not None:
            return self._failure(operation, reference, reference_failure, "not_completed")
        if request.cancellation.is_cancelled:
            return self._failure(operation, reference, "cancelled", "not_completed")
        deadline = self._now() + float(request.timeout_seconds)
        adapter = self._registry.get(reference.store_adapter_class)
        if adapter is None:
            return self._failure(
                operation, reference, "adapter_not_configured", "not_completed"
            )
        status = self._adapter_status(reference.store_adapter_class, adapter)
        if request.cancellation.is_cancelled:
            return self._failure(operation, reference, "cancelled", "not_completed")
        if self._now() >= deadline:
            return self._failure(operation, reference, "timeout", "not_completed")
        if status.availability == "unavailable":
            return self._failure(
                operation,
                reference,
                status.failure_code or "store_unavailable",
                "not_completed",
            )
        if operation not in status.supported_operations:
            return self._failure(
                operation, reference, "unsupported_operation", "not_completed"
            )
        if status.lock_state == "locked":
            return self._failure(operation, reference, "locked", "not_completed")
        presence_failure = _user_presence_failure(request.user_presence, status.user_presence)
        if presence_failure is not None:
            return self._failure(operation, reference, presence_failure, "not_completed")
        return adapter, SecretStoreAdapterContext(
            operation_id=request.operation_id,
            deadline_monotonic=deadline,
            user_presence=request.user_presence,
            cancellation=request.cancellation,
        )

    def _adapter_status(
        self,
        adapter_class: str,
        adapter: SecretStoreAdapter,
    ) -> SecretStoreStatus:
        try:
            if adapter.adapter_class != adapter_class:
                return unavailable_status(adapter_class, "adapter_failure")
            status = adapter.status()
        except Exception:
            return unavailable_status(adapter_class, "adapter_failure")
        if not isinstance(status, SecretStoreStatus) or status.adapter_class != adapter_class:
            return unavailable_status(adapter_class, "adapter_failure")
        return status

    def _post_mutation_result(
        self,
        operation: SecretStoreOperation,
        reference: SecretReferenceMetadata,
        request: SecretStoreRequest,
        context: SecretStoreAdapterContext,
    ) -> SecretStoreOperationResult:
        if request.cancellation.is_cancelled:
            return self._failure(operation, reference, "cancelled", "unknown")
        if self._now() >= context.deadline_monotonic:
            return self._failure(operation, reference, "timeout", "unknown")
        return self._success(operation, reference)

    def _now(self) -> float:
        try:
            raw_value = self._clock()
        except Exception:
            raise SecretStoreContractError("secret-store clock failed") from None
        if isinstance(raw_value, bool) or not isinstance(raw_value, int | float):
            raise SecretStoreContractError("secret-store clock failed")
        value = float(raw_value)
        if not math.isfinite(value):
            raise SecretStoreContractError("secret-store clock failed")
        return value

    @staticmethod
    def _success(
        operation: SecretStoreOperation,
        reference: SecretReferenceMetadata,
    ) -> SecretStoreOperationResult:
        return SecretStoreOperationResult(
            operation=operation,
            reference_id=reference.reference_id,
            adapter_class=reference.store_adapter_class,
            succeeded=True,
            failure_code=None,
            completion="confirmed",
        )

    @staticmethod
    def _failure(
        operation: SecretStoreOperation,
        reference: SecretReferenceMetadata,
        code: SecretStoreFailureCode,
        completion: SecretStoreCompletion,
    ) -> SecretStoreOperationResult:
        return SecretStoreOperationResult(
            operation=operation,
            reference_id=reference.reference_id,
            adapter_class=reference.store_adapter_class,
            succeeded=False,
            failure_code=code,
            completion=completion,
        )


def _require_validated_reference(reference: SecretReferenceMetadata) -> None:
    if type(reference) is not SecretReferenceMetadata:
        raise SecretStoreContractError("secret-store operation requires a validated reference")
    try:
        validated = validate_secret_reference_metadata(reference.as_record_metadata())
    except (SecretReferenceValidationError, TypeError, ValueError):
        raise SecretStoreContractError(
            "secret-store operation requires a validated reference"
        ) from None
    if validated != reference:
        raise SecretStoreContractError("secret-store operation requires a validated reference")


def _reference_state_failure(
    operation: SecretStoreOperation,
    reference: SecretReferenceMetadata,
) -> SecretStoreFailureCode | None:
    if reference.status == "revoked" and operation != "delete":
        return "reference_revoked"
    if operation == "create" and reference.status != "active":
        return "invalid_reference_state"
    return None


def _user_presence_failure(
    policy: SecretStoreUserPresencePolicy,
    capability: SecretStoreUserPresence,
) -> SecretStoreFailureCode | None:
    if policy == "forbid" and capability != "none":
        return "user_presence_required"
    if policy == "require" and capability not in {"optional", "required"}:
        return "user_presence_unavailable"
    return None


__all__ = [
    "DEFAULT_SECRET_STORE_TIMEOUT_SECONDS",
    "ExternalSecretStore",
    "MAX_SECRET_MATERIAL_BYTES",
    "MAX_SECRET_STORE_TIMEOUT_SECONDS",
    "SecretMaterial",
    "SecretMaterialClosedError",
    "SecretStoreAdapter",
    "SecretStoreAdapterContext",
    "SecretStoreAdapterFailure",
    "SecretStoreAvailability",
    "SecretStoreCancellationToken",
    "SecretStoreCompletion",
    "SecretStoreContractError",
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
]
