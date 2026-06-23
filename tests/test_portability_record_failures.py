from __future__ import annotations

from typing import Any, cast
from uuid import uuid4

import pytest

from doll.portability import PortabilityContractError
from doll.portability_records import (
    ExportBatchRecord,
    ImportBatchRecord,
    MappingReportRecord,
    PortabilityLossRecord,
)

SHA = "a" * 64
STARTED = "2026-06-24T01:00:00Z"
COMPLETED = "2026-06-24T01:01:00Z"


def _import_batch(**changes: object) -> ImportBatchRecord:
    values: dict[str, object] = {
        "import_batch_id": str(uuid4()),
        "source_environment_id": str(uuid4()),
        "adapter_id": "generic-json",
        "adapter_version": "1",
        "started_at": STARTED,
        "status": "staged",
        "source_root_hash": SHA,
        "staged_object_count": 2,
        "published_object_count": 0,
        "quarantined_object_count": 0,
    }
    values.update(changes)
    return ImportBatchRecord(**cast(dict[str, Any], values))


def _mapping_report(**changes: object) -> MappingReportRecord:
    values: dict[str, object] = {
        "mapping_report_id": str(uuid4()),
        "direction": "import",
        "batch_id": str(uuid4()),
        "generated_at": COMPLETED,
        "total_object_count": 1,
        "mapped_without_known_loss_count": 1,
        "mapped_with_transformation_count": 0,
        "partially_mapped_count": 0,
        "unsupported_but_preserved_count": 0,
        "unsupported_and_omitted_count": 0,
        "missing_dependency_count": 0,
        "malformed_or_quarantined_count": 0,
        "unknown_count": 0,
    }
    values.update(changes)
    return MappingReportRecord(**cast(dict[str, Any], values))


def _export_batch(**changes: object) -> ExportBatchRecord:
    values: dict[str, object] = {
        "export_batch_id": str(uuid4()),
        "target_format": "json",
        "target_adapter_id": "generic-export",
        "target_adapter_version": "1",
        "selected_record_types": ("conversation",),
        "started_at": STARTED,
        "status": "planned",
        "exported_object_count": 0,
    }
    values.update(changes)
    return ExportBatchRecord(**cast(dict[str, Any], values))


def test_import_batch_rejects_invalid_identity_version_hash_and_status() -> None:
    with pytest.raises(PortabilityContractError, match="import batch id is invalid"):
        _import_batch(import_batch_id="not-a-uuid")
    with pytest.raises(PortabilityContractError, match="canonical UUID text"):
        _import_batch(source_environment_id=str(uuid4()).upper())
    with pytest.raises(PortabilityContractError, match="adapter id is invalid"):
        _import_batch(adapter_id="Bad Adapter")
    with pytest.raises(PortabilityContractError, match="adapter version is invalid"):
        _import_batch(adapter_version="bad version")
    with pytest.raises(PortabilityContractError, match="lowercase SHA-256"):
        _import_batch(source_root_hash="A" * 64)
    with pytest.raises(PortabilityContractError, match="import status is invalid"):
        _import_batch(status="completed")


def test_import_batch_rejects_invalid_time_and_count_windows() -> None:
    with pytest.raises(PortabilityContractError, match="timezone-aware"):
        _import_batch(started_at="2026-06-24T01:00:00")
    with pytest.raises(PortabilityContractError, match="completion timestamp"):
        _import_batch(status="failed")
    with pytest.raises(PortabilityContractError, match="precedes start"):
        _import_batch(
            status="failed",
            completed_at="2026-06-24T00:59:59Z",
        )
    with pytest.raises(PortabilityContractError, match="non-negative bounded"):
        _import_batch(staged_object_count=-1)
    with pytest.raises(PortabilityContractError, match="non-negative bounded"):
        _import_batch(staged_object_count=cast(Any, True))
    with pytest.raises(PortabilityContractError, match="exceed staged"):
        _import_batch(quarantined_object_count=3)


def test_import_batch_rejects_status_count_inconsistency() -> None:
    with pytest.raises(PortabilityContractError, match="cannot retain published"):
        _import_batch(published_object_count=1)
    with pytest.raises(PortabilityContractError, match="published import counts"):
        _import_batch(
            status="published",
            completed_at=COMPLETED,
            published_object_count=1,
        )
    with pytest.raises(PortabilityContractError, match="partially published"):
        _import_batch(
            status="partially_published",
            completed_at=COMPLETED,
            published_object_count=0,
        )


def test_mapping_report_rejects_invalid_direction_counts_and_loss_links() -> None:
    with pytest.raises(PortabilityContractError, match="mapping direction"):
        _mapping_report(direction="copy")
    with pytest.raises(PortabilityContractError, match="do not match total"):
        _mapping_report(total_object_count=2)
    with pytest.raises(PortabilityContractError, match="material loss count exceeds"):
        _mapping_report(material_loss_count=2, loss_record_ids=(str(uuid4()),))
    with pytest.raises(PortabilityContractError, match="requires at least one"):
        _mapping_report(material_loss_count=1)
    loss_id = str(uuid4())
    with pytest.raises(PortabilityContractError, match="contains duplicates"):
        _mapping_report(loss_record_ids=(loss_id, loss_id))
    with pytest.raises(PortabilityContractError, match="must be a tuple"):
        _mapping_report(loss_record_ids=cast(Any, [loss_id]))


def test_loss_record_rejects_invalid_classification_and_text() -> None:
    common = {
        "loss_record_id": str(uuid4()),
        "batch_id": str(uuid4()),
        "category": "attachment",
        "severity": "minor",
        "description": "Attachment metadata changed.",
        "preservation_state": "preserved_metadata",
        "future_recoverability": "unknown",
        "recorded_at": COMPLETED,
    }
    with pytest.raises(PortabilityContractError, match="loss category is invalid"):
        PortabilityLossRecord(**cast(dict[str, Any], {**common, "category": "Bad Category"}))
    with pytest.raises(PortabilityContractError, match="loss severity"):
        PortabilityLossRecord(**cast(dict[str, Any], {**common, "severity": "major"}))
    with pytest.raises(PortabilityContractError, match="preservation state"):
        PortabilityLossRecord(**cast(dict[str, Any], {**common, "preservation_state": "deleted"}))
    with pytest.raises(PortabilityContractError, match="future recoverability"):
        PortabilityLossRecord(**cast(dict[str, Any], {**common, "future_recoverability": "maybe"}))
    with pytest.raises(PortabilityContractError, match="must not be blank"):
        PortabilityLossRecord(**cast(dict[str, Any], {**common, "description": "   "}))
    with pytest.raises(PortabilityContractError, match="control character"):
        PortabilityLossRecord(**cast(dict[str, Any], {**common, "description": "bad\x01text"}))


def test_export_batch_rejects_invalid_declarations() -> None:
    with pytest.raises(
        PortabilityContractError,
        match="selected record types must not be empty",
    ):
        _export_batch(selected_record_types=())
    with pytest.raises(PortabilityContractError, match="contains duplicates"):
        _export_batch(selected_record_types=("conversation", "conversation"))
    with pytest.raises(PortabilityContractError, match="must be a tuple"):
        _export_batch(selected_record_types=cast(Any, ["conversation"]))
    with pytest.raises(PortabilityContractError, match="target format is invalid"):
        _export_batch(target_format="Bad Format")
    with pytest.raises(
        PortabilityContractError,
        match="target adapter version is invalid",
    ):
        _export_batch(target_adapter_version="bad version")
    with pytest.raises(PortabilityContractError, match="export status is invalid"):
        _export_batch(status="published")


def test_export_batch_rejects_status_time_manifest_and_loss_inconsistency() -> None:
    with pytest.raises(PortabilityContractError, match="completion timestamp"):
        _export_batch(status="completed", manifest_hash=SHA)
    with pytest.raises(PortabilityContractError, match="requires a manifest hash"):
        _export_batch(status="completed", completed_at=COMPLETED)
    with pytest.raises(PortabilityContractError, match="cannot have a manifest hash"):
        _export_batch(manifest_hash=SHA)
    with pytest.raises(PortabilityContractError, match="cannot retain exported objects"):
        _export_batch(
            status="failed",
            completed_at=COMPLETED,
            exported_object_count=1,
        )
    with pytest.raises(PortabilityContractError, match="requires a loss report"):
        _export_batch(
            status="completed_with_loss",
            completed_at=COMPLETED,
            manifest_hash=SHA,
            exported_object_count=1,
        )
    with pytest.raises(PortabilityContractError, match="precedes start"):
        _export_batch(
            status="cancelled",
            completed_at="2026-06-24T00:59:59Z",
        )
