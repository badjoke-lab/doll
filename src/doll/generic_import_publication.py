"""Reviewed, idempotent publication for staged generic imports."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast
from uuid import UUID, uuid5

from doll.generic_import import (
    GenericImportStageResult,
    QuarantinedSourceObject,
    StagedSourceObject,
)
from doll.portability import PortabilityState, SourceEnvironmentRecord
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
from doll.state import (
    ConversationActorType,
    ConversationEventKind,
    ConversationEventRecord,
    ConversationRecord,
    RecordEnvelope,
    RecordProvenance,
    RecordSensitivity,
    RecordStatus,
    StateCorruptError,
)
from doll.state_repository import (
    StateRepository,
    _serialize_metadata,
    _validate_record_fields,
    _validate_record_id,
    _validate_secret_boundary,
)
from doll.workspace_files import (
    DEFAULT_MAX_ARTIFACT_BYTES,
    PublishedFileCleanupError,
    PublishedWorkspaceFile,
    publish_new_workspace_file,
    verify_workspace_file,
)

SourcePreservationState = Literal["managed_snapshot", "hash_only"]

_IMPORT_BATCH_RECORD_TYPE = "portability_import_batch"
_MAPPING_REPORT_RECORD_TYPE = "portability_mapping_report"
_LOSS_RECORD_TYPE = "portability_loss"
_SOURCE_MAPPING_RECORD_TYPE = "portability_source_mapping"
_QUARANTINE_RECORD_TYPE = "portability_quarantine"
_ORIGINAL_SOURCE_RECORD_TYPE = "portability_original_source"
_SOURCE_ENVIRONMENT_RECORD_TYPE = "source_environment"
_CONVERSATION_RECORD_TYPE = "conversation"
_CONVERSATION_EVENT_RECORD_TYPE = "conversation_event"
_SCHEMA_VERSION = 1
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_MAX_TEXT_LENGTH = 4096

_IMPORT_BATCH_KEYS = frozenset(
    {
        "source_environment_id",
        "adapter_id",
        "adapter_version",
        "started_at",
        "completed_at",
        "status",
        "source_root_hash",
        "staged_object_count",
        "published_object_count",
        "quarantined_object_count",
        "mapping_report_id",
        "loss_report_id",
    }
)
_MAPPING_REPORT_KEYS = frozenset(
    {
        "direction",
        "batch_id",
        "generated_at",
        "total_object_count",
        "mapping_counts",
        "material_loss_count",
        "loss_record_ids",
        "full_fidelity_possible",
    }
)
_LOSS_KEYS = frozenset(
    {
        "batch_id",
        "category",
        "severity",
        "description",
        "preservation_state",
        "future_recoverability",
        "recorded_at",
        "source_object_id",
        "required_user_action",
        "is_material",
    }
)
_SOURCE_MAPPING_KEYS = frozenset(
    {
        "source_environment_id",
        "adapter_id",
        "adapter_version",
        "source_object_id",
        "source_type",
        "source_hash",
        "payload_json",
        "canonical_record_id",
        "canonical_record_type",
        "first_import_batch_id",
        "authority_class",
    }
)
_QUARANTINE_KEYS = frozenset(
    {
        "import_batch_id",
        "input_index",
        "source_object_id",
        "source_hash",
        "reason",
        "authority_class",
    }
)
_ORIGINAL_SOURCE_KEYS = frozenset(
    {
        "import_batch_id",
        "source_root_hash",
        "source_format",
        "preservation_state",
        "managed_path",
        "size_bytes",
        "authority_class",
    }
)


class GenericImportPublicationError(RuntimeError):
    """Raised when a staged import cannot be reviewed or published safely."""


@dataclass(frozen=True, slots=True)
class SourceObjectMappingRecord:
    """Stable idempotency link from one source object to one canonical record."""

    mapping_id: str
    source_environment_id: str
    adapter_id: str
    adapter_version: str
    source_object_id: str
    source_type: str
    source_hash: str
    payload_json: str
    canonical_record_id: str
    canonical_record_type: str
    first_import_batch_id: str
    authority_class: str = "external_data"

    def __post_init__(self) -> None:
        for name in (
            "mapping_id",
            "source_environment_id",
            "canonical_record_id",
            "first_import_batch_id",
        ):
            _canonical_uuid(name.replace("_", " "), getattr(self, name))
        _validate_text("adapter id", self.adapter_id)
        _validate_text("adapter version", self.adapter_version)
        _validate_text("source object id", self.source_object_id)
        _validate_text("source type", self.source_type)
        _validate_sha256("source hash", self.source_hash)
        _validate_text(
            "payload JSON",
            self.payload_json,
            maximum=DEFAULT_MAX_ARTIFACT_BYTES,
        )
        _load_json_object(self.payload_json, "source mapping payload")
        if self.canonical_record_type not in {
            _CONVERSATION_RECORD_TYPE,
            _CONVERSATION_EVENT_RECORD_TYPE,
        }:
            raise GenericImportPublicationError("canonical record type is invalid")
        if self.authority_class != "external_data":
            raise GenericImportPublicationError("source mapping authority class is invalid")

    def canonical_metadata(self) -> dict[str, object]:
        return {
            "source_environment_id": self.source_environment_id,
            "adapter_id": self.adapter_id,
            "adapter_version": self.adapter_version,
            "source_object_id": self.source_object_id,
            "source_type": self.source_type,
            "source_hash": self.source_hash,
            "payload_json": self.payload_json,
            "canonical_record_id": self.canonical_record_id,
            "canonical_record_type": self.canonical_record_type,
            "first_import_batch_id": self.first_import_batch_id,
            "authority_class": self.authority_class,
        }


@dataclass(frozen=True, slots=True)
class ImportQuarantineRecord:
    """Persisted content-free description of one staged quarantine decision."""

    quarantine_id: str
    import_batch_id: str
    input_index: int
    source_object_id: str | None
    source_hash: str
    reason: str
    authority_class: str = "external_data"

    def __post_init__(self) -> None:
        _canonical_uuid("quarantine id", self.quarantine_id)
        _canonical_uuid("import batch id", self.import_batch_id)
        if isinstance(self.input_index, bool) or not isinstance(self.input_index, int):
            raise GenericImportPublicationError("quarantine input index is invalid")
        if self.input_index < 0:
            raise GenericImportPublicationError("quarantine input index is invalid")
        if self.source_object_id is not None:
            _validate_text("source object id", self.source_object_id)
        _validate_sha256("source hash", self.source_hash)
        _validate_text("quarantine reason", self.reason)
        if self.authority_class != "external_data":
            raise GenericImportPublicationError("quarantine authority class is invalid")

    def canonical_metadata(self) -> dict[str, object]:
        return {
            "import_batch_id": self.import_batch_id,
            "input_index": self.input_index,
            "source_object_id": self.source_object_id,
            "source_hash": self.source_hash,
            "reason": self.reason,
            "authority_class": self.authority_class,
        }


@dataclass(frozen=True, slots=True)
class OriginalSourceSnapshotRecord:
    """Hash-only or managed-copy preservation metadata for one import batch."""

    snapshot_record_id: str
    import_batch_id: str
    source_root_hash: str
    source_format: str
    preservation_state: SourcePreservationState
    managed_path: str | None
    size_bytes: int
    authority_class: str = "external_data"

    def __post_init__(self) -> None:
        _canonical_uuid("snapshot record id", self.snapshot_record_id)
        _canonical_uuid("import batch id", self.import_batch_id)
        _validate_sha256("source root hash", self.source_root_hash)
        if self.source_format not in {"json", "jsonl"}:
            raise GenericImportPublicationError("source format is invalid")
        if self.preservation_state not in {"managed_snapshot", "hash_only"}:
            raise GenericImportPublicationError("source preservation state is invalid")
        if isinstance(self.size_bytes, bool) or not isinstance(self.size_bytes, int):
            raise GenericImportPublicationError("source size is invalid")
        if self.size_bytes < 1 or self.size_bytes > DEFAULT_MAX_ARTIFACT_BYTES:
            raise GenericImportPublicationError("source size is outside the supported range")
        if self.preservation_state == "managed_snapshot":
            if self.managed_path is None:
                raise GenericImportPublicationError("managed snapshot path is required")
        elif self.managed_path is not None:
            raise GenericImportPublicationError("hash-only source cannot declare a managed path")
        if self.authority_class != "external_data":
            raise GenericImportPublicationError("source snapshot authority class is invalid")

    def canonical_metadata(self) -> dict[str, object]:
        return {
            "import_batch_id": self.import_batch_id,
            "source_root_hash": self.source_root_hash,
            "source_format": self.source_format,
            "preservation_state": self.preservation_state,
            "managed_path": self.managed_path,
            "size_bytes": self.size_bytes,
            "authority_class": self.authority_class,
        }


@dataclass(frozen=True, slots=True)
class ImportConflict:
    """Non-persisted conflict that blocks publication until a later policy resolves it."""

    source_object_id: str
    source_hash: str
    existing_source_hash: str | None
    reason: str

    def canonical_metadata(self) -> dict[str, object]:
        return {
            "source_object_id": self.source_object_id,
            "source_hash": self.source_hash,
            "existing_source_hash": self.existing_source_hash,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class _PlannedRecord:
    record_id: str
    record_type: str
    schema_version: int
    status: RecordStatus
    provenance: RecordProvenance
    sensitivity: RecordSensitivity
    title: str | None
    metadata: dict[str, object]

    def canonical_metadata(self) -> dict[str, object]:
        return {
            "record_id": self.record_id,
            "record_type": self.record_type,
            "schema_version": self.schema_version,
            "status": self.status,
            "provenance": self.provenance,
            "sensitivity": self.sensitivity,
            "title": self.title,
            "metadata": self.metadata,
        }


@dataclass(frozen=True, slots=True)
class GenericImportPublicationPreview:
    """Immutable reviewed plan; constructing it performs no write."""

    stage_result: GenericImportStageResult
    source_environment: SourceEnvironmentRecord
    preserve_source: bool
    source_size_bytes: int
    managed_source_path: str | None
    planned_records: tuple[_PlannedRecord, ...]
    created_canonical_record_ids: tuple[str, ...]
    reused_canonical_record_ids: tuple[str, ...]
    conflicts: tuple[ImportConflict, ...]
    plan_hash: str

    def canonical_summary(self) -> dict[str, object]:
        return {
            "import_batch_id": self.stage_result.import_batch.import_batch_id,
            "source_environment_id": self.source_environment.environment_id,
            "source_format": self.stage_result.source_format,
            "source_root_hash": self.stage_result.source_root_hash,
            "adapter_fingerprint": self.stage_result.adapter_fingerprint,
            "preserve_source": self.preserve_source,
            "source_size_bytes": self.source_size_bytes,
            "managed_source_path": self.managed_source_path,
            "planned_records": [item.canonical_metadata() for item in self.planned_records],
            "created_canonical_record_ids": list(self.created_canonical_record_ids),
            "reused_canonical_record_ids": list(self.reused_canonical_record_ids),
            "conflicts": [item.canonical_metadata() for item in self.conflicts],
            "stage_summary": self.stage_result.canonical_summary(),
        }


@dataclass(frozen=True, slots=True)
class GenericImportPublicationResult:
    """Result of one committed publication."""

    import_batch: ImportBatchRecord
    source_snapshot: OriginalSourceSnapshotRecord
    state_revision: int
    created_record_ids: tuple[str, ...]
    created_canonical_record_ids: tuple[str, ...]
    reused_canonical_record_ids: tuple[str, ...]


@dataclass(slots=True)
class GenericImportPublicationState:
    """Read validated portability publication records from Doll State."""

    repository: StateRepository

    def get_import_batch(self, import_batch_id: str) -> ImportBatchRecord:
        envelope = self._envelope(import_batch_id, _IMPORT_BATCH_RECORD_TYPE, _IMPORT_BATCH_KEYS)
        metadata = envelope.metadata
        return ImportBatchRecord(
            import_batch_id=envelope.id,
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

    def get_mapping_report(self, mapping_report_id: str) -> MappingReportRecord:
        envelope = self._envelope(
            mapping_report_id,
            _MAPPING_REPORT_RECORD_TYPE,
            _MAPPING_REPORT_KEYS,
        )
        metadata = envelope.metadata
        counts = metadata["mapping_counts"]
        if not isinstance(counts, dict):
            raise StateCorruptError("mapping report counts are invalid")
        report = MappingReportRecord(
            mapping_report_id=envelope.id,
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
        fidelity = metadata["full_fidelity_possible"]
        if not isinstance(fidelity, bool) or report.full_fidelity_possible != fidelity:
            raise StateCorruptError("mapping report fidelity declaration is invalid")
        return report

    def get_loss(self, loss_record_id: str) -> PortabilityLossRecord:
        envelope = self._envelope(loss_record_id, _LOSS_RECORD_TYPE, _LOSS_KEYS)
        metadata = envelope.metadata
        record = PortabilityLossRecord(
            loss_record_id=envelope.id,
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
        material = metadata["is_material"]
        if not isinstance(material, bool) or record.is_material != material:
            raise StateCorruptError("loss materiality declaration is invalid")
        return record

    def get_source_mapping(self, mapping_id: str) -> SourceObjectMappingRecord:
        envelope = self._envelope(mapping_id, _SOURCE_MAPPING_RECORD_TYPE, _SOURCE_MAPPING_KEYS)
        metadata = envelope.metadata
        return SourceObjectMappingRecord(
            mapping_id=envelope.id,
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

    def get_quarantine(self, quarantine_id: str) -> ImportQuarantineRecord:
        envelope = self._envelope(quarantine_id, _QUARANTINE_RECORD_TYPE, _QUARANTINE_KEYS)
        metadata = envelope.metadata
        return ImportQuarantineRecord(
            quarantine_id=envelope.id,
            import_batch_id=cast(str, metadata["import_batch_id"]),
            input_index=cast(int, metadata["input_index"]),
            source_object_id=cast(str | None, metadata["source_object_id"]),
            source_hash=cast(str, metadata["source_hash"]),
            reason=cast(str, metadata["reason"]),
            authority_class=cast(str, metadata["authority_class"]),
        )

    def get_original_source(self, snapshot_record_id: str) -> OriginalSourceSnapshotRecord:
        envelope = self._envelope(
            snapshot_record_id,
            _ORIGINAL_SOURCE_RECORD_TYPE,
            _ORIGINAL_SOURCE_KEYS,
        )
        metadata = envelope.metadata
        record = OriginalSourceSnapshotRecord(
            snapshot_record_id=envelope.id,
            import_batch_id=cast(str, metadata["import_batch_id"]),
            source_root_hash=cast(str, metadata["source_root_hash"]),
            source_format=cast(str, metadata["source_format"]),
            preservation_state=cast(SourcePreservationState, metadata["preservation_state"]),
            managed_path=cast(str | None, metadata["managed_path"]),
            size_bytes=cast(int, metadata["size_bytes"]),
            authority_class=cast(str, metadata["authority_class"]),
        )
        if record.managed_path is not None:
            digest = verify_workspace_file(
                self.repository.workspace.root / "artifacts",
                record.managed_path,
            )
            if digest.content_hash != f"sha256:{record.source_root_hash}":
                raise StateCorruptError("managed original source hash does not match state")
            if digest.size_bytes != record.size_bytes:
                raise StateCorruptError("managed original source size does not match state")
        return record

    def _envelope(
        self,
        record_id: str,
        record_type: str,
        keys: frozenset[str],
    ) -> RecordEnvelope:
        envelope = self.repository.get_record(_canonical_uuid("record id", record_id))
        if envelope.record_type != record_type or envelope.schema_version != _SCHEMA_VERSION:
            raise StateCorruptError("record is not a supported portability publication record")
        if frozenset(envelope.metadata) != keys:
            raise StateCorruptError("portability publication metadata shape is invalid")
        return envelope


@dataclass(slots=True)
class GenericImportPublisher:
    """Create deterministic previews and atomically publish approved staged imports."""

    repository: StateRepository
    source_environment: SourceEnvironmentRecord
    max_snapshot_bytes: int = DEFAULT_MAX_ARTIFACT_BYTES

    def __post_init__(self) -> None:
        if (
            isinstance(self.max_snapshot_bytes, bool)
            or not isinstance(self.max_snapshot_bytes, int)
            or not 1 <= self.max_snapshot_bytes <= DEFAULT_MAX_ARTIFACT_BYTES
        ):
            raise GenericImportPublicationError(
                "snapshot byte limit is outside the supported range"
            )

    def preview(
        self,
        stage_result: GenericImportStageResult,
        source_bytes: bytes,
        *,
        preserve_source: bool,
    ) -> GenericImportPublicationPreview:
        """Return a state-aware plan without modifying state or managed files."""

        self._validate_stage(stage_result, source_bytes)
        if not isinstance(preserve_source, bool):
            raise GenericImportPublicationError("preserve source decision must be boolean")
        source_objects = {item.source_object_id: item for item in stage_result.staged_objects}
        if len(source_objects) != len(stage_result.staged_objects):
            raise GenericImportPublicationError("staged source identifiers contain duplicates")
        canonical_ids = {
            source_id: _canonical_record_id(self.source_environment.environment_id, item)
            for source_id, item in source_objects.items()
        }
        roots = {
            source_id: _conversation_root(source_id, source_objects)
            for source_id in source_objects
        }
        state = GenericImportPublicationState(self.repository)
        planned: list[_PlannedRecord] = []
        created_canonical: list[str] = []
        reused_canonical: list[str] = []
        conflicts: list[ImportConflict] = []

        self._plan_source_environment(planned)
        planned_by_source: dict[str, tuple[_PlannedRecord, SourceObjectMappingRecord]] = {}
        for source_id in sorted(source_objects):
            staged = source_objects[source_id]
            mapping_id = _mapping_id(
                self.source_environment.environment_id,
                stage_result.import_batch.adapter_id,
                staged,
            )
            canonical_type = (
                _CONVERSATION_RECORD_TYPE
                if staged.source_type == "conversation"
                else _CONVERSATION_EVENT_RECORD_TYPE
            )
            try:
                existing = state.get_source_mapping(mapping_id)
            except KeyError:
                existing = None
            if existing is not None:
                reason = _mapping_conflict_reason(
                    existing,
                    stage_result,
                    staged,
                    canonical_ids[source_id],
                    canonical_type,
                )
                if reason is not None:
                    conflicts.append(
                        ImportConflict(
                            source_object_id=source_id,
                            source_hash=staged.source_hash,
                            existing_source_hash=existing.source_hash,
                            reason=reason,
                        )
                    )
                    continue
                self._validate_existing_canonical(existing)
                reused_canonical.append(existing.canonical_record_id)
                continue

            if _record_exists(self.repository, canonical_ids[source_id]):
                conflicts.append(
                    ImportConflict(
                        source_object_id=source_id,
                        source_hash=staged.source_hash,
                        existing_source_hash=None,
                        reason="canonical-record-id-already-exists-without-source-mapping",
                    )
                )
                continue
            canonical = self._canonical_record(
                staged,
                root_source_id=roots[source_id],
                source_objects=source_objects,
                canonical_ids=canonical_ids,
                mapping_id=mapping_id,
            )
            mapping = SourceObjectMappingRecord(
                mapping_id=mapping_id,
                source_environment_id=self.source_environment.environment_id,
                adapter_id=stage_result.import_batch.adapter_id,
                adapter_version=stage_result.import_batch.adapter_version,
                source_object_id=staged.source_object_id,
                source_type=staged.source_type,
                source_hash=staged.source_hash,
                payload_json=staged.payload_json,
                canonical_record_id=canonical.record_id,
                canonical_record_type=canonical.record_type,
                first_import_batch_id=stage_result.import_batch.import_batch_id,
            )
            planned_by_source[source_id] = (canonical, mapping)

        for source_id in sorted(planned_by_source, key=lambda item: (roots[item] != item, item)):
            canonical, mapping = planned_by_source[source_id]
            planned.extend((canonical, _mapping_planned_record(mapping)))
            created_canonical.append(canonical.record_id)

        conflicts.sort(key=lambda item: item.source_object_id)
        managed_path = (
            "imports/"
            f"{stage_result.import_batch.import_batch_id}/source.{stage_result.source_format}"
            if preserve_source
            else None
        )
        preview_without_hash = GenericImportPublicationPreview(
            stage_result=stage_result,
            source_environment=self.source_environment,
            preserve_source=preserve_source,
            source_size_bytes=len(source_bytes),
            managed_source_path=managed_path,
            planned_records=tuple(planned),
            created_canonical_record_ids=tuple(sorted(created_canonical)),
            reused_canonical_record_ids=tuple(sorted(set(reused_canonical))),
            conflicts=tuple(conflicts),
            plan_hash="0" * 64,
        )
        plan_hash = _hash_json(preview_without_hash.canonical_summary())
        return GenericImportPublicationPreview(
            stage_result=stage_result,
            source_environment=self.source_environment,
            preserve_source=preserve_source,
            source_size_bytes=len(source_bytes),
            managed_source_path=managed_path,
            planned_records=tuple(planned),
            created_canonical_record_ids=tuple(sorted(created_canonical)),
            reused_canonical_record_ids=tuple(sorted(set(reused_canonical))),
            conflicts=tuple(conflicts),
            plan_hash=plan_hash,
        )

    def publish(
        self,
        preview: GenericImportPublicationPreview,
        source_bytes: bytes,
        *,
        approved_plan_hash: str,
        completed_at: str,
    ) -> GenericImportPublicationResult:
        """Publish one exact approved plan in one database revision."""

        if approved_plan_hash != preview.plan_hash:
            raise GenericImportPublicationError("approved preview hash does not match the plan")
        current = self.preview(
            preview.stage_result,
            source_bytes,
            preserve_source=preview.preserve_source,
        )
        if current != preview:
            raise GenericImportPublicationError("publication preview is stale")
        if preview.conflicts:
            raise GenericImportPublicationError("publication preview contains unresolved conflicts")

        final_batch = _final_import_batch(preview.stage_result, completed_at)
        snapshot = OriginalSourceSnapshotRecord(
            snapshot_record_id=_snapshot_record_id(final_batch.import_batch_id),
            import_batch_id=final_batch.import_batch_id,
            source_root_hash=preview.stage_result.source_root_hash,
            source_format=preview.stage_result.source_format,
            preservation_state=("managed_snapshot" if preview.preserve_source else "hash_only"),
            managed_path=preview.managed_source_path,
            size_bytes=len(source_bytes),
        )
        records = list(preview.planned_records)
        records.extend(
            _publication_records(
                final_batch,
                preview.stage_result.mapping_report,
                preview.stage_result.loss_records,
                preview.stage_result.quarantined_objects,
                snapshot,
            )
        )
        records.sort(key=_publication_order)
        published_file: PublishedWorkspaceFile | None = None
        committed = False
        try:
            if preview.preserve_source:
                if snapshot.managed_path is None:  # pragma: no cover - dataclass invariant.
                    raise GenericImportPublicationError("managed snapshot path is missing")
                published_file = publish_new_workspace_file(
                    self.repository.workspace.root / "artifacts",
                    snapshot.managed_path,
                    source_bytes,
                    max_bytes=self.max_snapshot_bytes,
                )
                if published_file.content_hash != f"sha256:{snapshot.source_root_hash}":
                    raise GenericImportPublicationError("published source snapshot hash is invalid")
            revision = _commit_records_atomic(self.repository, records, completed_at)
            committed = True
            self.repository._sync_after_commit(revision)
            if published_file is not None:
                published_file.close()
        except BaseException:
            if published_file is not None:
                if committed:
                    published_file.close()
                else:
                    try:
                        published_file.cleanup()
                    except PublishedFileCleanupError as exc:
                        raise GenericImportPublicationError(
                            "import publication failed and source snapshot cleanup was incomplete"
                        ) from exc
            raise

        state = GenericImportPublicationState(self.repository)
        persisted_batch = state.get_import_batch(final_batch.import_batch_id)
        persisted_snapshot = state.get_original_source(snapshot.snapshot_record_id)
        return GenericImportPublicationResult(
            import_batch=persisted_batch,
            source_snapshot=persisted_snapshot,
            state_revision=revision,
            created_record_ids=tuple(item.record_id for item in records),
            created_canonical_record_ids=preview.created_canonical_record_ids,
            reused_canonical_record_ids=preview.reused_canonical_record_ids,
        )

    def _validate_stage(self, stage_result: GenericImportStageResult, source_bytes: bytes) -> None:
        if not isinstance(stage_result, GenericImportStageResult):
            raise GenericImportPublicationError("stage result is invalid")
        if not isinstance(source_bytes, bytes) or not source_bytes:
            raise GenericImportPublicationError("source bytes must be non-empty bytes")
        if len(source_bytes) > self.max_snapshot_bytes:
            raise GenericImportPublicationError("source input exceeds publication byte limit")
        if hashlib.sha256(source_bytes).hexdigest() != stage_result.source_root_hash:
            raise GenericImportPublicationError("source bytes do not match staged source hash")
        batch = stage_result.import_batch
        if batch.status != "staged":
            raise GenericImportPublicationError("import batch is not staged")
        if batch.source_environment_id != self.source_environment.environment_id:
            raise GenericImportPublicationError("source environment does not match staged import")
        if stage_result.mapping_report.batch_id != batch.import_batch_id:
            raise GenericImportPublicationError("mapping report does not match import batch")
        if stage_result.mapping_report.direction != "import":
            raise GenericImportPublicationError("mapping report direction is invalid")

    def _plan_source_environment(self, planned: list[_PlannedRecord]) -> None:
        try:
            existing = PortabilityState(self.repository).get_source_environment(
                self.source_environment.environment_id
            )
        except KeyError:
            planned.append(
                _make_planned_record(
                    record_id=self.source_environment.environment_id,
                    record_type=_SOURCE_ENVIRONMENT_RECORD_TYPE,
                    provenance="imported",
                    sensitivity="personal",
                    metadata=self.source_environment.canonical_metadata(),
                )
            )
            return
        if existing != self.source_environment:
            raise GenericImportPublicationError(
                "persisted source environment does not match staging"
            )

    def _validate_existing_canonical(self, mapping: SourceObjectMappingRecord) -> None:
        envelope = self.repository.get_record(mapping.canonical_record_id)
        if envelope.record_type != mapping.canonical_record_type:
            raise StateCorruptError("source mapping points to the wrong canonical record type")
        if envelope.provenance != "imported":
            raise StateCorruptError("source mapping points to a non-imported canonical record")

    def _canonical_record(
        self,
        staged: StagedSourceObject,
        *,
        root_source_id: str,
        source_objects: Mapping[str, StagedSourceObject],
        canonical_ids: Mapping[str, str],
        mapping_id: str,
    ) -> _PlannedRecord:
        payload = _load_json_object(staged.payload_json, "staged source payload")
        if staged.source_type == "conversation":
            if staged.parent_source_object_ids:
                raise GenericImportPublicationError(
                    "conversation source object cannot have parents"
                )
            title_value = payload.get("title")
            if title_value is not None and not isinstance(title_value, str):
                raise GenericImportPublicationError("conversation title must be text")
            record = ConversationRecord(
                conversation_id=canonical_ids[staged.source_object_id],
                title=cast(str | None, title_value),
                source_environment_id=self.source_environment.environment_id,
                source_conversation_id=staged.source_object_id,
            )
            return _make_planned_record(
                record_id=record.conversation_id,
                record_type=_CONVERSATION_RECORD_TYPE,
                provenance="imported",
                sensitivity="personal",
                title=record.title,
                metadata=record.canonical_metadata(),
            )

        direct_event_parents = tuple(
            canonical_ids[parent_id]
            for parent_id in staged.parent_source_object_ids
            if source_objects[parent_id].source_type != "conversation"
        )
        event_kind, actor_type = _event_contract(staged.source_type)
        occurred_at = payload.get("occurred_at")
        if occurred_at is not None and not isinstance(occurred_at, str):
            raise GenericImportPublicationError("event occurred_at must be text")
        sequence_hint = payload.get("sequence_hint")
        if sequence_hint is not None and (
            isinstance(sequence_hint, bool) or not isinstance(sequence_hint, int)
        ):
            raise GenericImportPublicationError("event sequence_hint must be an integer")
        extensions: dict[str, object] = {
            "source_payload": payload,
            "source_hash": staged.source_hash,
            "mapping_status": staged.mapping_status,
        }
        if self.source_environment.runtime_id is not None:
            extensions["source_runtime_id"] = self.source_environment.runtime_id
        record = ConversationEventRecord(
            event_id=canonical_ids[staged.source_object_id],
            conversation_id=canonical_ids[root_source_id],
            event_kind=event_kind,
            actor_type=actor_type,
            origin_class="imported_data",
            parent_event_ids=direct_event_parents,
            sequence_hint=cast(int | None, sequence_hint),
            content_reference=f"imported-source:{mapping_id}",
            occurred_at=cast(str | None, occurred_at),
            source_event_kind=staged.source_type,
            source_environment_id=self.source_environment.environment_id,
            source_object_id=staged.source_object_id,
            provider_id=self.source_environment.provider_id,
            application_id=self.source_environment.application_id,
            interface_id=self.source_environment.interface_id,
            extensions=extensions,
        )
        return _make_planned_record(
            record_id=record.event_id,
            record_type=_CONVERSATION_EVENT_RECORD_TYPE,
            provenance="imported",
            sensitivity="personal",
            metadata=record.canonical_metadata(),
        )


def _mapping_conflict_reason(
    existing: SourceObjectMappingRecord,
    stage_result: GenericImportStageResult,
    staged: StagedSourceObject,
    canonical_record_id: str,
    canonical_record_type: str,
) -> str | None:
    if existing.source_environment_id != stage_result.import_batch.source_environment_id:
        return "source-environment-mismatch"
    if existing.adapter_id != stage_result.import_batch.adapter_id:
        return "source-adapter-mismatch"
    if existing.adapter_version != stage_result.import_batch.adapter_version:
        return "source-adapter-version-mismatch"
    if (
        existing.source_object_id != staged.source_object_id
        or existing.source_type != staged.source_type
    ):
        return "source-identity-mismatch"
    if existing.source_hash != staged.source_hash:
        return "changed-source-object"
    if existing.payload_json != staged.payload_json:
        return "changed-source-payload"
    if (
        existing.canonical_record_id != canonical_record_id
        or existing.canonical_record_type != canonical_record_type
    ):
        return "canonical-mapping-mismatch"
    return None


def _conversation_root(
    source_object_id: str,
    source_objects: Mapping[str, StagedSourceObject],
) -> str:
    memo: dict[str, frozenset[str]] = {}

    def roots(current_id: str) -> frozenset[str]:
        if current_id in memo:
            return memo[current_id]
        current = source_objects[current_id]
        if current.source_type == "conversation":
            result = frozenset({current_id})
        else:
            found: set[str] = set()
            for parent_id in current.parent_source_object_ids:
                found.update(roots(parent_id))
            result = frozenset(found)
        memo[current_id] = result
        return result

    found = roots(source_object_id)
    if len(found) != 1:
        raise GenericImportPublicationError(
            "each publishable source object must resolve to exactly one conversation"
        )
    return next(iter(found))


def _event_contract(source_type: str) -> tuple[ConversationEventKind, ConversationActorType]:
    known: dict[str, tuple[ConversationEventKind, ConversationActorType]] = {
        "user-message": ("user_message", "user"),
        "assistant-message": ("assistant_message", "assistant"),
        "system-message": ("system_context_snapshot", "system"),
        "system-context-snapshot": ("system_context_snapshot", "system"),
        "model-runtime-change": ("model_runtime_change", "runtime"),
        "tool-request": ("tool_request", "tool"),
        "tool-result": ("tool_result", "tool"),
        "attachment": ("attachment_reference", "importer"),
        "branch-creation": ("branch_creation", "importer"),
        "edit-regeneration": ("edit_regeneration", "importer"),
        "citation-reference": ("citation_reference", "importer"),
        "error": ("error", "unknown"),
    }
    return known.get(source_type, ("imported_unknown_event", "unknown"))


def _canonical_record_id(environment_id: str, staged: StagedSourceObject) -> str:
    kind = "conversation" if staged.source_type == "conversation" else "conversation-event"
    return str(uuid5(UUID(environment_id), f"canonical:{kind}:{staged.source_object_id}"))


def _mapping_id(environment_id: str, adapter_id: str, staged: StagedSourceObject) -> str:
    return str(
        uuid5(
            UUID(environment_id),
            f"source-mapping:{adapter_id}:{staged.source_object_id}",
        )
    )


def _snapshot_record_id(import_batch_id: str) -> str:
    return str(uuid5(UUID(import_batch_id), "original-source"))


def _quarantine_record(
    item: QuarantinedSourceObject,
    import_batch_id: str,
) -> ImportQuarantineRecord:
    quarantine_id = str(
        uuid5(
            UUID(import_batch_id),
            f"quarantine:{item.input_index}:{item.source_hash}",
        )
    )
    return ImportQuarantineRecord(
        quarantine_id=quarantine_id,
        import_batch_id=import_batch_id,
        input_index=item.input_index,
        source_object_id=item.source_object_id,
        source_hash=item.source_hash,
        reason=item.reason,
    )


def _mapping_planned_record(record: SourceObjectMappingRecord) -> _PlannedRecord:
    return _make_planned_record(
        record_id=record.mapping_id,
        record_type=_SOURCE_MAPPING_RECORD_TYPE,
        provenance="imported",
        sensitivity="personal",
        metadata=record.canonical_metadata(),
    )


def _publication_records(
    batch: ImportBatchRecord,
    report: MappingReportRecord,
    losses: Sequence[PortabilityLossRecord],
    quarantined: Sequence[QuarantinedSourceObject],
    snapshot: OriginalSourceSnapshotRecord,
) -> list[_PlannedRecord]:
    records = [
        _make_planned_record(
            record_id=batch.import_batch_id,
            record_type=_IMPORT_BATCH_RECORD_TYPE,
            provenance="system-generated",
            sensitivity="personal",
            metadata=batch.canonical_metadata(),
        ),
        _make_planned_record(
            record_id=report.mapping_report_id,
            record_type=_MAPPING_REPORT_RECORD_TYPE,
            provenance="system-generated",
            sensitivity="personal",
            metadata=report.canonical_metadata(),
        ),
        _make_planned_record(
            record_id=snapshot.snapshot_record_id,
            record_type=_ORIGINAL_SOURCE_RECORD_TYPE,
            provenance="imported",
            sensitivity="personal",
            metadata=snapshot.canonical_metadata(),
        ),
    ]
    records.extend(
        _make_planned_record(
            record_id=loss.loss_record_id,
            record_type=_LOSS_RECORD_TYPE,
            provenance="system-generated",
            sensitivity="personal",
            metadata=loss.canonical_metadata(),
        )
        for loss in losses
    )
    records.extend(
        _make_planned_record(
            record_id=record.quarantine_id,
            record_type=_QUARANTINE_RECORD_TYPE,
            provenance="system-generated",
            sensitivity="personal",
            metadata=record.canonical_metadata(),
        )
        for record in (_quarantine_record(item, batch.import_batch_id) for item in quarantined)
    )
    return records


def _final_import_batch(
    stage_result: GenericImportStageResult,
    completed_at: str,
) -> ImportBatchRecord:
    staged_count = stage_result.import_batch.staged_object_count
    quarantined_count = stage_result.import_batch.quarantined_object_count
    successful_count = staged_count - quarantined_count
    if successful_count == 0:
        status: ImportBatchStatus = "rejected"
        published_count = 0
    elif quarantined_count == 0:
        status = "published"
        published_count = staged_count
    else:
        status = "partially_published"
        published_count = successful_count
    return ImportBatchRecord(
        import_batch_id=stage_result.import_batch.import_batch_id,
        source_environment_id=stage_result.import_batch.source_environment_id,
        adapter_id=stage_result.import_batch.adapter_id,
        adapter_version=stage_result.import_batch.adapter_version,
        started_at=stage_result.import_batch.started_at,
        completed_at=completed_at,
        status=status,
        source_root_hash=stage_result.import_batch.source_root_hash,
        staged_object_count=staged_count,
        published_object_count=published_count,
        quarantined_object_count=quarantined_count,
        mapping_report_id=stage_result.mapping_report.mapping_report_id,
        loss_report_id=None,
    )


def _make_planned_record(
    *,
    record_id: str,
    record_type: str,
    provenance: RecordProvenance,
    sensitivity: RecordSensitivity,
    metadata: dict[str, object],
    title: str | None = None,
) -> _PlannedRecord:
    _validate_record_id(record_id)
    _validate_record_fields(
        record_type=record_type,
        schema_version=_SCHEMA_VERSION,
        status="active",
        provenance=provenance,
        sensitivity=sensitivity,
    )
    _validate_secret_boundary(
        record_type=record_type,
        sensitivity=sensitivity,
        metadata=metadata,
    )
    _serialize_metadata(metadata)
    return _PlannedRecord(
        record_id=record_id,
        record_type=record_type,
        schema_version=_SCHEMA_VERSION,
        status="active",
        provenance=provenance,
        sensitivity=sensitivity,
        title=title,
        metadata=metadata,
    )


def _publication_order(record: _PlannedRecord) -> tuple[int, str]:
    priority = {
        _SOURCE_ENVIRONMENT_RECORD_TYPE: 0,
        _CONVERSATION_RECORD_TYPE: 1,
        _CONVERSATION_EVENT_RECORD_TYPE: 2,
        _SOURCE_MAPPING_RECORD_TYPE: 3,
        _IMPORT_BATCH_RECORD_TYPE: 4,
        _MAPPING_REPORT_RECORD_TYPE: 5,
        _LOSS_RECORD_TYPE: 6,
        _QUARANTINE_RECORD_TYPE: 7,
        _ORIGINAL_SOURCE_RECORD_TYPE: 8,
    }
    return (priority[record.record_type], record.record_id)


def _commit_records_atomic(
    repository: StateRepository,
    records: Sequence[_PlannedRecord],
    created_at: str,
) -> int:
    repository._require_write()
    ids = [item.record_id for item in records]
    if len(ids) != len(set(ids)):
        raise GenericImportPublicationError(
            "publication plan contains duplicate record identifiers"
        )
    connection = repository.connection
    connection.execute("BEGIN IMMEDIATE")
    try:
        for record_id in ids:
            if connection.execute("SELECT 1 FROM records WHERE id = ?", (record_id,)).fetchone():
                raise GenericImportPublicationError("publication target record already exists")
        for record in records:
            _insert_planned_record(connection, record, created_at)
        revision = repository._commit_state_revision()
        connection.execute("COMMIT")
    except BaseException:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise
    return revision


def _insert_planned_record(
    connection: sqlite3.Connection,
    record: _PlannedRecord,
    created_at: str,
) -> None:
    connection.execute(
        """
        INSERT INTO records (
            id,
            record_type,
            schema_version,
            created_at,
            updated_at,
            revision,
            status,
            provenance,
            sensitivity,
            title,
            metadata_json
        ) VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?)
        """,
        (
            record.record_id,
            record.record_type,
            record.schema_version,
            created_at,
            created_at,
            record.status,
            record.provenance,
            record.sensitivity,
            record.title,
            _serialize_metadata(record.metadata),
        ),
    )


def _record_exists(repository: StateRepository, record_id: str) -> bool:
    return (
        repository.connection.execute("SELECT 1 FROM records WHERE id = ?", (record_id,)).fetchone()
        is not None
    )


def _count(value: Mapping[object, object], key: str) -> int:
    item = value.get(key)
    if isinstance(item, bool) or not isinstance(item, int):
        raise StateCorruptError("mapping report count is invalid")
    return item


def _string_tuple(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise StateCorruptError(f"{name} are invalid")
    return tuple(cast(list[str], value))


def _load_json_object(value: str, name: str) -> dict[str, object]:
    try:
        parsed = json.loads(value, parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError) as exc:
        raise GenericImportPublicationError(f"{name} is invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise GenericImportPublicationError(f"{name} must be an object")
    return cast(dict[str, object], parsed)


def _reject_json_constant(value: str) -> object:
    raise ValueError(f"non-standard JSON constant: {value}")


def _hash_json(value: object) -> str:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise GenericImportPublicationError("publication preview is not canonical JSON") from exc
    return hashlib.sha256(encoded).hexdigest()


def _canonical_uuid(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise GenericImportPublicationError(f"{name} must be text")
    try:
        canonical = str(UUID(value))
    except (ValueError, AttributeError) as exc:
        raise GenericImportPublicationError(f"{name} is invalid") from exc
    if canonical != value:
        raise GenericImportPublicationError(f"{name} must use canonical UUID text")
    return canonical


def _validate_sha256(name: str, value: object) -> str:
    if not isinstance(value, str) or _SHA256_PATTERN.fullmatch(value) is None:
        raise GenericImportPublicationError(f"{name} is invalid")
    return value


def _validate_text(name: str, value: object, *, maximum: int = _MAX_TEXT_LENGTH) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise GenericImportPublicationError(f"{name} is invalid")
    return value


__all__ = [
    "GenericImportPublicationError",
    "GenericImportPublicationPreview",
    "GenericImportPublicationResult",
    "GenericImportPublicationState",
    "GenericImportPublisher",
    "ImportConflict",
    "ImportQuarantineRecord",
    "OriginalSourceSnapshotRecord",
    "SourceObjectMappingRecord",
    "SourcePreservationState",
]
