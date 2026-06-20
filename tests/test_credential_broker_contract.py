from __future__ import annotations

from dataclasses import replace
from typing import cast

import pytest

from doll.credential_broker_contract import (
    CredentialAuditEvent,
    CredentialAuditPhase,
    CredentialAuthorizationGrant,
    CredentialBrokerContractError,
    CredentialBrokerResult,
    CredentialCompletion,
    CredentialFailureCode,
    CredentialHandlerContext,
    CredentialHandlerRegistry,
    CredentialHandlerResult,
    CredentialRiskTier,
    CredentialUseIntent,
)
from doll.secret_material import SecretStoreCancellationToken
from doll.secret_policy import SecretReferenceMetadata, validate_secret_reference_metadata


def _reference() -> SecretReferenceMetadata:
    return validate_secret_reference_metadata(
        {
            "reference_id": "credential:example:primary",
            "credential_class": "api_key",
            "store_adapter_class": "test.synthetic",
            "label": "Synthetic credential",
            "status": "active",
            "allowed_operation_scope": ["example.read"],
            "allowed_destination_scope": ["api.example.invalid"],
            "created_at": "2026-06-20T00:00:00Z",
        }
    )


def _intent(**changes: object) -> CredentialUseIntent:
    values: dict[str, object] = {
        "operation_id": "operation-1",
        "capability_id": "credential.example.read",
        "capability_version": 1,
        "actor_type": "user",
        "actor_id": "local-user",
        "reference": _reference(),
        "operation_scope": "example.read",
        "destination": "api.example.invalid",
        "risk_tier": "tier3",
        "timeout_seconds": 30.0,
        "user_presence": "forbid",
        "cancellation": SecretStoreCancellationToken(),
    }
    values.update(changes)
    return CredentialUseIntent(**values)  # type: ignore[arg-type]


class MinimalHandler:
    capability_id = "credential.example.read"
    capability_version = 1
    operation_scope = "example.read"
    risk_tier: CredentialRiskTier = "tier3"

    def execute(
        self,
        context: CredentialHandlerContext,
        credential: memoryview,
    ) -> CredentialHandlerResult:
        del context, credential
        return CredentialHandlerResult(True, "ok", "completed")


def test_intent_accepts_only_exact_bounded_non_secret_fields() -> None:
    intent = _intent()
    assert intent.risk_tier == "tier3"
    assert "cancellation" not in repr(intent)

    invalid: tuple[dict[str, object], ...] = (
        {"operation_id": "bad id"},
        {"capability_id": "*"},
        {"capability_version": 0},
        {"capability_version": True},
        {"actor_type": "unknown"},
        {"actor_id": "bad id"},
        {"reference": object()},
        {"operation_scope": "example.*"},
        {"destination": "https://api.example.invalid/path"},
        {"destination": "api.example.invalid:0"},
        {"destination": "api.example.invalid:65536"},
        {"risk_tier": "tier2"},
        {"timeout_seconds": 0},
        {"timeout_seconds": float("inf")},
        {"timeout_seconds": True},
        {"user_presence": "unknown"},
        {"cancellation": object()},
    )
    for change in invalid:
        with pytest.raises(CredentialBrokerContractError):
            _intent(**change)


def test_authorization_grant_and_handler_context_validate_identity() -> None:
    grant = CredentialAuthorizationGrant(
        grant_id="grant-1",
        operation_id="operation-1",
        capability_id="credential.example.read",
        capability_version=1,
        reference_id="credential:example:primary",
        operation_scope="example.read",
        destination="api.example.invalid",
        risk_tier="tier3",
        expires_at_monotonic=100.0,
    )
    assert "secret" not in repr(grant).lower()

    token = SecretStoreCancellationToken()
    context = CredentialHandlerContext(
        operation_id="operation-1",
        capability_id="credential.example.read",
        capability_version=1,
        reference_id="credential:example:primary",
        operation_scope="example.read",
        destination="api.example.invalid",
        risk_tier="tier3",
        deadline_monotonic=100.0,
        cancellation=token,
    )
    assert "cancellation" not in repr(context)

    with pytest.raises(CredentialBrokerContractError):
        replace(grant, expires_at_monotonic=float("nan"))
    with pytest.raises(CredentialBrokerContractError):
        replace(context, deadline_monotonic=-1.0)
    with pytest.raises(CredentialBrokerContractError):
        replace(context, cancellation=cast(SecretStoreCancellationToken, object()))


def test_handler_and_broker_result_invariants() -> None:
    success = CredentialHandlerResult(True, "remote.ok", "completed")
    failure = CredentialHandlerResult(False, "remote.denied", "unknown")
    assert success.succeeded is True
    assert failure.succeeded is False

    with pytest.raises(CredentialBrokerContractError):
        CredentialHandlerResult(True, "ok", "unknown")
    with pytest.raises(CredentialBrokerContractError):
        CredentialHandlerResult(False, "denied", "not_started")
    with pytest.raises(CredentialBrokerContractError):
        CredentialHandlerResult(False, "bad code", "unknown")

    broker_success = CredentialBrokerResult(
        operation_id="operation-1",
        capability_id="credential.example.read",
        capability_version=1,
        reference_id="credential:example:primary",
        operation_scope="example.read",
        destination="api.example.invalid",
        succeeded=True,
        failure_code=None,
        completion="completed",
        handler_result_code="remote.ok",
    )
    assert broker_success.succeeded is True

    invalid: tuple[tuple[bool, object, object, object], ...] = (
        (True, "handler_failure", "completed", "ok"),
        (True, None, "unknown", "ok"),
        (True, None, "completed", None),
        (False, None, "not_started", None),
        (False, "invented", "not_started", None),
        (False, "handler_failure", "invented", None),
        (False, "handler_failure", "unknown", "bad code"),
    )
    for succeeded, code, completion, handler_code in invalid:
        with pytest.raises(CredentialBrokerContractError):
            CredentialBrokerResult(
                operation_id="operation-1",
                capability_id="credential.example.read",
                capability_version=1,
                reference_id="credential:example:primary",
                operation_scope="example.read",
                destination="api.example.invalid",
                succeeded=succeeded,
                failure_code=cast(CredentialFailureCode | None, code),
                completion=cast(CredentialCompletion, completion),
                handler_result_code=cast(str | None, handler_code),
            )


def test_audit_event_enforces_attempt_and_result_shapes() -> None:
    attempt = CredentialAuditEvent(
        phase="attempt",
        operation_id="operation-1",
        actor_type="model",
        actor_id="model-proposal",
        capability_id="credential.example.read",
        capability_version=1,
        reference_id="credential:example:primary",
        credential_class="api_key",
        operation_scope="example.read",
        destination="api.example.invalid",
        risk_tier="tier3",
        result="success",
    )
    assert attempt.failure_code is None

    result = CredentialAuditEvent(
        phase="result",
        operation_id="operation-1",
        actor_type="model",
        actor_id="model-proposal",
        capability_id="credential.example.read",
        capability_version=1,
        reference_id="credential:example:primary",
        credential_class="api_key",
        operation_scope="example.read",
        destination="api.example.invalid",
        risk_tier="tier3",
        result="denied",
        failure_code="authorization_missing",
        completion="not_started",
    )
    assert result.result == "denied"

    with pytest.raises(CredentialBrokerContractError):
        replace(attempt, result="failed")
    with pytest.raises(CredentialBrokerContractError):
        replace(attempt, failure_code="authorization_missing")
    with pytest.raises(CredentialBrokerContractError):
        replace(result, completion=None)
    with pytest.raises(CredentialBrokerContractError):
        replace(result, phase=cast(CredentialAuditPhase, "invented"))


def test_handler_registry_is_immutable_exact_and_tier3_only() -> None:
    handler = MinimalHandler()
    registry = CredentialHandlerRegistry((handler,))
    assert registry.handler_keys == (("credential.example.read", 1),)
    assert registry.get("credential.example.read", 1) is handler
    assert "credential.example.read" in repr(registry)

    with pytest.raises(CredentialBrokerContractError, match="duplicate"):
        CredentialHandlerRegistry((handler, handler))
    with pytest.raises(CredentialBrokerContractError, match="registration"):
        CredentialHandlerRegistry((cast(MinimalHandler, object()),))

    wrong_tier = MinimalHandler()
    wrong_tier.risk_tier = cast(CredentialRiskTier, "tier2")
    with pytest.raises(CredentialBrokerContractError, match="registration"):
        CredentialHandlerRegistry((wrong_tier,))

    wildcard = MinimalHandler()
    wildcard.operation_scope = "example.*"
    with pytest.raises(CredentialBrokerContractError, match="registration"):
        CredentialHandlerRegistry((wildcard,))

    with pytest.raises(CredentialBrokerContractError):
        registry.get("bad id", 1)
