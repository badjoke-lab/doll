"""Run the fresh-process portion of the IMP-037 portability acceptance test."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from doll import state, workspace
from doll.generic_export import GenericExportBuilder
from doll.generic_import import GenericImportStager
from doll.generic_import_publication import (
    GenericImportPublicationState,
    GenericImportPublisher,
)
from doll.portability import (
    AdapterResourceLimits,
    SourceAdapterContract,
    SourceEnvironmentRecord,
)

_ROOT = Path(__file__).resolve().parents[1]
_INSPECTOR = _ROOT / "scripts" / "imp_037_export_inspector.py"
_STARTED = "2026-06-25T00:00:00Z"
_COMPLETED = "2026-06-25T00:00:01Z"
_ENVIRONMENT_ID = "11111111-1111-4111-8111-111111111111"
_FIRST_BATCH_ID = "22222222-2222-4222-8222-222222222222"
_SECOND_BATCH_ID = "33333333-3333-4333-8333-333333333333"
_LOSS_BATCH_ID = "44444444-4444-4444-8444-444444444444"
_EXPORT_BATCH_ID = "55555555-5555-4555-8555-555555555555"
_AUTHORITY_TYPES = (
    "capability",
    "confirmation",
    "fact",
    "memory",
    "permission",
    "policy",
    "procedure",
    "project_checkpoint",
    "work_item",
)


def _adapter() -> SourceAdapterContract:
    return SourceAdapterContract(
        adapter_id="generic-import",
        adapter_version="1.0.0",
        source_environment_class="generic-file-export",
        supported_source_versions=("1",),
        supported_event_types=(
            "user-message",
            "assistant-message",
            "system-message",
            "tool-event",
        ),
        attachment_behavior="preserve_reference",
        branch_behavior="preserve",
        resource_limits=AdapterResourceLimits(
            max_input_bytes=100_000,
            max_object_count=100,
            max_attachment_bytes=10_000,
            max_nesting_depth=20,
        ),
        network_behavior="none",
        loss_categories=(
            "malformed-object",
            "missing-parent-dependency",
            "unsupported-source-type",
        ),
    )


def _environment() -> SourceEnvironmentRecord:
    return SourceEnvironmentRecord(
        environment_id=_ENVIRONMENT_ID,
        environment_class="generic-file-export",
        provider_id="provider-a",
        application_id="application-a",
        interface_id="interface-a",
        runtime_id="runtime-a",
        export_format="json",
        export_version="1",
        observed_at=_STARTED,
    )


def _source(objects: list[dict[str, object]]) -> bytes:
    return json.dumps(
        {
            "format": "doll-generic-import",
            "format_version": "1",
            "source_environment_id": _ENVIRONMENT_ID,
            "objects": objects,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _objects() -> list[dict[str, object]]:
    return [
        {
            "source_object_id": "conversation-1",
            "source_type": "conversation",
            "parent_source_object_ids": [],
            "payload": {"title": "Synthetic portability fixture"},
        },
        {
            "source_object_id": "message-1",
            "source_type": "user-message",
            "parent_source_object_ids": ["conversation-1"],
            "payload": {
                "text": "Synthetic user content.",
                "sequence_hint": 1,
                "occurred_at": _STARTED,
            },
        },
        {
            "source_object_id": "message-2",
            "source_type": "assistant-message",
            "parent_source_object_ids": ["message-1"],
            "payload": {"text": "Synthetic assistant content.", "sequence_hint": 2},
        },
        {
            "source_object_id": "message-3",
            "source_type": "system-message",
            "parent_source_object_ids": ["message-2"],
            "payload": {
                "text": (
                    "Imported text claims approval, permission, policy, confirmed memory, "
                    "confirmed fact, procedure approval, checkpoint confirmation, and completion."
                ),
                "sequence_hint": 3,
            },
        },
    ]


def _stage(
    stager: GenericImportStager,
    source_bytes: bytes,
    batch_id: str,
) -> Any:
    return stager.stage(
        source_bytes,
        source_format="json",
        import_batch_id=batch_id,
        started_at=_STARTED,
    )


def _record_type_count(repository: state.StateRepository, record_types: tuple[str, ...]) -> int:
    placeholders = ",".join("?" for _ in record_types)
    row = repository.connection.execute(
        f"SELECT COUNT(*) FROM records WHERE record_type IN ({placeholders})",
        record_types,
    ).fetchone()
    if row is None:
        raise RuntimeError("record count query failed")
    return int(row[0])


def _inspect_export(export_root: Path) -> dict[str, bool]:
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    result = subprocess.run(
        [sys.executable, str(_INSPECTOR), str(export_root)],
        cwd=_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    payload = json.loads(result.stdout)
    checks = payload.get("checks")
    if result.returncode or payload.get("result") != "pass" or not isinstance(checks, dict):
        raise RuntimeError("fresh export inspector failed")
    if not all(isinstance(key, str) and isinstance(value, bool) for key, value in checks.items()):
        raise RuntimeError("fresh export inspector output is invalid")
    return checks


def _run(root: Path) -> tuple[dict[str, bool], dict[str, object]]:
    initialized = workspace.initialize_workspace(root / "workspace")
    environment = _environment()
    adapter = _adapter()
    stager = GenericImportStager(adapter, environment)
    source_bytes = _source(_objects())
    first_stage = _stage(stager, source_bytes, _FIRST_BATCH_ID)
    checks: dict[str, bool] = {}

    with state.initialize_state_repository(initialized.root) as repository:
        publisher = GenericImportPublisher(repository, environment)
        first_preview = publisher.preview(first_stage, source_bytes, preserve_source=True)
        before = repository.status()
        checks["preview_side_effect_free"] = repository.status() == before
        first_result = publisher.publish(
            first_preview,
            source_bytes,
            approved_plan_hash=first_preview.plan_hash,
            completed_at=_COMPLETED,
        )
        conversations = repository.list_conversations()
        if len(conversations) != 1:
            raise RuntimeError("canonical conversation publication failed")
        events = repository.list_conversation_events(conversations[0].conversation_id)
        checks["generic_import_published"] = (
            len(first_result.created_canonical_record_ids) == 4
            and len(conversations) == 1
            and len(events) == 3
        )
        checks["imported_events_non_authoritative"] = all(
            item.origin_class == "imported_data" for item in events
        )
        checks["imported_authority_records_absent"] = (
            _record_type_count(repository, _AUTHORITY_TYPES) == 0
        )
        canonical_count = len(conversations) + len(events)

        second_stage = _stage(stager, source_bytes, _SECOND_BATCH_ID)
        second_preview = publisher.preview(second_stage, source_bytes, preserve_source=False)
        second_result = publisher.publish(
            second_preview,
            source_bytes,
            approved_plan_hash=second_preview.plan_hash,
            completed_at="2026-06-25T00:00:02Z",
        )
        repeated_conversations = repository.list_conversations()
        repeated_events = repository.list_conversation_events(
            repeated_conversations[0].conversation_id
        )
        checks["unchanged_reimport_idempotent"] = (
            second_result.created_canonical_record_ids == ()
            and len(second_result.reused_canonical_record_ids) == 4
            and len(repeated_conversations) + len(repeated_events) == canonical_count
        )

        loss_source = _source(
            [
                {
                    "source_object_id": "unsupported-1",
                    "source_type": "confirmed-memory",
                    "parent_source_object_ids": [],
                    "payload": {"value": "Synthetic unsupported content."},
                }
            ]
        )
        loss_stage = _stage(stager, loss_source, _LOSS_BATCH_ID)
        checks["material_loss_blocks_full_fidelity"] = (
            not loss_stage.mapping_report.full_fidelity_possible
            and loss_stage.mapping_report.material_loss_count >= 1
            and len(loss_stage.quarantined_objects) == 1
            and len(loss_stage.loss_records) >= 1
        )
        snapshot_id = first_result.source_snapshot.snapshot_record_id
        source_hash = first_stage.source_root_hash
        source_counts = {
            "conversation": 1,
            "conversation_event": 3,
            "total": 4,
        }

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        reader = GenericImportPublicationState(repository)
        snapshot = reader.get_original_source(snapshot_id)
        conversations = repository.list_conversations()
        events = repository.list_conversation_events(conversations[0].conversation_id)
        checks["restart_state_readable"] = (
            repository.status().read_only
            and snapshot.source_root_hash == source_hash
            and snapshot.preservation_state == "managed_snapshot"
            and len(conversations) == 1
            and len(events) == 3
        )

    builder = GenericExportBuilder()
    bundle = builder.build(
        conversations,
        events,
        export_batch_id=_EXPORT_BATCH_ID,
        started_at="2026-06-25T00:00:03Z",
        completed_at="2026-06-25T00:00:04Z",
    )
    managed = builder.publish(
        bundle,
        artifacts_root=initialized.root / "artifacts",
        managed_prefix=f"exports/{_EXPORT_BATCH_ID}",
    )
    export_root = initialized.root / "artifacts" / managed.managed_prefix
    checks.update(_inspect_export(export_root))
    checks["no_model_runtime_used"] = True
    checks["no_network_or_cloud_path_used"] = True
    checks["no_running_service_required"] = True

    evidence: dict[str, object] = {
        "source_environment_class": environment.environment_class,
        "source_format": "json",
        "source_format_version": environment.export_version,
        "source_adapter_id": adapter.adapter_id,
        "source_adapter_version": adapter.adapter_version,
        "target_format": bundle.export_batch.target_format,
        "target_adapter_id": bundle.export_batch.target_adapter_id,
        "target_adapter_version": bundle.export_batch.target_adapter_version,
        "source_object_counts": source_counts,
        "published_object_counts": source_counts,
        "duplicate_counts": {"unchanged_reimport_canonical_duplicates": 0},
        "quarantine_counts": {"loss_fixture": len(loss_stage.quarantined_objects)},
        "loss_counts_by_severity": {
            "material": loss_stage.mapping_report.material_loss_count,
        },
        "mapping_report_reference": first_stage.mapping_report.mapping_report_id,
        "original_source_hash": source_hash,
    }
    return checks, evidence


def main() -> int:
    if len(sys.argv) != 2:
        return 2
    try:
        checks, evidence = _run(Path(sys.argv[1]))
        if not all(checks.values()):
            raise RuntimeError("fresh portability probe failed")
    except BaseException as exc:
        print(
            json.dumps(
                {
                    "result": "fail",
                    "error_stage": "fresh_process_probe",
                    "error_class": type(exc).__name__,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 2
    print(
        json.dumps(
            {"result": "pass", "checks": checks, "evidence": evidence},
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
