"""Model-independent portability adapter contracts and source environments."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, cast
from uuid import UUID

from doll.state import (
    RecordProvenance,
    RecordSensitivity,
    RecordValidationError,
    StateCorruptError,
)
from doll.state_repository import StateRepository

AttachmentBehavior = Literal[
    "preserve_reference",
    "preserve_managed_copy",
    "metadata_only",
    "unsupported",
]
BranchBehavior = Literal["preserve", "linearize_with_loss", "unsupported"]
NetworkBehavior = Literal["none", "declared_read_only", "declared_read_write"]

_SOURCE_ENVIRONMENT_RECORD_TYPE = "source_environment"
_SOURCE_ENVIRONMENT_SCHEMA_VERSION = 1
_IDENTIFIER_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_VERSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+\-]{0,127}$")
_ALLOWED_ATTACHMENT_BEHAVIORS = frozenset(
    {
        "preserve_reference",
        "preserve_managed_copy",
        "metadata_only",
        "unsupported",
    }
)
_ALLOWED_BRANCH_BEHAVIORS = frozenset({"preserve", "linearize_with_loss", "unsupported"})
_ALLOWED_NETWORK_BEHAVIORS = frozenset({"none", "declared_read_only", "declared_read_write"})
_SOURCE_ENVIRONMENT_KEYS = frozenset(
    {
        "environment_class",
        "provider_id",
        "application_id",
        "interface_id",
        "runtime_id",
        "export_format",
        "export_version",
        "observed_at",
    }
)
_MAX_TEXT_LENGTH = 1024
_MAX_DECLARATIONS = 256
_MAX_RESOURCE_LIMIT = 2**63 - 1
_MAX_LIST_LIMIT = 500


class PortabilityContractError(RecordValidationError):
    """Raised when a portability declaration is invalid."""


class PortabilityStateCorruptError(StateCorruptError):
    """Raised when persisted portability state is malformed."""


@dataclass(frozen=True, slots=True)
class AdapterResourceLimits:
    """Declared parser/exporter limits; the contract itself performs no I/O."""

    max_input_bytes: int
    max_object_count: int
    max_attachment_bytes: int
    max_nesting_depth: int

    def __post_init__(self) -> None:
        for field_name in (
            "max_input_bytes",
            "max_object_count",
            "max_attachment_bytes",
            "max_nesting_depth",
        ):
            value = getattr(self, field_name)
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or not 1 <= value <= _MAX_RESOURCE_LIMIT
            ):
                raise PortabilityContractError(
                    f"{field_name.replace('_', ' ')} must be a positive bounded integer"
                )

    def canonical_payload(self) -> dict[str, int]:
        return {
            "max_input_bytes": self.max_input_bytes,
            "max_object_count": self.max_object_count,
            "max_attachment_bytes": self.max_attachment_bytes,
            "max_nesting_depth": self.max_nesting_depth,
        }


@dataclass(frozen=True, slots=True)
class SourceAdapterContract:
    """Declarative contract for a parser that never executes source content."""

    adapter_id: str
    adapter_version: str
    source_environment_class: str
    supported_source_versions: tuple[str, ...]
    supported_event_types: tuple[str, ...]
    attachment_behavior: AttachmentBehavior
    branch_behavior: BranchBehavior
    resource_limits: AdapterResourceLimits
    network_behavior: NetworkBehavior
    loss_categories: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "adapter_id", _validate_identifier("adapter id", self.adapter_id))
        object.__setattr__(
            self,
            "adapter_version",
            _validate_version("adapter version", self.adapter_version),
        )
        object.__setattr__(
            self,
            "source_environment_class",
            _validate_identifier(
                "source environment class",
                self.source_environment_class,
            ),
        )
        object.__setattr__(
            self,
            "supported_source_versions",
            _validate_declarations(
                "supported source versions",
                self.supported_source_versions,
                version_values=True,
                require_nonempty=True,
            ),
        )
        object.__setattr__(
            self,
            "supported_event_types",
            _validate_declarations(
                "supported event types",
                self.supported_event_types,
                require_nonempty=True,
            ),
        )
        _validate_behaviors(
            self.attachment_behavior,
            self.branch_behavior,
            self.network_behavior,
        )
        object.__setattr__(
            self,
            "loss_categories",
            _validate_declarations("loss categories", self.loss_categories),
        )

    def canonical_payload(self) -> dict[str, object]:
        return {
            "contract_kind": "source",
            "adapter_id": self.adapter_id,
            "adapter_version": self.adapter_version,
            "source_environment_class": self.source_environment_class,
            "supported_source_versions": list(self.supported_source_versions),
            "supported_event_types": list(self.supported_event_types),
            "attachment_behavior": self.attachment_behavior,
            "branch_behavior": self.branch_behavior,
            "resource_limits": self.resource_limits.canonical_payload(),
            "network_behavior": self.network_behavior,
            "loss_categories": list(self.loss_categories),
        }

    @property
    def fingerprint(self) -> str:
        return _fingerprint(self.canonical_payload())


@dataclass(frozen=True, slots=True)
class TargetAdapterContract:
    """Declarative contract for a target-specific exporter."""

    adapter_id: str
    adapter_version: str
    target_environment_class: str
    supported_target_versions: tuple[str, ...]
    supported_record_types: tuple[str, ...]
    attachment_behavior: AttachmentBehavior
    branch_behavior: BranchBehavior
    resource_limits: AdapterResourceLimits
    network_behavior: NetworkBehavior
    loss_categories: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "adapter_id", _validate_identifier("adapter id", self.adapter_id))
        object.__setattr__(
            self,
            "adapter_version",
            _validate_version("adapter version", self.adapter_version),
        )
        object.__setattr__(
            self,
            "target_environment_class",
            _validate_identifier(
                "target environment class",
                self.target_environment_class,
            ),
        )
        object.__setattr__(
            self,
            "supported_target_versions",
            _validate_declarations(
                "supported target versions",
                self.supported_target_versions,
                version_values=True,
                require_nonempty=True,
            ),
        )
        object.__setattr__(
            self,
            "supported_record_types",
            _validate_declarations(
                "supported record types",
                self.supported_record_types,
                require_nonempty=True,
            ),
        )
        _validate_behaviors(
            self.attachment_behavior,
            self.branch_behavior,
            self.network_behavior,
        )
        object.__setattr__(
            self,
            "loss_categories",
            _validate_declarations("loss categories", self.loss_categories),
        )

    def canonical_payload(self) -> dict[str, object]:
        return {
            "contract_kind": "target",
            "adapter_id": self.adapter_id,
            "adapter_version": self.adapter_version,
            "target_environment_class": self.target_environment_class,
            "supported_target_versions": list(self.supported_target_versions),
            "supported_record_types": list(self.supported_record_types),
            "attachment_behavior": self.attachment_behavior,
            "branch_behavior": self.branch_behavior,
            "resource_limits": self.resource_limits.canonical_payload(),
            "network_behavior": self.network_behavior,
            "loss_categories": list(self.loss_categories),
        }

    @property
    def fingerprint(self) -> str:
        return _fingerprint(self.canonical_payload())


@dataclass(frozen=True, slots=True)
class SourceEnvironmentRecord:
    """Canonical identity for an imported or inspected AI environment."""

    environment_id: str
    environment_class: str
    provider_id: str | None = None
    application_id: str | None = None
    interface_id: str | None = None
    runtime_id: str | None = None
    export_format: str | None = None
    export_version: str | None = None
    observed_at: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "environment_id",
            _validate_uuid("environment id", self.environment_id),
        )
        object.__setattr__(
            self,
            "environment_class",
            _validate_identifier("environment class", self.environment_class),
        )
        for field_name in (
            "provider_id",
            "application_id",
            "interface_id",
            "runtime_id",
            "export_format",
        ):
            value = getattr(self, field_name)
            object.__setattr__(
                self,
                field_name,
                _validate_optional_identifier(field_name.replace("_", " "), value),
            )
        object.__setattr__(
            self,
            "export_version",
            _validate_optional_version("export version", self.export_version),
        )
        object.__setattr__(
            self,
            "observed_at",
            _validate_optional_timestamp("observed at", self.observed_at),
        )

    def canonical_metadata(self) -> dict[str, object]:
        return {
            "environment_class": self.environment_class,
            "provider_id": self.provider_id,
            "application_id": self.application_id,
            "interface_id": self.interface_id,
            "runtime_id": self.runtime_id,
            "export_format": self.export_format,
            "export_version": self.export_version,
            "observed_at": self.observed_at,
        }


@dataclass(slots=True)
class PortabilityState:
    """Persist canonical source-environment records through Doll State."""

    repository: StateRepository

    def save_source_environment(
        self,
        record: SourceEnvironmentRecord,
        *,
        provenance: RecordProvenance = "imported",
        sensitivity: RecordSensitivity = "personal",
    ) -> SourceEnvironmentRecord:
        self.repository.create_record(
            record_id=record.environment_id,
            record_type=_SOURCE_ENVIRONMENT_RECORD_TYPE,
            schema_version=_SOURCE_ENVIRONMENT_SCHEMA_VERSION,
            provenance=provenance,
            sensitivity=sensitivity,
            metadata=record.canonical_metadata(),
        )
        return self.get_source_environment(record.environment_id)

    def get_source_environment(self, environment_id: str) -> SourceEnvironmentRecord:
        envelope = self.repository.get_record(_validate_uuid("environment id", environment_id))
        if (
            envelope.record_type != _SOURCE_ENVIRONMENT_RECORD_TYPE
            or envelope.schema_version != _SOURCE_ENVIRONMENT_SCHEMA_VERSION
        ):
            raise PortabilityStateCorruptError("record is not a supported source environment")
        if frozenset(envelope.metadata) != _SOURCE_ENVIRONMENT_KEYS:
            raise PortabilityStateCorruptError("source environment metadata shape is invalid")
        try:
            return SourceEnvironmentRecord(
                environment_id=envelope.id,
                environment_class=cast(str, envelope.metadata["environment_class"]),
                provider_id=cast(str | None, envelope.metadata["provider_id"]),
                application_id=cast(str | None, envelope.metadata["application_id"]),
                interface_id=cast(str | None, envelope.metadata["interface_id"]),
                runtime_id=cast(str | None, envelope.metadata["runtime_id"]),
                export_format=cast(str | None, envelope.metadata["export_format"]),
                export_version=cast(str | None, envelope.metadata["export_version"]),
                observed_at=cast(str | None, envelope.metadata["observed_at"]),
            )
        except PortabilityContractError as exc:
            raise PortabilityStateCorruptError("source environment metadata is invalid") from exc

    def list_source_environments(
        self,
        *,
        limit: int = 100,
    ) -> tuple[SourceEnvironmentRecord, ...]:
        _validate_list_limit(limit)
        rows = self.repository.connection.execute(
            """
            SELECT id
            FROM records
            WHERE record_type = ?
            ORDER BY created_at ASC, id ASC
            LIMIT ?
            """,
            (_SOURCE_ENVIRONMENT_RECORD_TYPE, limit),
        ).fetchall()
        return tuple(self.get_source_environment(cast(str, row[0])) for row in rows)


def _validate_behaviors(
    attachment_behavior: object,
    branch_behavior: object,
    network_behavior: object,
) -> None:
    if attachment_behavior not in _ALLOWED_ATTACHMENT_BEHAVIORS:
        raise PortabilityContractError("attachment behavior is invalid")
    if branch_behavior not in _ALLOWED_BRANCH_BEHAVIORS:
        raise PortabilityContractError("branch behavior is invalid")
    if network_behavior not in _ALLOWED_NETWORK_BEHAVIORS:
        raise PortabilityContractError("network behavior is invalid or undeclared")


def _validate_uuid(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise PortabilityContractError(f"{name} must be text")
    try:
        canonical = str(UUID(value))
    except (ValueError, AttributeError) as exc:
        raise PortabilityContractError(f"{name} is invalid") from exc
    if canonical != value:
        raise PortabilityContractError(f"{name} must use canonical UUID text")
    return canonical


def _validate_identifier(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise PortabilityContractError(f"{name} must be text")
    normalized = value.strip().lower()
    if not _IDENTIFIER_PATTERN.fullmatch(normalized):
        raise PortabilityContractError(f"{name} is invalid")
    return normalized


def _validate_optional_identifier(name: str, value: object) -> str | None:
    return None if value is None else _validate_identifier(name, value)


def _validate_version(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise PortabilityContractError(f"{name} must be text")
    normalized = value.strip()
    if not _VERSION_PATTERN.fullmatch(normalized):
        raise PortabilityContractError(f"{name} is invalid")
    return normalized


def _validate_optional_version(name: str, value: object) -> str | None:
    return None if value is None else _validate_version(name, value)


def _validate_declarations(
    name: str,
    value: object,
    *,
    version_values: bool = False,
    require_nonempty: bool = False,
) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise PortabilityContractError(f"{name} must be a tuple")
    if require_nonempty and not value:
        raise PortabilityContractError(f"{name} must not be empty")
    if len(value) > _MAX_DECLARATIONS:
        raise PortabilityContractError(f"{name} has too many values")
    validator = _validate_version if version_values else _validate_identifier
    normalized = tuple(validator(name, item) for item in value)
    if len(normalized) != len(set(normalized)):
        raise PortabilityContractError(f"{name} contains duplicates")
    return tuple(sorted(normalized))


def _validate_optional_timestamp(name: str, value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise PortabilityContractError(f"{name} must be text")
    normalized = value.strip()
    if not normalized or len(normalized) > _MAX_TEXT_LENGTH:
        raise PortabilityContractError(f"{name} is invalid")
    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PortabilityContractError(f"{name} is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise PortabilityContractError(f"{name} must be timezone-aware")
    return normalized


def _validate_list_limit(value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= _MAX_LIST_LIMIT:
        raise PortabilityContractError("list limit is invalid")


def _fingerprint(payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


__all__ = [
    "AdapterResourceLimits",
    "AttachmentBehavior",
    "BranchBehavior",
    "NetworkBehavior",
    "PortabilityContractError",
    "PortabilityState",
    "PortabilityStateCorruptError",
    "SourceAdapterContract",
    "SourceEnvironmentRecord",
    "TargetAdapterContract",
]
