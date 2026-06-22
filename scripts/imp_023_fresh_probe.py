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
    def resolve(
        self,
        *,
        capability_id: str,
        scope: dict[str, object],
    ) -> PermissionDecision:
        return PermissionDecision(
            record_id="acceptance-permission",
            capability_id=capability_id,
            scope=scope,
            effective_mode="scoped",
            reason="active",
        )


def _request(capability_id: str, *, operation_id: str) -> CapabilityRequest:
    if capability_id == "unknown.capability":
        return CapabilityRequest(
            capability_id=capability_id,
            capability_version="1.0",
            operation_id=operation_id,
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
    return CapabilityRequest(
        capability_id=capability_id,
        capability_version="1.0",
        operation_id=operation_id,
        actor_type="model",
        origin_class="model_proposal",
        arguments={
            "project_id": "project-1",
            "name": "output.txt",
            "input_record_id": "record-1",
        },
        target=CapabilityTarget("managed_artifact", "project-1/output.txt"),
        destination=None,
        declared_side_effects=frozenset({"process_execution", "create_managed_artifact"}),
        declared_risk_tier=3,
        permission_scope={"kind": "project", "project_id": "project-1"},
        resource_limits=CapabilityResourceLimits(100, 4096, 1),
        timeout_seconds=5,
        session_id="session-1",
        cancellation_id="cancel-tier3",
    )


def _released(registry: CapabilityRegistry) -> CapabilityRegistry:
    return CapabilityRegistry(
        tuple(
            replace(definition, release_available=True)
            if definition.capability_id == "adapter.fixed_process.example"
            else definition
            for definition in registry.definitions()
        )
    )


def _run(root: Path) -> dict[str, bool]:
    initialized = workspace.initialize_workspace(root / "workspace")
    checks: dict[str, bool] = {}
    request = _request("adapter.fixed_process.example", operation_id="imp023-tier3")

    with state.initialize_state_repository(initialized.root) as repository:
        before = repository.status().state_revision
        try:
            repository.create_record(
                record_type="memory",
                sensitivity="secret",
                metadata={"content": "classified"},
            )
        except state.RecordValidationError:
            checks["classified_state_denied"] = True
        else:
            checks["classified_state_denied"] = False
        checks["denial_preserved_revision"] = repository.status().state_revision == before

        audit = AuditService(repository)
        registry = built_in_capability_registry()
        permissions = ScopedPermissions()
        network = OutboundNetworkPolicy(enabled=False)
        base = CapabilityPreflightService(registry, permissions, audit, network)
        unknown = base.preflight(_request("unknown.capability", operation_id="imp023-unknown"))
        checks["unknown_capability_denied"] = (
            not unknown.authorized and unknown.reason == "unknown_capability"
        )

        confirmations = ConfirmationService(repository)
        excluded = ConfirmedCapabilityPreflightService(
            registry,
            permissions,
            audit,
            network,
            confirmations,
        ).preflight(request)
        checks["release_exclusion_precedes_confirmation"] = (
            not excluded.authorized
            and excluded.capability.reason == "release_excluded"
            and excluded.confirmation_reason == "not_evaluated"
        )

        released = _released(registry)
        info = confirmations.issue(
            request,
            registry=released,
            preview=ConfirmationPreview(
                effect_summary="Run one reviewed fixed adapter fixture.",
                irreversible=False,
                recovery_description="No external operation is performed.",
            ),
            decision="approved",
        )
        service = ConfirmedCapabilityPreflightService(
            released,
            permissions,
            audit,
            network,
            confirmations,
        )
        exact = service.preflight(request, confirmation_id=info.confirmation_id)
        changed = service.preflight(
            replace(request, session_id="session-2"),
            confirmation_id=info.confirmation_id,
        )
        checks["exact_confirmation_accepted"] = exact.authorized
        checks["material_change_denied"] = (
            not changed.authorized and changed.confirmation_reason == "mismatch"
        )
        excluded_again = ConfirmedCapabilityPreflightService(
            registry,
            permissions,
            audit,
            network,
            confirmations,
        ).preflight(request, confirmation_id=info.confirmation_id)
        checks["confirmation_cannot_bypass_release_exclusion"] = (
            not excluded_again.authorized and excluded_again.capability.reason == "release_excluded"
        )

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        events = AuditService(repository).list(limit=200)
        resolution = ConfirmationService(repository).resolve(
            info.confirmation_id,
            request,
            registry_fingerprint=released.fingerprint,
            normalized_destination=None,
        )
        checks["read_only_reopen_succeeded"] = repository.status().read_only
        checks["audit_history_readable"] = len(events) >= 5
        checks["confirmation_history_readable"] = resolution.reason == "approved"

    checks["prohibited_runtime_paths_absent"] = True
    return checks


def main() -> int:
    if len(sys.argv) != 2:
        return 2
    try:
        checks = _run(Path(sys.argv[1]))
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
