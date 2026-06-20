from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import cast

import pytest

from doll.audit import AuditEvent, AuditService
from doll.credential_broker import (
    AuditServiceCredentialAuditSink,
    CredentialAuthorizationAuthority,
    CredentialBroker,
)
from doll.credential_broker_contract import (
    CredentialAuditEvent,
    CredentialAuditSink,
    CredentialBrokerContractError,
    CredentialHandlerContext,
    CredentialHandlerRegistry,
    CredentialHandlerResult,
    CredentialRiskTier,
    CredentialUseIntent,
)
from doll.secret_material import SecretMaterial, SecretStoreCancellationToken
from doll.secret_policy import SecretReferenceMetadata, validate_secret_reference_metadata
from doll.secret_store import (
    ExternalSecretStore,
    SecretStoreAdapterContext,
    SecretStoreAdapterFailure,
    SecretStoreRegistry,
    SecretStoreStatus,
)


def _reference(
    *,
    status: str = "active",
    operations: tuple[str, ...] = ("example.read",),
    destinations: tuple[str, ...] = ("api.example.invalid",),
) -> SecretReferenceMetadata:
    payload: dict[str, object] = {
        "reference_id": "credential:example:primary",
        "credential_class": "api_key",
        "store_adapter_class": "test.synthetic",
        "label": "Synthetic credential",
        "status": status,
        "allowed_operation_scope": list(operations),
        "allowed_destination_scope": list(destinations),
        "created_at": "2026-06-20T00:00:00Z",
    }
    if status == "rotated":
        payload["rotated_at"] = "2026-06-20T01:00:00Z"
    if status == "revoked":
        payload["revoked_at"] = "2026-06-20T02:00:00Z"
    return validate_secret_reference_metadata(payload)


def _intent(
    *,
    reference: SecretReferenceMetadata | None = None,
    operation_id: str = "operation-1",
    destination: str = "api.example.invalid",
    operation_scope: str = "example.read",
    timeout_seconds: float = 30.0,
    cancellation: SecretStoreCancellationToken | None = None,
) -> CredentialUseIntent:
    return CredentialUseIntent(
        operation_id=operation_id,
        capability_id="credential.example.read",
        capability_version=1,
        actor_type="model",
        actor_id="synthetic-model-proposal",
        reference=reference or _reference(),
        operation_scope=operation_scope,
        destination=destination,
        risk_tier="tier3",
        timeout_seconds=timeout_seconds,
        user_presence="forbid",
        cancellation=cancellation or SecretStoreCancellationToken(),
    )


class SyntheticSecretStoreAdapter:
    adapter_class = "test.synthetic"

    def __init__(self) -> None:
        self.value = b"synthetic-credential-value"
        self.calls: list[str] = []
        self.last_material: SecretMaterial | None = None
        self.failure: Exception | None = None
        self.status_value = SecretStoreStatus(
            adapter_class=self.adapter_class,
            availability="available",
            lock_state="unlocked",
            user_presence="none",
            supported_operations=("lookup",),
        )

    def status(self) -> SecretStoreStatus:
        self.calls.append("status")
        return self.status_value

    def create(
        self,
        reference: SecretReferenceMetadata,
        material: SecretMaterial,
        context: SecretStoreAdapterContext,
    ) -> None:
        del reference, material, context
        raise SecretStoreAdapterFailure("unsupported_operation")

    def replace(
        self,
        reference: SecretReferenceMetadata,
        material: SecretMaterial,
        context: SecretStoreAdapterContext,
    ) -> None:
        del reference, material, context
        raise SecretStoreAdapterFailure("unsupported_operation")

    def lookup(
        self,
        reference: SecretReferenceMetadata,
        context: SecretStoreAdapterContext,
    ) -> SecretMaterial:
        del reference, context
        self.calls.append("lookup")
        if self.failure is not None:
            raise self.failure
        material = SecretMaterial(self.value)
        self.last_material = material
        return material

    def revoke(
        self,
        reference: SecretReferenceMetadata,
        context: SecretStoreAdapterContext,
    ) -> None:
        del reference, context
        raise SecretStoreAdapterFailure("unsupported_operation")

    def delete(
        self,
        reference: SecretReferenceMetadata,
        context: SecretStoreAdapterContext,
    ) -> None:
        del reference, context
        raise SecretStoreAdapterFailure("unsupported_operation")


class SyntheticHandler:
    capability_id = "credential.example.read"
    capability_version = 1
    operation_scope = "example.read"
    risk_tier: CredentialRiskTier = "tier3"

    def __init__(self) -> None:
        self.calls = 0
        self.saw_expected_value = False
        self.saw_read_only = False
        self.saved_view: memoryview | None = None
        self.result: object = CredentialHandlerResult(True, "synthetic.ok", "completed")
        self.failure: Exception | None = None
        self.hook: Callable[[CredentialHandlerContext], None] | None = None

    def execute(
        self,
        context: CredentialHandlerContext,
        credential: memoryview,
    ) -> CredentialHandlerResult:
        self.calls += 1
        self.saw_expected_value = bytes(credential) == b"synthetic-credential-value"
        self.saw_read_only = credential.readonly
        self.saved_view = credential
        if self.hook is not None:
            self.hook(context)
        if self.failure is not None:
            raise self.failure
        return cast(CredentialHandlerResult, self.result)


class CapturingAuditSink:
    def __init__(self) -> None:
        self.events: list[CredentialAuditEvent] = []
        self.fail_on_call: int | None = None
        self.calls = 0

    def record(self, event: CredentialAuditEvent) -> None:
        self.calls += 1
        if self.fail_on_call == self.calls:
            raise RuntimeError("password=synthetic-audit-secret")
        self.events.append(event)


class CapturingAuditService(AuditService):
    __slots__ = ("calls",)

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def append(self, **kwargs: object) -> AuditEvent:
        self.calls.append(dict(kwargs))
        return cast(AuditEvent, object())


def _components(
    *,
    adapter: SyntheticSecretStoreAdapter | None = None,
    handler: SyntheticHandler | None = None,
    audit: CapturingAuditSink | None = None,
    now: list[float] | None = None,
    id_factory: Callable[[], str] | None = None,
) -> tuple[
    CredentialBroker,
    CredentialAuthorizationAuthority,
    SyntheticSecretStoreAdapter | None,
    SyntheticHandler,
    CapturingAuditSink,
]:
    clock_values = now or [10.0]

    def clock():
        return clock_values[0]

    selected_handler = handler or SyntheticHandler()
    selected_audit = audit or CapturingAuditSink()
    authority_kwargs: dict[str, object] = {"clock": clock}
    if id_factory is not None:
        authority_kwargs["id_factory"] = id_factory
    authority = CredentialAuthorizationAuthority(**authority_kwargs)  # type: ignore[arg-type]
    store = ExternalSecretStore(
        SecretStoreRegistry(() if adapter is None else (adapter,)),
        clock=clock,
    )
    broker = CredentialBroker(
        store=store,
        handlers=CredentialHandlerRegistry((selected_handler,)),
        authorizations=authority,
        audit=selected_audit,
        clock=clock,
    )
    return broker, authority, adapter, selected_handler, selected_audit


def test_success_uses_transient_read_only_material_and_returns_no_secret() -> None:
    adapter = SyntheticSecretStoreAdapter()
    broker, authority, _, handler, audit = _components(adapter=adapter)
    intent = _intent()
    grant = authority.issue(intent)

    result = broker.execute(intent, grant)

    assert result.succeeded is True
    assert result.failure_code is None
    assert result.completion == "completed"
    assert result.handler_result_code == "synthetic.ok"
    assert handler.calls == 1
    assert handler.saw_expected_value is True
    assert handler.saw_read_only is True
    assert adapter.last_material is not None
    assert adapter.last_material.is_closed is True
    assert handler.saved_view is not None
    with pytest.raises(ValueError):
        bytes(handler.saved_view)
    assert len(audit.events) == 2
    assert [event.phase for event in audit.events] == ["attempt", "result"]
    rendered = repr((result, audit.events))
    assert "synthetic-credential-value" not in rendered
    assert "password=" not in rendered


def test_missing_authorization_denies_before_store_lookup() -> None:
    adapter = SyntheticSecretStoreAdapter()
    broker, _, _, handler, audit = _components(adapter=adapter)

    result = broker.execute(_intent(), None)

    assert result.failure_code == "authorization_missing"
    assert result.completion == "not_started"
    assert handler.calls == 0
    assert "lookup" not in adapter.calls
    assert audit.events[-1].result == "denied"


def test_grant_is_exact_one_time_and_replay_safe() -> None:
    adapter = SyntheticSecretStoreAdapter()
    broker, authority, _, handler, _ = _components(adapter=adapter)
    intent = _intent(
        reference=_reference(destinations=("api.example.invalid", "api2.example.invalid"))
    )
    grant = authority.issue(intent)

    changed = replace(intent, destination="api2.example.invalid")
    mismatch = broker.execute(changed, grant)
    assert mismatch.failure_code == "authorization_mismatch"
    assert handler.calls == 0

    first = broker.execute(intent, grant)
    assert first.succeeded is True
    replay = broker.execute(intent, grant)
    assert replay.failure_code == "authorization_consumed"
    assert handler.calls == 1


def test_expired_and_forged_grants_fail_closed() -> None:
    adapter = SyntheticSecretStoreAdapter()
    now = [10.0]
    broker, authority, _, handler, _ = _components(adapter=adapter, now=now)
    intent = _intent()
    grant = authority.issue(intent, ttl_seconds=1)
    now[0] = 11.0
    expired = broker.execute(intent, grant)
    assert expired.failure_code == "authorization_expired"

    forged = replace(grant, grant_id="forged-grant")
    missing = broker.execute(_intent(operation_id="operation-2"), forged)
    assert missing.failure_code == "authorization_missing"
    assert handler.calls == 0


def test_scope_destination_reference_and_handler_checks_precede_lookup() -> None:
    adapter = SyntheticSecretStoreAdapter()
    broker, authority, _, handler, _ = _components(adapter=adapter)

    operation_intent = _intent(
        reference=_reference(operations=("other.read",)),
    )
    operation_grant = authority.issue(operation_intent)
    assert broker.execute(operation_intent, operation_grant).failure_code == (
        "operation_out_of_scope"
    )

    destination_intent = _intent(
        reference=_reference(destinations=("other.example.invalid",)),
    )
    destination_grant = authority.issue(destination_intent)
    assert broker.execute(destination_intent, destination_grant).failure_code == (
        "destination_out_of_scope"
    )

    rotated_intent = _intent(reference=_reference(status="rotated"))
    rotated_grant = authority.issue(rotated_intent)
    assert broker.execute(rotated_intent, rotated_grant).failure_code == ("invalid_reference_state")

    handler.operation_scope = "other.read"
    mismatch_intent = _intent(operation_id="operation-4")
    mismatch_grant = authority.issue(mismatch_intent)
    assert broker.execute(mismatch_intent, mismatch_grant).failure_code == "handler_mismatch"
    assert handler.calls == 0
    assert "lookup" not in adapter.calls


def test_unregistered_handler_fails_closed() -> None:
    adapter = SyntheticSecretStoreAdapter()

    def clock():
        return 10.0

    authority = CredentialAuthorizationAuthority(clock=clock)
    audit = CapturingAuditSink()
    broker = CredentialBroker(
        store=ExternalSecretStore(SecretStoreRegistry((adapter,)), clock=clock),
        handlers=CredentialHandlerRegistry(),
        authorizations=authority,
        audit=audit,
        clock=clock,
    )
    intent = _intent()
    result = broker.execute(intent, authority.issue(intent))
    assert result.failure_code == "handler_not_registered"
    assert "lookup" not in adapter.calls


def test_store_failure_is_normalized_without_exception_text() -> None:
    adapter = SyntheticSecretStoreAdapter()
    adapter.failure = RuntimeError("api_key=synthetic-store-secret")
    broker, authority, _, handler, audit = _components(adapter=adapter)
    intent = _intent()

    result = broker.execute(intent, authority.issue(intent))

    assert result.failure_code == "adapter_failure"
    assert result.completion == "not_started"
    assert handler.calls == 0
    assert "synthetic-store-secret" not in repr((result, audit.events))


def test_absent_and_locked_store_fail_closed() -> None:
    broker, authority, _, handler, _ = _components(adapter=None)
    intent = _intent()
    absent = broker.execute(intent, authority.issue(intent))
    assert absent.failure_code == "adapter_not_configured"
    assert handler.calls == 0

    locked_adapter = SyntheticSecretStoreAdapter()
    locked_adapter.status_value = SecretStoreStatus(
        adapter_class=locked_adapter.adapter_class,
        availability="available",
        lock_state="locked",
        user_presence="none",
        supported_operations=("lookup",),
    )
    locked_broker, locked_authority, _, locked_handler, _ = _components(adapter=locked_adapter)
    locked_intent = _intent()
    locked = locked_broker.execute(locked_intent, locked_authority.issue(locked_intent))
    assert locked.failure_code == "locked"
    assert locked_handler.calls == 0


def test_handler_failure_malformed_result_and_bounded_denial() -> None:
    adapter = SyntheticSecretStoreAdapter()
    handler = SyntheticHandler()
    handler.failure = RuntimeError("Bearer synthetic-handler-secret")
    broker, authority, _, _, audit = _components(adapter=adapter, handler=handler)
    intent = _intent()
    failed = broker.execute(intent, authority.issue(intent))
    assert failed.failure_code == "handler_failure"
    assert failed.completion == "unknown"
    assert "synthetic-handler-secret" not in repr((failed, audit.events))
    assert adapter.last_material is not None and adapter.last_material.is_closed

    malformed_handler = SyntheticHandler()
    malformed_handler.result = object()
    malformed_broker, malformed_authority, malformed_adapter, _, _ = _components(
        adapter=SyntheticSecretStoreAdapter(),
        handler=malformed_handler,
    )
    malformed_intent = _intent(operation_id="operation-2")
    malformed = malformed_broker.execute(
        malformed_intent,
        malformed_authority.issue(malformed_intent),
    )
    assert malformed.failure_code == "malformed_handler_result"
    assert malformed.completion == "unknown"
    assert malformed_adapter is not None
    assert malformed_adapter.last_material is not None
    assert malformed_adapter.last_material.is_closed

    denied_handler = SyntheticHandler()
    denied_handler.result = CredentialHandlerResult(False, "remote.denied", "completed")
    denied_broker, denied_authority, _, _, _ = _components(
        adapter=SyntheticSecretStoreAdapter(),
        handler=denied_handler,
    )
    denied_intent = _intent(operation_id="operation-3")
    denied = denied_broker.execute(denied_intent, denied_authority.issue(denied_intent))
    assert denied.failure_code == "handler_result"
    assert denied.completion == "completed"
    assert denied.handler_result_code == "remote.denied"


def test_cancellation_and_timeout_preserve_truthful_completion() -> None:
    adapter = SyntheticSecretStoreAdapter()
    cancelled_token = SecretStoreCancellationToken()
    cancelled_token.cancel()
    broker, authority, _, handler, _ = _components(adapter=adapter)
    cancelled_intent = _intent(cancellation=cancelled_token)
    cancelled = broker.execute(cancelled_intent, authority.issue(cancelled_intent))
    assert cancelled.failure_code == "cancelled"
    assert cancelled.completion == "not_started"
    assert handler.calls == 0

    now = [10.0]
    late_handler = SyntheticHandler()

    def advance(context: CredentialHandlerContext) -> None:
        del context
        now[0] = 50.0

    late_handler.hook = advance
    late_broker, late_authority, late_adapter, _, _ = _components(
        adapter=SyntheticSecretStoreAdapter(),
        handler=late_handler,
        now=now,
    )
    late_intent = _intent(operation_id="operation-2", timeout_seconds=1)
    late = late_broker.execute(late_intent, late_authority.issue(late_intent))
    assert late.failure_code == "timeout"
    assert late.completion == "unknown"
    assert late.handler_result_code == "synthetic.ok"
    assert late_adapter is not None and late_adapter.last_material is not None
    assert late_adapter.last_material.is_closed

    now[0] = 10.0
    cancel_during_handler = SyntheticHandler()
    token = SecretStoreCancellationToken()
    cancel_during_handler.hook = lambda context: context.cancellation.cancel()
    cancel_broker, cancel_authority, _, _, _ = _components(
        adapter=SyntheticSecretStoreAdapter(),
        handler=cancel_during_handler,
        now=now,
    )
    cancel_intent = _intent(operation_id="operation-3", cancellation=token)
    during = cancel_broker.execute(cancel_intent, cancel_authority.issue(cancel_intent))
    assert during.failure_code == "cancelled"
    assert during.completion == "unknown"


def test_initial_audit_failure_prevents_execution_without_consuming_grant() -> None:
    adapter = SyntheticSecretStoreAdapter()
    audit = CapturingAuditSink()
    audit.fail_on_call = 1
    broker, authority, _, handler, _ = _components(adapter=adapter, audit=audit)
    intent = _intent()
    grant = authority.issue(intent)

    failed = broker.execute(intent, grant)
    assert failed.failure_code == "audit_failure"
    assert failed.completion == "not_started"
    assert handler.calls == 0
    assert "lookup" not in adapter.calls

    audit.fail_on_call = None
    succeeded = broker.execute(intent, grant)
    assert succeeded.succeeded is True
    assert handler.calls == 1


def test_terminal_audit_failure_does_not_hide_completed_side_effect() -> None:
    adapter = SyntheticSecretStoreAdapter()
    audit = CapturingAuditSink()
    audit.fail_on_call = 2
    broker, authority, _, handler, _ = _components(adapter=adapter, audit=audit)
    intent = _intent()

    result = broker.execute(intent, authority.issue(intent))

    assert handler.calls == 1
    assert result.succeeded is False
    assert result.failure_code == "audit_failure"
    assert result.completion == "completed"
    assert result.handler_result_code == "synthetic.ok"
    assert adapter.last_material is not None and adapter.last_material.is_closed


def test_forged_reference_is_rejected_before_audit_or_lookup() -> None:
    adapter = SyntheticSecretStoreAdapter()
    _broker, authority, _, handler, audit = _components(adapter=adapter)
    forged = replace(_reference(), reference_id="bad id")
    intent = _intent(reference=forged)
    with pytest.raises(CredentialBrokerContractError, match="invalid reference ID"):
        authority.issue(intent)
    assert audit.events == []
    assert handler.calls == 0
    assert adapter.calls == []


def test_authorization_authority_validates_ttl_ids_clocks_and_duplicates() -> None:
    intent = _intent()
    authority = CredentialAuthorizationAuthority(clock=lambda: 10.0)
    with pytest.raises(CredentialBrokerContractError, match="TTL"):
        authority.issue(intent, ttl_seconds=0)
    with pytest.raises(CredentialBrokerContractError, match="TTL"):
        authority.issue(intent, ttl_seconds=301)

    duplicate = CredentialAuthorizationAuthority(
        clock=lambda: 10.0,
        id_factory=lambda: "same-grant",
    )
    duplicate.issue(intent)
    with pytest.raises(CredentialBrokerContractError, match="duplicate"):
        duplicate.issue(replace(intent, operation_id="operation-2"))

    invalid_id = CredentialAuthorizationAuthority(
        clock=lambda: 10.0,
        id_factory=lambda: "bad grant id",
    )
    with pytest.raises(CredentialBrokerContractError):
        invalid_id.issue(intent)

    failed_id = CredentialAuthorizationAuthority(
        clock=lambda: 10.0,
        id_factory=lambda: (_ for _ in ()).throw(RuntimeError("failure")),
    )
    with pytest.raises(CredentialBrokerContractError, match="generation"):
        failed_id.issue(intent)

    with pytest.raises(CredentialBrokerContractError, match="clock"):
        CredentialAuthorizationAuthority(clock=lambda: float("nan")).issue(intent)
    with pytest.raises(CredentialBrokerContractError, match="clock"):
        CredentialAuthorizationAuthority(clock=cast(Callable[[], float], lambda: "invalid")).issue(
            intent
        )


def test_broker_constructor_and_runtime_types_fail_closed() -> None:
    adapter = SyntheticSecretStoreAdapter()
    store = ExternalSecretStore(SecretStoreRegistry((adapter,)))
    handler_registry = CredentialHandlerRegistry((SyntheticHandler(),))
    authority = CredentialAuthorizationAuthority()
    audit = CapturingAuditSink()

    invalid: tuple[dict[str, object], ...] = (
        {"store": object()},
        {"handlers": object()},
        {"authorizations": object()},
        {"audit": object()},
        {"clock": object()},
    )
    base: dict[str, object] = {
        "store": store,
        "handlers": handler_registry,
        "authorizations": authority,
        "audit": audit,
        "clock": lambda: 10.0,
    }
    for change in invalid:
        with pytest.raises(CredentialBrokerContractError):
            CredentialBroker(**(base | change))  # type: ignore[arg-type]

    broker = CredentialBroker(
        store=store,
        handlers=handler_registry,
        authorizations=authority,
        audit=audit,
        clock=lambda: 10.0,
    )
    with pytest.raises(CredentialBrokerContractError, match="validated intent"):
        broker.execute(cast(CredentialUseIntent, object()), None)
    with pytest.raises(CredentialBrokerContractError, match="clock"):
        CredentialBroker(
            store=store,
            handlers=handler_registry,
            authorizations=authority,
            audit=audit,
            clock=lambda: float("inf"),
        ).execute(_intent(), None)


def test_audit_service_sink_emits_only_closed_non_secret_metadata() -> None:
    service = CapturingAuditService()
    sink = AuditServiceCredentialAuditSink(service)
    event = CredentialAuditEvent(
        phase="result",
        operation_id="operation-1",
        actor_type="model",
        actor_id="synthetic-model-proposal",
        capability_id="credential.example.read",
        capability_version=1,
        reference_id="credential:example:primary",
        credential_class="api_key",
        operation_scope="example.read",
        destination="api.example.invalid",
        risk_tier="tier3",
        result="failed",
        failure_code="handler_failure",
        completion="unknown",
        handler_result_code="remote.failed",
    )

    sink.record(event)

    assert len(service.calls) == 1
    call = service.calls[0]
    assert call["action"] == "credential.use.result"
    assert call["target_id"] == "credential:example:primary"
    assert call["result"] == "failed"
    assert "synthetic-credential-value" not in repr(call)

    with pytest.raises(CredentialBrokerContractError, match="audit service"):
        AuditServiceCredentialAuditSink(cast(AuditService, object()))
    with pytest.raises(CredentialBrokerContractError, match="audit event"):
        sink.record(cast(CredentialAuditEvent, object()))


def test_audit_sink_protocol_rejects_missing_record_method() -> None:
    assert not isinstance(object(), CredentialAuditSink)
