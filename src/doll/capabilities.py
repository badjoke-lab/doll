"""Immutable capability registry and model-independent authorization preflight."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import IntEnum
from pathlib import PurePosixPath
from types import MappingProxyType
from typing import Literal, Protocol, cast
from urllib.parse import SplitResult, urlsplit, urlunsplit

from doll.audit import AuditActorType, AuditService
from doll.instruction_origin import InstructionActorType, InstructionOriginClass
from doll.settings import PermissionDecision, PermissionService, SettingsError
from doll.state import StateError

CapabilityArgumentKind = Literal["text", "integer", "boolean", "string_list"]
CapabilityTargetKind = Literal["provided_data", "state_record", "managed_artifact", "url"]
CapabilitySideEffect = Literal[
    "read_state",
    "create_managed_artifact",
    "network_read",
    "process_execution",
]
CapabilityNetworkMode = Literal["none", "explicit_url"]
CapabilityBindingMode = Literal["none", "record_identity", "project_artifact", "destination_host"]
CapabilityDecisionReason = Literal[
    "authorized",
    "unknown_capability",
    "unsupported_version",
    "argument_schema_mismatch",
    "target_mismatch",
    "destination_mismatch",
    "binding_mismatch",
    "side_effect_mismatch",
    "risk_tier_mismatch",
    "resource_limit_mismatch",
    "timeout_mismatch",
    "cancellation_mismatch",
    "release_excluded",
    "permission_denied",
    "permission_requires_user_action",
    "network_denied",
    "actor_origin_mismatch",
    "tier3_confirmation_unavailable",
]

REGISTRY_SCHEMA_VERSION = 1
MAX_CAPABILITY_DEFINITIONS = 256
MAX_ARGUMENT_FIELDS = 32
MAX_CAPABILITY_ID_LENGTH = 120
MAX_VERSION_LENGTH = 32
MAX_OPERATION_ID_LENGTH = 200
MAX_SESSION_ID_LENGTH = 200
MAX_CANCELLATION_ID_LENGTH = 200
MAX_ARGUMENT_NAME_LENGTH = 80
MAX_ARGUMENT_TEXT_LENGTH = 16_000
MAX_ARGUMENT_LIST_ITEMS = 256
MAX_ARGUMENT_JSON_BYTES = 32 * 1024
MAX_TARGET_IDENTIFIER_LENGTH = 2_048
MAX_PERMISSION_SCOPE_BYTES = 4_096
MAX_TIMEOUT_SECONDS = 3_600

_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
_VERSION_PATTERN = re.compile(r"^[0-9]+(?:\.[0-9]+){0,2}$")
_HOST_LABEL_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_PROHIBITED_ARGUMENT_NAMES = frozenset(
    {
        "argv",
        "command",
        "command_line",
        "executable",
        "permission",
        "permission_mode",
        "registry",
        "risk_tier",
        "shell",
    }
)
_PROHIBITED_CAPABILITY_PATTERN = re.compile(
    r"(?:^|[._:-])(?:shell|command(?:[._:-]?runner)?)(?:$|[._:-])", re.IGNORECASE
)
_PROHIBITED_CAPABILITY_MARKERS = (
    "arbitrary-command",
    "arbitrary_command",
    "command-runner",
    "command_runner",
    "generic-shell",
    "generic_shell",
    "unrestricted-shell",
    "unrestricted_shell",
)
_ALLOWED_REQUEST_ORIGINS: frozenset[InstructionOriginClass] = frozenset(
    {
        "system_policy",
        "current_user_instruction",
        "user_management_action",
        "model_proposal",
    }
)
_ORIGIN_ACTORS: dict[InstructionOriginClass, frozenset[InstructionActorType]] = {
    "system_policy": frozenset({"system"}),
    "current_user_instruction": frozenset({"user"}),
    "durable_user_policy": frozenset({"user"}),
    "user_management_action": frozenset({"user"}),
    "external_content": frozenset({"retriever", "extractor"}),
    "imported_data": frozenset({"importer"}),
    "tool_result": frozenset({"tool"}),
    "runtime_output": frozenset({"runtime"}),
    "model_proposal": frozenset({"model"}),
    "unknown": frozenset({"unknown"}),
}


class CapabilityRiskTier(IntEnum):
    """Reviewed risk classification fixed by the registry."""

    PURE_COMPUTATION = 0
    BOUNDED_READ_OR_REVERSIBLE_CREATE = 1
    SCOPED_MODIFICATION_OR_EXTERNAL_READ = 2
    HIGH_RISK = 3


class CapabilityError(RuntimeError):
    """Base class for capability-boundary failures."""


class CapabilityRegistryError(CapabilityError):
    """Raised when immutable registry construction fails."""


class CapabilityRequestValidationError(CapabilityError):
    """Raised when a request envelope cannot be handled safely."""


class CapabilityAuditError(CapabilityError):
    """Raised when required authorization audit persistence fails."""


@dataclass(frozen=True, slots=True)
class CapabilityArgument:
    """One bounded argument field in a reviewed capability contract."""

    name: str
    kind: CapabilityArgumentKind
    required: bool = True
    maximum_length: int | None = None
    minimum_integer: int | None = None
    maximum_integer: int | None = None
    maximum_items: int | None = None


@dataclass(frozen=True, slots=True)
class CapabilityTargetContract:
    """Reviewed target type and identifier constraints."""

    kind: CapabilityTargetKind
    maximum_identifier_length: int = MAX_TARGET_IDENTIFIER_LENGTH


@dataclass(frozen=True, slots=True)
class CapabilityResourceLimits:
    """Complete request-side resource limits."""

    max_input_chars: int
    max_output_bytes: int
    max_items: int


@dataclass(frozen=True, slots=True)
class CapabilityResourceContract:
    """Maximum limits accepted by one capability definition."""

    max_input_chars: int
    max_output_bytes: int
    max_items: int
    max_timeout_seconds: int


@dataclass(frozen=True, slots=True)
class CapabilityDefinition:
    """One immutable reviewed capability definition."""

    capability_id: str
    version: str
    risk_tier: CapabilityRiskTier
    arguments: tuple[CapabilityArgument, ...]
    target: CapabilityTargetContract
    side_effects: frozenset[CapabilitySideEffect]
    permission_scope_kind: str
    network_mode: CapabilityNetworkMode
    binding_mode: CapabilityBindingMode
    allowed_request_origins: frozenset[InstructionOriginClass]
    release_available: bool
    resource_contract: CapabilityResourceContract
    cancellation_required: bool
    description: str


@dataclass(frozen=True, slots=True)
class CapabilityTarget:
    """Declared operation target."""

    kind: CapabilityTargetKind
    identifier: str


@dataclass(frozen=True, slots=True)
class CapabilityRequest:
    """Structured untrusted request evaluated before any execution adapter."""

    capability_id: str
    capability_version: str
    operation_id: str
    actor_type: InstructionActorType
    origin_class: InstructionOriginClass
    arguments: Mapping[str, object]
    target: CapabilityTarget
    destination: str | None
    declared_side_effects: frozenset[CapabilitySideEffect]
    declared_risk_tier: int
    permission_scope: Mapping[str, object]
    resource_limits: CapabilityResourceLimits
    timeout_seconds: int
    session_id: str | None = None
    cancellation_id: str | None = None


@dataclass(frozen=True, slots=True)
class OutboundNetworkPolicy:
    """Immutable preflight-only outbound policy; no DNS or network access occurs."""

    enabled: bool
    allowed_schemes: frozenset[str] = frozenset({"https"})
    allowed_hosts: frozenset[str] = frozenset()
    allow_subdomains: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool):
            raise CapabilityRegistryError("network policy enabled flag must be boolean")
        if not isinstance(self.allow_subdomains, bool):
            raise CapabilityRegistryError("network policy subdomain flag must be boolean")
        if not isinstance(self.allowed_schemes, frozenset) or not isinstance(
            self.allowed_hosts, frozenset
        ):
            raise CapabilityRegistryError("network policy collections must be immutable sets")
        if len(self.allowed_schemes) > 2 or len(self.allowed_hosts) > 256:
            raise CapabilityRegistryError("network policy exceeds configured entry limits")
        schemes = frozenset(_validate_scheme(value) for value in self.allowed_schemes)
        hosts = frozenset(_validate_policy_host(value) for value in self.allowed_hosts)
        object.__setattr__(self, "allowed_schemes", schemes)
        object.__setattr__(self, "allowed_hosts", hosts)


@dataclass(frozen=True, slots=True)
class CapabilityPreflightDecision:
    """Authorization result; an authorized result still performs no side effect."""

    authorized: bool
    reason: CapabilityDecisionReason
    capability_id: str
    capability_version: str
    operation_id: str
    risk_tier: CapabilityRiskTier | None
    registry_fingerprint: str
    permission_mode: str | None
    normalized_destination: str | None


class PermissionResolver(Protocol):
    def resolve(self, *, capability_id: str, scope: dict[str, object]) -> PermissionDecision: ...


class AuditRecorder(Protocol):
    def append(
        self,
        *,
        action: str,
        result: Literal["success", "denied", "failed", "cancelled", "partial"],
        actor_type: AuditActorType = "system",
        operation_id: str | None = None,
        actor_id: str | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        summary: str | None = None,
        error: BaseException | None = None,
        metadata: dict[str, object] | None = None,
    ) -> object: ...


class CapabilityRegistry:
    """Versioned registry sealed at construction time."""

    __slots__ = ("_definitions", "_fingerprint")

    def __init__(self, definitions: Sequence[CapabilityDefinition]) -> None:
        if isinstance(definitions, (str, bytes)) or not isinstance(definitions, Sequence):
            raise CapabilityRegistryError("capability definitions must be a sequence")
        entries = tuple(definitions)
        if len(entries) > MAX_CAPABILITY_DEFINITIONS:
            raise CapabilityRegistryError(
                f"capability registry exceeds {MAX_CAPABILITY_DEFINITIONS} definitions"
            )
        registered: dict[tuple[str, str], CapabilityDefinition] = {}
        for definition in entries:
            safe = _validate_definition(definition)
            key = (safe.capability_id, safe.version)
            if key in registered:
                raise CapabilityRegistryError(
                    f"duplicate capability registration: {safe.capability_id}@{safe.version}"
                )
            registered[key] = safe
        if not registered:
            raise CapabilityRegistryError("capability registry must not be empty")
        ordered = dict(sorted(registered.items()))
        self._definitions = MappingProxyType(ordered)
        self._fingerprint = _registry_fingerprint(tuple(ordered.values()))

    @property
    def fingerprint(self) -> str:
        return self._fingerprint

    def get(self, capability_id: str, version: str) -> CapabilityDefinition | None:
        return self._definitions.get((capability_id, version))

    def versions(self, capability_id: str) -> tuple[str, ...]:
        return tuple(
            version
            for registered_id, version in self._definitions
            if registered_id == capability_id
        )

    def definitions(self) -> tuple[CapabilityDefinition, ...]:
        return tuple(self._definitions.values())


@dataclass(slots=True)
class CapabilityPreflightService:
    """Validate and authorize requests without invoking any capability adapter."""

    registry: CapabilityRegistry
    permissions: PermissionResolver
    audit: AuditRecorder
    network_policy: OutboundNetworkPolicy

    def preflight(self, request: CapabilityRequest) -> CapabilityPreflightDecision:
        envelope = _validate_request_envelope(request)
        capability_id = envelope.capability_id
        version = envelope.capability_version
        operation_id = envelope.operation_id

        versions = self.registry.versions(capability_id)
        if not versions:
            return self._deny(envelope, "unknown_capability", risk_tier=None)
        definition = self.registry.get(capability_id, version)
        if definition is None:
            return self._deny(envelope, "unsupported_version", risk_tier=None)

        if (
            not _actor_matches_origin(envelope.actor_type, envelope.origin_class)
            or envelope.origin_class not in definition.allowed_request_origins
        ):
            return self._deny(envelope, "actor_origin_mismatch", risk_tier=definition.risk_tier)
        if not _arguments_match(definition, envelope.arguments):
            return self._deny(envelope, "argument_schema_mismatch", risk_tier=definition.risk_tier)
        if not _target_matches(definition.target, envelope.target):
            return self._deny(envelope, "target_mismatch", risk_tier=definition.risk_tier)
        normalized_destination = _destination_for(definition, envelope)
        if normalized_destination is _DESTINATION_MISMATCH:
            return self._deny(envelope, "destination_mismatch", risk_tier=definition.risk_tier)
        destination = cast(str | None, normalized_destination)
        if envelope.declared_side_effects != definition.side_effects:
            return self._deny(envelope, "side_effect_mismatch", risk_tier=definition.risk_tier)
        if envelope.declared_risk_tier != int(definition.risk_tier):
            return self._deny(envelope, "risk_tier_mismatch", risk_tier=definition.risk_tier)
        if not _resource_limits_match(
            definition.resource_contract, envelope.resource_limits
        ) or not _declared_limits_cover_request(envelope):
            return self._deny(envelope, "resource_limit_mismatch", risk_tier=definition.risk_tier)
        if not _timeout_matches(definition.resource_contract, envelope.timeout_seconds):
            return self._deny(envelope, "timeout_mismatch", risk_tier=definition.risk_tier)
        if not _cancellation_matches(definition, envelope.cancellation_id):
            return self._deny(envelope, "cancellation_mismatch", risk_tier=definition.risk_tier)

        scope = _permission_scope(envelope.permission_scope)
        if scope is None or scope.get("kind") != definition.permission_scope_kind:
            return self._deny(envelope, "permission_denied", risk_tier=definition.risk_tier)
        if not _bindings_match(definition, envelope, destination, scope):
            return self._deny(envelope, "binding_mismatch", risk_tier=definition.risk_tier)
        if not definition.release_available:
            return self._deny(envelope, "release_excluded", risk_tier=definition.risk_tier)
        if definition.risk_tier is CapabilityRiskTier.HIGH_RISK:
            return self._deny(
                envelope,
                "tier3_confirmation_unavailable",
                risk_tier=definition.risk_tier,
            )

        permission_mode: str | None = None
        if definition.permission_scope_kind != "none":
            try:
                permission = self.permissions.resolve(
                    capability_id=definition.capability_id,
                    scope=scope,
                )
            except (SettingsError, StateError):
                return self._deny(envelope, "permission_denied", risk_tier=definition.risk_tier)
            permission_mode = permission.effective_mode
            if permission.effective_mode == "ask":
                return self._deny(
                    envelope,
                    "permission_requires_user_action",
                    risk_tier=definition.risk_tier,
                    permission_mode=permission_mode,
                )
            if permission.effective_mode not in {"allow_once", "scoped"}:
                return self._deny(
                    envelope,
                    "permission_denied",
                    risk_tier=definition.risk_tier,
                    permission_mode=permission_mode,
                )

        if definition.network_mode == "explicit_url":
            assert destination is not None
            if not _network_allowed(self.network_policy, destination):
                return self._deny(
                    envelope,
                    "network_denied",
                    risk_tier=definition.risk_tier,
                    permission_mode=permission_mode,
                )

        decision = CapabilityPreflightDecision(
            authorized=True,
            reason="authorized",
            capability_id=capability_id,
            capability_version=version,
            operation_id=operation_id,
            risk_tier=definition.risk_tier,
            registry_fingerprint=self.registry.fingerprint,
            permission_mode=permission_mode,
            normalized_destination=destination,
        )
        self._audit_decision(envelope, decision)
        return decision

    def _deny(
        self,
        request: CapabilityRequest,
        reason: CapabilityDecisionReason,
        *,
        risk_tier: CapabilityRiskTier | None,
        permission_mode: str | None = None,
    ) -> CapabilityPreflightDecision:
        decision = CapabilityPreflightDecision(
            authorized=False,
            reason=reason,
            capability_id=request.capability_id,
            capability_version=request.capability_version,
            operation_id=request.operation_id,
            risk_tier=risk_tier,
            registry_fingerprint=self.registry.fingerprint,
            permission_mode=permission_mode,
            normalized_destination=None,
        )
        self._audit_decision(request, decision)
        return decision

    def _audit_decision(
        self, request: CapabilityRequest, decision: CapabilityPreflightDecision
    ) -> None:
        try:
            self.audit.append(
                action="capability.preflight",
                result="success" if decision.authorized else "denied",
                actor_type=_audit_actor(request.actor_type),
                operation_id=request.operation_id,
                target_type="capability_request",
                target_id=request.operation_id,
                summary=(
                    "Capability preflight authorized"
                    if decision.authorized
                    else "Capability preflight denied"
                ),
                metadata={
                    "capability_id": request.capability_id,
                    "capability_version": request.capability_version,
                    "origin_class": request.origin_class,
                    "target_kind": request.target.kind,
                    "risk_tier": (
                        int(decision.risk_tier) if decision.risk_tier is not None else None
                    ),
                    "decision_reason": decision.reason,
                    "side_effect_count": len(request.declared_side_effects),
                },
            )
        except BaseException as exc:
            raise CapabilityAuditError(
                "capability authorization failed because required audit persistence failed"
            ) from exc


_DESTINATION_MISMATCH = object()


def built_in_capability_registry() -> CapabilityRegistry:
    """Return the conservative built-in IMP-021 registry."""

    definitions = (
        CapabilityDefinition(
            capability_id="compute.transform",
            version="1.0",
            risk_tier=CapabilityRiskTier.PURE_COMPUTATION,
            arguments=(
                CapabilityArgument("text", "text", maximum_length=16_000),
                CapabilityArgument("operation", "text", maximum_length=80),
            ),
            target=CapabilityTargetContract("provided_data", maximum_identifier_length=120),
            side_effects=frozenset(),
            permission_scope_kind="none",
            network_mode="none",
            binding_mode="none",
            allowed_request_origins=_ALLOWED_REQUEST_ORIGINS,
            release_available=True,
            resource_contract=CapabilityResourceContract(
                max_input_chars=16_000,
                max_output_bytes=64 * 1024,
                max_items=16,
                max_timeout_seconds=30,
            ),
            cancellation_required=False,
            description="Deterministic transformation of data already supplied by the caller.",
        ),
        CapabilityDefinition(
            capability_id="state.read",
            version="1.0",
            risk_tier=CapabilityRiskTier.BOUNDED_READ_OR_REVERSIBLE_CREATE,
            arguments=(CapabilityArgument("record_id", "text", maximum_length=200),),
            target=CapabilityTargetContract("state_record", maximum_identifier_length=200),
            side_effects=frozenset({"read_state"}),
            permission_scope_kind="record",
            network_mode="none",
            binding_mode="record_identity",
            allowed_request_origins=_ALLOWED_REQUEST_ORIGINS,
            release_available=True,
            resource_contract=CapabilityResourceContract(
                max_input_chars=2_000,
                max_output_bytes=256 * 1024,
                max_items=100,
                max_timeout_seconds=30,
            ),
            cancellation_required=False,
            description="Read one explicitly scoped managed state record.",
        ),
        CapabilityDefinition(
            capability_id="artifact.create",
            version="1.0",
            risk_tier=CapabilityRiskTier.BOUNDED_READ_OR_REVERSIBLE_CREATE,
            arguments=(
                CapabilityArgument("project_id", "text", maximum_length=120),
                CapabilityArgument("name", "text", maximum_length=240),
                CapabilityArgument("content", "text", maximum_length=16_000),
            ),
            target=CapabilityTargetContract("managed_artifact", maximum_identifier_length=500),
            side_effects=frozenset({"create_managed_artifact"}),
            permission_scope_kind="project",
            network_mode="none",
            binding_mode="project_artifact",
            allowed_request_origins=_ALLOWED_REQUEST_ORIGINS,
            release_available=True,
            resource_contract=CapabilityResourceContract(
                max_input_chars=16_000,
                max_output_bytes=1024 * 1024,
                max_items=16,
                max_timeout_seconds=60,
            ),
            cancellation_required=True,
            description="Create a new managed artifact without overwrite.",
        ),
        CapabilityDefinition(
            capability_id="network.fetch_url",
            version="1.0",
            risk_tier=CapabilityRiskTier.SCOPED_MODIFICATION_OR_EXTERNAL_READ,
            arguments=(CapabilityArgument("url", "text", maximum_length=2_048),),
            target=CapabilityTargetContract("url", maximum_identifier_length=2_048),
            side_effects=frozenset({"network_read"}),
            permission_scope_kind="destination",
            network_mode="explicit_url",
            binding_mode="destination_host",
            allowed_request_origins=_ALLOWED_REQUEST_ORIGINS,
            release_available=True,
            resource_contract=CapabilityResourceContract(
                max_input_chars=4_096,
                max_output_bytes=2 * 1024 * 1024,
                max_items=8,
                max_timeout_seconds=60,
            ),
            cancellation_required=True,
            description="Retrieve one explicit URL within outbound policy.",
        ),
        CapabilityDefinition(
            capability_id="adapter.fixed_process.example",
            version="1.0",
            risk_tier=CapabilityRiskTier.HIGH_RISK,
            arguments=(
                CapabilityArgument("project_id", "text", maximum_length=120),
                CapabilityArgument("name", "text", maximum_length=240),
                CapabilityArgument("input_record_id", "text", maximum_length=200),
            ),
            target=CapabilityTargetContract("managed_artifact", maximum_identifier_length=500),
            side_effects=frozenset({"process_execution", "create_managed_artifact"}),
            permission_scope_kind="project",
            network_mode="none",
            binding_mode="project_artifact",
            allowed_request_origins=_ALLOWED_REQUEST_ORIGINS,
            release_available=False,
            resource_contract=CapabilityResourceContract(
                max_input_chars=4_096,
                max_output_bytes=1024 * 1024,
                max_items=4,
                max_timeout_seconds=60,
            ),
            cancellation_required=True,
            description=(
                "Release-excluded example of a dedicated fixed adapter; "
                "no command string is accepted."
            ),
        ),
    )
    return CapabilityRegistry(definitions)


def default_capability_preflight_service(
    *,
    permissions: PermissionService,
    audit: AuditService,
    network_policy: OutboundNetworkPolicy,
) -> CapabilityPreflightService:
    """Construct the default preflight boundary from existing authoritative services."""

    return CapabilityPreflightService(
        registry=built_in_capability_registry(),
        permissions=permissions,
        audit=audit,
        network_policy=network_policy,
    )


def _validate_definition(definition: CapabilityDefinition) -> CapabilityDefinition:
    if not isinstance(definition, CapabilityDefinition):
        raise CapabilityRegistryError("registry entries must be CapabilityDefinition values")
    capability_id = _validate_token(
        "capability ID",
        definition.capability_id,
        MAX_CAPABILITY_ID_LENGTH,
        registry=True,
    )
    lowered_id = capability_id.lower()
    if _PROHIBITED_CAPABILITY_PATTERN.search(lowered_id) or any(
        marker in lowered_id for marker in _PROHIBITED_CAPABILITY_MARKERS
    ):
        raise CapabilityRegistryError(
            "generic command and unrestricted shell capabilities are prohibited"
        )
    version = _validate_version(definition.version)
    if type(definition.risk_tier) is not CapabilityRiskTier:
        raise CapabilityRegistryError("capability risk tier must be a reviewed CapabilityRiskTier")
    if not isinstance(definition.arguments, tuple) or not definition.arguments:
        raise CapabilityRegistryError("capability argument schema must be a non-empty tuple")
    if len(definition.arguments) > MAX_ARGUMENT_FIELDS:
        raise CapabilityRegistryError(
            f"capability argument schema exceeds {MAX_ARGUMENT_FIELDS} fields"
        )
    names: set[str] = set()
    arguments: list[CapabilityArgument] = []
    for argument in definition.arguments:
        safe = _validate_argument_definition(argument)
        if safe.name in names:
            raise CapabilityRegistryError(f"duplicate argument field: {safe.name}")
        names.add(safe.name)
        arguments.append(safe)
    target = _validate_target_contract(definition.target)
    if not isinstance(definition.side_effects, frozenset):
        raise CapabilityRegistryError("capability side effects must be an immutable set")
    effects = definition.side_effects
    if any(effect not in _allowed_side_effects() for effect in effects):
        raise CapabilityRegistryError("capability declares an unsupported side effect")
    permission_scope_kind = _validate_token(
        "permission scope kind", definition.permission_scope_kind, 80, registry=True
    )
    if "process_execution" in effects and definition.risk_tier is not CapabilityRiskTier.HIGH_RISK:
        raise CapabilityRegistryError("process execution capabilities must use Tier 3")
    if definition.network_mode not in {"none", "explicit_url"}:
        raise CapabilityRegistryError("invalid capability network mode")
    if definition.binding_mode not in {
        "none",
        "record_identity",
        "project_artifact",
        "destination_host",
    }:
        raise CapabilityRegistryError("invalid capability binding mode")
    _validate_binding_contract(
        definition.binding_mode,
        target=target,
        arguments=tuple(arguments),
        permission_scope_kind=permission_scope_kind,
        network_mode=definition.network_mode,
    )
    if not isinstance(definition.allowed_request_origins, frozenset):
        raise CapabilityRegistryError("capability request origins must be an immutable set")
    origins = definition.allowed_request_origins
    if not origins or any(origin not in _ALLOWED_REQUEST_ORIGINS for origin in origins):
        raise CapabilityRegistryError("capability request origins are invalid")
    if definition.network_mode == "explicit_url":
        if target.kind != "url" or "network_read" not in effects:
            raise CapabilityRegistryError(
                "explicit URL capabilities require a URL target and declared network read"
            )
    elif "network_read" in effects:
        raise CapabilityRegistryError("network side effects require an explicit URL contract")
    if not isinstance(definition.release_available, bool):
        raise CapabilityRegistryError("release availability must be boolean")
    resource_contract = _validate_resource_contract(definition.resource_contract)
    if not isinstance(definition.cancellation_required, bool):
        raise CapabilityRegistryError("cancellation requirement must be boolean")
    description = _validate_description(definition.description)
    return CapabilityDefinition(
        capability_id=capability_id,
        version=version,
        risk_tier=definition.risk_tier,
        arguments=tuple(arguments),
        target=target,
        side_effects=effects,
        permission_scope_kind=permission_scope_kind,
        network_mode=definition.network_mode,
        binding_mode=definition.binding_mode,
        allowed_request_origins=origins,
        release_available=definition.release_available,
        resource_contract=resource_contract,
        cancellation_required=definition.cancellation_required,
        description=description,
    )


def _validate_binding_contract(
    mode: CapabilityBindingMode,
    *,
    target: CapabilityTargetContract,
    arguments: tuple[CapabilityArgument, ...],
    permission_scope_kind: str,
    network_mode: CapabilityNetworkMode,
) -> None:
    fields = {argument.name for argument in arguments}
    if mode == "none":
        if permission_scope_kind != "none":
            raise CapabilityRegistryError("unbound capabilities must use the none scope")
        return
    if mode == "record_identity":
        if (
            target.kind != "state_record"
            or "record_id" not in fields
            or permission_scope_kind != "record"
        ):
            raise CapabilityRegistryError("record binding contract is inconsistent")
        return
    if mode == "project_artifact":
        if (
            target.kind != "managed_artifact"
            or not {"project_id", "name"}.issubset(fields)
            or permission_scope_kind != "project"
        ):
            raise CapabilityRegistryError("project artifact binding contract is inconsistent")
        return
    if (
        target.kind != "url"
        or "url" not in fields
        or permission_scope_kind != "destination"
        or network_mode != "explicit_url"
    ):
        raise CapabilityRegistryError("destination binding contract is inconsistent")


def _validate_argument_definition(argument: CapabilityArgument) -> CapabilityArgument:
    if not isinstance(argument, CapabilityArgument):
        raise CapabilityRegistryError("argument schemas must use CapabilityArgument")
    name = _validate_token("argument name", argument.name, MAX_ARGUMENT_NAME_LENGTH, registry=True)
    if name.lower() in _PROHIBITED_ARGUMENT_NAMES:
        raise CapabilityRegistryError(f"prohibited generic or authority-changing argument: {name}")
    if argument.kind not in {"text", "integer", "boolean", "string_list"}:
        raise CapabilityRegistryError(f"unsupported argument kind: {argument.kind}")
    if not isinstance(argument.required, bool):
        raise CapabilityRegistryError("argument required flag must be boolean")
    maximum_length = _positive_optional(argument.maximum_length, "argument maximum length")
    minimum_integer = _plain_optional_integer(argument.minimum_integer, "argument minimum")
    maximum_integer = _plain_optional_integer(argument.maximum_integer, "argument maximum")
    maximum_items = _positive_optional(argument.maximum_items, "argument maximum items")
    if minimum_integer is not None and maximum_integer is not None:
        if minimum_integer > maximum_integer:
            raise CapabilityRegistryError("argument integer range is inverted")
    if argument.kind == "text" and maximum_length is None:
        raise CapabilityRegistryError("text arguments require a maximum length")
    if argument.kind == "string_list" and (maximum_length is None or maximum_items is None):
        raise CapabilityRegistryError("string-list arguments require item and length limits")
    return CapabilityArgument(
        name=name,
        kind=argument.kind,
        required=argument.required,
        maximum_length=maximum_length,
        minimum_integer=minimum_integer,
        maximum_integer=maximum_integer,
        maximum_items=maximum_items,
    )


def _validate_target_contract(
    contract: CapabilityTargetContract,
) -> CapabilityTargetContract:
    if not isinstance(contract, CapabilityTargetContract):
        raise CapabilityRegistryError("target contract must be CapabilityTargetContract")
    if contract.kind not in {
        "provided_data",
        "state_record",
        "managed_artifact",
        "url",
    }:
        raise CapabilityRegistryError("unsupported capability target kind")
    maximum = _positive_integer(contract.maximum_identifier_length, "target identifier limit")
    if maximum > MAX_TARGET_IDENTIFIER_LENGTH:
        raise CapabilityRegistryError("target identifier limit exceeds global maximum")
    return CapabilityTargetContract(contract.kind, maximum)


def _validate_resource_contract(
    contract: CapabilityResourceContract,
) -> CapabilityResourceContract:
    if not isinstance(contract, CapabilityResourceContract):
        raise CapabilityRegistryError("resource contract must be CapabilityResourceContract")
    timeout = _positive_integer(contract.max_timeout_seconds, "maximum timeout")
    if timeout > MAX_TIMEOUT_SECONDS:
        raise CapabilityRegistryError("maximum timeout exceeds the global limit")
    return CapabilityResourceContract(
        max_input_chars=_positive_integer(contract.max_input_chars, "maximum input characters"),
        max_output_bytes=_positive_integer(contract.max_output_bytes, "maximum output bytes"),
        max_items=_positive_integer(contract.max_items, "maximum items"),
        max_timeout_seconds=timeout,
    )


def _validate_request_envelope(request: CapabilityRequest) -> CapabilityRequest:
    if not isinstance(request, CapabilityRequest):
        raise CapabilityRequestValidationError("preflight requires a CapabilityRequest")
    capability_id = _validate_token(
        "capability ID", request.capability_id, MAX_CAPABILITY_ID_LENGTH, registry=False
    )
    version = _validate_version(request.capability_version, registry=False)
    operation_id = _validate_token(
        "operation ID", request.operation_id, MAX_OPERATION_ID_LENGTH, registry=False
    )
    session_id = _validate_optional_token("session ID", request.session_id, MAX_SESSION_ID_LENGTH)
    cancellation_id = _validate_optional_token(
        "cancellation ID", request.cancellation_id, MAX_CANCELLATION_ID_LENGTH
    )
    if request.actor_type not in {
        "system",
        "user",
        "retriever",
        "extractor",
        "importer",
        "tool",
        "runtime",
        "model",
        "unknown",
    }:
        raise CapabilityRequestValidationError("invalid request actor type")
    if request.origin_class not in _ORIGIN_ACTORS:
        raise CapabilityRequestValidationError("invalid request origin class")
    arguments = _safe_mapping(request.arguments, "arguments", MAX_ARGUMENT_JSON_BYTES)
    if not isinstance(request.target, CapabilityTarget):
        raise CapabilityRequestValidationError("request target must be CapabilityTarget")
    if request.target.kind not in {
        "provided_data",
        "state_record",
        "managed_artifact",
        "url",
    }:
        raise CapabilityRequestValidationError("request target kind is invalid")
    target = CapabilityTarget(
        kind=request.target.kind,
        identifier=_validate_text(
            "target identifier", request.target.identifier, MAX_TARGET_IDENTIFIER_LENGTH
        ),
    )
    destination = (
        None
        if request.destination is None
        else _validate_text("destination", request.destination, MAX_TARGET_IDENTIFIER_LENGTH)
    )
    if not isinstance(request.declared_side_effects, frozenset):
        raise CapabilityRequestValidationError("declared side effects must be an immutable set")
    effects = request.declared_side_effects
    if any(effect not in _allowed_side_effects() for effect in effects):
        raise CapabilityRequestValidationError("request contains an unsupported side effect")
    if isinstance(request.declared_risk_tier, bool) or not isinstance(
        request.declared_risk_tier, int
    ):
        raise CapabilityRequestValidationError("declared risk tier must be an integer")
    if request.declared_risk_tier not in {0, 1, 2, 3}:
        raise CapabilityRequestValidationError("declared risk tier is outside 0 through 3")
    permission_scope = _safe_mapping(
        request.permission_scope, "permission scope", MAX_PERMISSION_SCOPE_BYTES
    )
    limits = _validate_request_limits(request.resource_limits)
    timeout = _positive_integer(request.timeout_seconds, "request timeout", request=True)
    if timeout > MAX_TIMEOUT_SECONDS:
        raise CapabilityRequestValidationError("request timeout exceeds the global limit")
    return CapabilityRequest(
        capability_id=capability_id,
        capability_version=version,
        operation_id=operation_id,
        actor_type=request.actor_type,
        origin_class=request.origin_class,
        arguments=MappingProxyType(arguments),
        target=target,
        destination=destination,
        declared_side_effects=effects,
        declared_risk_tier=request.declared_risk_tier,
        permission_scope=MappingProxyType(permission_scope),
        resource_limits=limits,
        timeout_seconds=timeout,
        session_id=session_id,
        cancellation_id=cancellation_id,
    )


def _arguments_match(definition: CapabilityDefinition, arguments: Mapping[str, object]) -> bool:
    schema = {field.name: field for field in definition.arguments}
    if set(arguments) - set(schema):
        return False
    if any(field.required and field.name not in arguments for field in definition.arguments):
        return False
    return all(
        field.name not in arguments or _argument_value_matches(field, arguments[field.name])
        for field in definition.arguments
    )


def _argument_value_matches(field: CapabilityArgument, value: object) -> bool:
    if field.kind == "text":
        return (
            isinstance(value, str)
            and bool(value.strip())
            and field.maximum_length is not None
            and len(value) <= field.maximum_length
            and not _contains_control(value)
        )
    if field.kind == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            return False
        if field.minimum_integer is not None and value < field.minimum_integer:
            return False
        return field.maximum_integer is None or value <= field.maximum_integer
    if field.kind == "boolean":
        return isinstance(value, bool)
    if field.kind == "string_list":
        if not isinstance(value, list) or field.maximum_items is None:
            return False
        if len(value) > field.maximum_items or field.maximum_length is None:
            return False
        return all(
            isinstance(item, str)
            and bool(item.strip())
            and len(item) <= field.maximum_length
            and not _contains_control(item)
            for item in value
        )
    return False


def _target_matches(contract: CapabilityTargetContract, target: CapabilityTarget) -> bool:
    if target.kind != contract.kind or len(target.identifier) > contract.maximum_identifier_length:
        return False
    if contract.kind == "provided_data":
        return bool(_TOKEN_PATTERN.fullmatch(target.identifier))
    if contract.kind == "state_record":
        return bool(_TOKEN_PATTERN.fullmatch(target.identifier))
    if contract.kind == "managed_artifact":
        return _safe_relative_artifact(target.identifier)
    if contract.kind == "url":
        return _normalize_url(target.identifier) is not None
    return False


def _destination_for(
    definition: CapabilityDefinition, request: CapabilityRequest
) -> str | None | object:
    if definition.network_mode == "none":
        return None if request.destination is None else _DESTINATION_MISMATCH
    if request.destination is None:
        return _DESTINATION_MISMATCH
    normalized_target = _normalize_url(request.target.identifier)
    normalized_destination = _normalize_url(request.destination)
    argument_url = request.arguments.get("url")
    normalized_argument = _normalize_url(argument_url) if isinstance(argument_url, str) else None
    if (
        normalized_target is None
        or normalized_destination is None
        or normalized_argument is None
        or len({normalized_target, normalized_destination, normalized_argument}) != 1
    ):
        return _DESTINATION_MISMATCH
    return normalized_destination


def _bindings_match(
    definition: CapabilityDefinition,
    request: CapabilityRequest,
    destination: str | None,
    scope: dict[str, object],
) -> bool:
    mode = definition.binding_mode
    if mode == "none":
        return scope == {"kind": "none"}
    if mode == "record_identity":
        record_id = request.arguments.get("record_id")
        return (
            isinstance(record_id, str)
            and request.target.identifier == record_id
            and scope == {"kind": "record", "record_id": record_id}
        )
    if mode == "project_artifact":
        project_id = request.arguments.get("project_id")
        name = request.arguments.get("name")
        if (
            not isinstance(project_id, str)
            or not _TOKEN_PATTERN.fullmatch(project_id)
            or not isinstance(name, str)
            or not _TOKEN_PATTERN.fullmatch(name)
        ):
            return False
        return request.target.identifier == f"{project_id}/{name}" and scope == {
            "kind": "project",
            "project_id": project_id,
        }
    if destination is None:
        return False
    host = urlsplit(destination).hostname
    scope_host = scope.get("host")
    if host is None or not isinstance(scope_host, str):
        return False
    normalized_scope_host = _normalize_host(scope_host)
    return normalized_scope_host == host and scope == {
        "kind": "destination",
        "host": scope_host,
    }


def _declared_limits_cover_request(request: CapabilityRequest) -> bool:
    input_characters, list_items = _request_input_usage(request)
    return (
        input_characters <= request.resource_limits.max_input_chars
        and max(1, list_items) <= request.resource_limits.max_items
    )


def _request_input_usage(request: CapabilityRequest) -> tuple[int, int]:
    characters, items = _json_input_usage(request.arguments)
    characters += len(request.target.identifier)
    if request.destination is not None:
        characters += len(request.destination)
    return characters, items


def _json_input_usage(value: object) -> tuple[int, int]:
    if isinstance(value, Mapping):
        characters = 0
        items = 0
        for key, nested in value.items():
            nested_characters, nested_items = _json_input_usage(nested)
            characters += len(key) + nested_characters
            items += nested_items
        return characters, items
    if isinstance(value, list):
        characters = 0
        items = len(value)
        for nested in value:
            nested_characters, nested_items = _json_input_usage(nested)
            characters += nested_characters
            items += nested_items
        return characters, items
    if isinstance(value, str):
        return len(value), 0
    if value is None:
        return 0, 0
    return len(str(value)), 0


def _resource_limits_match(
    contract: CapabilityResourceContract, limits: CapabilityResourceLimits
) -> bool:
    return (
        0 < limits.max_input_chars <= contract.max_input_chars
        and 0 < limits.max_output_bytes <= contract.max_output_bytes
        and 0 < limits.max_items <= contract.max_items
    )


def _timeout_matches(contract: CapabilityResourceContract, timeout_seconds: int) -> bool:
    return 0 < timeout_seconds <= contract.max_timeout_seconds


def _cancellation_matches(definition: CapabilityDefinition, cancellation_id: str | None) -> bool:
    if definition.cancellation_required:
        return cancellation_id is not None
    return cancellation_id is None


def _permission_scope(scope: Mapping[str, object]) -> dict[str, object] | None:
    kind = scope.get("kind")
    if not isinstance(kind, str) or not _TOKEN_PATTERN.fullmatch(kind):
        return None
    return dict(scope)


def _actor_matches_origin(
    actor_type: InstructionActorType, origin_class: InstructionOriginClass
) -> bool:
    return actor_type in _ORIGIN_ACTORS[origin_class]


def _network_allowed(policy: OutboundNetworkPolicy, destination: str) -> bool:
    if not policy.enabled:
        return False
    parsed = urlsplit(destination)
    if parsed.scheme not in policy.allowed_schemes:
        return False
    host = parsed.hostname
    if host is None or _is_private_or_local_host(host):
        return False
    if not policy.allowed_hosts:
        return True
    if host in policy.allowed_hosts:
        return True
    return policy.allow_subdomains and any(
        host.endswith(f".{allowed}") for allowed in policy.allowed_hosts
    )


def _normalize_url(value: str) -> str | None:
    if not isinstance(value, str) or len(value) > MAX_TARGET_IDENTIFIER_LENGTH:
        return None
    try:
        parsed = urlsplit(value.strip())
        port = parsed.port
    except ValueError:
        return None
    if parsed.scheme.lower() not in {"http", "https"}:
        return None
    if parsed.username is not None or parsed.password is not None or parsed.fragment:
        return None
    host = parsed.hostname
    if host is None:
        return None
    normalized_host = _normalize_host(host)
    if normalized_host is None:
        return None
    scheme = parsed.scheme.lower()
    default_port = 443 if scheme == "https" else 80
    if port is not None and port != default_port:
        return None
    host_for_netloc = normalized_host
    try:
        if ipaddress.ip_address(normalized_host).version == 6:
            host_for_netloc = f"[{normalized_host}]"
    except ValueError:
        pass
    netloc = host_for_netloc
    path = parsed.path or "/"
    normalized = SplitResult(scheme, netloc, path, parsed.query, "")
    return urlunsplit(normalized)


def _normalize_host(host: str) -> str | None:
    normalized = host.rstrip(".").lower()
    if not normalized or len(normalized) > 253:
        return None
    try:
        ipaddress.ip_address(normalized)
    except ValueError:
        try:
            normalized = normalized.encode("idna").decode("ascii")
        except UnicodeError:
            return None
        if any(not _HOST_LABEL_PATTERN.fullmatch(label) for label in normalized.split(".")):
            return None
    return normalized


def _is_private_or_local_host(host: str) -> bool:
    normalized = host.rstrip(".").lower()
    if normalized == "localhost" or normalized.endswith((".localhost", ".local")):
        return True
    try:
        address = ipaddress.ip_address(normalized)
    except ValueError:
        return False
    return any(
        (
            address.is_private,
            address.is_loopback,
            address.is_link_local,
            address.is_multicast,
            address.is_reserved,
            address.is_unspecified,
        )
    )


def _safe_relative_artifact(value: str) -> bool:
    if (
        not value
        or value.startswith(("/", "\\"))
        or "\\" in value
        or _contains_control(value)
        or re.match(r"^[A-Za-z]:", value)
    ):
        return False
    raw_parts = value.split("/")
    if any(part in {"", ".", ".."} for part in raw_parts):
        return False
    path = PurePosixPath(value)
    return not path.is_absolute()


def _registry_fingerprint(definitions: tuple[CapabilityDefinition, ...]) -> str:
    payload = {
        "schema_version": REGISTRY_SCHEMA_VERSION,
        "definitions": [_definition_payload(definition) for definition in definitions],
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _definition_payload(definition: CapabilityDefinition) -> dict[str, object]:
    return {
        "capability_id": definition.capability_id,
        "version": definition.version,
        "risk_tier": int(definition.risk_tier),
        "arguments": [
            {
                "name": field.name,
                "kind": field.kind,
                "required": field.required,
                "maximum_length": field.maximum_length,
                "minimum_integer": field.minimum_integer,
                "maximum_integer": field.maximum_integer,
                "maximum_items": field.maximum_items,
            }
            for field in definition.arguments
        ],
        "target": {
            "kind": definition.target.kind,
            "maximum_identifier_length": definition.target.maximum_identifier_length,
        },
        "side_effects": sorted(definition.side_effects),
        "permission_scope_kind": definition.permission_scope_kind,
        "network_mode": definition.network_mode,
        "binding_mode": definition.binding_mode,
        "allowed_request_origins": sorted(definition.allowed_request_origins),
        "release_available": definition.release_available,
        "resource_contract": {
            "max_input_chars": definition.resource_contract.max_input_chars,
            "max_output_bytes": definition.resource_contract.max_output_bytes,
            "max_items": definition.resource_contract.max_items,
            "max_timeout_seconds": definition.resource_contract.max_timeout_seconds,
        },
        "cancellation_required": definition.cancellation_required,
        "description": definition.description,
    }


def _safe_mapping(value: Mapping[str, object], name: str, maximum_bytes: int) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise CapabilityRequestValidationError(f"{name} must be a mapping")
    copied: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key or len(key) > MAX_ARGUMENT_NAME_LENGTH:
            raise CapabilityRequestValidationError(f"{name} contains an invalid key")
        if _contains_control(key):
            raise CapabilityRequestValidationError(f"{name} contains a control character")
        copied[key] = _validate_json_value(item, name=name, depth=0)
    try:
        encoded = json.dumps(
            copied,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CapabilityRequestValidationError(f"{name} is not JSON-compatible") from exc
    if len(encoded) > maximum_bytes:
        raise CapabilityRequestValidationError(f"{name} exceeds {maximum_bytes} bytes")
    return cast(dict[str, object], json.loads(encoded.decode("utf-8")))


def _validate_json_value(value: object, *, name: str, depth: int) -> object:
    if depth > 8:
        raise CapabilityRequestValidationError(f"{name} nesting is too deep")
    if isinstance(value, dict):
        copied: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str) or not key or _contains_control(key):
                raise CapabilityRequestValidationError(f"{name} contains an invalid JSON key")
            copied[key] = _validate_json_value(item, name=name, depth=depth + 1)
        return copied
    if isinstance(value, list):
        return [_validate_json_value(item, name=name, depth=depth + 1) for item in value]
    if isinstance(value, str):
        if len(value) > MAX_ARGUMENT_TEXT_LENGTH or _contains_control(value):
            raise CapabilityRequestValidationError(f"{name} contains invalid text")
        return value
    if value is None or isinstance(value, (bool, int, float)):
        return value
    raise CapabilityRequestValidationError(f"{name} is not JSON-compatible")


def _validate_request_limits(
    limits: CapabilityResourceLimits,
) -> CapabilityResourceLimits:
    if not isinstance(limits, CapabilityResourceLimits):
        raise CapabilityRequestValidationError("resource limits must be CapabilityResourceLimits")
    return CapabilityResourceLimits(
        max_input_chars=_positive_integer(
            limits.max_input_chars, "maximum input characters", request=True
        ),
        max_output_bytes=_positive_integer(
            limits.max_output_bytes, "maximum output bytes", request=True
        ),
        max_items=_positive_integer(limits.max_items, "maximum items", request=True),
    )


def _validate_token(name: str, value: str, maximum: int, *, registry: bool) -> str:
    error_type = CapabilityRegistryError if registry else CapabilityRequestValidationError
    if not isinstance(value, str):
        raise error_type(f"{name} must be text")
    normalized = value.strip()
    if not normalized or len(normalized) > maximum or not _TOKEN_PATTERN.fullmatch(normalized):
        raise error_type(f"{name} is invalid")
    return normalized


def _validate_optional_token(name: str, value: str | None, maximum: int) -> str | None:
    if value is None:
        return None
    return _validate_token(name, value, maximum, registry=False)


def _validate_version(value: str, *, registry: bool = True) -> str:
    error_type = CapabilityRegistryError if registry else CapabilityRequestValidationError
    if not isinstance(value, str):
        raise error_type("capability version must be text")
    normalized = value.strip()
    if len(normalized) > MAX_VERSION_LENGTH or not _VERSION_PATTERN.fullmatch(normalized):
        raise error_type("capability version is invalid")
    return normalized


def _validate_text(name: str, value: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise CapabilityRequestValidationError(f"{name} must be text")
    normalized = value.strip()
    if not normalized or len(normalized) > maximum or _contains_control(normalized):
        raise CapabilityRequestValidationError(f"{name} is invalid")
    return normalized


def _validate_description(value: str) -> str:
    if not isinstance(value, str):
        raise CapabilityRegistryError("capability description must be text")
    normalized = " ".join(value.split())
    if not normalized or len(normalized) > 500 or _contains_control(normalized):
        raise CapabilityRegistryError("capability description is invalid")
    return normalized


def _validate_scheme(value: str) -> str:
    if not isinstance(value, str):
        raise CapabilityRequestValidationError("network policy scheme must be text")
    normalized = value.strip().lower()
    if normalized not in {"http", "https"}:
        raise CapabilityRequestValidationError("network policy scheme is unsupported")
    return normalized


def _validate_policy_host(value: str) -> str:
    if not isinstance(value, str):
        raise CapabilityRequestValidationError("network policy host must be text")
    normalized = _normalize_host(value)
    if normalized is None or _is_private_or_local_host(normalized):
        raise CapabilityRequestValidationError("network policy host is invalid")
    return normalized


def _positive_integer(value: int, name: str, *, request: bool = False) -> int:
    error_type = CapabilityRequestValidationError if request else CapabilityRegistryError
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise error_type(f"{name} must be a positive integer")
    return value


def _positive_optional(value: int | None, name: str) -> int | None:
    if value is None:
        return None
    return _positive_integer(value, name)


def _plain_optional_integer(value: int | None, name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise CapabilityRegistryError(f"{name} must be an integer")
    return value


def _contains_control(value: str) -> bool:
    return any(ord(character) < 32 for character in value)


def _allowed_side_effects() -> frozenset[str]:
    return frozenset({"read_state", "create_managed_artifact", "network_read", "process_execution"})


def _audit_actor(actor_type: InstructionActorType) -> AuditActorType:
    if actor_type in {"user", "system", "model", "runtime"}:
        return cast(AuditActorType, actor_type)
    return "capability"
