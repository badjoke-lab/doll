"""Typed State Package support for canonical portability publication records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from doll.generic_import_publication import (
    GenericImportPublicationError,
    ImportQuarantineRecord,
    OriginalSourceSnapshotRecord,
    SourceObjectMappingRecord,
    _IMPORT_BATCH_KEYS,
    _LOSS_KEYS,
    _MAPPING_REPORT_KEYS,
    _ORIGINAL_SOURCE_KEYS,
    _QUARANTINE_KEYS,
    _SOURCE_MAPPING_KEYS,
)
from doll.portability import (
    PortabilityContractError,
    SourceEnvironmentRecord,
    _SOURCE_ENVIRONMENT_KEYS,
)
from doll.portability_records import (
    FutureRecoverability,
    ImportBatchRecord,
    ImportBatchStatus,
    LossSeverity,
    MappingDirection,
    MappingReportRecord,
    PortabilityLossRecord,
    PreservationState,
)
from doll.state import RecordEnvelope, StateCorruptError
from doll.workspace_files import validate_managed_path

_SCHEMA_VERSION = 1


class PortabilityPackageCorruptError(StateCorruptError):
    """Raised when packaged portability state is malformed or inconsistent."""


@dataclass(frozen=True, slots=True)
class ManagedPortabilitySource:
    """One original-source managed file declared by portability state."""

    managed_path: str
    size_bytes: int
    source_root_hash: str

    @property
    def content_hash(self) -> str:
        return f"sha256:{self.source_root_hash}"


def source_environment_from_record(record: RecordEnvelope) -> SourceEnvironmentRecord:
    metadata = _metadata(record, "source_environment", _SOURCE_ENVIRONMENT_KEYS)
    try:
        return SourceEnvironmentRecord(
            environment_id=record.id,
            environment_class=cast(str, metadata["environment_class"]),
            provider_id=cast(str | None, metadata["provider_id"]),
            application_id=cast(str | None, metadata["application_id"]),
            interface_id=cast(str | None, metadata["interface_id"]),
            runtime_id=cast(str | None, metadata["runtime_id"]),
            export_format=cast(str | None, metadata["export_format"]),
            export_version=cast(str | None, metadata["export_version"]),
            observed_at=cast(str | None, metadata["observed_at"]),
        )
    except PortabilityContractError as exc:
        raise PortabilityPackageCorruptError("source environment metadata is invalid") from exc


def import_batch_from_record(record: RecordEnvelope) -> ImportBatchRecord:
    metadata = _metadata(record, "portability_import_batch", _IMPORT_BATCH_KEYS)
    try:
        return ImportBatchRecord(
            import_batch_id=record.id,
            source_environment_id=cast(str, metadata["source_environment_id"]),
            adapter_id=cast(str, metadata["adapter_id"]),
            adapter_version=cast(str, metadata["adapter_version"]),
            started_at=cast(str, metadata["started_at"]),
            completed_at=cast(str | None, metadata["completed_at"]),
            status=cast(ImportBatchStatus, metadata["status"]),
            source_root_hash=cast(str, metadata["source_root_hash"]),
            staged_object_count=cast(int, metadata["staged_object_count"]),
            published_object_count=cast(int, metadata["published_object_count"]),
            quarantined_object_count=cast(int, metadata["quarantined_object_count"]),
            mapping_report_id=cast(str | None, metadata["mapping_report_id"]),
            loss_report_id=cast(str | None, metadata["loss_report_id"]),
        )
    except PortabilityContractError as exc:
        raise PortabilityPackageCorruptError("import batch metadata is invalid") from exc


def mapping_report_from_record(record: RecordEnvelope) -> MappingReportRecord:
    metadata = _metadata(record, "portability_mapping_report", _MAPPING_REPORT_KEYS)
    counts = metadata["mapping_counts"]
    if not isinstance(counts, dict):
        raise PortabilityPackageCorruptError("mapping report counts are invalid")
    try:
        report = MappingReportRecord(
            mapping_report_id=record.id,
            direction=cast(MappingDirection, metadata["direction"]),
            batch_id=cast(str, metadata["batch_id"]),
            generated_at=cast(str, metadata["generated_at"]),
            total_object_count=cast(int, metadata["total_object_count"]),
            mapped_without_known_loss_count=_count(counts, "mapped_without_known_loss"),
            mapped_with_transformation_count=_count(counts, "mapped_with_transformation"),
            partially_mapped_count=_count(counts, "partially_mapped"),
            unsupported_but_preserved_count=_count(counts, "unsupported_but_preserved"),
            unsupported_and_omitted_count=_count(counts, "unsupported_and_omitted"),
            missing_dependency_count=_count(counts, "missing_dependency"),
            malformed_or_quarantined_count=_count(counts, "malformed_or_quarantined"),
            unknown_count=_count(counts, "unknown"),
            material_loss_count=cast(int, metadata["material_loss_count"]),
            loss_record_ids=_string_tuple(metadata["loss_record_ids"], "loss record ids"),
        )
    except PortabilityContractError as exc:
        raise PortabilityPackageCorruptError("mapping report metadata is invalid") from exc
    fidelity = metadata["full_fidelity_possible"]
    if not isinstance(fidelity, bool) or report.full_fidelity_possible != fidelity:
        raise PortabilityPackageCorruptError("mapping report fidelity declaration is invalid")
    return report


def portability_loss_from_record(record: RecordEnvelope) -> PortabilityLossRecord:
    metadata = _metadata(record, "portability_loss", _LOSS_KEYS)
    try:
        loss = PortabilityLossRecord(
            loss_record_id=record.id,
            batch_id=cast(str, metadata["batch_id"]),
            category=cast(str, metadata["category"]),
            severity=cast(LossSeverity, metadata["severity"]),
            description=cast(str, metadata["description"]),
            preservation_state=cast(PreservationState, metadata["preservation_state"]),
            future_recoverability=cast(
                FutureRecoverability,
                metadata["future_recoverability"],
            ),
            recorded_at=cast(str, metadata["recorded_at"]),
            source_object_id=cast(str | None, metadata["source_object_id"]),
            required_user_action=cast(str | None, metadata["required_user_action"]),
        )
    except PortabilityContractError as exc:
        raise PortabilityPackageCorruptError("portability loss metadata is invalid") from exc
    material = metadata["is_material"]
    if not isinstance(material, bool) or loss.is_material != material:
        raise PortabilityPackageCorruptError("portability loss materiality is invalid")
    return loss


def source_mapping_from_record(record: RecordEnvelope) -> SourceObjectMappingRecord:
    metadata = _metadata(record, "portability_source_mapping", _SOURCE_MAPPING_KEYS)
    try:
        return SourceObjectMappingRecord(
            mapping_id=record.id,
            source_environment_id=cast(str, metadata["source_environment_id"]),
            adapter_id=cast(str, metadata["adapter_id"]),
            adapter_version=cast(str, metadata["adapter_version"]),
            source_object_id=cast(str, metadata["source_object_id"]),
            source_type=cast(str, metadata["source_type"]),
            source_hash=cast(str, metadata["source_hash"]),
            payload_json=cast(str, metadata["payload_json"]),
            canonical_record_id=cast(str, metadata["canonical_record_id"]),
            canonical_record_type=cast(str, metadata["canonical_record_type"]),
            first_import_batch_id=cast(str, metadata["first_import_batch_id"]),
            authority_class=cast(str, metadata["authority_class"]),
        )
    except GenericImportPublicationError as exc:
        raise PortabilityPackageCorruptError("source mapping metadata is invalid") from exc


def quarantine_from_record(record: RecordEnvelope) -> ImportQuarantineRecord:
    metadata = _metadata(record, "portability_quarantine", _QUARANTINE_KEYS)
    try:
        return ImportQuarantineRecord(
            quarantine_id=record.id,
            import_batch_id=cast(str, metadata["import_batch_id"]),
            input_index=cast(int, metadata["input_index"]),
            source_object_id=cast(str | None, metadata["source_object_id"]),
            source_hash=cast(str, metadata["source_hash"]),
            reason=cast(str, metadata["reason"]),
            authority_class=cast(str, metadata["authority_class"]),
        )
    except GenericImportPublicationError as exc:
        raise PortabilityPackageCorruptError("quarantine metadata is invalid") from exc


def original_source_from_record(record: RecordEnvelope) -> OriginalSourceSnapshotRecord:
    metadata = _metadata(record, "portability_original_source", _ORIGINAL_SOURCE_KEYS)
    try:
        return OriginalSourceSnapshotRecord(
            snapshot_record_id=record.id,
            import_batch_id=cast(str, metadata["import_batch_id"]),
            source_root_hash=cast(str, metadata["source_root_hash"]),
            source_format=cast(str, metadata["source_format"]),
            preservation_state=cast(str, metadata["preservation_state"]),
            managed_path=cast(str | None, metadata["managed_path"]),
            size_bytes=cast(int, metadata["size_bytes"]),
            authority_class=cast(str, metadata["authority_class"]),
        )
    except GenericImportPublicationError as exc:
        raise PortabilityPackageCorruptError("original source metadata is invalid") from exc


def managed_source_from_record(record: RecordEnvelope) -> ManagedPortabilitySource | None:
    snapshot = original_source_from_record(record)
    if snapshot.managed_path is None:
        return None
    path = validate_managed_path(snapshot.managed_path).as_posix()
    return ManagedPortabilitySource(
        managed_path=path,
        size_bytes=snapshot.size_bytes,
        source_root_hash=snapshot.source_root_hash,
    )


def validate_portability_package_graph(records: dict[str, RecordEnvelope]) -> None:
    environments = {
        record.id: source_environment_from_record(record)
        for record in records.values()
        if record.record_type == "source_environment"
    }
    batches = {
        record.id: import_batch_from_record(record)
        for record in records.values()
        if record.record_type == "portability_import_batch"
    }
    reports = {
        record.id: mapping_report_from_record(record)
        for record in records.values()
        if record.record_type == "portability_mapping_report"
    }
    losses = {
        record.id: portability_loss_from_record(record)
        for record in records.values()
        if record.record_type == "portability_loss"
    }
    mappings = {
        record.id: source_mapping_from_record(record)
        for record in records.values()
        if record.record_type == "portability_source_mapping"
    }
    quarantines = {
        record.id: quarantine_from_record(record)
        for record in records.values()
        if record.record_type == "portability_quarantine"
    }
    snapshots = {
        record.id: original_source_from_record(record)
        for record in records.values()
        if record.record_type == "portability_original_source"
    }

    for batch in batches.values():
        if batch.source_environment_id not in environments:
            raise PortabilityPackageCorruptError("import batch source environment is missing")
        if batch.mapping_report_id is not None:
            report = reports.get(batch.mapping_report_id)
            if report is None or report.batch_id != batch.import_batch_id:
                raise PortabilityPackageCorruptError("import batch mapping report is invalid")
    for report in reports.values():
        if report.direction == "import" and report.batch_id not in batches:
            raise PortabilityPackageCorruptError("mapping report import batch is missing")
        for loss_id in report.loss_record_ids:
            loss = losses.get(loss_id)
            if loss is None or loss.batch_id != report.batch_id:
                raise PortabilityPackageCorruptError("mapping report loss link is invalid")
    for loss in losses.values():
        if loss.batch_id not in batches:
            raise PortabilityPackageCorruptError("portability loss batch is missing")
    for mapping in mappings.values():
        if mapping.source_environment_id not in environments:
            raise PortabilityPackageCorruptError("source mapping environment is missing")
        if mapping.first_import_batch_id not in batches:
            raise PortabilityPackageCorruptError("source mapping import batch is missing")
        canonical = records.get(mapping.canonical_record_id)
        if canonical is None or canonical.record_type != mapping.canonical_record_type:
            raise PortabilityPackageCorruptError("source mapping canonical record is invalid")
    for quarantine in quarantines.values():
        if quarantine.import_batch_id not in batches:
            raise PortabilityPackageCorruptError("quarantine import batch is missing")
    for snapshot in snapshots.values():
        batch = batches.get(snapshot.import_batch_id)
        if batch is None or batch.source_root_hash != snapshot.source_root_hash:
            raise PortabilityPackageCorruptError("original source import batch is invalid")


def _metadata(
    record: RecordEnvelope,
    expected_type: str,
    expected_keys: frozenset[str],
) -> dict[str, object]:
    if record.record_type != expected_type or record.schema_version != _SCHEMA_VERSION:
        raise PortabilityPackageCorruptError("record is not a supported portability record")
    if frozenset(record.metadata) != expected_keys:
        raise PortabilityPackageCorruptError("portability metadata shape is invalid")
    return record.metadata


def _count(mapping: dict[str, object], key: str) -> int:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise PortabilityPackageCorruptError("mapping report count is invalid")
    return value


def _string_tuple(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise PortabilityPackageCorruptError(f"{name} are invalid")
    return tuple(value)
