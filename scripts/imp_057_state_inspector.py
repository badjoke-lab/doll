"""Inspect IMP-057 imported state without the Ollama capture component."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, cast

from doll import state
from doll.generic_export import GenericExportBuilder
from doll.generic_import_publication import GenericImportPublicationState
from doll.state_repository import StateRepository

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


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace")
    parser.add_argument("descriptor")
    return parser.parse_args()


def _record_counts(repository: StateRepository) -> dict[str, int]:
    rows = repository.connection.execute(
        "SELECT record_type, COUNT(*) FROM records GROUP BY record_type ORDER BY record_type"
    ).fetchall()
    return {str(row[0]): int(row[1]) for row in rows}


def _authority_count(repository: StateRepository) -> int:
    placeholders = ",".join("?" for _ in _AUTHORITY_TYPES)
    row = repository.connection.execute(
        f"SELECT COUNT(*) FROM records WHERE record_type IN ({placeholders})",
        _AUTHORITY_TYPES,
    ).fetchone()
    if row is None:
        raise RuntimeError("authority count query failed")
    return int(row[0])


def _record_type_count(repository: StateRepository, record_type: str) -> int:
    row = repository.connection.execute(
        "SELECT COUNT(*) FROM records WHERE record_type = ?",
        (record_type,),
    ).fetchone()
    if row is None:
        raise RuntimeError("record count query failed")
    return int(row[0])


def inspect(
    workspace_root: Path,
    descriptor_path: Path,
) -> tuple[dict[str, bool], dict[str, int]]:
    descriptor: dict[str, Any] = json.loads(descriptor_path.read_text(encoding="utf-8"))
    expected_keys = {
        "conversation_id",
        "expected_event_count",
        "source_environment_id",
        "snapshot_record_id",
        "source_root_hash",
        "export_batch_id",
        "export_started_at",
        "export_completed_at",
        "generic_manifest_hash",
        "generic_export_prefix",
    }
    if set(descriptor) != expected_keys:
        raise RuntimeError("invalid local-portability descriptor")

    with state.open_state_repository(workspace_root, read_only=True) as repository:
        conversation_id = cast(str, descriptor["conversation_id"])
        conversation = repository.get_conversation(conversation_id)
        events = repository.list_conversation_events(conversation_id)
        snapshot = GenericImportPublicationState(repository).get_original_source(
            cast(str, descriptor["snapshot_record_id"])
        )
        bundle = GenericExportBuilder().build(
            (conversation,),
            events,
            export_batch_id=cast(str, descriptor["export_batch_id"]),
            started_at=cast(str, descriptor["export_started_at"]),
            completed_at=cast(str, descriptor["export_completed_at"]),
        )
        counts = _record_counts(repository)
        event_ids = {event.event_id for event in events}
        checks = {
            "schema_version_unchanged": repository.status().schema_version == 3,
            "canonical_conversation_retrieved": (
                conversation.source_environment_id == descriptor["source_environment_id"]
                and conversation.source_conversation_id == "conversation:imp057-conversation"
            ),
            "canonical_events_retrieved": (
                len(events) == descriptor["expected_event_count"]
                and len(events) == 2
                and all(event.origin_class == "imported_data" for event in events)
            ),
            "message_relationship_preserved": (
                events[0].parent_event_ids == ()
                and events[1].parent_event_ids == (events[0].event_id,)
                and set(events[1].parent_event_ids).issubset(event_ids)
            ),
            "source_provenance_preserved": all(
                event.source_environment_id == descriptor["source_environment_id"]
                and event.application_id == "ollama"
                and event.interface_id == "ollama.api"
                for event in events
            ),
            "managed_original_source_verified": (
                snapshot.preservation_state == "managed_snapshot"
                and snapshot.source_root_hash == descriptor["source_root_hash"]
                and snapshot.managed_path is not None
            ),
            "source_mapping_records_preserved": (
                _record_type_count(repository, "portability_source_mapping") == 3
            ),
            "generic_export_rebuilt_without_capture": (
                bundle.export_batch.manifest_hash == descriptor["generic_manifest_hash"]
                and bundle.export_batch.exported_object_count == 3
            ),
            "imported_content_has_no_authority_records": _authority_count(repository) == 0,
            "capture_component_not_required": True,
        }
    return checks, counts


def main() -> int:
    arguments = _arguments()
    try:
        checks, counts = inspect(Path(arguments.workspace), Path(arguments.descriptor))
        if not all(checks.values()):
            raise RuntimeError("local-portability state inspection failed")
        payload: dict[str, object] = {
            "result": "pass",
            "checks": checks,
            "counts": counts,
        }
    except BaseException as exc:
        payload = {"result": "fail", "error_class": type(exc).__name__}
        print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
        return 2
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
