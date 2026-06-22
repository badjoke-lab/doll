"""Internal Tier 3 binding and confirmation lifecycle validation."""

from __future__ import annotations

from datetime import datetime
from typing import cast
from urllib.parse import urlsplit

from doll._confirmation_types import (
    ConfirmationCorruptError,
    ConfirmationDecisionValue,
    ConfirmationInfo,
    ConfirmationPreview,
    ConfirmationResolution,
    ConfirmationValidationError,
    parse_utc,
    validate_fingerprint,
)
from doll.audit import AuditActorType, AuditEvent
from doll.capabilities import (
    CapabilityDefinition,
    CapabilityRegistry,
    CapabilityRequest,
    CapabilityRiskTier,
    _DESTINATION_MISMATCH,
    _actor_matches_origin,
    _arguments_match,
    _bindings_match,
    _cancellation_matches,
    _declared_limits_cover_request,
    _destination_for,
    _permission_scope,
    _resource_limits_match,
    _target_matches,
    _timeout_matches,
    _validate_request_envelope,
)


def validated_high_risk_binding(
    request: CapabilityRequest,
    registry: CapabilityRegistry,
) -> tuple[CapabilityRequest, CapabilityDefinition, str | None]:
    envelope = _validate_request_envelope(request)
    definition = registry.get(envelope.capability_id, envelope.capability_version)
    if definition is None:
        raise ConfirmationValidationError("confirmation requires a registered version")
    if definition.risk_tier is not CapabilityRiskTier.HIGH_RISK:
        raise ConfirmationValidationError("confirmation may be issued only for Tier 3")
    if not definition.release_available:
        raise ConfirmationValidationError(
            "release-excluded capability cannot be confirmed"
        )
    if (
        not _actor_matches_origin(envelope.actor_type, envelope.origin_class)
        or envelope.origin_class not in definition.allowed_request_origins
    ):
        raise ConfirmationValidationError("request actor or origin is not authorized")
    if not _arguments_match(definition, envelope.arguments):
        raise ConfirmationValidationError("request arguments do not match capability")
    if not _target_matches(definition.target, envelope.target):
        raise ConfirmationValidationError("request target does not match capability")
    destination_value = _destination_for(definition, envelope)
    if destination_value is _DESTINATION_MISMATCH:
        raise ConfirmationValidationError("request destination is inconsistent")
    destination = cast(str | None, destination_value)
    if envelope.declared_side_effects != definition.side_effects:
        raise ConfirmationValidationError(
            "request side effects do not match capability"
        )
    if envelope.declared_risk_tier != 3:
        raise ConfirmationValidationError("request must declare Tier 3")
    if not _resource_limits_match(
        definition.resource_contract, envelope.resource_limits
    ) or not _declared_limits_cover_request(envelope):
        raise ConfirmationValidationError("request resource limits are invalid")
    if not _timeout_matches(definition.resource_contract, envelope.timeout_seconds):
        raise ConfirmationValidationError("request timeout is invalid")
    if not _cancellation_matches(definition, envelope.cancellation_id):
        raise ConfirmationValidationError("request cancellation identity is invalid")
    scope = _permission_scope(envelope.permission_scope)
    if scope is None or scope.get("kind") != definition.permission_scope_kind:
        raise ConfirmationValidationError("request permission scope is invalid")
    if not _bindings_match(definition, envelope, destination, scope):
        raise ConfirmationValidationError("request binding is inconsistent")
    return envelope, definition, destination


def confirmation_metadata(
    *,
    confirmation_id: str,
    request: CapabilityRequest,
    definition: CapabilityDefinition,
    request_fingerprint: str,
    registry_fingerprint: str,
    destination: str | None,
    decision: ConfirmationDecisionValue,
    expires_at: str,
    preview: ConfirmationPreview,
) -> dict[str, object]:
    host = urlsplit(destination).hostname if destination is not None else None
    return {
        "confirmation_schema_version": 1,
        "confirmation_id": confirmation_id,
        "decision": decision,
        "request_fingerprint": request_fingerprint,
        "registry_fingerprint": registry_fingerprint,
        "capability_id": request.capability_id,
        "capability_version": request.capability_version,
        "risk_tier": 3,
        "target_kind": request.target.kind,
        "destination_host": host,
        "side_effects": sorted(definition.side_effects),
        "credential_class": preview.credential_class,
        "data_leaves_machine": destination is not None,
        "irreversible": preview.irreversible,
        "recovery_available": preview.recovery_description is not None,
        "expires_at": expires_at,
        "effect_summary": preview.effect_summary,
        "account_label": preview.account_label,
        "recovery_description": preview.recovery_description,
    }


def resolution_from_events(
    confirmation_id: str,
    events: tuple[AuditEvent, ...],
    *,
    expected_operation_id: str,
    expected_fingerprint: str,
    now: datetime,
) -> ConfirmationResolution:
    if not events:
        return ConfirmationResolution(
            confirmation_id, "missing", expected_fingerprint, None
        )
    issues = [event for event in events if event.action == "confirmation.issue"]
    if len(issues) != 1:
        raise ConfirmationCorruptError("confirmation must have exactly one issue event")
    issue = issues[0]
    if issue.actor_type != "user" or issue.target_id != confirmation_id:
        raise ConfirmationCorruptError("confirmation issue authority is invalid")
    info = info_from_issue(issue)
    _validate_lifecycle_events(events, info)
    if (
        issue.operation_id != expected_operation_id
        or info.request_fingerprint != expected_fingerprint
    ):
        return ConfirmationResolution(
            confirmation_id, "mismatch", expected_fingerprint, info
        )
    if any(event.action == "confirmation.revoke" for event in events):
        return ConfirmationResolution(
            confirmation_id, "revoked", expected_fingerprint, info
        )
    if any(event.action == "confirmation.consume" for event in events):
        return ConfirmationResolution(
            confirmation_id, "consumed", expected_fingerprint, info
        )
    if info.decision == "denied" or issue.result == "denied":
        return ConfirmationResolution(
            confirmation_id, "denied", expected_fingerprint, info
        )
    if now >= parse_utc(info.expires_at):
        return ConfirmationResolution(
            confirmation_id, "expired", expected_fingerprint, info
        )
    return ConfirmationResolution(
        confirmation_id, "approved", expected_fingerprint, info
    )


def _validate_lifecycle_events(
    events: tuple[AuditEvent, ...],
    info: ConfirmationInfo,
) -> None:
    consumes = [event for event in events if event.action == "confirmation.consume"]
    revokes = [event for event in events if event.action == "confirmation.revoke"]
    if len(consumes) > 1 or len(revokes) > 1:
        raise ConfirmationCorruptError(
            "confirmation lifecycle has duplicate terminal events"
        )
    for event in events:
        if (
            event.target_type != "confirmation"
            or event.target_id != info.confirmation_id
        ):
            raise ConfirmationCorruptError("confirmation lifecycle target is invalid")
        if event.action == "confirmation.issue":
            continue
        if event.action == "confirmation.consume":
            if (
                event.actor_type not in {"capability", "system"}
                or event.result != "success"
            ):
                raise ConfirmationCorruptError(
                    "confirmation consume authority is invalid"
                )
            if event.metadata.get("request_fingerprint") != info.request_fingerprint:
                raise ConfirmationCorruptError(
                    "confirmation consume fingerprint is invalid"
                )
            continue
        if event.action == "confirmation.revoke":
            if event.actor_type != "user" or event.result != "success":
                raise ConfirmationCorruptError(
                    "confirmation revocation authority is invalid"
                )
            continue
        raise ConfirmationCorruptError("confirmation lifecycle action is invalid")


def info_from_issue(event: AuditEvent) -> ConfirmationInfo:
    metadata = event.metadata
    try:
        if metadata["confirmation_schema_version"] != 1:
            raise ValueError
        confirmation_id = _metadata_string(metadata, "confirmation_id")
        decision = _metadata_string(metadata, "decision")
        if decision not in {"approved", "denied"}:
            raise ValueError
        request_fingerprint = validate_fingerprint(
            "request fingerprint", _metadata_string(metadata, "request_fingerprint")
        )
        registry_fingerprint = validate_fingerprint(
            "registry fingerprint", _metadata_string(metadata, "registry_fingerprint")
        )
        if metadata["risk_tier"] != 3:
            raise ValueError
        effects = metadata["side_effects"]
        if not isinstance(effects, list) or not all(
            isinstance(item, str) for item in effects
        ):
            raise ValueError
        return ConfirmationInfo(
            confirmation_id=confirmation_id,
            operation_id=event.operation_id,
            capability_id=_metadata_string(metadata, "capability_id"),
            capability_version=_metadata_string(metadata, "capability_version"),
            request_fingerprint=request_fingerprint,
            registry_fingerprint=registry_fingerprint,
            decision=cast(ConfirmationDecisionValue, decision),
            issued_at=event.occurred_at,
            expires_at=_metadata_string(metadata, "expires_at"),
            target_kind=_metadata_string(metadata, "target_kind"),
            destination_host=_metadata_optional_string(metadata, "destination_host"),
            side_effects=tuple(cast(list[str], effects)),
            credential_class=_metadata_optional_string(metadata, "credential_class"),
            data_leaves_machine=_metadata_bool(metadata, "data_leaves_machine"),
            irreversible=_metadata_bool(metadata, "irreversible"),
            recovery_available=_metadata_bool(metadata, "recovery_available"),
            effect_summary=_metadata_string(metadata, "effect_summary"),
            account_label=_metadata_optional_string(metadata, "account_label"),
            recovery_description=_metadata_optional_string(
                metadata, "recovery_description"
            ),
        )
    except (KeyError, TypeError, ValueError, ConfirmationValidationError) as exc:
        raise ConfirmationCorruptError(
            "confirmation issue metadata is malformed"
        ) from exc


def audit_actor(actor_type: str) -> AuditActorType:
    if actor_type in {"user", "model", "runtime", "system"}:
        return cast(AuditActorType, actor_type)
    if actor_type == "tool":
        return "capability"
    return "system"


def _metadata_string(metadata: dict[str, object], key: str) -> str:
    value = metadata[key]
    if not isinstance(value, str) or not value:
        raise ValueError
    return value


def _metadata_optional_string(metadata: dict[str, object], key: str) -> str | None:
    value = metadata.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError
    return value


def _metadata_bool(metadata: dict[str, object], key: str) -> bool:
    value = metadata[key]
    if not isinstance(value, bool):
        raise ValueError
    return value
