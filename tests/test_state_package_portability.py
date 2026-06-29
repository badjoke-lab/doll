from __future__ import annotations

from dataclasses import replace

import pytest

from doll import state
from doll.generic_import_publication import (
    ImportQuarantineRecord,
    OriginalSourceSnapshotRecord,
    SourceObjectMappingRecord,
)
from doll.portability import SourceEnvironmentRecord
from doll.portability_records import (
    ImportBatchRecord,
    MappingReportRecord,
    PortabilityLossRecord,
)
from doll.state_package_portability import (
    PortabilityPackageCorruptError,
    import_batch_from_record,
    managed_source_from_record,
    mapping_report_from_record,
    original_source_from_record,
    portability_loss_from_record,
    quarantine_from_record,
    source_environment_from_record,
    source_mapping_from_record,
    validate_portability_package_graph,
)

_ENVIRONMENT_ID = "11111111-1111-4111-8111-111111111111"
_BATCH_ID = "22222222-2222-4222-8222-222222222222"
_REPORT_ID = "33333333-3333-4333-8333-333333333333"
_LOSS_ID = "44444444-4444-4444-8444-444444444444"
_MAPPING_ID = "55555555-5555-4555-8555-555555555555"
_QUARANTINE_ID = "66666666-6666-4666-8666-666666666666"
_SNAPSHOT_ID = "77777777-7777-4777-8777-777777777777"
_CANONICAL_ID = "88888888-8888-4888-8888-888888888888"
_TIMESTAMP = "2026-06-29T00:00:00Z"
_COMPLETED_AT = "2026-06-29T00:00:01Z"
_HASH = "a" * 64


def _envelope(
    record_id: str,
    record_type: str,
    metadata: dict[str, object],
    *,
    schema_version: int = 1,
) -> state.RecordEnvelope:
    return state.RecordEnvelope(
        id=record_id,
        record_type=record_type,
        schema_version=schema_version,
        created_at=_TIMESTAMP,
        updated_at=_TIMESTAMP,
        revision=1,
        status="active",
        provenance="imported",
        sensitivity="internal",
        title=None,
        metadata=metadata,
    )


def _source_environment() -> SourceEnvironmentRecord:
    return SourceEnvironmentRecord(
        environment_id=_ENVIRONMENT_ID,
        environment_class="local_runtime",
        application_id="ollama",
        interface_id="ollama.api",
        runtime_id="ollama",
        export_format="ollama_api_chat_session",
        export_version="1.0.0",
        observed_at=_TIMESTAMP,
    )


def _import_batch(*, mapping_report_id: str | None = _REPORT_ID) -> ImportBatchRecord:
    return ImportBatchRecord(
        import_batch_id=_BATCH_ID,
        source_environment_id=_ENVIRONMENT_ID,
        adapter_id="ollama-api-session",
        adapter_version="1.0.0",
        started_at=_TIMESTAMP,
        completed_at=_COMPLETED_AT,
        status="published",
        source_root_hash=_HASH,
        staged_object_count=1,
        published_object_count=1,
        quarantined_object_count=0,
        mapping_report_id=mapping_report_id,
    )


def _mapping_report(
    *,
    material_loss_count: int = 0,
    loss_record_ids: tuple[str, ...] = (),
) -> MappingReportRecord:
    return MappingReportRecord(
        mapping_report_id=_REPORT_ID,
        direction="import",
        batch_id=_BATCH_ID,
        generated_at=_COMPLETED_AT,
        total_object_count=1,
        mapped_without_known_loss_count=1,
        mapped_with_transformation_count=0,
        partially_mapped_count=0,
        unsupported_but_preserved_count=0,
        unsupported_and_omitted_count=0,
        missing_dependency_count=0,
        malformed_or_quarantined_count=0,
        unknown_count=0,
        material_loss_count=material_loss_count,
        loss_record_ids=loss_record_ids,
    )


def _loss() -> PortabilityLossRecord:
    return PortabilityLossRecord(
        loss_record_id=_LOSS_ID,
        batch_id=_BATCH_ID,
        category="metadata_loss",
        severity="material",
        description="Synthetic portability loss.",
        preservation_state="preserved_metadata",
        future_recoverability="recoverable",
        recorded_at=_COMPLETED_AT,
    )


def _source_mapping() -> SourceObjectMappingRecord:
    return SourceObjectMappingRecord(
        mapping_id=_MAPPING_ID,
        source_environment_id=_ENVIRONMENT_ID,
        adapter_id="ollama-api-session",
        adapter_version="1.0.0",
        source_object_id="conversation:synthetic",
        source_type="conversation",
        source_hash=_HASH,
        payload_json="{}",
        canonical_record_id=_CANONICAL_ID,
        canonical_record_type="conversation",
        first_import_batch_id=_BATCH_ID,
    )


def _quarantine() -> ImportQuarantineRecord:
    return ImportQuarantineRecord(
        quarantine_id=_QUARANTINE_ID,
        import_batch_id=_BATCH_ID,
        input_index=0,
        source_object_id="conversation:quarantined",
        source_hash=_HASH,
        reason="synthetic-invalid-object",
    )


def _snapshot(*, managed: bool = False) -> OriginalSourceSnapshotRecord:
    return OriginalSourceSnapshotRecord(
        snapshot_record_id=_SNAPSHOT_ID,
        import_batch_id=_BATCH_ID,
        source_root_hash=_HASH,
        source_format="json",
        preservation_state="managed_snapshot" if managed else "hash_only",
        managed_path="imports/source.json" if managed else None,
        size_bytes=10,
    )


def _record_set() -> dict[str, state.RecordEnvelope]:
    environment = _source_environment()
    batch = _import_batch()
    report = _mapping_report()
    mapping = _source_mapping()
    quarantine = _quarantine()
    snapshot = _snapshot()
    canonical = _envelope(_CANONICAL_ID, "conversation", {})
    records = (
        _envelope(environment.environment_id, "source_environment", environment.canonical_metadata()),
        _envelope(batch.import_batch_id, "portability_import_batch", batch.canonical_metadata()),
        _envelope(
            report.mapping_report_id,
            "portability_mapping_report",
            report.canonical_metadata(),
        ),
        _envelope(mapping.mapping_id, "portability_source_mapping", mapping.canonical_metadata()),
        _envelope(
            quarantine.quarantine_id,
            "portability_quarantine",
            quarantine.canonical_metadata(),
        ),
        _envelope(
            snapshot.snapshot_record_id,
            "portability_original_source",
            snapshot.canonical_metadata(),
        ),
        canonical,
    )
    return {record.id: record for record in records}


def test_portability_record_decoders_round_trip() -> None:
    environment = _source_environment()
    batch = _import_batch()
    report = _mapping_report()
    loss = _loss()
    mapping = _source_mapping()
    quarantine = _quarantine()
    snapshot = _snapshot()

    assert source_environment_from_record(
        _envelope(environment.environment_id, "source_environment", environment.canonical_metadata())
    ) == environment
    assert import_batch_from_record(
        _envelope(batch.import_batch_id, "portability_import_batch", batch.canonical_metadata())
    ) == batch
    assert mapping_report_from_record(
        _envelope(
            report.mapping_report_id,
            "portability_mapping_report",
            report.canonical_metadata(),
        )
    ) == report
    assert portability_loss_from_record(
        _envelope(loss.loss_record_id, "portability_loss", loss.canonical_metadata())
    ) == loss
    assert source_mapping_from_record(
        _envelope(mapping.mapping_id, "portability_source_mapping", mapping.canonical_metadata())
    ) == mapping
    assert quarantine_from_record(
        _envelope(
            quarantine.quarantine_id,
            "portability_quarantine",
            quarantine.canonical_metadata(),
        )
    ) == quarantine
    assert original_source_from_record(
        _envelope(
            snapshot.snapshot_record_id,
            "portability_original_source",
            snapshot.canonical_metadata(),
        )
    ) == snapshot


def test_managed_source_projection_and_hash_only_omission() -> None:
    managed = _snapshot(managed=True)
    managed_record = _envelope(
        managed.snapshot_record_id,
        "portability_original_source",
        managed.canonical_metadata(),
    )
    projected = managed_source_from_record(managed_record)

    assert projected is not None
    assert projected.managed_path == "imports/source.json"
    assert projected.size_bytes == 10
    assert projected.content_hash == f"sha256:{_HASH}"

    hash_only = _snapshot()
    assert (
        managed_source_from_record(
            _envelope(
                hash_only.snapshot_record_id,
                "portability_original_source",
                hash_only.canonical_metadata(),
            )
        )
        is None
    )


def test_portability_decoders_fail_closed_on_invalid_shapes() -> None:
    environment = _source_environment()
    valid = _envelope(
        environment.environment_id,
        "source_environment",
        environment.canonical_metadata(),
    )
    with pytest.raises(PortabilityPackageCorruptError):
        source_environment_from_record(replace(valid, record_type="preference"))
    with pytest.raises(PortabilityPackageCorruptError):
        source_environment_from_record(replace(valid, schema_version=2))
    with pytest.raises(PortabilityPackageCorruptError):
        source_environment_from_record(replace(valid, metadata={}))

    invalid_environment = dict(environment.canonical_metadata())
    invalid_environment["environment_class"] = "Invalid Class"
    with pytest.raises(PortabilityPackageCorruptError):
        source_environment_from_record(replace(valid, metadata=invalid_environment))

    batch = _import_batch()
    invalid_batch = dict(batch.canonical_metadata())
    invalid_batch["status"] = "invalid-status"
    with pytest.raises(PortabilityPackageCorruptError):
        import_batch_from_record(
            _envelope(batch.import_batch_id, "portability_import_batch", invalid_batch)
        )

    report = _mapping_report()
    invalid_counts = dict(report.canonical_metadata())
    invalid_counts["mapping_counts"] = []
    with pytest.raises(PortabilityPackageCorruptError):
        mapping_report_from_record(
            _envelope(report.mapping_report_id, "portability_mapping_report", invalid_counts)
        )

    missing_count = dict(report.canonical_metadata())
    missing_count["mapping_counts"] = {}
    with pytest.raises(PortabilityPackageCorruptError):
        mapping_report_from_record(
            _envelope(report.mapping_report_id, "portability_mapping_report", missing_count)
        )

    wrong_fidelity = dict(report.canonical_metadata())
    wrong_fidelity["full_fidelity_possible"] = False
    with pytest.raises(PortabilityPackageCorruptError):
        mapping_report_from_record(
            _envelope(report.mapping_report_id, "portability_mapping_report", wrong_fidelity)
        )

    loss = _loss()
    wrong_materiality = dict(loss.canonical_metadata())
    wrong_materiality["is_material"] = False
    with pytest.raises(PortabilityPackageCorruptError):
        portability_loss_from_record(
            _envelope(loss.loss_record_id, "portability_loss", wrong_materiality)
        )

    mapping = _source_mapping()
    invalid_mapping = dict(mapping.canonical_metadata())
    invalid_mapping["authority_class"] = "authority"
    with pytest.raises(PortabilityPackageCorruptError):
        source_mapping_from_record(
            _envelope(mapping.mapping_id, "portability_source_mapping", invalid_mapping)
        )

    quarantine = _quarantine()
    invalid_quarantine = dict(quarantine.canonical_metadata())
    invalid_quarantine["input_index"] = -1
    with pytest.raises(PortabilityPackageCorruptError):
        quarantine_from_record(
            _envelope(
                quarantine.quarantine_id,
                "portability_quarantine",
                invalid_quarantine,
            )
        )

    snapshot = _snapshot()
    invalid_snapshot = dict(snapshot.canonical_metadata())
    invalid_snapshot["authority_class"] = "authority"
    with pytest.raises(PortabilityPackageCorruptError):
        original_source_from_record(
            _envelope(
                snapshot.snapshot_record_id,
                "portability_original_source",
                invalid_snapshot,
            )
        )


def test_portability_graph_validation_accepts_complete_graph() -> None:
    validate_portability_package_graph(_record_set())


def test_portability_graph_validation_rejects_missing_links() -> None:
    records = _record_set()
    records.pop(_ENVIRONMENT_ID)
    with pytest.raises(PortabilityPackageCorruptError, match="source environment"):
        validate_portability_package_graph(records)

    records = _record_set()
    records.pop(_REPORT_ID)
    with pytest.raises(PortabilityPackageCorruptError, match="mapping report"):
        validate_portability_package_graph(records)

    material_report = _mapping_report(material_loss_count=1, loss_record_ids=(_LOSS_ID,))
    records = _record_set()
    records[_REPORT_ID] = _envelope(
        _REPORT_ID,
        "portability_mapping_report",
        material_report.canonical_metadata(),
    )
    with pytest.raises(PortabilityPackageCorruptError, match="loss link"):
        validate_portability_package_graph(records)

    loss = _loss()
    records = {
        _LOSS_ID: _envelope(_LOSS_ID, "portability_loss", loss.canonical_metadata())
    }
    with pytest.raises(PortabilityPackageCorruptError, match="loss batch"):
        validate_portability_package_graph(records)

    records = _record_set()
    records.pop(_BATCH_ID)
    records.pop(_REPORT_ID)
    with pytest.raises(PortabilityPackageCorruptError, match="import batch"):
        validate_portability_package_graph(records)

    records = _record_set()
    records[_CANONICAL_ID] = _envelope(_CANONICAL_ID, "decision", {})
    with pytest.raises(PortabilityPackageCorruptError, match="canonical record"):
        validate_portability_package_graph(records)


def test_portability_graph_validation_rejects_quarantine_and_snapshot_orphans() -> None:
    quarantine = _quarantine()
    records = {
        _QUARANTINE_ID: _envelope(
            _QUARANTINE_ID,
            "portability_quarantine",
            quarantine.canonical_metadata(),
        )
    }
    with pytest.raises(PortabilityPackageCorruptError, match="quarantine import batch"):
        validate_portability_package_graph(records)

    snapshot = _snapshot()
    records = {
        _SNAPSHOT_ID: _envelope(
            _SNAPSHOT_ID,
            "portability_original_source",
            snapshot.canonical_metadata(),
        )
    }
    with pytest.raises(PortabilityPackageCorruptError, match="original source import batch"):
        validate_portability_package_graph(records)
