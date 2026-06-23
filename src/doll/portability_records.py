"""Canonical portability batch, mapping, loss, and export contracts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

from doll.portability import PortabilityContractError

ImportBatchStatus = Literal[
    "staged",
    "awaiting_review",
    "published",
    "partially_published",
    "rejected",
    "failed",
    "rolled_back",
]
MappingDirection = Literal["import", "export"]
LossSeverity = Literal["informational", "minor", "material", "critical"]
PreservationState = Literal[
    "preserved_original",
    "preserved_reference",
    "preserved_metadata",
    "quarantined",
    "omitted",
    "unknown",
]
FutureRecoverability = Literal[
    "recoverable",
    "partially_recoverable",
    "not_recoverable",
    "unknown",
]
ExportBatchStatus = Literal[
    "planned",
    "running",
    "completed",
    "completed_with_loss",
    "partially_completed",
    "denied",
    "incompatible",
    "failed",
    "cancelled",
]

_IDENTIFIER_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_VERSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+\-]{0,127}$")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_MAX_COUNT = 2**63 - 1
_MAX_DECLARATIONS = 256
_MAX_TEXT_LENGTH = 4096

_IMPORT_STATUSES = frozenset(
    {
        "staged",
        "awaiting_review",
        "published",
        "partially_published",
        "rejected",
        "failed",
        "rolled_back",
    }
)
_TERMINAL_IMPORT_STATUSES = frozenset(
    {"published", "partially_published", "rejected", "failed", "rolled_back"}
)
_MAPPING_DIRECTIONS = frozenset({"import", "export"})
_LOSS_SEVERITIES = frozenset({"informational", "minor", "material", "critical"})
_MATERIAL_LOSS_SEVERITIES = frozenset({"material", "critical"})
_PRESERVATION_STATES = frozenset(
    {
        "preserved_original",
        "preserved_reference",
        "preserved_metadata",
        "quarantined",
        "omitted",
        "unknown",
    }
)
_FUTURE_RECOVERABILITY = frozenset(
    {"recoverable", "partially_recoverable", "not_recoverable", "unknown"}
)
_EXPORT_STATUSES = frozenset(
    {
        "planned",
        "running",
        "completed",
        "completed_with_loss",
        "partially_completed",
        "denied",
        "incompatible",
        "failed",
        "cancelled",
    }
)
_TERMINAL_EXPORT_STATUSES = frozenset(
    {
        "completed",
        "completed_with_loss",
        "partially_completed",
        "denied",
        "incompatible",
        "failed",
        "cancelled",
    }
)
_MANIFEST_EXPORT_STATUSES = frozenset(
    {"completed", "completed_with_loss", "partially_completed"}
)
_FAILURE_EXPORT_STATUSES = frozenset({"denied", "incompatible", "failed", "cancelled"})


@dataclass(frozen=True, slots=True)
class ImportBatchRecord:
    """One provider-independent staged import attempt."""

    import_batch_id: str
    source_environment_id: str
    adapter_id: str
    adapter_version: str
    started_at: str
    status: ImportBatchStatus
    source_root_hash: str
    staged_object_count: int
    published_object_count: int
    quarantined_object_count: int
    completed_at: str | None = None
    mapping_report_id: str | None = None
    loss_report_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "import_batch_id",
            _validate_uuid("import batch id", self.import_batch_id),
        )
        object.__setattr__(
            self,
            "source_environment_id",
            _validate_uuid("source environment id", self.source_environment_id),
        )
        object.__setattr__(
            self,
            "adapter_id",
            _validate_identifier("adapter id", self.adapter_id),
        )
        object.__setattr__(
            self,
            "adapter_version",
            _validate_version("adapter version", self.adapter_version),
        )
        object.__setattr__(
            self,
            "started_at",
            _validate_timestamp("started at", self.started_at),
        )
        object.__setattr__(
            self,
            "completed_at",
            _validate_optional_timestamp("completed at", self.completed_at),
        )
        if self.status not in _IMPORT_STATUSES:
            raise PortabilityContractError("import status is invalid")
        object.__setattr__(
            self,
            "source_root_hash",
            _validate_sha256("source root hash", self.source_root_hash),
        )
        for field_name in (
            "staged_object_count",
            "published_object_count",
            "quarantined_object_count",
        ):
            _validate_count(field_name.replace("_", " "), getattr(self, field_name))
        object.__setattr__(
            self,
            "mapping_report_id",
            _validate_optional_uuid("mapping report id", self.mapping_report_id),
        )
        object.__setattr__(
            self,
            "loss_report_id",
            _validate_optional_uuid("loss report id", self.loss_report_id),
        )
        _validate_time_window(self.started_at, self.completed_at)
        self._validate_status_invariants()

    def _validate_status_invariants(self) -> None:
        terminal = self.status in _TERMINAL_IMPORT_STATUSES
        if terminal != (self.completed_at is not None):
            raise PortabilityContractError(
                "import completion timestamp does not match status"
            )
        if (
            self.published_object_count + self.quarantined_object_count
            > self.staged_object_count
        ):
            raise PortabilityContractError(
                "import object counts exceed staged object count"
            )
        if self.status in {
            "staged",
            "awaiting_review",
            "rejected",
            "failed",
            "rolled_back",
        }:
            if self.published_object_count != 0:
                raise PortabilityContractError(
                    "import status cannot retain published objects"
                )
        elif self.status == "published":
            if (
                self.published_object_count != self.staged_object_count
                or self.quarantined_object_count != 0
            ):
                raise PortabilityContractError(
                    "published import counts are inconsistent"
                )
        elif self.status == "partially_published":
            if not 0 < self.published_object_count < self.staged_object_count:
                raise PortabilityContractError(
                    "partially published import counts are inconsistent"
                )

    def canonical_metadata(self) -> dict[str, object]:
        return {
            "source_environment_id": self.source_environment_id,
            "adapter_id": self.adapter_id,
            "adapter_version": self.adapter_version,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "status": self.status,
            "source_root_hash": self.source_root_hash,
            "staged_object_count": self.staged_object_count,
            "published_object_count": self.published_object_count,
            "quarantined_object_count": self.quarantined_object_count,
            "mapping_report_id": self.mapping_report_id,
            "loss_report_id": self.loss_report_id,
        }


@dataclass(frozen=True, slots=True)
class MappingReportRecord:
    """Explicit mapping counts for one import or export batch."""

    mapping_report_id: str
    direction: MappingDirection
    batch_id: str
    generated_at: str
    total_object_count: int
    mapped_without_known_loss_count: int
    mapped_with_transformation_count: int
    partially_mapped_count: int
    unsupported_but_preserved_count: int
    unsupported_and_omitted_count: int
    missing_dependency_count: int
    malformed_or_quarantined_count: int
    unknown_count: int
    material_loss_count: int = 0
    loss_record_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "mapping_report_id",
            _validate_uuid("mapping report id", self.mapping_report_id),
        )
        if self.direction not in _MAPPING_DIRECTIONS:
            raise PortabilityContractError("mapping direction is invalid")
        object.__setattr__(
            self,
            "batch_id",
            _validate_uuid("batch id", self.batch_id),
        )
        object.__setattr__(
            self,
            "generated_at",
            _validate_timestamp("generated at", self.generated_at),
        )
        for field_name in (
            "total_object_count",
            "mapped_without_known_loss_count",
            "mapped_with_transformation_count",
            "partially_mapped_count",
            "unsupported_but_preserved_count",
            "unsupported_and_omitted_count",
            "missing_dependency_count",
            "malformed_or_quarantined_count",
            "unknown_count",
            "material_loss_count",
        ):
            _validate_count(field_name.replace("_", " "), getattr(self, field_name))
        if self.total_object_count != sum(self.mapping_counts.values()):
            raise PortabilityContractError(
                "mapping counts do not match total object count"
            )
        if self.material_loss_count > self.total_object_count:
            raise PortabilityContractError(
                "material loss count exceeds total object count"
            )
        object.__setattr__(
            self,
            "loss_record_ids",
            _validate_uuid_declarations("loss record ids", self.loss_record_ids),
        )
        if self.material_loss_count and not self.loss_record_ids:
            raise PortabilityContractError(
                "material loss requires at least one loss record"
            )

    @property
    def mapping_counts(self) -> dict[str, int]:
        return {
            "mapped_without_known_loss": self.mapped_without_known_loss_count,
            "mapped_with_transformation": self.mapped_with_transformation_count,
            "partially_mapped": self.partially_mapped_count,
            "unsupported_but_preserved": self.unsupported_but_preserved_count,
            "unsupported_and_omitted": self.unsupported_and_omitted_count,
            "missing_dependency": self.missing_dependency_count,
            "malformed_or_quarantined": self.malformed_or_quarantined_count,
            "unknown": self.unknown_count,
        }

    @property
    def full_fidelity_possible(self) -> bool:
        return self.material_loss_count == 0

    def canonical_metadata(self) -> dict[str, object]:
        return {
            "direction": self.direction,
            "batch_id": self.batch_id,
            "generated_at": self.generated_at,
            "total_object_count": self.total_object_count,
            "mapping_counts": self.mapping_counts,
            "material_loss_count": self.material_loss_count,
            "loss_record_ids": list(self.loss_record_ids),
            "full_fidelity_possible": self.full_fidelity_possible,
        }


@dataclass(frozen=True, slots=True)
class PortabilityLossRecord:
    """One explicit portability limitation or loss."""

    loss_record_id: str
    batch_id: str
    category: str
    severity: LossSeverity
    description: str
    preservation_state: PreservationState
    future_recoverability: FutureRecoverability
    recorded_at: str
    source_object_id: str | None = None
    required_user_action: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "loss_record_id",
            _validate_uuid("loss record id", self.loss_record_id),
        )
        object.__setattr__(
            self,
            "batch_id",
            _validate_uuid("batch id", self.batch_id),
        )
        object.__setattr__(
            self,
            "category",
            _validate_identifier("loss category", self.category),
        )
        if self.severity not in _LOSS_SEVERITIES:
            raise PortabilityContractError("loss severity is invalid")
        object.__setattr__(
            self,
            "description",
            _validate_text("loss description", self.description),
        )
        if self.preservation_state not in _PRESERVATION_STATES:
            raise PortabilityContractError("preservation state is invalid")
        if self.future_recoverability not in _FUTURE_RECOVERABILITY:
            raise PortabilityContractError("future recoverability is invalid")
        object.__setattr__(
            self,
            "recorded_at",
            _validate_timestamp("recorded at", self.recorded_at),
        )
        object.__setattr__(
            self,
            "source_object_id",
            _validate_optional_text("source object id", self.source_object_id),
        )
        object.__setattr__(
            self,
            "required_user_action",
            _validate_optional_text(
                "required user action",
                self.required_user_action,
            ),
        )

    @property
    def is_material(self) -> bool:
        return self.severity in _MATERIAL_LOSS_SEVERITIES

    def canonical_metadata(self) -> dict[str, object]:
        return {
            "batch_id": self.batch_id,
            "category": self.category,
            "severity": self.severity,
            "description": self.description,
            "preservation_state": self.preservation_state,
            "future_recoverability": self.future_recoverability,
            "recorded_at": self.recorded_at,
            "source_object_id": self.source_object_id,
            "required_user_action": self.required_user_action,
            "is_material": self.is_material,
        }


@dataclass(frozen=True, slots=True)
class ExportBatchRecord:
    """One provider-independent generic or target-specific export attempt."""

    export_batch_id: str
    target_format: str
    target_adapter_id: str
    target_adapter_version: str
    selected_record_types: tuple[str, ...]
    started_at: str
    status: ExportBatchStatus
    exported_object_count: int
    completed_at: str | None = None
    manifest_hash: str | None = None
    mapping_report_id: str | None = None
    loss_report_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "export_batch_id",
            _validate_uuid("export batch id", self.export_batch_id),
        )
        object.__setattr__(
            self,
            "target_format",
            _validate_identifier("target format", self.target_format),
        )
        object.__setattr__(
            self,
            "target_adapter_id",
            _validate_identifier("target adapter id", self.target_adapter_id),
        )
        object.__setattr__(
            self,
            "target_adapter_version",
            _validate_version(
                "target adapter version",
                self.target_adapter_version,
            ),
        )
        object.__setattr__(
            self,
            "selected_record_types",
            _validate_identifier_declarations(
                "selected record types",
                self.selected_record_types,
                require_nonempty=True,
            ),
        )
        object.__setattr__(
            self,
            "started_at",
            _validate_timestamp("started at", self.started_at),
        )
        object.__setattr__(
            self,
            "completed_at",
            _validate_optional_timestamp("completed at", self.completed_at),
        )
        if self.status not in _EXPORT_STATUSES:
            raise PortabilityContractError("export status is invalid")
        _validate_count("exported object count", self.exported_object_count)
        object.__setattr__(
            self,
            "manifest_hash",
            _validate_optional_sha256("manifest hash", self.manifest_hash),
        )
        object.__setattr__(
            self,
            "mapping_report_id",
            _validate_optional_uuid("mapping report id", self.mapping_report_id),
        )
        object.__setattr__(
            self,
            "loss_report_id",
            _validate_optional_uuid("loss report id", self.loss_report_id),
        )
        _validate_time_window(self.started_at, self.completed_at)
        self._validate_status_invariants()

    def _validate_status_invariants(self) -> None:
        terminal = self.status in _TERMINAL_EXPORT_STATUSES
        if terminal != (self.completed_at is not None):
            raise PortabilityContractError(
                "export completion timestamp does not match status"
            )
        if self.status in _MANIFEST_EXPORT_STATUSES:
            if self.manifest_hash is None:
                raise PortabilityContractError(
                    "completed export requires a manifest hash"
                )
        elif self.manifest_hash is not None:
            raise PortabilityContractError(
                "non-completed export cannot have a manifest hash"
            )
        if (
            self.status in _FAILURE_EXPORT_STATUSES
            and self.exported_object_count != 0
        ):
            raise PortabilityContractError(
                "failed export status cannot retain exported objects"
            )
        if (
            self.status in {"completed_with_loss", "partially_completed"}
            and self.loss_report_id is None
        ):
            raise PortabilityContractError(
                "lossy export status requires a loss report"
            )

    def canonical_metadata(self) -> dict[str, object]:
        return {
            "target_format": self.target_format,
            "target_adapter_id": self.target_adapter_id,
            "target_adapter_version": self.target_adapter_version,
            "selected_record_types": list(self.selected_record_types),
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "status": self.status,
            "exported_object_count": self.exported_object_count,
            "manifest_hash": self.manifest_hash,
            "mapping_report_id": self.mapping_report_id,
            "loss_report_id": self.loss_report_id,
        }


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


def _validate_optional_uuid(name: str, value: object) -> str | None:
    return None if value is None else _validate_uuid(name, value)


def _validate_identifier(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise PortabilityContractError(f"{name} must be text")
    normalized = value.strip().lower()
    if not _IDENTIFIER_PATTERN.fullmatch(normalized):
        raise PortabilityContractError(f"{name} is invalid")
    return normalized


def _validate_version(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise PortabilityContractError(f"{name} must be text")
    normalized = value.strip()
    if not _VERSION_PATTERN.fullmatch(normalized):
        raise PortabilityContractError(f"{name} is invalid")
    return normalized


def _validate_timestamp(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise PortabilityContractError(f"{name} must be text")
    normalized = value.strip()
    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PortabilityContractError(f"{name} is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise PortabilityContractError(f"{name} must be timezone-aware")
    return normalized


def _validate_optional_timestamp(name: str, value: object) -> str | None:
    return None if value is None else _validate_timestamp(name, value)


def _validate_time_window(started_at: str, completed_at: str | None) -> None:
    if completed_at is None:
        return
    started = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
    completed = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
    if completed < started:
        raise PortabilityContractError(
            "completion timestamp precedes start timestamp"
        )


def _validate_sha256(name: str, value: object) -> str:
    if not isinstance(value, str) or not _SHA256_PATTERN.fullmatch(value):
        raise PortabilityContractError(
            f"{name} must be a lowercase SHA-256 digest"
        )
    return value


def _validate_optional_sha256(name: str, value: object) -> str | None:
    return None if value is None else _validate_sha256(name, value)


def _validate_count(name: str, value: object) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 0 <= value <= _MAX_COUNT
    ):
        raise PortabilityContractError(
            f"{name} must be a non-negative bounded integer"
        )
    return value


def _validate_text(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise PortabilityContractError(f"{name} must be text")
    normalized = value.strip()
    if not normalized:
        raise PortabilityContractError(f"{name} must not be blank")
    if len(normalized) > _MAX_TEXT_LENGTH:
        raise PortabilityContractError(f"{name} exceeds the maximum length")
    if any(
        ord(character) < 32 and character not in "\t\n\r"
        for character in normalized
    ):
        raise PortabilityContractError(f"{name} contains a control character")
    return normalized


def _validate_optional_text(name: str, value: object) -> str | None:
    return None if value is None else _validate_text(name, value)


def _validate_identifier_declarations(
    name: str,
    value: object,
    *,
    require_nonempty: bool = False,
) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise PortabilityContractError(f"{name} must be a tuple")
    if require_nonempty and not value:
        raise PortabilityContractError(f"{name} must not be empty")
    if len(value) > _MAX_DECLARATIONS:
        raise PortabilityContractError(f"{name} has too many values")
    normalized = tuple(_validate_identifier(name, item) for item in value)
    if len(normalized) != len(set(normalized)):
        raise PortabilityContractError(f"{name} contains duplicates")
    return tuple(sorted(normalized))


def _validate_uuid_declarations(name: str, value: object) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise PortabilityContractError(f"{name} must be a tuple")
    if len(value) > _MAX_DECLARATIONS:
        raise PortabilityContractError(f"{name} has too many values")
    normalized = tuple(_validate_uuid(name, item) for item in value)
    if len(normalized) != len(set(normalized)):
        raise PortabilityContractError(f"{name} contains duplicates")
    return tuple(sorted(normalized))


__all__ = [
    "ExportBatchRecord",
    "ExportBatchStatus",
    "FutureRecoverability",
    "ImportBatchRecord",
    "ImportBatchStatus",
    "LossSeverity",
    "MappingDirection",
    "MappingReportRecord",
    "PortabilityLossRecord",
    "PreservationState",
]
