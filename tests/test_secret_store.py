from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import cast

import pytest

from doll.secret_policy import (
    SecretReferenceMetadata,
    SecretReferenceStatus,
    validate_secret_reference_metadata,
)
from doll.secret_store import (
    ExternalSecretStore,
    SecretMaterial,
    SecretMaterialClosedError,
    SecretStoreAdapterContext,
    SecretStoreAdapterFailure,
    SecretStoreCancellationToken,
    SecretStoreContractError,
    SecretStoreRegistry,
    SecretStoreRequest,
    SecretStoreStatus,
    SecretStoreUserPresencePolicy,
)


def _reference(
    status: SecretReferenceStatus = "active",
    *,
    adapter_class: str = "test.synthetic",
) -> SecretReferenceMetadata:
    payload: dict[str, object] = {
        "reference_id": "credential:example:primary",
        "credential_class": "api_key",
        "store_adapter_class": adapter_class,
        "label": "Synthetic API credential",
        "status": status,
        "allowed_operation_scope": ["example.read"],
        "allowed_destination_scope": ["api.example.invalid"],
        "created_at": "2026-06-20T00:00:00Z",
    }
    if status == "rotated":
        payload["rotated_at"] = "2026-06-20T01:00:00Z"
    if status == "revoked":
        payload["revoked_at"] = "2026-06-20T02:00:00Z"
    return validate_secret_reference_metadata(payload)


def _request(
    *,
    timeout_seconds: float = 30.0,
    user_presence: SecretStoreUserPresencePolicy = "forbid",
    cancellation: SecretStoreCancellationToken | None = None,
) -> SecretStoreRequest:
    return SecretStoreRequest(
        operation_id="operation-1",
        timeout_seconds=timeout_seconds,
        user_presence=user_presence,
        cancellation=cancellation or SecretStoreCancellationToken(),
    )


class SyntheticAdapter:
    adapter_class = "test.synthetic"

    def __init__(self) -> None:
        self.values: dict[str, bytes] = {}
        self.revoked: set[str] = set()
        self.calls: list[str] = []
        self.status_value = SecretStoreStatus(
            adapter_class=self.adapter_class,
            availability="available",
            lock_state="unlocked",
            user_presence="none",
            supported_operations=("create", "delete", "lookup", "replace", "revoke"),
        )
        self.failure: Exception | None = None
        self.operation_hook: Callable[[str], None] | None = None
        self.status_hook: Callable[[], None] | None = None
        self.lookup_override: SecretMaterial | object | None = None

    def status(self) -> SecretStoreStatus:
        self.calls.append("status")
        if self.status_hook is not None:
            self.status_hook()
        return self.status_value

    def _before(self, operation: str) -> None:
        self.calls.append(operation)
        if self.operation_hook is not None:
            self.operation_hook(operation)
        if self.failure is not None:
            raise self.failure

    def create(
        self,
        reference: SecretReferenceMetadata,
        material: SecretMaterial,
        context: SecretStoreAdapterContext,
    ) -> None:
        del context
        self._before("create")
        if reference.reference_id in self.values:
            raise SecretStoreAdapterFailure("already_exists")
        with material.borrow() as view:
            self.values[reference.reference_id] = bytes(view)

    def replace(
        self,
        reference: SecretReferenceMetadata,
        material: SecretMaterial,
        context: SecretStoreAdapterContext,
    ) -> None:
        del context
        self._before("replace")
        if reference.reference_id not in self.values:
            raise SecretStoreAdapterFailure("not_found")
        with material.borrow() as view:
            self.values[reference.reference_id] = bytes(view)
        self.revoked.discard(reference.reference_id)

    def lookup(
        self,
        reference: SecretReferenceMetadata,
        context: SecretStoreAdapterContext,
    ) -> SecretMaterial:
        del context
        self._before("lookup")
        if self.lookup_override is not None:
            return cast(SecretMaterial, self.lookup_override)
        if reference.reference_id in self.revoked:
            raise SecretStoreAdapterFailure("reference_revoked")
        try:
            return SecretMaterial(self.values[reference.reference_id])
        except KeyError:
            raise SecretStoreAdapterFailure("not_found") from None

    def revoke(
        self,
        reference: SecretReferenceMetadata,
        context: SecretStoreAdapterContext,
    ) -> None:
        del context
        self._before("revoke")
        if reference.reference_id not in self.values:
            raise SecretStoreAdapterFailure("not_found")
        self.revoked.add(reference.reference_id)

    def delete(
        self,
        reference: SecretReferenceMetadata,
        context: SecretStoreAdapterContext,
    ) -> None:
        del context
        self._before("delete")
        if reference.reference_id not in self.values:
            raise SecretStoreAdapterFailure("not_found")
        del self.values[reference.reference_id]
        self.revoked.discard(reference.reference_id)


def _store(
    adapter: SyntheticAdapter | None = None,
    *,
    clock: Callable[[], float] | None = None,
) -> ExternalSecretStore:
    adapters = () if adapter is None else (adapter,)
    if clock is None:
        return ExternalSecretStore(SecretStoreRegistry(adapters))
    return ExternalSecretStore(SecretStoreRegistry(adapters), clock=clock)


def _reveal(material: SecretMaterial) -> bytes:
    with material.borrow() as view:
        return bytes(view)


def test_empty_registry_is_safe_and_core_constructs() -> None:
    store = ExternalSecretStore()
    status = store.status("test.synthetic")
    assert status.availability == "unavailable"
    assert status.failure_code == "adapter_not_configured"
    assert store.lookup(_reference(), _request()).result.failure_code == (
        "adapter_not_configured"
    )


def test_boundary_constructor_validation() -> None:
    with pytest.raises(SecretStoreContractError, match="registry"):
        ExternalSecretStore(cast(SecretStoreRegistry, object()))
    with pytest.raises(SecretStoreContractError, match="clock"):
        ExternalSecretStore(clock=cast(Callable[[], float], object()))


def test_lifecycle_uses_stable_reference_and_consumes_write_material() -> None:
    adapter = SyntheticAdapter()
    store = _store(adapter)
    reference = _reference()
    first = SecretMaterial(b"first-synthetic")
    created = store.create(reference, first, _request())
    assert created.succeeded is True
    assert created.reference_id == reference.reference_id
    assert created.completion == "confirmed"
    assert first.is_closed is True

    with store.lookup(reference, _request()) as lookup:
        assert lookup.succeeded is True
        assert lookup.material is not None
        assert _reveal(lookup.material) == b"first-synthetic"
        assert "first-synthetic" not in repr(lookup)
    assert lookup.material is None
    lookup.close()

    second = SecretMaterial(b"second-synthetic")
    replaced = store.replace(reference, second, _request())
    assert replaced.succeeded is True
    assert second.is_closed is True
    with store.lookup(reference, _request()) as lookup2:
        assert lookup2.material is not None
        assert _reveal(lookup2.material) == b"second-synthetic"

    assert store.revoke(reference, _request()).succeeded is True
    assert store.lookup(reference, _request()).result.failure_code == "reference_revoked"
    assert store.delete(reference, _request()).succeeded is True
    assert store.lookup(reference, _request()).result.failure_code == "not_found"


def test_reference_state_fails_closed_before_adapter_call() -> None:
    adapter = SyntheticAdapter()
    store = _store(adapter)
    revoked = _reference("revoked")
    assert store.lookup(revoked, _request()).result.failure_code == "reference_revoked"
    assert store.revoke(revoked, _request()).failure_code == "reference_revoked"
    assert adapter.calls == []

    rotated_input = SecretMaterial(b"synthetic")
    create = store.create(_reference("rotated"), rotated_input, _request())
    assert create.failure_code == "invalid_reference_state"
    assert rotated_input.is_closed is True
    assert store.delete(revoked, _request()).failure_code == "not_found"


def test_preflight_availability_lock_support_and_user_presence() -> None:
    adapter = SyntheticAdapter()
    store = _store(adapter)

    adapter.status_value = SecretStoreStatus(
        adapter.adapter_class,
        "unavailable",
        "unknown",
        "unknown",
        (),
        "store_unavailable",
    )
    assert store.lookup(_reference(), _request()).result.failure_code == "store_unavailable"

    adapter.status_value = SecretStoreStatus(
        adapter.adapter_class,
        "available",
        "locked",
        "none",
        ("lookup",),
    )
    assert store.lookup(_reference(), _request()).result.failure_code == "locked"

    adapter.status_value = SecretStoreStatus(
        adapter.adapter_class,
        "available",
        "unlocked",
        "none",
        ("lookup",),
    )
    material = SecretMaterial(b"synthetic")
    assert store.create(_reference(), material, _request()).failure_code == (
        "unsupported_operation"
    )
    assert material.is_closed is True

    adapter.status_value = SecretStoreStatus(
        adapter.adapter_class,
        "available",
        "unlocked",
        "required",
        ("lookup",),
    )
    assert store.lookup(_reference(), _request()).result.failure_code == (
        "user_presence_required"
    )
    assert store.lookup(
        _reference(), _request(user_presence="allow")
    ).result.failure_code == "not_found"

    adapter.status_value = SecretStoreStatus(
        adapter.adapter_class,
        "available",
        "unlocked",
        "none",
        ("lookup",),
    )
    assert store.lookup(
        _reference(), _request(user_presence="require")
    ).result.failure_code == "user_presence_unavailable"


def test_preflight_cancellation_and_timeout_after_status() -> None:
    adapter = SyntheticAdapter()
    now = [10.0]
    store = _store(adapter, clock=lambda: now[0])

    cancelled = SecretStoreCancellationToken()

    def cancel_during_status() -> None:
        cancelled.cancel()

    adapter.status_hook = cancel_during_status
    result = store.lookup(_reference(), _request(cancellation=cancelled))
    assert result.result.failure_code == "cancelled"
    assert "lookup" not in adapter.calls

    adapter.status_hook = lambda: now.__setitem__(0, 20.0)
    timed_out = store.lookup(_reference(), _request(timeout_seconds=1))
    assert timed_out.result.failure_code == "timeout"


def test_pre_cancelled_write_is_not_called_and_material_is_closed() -> None:
    adapter = SyntheticAdapter()
    token = SecretStoreCancellationToken()
    token.cancel()
    material = SecretMaterial(b"synthetic")
    result = _store(adapter).create(
        _reference(),
        material,
        _request(cancellation=token),
    )
    assert result.failure_code == "cancelled"
    assert result.completion == "not_completed"
    assert adapter.calls == []
    assert material.is_closed is True


def test_late_or_cancelled_lookup_closes_returned_material() -> None:
    adapter = SyntheticAdapter()
    adapter.values[_reference().reference_id] = b"synthetic"
    now = [10.0]
    store = _store(adapter, clock=lambda: now[0])

    adapter.operation_hook = lambda operation: now.__setitem__(0, 50.0)
    late = store.lookup(_reference(), _request(timeout_seconds=1))
    assert late.result.failure_code == "timeout"
    assert late.material is None

    token = SecretStoreCancellationToken()

    def cancel_lookup(operation: str) -> None:
        if operation == "lookup":
            token.cancel()

    now[0] = 10.0
    adapter.operation_hook = cancel_lookup
    cancelled = store.lookup(_reference(), _request(cancellation=token))
    assert cancelled.result.failure_code == "cancelled"
    assert cancelled.material is None


def test_late_or_cancelled_mutation_has_unknown_completion() -> None:
    adapter = SyntheticAdapter()
    adapter.values[_reference().reference_id] = b"existing"
    now = [10.0]
    store = _store(adapter, clock=lambda: now[0])

    adapter.operation_hook = lambda operation: now.__setitem__(0, 50.0)
    late = SecretMaterial(b"replacement")
    result = store.replace(_reference(), late, _request(timeout_seconds=1))
    assert result.failure_code == "timeout"
    assert result.completion == "unknown"
    assert late.is_closed is True

    token = SecretStoreCancellationToken()

    def cancel_delete(operation: str) -> None:
        if operation == "delete":
            token.cancel()

    now[0] = 10.0
    adapter.operation_hook = cancel_delete
    cancelled = store.delete(_reference(), _request(cancellation=token))
    assert cancelled.failure_code == "cancelled"
    assert cancelled.completion == "unknown"


def test_adapter_failures_are_normalized_without_raw_exception_text() -> None:
    adapter = SyntheticAdapter()
    store = _store(adapter)
    adapter.failure = RuntimeError("password=synthetic-adapter-secret")

    material = SecretMaterial(b"synthetic-input")
    create = store.create(_reference(), material, _request())
    assert create.failure_code == "adapter_failure"
    assert create.completion == "unknown"
    assert "synthetic-adapter-secret" not in repr(create)
    assert "synthetic-input" not in repr(create)
    assert material.is_closed is True

    lookup = store.lookup(_reference(), _request())
    assert lookup.result.failure_code == "adapter_failure"
    assert "synthetic-adapter-secret" not in repr(lookup)

    revoke = store.revoke(_reference(), _request())
    assert revoke.failure_code == "adapter_failure"
    assert revoke.completion == "unknown"


def test_known_adapter_failures_preserve_safe_code_and_completion() -> None:
    adapter = SyntheticAdapter()
    store = _store(adapter)
    adapter.failure = SecretStoreAdapterFailure("permission_denied", completion="unknown")

    material = SecretMaterial(b"synthetic")
    write = store.create(_reference(), material, _request())
    assert write.failure_code == "permission_denied"
    assert write.completion == "unknown"
    assert material.is_closed is True

    lookup = store.lookup(_reference(), _request())
    assert lookup.result.failure_code == "permission_denied"
    assert lookup.result.completion == "not_completed"

    revoke = store.revoke(_reference(), _request())
    assert revoke.failure_code == "permission_denied"
    assert revoke.completion == "unknown"


def test_status_and_lookup_malformed_adapter_values_fail_closed() -> None:
    class MalformedStatusAdapter(SyntheticAdapter):
        def status(self) -> SecretStoreStatus:
            return cast(SecretStoreStatus, object())

    malformed_status = MalformedStatusAdapter()
    store = _store(malformed_status)
    assert store.status(malformed_status.adapter_class).failure_code == "adapter_failure"
    assert store.lookup(_reference(), _request()).result.failure_code == "adapter_failure"

    adapter = SyntheticAdapter()
    adapter.lookup_override = object()
    malformed_lookup = _store(adapter).lookup(_reference(), _request())
    assert malformed_lookup.result.failure_code == "adapter_failure"

    closed = SecretMaterial(b"synthetic")
    closed.close()
    adapter.lookup_override = closed
    closed_lookup = _store(adapter).lookup(_reference(), _request())
    assert closed_lookup.result.failure_code == "adapter_failure"
    assert closed.is_closed is True


def test_status_probe_failure_and_adapter_class_mismatch_are_isolated() -> None:
    class FailingStatusAdapter(SyntheticAdapter):
        def status(self) -> SecretStoreStatus:
            raise RuntimeError("api_key=synthetic-status-secret")

    failed = FailingStatusAdapter()
    assert _store(failed).status(failed.adapter_class).failure_code == "adapter_failure"

    mismatch = SyntheticAdapter()
    mismatch.status_value = replace(mismatch.status_value, adapter_class="test.other")
    assert _store(mismatch).status(mismatch.adapter_class).failure_code == "adapter_failure"

    mutated = SyntheticAdapter()
    mutated_store = _store(mutated)
    mutated.adapter_class = "test.other"
    assert mutated_store.status("test.synthetic").failure_code == "adapter_failure"


def test_contract_type_and_clock_validation() -> None:
    store = ExternalSecretStore()
    with pytest.raises(SecretStoreContractError, match="validated reference"):
        store.lookup(cast(SecretReferenceMetadata, object()), _request())
    forged_id = replace(_reference(), reference_id="bad id")
    with pytest.raises(SecretStoreContractError, match="validated reference"):
        store.lookup(forged_id, _request())

    forged_scope = replace(
        _reference(),
        allowed_operation_scope=cast(tuple[str, ...], ["example.read"]),
    )
    with pytest.raises(SecretStoreContractError, match="validated reference"):
        store.lookup(forged_scope, _request())

    with pytest.raises(SecretStoreContractError, match="validated request"):
        store.lookup(_reference(), cast(SecretStoreRequest, object()))
    with pytest.raises(SecretStoreContractError, match="SecretMaterial"):
        store.create(_reference(), cast(SecretMaterial, object()), _request())

    closed = SecretMaterial(b"synthetic")
    closed.close()
    with pytest.raises(SecretMaterialClosedError):
        store.create(_reference(), closed, _request())

    material = SecretMaterial(b"synthetic")
    with pytest.raises(SecretStoreContractError, match="clock"):
        _store(SyntheticAdapter(), clock=lambda: float("nan")).create(
            _reference(), material, _request()
        )
    assert material.is_closed is True

    def failed_clock() -> float:
        raise RuntimeError("synthetic clock failure")

    with pytest.raises(SecretStoreContractError, match="clock"):
        _store(SyntheticAdapter(), clock=failed_clock).lookup(_reference(), _request())
    with pytest.raises(SecretStoreContractError, match="clock"):
        _store(SyntheticAdapter(), clock=lambda: True).lookup(_reference(), _request())
    with pytest.raises(SecretStoreContractError, match="clock"):
        _store(
            SyntheticAdapter(),
            clock=cast(Callable[[], float], lambda: "invalid"),
        ).lookup(_reference(), _request())
