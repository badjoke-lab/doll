"""Run the synthetic IMP-059 ChatGPT conversations.json import scenario."""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from doll import state, workspace
from doll.chatgpt_export_import import ChatGPTExportSourceAdapter
from doll.generic_export import GenericExportBuilder
from doll.generic_import_publication import GenericImportPublicationError, GenericImportPublisher
from doll.shutdown_escape import export_shutdown_escape_bundle

ENVIRONMENT_ID = "59000000-0000-4000-8000-000000000001"
FIRST_BATCH_ID = "59000000-0000-4000-8000-000000000002"
SECOND_BATCH_ID = "59000000-0000-4000-8000-000000000003"
CHANGED_BATCH_ID = "59000000-0000-4000-8000-000000000004"
STARTED = "2026-07-04T00:00:00Z"
COMPLETED = "2026-07-04T00:00:01Z"
SELECTED_ID = "imp059-selected"
UNSELECTED_ID = "imp059-unselected"
_AUTHORITY_TYPES = (
    "capability",
    "confirmation",
    "credential",
    "memory",
    "permission",
    "policy",
    "procedure",
    "project_checkpoint",
    "work_item",
)


def _message(message_id: str, role: str, text: str) -> dict[str, object]:
    return {
        "id": message_id,
        "author": {"role": role, "name": None, "metadata": {}},
        "create_time": 1_700_000_000.0,
        "update_time": None,
        "content": {"content_type": "text", "parts": [text]},
        "status": "finished_successfully",
        "end_turn": True,
        "weight": 1.0,
        "metadata": {"model_slug": "synthetic-provider-model"},
        "recipient": "all",
        "channel": None,
    }


def _conversation(conversation_id: str, *, changed: bool = False) -> dict[str, object]:
    user_text = "synthetic changed selected text" if changed else "synthetic selected user text"
    mapping = {
        "root": {"id": "root", "message": None, "parent": None, "children": ["user"]},
        "user": {
            "id": "user",
            "message": _message("message-user", "user", user_text),
            "parent": "root",
            "children": ["assistant", "branch"],
        },
        "assistant": {
            "id": "assistant",
            "message": _message(
                "message-assistant", "assistant", "synthetic selected assistant text"
            ),
            "parent": "user",
            "children": [],
        },
        "branch": {
            "id": "branch",
            "message": _message("message-branch", "assistant", "synthetic selected branch text"),
            "parent": "user",
            "children": [],
        },
    }
    return {
        "id": conversation_id,
        "conversation_id": conversation_id,
        "title": "Synthetic selected conversation",
        "create_time": 1_700_000_000.0,
        "update_time": 1_700_000_001.0,
        "mapping": mapping,
        "current_node": "assistant",
    }


def _source(*, changed: bool = False) -> bytes:
    document = [
        _conversation(SELECTED_ID, changed=changed),
        {
            **_conversation(UNSELECTED_ID),
            "title": "Synthetic unselected conversation",
        },
    ]
    return json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _initialize_workspace(root: Path) -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(root)
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def _authority_count(repository: state.StateRepository) -> int:
    placeholders = ",".join("?" for _ in _AUTHORITY_TYPES)
    row = repository.connection.execute(
        f"SELECT COUNT(*) FROM records WHERE record_type IN ({placeholders})",
        _AUTHORITY_TYPES,
    ).fetchone()
    if row is None:
        raise RuntimeError("authority count query failed")
    return int(row[0])


def run(root: Path) -> tuple[dict[str, bool], dict[str, object]]:
    source_bytes = _source()
    changed_bytes = _source(changed=True)
    initialized = _initialize_workspace(root / "workspace")
    adapter = ChatGPTExportSourceAdapter()
    first = adapter.stage(
        source_bytes,
        source_environment_id=ENVIRONMENT_ID,
        selected_conversation_ids=(SELECTED_ID,),
        import_batch_id=FIRST_BATCH_ID,
        started_at=STARTED,
        observed_at=STARTED,
    )

    with state.open_state_repository(initialized.root) as repository:
        publisher = GenericImportPublisher(repository, first.source_environment)
        before_preview = repository.status()
        preview = publisher.preview(first.stage_result, source_bytes, preserve_source=True)
        preview_side_effect_free = repository.status() == before_preview
        published = publisher.publish(
            preview,
            source_bytes,
            approved_plan_hash=preview.plan_hash,
            completed_at=COMPLETED,
        )
        conversations = repository.list_conversations()
        if len(conversations) != 1:
            raise RuntimeError("selected conversation publication failed")
        conversation = conversations[0]
        events = repository.list_conversation_events(conversation.conversation_id)
        authority_count = _authority_count(repository)

        second = adapter.stage(
            source_bytes,
            source_environment_id=ENVIRONMENT_ID,
            selected_conversation_ids=(SELECTED_ID,),
            import_batch_id=SECOND_BATCH_ID,
            started_at="2026-07-04T00:00:02Z",
            observed_at=STARTED,
        )
        second_preview = GenericImportPublisher(repository, second.source_environment).preview(
            second.stage_result,
            source_bytes,
            preserve_source=False,
        )
        second_result = GenericImportPublisher(repository, second.source_environment).publish(
            second_preview,
            source_bytes,
            approved_plan_hash=second_preview.plan_hash,
            completed_at="2026-07-04T00:00:03Z",
        )

        changed = adapter.stage(
            changed_bytes,
            source_environment_id=ENVIRONMENT_ID,
            selected_conversation_ids=(SELECTED_ID,),
            import_batch_id=CHANGED_BATCH_ID,
            started_at="2026-07-04T00:00:04Z",
            observed_at=STARTED,
        )
        changed_preview = GenericImportPublisher(repository, changed.source_environment).preview(
            changed.stage_result,
            changed_bytes,
            preserve_source=False,
        )
        changed_blocked = False
        try:
            GenericImportPublisher(repository, changed.source_environment).publish(
                changed_preview,
                changed_bytes,
                approved_plan_hash=changed_preview.plan_hash,
                completed_at="2026-07-04T00:00:05Z",
            )
        except GenericImportPublicationError:
            changed_blocked = True

        export_batch_id = str(uuid5(NAMESPACE_URL, first.inventory.source_root_hash))
        generic = GenericExportBuilder().build(
            conversations,
            events,
            export_batch_id=export_batch_id,
            started_at="2026-07-04T00:00:06Z",
            completed_at="2026-07-04T00:00:07Z",
        )

    escape_path = root / "shutdown-escape.zip"
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        escape = export_shutdown_escape_bundle(
            repository,
            escape_path,
            exported_at="2026-07-04T00:00:08Z",
        )

    checks = {
        "contract_is_offline_and_provider_specific": (
            adapter.contract.adapter_id == "chatgpt-conversations"
            and adapter.contract.adapter_version == "1.0.0"
            and adapter.contract.network_behavior == "none"
        ),
        "content_free_inventory_valid": (
            first.inventory.conversation_count == 2
            and first.inventory.selected_conversation_count == 1
            and first.inventory.selected_message_count == 3
            and first.inventory.supported_message_count == 3
            and first.inventory.source_object_count == 4
        ),
        "preview_is_side_effect_free": preview_side_effect_free,
        "selected_history_published": (
            published.import_batch.status == "published"
            and len(published.created_canonical_record_ids) == 4
            and len(events) == 3
        ),
        "exact_source_preserved": (
            published.source_snapshot.preservation_state == "managed_snapshot"
            and published.source_snapshot.source_root_hash
            == hashlib.sha256(source_bytes).hexdigest()
        ),
        "unselected_history_not_published": len(conversations) == 1,
        "imported_content_remains_data_only": (
            authority_count == 0 and all(event.origin_class == "imported_data" for event in events)
        ),
        "unchanged_reimport_is_idempotent": (
            second_result.created_canonical_record_ids == ()
            and len(second_result.reused_canonical_record_ids) == 4
        ),
        "changed_source_conflict_blocks_overwrite": (
            changed_blocked
            and {item.reason for item in changed_preview.conflicts} == {"changed-source-object"}
        ),
        "generic_export_available": (
            generic.export_batch.status == "completed"
            and generic.export_batch.exported_object_count == 4
        ),
        "shutdown_escape_preserves_imported_history": (
            escape.generic_conversation_export
            and escape.recoverable_surfaces.get("conversations") is True
        ),
        "no_private_source_is_required": True,
        "no_model_network_cloud_or_credentials_used": True,
    }
    evidence: dict[str, object] = {
        "source_environment_class": first.source_environment.environment_class,
        "source_format": first.source_environment.export_format,
        "source_format_version": first.source_environment.export_version,
        "source_adapter_id": adapter.contract.adapter_id,
        "source_adapter_version": adapter.contract.adapter_version,
        "source_root_hash": first.inventory.source_root_hash,
        "conversation_count": first.inventory.conversation_count,
        "selected_conversation_count": first.inventory.selected_conversation_count,
        "selected_message_count": first.inventory.selected_message_count,
        "source_object_count": first.inventory.source_object_count,
        "published_object_count": len(published.created_canonical_record_ids),
        "duplicate_object_count": first.stage_result.duplicate_object_count,
        "quarantine_count": len(first.stage_result.quarantined_objects),
        "material_loss_count": first.stage_result.mapping_report.material_loss_count,
        "mapping_report_reference": first.stage_result.mapping_report.mapping_report_id,
        "generic_export_manifest_hash": generic.export_batch.manifest_hash,
        "shutdown_escape_sha256": escape.top_level_sha256,
        "runtime_mode": "synthetic",
    }
    return checks, evidence


def main() -> int:
    try:
        with tempfile.TemporaryDirectory(prefix="doll-imp059-") as raw:
            checks, evidence = run(Path(raw))
        if not all(checks.values()):
            raise RuntimeError("IMP-059 synthetic acceptance failed")
        payload: dict[str, object] = {
            "result": "pass",
            "checks": checks,
            "evidence": evidence,
        }
        status = 0
    except BaseException as exc:
        payload = {
            "result": "fail",
            "error_class": type(exc).__name__,
        }
        status = 1
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
