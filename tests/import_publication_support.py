from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from uuid import uuid4

from doll import workspace
from doll.generic_import import GenericImportStager, GenericImportStageResult
from doll.portability import (
    AdapterResourceLimits,
    SourceAdapterContract,
    SourceEnvironmentRecord,
)

STARTED = "2026-06-24T09:00:00Z"
COMPLETED = "2026-06-24T09:00:01Z"


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


def _environment(environment_id: str | None = None) -> SourceEnvironmentRecord:
    return SourceEnvironmentRecord(
        environment_id=environment_id or str(uuid4()),
        environment_class="generic-file-export",
        provider_id="provider-a",
        application_id="application-a",
        interface_id="interface-a",
        runtime_id="runtime-a",
        export_format="json",
        export_version="1",
        observed_at=STARTED,
    )


def _object(
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


def _source(environment: SourceEnvironmentRecord, objects: list[object]) -> bytes:
    return json.dumps(
        {
            "format": "doll-generic-import",
            "format_version": "1",
            "source_environment_id": environment.environment_id,
            "objects": objects,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()


def _stage(
    environment: SourceEnvironmentRecord,
    source_bytes: bytes,
    *,
    batch_id: str | None = None,
) -> GenericImportStageResult:
    return GenericImportStager(_adapter(), environment).stage(
        source_bytes,
        source_format="json",
        import_batch_id=batch_id or str(uuid4()),
        started_at=STARTED,
    )


def _portable_objects(*, assistant_text: str = "world") -> list[object]:
    return [
        _object("conversation-1", "conversation", {"title": "Portable"}),
        _object(
            "message-1",
            "user-message",
            {"text": "hello", "sequence_hint": 1, "occurred_at": STARTED},
            parents=["conversation-1"],
        ),
        _object(
            "message-2",
            "assistant-message",
            {"text": assistant_text, "sequence_hint": 2},
            parents=["message-1"],
        ),
    ]


def _initialized(tmp_path: Path) -> workspace.InitializedWorkspace:
    return workspace.initialize_workspace(tmp_path / "workspace")


def _scalar(connection: sqlite3.Connection, query: str) -> int:
    row = connection.execute(query).fetchone()
    assert row is not None
    return int(row[0])


def _text_scalar(connection: sqlite3.Connection, query: str) -> str:
    row = connection.execute(query).fetchone()
    assert row is not None
    value = row[0]
    assert isinstance(value, str)
    return value
