"""Confirmation-aware capability preflight with no execution authority."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from doll._confirmation_types import ConfirmationReason, ConfirmationResolution
from doll._confirmation_validation import audit_actor
from doll.audit import AuditService
from doll.capabilities import (
    _DESTINATION_MISMATCH,
    CapabilityAuditError,
    CapabilityDecisionReason,
    CapabilityDefinition,
    CapabilityPreflightDecision,
    CapabilityPreflightService,
    CapabilityRegistry,
    CapabilityRequest,
    CapabilityRiskTier,
    OutboundNetworkPolicy,
    PermissionResolver,
    _actor_matches_origin,
    _arguments_match,
    _bindings_match,
    _cancellation_matches,
    _declared_limits_cover_request,
    _destination_for,
    _network_allowed,
    _permission_scope,
    _resource_limits_match,
    _target_matches,
    _timeout_matches,
    _validate_request_envelope,
)
from doll.confirmation import ConfirmationService
from doll.settings import SettingsError
from doll.state import StateError


@dataclass(frozen=True, slots=True)
class ConfirmedCapabilityPreflightDecision:
    capability: CapabilityPreflightDecision
    confirmation_id: str | None
    confirmation_reason: ConfirmationReason
    confirmation_fingerprint: str | None

    @property
    def authorized(self) -> bool:
        return self.capability.authorized


@dataclass(slots=True)
class ConfirmedCapabilityPreflightService:
    """Apply every IMP-021 gate before fresh exact Tier 3 confirmation."""

    registry: CapabilityRegistry
    permissions: PermissionResolver
    audit: AuditService
    network_policy: OutboundNetworkPolicy
    confirmations: ConfirmationService

    def preflight(
        self,
        request: CapabilityRequest,
        *,
        confirmation_id: str | None = None,
        credential_class: str | None = None,
    ) -> ConfirmedCapabilityPreflightDecision:
        envelope = _validate_request_envelope(request)
        base = CapabilityPreflightService(
            registry=self.registry,
            permissions=self.permissions,
            audit=self.audit,
            network_policy=self.network_policy,
        )
        definition = self.registry.get(envelope.capability_id, envelope.capability_version)
        if definition is None or definition.risk_tier is not CapabilityRiskTier.HIGH_RISK:
            decision = base.preflight(envelope)
            return ConfirmedCapabilityPreflightDecision(
                capability=decision,
                confirmation_id=None,
                confirmation_reason="not_required",
                confirmation_fingerprint=None,
            )

        denied, destination, permission_mode = self._checks_before_confirmation(
            base, envelope, definition
        )
        if denied is not None:
            return ConfirmedCapabilityPreflightDecision(
                capability=denied,
                confirmation_id=confirmation_id,
                confirmation_reason="not_evaluated",
                confirmation_fingerprint=None,
            )

        resolution = self.confirmations.resolve(
            confirmation_id,
            envelope,
            registry_fingerprint=self.registry.fingerprint,
            normalized_destination=destination,
            credential_class=credential_class,
        )
        if not resolution.approved:
            decision = base._deny(
                envelope,
                cast(CapabilityDecisionReason, "tier3_confirmation_unavailable"),
                risk_tier=definition.risk_tier,
                permission_mode=permission_mode,
            )
            self._audit_confirmation(envelope, resolution, authorized=False)
            return ConfirmedCapabilityPreflightDecision(
                capability=decision,
                confirmation_id=confirmation_id,
                confirmation_reason=resolution.reason,
                confirmation_fingerprint=resolution.request_fingerprint,
            )

        decision = CapabilityPreflightDecision(
            authorized=True,
            reason="authorized",
            capability_id=envelope.capability_id,
            capability_version=envelope.capability_version,
            operation_id=envelope.operation_id,
            risk_tier=definition.risk_tier,
            registry_fingerprint=self.registry.fingerprint,
            permission_mode=permission_mode,
            normalized_destination=destination,
        )
        base._audit_decision(envelope, decision)
        self._audit_confirmation(envelope, resolution, authorized=True)
        return ConfirmedCapabilityPreflightDecision(
            capability=decision,
            confirmation_id=confirmation_id,
            confirmation_reason="approved",
            confirmation_fingerprint=resolution.request_fingerprint,
        )

    def _checks_before_confirmation(
        self,
        base: CapabilityPreflightService,
        request: CapabilityRequest,
        definition: CapabilityDefinition,
    ) -> tuple[CapabilityPreflightDecision | None, str | None, str | None]:
        def denied(
            reason: CapabilityDecisionReason,
            *,
            permission_mode: str | None = None,
        ) -> tuple[CapabilityPreflightDecision, None, None]:
            return (
                base._deny(
                    request,
                    reason,
                    risk_tier=definition.risk_tier,
                    permission_mode=permission_mode,
                ),
                None,
                None,
            )

        if (
            not _actor_matches_origin(request.actor_type, request.origin_class)
            or request.origin_class not in definition.allowed_request_origins
        ):
            return denied("actor_origin_mismatch")
        if not _arguments_match(definition, request.arguments):
            return denied("argument_schema_mismatch")
        if not _target_matches(definition.target, request.target):
            return denied("target_mismatch")
        destination_value = _destination_for(definition, request)
        if destination_value is _DESTINATION_MISMATCH:
            return denied("destination_mismatch")
        destination = cast(str | None, destination_value)
        if request.declared_side_effects != definition.side_effects:
            return denied("side_effect_mismatch")
        if request.declared_risk_tier != int(definition.risk_tier):
            return denied("risk_tier_mismatch")
        if not _resource_limits_match(
            definition.resource_contract, request.resource_limits
        ) or not _declared_limits_cover_request(request):
            return denied("resource_limit_mismatch")
        if not _timeout_matches(definition.resource_contract, request.timeout_seconds):
            return denied("timeout_mismatch")
        if not _cancellation_matches(definition, request.cancellation_id):
            return denied("cancellation_mismatch")
        scope = _permission_scope(request.permission_scope)
        if scope is None or scope.get("kind") != definition.permission_scope_kind:
            return denied("permission_denied")
        if not _bindings_match(definition, request, destination, scope):
            return denied("binding_mismatch")
        if not definition.release_available:
            return denied("release_excluded")

        permission_mode: str | None = None
        if definition.permission_scope_kind != "none":
            try:
                permission = self.permissions.resolve(
                    capability_id=definition.capability_id,
                    scope=scope,
                )
            except (SettingsError, StateError):
                return denied("permission_denied")
            permission_mode = permission.effective_mode
            if permission_mode == "ask":
                return denied(
                    "permission_requires_user_action",
                    permission_mode=permission_mode,
                )
            if permission_mode not in {"allow_once", "scoped"}:
                return denied("permission_denied", permission_mode=permission_mode)

        if definition.network_mode == "explicit_url":
            assert destination is not None
            if not _network_allowed(self.network_policy, destination):
                return denied("network_denied", permission_mode=permission_mode)
        return None, destination, permission_mode

    def _audit_confirmation(
        self,
        request: CapabilityRequest,
        resolution: ConfirmationResolution,
        *,
        authorized: bool,
    ) -> None:
        try:
            self.audit.append(
                action="confirmation.preflight",
                result="success" if authorized else "denied",
                actor_type=audit_actor(request.actor_type),
                operation_id=request.operation_id,
                target_type="confirmation",
                target_id=resolution.confirmation_id,
                summary=(
                    "Exact high-risk confirmation accepted"
                    if authorized
                    else "Exact high-risk confirmation unavailable"
                ),
                metadata={
                    "capability_id": request.capability_id,
                    "capability_version": request.capability_version,
                    "confirmation_reason": resolution.reason,
                    "risk_tier": 3,
                    "request_fingerprint": resolution.request_fingerprint,
                },
            )
        except BaseException as exc:
            raise CapabilityAuditError(
                "capability authorization failed because confirmation audit persistence failed"
            ) from exc
