from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
from typing import cast

import pytest
from doll import capabilities as cap
from doll.capabilities import (
    MAX_TARGET_IDENTIFIER_LENGTH,
    MAX_TIMEOUT_SECONDS,
    CapabilityArgument,
    CapabilityArgumentKind,
    CapabilityDefinition,
    CapabilityRegistry,
    CapabilityRegistryError,
    CapabilityRequest,
    CapabilityRequestValidationError,
    CapabilityResourceContract,
    CapabilityResourceLimits,
    CapabilityTarget,
    CapabilityTargetContract,
    CapabilityTargetKind,
    OutboundNetworkPolicy,
    built_in_capability_registry,
)
from doll.instruction_origin import InstructionOriginClass


def definition(capability_id: str) -> CapabilityDefinition:
    return next(
        item
        for item in built_in_capability_registry().definitions()
        if item.capability_id == capability_id
    )


def compute_request() -> CapabilityRequest:
    return CapabilityRequest(
        capability_id="compute.transform",
        capability_version="1.0",
        operation_id="coverage-compute",
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


@pytest.mark.parametrize(
    "bad_definition",
    [
        replace(
            definition("compute.transform"),
            arguments=(cast(CapabilityArgument, "not-an-argument"),),
        ),
        replace(
            definition("compute.transform"),
            target=cast(CapabilityTargetContract, "not-a-target-contract"),
        ),
        replace(
            definition("compute.transform"),
            resource_contract=cast(CapabilityResourceContract, "not-a-resource-contract"),
        ),
        replace(
            definition("compute.transform"),
            resource_contract=CapabilityResourceContract(1, 1, 1, MAX_TIMEOUT_SECONDS + 1),
        ),
        replace(
            definition("compute.transform"),
            description=cast(str, 1),
        ),
    ],
)
def test_registry_defensive_type_and_limit_branches(
    bad_definition: CapabilityDefinition,
) -> None:
    with pytest.raises(CapabilityRegistryError):
        CapabilityRegistry((bad_definition,))


def test_argument_kind_and_target_defensive_fallbacks() -> None:
    integer = CapabilityArgument(
        "count", "integer", required=False, minimum_integer=1, maximum_integer=3
    )
    assert cap._argument_value_matches(integer, 2)
    assert not cap._argument_value_matches(integer, True)
    assert not cap._argument_value_matches(integer, 0)
    assert not cap._argument_value_matches(integer, 4)

    boolean = CapabilityArgument("enabled", "boolean", required=False)
    assert cap._argument_value_matches(boolean, True)
    assert not cap._argument_value_matches(boolean, 1)

    values = CapabilityArgument("values", "string_list", maximum_length=3, maximum_items=2)
    assert cap._argument_value_matches(values, ["a", "bb"])
    assert not cap._argument_value_matches(values, "a")
    assert not cap._argument_value_matches(values, ["a", "b", "c"])
    assert not cap._argument_value_matches(values, ["long"])

    unknown = CapabilityArgument("value", cast(CapabilityArgumentKind, "unknown"), maximum_length=3)
    assert not cap._argument_value_matches(unknown, "x")
    contract = CapabilityTargetContract(cast(CapabilityTargetKind, "unknown"))
    assert not cap._target_matches(contract, CapabilityTarget(contract.kind, "x"))


def test_request_and_mapping_defensive_validation() -> None:
    with pytest.raises(CapabilityRequestValidationError):
        cap._validate_request_envelope(
            replace(compute_request(), timeout_seconds=MAX_TIMEOUT_SECONDS + 1)
        )
    with pytest.raises(CapabilityRequestValidationError):
        cap._safe_mapping(cast(Mapping[str, object], []), "mapping", 100)
    with pytest.raises(CapabilityRequestValidationError):
        cap._safe_mapping(cast(dict[str, object], {1: "value"}), "mapping", 100)
    with pytest.raises(CapabilityRequestValidationError):
        cap._safe_mapping({"bad\x00key": "value"}, "mapping", 100)
    with pytest.raises(CapabilityRequestValidationError):
        cap._safe_mapping({"value": float("nan")}, "mapping", 100)
    with pytest.raises(CapabilityRequestValidationError):
        cap._safe_mapping({"value": "x" * 101}, "mapping", 100)
    with pytest.raises(CapabilityRequestValidationError):
        cap._safe_mapping({"value": [[[[[[[[[["x"]]]]]]]]]]}, "mapping", 1000)
    with pytest.raises(CapabilityRequestValidationError):
        cap._safe_mapping({"value": "bad\x00text"}, "mapping", 100)
    assert cap._safe_mapping(
        {"nested": {"key": "value"}, "items": ["a", "b"]}, "mapping", 1000
    ) == {"nested": {"key": "value"}, "items": ["a", "b"]}


@pytest.mark.parametrize(
    ("call", "error_type"),
    [
        (
            lambda: cap._validate_token("token", cast(str, 1), 10, registry=False),
            CapabilityRequestValidationError,
        ),
        (
            lambda: cap._validate_version(cast(str, 1), registry=False),
            CapabilityRequestValidationError,
        ),
        (
            lambda: cap._validate_text("text", cast(str, 1), 10),
            CapabilityRequestValidationError,
        ),
        (
            lambda: cap._validate_scheme(cast(str, 1)),
            CapabilityRequestValidationError,
        ),
        (
            lambda: cap._plain_optional_integer(cast(int, "one"), "integer"),
            CapabilityRegistryError,
        ),
    ],
)
def test_primitive_validator_type_branches(
    call: Callable[[], object], error_type: type[Exception]
) -> None:
    with pytest.raises(error_type):
        call()


def test_destination_scope_and_network_fallbacks() -> None:
    network_definition = definition("network.fetch_url")
    request = CapabilityRequest(
        capability_id="network.fetch_url",
        capability_version="1.0",
        operation_id="coverage-network",
        actor_type="model",
        origin_class="model_proposal",
        arguments={"url": "https://example.com/"},
        target=CapabilityTarget("url", "https://example.com/"),
        destination=None,
        declared_side_effects=frozenset({"network_read"}),
        declared_risk_tier=2,
        permission_scope={"kind": "destination", "host": "example.com"},
        resource_limits=CapabilityResourceLimits(100, 1024, 1),
        timeout_seconds=5,
        cancellation_id="cancel-network",
    )
    assert cap._destination_for(network_definition, request) is cap._DESTINATION_MISMATCH
    assert cap._permission_scope({}) is None
    assert cap._permission_scope({"kind": "bad kind"}) is None
    assert cap._network_allowed(OutboundNetworkPolicy(enabled=True), "https://example.com/")
    assert cap._normalize_url(cast(str, 1)) is None
    assert cap._normalize_url("https:///missing-host") is None
    assert cap._normalize_url("https://example.com/" + "x" * MAX_TARGET_IDENTIFIER_LENGTH) is None
    assert cap._normalize_host("") is None
    assert cap._normalize_host("x" * 254) is None
    assert cap._normalize_host("\ud800") is None


def test_immutable_collection_and_count_limits() -> None:
    with pytest.raises(CapabilityRegistryError):
        OutboundNetworkPolicy(
            enabled=True,
            allowed_hosts=cast(frozenset[str], ["example.com"]),
        )
    with pytest.raises(CapabilityRegistryError):
        OutboundNetworkPolicy(
            enabled=True,
            allowed_hosts=frozenset(f"host-{index}.example" for index in range(257)),
        )
    with pytest.raises(CapabilityRequestValidationError):
        OutboundNetworkPolicy(enabled=True, allowed_hosts=frozenset({cast(str, 1)}))

    base = definition("compute.transform")
    with pytest.raises(CapabilityRegistryError):
        CapabilityRegistry(tuple(base for _ in range(cap.MAX_CAPABILITY_DEFINITIONS + 1)))
    with pytest.raises(CapabilityRegistryError):
        CapabilityRegistry(
            (
                replace(
                    base,
                    arguments=tuple(
                        CapabilityArgument(f"field-{index}", "text", maximum_length=10)
                        for index in range(cap.MAX_ARGUMENT_FIELDS + 1)
                    ),
                ),
            )
        )
    with pytest.raises(CapabilityRegistryError):
        CapabilityRegistry(
            (
                replace(
                    base,
                    side_effects=cast(frozenset[cap.CapabilitySideEffect], ["read_state"]),
                ),
            )
        )
    with pytest.raises(CapabilityRegistryError):
        CapabilityRegistry(
            (
                replace(
                    base,
                    allowed_request_origins=cast(
                        frozenset[InstructionOriginClass], ["model_proposal"]
                    ),
                ),
            )
        )


def test_registry_binding_contract_rejections() -> None:
    compute = definition("compute.transform")
    state_read = definition("state.read")
    artifact = definition("artifact.create")
    network = definition("network.fetch_url")
    bad_definitions = (
        replace(compute, permission_scope_kind="record"),
        replace(state_read, target=CapabilityTargetContract("provided_data")),
        replace(artifact, target=CapabilityTargetContract("state_record")),
        replace(network, side_effects=frozenset()),
        replace(compute, binding_mode=cast(cap.CapabilityBindingMode, "unknown")),
        replace(compute, release_available=cast(bool, "yes")),
    )
    for bad_definition in bad_definitions:
        with pytest.raises(CapabilityRegistryError):
            CapabilityRegistry((bad_definition,))


def test_request_collection_and_target_kind_validation() -> None:
    with pytest.raises(CapabilityRequestValidationError):
        cap._validate_request_envelope(
            replace(
                compute_request(),
                target=CapabilityTarget(cast(CapabilityTargetKind, "filesystem"), "item"),
            )
        )
    with pytest.raises(CapabilityRequestValidationError):
        cap._validate_request_envelope(
            replace(
                compute_request(),
                declared_side_effects=cast(frozenset[cap.CapabilitySideEffect], ["read_state"]),
            )
        )


def test_binding_and_input_usage_defensive_branches() -> None:
    artifact = definition("artifact.create")
    bad_artifact = replace(
        compute_request(),
        arguments={"project_id": "bad project", "name": "output.txt"},
        target=CapabilityTarget("managed_artifact", "bad project/output.txt"),
        permission_scope={"kind": "project", "project_id": "bad project"},
    )
    assert not cap._bindings_match(
        artifact,
        bad_artifact,
        None,
        {"kind": "project", "project_id": "bad project"},
    )
    network = definition("network.fetch_url")
    assert not cap._bindings_match(network, compute_request(), None, {"kind": "destination"})
    assert not cap._bindings_match(
        network,
        compute_request(),
        "https://example.com/",
        {"kind": "destination", "host": 1},
    )
    assert cap._json_input_usage(["a", None, 2]) == (2, 3)


def test_nondefault_port_and_ipv6_normalization() -> None:
    assert cap._normalize_url("https://example.com:8443/") is None
    assert cap._normalize_url("https://[2606:4700:4700::1111]/") == (
        "https://[2606:4700:4700::1111]/"
    )
