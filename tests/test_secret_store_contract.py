from __future__ import annotations

from typing import cast

import pytest

from doll.secret_policy import SecretReferenceMetadata
from doll.secret_store import (
    MAX_SECRET_MATERIAL_BYTES,
    SecretMaterial,
    SecretMaterialClosedError,
    SecretStoreAdapterContext,
    SecretStoreAdapterFailure,
    SecretStoreCancellationToken,
    SecretStoreCompletion,
    SecretStoreContractError,
    SecretStoreFailureCode,
    SecretStoreLookupResult,
    SecretStoreOperation,
    SecretStoreOperationResult,
    SecretStoreRegistry,
    SecretStoreRequest,
    SecretStoreStatus,
    SecretStoreUserPresencePolicy,
)


class MinimalAdapter:
    adapter_class = "test.minimal"

    def status(self) -> SecretStoreStatus:
        return SecretStoreStatus(
            adapter_class=self.adapter_class,
            availability="available",
            lock_state="unlocked",
            user_presence="none",
            supported_operations=(),
        )

    def create(
        self,
        reference: SecretReferenceMetadata,
        material: SecretMaterial,
        context: SecretStoreAdapterContext,
    ) -> None:
        del reference, material, context

    def replace(
        self,
        reference: SecretReferenceMetadata,
        material: SecretMaterial,
        context: SecretStoreAdapterContext,
    ) -> None:
        del reference, material, context

    def lookup(
        self,
        reference: SecretReferenceMetadata,
        context: SecretStoreAdapterContext,
    ) -> SecretMaterial:
        del reference, context
        return SecretMaterial(b"synthetic")

    def revoke(
        self,
        reference: SecretReferenceMetadata,
        context: SecretStoreAdapterContext,
    ) -> None:
        del reference, context

    def delete(
        self,
        reference: SecretReferenceMetadata,
        context: SecretStoreAdapterContext,
    ) -> None:
        del reference, context


def test_secret_material_is_bounded_redacted_and_closed() -> None:
    material = SecretMaterial(bytearray(b"synthetic-secret"))
    assert str(material) == repr(material) == "<SecretMaterial redacted>"
    with material.borrow() as view:
        assert bytes(view) == b"synthetic-secret"
        assert view.readonly is True
    material.close()
    assert material.is_closed is True
    material.close()
    with pytest.raises(SecretMaterialClosedError):
        with material.borrow():
            pass
    with pytest.raises(SecretMaterialClosedError):
        with material:
            pass
    with pytest.raises(SecretStoreContractError, match="empty"):
        SecretMaterial(b"")
    with pytest.raises(SecretStoreContractError, match="size"):
        SecretMaterial(b"x" * (MAX_SECRET_MATERIAL_BYTES + 1))
    with pytest.raises(SecretStoreContractError, match="bytes-like"):
        SecretMaterial(object())  # type: ignore[arg-type]
    released_view = memoryview(b"synthetic")
    released_view.release()
    with pytest.raises(SecretStoreContractError, match="bytes-like"):
        SecretMaterial(released_view)


def test_secret_material_context_manager_closes() -> None:
    material = SecretMaterial(b"synthetic")
    with material as opened:
        assert opened is material
    assert material.is_closed is True


def test_adapter_failure_contract_is_closed_and_non_secret() -> None:
    failure = SecretStoreAdapterFailure("permission_denied", completion="unknown")
    assert failure.code == "permission_denied"
    assert failure.completion == "unknown"
    assert str(failure) == "secret-store adapter failure: permission_denied"
    with pytest.raises(SecretStoreContractError, match="failure code"):
        SecretStoreAdapterFailure(cast(SecretStoreFailureCode, "invented"))
    with pytest.raises(SecretStoreContractError, match="completion"):
        SecretStoreAdapterFailure("not_found", completion="confirmed")
    with pytest.raises(SecretStoreContractError, match="completion"):
        SecretStoreAdapterFailure(
            "not_found",
            completion=cast(SecretStoreCompletion, "invented"),
        )


def test_request_validation_and_cancellation() -> None:
    token = SecretStoreCancellationToken()
    valid = SecretStoreRequest("operation-1", cancellation=token)
    assert "cancellation" not in repr(valid)
    assert token.is_cancelled is False
    assert "active" in repr(token)
    token.cancel()
    assert token.is_cancelled is True
    assert "cancelled" in repr(token)

    invalid_requests: tuple[dict[str, object], ...] = (
        {"operation_id": "bad id"},
        {"operation_id": "x", "timeout_seconds": 0},
        {"operation_id": "x", "timeout_seconds": float("inf")},
        {"operation_id": "x", "timeout_seconds": True},
        {"operation_id": "x", "timeout_seconds": "30"},
        {"operation_id": "x", "timeout_seconds": 301},
        {"operation_id": "x", "user_presence": "unknown"},
        {"operation_id": "x", "cancellation": object()},
    )
    for kwargs in invalid_requests:
        with pytest.raises(SecretStoreContractError):
            SecretStoreRequest(**kwargs)  # type: ignore[arg-type]


def test_adapter_context_validation() -> None:
    token = SecretStoreCancellationToken()
    context = SecretStoreAdapterContext("operation-1", 10.0, "allow", token)
    assert "cancellation" not in repr(context)
    invalid_contexts: tuple[tuple[object, object, object, object], ...] = (
        ("bad id", 10.0, "allow", token),
        ("operation-1", float("inf"), "allow", token),
        ("operation-1", True, "allow", token),
        ("operation-1", 10.0, "unknown", token),
        ("operation-1", 10.0, "allow", object()),
    )
    for operation_id, deadline, user_presence, cancellation in invalid_contexts:
        with pytest.raises(SecretStoreContractError):
            SecretStoreAdapterContext(
                cast(str, operation_id),
                cast(float, deadline),
                cast(SecretStoreUserPresencePolicy, user_presence),
                cast(SecretStoreCancellationToken, cancellation),
            )


def test_status_validation_is_closed_and_deterministic() -> None:
    invalid_statuses: tuple[dict[str, object], ...] = (
        {"adapter_class": "Bad Adapter"},
        {"availability": "invented"},
        {"lock_state": "invented"},
        {"user_presence": "invented"},
        {"supported_operations": ["lookup"]},
        {"supported_operations": ("invented",)},
        {"supported_operations": ("lookup", "lookup")},
        {"supported_operations": ("replace", "lookup")},
        {"failure_code": "not_found", "availability": "unavailable"},
        {"failure_code": "store_unavailable"},
        {"availability": "unavailable"},
        {"availability": []},
        {"lock_state": []},
        {"user_presence": []},
        {"supported_operations": ({},)},
        {"failure_code": []},
        {
            "availability": "unavailable",
            "failure_code": "store_unavailable",
            "supported_operations": ("lookup",),
        },
        {
            "availability": "unavailable",
            "failure_code": "store_unavailable",
            "lock_state": "unlocked",
            "user_presence": "unknown",
            "supported_operations": (),
        },
    )
    base: dict[str, object] = {
        "adapter_class": "test.synthetic",
        "availability": "available",
        "lock_state": "unlocked",
        "user_presence": "none",
        "supported_operations": ("lookup",),
        "failure_code": None,
    }
    for change in invalid_statuses:
        payload = base | change
        with pytest.raises(SecretStoreContractError):
            SecretStoreStatus(**payload)  # type: ignore[arg-type]


def test_registry_is_immutable_validated_and_duplicate_safe() -> None:
    adapter = MinimalAdapter()
    registry = SecretStoreRegistry((adapter,))
    assert registry.adapter_classes == ("test.minimal",)
    assert registry.get("test.minimal") is adapter
    assert "test.minimal" in repr(registry)
    with pytest.raises(SecretStoreContractError, match="duplicate"):
        SecretStoreRegistry((adapter, adapter))

    invalid_name = MinimalAdapter()
    invalid_name.adapter_class = "Bad Adapter"
    with pytest.raises(SecretStoreContractError, match="registration"):
        SecretStoreRegistry((invalid_name,))
    with pytest.raises(SecretStoreContractError, match="registration"):
        SecretStoreRegistry((cast(MinimalAdapter, object()),))
    with pytest.raises(SecretStoreContractError):
        registry.get("Bad Adapter")


def test_result_invariants_and_lookup_ownership() -> None:
    invalid_results: tuple[tuple[object, ...], ...] = (
        ("invented", "ref", "test.x", False, "not_found", "not_completed"),
        ("lookup", "bad ref", "test.x", False, "not_found", "not_completed"),
        ("lookup", "ref", "test.x", 1, "not_found", "not_completed"),
        ("lookup", "ref", "test.x", False, "not_found", "invented"),
        ("lookup", "ref", "test.x", False, "invented", "not_completed"),
        ("lookup", "ref", "test.x", True, "not_found", "confirmed"),
        ("lookup", "ref", "test.x", False, None, "not_completed"),
        ("lookup", "ref", "test.x", False, "not_found", "confirmed"),
    )
    for operation, reference_id, adapter_class, succeeded, code, completion in invalid_results:
        with pytest.raises(SecretStoreContractError):
            SecretStoreOperationResult(
                cast(SecretStoreOperation, operation),
                cast(str, reference_id),
                cast(str, adapter_class),
                cast(bool, succeeded),
                cast(SecretStoreFailureCode | None, code),
                cast(SecretStoreCompletion, completion),
            )

    failed = SecretStoreOperationResult(
        "lookup", "ref", "test.x", False, "not_found", "not_completed"
    )
    material = SecretMaterial(b"synthetic")
    failed_lookup = SecretStoreLookupResult(failed, material)
    assert failed_lookup.material is None
    assert material.is_closed is True
    failed_lookup.close()

    non_lookup = SecretStoreOperationResult(
        "delete", "ref", "test.x", True, None, "confirmed"
    )
    with pytest.raises(SecretStoreContractError, match="lookup operation"):
        SecretStoreLookupResult(non_lookup)

    success = SecretStoreOperationResult(
        "lookup", "ref", "test.x", True, None, "confirmed"
    )
    with pytest.raises(SecretStoreContractError, match="open secret material"):
        SecretStoreLookupResult(success)
    closed = SecretMaterial(b"synthetic")
    closed.close()
    with pytest.raises(SecretStoreContractError, match="open secret material"):
        SecretStoreLookupResult(success, closed)


def test_lookup_result_rejects_invalid_runtime_objects() -> None:
    failed = SecretStoreOperationResult(
        "lookup", "ref", "test.x", False, "not_found", "not_completed"
    )
    with pytest.raises(SecretStoreContractError, match="invalid lookup result"):
        SecretStoreLookupResult(cast(SecretStoreOperationResult, object()))
    with pytest.raises(SecretStoreContractError, match="invalid lookup material"):
        SecretStoreLookupResult(failed, cast(SecretMaterial, object()))
