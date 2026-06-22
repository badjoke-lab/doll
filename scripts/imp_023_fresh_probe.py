"""Run the fresh-process portion of the IMP-023 safety acceptance test."""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

from doll import state, workspace
from doll.audit import AuditService
from doll.capabilities import (
    CapabilityPreflightService,
    CapabilityRegistry,
    CapabilityRequest,
    CapabilityResourceLimits,
    CapabilityTarget,
    OutboundNetworkPolicy,
    built_in_capability_registry,
)
from doll.confirmation import ConfirmationPreview, ConfirmationService
from doll.confirmation_preflight import ConfirmedCapabilityPreflightService
from doll.settings import PermissionDecision


class ScopedPermissions:
    """Synthetic scoped permission resolver used only by the acceptance probe."""

    def resolve(
        self,
        *,
        capability_id: str,
        scope: dict[str, object],
    ) -> PermissionDecision:
        return PermissionDecision(
            record_id="synthetic-permission",
            capability_id=capability_id,
            scope=scope,
            effective_mode="scoped",
            reason="active",
        )


def _tier3_request() -> CapabilityRequest:
    return CapabilityRequest(
        capability_id="adapter.fixed_process.example",
        capability_version="1.0",
        operation_id="imp023-tier3",
        actor_type="model",
        origin_class="model_proposal",
        arguments={
            "project_id": "project-1",
            "name": "output.txt",
            "input_record_id": "record-1",
        },
        target=CapabilityTarget("managed_artifact", "project-1/output.txt"),
        destination=None,
        declared_side_effects=frozenset(
            {"process_execution", "create_managed_artifact"}
        ),
        declared_risk_tier=3,
        permission_scope={"kind": "project", "project_id": "project-1"},
        resource_limits=CapabilityResourceLimits(100, 4096, 1),
        timeout_seconds=5,
        session_id="session-1",
        cancellation_id="cancel-tier3",
    )


def _unknown_request() -> CapabilityRequest:
    return CapabilityRequest(
        capability_id="unknown.capability",
        capability_version="1.0",
        operation_id="imp023-unknown",
        actor_type="model",
        origin_class="model_proposal",
        arguments={"text": "hello", "operation": "uppercase"},
        target=CapabilityTarget("provided_data", "inline-data"),
        destination=None,
        declared_side_effects=frozenset(),
        declared_risk_tier=0,
        permission_scope={"kind": "none"},
        resource_limits=CapabilityResourceLimits(100, 1024, 1),
        timeout_seconds=5,
    )


def _released_registry(registry: CapabilityRegistry) -> CapabilityRegistry:
    return CapabilityRegistry(
        tuple(
            replace(definition, release_available=True)
            if definition.capability_id == "adapter.fixed_process.example"
            else definition
            for definition in registry.definitions()
        )
    )


def _probe(root: Path) -> dict[str, bool]:
    initialized = workspace.initialize_workspace(root / "workspace")
    checks: dict[str, bool] = {}

    with state.initialize_state_repository(initialized.root) as repository:
        before = repository.status().state_revision
        try:
            repository.create_record(
                record_type="memory",
                sensitivity="secret",
                metadata={"content": "synthetic secret-shaped value"},
            )
        except state.RecordValidationError:
            checks["secret_write_denied"] = True
        else:
            checks["secret_write_denied"] = False
        checks["denial_preserved_revision"] = (
            repository.status().state_revision == before
        )

        secret_value = "Bearer synthetic-imp023-credential"
        event = AuditService(repository).append(
            action="imp023.synthetic",
            result="denied",
            metadata={"note": secret_value},
        )
        rendered_event = repr(event)
        checks["audit_redacted"] = (
            secret_value not in rendered_event
            and "[REDACTED:authorization_header]" in rendered_event
        )

        registry = built_in_capability_registry()
        permissions = ScopedPermissions()
        network_policy = OutboundNetworkPolicy(enabled=False)
        base = CapabilityPreflightService(
            registry=registry,
            permissions=permissions,
            audit=AuditService(repository),
            network_policy=network_policy,
        )
        unknown_decision = base.preflight(_unknown_request())
        checks["unknown_capability_denied"] = (
            not unknown_decision.authorized
            and unknown_decision.reason == "unknown_capability"
        )

        request = _tier3_request()
        confirmations = ConfirmationService(repository)
        release_excluded = ConfirmedCapabilityPreflightService(
            registry=registry,
            permissions=permissions,
            audit=AuditService(repository),
            network_policy=network_policy,
            confirmations=confirmations,
        ).preflight(request)
        checks["release_excluded_precedes_confirmation"] = (
            not release_excluded.authorized
            and release_excluded.capability.reason == "release_excluded"
            and release_excluded.confirmation_reason == "not_evaluated"
        )

        released = _released_registry(registry)
        info = confirmations.issue(
            request,
            registry=released,
            preview=ConfirmationPreview(
                effect_summary="Run one reviewed synthetic fixed adapter.",
                irreversible=False,
                recovery_description="No real side effect is performed.",
            ),
            decision="approved",
        )
        confirmed = ConfirmedCapabilityPreflightService(
            registry=released,
            permissions=permissions,
            audit=AuditService(repository),
            network_policy=network_policy,
            confirmations=confirmations,
        )
        exact = confirmed.preflight(
            request,
            confirmation_id=info.confirmation_id,
        )
        changed = confirmed.preflight(
            replace(request, session_id="session-2"),
            confirmation_id=info.confirmation_id,
        )
        checks["fresh_exact_confirmation_accepted"] = exact.authorized
        checks["material_change_invalidates_confirmation"] = (
            not changed.authorized and changed.confirmation_reason == "mismatch"
        )
        excluded_after_confirmation = ConfirmedCapabilityPreflightService(
            registry=registry,
            permissions=permissions,
            audit=AuditService(repository),
            network_policy=network_policy,
            confirmations=confirmations,
        ).preflight(request, confirmation_id=info.confirmation_id)
        checks["confirmation_cannot_bypass_release_exclusion"] = (
            not excluded_after_confirmation.authorized
            and excluded_after_confirmation.capability.reason == "release_excluded"
        )

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        events = AuditService(repository).list(limit=200)
        resolution = ConfirmationService(repository).resolve(
            info.confirmation_id,
            request,
            registry_fingerprint=released.fingerprint,
            normalized_destination=None,
        )
        checks["fresh_process_state_opened"] = (
            repository.status().record_count == 0
        )
        checks["fresh_process_audit_readable"] = len(events) >= 5
        checks["fresh_process_confirmation_readable"] = (
            resolution.reason == "approved"
        )

    checks["model_runtime_used"] = False
    checks["cloud_credentials_used"] = False
    checks["live_side_effect_used"] = False
    return checks


def main() -> int:
    if len(sys.argv) != 2:
        print(
            json.dumps(
                {"result": "fail", "error_stage": "arguments"},
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 2
    try:
        checks = _probe(Path(sys.argv[1]))
    except BaseException as exc:
        print(
            json.dumps(
                {
                    "result": "fail",
                    "error_stage": "fresh_process_probe",
                    "error_class": type(exc).__name__,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 2
    print(
        json.dumps(
            {"result": "pass", "checks": checks},
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
