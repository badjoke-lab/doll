from __future__ import annotations

import json
from uuid import uuid4

from doll.generic_import import GenericImportStager
from doll.portability import (
    AdapterResourceLimits,
    SourceAdapterContract,
    SourceEnvironmentRecord,
)

STARTED = "2026-06-24T03:00:00Z"


def _adapter(
    *,
    branch_behavior: str = "preserve",
    attachment_behavior: str = "preserve_reference",
    max_input_bytes: int = 100_000,
    max_object_count: int = 100,
    max_attachment_bytes: int = 10_000,
    max_nesting_depth: int = 20,
) -> SourceAdapterContract:
    return SourceAdapterContract(
        adapter_id="generic-import",
        adapter_version="1.0.0",
        source_environment_class="generic-file-export",
        supported_source_versions=("1",),
        supported_event_types=("user-message", "assistant-message", "tool-event"),
        attachment_behavior=attachment_behavior,  # type: ignore[arg-type]
        branch_behavior=branch_behavior,  # type: ignore[arg-type]
        resource_limits=AdapterResourceLimits(
            max_input_bytes=max_input_bytes,
            max_object_count=max_object_count,
            max_attachment_bytes=max_attachment_bytes,
            max_nesting_depth=max_nesting_depth,
        ),
        network_behavior="none",
        loss_categories=(
            "attachment-metadata-only",
            "branch-linearization",
            "conflicting-duplicate",
            "cyclic-parent-relationship",
            "malformed-object",
            "missing-parent-dependency",
            "unsupported-source-type",
        ),
    )


def _environment(
    environment_id: str,
    *,
    export_format: str | None = None,
    export_version: str | None = "1",
) -> SourceEnvironmentRecord:
    return SourceEnvironmentRecord(
        environment_id=environment_id,
        environment_class="generic-file-export",
        export_format=export_format,
        export_version=export_version,
    )


def _source_object(
    source_object_id: str,
    source_type: str,
    payload: dict[str, object],
    *,
    parents: list[str] | None = None,
) -> dict[str, object]:
    return {
        "source_object_id": source_object_id,
        "source_type": source_type,
        "parent_source_object_ids": parents or [],
        "payload": payload,
    }


def _json_bytes(
    environment_id: str,
    objects: list[object],
    *,
    version: str = "1",
) -> bytes:
    return json.dumps(
        {
            "format": "doll-generic-import",
            "format_version": version,
            "source_environment_id": environment_id,
            "objects": objects,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()


def _jsonl_bytes(
    environment_id: str,
    objects: list[dict[str, object]],
    *,
    version: str = "1",
) -> bytes:
    manifest = {
        "record_kind": "manifest",
        "format": "doll-generic-import",
        "format_version": version,
        "source_environment_id": environment_id,
    }
    lines = [json.dumps(manifest, separators=(",", ":"))]
    for item in objects:
        lines.append(
            json.dumps(
                {"record_kind": "object", **item},
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
    return ("\n".join(lines) + "\n").encode()


def test_json_and_jsonl_stage_the_same_generic_object_model() -> None:
    environment_id = str(uuid4())
    batch_id = str(uuid4())
    objects = [
        _source_object("conversation-1", "conversation", {"title": "Portable"}),
        _source_object(
            "message-1",
            "user-message",
            {"text": "hello"},
            parents=["conversation-1"],
        ),
        _source_object(
            "message-2",
            "assistant-message",
            {"text": "world"},
            parents=["message-1"],
        ),
    ]
    stager = GenericImportStager(_adapter(), _environment(environment_id))

    json_result = stager.stage(
        _json_bytes(environment_id, objects),
        source_format="json",
        import_batch_id=batch_id,
        started_at=STARTED,
    )
    jsonl_result = stager.stage(
        _jsonl_bytes(environment_id, objects),
        source_format="jsonl",
        import_batch_id=batch_id,
        started_at=STARTED,
    )

    assert [item.source_object_id for item in json_result.staged_objects] == [
        "conversation-1",
        "message-1",
        "message-2",
    ]
    assert [item.source_hash for item in json_result.staged_objects] == [
        item.source_hash for item in jsonl_result.staged_objects
    ]
    assert json_result.mapping_report.mapping_counts == (jsonl_result.mapping_report.mapping_counts)
    assert json_result.mapping_report.mapped_without_known_loss_count == 3
    assert json_result.mapping_report.full_fidelity_possible is True
    assert json_result.import_batch.staged_object_count == 3
    assert json_result.import_batch.quarantined_object_count == 0
    assert json_result.loss_records == ()
    assert all(item.authority_class == "external_data" for item in json_result.staged_objects)
    json.dumps(json_result.canonical_summary(), allow_nan=False)


def test_identical_duplicate_objects_are_deduplicated_deterministically() -> None:
    environment_id = str(uuid4())
    source = _source_object("message-1", "user-message", {"text": "same"})
    result = GenericImportStager(
        _adapter(),
        _environment(environment_id, export_format="json"),
    ).stage(
        _json_bytes(environment_id, [source, source]),
        source_format="json",
        import_batch_id=str(uuid4()),
        started_at=STARTED,
    )

    assert len(result.staged_objects) == 1
    assert result.duplicate_object_count == 1
    assert result.mapping_report.total_object_count == 2
    assert result.mapping_report.mapped_without_known_loss_count == 2
    assert result.quarantined_objects == ()


def test_branch_linearization_and_attachment_metadata_are_explicit_losses() -> None:
    environment_id = str(uuid4())
    objects = [
        _source_object("conversation-1", "conversation", {}),
        _source_object(
            "message-1",
            "assistant-message",
            {"text": "branch"},
            parents=["conversation-1"],
        ),
        _source_object("attachment-1", "attachment", {"name": "file.bin"}),
    ]
    result = GenericImportStager(
        _adapter(
            branch_behavior="linearize_with_loss",
            attachment_behavior="metadata_only",
        ),
        _environment(environment_id),
    ).stage(
        _json_bytes(environment_id, objects),
        source_format="json",
        import_batch_id=str(uuid4()),
        started_at=STARTED,
    )

    statuses = {item.source_object_id: item.mapping_status for item in result.staged_objects}
    assert statuses == {
        "attachment-1": "mapped_with_transformation",
        "conversation-1": "mapped_without_known_loss",
        "message-1": "mapped_with_transformation",
    }
    assert result.mapping_report.mapped_without_known_loss_count == 1
    assert result.mapping_report.mapped_with_transformation_count == 2
    assert result.mapping_report.material_loss_count == 2
    assert result.mapping_report.full_fidelity_possible is False
    assert {item.category for item in result.loss_records} == {
        "attachment-metadata-only",
        "branch-linearization",
    }
    assert {item.recorded_at for item in result.loss_records} == {STARTED}


def test_result_is_deterministic_for_same_context_and_bytes() -> None:
    environment_id = str(uuid4())
    batch_id = str(uuid4())
    source_bytes = _json_bytes(
        environment_id,
        [_source_object("message-1", "user-message", {"value": [1, 2, 3]})],
    )
    stager = GenericImportStager(_adapter(), _environment(environment_id))

    first = stager.stage(
        source_bytes,
        source_format="json",
        import_batch_id=batch_id,
        started_at=STARTED,
    )
    second = stager.stage(
        source_bytes,
        source_format="json",
        import_batch_id=batch_id,
        started_at=STARTED,
    )

    assert first == second
    assert first.source_root_hash == second.source_root_hash
    assert first.adapter_fingerprint == second.adapter_fingerprint
    assert first.mapping_report.mapping_report_id == second.mapping_report.mapping_report_id
    assert not hasattr(first, "publish")
    assert not hasattr(stager, "execute")
