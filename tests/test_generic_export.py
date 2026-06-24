from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID, uuid5

from doll.state import ConversationEventRecord, ConversationRecord
from doll.workspace import initialize_workspace

from doll.generic_export import (
    GenericExportBuilder,
    GenericExportBundle,
    verify_generic_export_bundle,
)

STARTED = "2026-06-24T03:00:00Z"
COMPLETED = "2026-06-24T03:00:01Z"
NAMESPACE = UUID("fdd75a56-875f-4f05-9364-6f149a6fd938")


def _id(name: str) -> str:
    return str(uuid5(NAMESPACE, name))


def _conversation(name: str, *, title: str | None = None) -> ConversationRecord:
    return ConversationRecord(
        conversation_id=_id(f"conversation:{name}"),
        title=title,
        source_environment_id=_id("source-environment"),
        source_conversation_id=f"source-{name}",
    )


def _event(
    name: str,
    conversation: ConversationRecord,
    *,
    kind: str = "user_message",
    actor: str = "user",
    origin: str = "imported_data",
    parents: tuple[str, ...] = (),
    sequence_hint: int | None = None,
    extensions: dict[str, object] | None = None,
) -> ConversationEventRecord:
    return ConversationEventRecord(
        event_id=_id(f"event:{name}"),
        conversation_id=conversation.conversation_id,
        event_kind=kind,  # type: ignore[arg-type]
        actor_type=actor,  # type: ignore[arg-type]
        origin_class=origin,  # type: ignore[arg-type]
        parent_event_ids=parents,
        sequence_hint=sequence_hint,
        content_reference=f"artifact:content/{name}.txt",
        occurred_at=f"2026-06-24T03:00:{sequence_hint or 0:02d}Z",
        source_event_kind="provider-message",
        source_environment_id=_id("source-environment"),
        source_object_id=f"source-object-{name}",
        provider_id="provider-a",
        application_id="application-a",
        interface_id="interface-a",
        model_manifest_id="model-a",
        runtime_adapter_id="runtime-a",
        operation_id=f"operation-{name}",
        extensions=extensions,
    )


def _bundle() -> GenericExportBundle:
    conversation_b = _conversation("b", title="Second")
    conversation_a = _conversation("a", title="First")
    first = _event("first", conversation_a, sequence_hint=0)
    second = _event(
        "second",
        conversation_a,
        kind="assistant_message",
        actor="assistant",
        origin="model_proposal",
        parents=(first.event_id,),
        sequence_hint=1,
    )
    other = _event("other", conversation_b, sequence_hint=0)
    return GenericExportBuilder().build(
        [conversation_b, conversation_a],
        [second, other, first],
        export_batch_id=_id("export-batch"),
        started_at=STARTED,
        completed_at=COMPLETED,
    )


def test_generic_export_is_deterministic_and_formats_agree() -> None:
    conversation_b = _conversation("b", title="Second")
    conversation_a = _conversation("a", title="First")
    first = _event("first", conversation_a, sequence_hint=0)
    second = _event(
        "second",
        conversation_a,
        kind="assistant_message",
        actor="assistant",
        origin="model_proposal",
        parents=(first.event_id,),
        sequence_hint=1,
    )
    other = _event("other", conversation_b, sequence_hint=0)
    builder = GenericExportBuilder()

    first_result = builder.build(
        [conversation_b, conversation_a],
        [second, other, first],
        export_batch_id=_id("export-batch"),
        started_at=STARTED,
        completed_at=COMPLETED,
    )
    second_result = builder.build(
        [conversation_a, conversation_b],
        [first, second, other],
        export_batch_id=_id("export-batch"),
        started_at=STARTED,
        completed_at=COMPLETED,
    )

    assert first_result == second_result
    assert tuple(item.name for item in first_result.files) == (
        "manifest.json",
        "records.json",
        "records.jsonl",
        "transcript.md",
        "checksums.sha256",
    )
    assert first_result.export_batch.status == "completed"
    assert first_result.export_batch.selected_record_types == (
        "conversation",
        "conversation-event",
    )
    assert first_result.export_batch.exported_object_count == 5
    assert first_result.mapping_report.mapped_without_known_loss_count == 5
    assert first_result.mapping_report.full_fidelity_possible is True
    assert first_result.export_batch.manifest_hash == first_result.file("manifest.json").sha256

    records_document = json.loads(first_result.file("records.json").content)
    jsonl_lines = first_result.file("records.jsonl").content.decode().splitlines()
    assert records_document["records"] == [json.loads(line) for line in jsonl_lines[1:]]
    assert [item["record_kind"] for item in records_document["records"]] == [
        "conversation",
        "conversation",
        "conversation_event",
        "conversation_event",
        "conversation_event",
    ]
    assert json.loads(jsonl_lines[0]) == {
        "export_batch_id": _id("export-batch"),
        "format": "doll-generic-export",
        "format_version": "1",
        "record_kind": "manifest",
    }

    manifest = json.loads(first_result.file("manifest.json").content)
    assert manifest["object_counts"] == {
        "conversation": 2,
        "conversation_event": 3,
        "total": 5,
    }
    assert manifest["full_fidelity_possible"] is True
    assert "does not grant policy" in manifest["authority_note"]
    assert [item["name"] for item in manifest["files"]] == [
        "records.json",
        "records.jsonl",
        "transcript.md",
    ]

    markdown = first_result.file("transcript.md").content.decode()
    assert "Non-authoritative inspectable view" in markdown
    assert markdown.index(f"Event `{first.event_id}`") < markdown.index(
        f"Event `{second.event_id}`"
    )
    assert "artifact:content/first.txt" in markdown
    assert "provider-a" in markdown
    verify_generic_export_bundle(first_result)
    json.dumps(first_result.canonical_summary(), allow_nan=False)


def test_export_without_events_has_explicit_empty_transcript_section() -> None:
    conversation = _conversation("empty", title="Empty")
    result = GenericExportBuilder().build(
        [conversation],
        [],
        export_batch_id=_id("empty-export"),
        started_at=STARTED,
        completed_at=COMPLETED,
    )

    assert result.export_batch.selected_record_types == ("conversation",)
    assert result.export_batch.exported_object_count == 1
    assert result.mapping_report.total_object_count == 1
    assert "_No exported events._" in result.file("transcript.md").content.decode()


def test_markdown_uses_a_safe_fence_for_backtick_runs() -> None:
    conversation = _conversation("fence")
    event = _event(
        "fence",
        conversation,
        extensions={"quoted": "```untrusted fence```"},
    )
    result = GenericExportBuilder().build(
        [conversation],
        [event],
        export_batch_id=_id("fence-export"),
        started_at=STARTED,
        completed_at=COMPLETED,
    )

    markdown = result.file("transcript.md").content.decode()
    assert "````json" in markdown
    assert "```untrusted fence```" in markdown
    verify_generic_export_bundle(result)


def test_managed_publication_creates_only_bundle_files(tmp_path: Path) -> None:
    workspace = initialize_workspace(tmp_path / "workspace")
    bundle = _bundle()
    prefix = f"exports/{bundle.export_batch.export_batch_id}"

    published = GenericExportBuilder().publish(
        bundle,
        artifacts_root=workspace.root / "artifacts",
        managed_prefix=prefix,
    )

    assert published.export_batch_id == bundle.export_batch.export_batch_id
    assert published.managed_prefix == prefix
    assert [item.name for item in published.files] == [item.name for item in bundle.files]
    for metadata, source in zip(published.files, bundle.files, strict=True):
        path = workspace.root / "artifacts" / metadata.managed_path
        assert path.read_bytes() == source.content
        assert metadata.content_hash == f"sha256:{source.sha256}"
        assert metadata.size_bytes == source.size_bytes
