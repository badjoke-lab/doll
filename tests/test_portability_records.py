from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from uuid import uuid4

import pytest

from doll.portability_records import (
    ExportBatchRecord,
    ImportBatchRecord,
    MappingReportRecord,
    PortabilityLossRecord,
)

SHA_A = "a" * 64
SHA_B = "b" * 64
STARTED = "2026-06-24T01:00:00Z"
COMPLETED = "2026-06-24T01:01:00Z"


def test_import_batch_records_staging_and_completed_publication() -> None:
    batch_id = str(uuid4())
    source_environment_id = str(uuid4())
    mapping_report_id = str(uuid4())

    staged = ImportBatchRecord(
        import_batch_id=batch_id,
        source_environment_id=source_environment_id,
        adapter_id="Generic-JSON",
        adapter_version="1.0.0",
        started_at=STARTED,
        status="staged",
        source_root_hash=SHA_A,
        staged_object_count=3,
        published_object_count=0,
        quarantined_object_count=1,
        mapping_report_id=mapping_report_id,
    )
    published = ImportBatchRecord(
        import_batch_id=str(uuid4()),
        source_environment_id=source_environment_id,
        adapter_id="generic-json",
        adapter_version="1.0.0",
        started_at=STARTED,
        completed_at=COMPLETED,
        status="published",
        source_root_hash=SHA_A,
        staged_object_count=3,
        published_object_count=3,
        quarantined_object_count=0,
        mapping_report_id=mapping_report_id,
    )

    assert staged.adapter_id == "generic-json"
    assert staged.completed_at is None
    assert staged.canonical_metadata()["source_environment_id"] == source_environment_id
    assert published.completed_at == COMPLETED
    assert published.canonical_metadata()["published_object_count"] == 3
    json.dumps(staged.canonical_metadata(), allow_nan=False)
    json.dumps(published.canonical_metadata(), allow_nan=False)


def test_mapping_report_exposes_every_accepted_status_and_material_loss() -> None:
    loss_ids = (str(uuid4()), str(uuid4()))
    report = MappingReportRecord(
        mapping_report_id=str(uuid4()),
        direction="import",
        batch_id=str(uuid4()),
        generated_at=COMPLETED,
        total_object_count=36,
        mapped_without_known_loss_count=8,
        mapped_with_transformation_count=7,
        partially_mapped_count=6,
        unsupported_but_preserved_count=5,
        unsupported_and_omitted_count=4,
        missing_dependency_count=3,
        malformed_or_quarantined_count=2,
        unknown_count=1,
        material_loss_count=2,
        loss_record_ids=tuple(reversed(loss_ids)),
    )

    assert report.mapping_counts == {
        "mapped_without_known_loss": 8,
        "mapped_with_transformation": 7,
        "partially_mapped": 6,
        "unsupported_but_preserved": 5,
        "unsupported_and_omitted": 4,
        "missing_dependency": 3,
        "malformed_or_quarantined": 2,
        "unknown": 1,
    }
    assert report.loss_record_ids == tuple(sorted(loss_ids))
    assert report.full_fidelity_possible is False
    metadata = report.canonical_metadata()
    assert metadata["material_loss_count"] == 2
    assert metadata["full_fidelity_possible"] is False
    json.dumps(metadata, allow_nan=False)


def test_mapping_report_without_material_loss_can_support_full_fidelity() -> None:
    report = MappingReportRecord(
        mapping_report_id=str(uuid4()),
        direction="export",
        batch_id=str(uuid4()),
        generated_at=COMPLETED,
        total_object_count=2,
        mapped_without_known_loss_count=2,
        mapped_with_transformation_count=0,
        partially_mapped_count=0,
        unsupported_but_preserved_count=0,
        unsupported_and_omitted_count=0,
        missing_dependency_count=0,
        malformed_or_quarantined_count=0,
        unknown_count=0,
    )

    assert report.full_fidelity_possible is True
    assert report.canonical_metadata()["loss_record_ids"] == []


def test_loss_record_preserves_source_reference_and_material_signal() -> None:
    loss = PortabilityLossRecord(
        loss_record_id=str(uuid4()),
        batch_id=str(uuid4()),
        category="Branch-Relationship",
        severity="material",
        description="  A source branch could not be represented exactly.  ",
        preservation_state="preserved_original",
        future_recoverability="recoverable",
        recorded_at=COMPLETED,
        source_object_id="  source/event/42  ",
        required_user_action="  Review the preserved source branch.  ",
    )

    assert loss.category == "branch-relationship"
    assert loss.description == "A source branch could not be represented exactly."
    assert loss.source_object_id == "source/event/42"
    assert loss.required_user_action == "Review the preserved source branch."
    assert loss.is_material is True
    assert loss.canonical_metadata()["is_material"] is True


def test_minor_loss_is_not_a_material_loss() -> None:
    loss = PortabilityLossRecord(
        loss_record_id=str(uuid4()),
        batch_id=str(uuid4()),
        category="formatting",
        severity="minor",
        description="Whitespace formatting changed.",
        preservation_state="preserved_metadata",
        future_recoverability="unknown",
        recorded_at=COMPLETED,
    )

    assert loss.is_material is False
    assert loss.source_object_id is None
    assert loss.required_user_action is None


def test_export_batch_sorts_selected_types_and_records_manifest() -> None:
    mapping_report_id = str(uuid4())
    export = ExportBatchRecord(
        export_batch_id=str(uuid4()),
        target_format="Generic-JSONL",
        target_adapter_id="generic-export",
        target_adapter_version="1.0.0",
        selected_record_types=("conversation-event", "conversation"),
        started_at=STARTED,
        completed_at=COMPLETED,
        status="completed",
        exported_object_count=4,
        manifest_hash=SHA_B,
        mapping_report_id=mapping_report_id,
    )

    assert export.target_format == "generic-jsonl"
    assert export.selected_record_types == ("conversation", "conversation-event")
    assert export.canonical_metadata()["manifest_hash"] == SHA_B
    json.dumps(export.canonical_metadata(), allow_nan=False)


def test_lossy_export_requires_and_records_loss_report() -> None:
    loss_report_id = str(uuid4())
    export = ExportBatchRecord(
        export_batch_id=str(uuid4()),
        target_format="markdown",
        target_adapter_id="markdown-export",
        target_adapter_version="1",
        selected_record_types=("conversation",),
        started_at=STARTED,
        completed_at=COMPLETED,
        status="completed_with_loss",
        exported_object_count=1,
        manifest_hash=SHA_A,
        loss_report_id=loss_report_id,
    )

    assert export.loss_report_id == loss_report_id
    assert export.canonical_metadata()["status"] == "completed_with_loss"


def test_contract_records_are_immutable() -> None:
    batch = ImportBatchRecord(
        import_batch_id=str(uuid4()),
        source_environment_id=str(uuid4()),
        adapter_id="generic-json",
        adapter_version="1",
        started_at=STARTED,
        status="awaiting_review",
        source_root_hash=SHA_A,
        staged_object_count=1,
        published_object_count=0,
        quarantined_object_count=0,
    )

    with pytest.raises(FrozenInstanceError):
        batch.status = "failed"  # type: ignore[misc]
