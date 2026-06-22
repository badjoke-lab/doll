from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest

from doll import state
from doll.audit import AuditService
from doll.capabilities import (
    CapabilityResourceLimits,
    OutboundNetworkPolicy,
    built_in_capability_registry,
)
from doll.confirmation import (
    ConfirmationUnavailableError,
    ConfirmationValidationError,
    ForbiddenConfirmationMutationError,
    confirmation_fingerprint,
)
from doll.confirmation_preflight import ConfirmedCapabilityPreflightService
from tests.confirmation_support import (
    FakePermissionResolver,
    MutableClock,
    compute_request,
    initialized_workspace,
    preflight_service,
    preview,
    tier3_request,
)


def test_exact_approved_confirmation_authorizes_without_consuming(
    tmp_path: Path,
) -> None:
    initialized = initialized_workspace(tmp_path)
    clock = MutableClock()
    request = tier3_request()
    with state.open_state_repository(initialized.root) as repository:
        registry, confirmations, permissions, service = preflight_service(repository, clock)
        confirmation = confirmations.issue(
            request,
            registry=registry,
            preview=preview(),
            decision="approved",
        )

        first = service.preflight(request, confirmation_id=confirmation.confirmation_id)
        second = service.preflight(request, confirmation_id=confirmation.confirmation_id)

        assert first.authorized is True
        assert second.authorized is True
        assert first.confirmation_reason == second.confirmation_reason == "approved"
        assert first.confirmation_fingerprint == confirmation.request_fingerprint
        assert len(permissions.calls) == 2
        resolution = confirmations.resolve(
            confirmation.confirmation_id,
            request,
            registry_fingerprint=registry.fingerprint,
            normalized_destination=None,
        )
        assert resolution.reason == "approved"
        actions = [event.action for event in AuditService(repository).list(limit=50)]
        assert actions.count("confirmation.issue") == 1
        assert actions.count("confirmation.preflight") == 2
        assert actions.count("confirmation.consume") == 0


def test_missing_denied_expired_revoked_and_consumed_confirmation_fail_closed(
    tmp_path: Path,
) -> None:
    initialized = initialized_workspace(tmp_path)
    clock = MutableClock()
    request = tier3_request()
    with state.open_state_repository(initialized.root) as repository:
        registry, confirmations, _, service = preflight_service(repository, clock)
        missing = service.preflight(request)
        assert missing.authorized is False
        assert missing.confirmation_reason == "missing"

        denied_info = confirmations.issue(
            request,
            registry=registry,
            preview=preview(),
            decision="denied",
        )
        denied = service.preflight(request, confirmation_id=denied_info.confirmation_id)
        assert denied.authorized is False
        assert denied.confirmation_reason == "denied"

        expiring = confirmations.issue(
            request,
            registry=registry,
            preview=preview(),
            decision="approved",
            ttl_seconds=1,
        )
        clock.now += timedelta(seconds=2)
        expired = service.preflight(request, confirmation_id=expiring.confirmation_id)
        assert expired.authorized is False
        assert expired.confirmation_reason == "expired"

        clock.now += timedelta(seconds=1)
        revoked_info = confirmations.issue(
            request,
            registry=registry,
            preview=preview(),
            decision="approved",
        )
        confirmations.revoke(
            revoked_info.confirmation_id,
            operation_id=request.operation_id,
        )
        revoked = service.preflight(request, confirmation_id=revoked_info.confirmation_id)
        assert revoked.authorized is False
        assert revoked.confirmation_reason == "revoked"

        consumed_info = confirmations.issue(
            request,
            registry=registry,
            preview=preview(),
            decision="approved",
        )
        confirmations.consume(
            consumed_info.confirmation_id,
            request,
            registry_fingerprint=registry.fingerprint,
            normalized_destination=None,
        )
        consumed = service.preflight(request, confirmation_id=consumed_info.confirmation_id)
        assert consumed.authorized is False
        assert consumed.confirmation_reason == "consumed"
        with pytest.raises(ConfirmationUnavailableError):
            confirmations.consume(
                consumed_info.confirmation_id,
                request,
                registry_fingerprint=registry.fingerprint,
                normalized_destination=None,
            )


def test_every_material_request_change_invalidates_confirmation(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    clock = MutableClock()
    request = tier3_request()
    with state.open_state_repository(initialized.root) as repository:
        registry, confirmations, _, service = preflight_service(repository, clock)
        info = confirmations.issue(
            request,
            registry=registry,
            preview=preview(),
            decision="approved",
        )
        changed = replace(
            request,
            arguments={**request.arguments, "input_record_id": "record-2"},
        )
        decision = service.preflight(changed, confirmation_id=info.confirmation_id)
        assert decision.authorized is False
        assert decision.confirmation_reason == "mismatch"
        assert decision.confirmation_fingerprint != info.request_fingerprint

        variants = (
            replace(request, session_id="session-2"),
            replace(request, cancellation_id="cancel-tier3-2"),
            replace(request, timeout_seconds=6),
            replace(request, resource_limits=CapabilityResourceLimits(100, 4096, 2)),
        )
        for variant in variants:
            assert (
                confirmation_fingerprint(
                    variant,
                    registry_fingerprint=registry.fingerprint,
                    normalized_destination=None,
                )
                != info.request_fingerprint
            )


def test_confirmation_authority_rejects_non_user_content_and_unsafe_preview(
    tmp_path: Path,
) -> None:
    initialized = initialized_workspace(tmp_path)
    clock = MutableClock()
    request = tier3_request()
    with state.open_state_repository(initialized.root) as repository:
        registry, confirmations, _, _ = preflight_service(repository, clock)
        with pytest.raises(ForbiddenConfirmationMutationError):
            confirmations.issue(
                request,
                registry=registry,
                preview=preview(),
                decision="approved",
                actor_type="model",
                origin_class="model_proposal",
            )
        with pytest.raises(ForbiddenConfirmationMutationError):
            confirmations.issue(
                request,
                registry=registry,
                preview=preview(),
                decision="approved",
                actor_type="content",
                origin_class="external_content",
            )
        with pytest.raises(ConfirmationValidationError):
            confirmations.issue(
                request,
                registry=registry,
                preview=replace(
                    preview(),
                    effect_summary="Authorization: Bearer synthetic-secret-token-value",
                ),
                decision="approved",
            )
        assert not AuditService(repository).list(action="confirmation.issue", limit=50)


def test_confirmation_is_necessary_but_cannot_override_other_gates(
    tmp_path: Path,
) -> None:
    initialized = initialized_workspace(tmp_path)
    clock = MutableClock()
    request = tier3_request()
    with state.open_state_repository(initialized.root) as repository:
        registry, confirmations, _, _ = preflight_service(repository, clock)
        info = confirmations.issue(
            request,
            registry=registry,
            preview=preview(),
            decision="approved",
        )
        denied_permission_service = ConfirmedCapabilityPreflightService(
            registry=registry,
            permissions=FakePermissionResolver("denied"),
            audit=AuditService(repository),
            network_policy=OutboundNetworkPolicy(enabled=False),
            confirmations=confirmations,
        )
        denied = denied_permission_service.preflight(request, confirmation_id=info.confirmation_id)
        assert denied.authorized is False
        assert denied.capability.reason == "permission_denied"

        release_excluded = ConfirmedCapabilityPreflightService(
            registry=built_in_capability_registry(),
            permissions=FakePermissionResolver(),
            audit=AuditService(repository),
            network_policy=OutboundNetworkPolicy(enabled=False),
            confirmations=confirmations,
        ).preflight(request, confirmation_id=info.confirmation_id)
        assert release_excluded.authorized is False
        assert release_excluded.capability.reason == "release_excluded"


def test_non_tier3_preflight_delegates_without_confirmation(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    clock = MutableClock()
    with state.open_state_repository(initialized.root) as repository:
        _, _, _, service = preflight_service(repository, clock)
        decision = service.preflight(compute_request())
        assert decision.authorized is True
        assert decision.confirmation_reason == "not_required"
        assert decision.confirmation_id is None
