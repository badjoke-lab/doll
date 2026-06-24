from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid5

import pytest

from doll.generic_export import (
    GenericExportBuilder,
    GenericExportBundle,
    GenericExportError,
    GenericExportFile,
    verify_generic_export_bundle,
)
from doll.state import ConversationEventRecord, ConversationRecord
from doll.workspace import initialize_workspace
from doll.workspace_files import (
    ManagedFileExistsError,
    UnsafeManagedPathError,
    publish_new_workspace_file,
)

STARTED = "2026-06-24T03:00:00Z"
COMPLETED = "2026-06-24T03:00:01Z"
NAMESPACE = UUID("831a1512-c3a5-412d-8305-b83a5b8ef98e")


def _id(name: str) -> str:
    return str(uuid5(NAMESPACE, name))


def _conversation(name: str) -> ConversationRecord:
    return ConversationRecord(conversation_id=_id(f"conversation:{name}"), title=name)


def _event(
    name: str,
    conversation_id: str,
    *,
    parents: tuple[str, ...] = (),
    extensions: dict[str, object] | None = None,
) -> ConversationEventRecord:
    return ConversationEventRecord(
        event_id=_id(f"event:{name}"),
        conversation_id=conversation_id,
        event_kind="user_message",
        actor_type="user",
        origin_class="imported_data",
        parent_event_ids=parents,
        extensions=extensions,
    )


def _build(
    conversations: list[ConversationRecord],
    events: list[ConversationEventRecord],
    *,
    builder: GenericExportBuilder | None = None,
) -> GenericExportBundle:
    return (builder or GenericExportBuilder()).build(
        conversations,
        events,
        export_batch_id=_id("batch"),
        started_at=STARTED,
        completed_at=COMPLETED,
    )


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"target_adapter_id": "BAD VALUE"}, "target adapter id"),
        ({"target_adapter_version": "bad value"}, "target adapter version"),
        ({"max_object_count": 0}, "object count limit"),
        ({"max_object_count": True}, "object count limit"),
        ({"max_file_bytes": 0}, "file byte limit"),
        ({"max_total_bytes": 0}, "total byte limit"),
    ],
)
def test_builder_rejects_invalid_configuration(
    kwargs: dict[str, object], message: str
) -> None:
    with pytest.raises(GenericExportError, match=message):
        GenericExportBuilder(**cast(Any, kwargs))


def test_builder_normalizes_adapter_identifier() -> None:
    builder = GenericExportBuilder(target_adapter_id=" Generic-Export ")
    assert builder.target_adapter_id == "generic-export"


def test_export_rejects_invalid_input_sequences_and_counts() -> None:
    conversation = _conversation("one")
    with pytest.raises(GenericExportError, match="record sequences"):
        GenericExportBuilder().build(
            cast(Any, "not-records"),
            [],
            export_batch_id=_id("batch"),
            started_at=STARTED,
            completed_at=COMPLETED,
        )
    with pytest.raises(GenericExportError, match="at least one conversation"):
        _build([], [])
    with pytest.raises(GenericExportError, match="object count"):
        _build(
            [conversation],
            [_event("one", conversation.conversation_id)],
            builder=GenericExportBuilder(max_object_count=1),
        )
    with pytest.raises(GenericExportError, match="invalid conversation record"):
        _build(cast(Any, [object()]), [])
    with pytest.raises(GenericExportError, match="invalid conversation event"):
        _build([conversation], cast(Any, [object()]))


def test_export_rejects_duplicate_and_colliding_identifiers() -> None:
    conversation = _conversation("one")
    event = _event("one", conversation.conversation_id)
    with pytest.raises(
        GenericExportError, match="conversation identifiers contain duplicates"
    ):
        _build([conversation, conversation], [])
    with pytest.raises(
        GenericExportError, match="event identifiers contain duplicates"
    ):
        _build([conversation], [event, event])

    colliding_event = replace(event, event_id=conversation.conversation_id)
    with pytest.raises(GenericExportError, match="globally distinct"):
        _build([conversation], [colliding_event])


def test_export_rejects_missing_cross_conversation_and_cyclic_relationships() -> None:
    first = _conversation("first")
    second = _conversation("second")
    missing_conversation = _event(
        "missing-conversation", _id("unavailable-conversation")
    )
    with pytest.raises(GenericExportError, match="unavailable conversation"):
        _build([first], [missing_conversation])

    missing_parent = _event(
        "missing-parent", first.conversation_id, parents=(_id("missing"),)
    )
    with pytest.raises(GenericExportError, match="parent is unavailable"):
        _build([first], [missing_parent])

    parent = _event("parent", first.conversation_id)
    cross_child = _event(
        "cross-child", second.conversation_id, parents=(parent.event_id,)
    )
    with pytest.raises(GenericExportError, match="another conversation"):
        _build([first, second], [parent, cross_child])

    first_cycle_id = _id("event:first-cycle")
    second_cycle_id = _id("event:second-cycle")
    first_cycle = replace(
        _event("first-cycle", first.conversation_id),
        parent_event_ids=(second_cycle_id,),
    )
    second_cycle = replace(
        _event("second-cycle", first.conversation_id),
        parent_event_ids=(first_cycle_id,),
    )
    with pytest.raises(GenericExportError, match="contains a cycle"):
        _build([first], [first_cycle, second_cycle])


def test_export_rejects_invalid_batch_context_and_non_json_metadata() -> None:
    conversation = _conversation("one")
    with pytest.raises(GenericExportError, match="export batch id is invalid"):
        GenericExportBuilder().build(
            [conversation],
            [],
            export_batch_id="not-a-uuid",
            started_at=STARTED,
            completed_at=COMPLETED,
        )
    with pytest.raises(GenericExportError, match="canonical UUID"):
        GenericExportBuilder().build(
            [conversation],
            [],
            export_batch_id=_id("batch").upper(),
            started_at=STARTED,
            completed_at=COMPLETED,
        )

    event = _event("bad-json", conversation.conversation_id)
    object.__setattr__(event, "extensions", {"bad": object()})
    with pytest.raises(GenericExportError, match="not canonical JSON"):
        _build([conversation], [event])


def test_export_enforces_file_and_total_byte_limits() -> None:
    conversation = _conversation("one")
    with pytest.raises(GenericExportError, match="file exceeds"):
        _build(
            [conversation],
            [],
            builder=GenericExportBuilder(max_file_bytes=1),
        )
    with pytest.raises(GenericExportError, match="total byte"):
        _build(
            [conversation],
            [],
            builder=GenericExportBuilder(max_total_bytes=1),
        )


def test_bundle_lookup_and_constructor_fail_closed() -> None:
    bundle = _build([_conversation("one")], [])
    with pytest.raises(KeyError):
        bundle.file("missing.txt")
    with pytest.raises(GenericExportError, match="ordering"):
        GenericExportBundle(
            export_batch=bundle.export_batch,
            mapping_report=bundle.mapping_report,
            files=tuple(reversed(bundle.files)),
        )


def _replace_file(
    bundle: GenericExportBundle,
    name: str,
    replacement: GenericExportFile,
) -> GenericExportBundle:
    return replace(
        bundle,
        files=tuple(
            replacement if item.name == name else item for item in bundle.files
        ),
    )


def test_verifier_rejects_content_checksum_manifest_and_jsonl_tampering() -> None:
    bundle = _build([_conversation("one")], [])
    records = bundle.file("records.json")
    tampered_records = replace(records, content=records.content + b" ")
    with pytest.raises(GenericExportError, match="digest"):
        verify_generic_export_bundle(
            _replace_file(bundle, records.name, tampered_records)
        )

    checksum = bundle.file("checksums.sha256")
    invalid_checksum_content = b"invalid checksum line\n"
    invalid_checksum = replace(
        checksum,
        content=invalid_checksum_content,
        sha256=hashlib.sha256(invalid_checksum_content).hexdigest(),
    )
    with pytest.raises(GenericExportError, match="checksum declaration is invalid"):
        verify_generic_export_bundle(
            _replace_file(bundle, checksum.name, invalid_checksum)
        )

    manifest = bundle.file("manifest.json")
    manifest_value = json.loads(manifest.content)
    manifest_value["format"] = "other"
    changed_manifest_content = (
        json.dumps(
            manifest_value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        + "\n"
    ).encode()
    changed_manifest = replace(
        manifest,
        content=changed_manifest_content,
        sha256=hashlib.sha256(changed_manifest_content).hexdigest(),
    )
    changed = _replace_file(bundle, manifest.name, changed_manifest)
    checksum_text = (
        changed.file("checksums.sha256")
        .content.decode()
        .replace(
            manifest.sha256,
            changed_manifest.sha256,
        )
    )
    changed_checksum_content = checksum_text.encode()
    changed_checksum = replace(
        changed.file("checksums.sha256"),
        content=changed_checksum_content,
        sha256=hashlib.sha256(changed_checksum_content).hexdigest(),
    )
    with pytest.raises(GenericExportError, match="manifest format"):
        verify_generic_export_bundle(
            _replace_file(changed, changed_checksum.name, changed_checksum)
        )

    jsonl = bundle.file("records.jsonl")
    lines = jsonl.content.decode().splitlines()
    lines[-1] = json.dumps({"different": True}, separators=(",", ":"))
    changed_jsonl_content = ("\n".join(lines) + "\n").encode()
    changed_jsonl = replace(
        jsonl,
        content=changed_jsonl_content,
        sha256=hashlib.sha256(changed_jsonl_content).hexdigest(),
    )
    changed = _replace_file(bundle, jsonl.name, changed_jsonl)
    manifest_value = json.loads(changed.file("manifest.json").content)
    for entry in manifest_value["files"]:
        if entry["name"] == "records.jsonl":
            entry["sha256"] = changed_jsonl.sha256
            entry["size_bytes"] = len(changed_jsonl_content)
    changed_manifest_content = (
        json.dumps(
            manifest_value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        + "\n"
    ).encode()
    changed_manifest = replace(
        changed.file("manifest.json"),
        content=changed_manifest_content,
        sha256=hashlib.sha256(changed_manifest_content).hexdigest(),
    )
    changed = _replace_file(changed, "manifest.json", changed_manifest)
    checksum_lines = []
    for name in ("manifest.json", "records.json", "records.jsonl", "transcript.md"):
        checksum_lines.append(f"{changed.file(name).sha256}  {name}")
    changed_checksum_content = ("\n".join(checksum_lines) + "\n").encode()
    changed_checksum = replace(
        changed.file("checksums.sha256"),
        content=changed_checksum_content,
        sha256=hashlib.sha256(changed_checksum_content).hexdigest(),
    )
    changed = _replace_file(changed, "checksums.sha256", changed_checksum)
    changed_batch = replace(changed.export_batch, manifest_hash=changed_manifest.sha256)
    changed = replace(changed, export_batch=changed_batch)
    with pytest.raises(GenericExportError, match="JSON and JSONL records differ"):
        verify_generic_export_bundle(changed)


def test_publish_rejects_unsafe_prefix_and_cleans_partial_output(
    tmp_path: Path,
) -> None:
    workspace = initialize_workspace(tmp_path / "workspace")
    artifacts = workspace.root / "artifacts"
    bundle = _build([_conversation("one")], [])
    builder = GenericExportBuilder()

    with pytest.raises(UnsafeManagedPathError, match="path"):
        builder.publish(bundle, artifacts_root=artifacts, managed_prefix="../escape")

    prefix = f"exports/{bundle.export_batch.export_batch_id}"
    preexisting = publish_new_workspace_file(
        artifacts,
        f"{prefix}/records.jsonl",
        b"existing",
    )
    preexisting.close()
    with pytest.raises(ManagedFileExistsError):
        builder.publish(bundle, artifacts_root=artifacts, managed_prefix=prefix)

    assert not (artifacts / prefix / "manifest.json").exists()
    assert not (artifacts / prefix / "records.json").exists()
    assert (artifacts / prefix / "records.jsonl").read_bytes() == b"existing"
    assert not (artifacts / prefix / "transcript.md").exists()
    assert not (artifacts / prefix / "checksums.sha256").exists()


def test_publish_reports_incomplete_cleanup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    bundle = _build([_conversation("one")], [])

    class BrokenPublished:
        managed_path = "exports/x/manifest.json"
        size_bytes = 1
        content_hash = "sha256:" + "0" * 64

        def cleanup(self) -> None:
            raise OSError("cleanup failed")

        def close(self) -> None:
            pass

    calls = 0

    def fake_publish(*args: object, **kwargs: object) -> Any:
        nonlocal calls
        calls += 1
        if calls == 1:
            return BrokenPublished()
        raise OSError("publish failed")

    monkeypatch.setattr("doll.generic_export.publish_new_workspace_file", fake_publish)
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    with pytest.raises(GenericExportError, match="cleanup was incomplete"):
        GenericExportBuilder().publish(
            bundle,
            artifacts_root=artifacts,
            managed_prefix="exports/x",
        )
