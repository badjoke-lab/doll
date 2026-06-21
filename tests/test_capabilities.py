from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Literal, cast
from urllib.parse import urlsplit

import pytest
from doll import state, workspace
from doll.audit import AuditActorType, AuditResult, AuditService
from doll.capabilities import (
    MAX_TARGET_IDENTIFIER_LENGTH,
    CapabilityArgument,
    CapabilityArgumentKind,
    CapabilityAuditError,
    CapabilityBindingMode,
    CapabilityDefinition,
    CapabilityNetworkMode,
    CapabilityPreflightService,
    CapabilityRegistry,
    CapabilityRegistryError,
    CapabilityRequest,
    CapabilityRequestValidationError,
    CapabilityResourceContract,
    CapabilityResourceLimits,
    CapabilityRiskTier,
    CapabilitySideEffect,
    CapabilityTarget,
    CapabilityTargetContract,
    CapabilityTargetKind,
    OutboundNetworkPolicy,
    built_in_capability_registry,
    default_capability_preflight_service,
)
from doll.instruction_origin import InstructionActorType, InstructionOriginClass
from doll.settings import (
    PermissionDecision,
    PermissionMode,
    PermissionService,
    SettingsError,
)


class FakePermissionResolver:
    def __init__(self, mode: PermissionMode = "scoped", *, fail: bool = False) -> None:
        self.mode = mode
        self.fail = fail
        self.calls: list[tuple[str, dict[str, object]]] = []

    def resolve(self, *, capability_id: str, scope: dict[str, object]) -> PermissionDecision:
        self.calls.append((capability_id, scope))
        if self.fail:
            raise SettingsError("synthetic permission failure")
        reason = "active" if self.mode != "denied" else "no_record"
        return PermissionDecision(
            record_id="permission-1" if self.mode != "denied" else None,
            capability_id=capability_id,
            scope=scope,
            effective_mode=self.mode,
            reason=cast(Literal["active", "no_record"], reason),
        )


class FakeAuditRecorder:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.events: list[dict[str, object]] = []

    def append(
        self,
        *,
        action: str,
        result: AuditResult,
        actor_type: AuditActorType = "system",
        operation_id: str | None = None,
        actor_id: str | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        summary: str | None = None,
        error: BaseException | None = None,
        metadata: dict[str, object] | None = None,
    ) -> object:
        if self.fail:
            raise RuntimeError("synthetic audit failure")
        event: dict[str, object] = {
            "action": action,
            "result": result,
            "actor_type": actor_type,
            "operation_id": operation_id,
            "actor_id": actor_id,
            "target_type": target_type,
            "target_id": target_id,
            "summary": summary,
            "error": error,
            "metadata": metadata or {},
        }
        self.events.append(event)
        return event


def initialized_workspace(tmp_path: Path) -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(tmp_path / "workspace")
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def fake_service(
    *,
    mode: PermissionMode = "scoped",
    permission_failure: bool = False,
    audit_failure: bool = False,
    network_policy: OutboundNetworkPolicy | None = None,
    registry: CapabilityRegistry | None = None,
) -> tuple[CapabilityPreflightService, FakePermissionResolver, FakeAuditRecorder]:
    permissions = FakePermissionResolver(mode, fail=permission_failure)
    audit = FakeAuditRecorder(fail=audit_failure)
    service = CapabilityPreflightService(
        registry=registry or built_in_capability_registry(),
        permissions=permissions,
        audit=audit,
        network_policy=network_policy
        or OutboundNetworkPolicy(enabled=True, allowed_hosts=frozenset({"example.com"})),
    )
    return service, permissions, audit


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


def state_read_request() -> CapabilityRequest:
    return CapabilityRequest(
        capability_id="state.read",
        capability_version="1.0",
        operation_id="operation-state-read",
        actor_type="model",
        origin_class="model_proposal",
        arguments={"record_id": "record-1"},
        target=CapabilityTarget("state_record", "record-1"),
        destination=None,
        declared_side_effects=frozenset({"read_state"}),
        declared_risk_tier=1,
        permission_scope={"kind": "record", "record_id": "record-1"},
        resource_limits=CapabilityResourceLimits(100, 4096, 1),
        timeout_seconds=5,
    )


def artifact_request() -> CapabilityRequest:
    return CapabilityRequest(
        capability_id="artifact.create",
        capability_version="1.0",
        operation_id="operation-artifact",
        actor_type="model",
        origin_class="model_proposal",
        arguments={
            "project_id": "project-1",
            "name": "report.txt",
            "content": "bounded content",
        },
        target=CapabilityTarget("managed_artifact", "project-1/report.txt"),
        destination=None,
        declared_side_effects=frozenset({"create_managed_artifact"}),
        declared_risk_tier=1,
        permission_scope={"kind": "project", "project_id": "project-1"},
        resource_limits=CapabilityResourceLimits(100, 4096, 1),
        timeout_seconds=5,
        cancellation_id="cancel-artifact",
    )


def network_request(url: str = "https://example.com/resource") -> CapabilityRequest:
    host = urlsplit(url).hostname or "missing-host"
    return CapabilityRequest(
        capability_id="network.fetch_url",
        capability_version="1.0",
        operation_id="operation-network",
        actor_type="model",
        origin_class="model_proposal",
        arguments={"url": url},
        target=CapabilityTarget("url", url),
        destination=url,
        declared_side_effects=frozenset({"network_read"}),
        declared_risk_tier=2,
        permission_scope={"kind": "destination", "host": host},
        resource_limits=CapabilityResourceLimits(100, 4096, 1),
        timeout_seconds=5,
        cancellation_id="cancel-network",
    )


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
        cancellation_id="cancel-tier3",
    )


def one_definition(capability_id: str) -> CapabilityDefinition:
    return next(
        definition
        for definition in built_in_capability_registry().definitions()
        if definition.capability_id == capability_id
    )


def test_built_in_registry_is_deterministic_versioned_and_immutable() -> None:
    first = built_in_capability_registry()
    second = CapabilityRegistry(tuple(reversed(first.definitions())))
    assert first.fingerprint == second.fingerprint
    assert first.fingerprint.startswith("sha256:")
    assert len(first.fingerprint) == 71
    assert first.get("state.read", "1.0") is not None
    assert first.get("state.read", "2.0") is None
    assert first.versions("state.read") == ("1.0",)
    assert not hasattr(first, "register")
    assert {definition.risk_tier for definition in first.definitions()} == {
        CapabilityRiskTier.PURE_COMPUTATION,
        CapabilityRiskTier.BOUNDED_READ_OR_REVERSIBLE_CREATE,
        CapabilityRiskTier.SCOPED_MODIFICATION_OR_EXTERNAL_READ,
        CapabilityRiskTier.HIGH_RISK,
    }


def test_registry_rejects_empty_non_sequence_duplicate_and_non_definition() -> None:
    definition = one_definition("compute.transform")
    with pytest.raises(CapabilityRegistryError):
        CapabilityRegistry(())
    with pytest.raises(CapabilityRegistryError):
        CapabilityRegistry(cast(Sequence[CapabilityDefinition], "not-a-sequence"))
    with pytest.raises(CapabilityRegistryError, match="duplicate"):
        CapabilityRegistry((definition, definition))
    with pytest.raises(CapabilityRegistryError):
        CapabilityRegistry((cast(CapabilityDefinition, "not-a-definition"),))


@pytest.mark.parametrize(
    "definition",
    [
        replace(one_definition("compute.transform"), capability_id="generic-shell.run"),
        replace(one_definition("compute.transform"), capability_id="command-runner.execute"),
        replace(
            one_definition("compute.transform"),
            risk_tier=cast(CapabilityRiskTier, 0),
        ),
        replace(one_definition("compute.transform"), arguments=()),
        replace(
            one_definition("compute.transform"),
            arguments=(
                CapabilityArgument("text", "text", maximum_length=10),
                CapabilityArgument("text", "text", maximum_length=10),
            ),
        ),
        replace(
            one_definition("compute.transform"),
            arguments=(CapabilityArgument("command", "text", maximum_length=10),),
        ),
        replace(
            one_definition("compute.transform"),
            arguments=(
                CapabilityArgument(
                    "value",
                    cast(CapabilityArgumentKind, "bytes"),
                    maximum_length=10,
                ),
            ),
        ),
        replace(
            one_definition("compute.transform"),
            arguments=(CapabilityArgument("value", "text", maximum_length=None),),
        ),
        replace(
            one_definition("compute.transform"),
            arguments=(CapabilityArgument("values", "string_list", maximum_length=10),),
        ),
        replace(
            one_definition("compute.transform"),
            arguments=(
                CapabilityArgument("count", "integer", minimum_integer=10, maximum_integer=1),
            ),
        ),
        replace(
            one_definition("compute.transform"),
            target=CapabilityTargetContract(cast(CapabilityTargetKind, "filesystem")),
        ),
        replace(
            one_definition("compute.transform"),
            target=CapabilityTargetContract("provided_data", MAX_TARGET_IDENTIFIER_LENGTH + 1),
        ),
        replace(
            one_definition("compute.transform"),
            side_effects=frozenset({cast(CapabilitySideEffect, "hidden_upload")}),
        ),
        replace(
            one_definition("network.fetch_url"),
            target=CapabilityTargetContract("state_record"),
        ),
        replace(
            one_definition("compute.transform"),
            side_effects=frozenset({"network_read"}),
        ),
        replace(
            one_definition("compute.transform"),
            network_mode=cast(CapabilityNetworkMode, "arbitrary"),
        ),
        replace(
            one_definition("compute.transform"),
            release_available=cast(bool, "yes"),
        ),
        replace(
            one_definition("compute.transform"),
            resource_contract=CapabilityResourceContract(1, 1, 1, 0),
        ),
        replace(
            one_definition("compute.transform"),
            cancellation_required=cast(bool, "yes"),
        ),
        replace(
            one_definition("compute.transform"),
            binding_mode=cast(CapabilityBindingMode, "unknown"),
        ),
        replace(
            one_definition("compute.transform"),
            allowed_request_origins=frozenset(),
        ),
        replace(
            one_definition("compute.transform"),
            allowed_request_origins=frozenset({"external_content"}),
        ),
        replace(
            one_definition("compute.transform"),
            arguments=(
                CapabilityArgument("text", "text", required=cast(bool, "yes"), maximum_length=10),
            ),
        ),
        replace(
            one_definition("compute.transform"),
            side_effects=frozenset({"process_execution"}),
        ),
        replace(one_definition("compute.transform"), description=""),
    ],
)
def test_registry_rejects_unsafe_or_malformed_definitions(
    definition: CapabilityDefinition,
) -> None:
    with pytest.raises(CapabilityRegistryError):
        CapabilityRegistry((definition,))


def test_registry_validates_optional_and_integer_argument_constraints() -> None:
    base = one_definition("compute.transform")
    valid = replace(
        base,
        arguments=(
            CapabilityArgument(
                "count",
                "integer",
                required=False,
                minimum_integer=0,
                maximum_integer=10,
            ),
            CapabilityArgument("labels", "string_list", maximum_length=20, maximum_items=3),
            CapabilityArgument("enabled", "boolean", required=False),
        ),
    )
    registry = CapabilityRegistry((valid,))
    assert registry.get(valid.capability_id, valid.version) == valid


@pytest.mark.parametrize(
    ("capability_request", "reason"),
    [
        (
            replace(compute_request(), capability_id="unknown.capability"),
            "unknown_capability",
        ),
        (replace(compute_request(), capability_version="2.0"), "unsupported_version"),
        (
            replace(compute_request(), actor_type="tool", origin_class="model_proposal"),
            "actor_origin_mismatch",
        ),
        (
            replace(compute_request(), arguments={"text": "hello"}),
            "argument_schema_mismatch",
        ),
        (
            replace(
                compute_request(),
                arguments={"text": "hello", "operation": "uppercase", "extra": True},
            ),
            "argument_schema_mismatch",
        ),
        (
            replace(
                compute_request(),
                arguments={"text": "hello", "operation": 1},
            ),
            "argument_schema_mismatch",
        ),
        (
            replace(compute_request(), target=CapabilityTarget("state_record", "record-1")),
            "target_mismatch",
        ),
        (
            replace(compute_request(), destination="https://example.com/"),
            "destination_mismatch",
        ),
        (
            replace(
                compute_request(),
                declared_side_effects=frozenset({"read_state"}),
            ),
            "side_effect_mismatch",
        ),
        (
            replace(state_read_request(), declared_side_effects=frozenset()),
            "side_effect_mismatch",
        ),
        (replace(state_read_request(), declared_risk_tier=0), "risk_tier_mismatch"),
        (
            replace(
                state_read_request(),
                resource_limits=CapabilityResourceLimits(2_001, 4096, 1),
            ),
            "resource_limit_mismatch",
        ),
        (
            replace(
                state_read_request(),
                resource_limits=CapabilityResourceLimits(1, 4096, 1),
            ),
            "resource_limit_mismatch",
        ),
        (
            replace(
                state_read_request(),
                target=CapabilityTarget("state_record", "record-2"),
            ),
            "binding_mismatch",
        ),
        (
            replace(
                state_read_request(),
                permission_scope={"kind": "record", "record_id": "record-2"},
            ),
            "binding_mismatch",
        ),
        (
            replace(
                artifact_request(),
                target=CapabilityTarget("managed_artifact", "project-1/other.txt"),
            ),
            "binding_mismatch",
        ),
        (
            replace(
                network_request(),
                permission_scope={"kind": "destination", "host": "other.example"},
            ),
            "binding_mismatch",
        ),
        (replace(state_read_request(), timeout_seconds=31), "timeout_mismatch"),
        (replace(artifact_request(), cancellation_id=None), "cancellation_mismatch"),
        (
            replace(compute_request(), cancellation_id="unexpected-cancellation"),
            "cancellation_mismatch",
        ),
    ],
)
def test_preflight_rejects_mismatches_with_secret_safe_audit(
    capability_request: CapabilityRequest, reason: str
) -> None:
    service, _, audit = fake_service()
    decision = service.preflight(capability_request)
    assert decision.authorized is False
    assert decision.reason == reason
    assert len(audit.events) == 1
    assert audit.events[0]["result"] == "denied"
    metadata = cast(dict[str, object], audit.events[0]["metadata"])
    assert metadata["decision_reason"] == reason
    assert "arguments" not in metadata
    assert "destination" not in metadata


@pytest.mark.parametrize(
    "capability_request",
    [
        cast(object, "not-a-request"),
        replace(compute_request(), capability_id="bad id"),
        replace(compute_request(), capability_version="latest"),
        replace(compute_request(), operation_id="bad operation"),
        replace(compute_request(), session_id="bad session"),
        replace(compute_request(), actor_type=cast(InstructionActorType, "agent")),
        replace(compute_request(), origin_class=cast(InstructionOriginClass, "page")),
        replace(compute_request(), arguments=cast(Mapping[str, object], [])),
        replace(compute_request(), arguments={"text": object()}),
        replace(
            compute_request(),
            arguments={
                "text": "hello",
                "operation": "uppercase",
                "extra": {1: "invalid-key"},
            },
        ),
        replace(compute_request(), target=cast(CapabilityTarget, "inline")),
        replace(compute_request(), destination="bad\x00destination"),
        replace(
            compute_request(),
            declared_side_effects=frozenset({cast(CapabilitySideEffect, "hidden_upload")}),
        ),
        replace(compute_request(), declared_risk_tier=cast(int, True)),
        replace(compute_request(), declared_risk_tier=4),
        replace(compute_request(), permission_scope=cast(Mapping[str, object], [])),
        replace(compute_request(), resource_limits=cast(CapabilityResourceLimits, None)),
        replace(
            compute_request(),
            resource_limits=CapabilityResourceLimits(0, 1, 1),
        ),
        replace(compute_request(), timeout_seconds=0),
        replace(compute_request(), cancellation_id="bad cancellation"),
    ],
)
def test_malformed_request_envelopes_fail_before_audit(
    capability_request: object,
) -> None:
    service, _, audit = fake_service()
    with pytest.raises(CapabilityRequestValidationError):
        service.preflight(cast(CapabilityRequest, capability_request))
    assert audit.events == []


@pytest.mark.parametrize(
    ("mode", "authorized", "reason"),
    [
        ("denied", False, "permission_denied"),
        ("ask", False, "permission_requires_user_action"),
        ("allow_once", True, "authorized"),
        ("scoped", True, "authorized"),
    ],
)
def test_permission_modes_are_resolved_without_consuming_allow_once(
    mode: PermissionMode, authorized: bool, reason: str
) -> None:
    service, permissions, _ = fake_service(mode=mode)
    decision = service.preflight(state_read_request())
    assert decision.authorized is authorized
    assert decision.reason == reason
    assert decision.permission_mode == mode
    assert permissions.calls == [("state.read", {"kind": "record", "record_id": "record-1"})]


def test_permission_scope_and_permission_service_failures_deny() -> None:
    service, permissions, _ = fake_service()
    wrong_scope = replace(
        state_read_request(),
        permission_scope={"kind": "project", "project_id": "project-1"},
    )
    assert service.preflight(wrong_scope).reason == "permission_denied"
    assert permissions.calls == []

    service, permissions, _ = fake_service(permission_failure=True)
    assert service.preflight(state_read_request()).reason == "permission_denied"
    assert len(permissions.calls) == 1


def test_compute_authorization_never_queries_permission_service() -> None:
    service, permissions, audit = fake_service(mode="denied")
    wrong_scope = replace(compute_request(), permission_scope={"kind": "global"})
    assert service.preflight(wrong_scope).reason == "permission_denied"
    assert permissions.calls == []

    decision = service.preflight(compute_request())
    assert decision.authorized is True
    assert decision.risk_tier is CapabilityRiskTier.PURE_COMPUTATION
    assert decision.permission_mode is None
    assert permissions.calls == []
    assert [event["result"] for event in audit.events] == ["denied", "success"]


def test_artifact_target_rejects_escape_and_accepts_bounded_relative_path() -> None:
    service, _, _ = fake_service()
    assert service.preflight(artifact_request()).authorized is True
    for unsafe in (
        "../escape.txt",
        "/absolute.txt",
        "folder\\escape.txt",
        "./same.txt",
    ):
        decision = service.preflight(
            replace(artifact_request(), target=CapabilityTarget("managed_artifact", unsafe))
        )
        assert decision.reason == "target_mismatch"


@pytest.mark.parametrize(
    ("url", "policy", "reason"),
    [
        (
            "https://example.com/resource",
            OutboundNetworkPolicy(enabled=False),
            "network_denied",
        ),
        (
            "http://example.com/resource",
            OutboundNetworkPolicy(
                enabled=True,
                allowed_schemes=frozenset({"https"}),
                allowed_hosts=frozenset({"example.com"}),
            ),
            "network_denied",
        ),
        (
            "https://other.example/resource",
            OutboundNetworkPolicy(
                enabled=True,
                allowed_hosts=frozenset({"example.com"}),
                allow_subdomains=False,
            ),
            "network_denied",
        ),
        (
            "https://sub.example.com/resource",
            OutboundNetworkPolicy(
                enabled=True,
                allowed_hosts=frozenset({"example.com"}),
                allow_subdomains=True,
            ),
            "authorized",
        ),
        (
            "https://127.0.0.1/resource",
            OutboundNetworkPolicy(enabled=True),
            "network_denied",
        ),
        (
            "https://10.0.0.1/resource",
            OutboundNetworkPolicy(enabled=True),
            "network_denied",
        ),
        (
            "https://service.local/resource",
            OutboundNetworkPolicy(enabled=True),
            "network_denied",
        ),
    ],
)
def test_network_policy_and_private_destination_controls(
    url: str, policy: OutboundNetworkPolicy, reason: str
) -> None:
    service, _, _ = fake_service(network_policy=policy)
    decision = service.preflight(network_request(url))
    assert decision.reason == reason
    assert decision.authorized is (reason == "authorized")


def test_url_target_argument_and_destination_must_normalize_to_same_value() -> None:
    service, _, _ = fake_service()
    request = network_request("https://EXAMPLE.com:443/resource")
    decision = service.preflight(request)
    assert decision.authorized is True
    assert decision.normalized_destination == "https://example.com/resource"

    mismatched = replace(request, destination="https://example.com/other")
    assert service.preflight(mismatched).reason == "destination_mismatch"


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.com/resource",
        "https://user@example.com/resource",
        "https://example.com/resource#fragment",
        "https://bad_host.example/resource",
        "https://example.com:99999/resource",
    ],
)
def test_invalid_url_contracts_are_target_mismatches(url: str) -> None:
    service, _, _ = fake_service()
    assert service.preflight(network_request(url)).reason == "target_mismatch"


def test_network_policy_constructor_rejects_invalid_configuration() -> None:
    with pytest.raises(CapabilityRegistryError):
        OutboundNetworkPolicy(enabled=cast(bool, "yes"))
    with pytest.raises(CapabilityRegistryError):
        OutboundNetworkPolicy(enabled=True, allow_subdomains=cast(bool, "yes"))
    with pytest.raises(CapabilityRequestValidationError):
        OutboundNetworkPolicy(enabled=True, allowed_schemes=frozenset({"ftp"}))
    with pytest.raises(CapabilityRequestValidationError):
        OutboundNetworkPolicy(enabled=True, allowed_hosts=frozenset({"localhost"}))


def test_release_excluded_and_tier3_confirmation_boundary_are_distinct() -> None:
    service, _, _ = fake_service()
    assert service.preflight(tier3_request()).reason == "release_excluded"

    definition = replace(one_definition("adapter.fixed_process.example"), release_available=True)
    registry = CapabilityRegistry((definition,))
    service, permissions, _ = fake_service(registry=registry)
    decision = service.preflight(tier3_request())
    assert decision.reason == "tier3_confirmation_unavailable"
    assert permissions.calls == []


def test_required_audit_failure_fails_closed_for_allow_and_deny() -> None:
    service, _, _ = fake_service(audit_failure=True)
    with pytest.raises(CapabilityAuditError):
        service.preflight(compute_request())
    with pytest.raises(CapabilityAuditError):
        service.preflight(replace(compute_request(), capability_id="unknown.capability"))


@pytest.mark.parametrize(
    ("actor", "origin", "audit_actor", "authorized"),
    [
        ("user", "current_user_instruction", "user", True),
        ("user", "user_management_action", "user", True),
        ("system", "system_policy", "system", True),
        ("model", "model_proposal", "model", True),
        ("user", "durable_user_policy", "user", False),
        ("runtime", "runtime_output", "runtime", False),
        ("tool", "tool_result", "capability", False),
        ("retriever", "external_content", "capability", False),
        ("importer", "imported_data", "capability", False),
        ("unknown", "unknown", "capability", False),
    ],
)
def test_actor_origin_pairs_are_audited_and_data_origins_cannot_request_capabilities(
    actor: InstructionActorType,
    origin: InstructionOriginClass,
    audit_actor: AuditActorType,
    authorized: bool,
) -> None:
    service, _, audit = fake_service()
    request = replace(
        compute_request(),
        actor_type=actor,
        origin_class=origin,
    )
    decision = service.preflight(request)
    assert decision.authorized is authorized
    assert decision.reason == ("authorized" if authorized else "actor_origin_mismatch")
    assert audit.events[0]["actor_type"] == audit_actor


def test_actual_permission_service_allow_once_is_not_consumed_by_preflight(
    tmp_path: Path,
) -> None:
    initialized = initialized_workspace(tmp_path)
    scope: dict[str, object] = {"kind": "record", "record_id": "record-1"}
    with state.open_state_repository(initialized.root) as repository:
        permissions = PermissionService(repository)
        created = permissions.create(
            capability_id="state.read",
            scope=scope,
            mode="allow_once",
            operation_id="permission-create",
        )
        service = default_capability_preflight_service(
            permissions=permissions,
            audit=AuditService(repository),
            network_policy=OutboundNetworkPolicy(enabled=False),
        )
        decision = service.preflight(state_read_request())
        assert decision.authorized is True
        unchanged = permissions.get(created.record_id)
        assert unchanged.mode == "allow_once"
        assert unchanged.remaining_uses == 1
        assert unchanged.revision == 1
        events = AuditService(repository).list(limit=10)
        assert any(
            event.action == "capability.preflight" and event.result == "success" for event in events
        )


def test_actual_permission_denial_is_audited(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        service = default_capability_preflight_service(
            permissions=PermissionService(repository),
            audit=AuditService(repository),
            network_policy=OutboundNetworkPolicy(enabled=False),
        )
        decision = service.preflight(state_read_request())
        assert decision.reason == "permission_denied"
        event = AuditService(repository).list(action="capability.preflight", limit=1)[0]
        assert event.result == "denied"
        assert event.metadata["decision_reason"] == "permission_denied"
