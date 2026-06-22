from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, cast

from doll import state, workspace
from doll.audit import AuditService
from doll.capabilities import (
    CapabilityDefinition,
    CapabilityRegistry,
    CapabilityRequest,
    CapabilityResourceLimits,
    CapabilityTarget,
    OutboundNetworkPolicy,
    built_in_capability_registry,
)
from doll.confirmation import ConfirmationPreview, ConfirmationService
from doll.confirmation_preflight import ConfirmedCapabilityPreflightService
from doll.settings import PermissionDecision, PermissionMode
from doll.state_repository import StateRepository


class FakePermissionResolver:
    def __init__(self, mode: PermissionMode = "scoped") -> None:
        self.mode = mode
        self.calls: list[tuple[str, dict[str, object]]] = []

    def resolve(self, *, capability_id: str, scope: dict[str, object]) -> PermissionDecision:
        self.calls.append((capability_id, scope))
        reason = "active" if self.mode != "denied" else "no_record"
        return PermissionDecision(
            record_id="permission-1" if self.mode != "denied" else None,
            capability_id=capability_id,
            scope=scope,
            effective_mode=self.mode,
            reason=cast(Literal["active", "no_record"], reason),
        )


class MutableClock:
    def __init__(self) -> None:
        self.now = datetime(2026, 6, 22, 0, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now


def initialized_workspace(tmp_path: Path) -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(tmp_path / "workspace")
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def release_tier3_registry() -> CapabilityRegistry:
    definitions: list[CapabilityDefinition] = []
    for definition in built_in_capability_registry().definitions():
        if definition.capability_id == "adapter.fixed_process.example":
            definition = replace(definition, release_available=True)
        definitions.append(definition)
    return CapabilityRegistry(tuple(definitions))


def tier3_request() -> CapabilityRequest:
    return CapabilityRequest(
        capability_id="adapter.fixed_process.example",
        capability_version="1.0",
        operation_id="operation-tier3",
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


def compute_request() -> CapabilityRequest:
    return CapabilityRequest(
        capability_id="compute.transform",
        capability_version="1.0",
        operation_id="operation-compute",
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


def preview() -> ConfirmationPreview:
    return ConfirmationPreview(
        effect_summary="Run the reviewed fixed adapter and create one managed artifact.",
        irreversible=False,
        recovery_description="The new artifact can be archived without overwriting prior data.",
    )


def preflight_service(
    repository: StateRepository,
    clock: MutableClock,
) -> tuple[
    CapabilityRegistry,
    ConfirmationService,
    FakePermissionResolver,
    ConfirmedCapabilityPreflightService,
]:
    registry = release_tier3_registry()
    confirmations = ConfirmationService(repository, clock=clock)
    permissions = FakePermissionResolver()
    service = ConfirmedCapabilityPreflightService(
        registry=registry,
        permissions=permissions,
        audit=AuditService(repository),
        network_policy=OutboundNetworkPolicy(enabled=False),
        confirmations=confirmations,
    )
    return registry, confirmations, permissions, service
