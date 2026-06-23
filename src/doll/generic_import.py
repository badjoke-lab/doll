"""In-memory staging for the versioned generic JSON and JSONL import format."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Literal, cast
from uuid import UUID, uuid5

from doll.portability import (
    PortabilityContractError,
    SourceAdapterContract,
    SourceEnvironmentRecord,
)
from doll.portability_records import (
    ImportBatchRecord,
    MappingReportRecord,
    PortabilityLossRecord,
)

GenericImportFormat = Literal["json", "jsonl"]
StagedMappingStatus = Literal[
    "mapped_without_known_loss",
    "mapped_with_transformation",
]

_FORMAT_NAME = "doll-generic-import"
_FORMATS = frozenset({"json", "jsonl"})
_JSON_ENVELOPE_KEYS = frozenset({"format", "format_version", "source_environment_id", "objects"})
_JSONL_MANIFEST_KEYS = frozenset(
    {"record_kind", "format", "format_version", "source_environment_id"}
)
_OBJECT_KEYS = frozenset({"source_object_id", "source_type", "parent_source_object_ids", "payload"})
_JSONL_OBJECT_KEYS = _OBJECT_KEYS | {"record_kind"}
_MAX_SOURCE_ID_LENGTH = 1024
_MAX_REASON_LENGTH = 256


class GenericImportStagingError(PortabilityContractError):
    """Raised when an input cannot safely produce a staging result."""


@dataclass(frozen=True, slots=True)
class StagedSourceObject:
    """One accepted external-data object represented without execution."""

    source_object_id: str
    source_type: str
    parent_source_object_ids: tuple[str, ...]
    source_hash: str
    payload_json: str
    mapping_status: StagedMappingStatus
    authority_class: str = "external_data"

    def canonical_metadata(self) -> dict[str, object]:
        return {
            "source_object_id": self.source_object_id,
            "source_type": self.source_type,
            "parent_source_object_ids": list(self.parent_source_object_ids),
            "source_hash": self.source_hash,
            "payload_json": self.payload_json,
            "mapping_status": self.mapping_status,
            "authority_class": self.authority_class,
        }


@dataclass(frozen=True, slots=True)
class QuarantinedSourceObject:
    """Bounded, content-free description of one rejected source object."""

    input_index: int
    source_object_id: str | None
    source_hash: str
    reason: str

    def __post_init__(self) -> None:
        if self.input_index < 0:
            raise GenericImportStagingError("quarantine input index is invalid")
        if not self.reason or len(self.reason) > _MAX_REASON_LENGTH:
            raise GenericImportStagingError("quarantine reason is invalid")

    def canonical_metadata(self) -> dict[str, object]:
        return {
            "input_index": self.input_index,
            "source_object_id": self.source_object_id,
            "source_hash": self.source_hash,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class GenericImportStageResult:
    """Immutable staging plan with no publication authority or state write."""

    source_format: GenericImportFormat
    format_version: str
    source_root_hash: str
    adapter_fingerprint: str
    import_batch: ImportBatchRecord
    mapping_report: MappingReportRecord
    staged_objects: tuple[StagedSourceObject, ...]
    quarantined_objects: tuple[QuarantinedSourceObject, ...]
    loss_records: tuple[PortabilityLossRecord, ...]
    duplicate_object_count: int

    def __post_init__(self) -> None:
        if self.source_format not in _FORMATS:
            raise GenericImportStagingError("source format is invalid")
        if self.duplicate_object_count < 0:
            raise GenericImportStagingError("duplicate object count is invalid")

    def canonical_summary(self) -> dict[str, object]:
        return {
            "source_format": self.source_format,
            "format_version": self.format_version,
            "source_root_hash": self.source_root_hash,
            "adapter_fingerprint": self.adapter_fingerprint,
            "import_batch": self.import_batch.canonical_metadata(),
            "mapping_report": self.mapping_report.canonical_metadata(),
            "staged_objects": [item.canonical_metadata() for item in self.staged_objects],
            "quarantined_objects": [item.canonical_metadata() for item in self.quarantined_objects],
            "loss_records": [item.canonical_metadata() for item in self.loss_records],
            "duplicate_object_count": self.duplicate_object_count,
        }


@dataclass(frozen=True, slots=True)
class GenericImportStager:
    """Parse and classify generic import bytes without I/O or publication."""

    adapter: SourceAdapterContract
    source_environment: SourceEnvironmentRecord

    def __post_init__(self) -> None:
        if self.adapter.network_behavior != "none":
            raise GenericImportStagingError(
                "generic in-memory staging requires network behavior none"
            )
        if self.adapter.source_environment_class != self.source_environment.environment_class:
            raise GenericImportStagingError(
                "source environment class does not match adapter contract"
            )

    def stage(
        self,
        source_bytes: bytes,
        *,
        source_format: GenericImportFormat,
        import_batch_id: str,
        started_at: str,
    ) -> GenericImportStageResult:
        """Return a deterministic staging result for accepted caller-provided bytes."""

        if source_format not in _FORMATS:
            raise GenericImportStagingError("source format is invalid")
        if not isinstance(source_bytes, bytes):
            raise GenericImportStagingError("source bytes must be bytes")
        if len(source_bytes) > self.adapter.resource_limits.max_input_bytes:
            raise GenericImportStagingError("source input exceeds adapter byte limit")
        if not source_bytes:
            raise GenericImportStagingError("source input must not be empty")
        if (
            self.source_environment.export_format is not None
            and self.source_environment.export_format != source_format
        ):
            raise GenericImportStagingError("source format does not match source environment")

        try:
            source_text = source_bytes.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise GenericImportStagingError("source input is not valid UTF-8") from exc

        source_root_hash = hashlib.sha256(source_bytes).hexdigest()
        if source_format == "json":
            manifest, raw_objects = _parse_json_envelope(source_text)
        else:
            manifest, raw_objects = _parse_jsonl_envelope(source_text)

        format_version = _validate_manifest(
            manifest,
            source_environment=self.source_environment,
            adapter=self.adapter,
        )
        if len(raw_objects) > self.adapter.resource_limits.max_object_count:
            raise GenericImportStagingError("source object count exceeds adapter limit")
        for raw in raw_objects:
            if raw.value is not None:
                try:
                    depth = _json_depth(raw.value)
                except RecursionError as exc:
                    raise GenericImportStagingError(
                        "source nesting exceeds safe parser depth"
                    ) from exc
                if depth > self.adapter.resource_limits.max_nesting_depth:
                    raise GenericImportStagingError("source nesting exceeds adapter limit")

        return self._build_stage_result(
            raw_objects,
            source_format=source_format,
            format_version=format_version,
            source_root_hash=source_root_hash,
            import_batch_id=import_batch_id,
            started_at=started_at,
        )

    def _build_stage_result(
        self,
        raw_objects: tuple[_RawObject, ...],
        *,
        source_format: GenericImportFormat,
        format_version: str,
        source_root_hash: str,
        import_batch_id: str,
        started_at: str,
    ) -> GenericImportStageResult:
        parsed: list[_Candidate] = []
        quarantined: list[QuarantinedSourceObject] = []
        losses: list[PortabilityLossRecord] = []
        mapping_counts = _empty_mapping_counts()
        material_object_indexes: set[int] = set()
        occurrence_indexes: dict[str, tuple[int, ...]] = {}

        for raw in raw_objects:
            if raw.parse_reason is not None:
                quarantined.append(
                    QuarantinedSourceObject(
                        input_index=raw.input_index,
                        source_object_id=None,
                        source_hash=raw.source_hash,
                        reason=raw.parse_reason,
                    )
                )
                mapping_counts["malformed_or_quarantined"] += 1
                material_object_indexes.add(raw.input_index)
                losses.append(
                    _make_loss(
                        import_batch_id,
                        raw.input_index,
                        recorded_at=started_at,
                        category="malformed-object",
                        source_object_id=None,
                        description="A source object could not be parsed safely.",
                    )
                )
                continue
            try:
                candidate = _parse_candidate(raw)
            except _ObjectProblem as problem:
                quarantined.append(
                    QuarantinedSourceObject(
                        input_index=raw.input_index,
                        source_object_id=problem.source_object_id,
                        source_hash=raw.source_hash,
                        reason=problem.reason,
                    )
                )
                mapping_counts["malformed_or_quarantined"] += 1
                material_object_indexes.add(raw.input_index)
                losses.append(
                    _make_loss(
                        import_batch_id,
                        raw.input_index,
                        recorded_at=started_at,
                        category="malformed-object",
                        source_object_id=problem.source_object_id,
                        description="A source object failed structural validation.",
                    )
                )
                continue
            parsed.append(candidate)

        accepted, duplicate_count = self._classify_duplicates_and_support(
            parsed,
            import_batch_id=import_batch_id,
            started_at=started_at,
            quarantined=quarantined,
            losses=losses,
            mapping_counts=mapping_counts,
            material_object_indexes=material_object_indexes,
            occurrence_indexes=occurrence_indexes,
        )
        self._quarantine_cycles_and_missing_dependencies(
            accepted,
            import_batch_id=import_batch_id,
            started_at=started_at,
            quarantined=quarantined,
            losses=losses,
            mapping_counts=mapping_counts,
            material_object_indexes=material_object_indexes,
            occurrence_indexes=occurrence_indexes,
        )

        staged_objects: list[StagedSourceObject] = []
        for candidate in accepted.values():
            indexes = occurrence_indexes[candidate.source_object_id]
            occurrence_count = len(indexes)
            mapping_status: StagedMappingStatus = "mapped_without_known_loss"
            transformed = False
            if (
                candidate.parent_source_object_ids
                and self.adapter.branch_behavior == "linearize_with_loss"
            ):
                transformed = True
                material_object_indexes.update(indexes)
                for input_index in indexes:
                    losses.append(
                        _make_loss(
                            import_batch_id,
                            input_index,
                            recorded_at=started_at,
                            category="branch-linearization",
                            source_object_id=candidate.source_object_id,
                            description=(
                                "The adapter declares branch linearization for this source object."
                            ),
                        )
                    )
            if (
                candidate.source_type == "attachment"
                and self.adapter.attachment_behavior == "metadata_only"
            ):
                transformed = True
                material_object_indexes.update(indexes)
                for input_index in indexes:
                    losses.append(
                        _make_loss(
                            import_batch_id,
                            input_index,
                            recorded_at=started_at,
                            category="attachment-metadata-only",
                            source_object_id=candidate.source_object_id,
                            description=(
                                "The adapter preserves attachment metadata without "
                                "attachment bytes."
                            ),
                        )
                    )
            if transformed:
                mapping_status = "mapped_with_transformation"
                mapping_counts["mapped_with_transformation"] += occurrence_count
            else:
                mapping_counts["mapped_without_known_loss"] += occurrence_count
            staged_objects.append(
                StagedSourceObject(
                    source_object_id=candidate.source_object_id,
                    source_type=candidate.source_type,
                    parent_source_object_ids=candidate.parent_source_object_ids,
                    source_hash=candidate.source_hash,
                    payload_json=candidate.payload_json,
                    mapping_status=mapping_status,
                )
            )

        staged_objects.sort(key=lambda item: item.source_object_id)
        quarantined.sort(key=lambda item: item.input_index)
        losses.sort(key=lambda item: item.loss_record_id)
        mapping_report_id = str(uuid5(UUID(import_batch_id), "mapping-report"))
        mapping_report = MappingReportRecord(
            mapping_report_id=mapping_report_id,
            direction="import",
            batch_id=import_batch_id,
            generated_at=started_at,
            total_object_count=len(raw_objects),
            mapped_without_known_loss_count=mapping_counts["mapped_without_known_loss"],
            mapped_with_transformation_count=mapping_counts["mapped_with_transformation"],
            partially_mapped_count=mapping_counts["partially_mapped"],
            unsupported_but_preserved_count=mapping_counts["unsupported_but_preserved"],
            unsupported_and_omitted_count=mapping_counts["unsupported_and_omitted"],
            missing_dependency_count=mapping_counts["missing_dependency"],
            malformed_or_quarantined_count=mapping_counts["malformed_or_quarantined"],
            unknown_count=mapping_counts["unknown"],
            material_loss_count=len(material_object_indexes),
            loss_record_ids=tuple(item.loss_record_id for item in losses),
        )
        import_batch = ImportBatchRecord(
            import_batch_id=import_batch_id,
            source_environment_id=self.source_environment.environment_id,
            adapter_id=self.adapter.adapter_id,
            adapter_version=self.adapter.adapter_version,
            started_at=started_at,
            status="staged",
            source_root_hash=source_root_hash,
            staged_object_count=len(raw_objects),
            published_object_count=0,
            quarantined_object_count=len(quarantined),
            mapping_report_id=mapping_report_id,
        )
        return GenericImportStageResult(
            source_format=source_format,
            format_version=format_version,
            source_root_hash=source_root_hash,
            adapter_fingerprint=self.adapter.fingerprint,
            import_batch=import_batch,
            mapping_report=mapping_report,
            staged_objects=tuple(staged_objects),
            quarantined_objects=tuple(quarantined),
            loss_records=tuple(losses),
            duplicate_object_count=duplicate_count,
        )

    def _classify_duplicates_and_support(
        self,
        candidates: list[_Candidate],
        *,
        import_batch_id: str,
        started_at: str,
        quarantined: list[QuarantinedSourceObject],
        losses: list[PortabilityLossRecord],
        mapping_counts: dict[str, int],
        material_object_indexes: set[int],
        occurrence_indexes: dict[str, tuple[int, ...]],
    ) -> dict[str, _Candidate]:
        grouped: dict[str, list[_Candidate]] = {}
        for candidate in candidates:
            grouped.setdefault(candidate.source_object_id, []).append(candidate)

        accepted: dict[str, _Candidate] = {}
        duplicate_count = 0
        for source_object_id in sorted(grouped):
            group = grouped[source_object_id]
            unique_hashes = {item.source_hash for item in group}
            if len(unique_hashes) > 1:
                for item in group:
                    quarantined.append(
                        QuarantinedSourceObject(
                            input_index=item.input_index,
                            source_object_id=item.source_object_id,
                            source_hash=item.source_hash,
                            reason="conflicting-duplicate",
                        )
                    )
                    mapping_counts["malformed_or_quarantined"] += 1
                    material_object_indexes.add(item.input_index)
                    losses.append(
                        _make_loss(
                            import_batch_id,
                            item.input_index,
                            recorded_at=started_at,
                            category="conflicting-duplicate",
                            source_object_id=item.source_object_id,
                            description=("The same source identifier has conflicting content."),
                        )
                    )
                continue

            representative = min(group, key=lambda item: item.input_index)
            if (
                representative.source_type == "attachment"
                and len(representative.payload_json.encode("utf-8"))
                > self.adapter.resource_limits.max_attachment_bytes
            ):
                for item in group:
                    quarantined.append(
                        QuarantinedSourceObject(
                            input_index=item.input_index,
                            source_object_id=item.source_object_id,
                            source_hash=item.source_hash,
                            reason="attachment-byte-limit",
                        )
                    )
                    mapping_counts["malformed_or_quarantined"] += 1
                    material_object_indexes.add(item.input_index)
                    losses.append(
                        _make_loss(
                            import_batch_id,
                            item.input_index,
                            recorded_at=started_at,
                            category="attachment-byte-limit",
                            source_object_id=item.source_object_id,
                            description=("The attachment payload exceeds the declared byte limit."),
                        )
                    )
                continue
            if not self._source_type_supported(representative):
                for item in group:
                    quarantined.append(
                        QuarantinedSourceObject(
                            input_index=item.input_index,
                            source_object_id=item.source_object_id,
                            source_hash=item.source_hash,
                            reason="unsupported-source-type",
                        )
                    )
                    mapping_counts["unsupported_but_preserved"] += 1
                    material_object_indexes.add(item.input_index)
                    losses.append(
                        _make_loss(
                            import_batch_id,
                            item.input_index,
                            recorded_at=started_at,
                            category="unsupported-source-type",
                            source_object_id=item.source_object_id,
                            description=(
                                "The adapter does not declare support for this source type."
                            ),
                        )
                    )
                continue
            if (
                representative.parent_source_object_ids
                and self.adapter.branch_behavior == "unsupported"
            ):
                for item in group:
                    quarantined.append(
                        QuarantinedSourceObject(
                            input_index=item.input_index,
                            source_object_id=item.source_object_id,
                            source_hash=item.source_hash,
                            reason="unsupported-branch-relationship",
                        )
                    )
                    mapping_counts["unsupported_but_preserved"] += 1
                    material_object_indexes.add(item.input_index)
                    losses.append(
                        _make_loss(
                            import_batch_id,
                            item.input_index,
                            recorded_at=started_at,
                            category="unsupported-branch-relationship",
                            source_object_id=item.source_object_id,
                            description=("The adapter does not support parent relationships."),
                        )
                    )
                continue

            accepted[source_object_id] = representative
            occurrence_indexes[source_object_id] = tuple(sorted(item.input_index for item in group))
            duplicate_count += len(group) - 1
        return accepted, duplicate_count

    def _source_type_supported(self, candidate: _Candidate) -> bool:
        if candidate.source_type == "conversation":
            return True
        if candidate.source_type == "attachment":
            return self.adapter.attachment_behavior != "unsupported"
        return candidate.source_type in self.adapter.supported_event_types

    def _quarantine_cycles_and_missing_dependencies(
        self,
        accepted: dict[str, _Candidate],
        *,
        import_batch_id: str,
        started_at: str,
        quarantined: list[QuarantinedSourceObject],
        losses: list[PortabilityLossRecord],
        mapping_counts: dict[str, int],
        material_object_indexes: set[int],
        occurrence_indexes: dict[str, tuple[int, ...]],
    ) -> None:
        cycle_ids = _cycle_source_ids(accepted)
        for source_object_id in sorted(cycle_ids):
            candidate = accepted.pop(source_object_id)
            indexes = occurrence_indexes.pop(source_object_id)
            for input_index in indexes:
                quarantined.append(
                    QuarantinedSourceObject(
                        input_index=input_index,
                        source_object_id=candidate.source_object_id,
                        source_hash=candidate.source_hash,
                        reason="cyclic-parent-relationship",
                    )
                )
                mapping_counts["malformed_or_quarantined"] += 1
                material_object_indexes.add(input_index)
                losses.append(
                    _make_loss(
                        import_batch_id,
                        input_index,
                        recorded_at=started_at,
                        category="cyclic-parent-relationship",
                        source_object_id=candidate.source_object_id,
                        description="The source parent graph contains a cycle.",
                    )
                )

        changed = True
        while changed:
            changed = False
            accepted_ids = set(accepted)
            missing = [
                candidate
                for candidate in accepted.values()
                if any(
                    parent_id not in accepted_ids
                    for parent_id in candidate.parent_source_object_ids
                )
            ]
            for candidate in sorted(missing, key=lambda item: item.source_object_id):
                accepted.pop(candidate.source_object_id)
                indexes = occurrence_indexes.pop(candidate.source_object_id)
                for input_index in indexes:
                    quarantined.append(
                        QuarantinedSourceObject(
                            input_index=input_index,
                            source_object_id=candidate.source_object_id,
                            source_hash=candidate.source_hash,
                            reason="missing-parent-dependency",
                        )
                    )
                    mapping_counts["missing_dependency"] += 1
                    material_object_indexes.add(input_index)
                    losses.append(
                        _make_loss(
                            import_batch_id,
                            input_index,
                            recorded_at=started_at,
                            category="missing-parent-dependency",
                            source_object_id=candidate.source_object_id,
                            description="A declared parent source object is unavailable.",
                        )
                    )
                changed = True


@dataclass(frozen=True, slots=True)
class _RawObject:
    input_index: int
    value: object | None
    source_hash: str
    parse_reason: str | None = None


@dataclass(frozen=True, slots=True)
class _Candidate:
    input_index: int
    source_object_id: str
    source_type: str
    parent_source_object_ids: tuple[str, ...]
    payload_json: str
    source_hash: str


class _ObjectProblem(Exception):
    def __init__(self, reason: str, source_object_id: str | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.source_object_id = source_object_id


class _JsonProblem(ValueError):
    pass


def _parse_json_envelope(source_text: str) -> tuple[dict[str, object], tuple[_RawObject, ...]]:
    value = _strict_json_loads(source_text, context="JSON source envelope")
    if not isinstance(value, dict):
        raise GenericImportStagingError("JSON source envelope must be an object")
    _require_exact_keys(value, _JSON_ENVELOPE_KEYS, "JSON source envelope")
    objects = value["objects"]
    if not isinstance(objects, list):
        raise GenericImportStagingError("JSON source objects must be a list")
    manifest = {
        "format": value["format"],
        "format_version": value["format_version"],
        "source_environment_id": value["source_environment_id"],
    }
    return manifest, tuple(
        _RawObject(
            input_index=index,
            value=item,
            source_hash=_hash_json_value(item),
        )
        for index, item in enumerate(objects)
    )


def _parse_jsonl_envelope(source_text: str) -> tuple[dict[str, object], tuple[_RawObject, ...]]:
    lines = source_text.splitlines()
    if not lines or not lines[0].strip():
        raise GenericImportStagingError("JSONL manifest line is missing")
    manifest_value = _strict_json_loads(lines[0], context="JSONL manifest")
    if not isinstance(manifest_value, dict):
        raise GenericImportStagingError("JSONL manifest must be an object")
    _require_exact_keys(manifest_value, _JSONL_MANIFEST_KEYS, "JSONL manifest")
    if manifest_value["record_kind"] != "manifest":
        raise GenericImportStagingError("JSONL first record must be a manifest")
    manifest = {
        "format": manifest_value["format"],
        "format_version": manifest_value["format_version"],
        "source_environment_id": manifest_value["source_environment_id"],
    }
    raw_objects: list[_RawObject] = []
    input_index = 0
    for line in lines[1:]:
        if not line.strip():
            continue
        line_hash = hashlib.sha256(line.encode("utf-8")).hexdigest()
        try:
            value = _strict_json_loads(line, context="JSONL object")
            if not isinstance(value, dict):
                raise _JsonProblem("JSONL object record must be an object")
            _require_exact_keys(value, _JSONL_OBJECT_KEYS, "JSONL object")
            if value["record_kind"] != "object":
                raise _JsonProblem("JSONL source record kind is invalid")
            value = {key: item for key, item in value.items() if key != "record_kind"}
            raw_objects.append(
                _RawObject(
                    input_index=input_index,
                    value=value,
                    source_hash=_hash_json_value(value),
                )
            )
        except (GenericImportStagingError, _JsonProblem):
            raw_objects.append(
                _RawObject(
                    input_index=input_index,
                    value=None,
                    source_hash=line_hash,
                    parse_reason="malformed-jsonl-object",
                )
            )
        input_index += 1
    return manifest, tuple(raw_objects)


def _validate_manifest(
    manifest: dict[str, object],
    *,
    source_environment: SourceEnvironmentRecord,
    adapter: SourceAdapterContract,
) -> str:
    if manifest["format"] != _FORMAT_NAME:
        raise GenericImportStagingError("generic source format name is invalid")
    format_version = manifest["format_version"]
    if not isinstance(format_version, str) or not format_version.strip():
        raise GenericImportStagingError("generic source format version is invalid")
    format_version = format_version.strip()
    if format_version not in adapter.supported_source_versions:
        raise GenericImportStagingError(
            "generic source format version is unsupported by the adapter"
        )
    if (
        source_environment.export_version is not None
        and source_environment.export_version != format_version
    ):
        raise GenericImportStagingError("source version does not match source environment")
    source_environment_id = manifest["source_environment_id"]
    if source_environment_id != source_environment.environment_id:
        raise GenericImportStagingError(
            "source environment identifier does not match staging context"
        )
    return format_version


def _parse_candidate(raw: _RawObject) -> _Candidate:
    value = raw.value
    if not isinstance(value, dict):
        raise _ObjectProblem("source-object-not-an-object")
    source_object_id = _extract_source_id(value)
    try:
        _require_exact_keys(value, _OBJECT_KEYS, "source object")
        source_type = _validate_identifier("source type", value["source_type"])
        parents = _validate_parent_ids(value["parent_source_object_ids"])
        if source_object_id in parents:
            raise _ObjectProblem("self-parent-relationship", source_object_id)
        payload = value["payload"]
        if not isinstance(payload, dict):
            raise _ObjectProblem("payload-not-an-object", source_object_id)
        payload_json = _canonical_json(payload)
        normalized = {
            "source_object_id": source_object_id,
            "source_type": source_type,
            "parent_source_object_ids": list(parents),
            "payload": payload,
        }
        return _Candidate(
            input_index=raw.input_index,
            source_object_id=source_object_id,
            source_type=source_type,
            parent_source_object_ids=parents,
            payload_json=payload_json,
            source_hash=_hash_json_value(normalized),
        )
    except GenericImportStagingError as exc:
        raise _ObjectProblem("malformed-source-object", source_object_id) from exc


def _extract_source_id(value: dict[str, object]) -> str:
    candidate = value.get("source_object_id")
    try:
        return _validate_source_id("source object id", candidate)
    except GenericImportStagingError as exc:
        raise _ObjectProblem("invalid-source-object-id") from exc


def _validate_parent_ids(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise GenericImportStagingError("parent source object identifiers must be a list")
    parents = tuple(_validate_source_id("parent source object id", item) for item in value)
    if len(parents) != len(set(parents)):
        raise GenericImportStagingError("parent source object identifiers contain duplicates")
    return tuple(sorted(parents))


def _strict_json_loads(source_text: str, *, context: str) -> object:
    try:
        return cast(
            object,
            json.loads(
                source_text,
                object_pairs_hook=_strict_object,
                parse_constant=_reject_json_constant,
            ),
        )
    except (json.JSONDecodeError, _JsonProblem, RecursionError, ValueError) as exc:
        raise GenericImportStagingError(f"{context} is invalid") from exc


def _strict_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _JsonProblem("JSON object contains duplicate keys")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> object:
    raise _JsonProblem(f"non-standard JSON constant: {value}")


def _require_exact_keys(
    value: dict[str, object],
    expected: frozenset[str],
    context: str,
) -> None:
    if frozenset(value) != expected:
        raise GenericImportStagingError(f"{context} fields are invalid")


def _validate_identifier(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise GenericImportStagingError(f"{name} must be text")
    normalized = value.strip().lower()
    if not normalized:
        raise GenericImportStagingError(f"{name} must not be blank")
    if len(normalized) > 128:
        raise GenericImportStagingError(f"{name} exceeds the maximum length")
    if not normalized[0].isalnum() or any(
        not (character.isalnum() or character in "._-") for character in normalized
    ):
        raise GenericImportStagingError(f"{name} is invalid")
    return normalized


def _validate_source_id(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise GenericImportStagingError(f"{name} must be text")
    normalized = value.strip()
    if not normalized:
        raise GenericImportStagingError(f"{name} must not be blank")
    if len(normalized) > _MAX_SOURCE_ID_LENGTH:
        raise GenericImportStagingError(f"{name} exceeds the maximum length")
    if any(ord(character) < 32 and character not in "\t\n\r" for character in normalized):
        raise GenericImportStagingError(f"{name} contains a control character")
    return normalized


def _canonical_json(value: object) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise GenericImportStagingError("source value is not canonical JSON") from exc


def _hash_json_value(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _json_depth(value: object) -> int:
    if isinstance(value, dict):
        return 1 + max((_json_depth(item) for item in value.values()), default=0)
    if isinstance(value, list):
        return 1 + max((_json_depth(item) for item in value), default=0)
    return 0


def _empty_mapping_counts() -> dict[str, int]:
    return {
        "mapped_without_known_loss": 0,
        "mapped_with_transformation": 0,
        "partially_mapped": 0,
        "unsupported_but_preserved": 0,
        "unsupported_and_omitted": 0,
        "missing_dependency": 0,
        "malformed_or_quarantined": 0,
        "unknown": 0,
    }


def _make_loss(
    import_batch_id: str,
    input_index: int,
    *,
    recorded_at: str,
    category: str,
    source_object_id: str | None,
    description: str,
) -> PortabilityLossRecord:
    loss_id = str(
        uuid5(
            UUID(import_batch_id),
            f"loss:{input_index}:{category}:{source_object_id or ''}",
        )
    )
    return PortabilityLossRecord(
        loss_record_id=loss_id,
        batch_id=import_batch_id,
        category=category,
        severity="material",
        description=description,
        preservation_state="preserved_metadata",
        future_recoverability="unknown",
        recorded_at=recorded_at,
        source_object_id=source_object_id,
        required_user_action="Review the original source before publication.",
    )


def _cycle_source_ids(accepted: dict[str, _Candidate]) -> set[str]:
    state: dict[str, int] = {}
    stack: list[str] = []
    positions: dict[str, int] = {}
    cycles: set[str] = set()

    def visit(source_object_id: str) -> None:
        state[source_object_id] = 1
        positions[source_object_id] = len(stack)
        stack.append(source_object_id)
        for parent_id in accepted[source_object_id].parent_source_object_ids:
            if parent_id not in accepted:
                continue
            parent_state = state.get(parent_id, 0)
            if parent_state == 0:
                visit(parent_id)
            elif parent_state == 1:
                cycles.update(stack[positions[parent_id] :])
        stack.pop()
        positions.pop(source_object_id)
        state[source_object_id] = 2

    for source_object_id in sorted(accepted):
        if state.get(source_object_id, 0) == 0:
            visit(source_object_id)
    return cycles


__all__ = [
    "GenericImportFormat",
    "GenericImportStageResult",
    "GenericImportStager",
    "GenericImportStagingError",
    "QuarantinedSourceObject",
    "StagedMappingStatus",
    "StagedSourceObject",
]
