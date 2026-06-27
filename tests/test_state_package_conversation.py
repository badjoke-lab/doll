from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import cast
from uuid import uuid4

import pytest

import doll.state_package as package
from doll import state, workspace
from doll.state import ConversationEventRecord, ConversationRecord


def _workspace_with_conversations(
    tmp_path: Path,
) -> tuple[workspace.InitializedWorkspace, dict[str, str]]:
    initialized = workspace.initialize_workspace(tmp_path / "source")
    with state.initialize_state_repository(initialized.root):
        pass

    first_conversation = str(uuid4())
    second_conversation = str(uuid4())
    first_event = str(uuid4())
    second_event = str(uuid4())
    other_event = str(uuid4())
    with state.open_state_repository(initialized.root) as repository:
        repository.save_conversation(
            ConversationRecord(
                conversation_id=first_conversation,
                title="Portable canonical conversation",
            )
        )
        repository.save_conversation(
            ConversationRecord(
                conversation_id=second_conversation,
                title="Second canonical conversation",
            )
        )
        repository.save_conversation_event(
            ConversationEventRecord(
                event_id=first_event,
                conversation_id=first_conversation,
                event_kind="user_message",
                actor_type="user",
                origin_class="current_user_instruction",
                sequence_hint=1,
                operation_id="package.conversation.first",
            )
        )
        repository.save_conversation_event(
            ConversationEventRecord(
                event_id=second_event,
                conversation_id=first_conversation,
                event_kind="assistant_message",
                actor_type="assistant",
                origin_class="runtime_output",
                parent_event_ids=(first_event,),
                sequence_hint=2,
                operation_id="package.conversation.second",
            )
        )
        repository.save_conversation_event(
            ConversationEventRecord(
                event_id=other_event,
                conversation_id=second_conversation,
                event_kind="user_message",
                actor_type="user",
                origin_class="current_user_instruction",
                sequence_hint=1,
                operation_id="package.conversation.other",
            )
        )
    return initialized, {
        "first_conversation": first_conversation,
        "second_conversation": second_conversation,
        "first_event": first_event,
        "second_event": second_event,
        "other_event": other_event,
    }


def _export(initialized: workspace.InitializedWorkspace, output: Path) -> None:
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        package.export_state_package(
            repository,
            output,
            exported_at="2026-06-27T13:00:00Z",
        )


def _read_members(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path, "r") as archive:
        return {info.filename: archive.read(info) for info in archive.infolist()}


def _write_members(path: Path, members: dict[str, bytes]) -> None:
    updated = dict(members)
    checksum_name = f"{package.PACKAGE_ROOT}/checksums.json"
    updated.pop(checksum_name, None)
    updated[checksum_name] = package._json_bytes(
        {
            "algorithm": package.CHECKSUM_ALGORITHM,
            "entries": [
                {
                    "path": name,
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "size_bytes": len(content),
                }
                for name, content in sorted(updated.items())
            ],
        }
    )
    package._write_deterministic_zip(path, updated)


def _event_payloads(members: dict[str, bytes]) -> list[dict[str, object]]:
    name = f"{package.PACKAGE_ROOT}/records/conversation-events.jsonl"
    return [
        cast(dict[str, object], json.loads(line))
        for line in members[name].decode("utf-8").splitlines()
        if line
    ]


def _replace_event_payloads(
    members: dict[str, bytes],
    payloads: list[dict[str, object]],
) -> None:
    name = f"{package.PACKAGE_ROOT}/records/conversation-events.jsonl"
    members[name] = package._jsonl_bytes(payloads)


def test_v2_round_trips_canonical_conversations_and_event_graph(tmp_path: Path) -> None:
    initialized, identifiers = _workspace_with_conversations(tmp_path)
    output = tmp_path / "state.zip"
    _export(initialized, output)

    inspection = package.verify_state_package(output)
    assert inspection.package_format_version == 2
    assert inspection.record_counts["conversation"] == 2
    assert inspection.record_counts["conversation_event"] == 3

    target = tmp_path / "target"
    result = package.import_state_package(output, target)
    assert result.imported_record_count == sum(inspection.record_counts.values())

    with state.open_state_repository(target, read_only=True) as repository:
        first = repository.get_conversation(identifiers["first_conversation"])
        second = repository.get_conversation(identifiers["second_conversation"])
        assert first.title == "Portable canonical conversation"
        assert second.title == "Second canonical conversation"
        first_events = repository.list_conversation_events(first.conversation_id)
        assert [event.event_id for event in first_events] == [
            identifiers["first_event"],
            identifiers["second_event"],
        ]
        assert first_events[1].parent_event_ids == (identifiers["first_event"],)
        other_events = repository.list_conversation_events(second.conversation_id)
        assert [event.event_id for event in other_events] == [identifiers["other_event"]]


def test_earlier_v2_without_optional_conversation_members_remains_readable(
    tmp_path: Path,
) -> None:
    initialized, _ = _workspace_with_conversations(tmp_path)
    current = tmp_path / "current.zip"
    earlier = tmp_path / "earlier-v2.zip"
    _export(initialized, current)
    members = _read_members(current)
    manifest_name = f"{package.PACKAGE_ROOT}/manifest.json"
    manifest = cast(dict[str, object], json.loads(members[manifest_name]))
    included = cast(list[str], manifest["included_categories"])
    counts = cast(dict[str, int], manifest["record_counts"])
    omitted = cast(dict[str, int], manifest["omitted_secret_counts"])
    for record_type, member in (
        ("conversation", "records/conversations.jsonl"),
        ("conversation_event", "records/conversation-events.jsonl"),
    ):
        included.remove(record_type)
        counts.pop(record_type)
        omitted.pop(record_type)
        members.pop(f"{package.PACKAGE_ROOT}/{member}")
    members[manifest_name] = package._json_bytes(manifest)
    _write_members(earlier, members)

    inspection = package.verify_state_package(earlier)
    assert inspection.package_format_version == 2
    assert inspection.record_counts["conversation"] == 0
    assert inspection.record_counts["conversation_event"] == 0
    target = tmp_path / "earlier-target"
    package.import_state_package(earlier, target)
    with state.open_state_repository(target, read_only=True) as repository:
        assert repository.list_conversations() == ()


@pytest.mark.parametrize(
    "mutation",
    ("missing_conversation", "missing_parent", "cross_conversation_parent", "malformed"),
)
def test_invalid_conversation_package_graph_is_rejected(
    tmp_path: Path,
    mutation: str,
) -> None:
    initialized, identifiers = _workspace_with_conversations(tmp_path)
    source = tmp_path / "source.zip"
    hostile = tmp_path / f"{mutation}.zip"
    _export(initialized, source)
    members = _read_members(source)
    payloads = _event_payloads(members)
    by_id = {cast(str, payload["id"]): payload for payload in payloads}
    target = by_id[identifiers["second_event"]]
    metadata = cast(dict[str, object], target["metadata"])
    if mutation == "missing_conversation":
        metadata["conversation_id"] = str(uuid4())
    elif mutation == "missing_parent":
        metadata["parent_event_ids"] = [str(uuid4())]
    elif mutation == "cross_conversation_parent":
        metadata["parent_event_ids"] = [identifiers["other_event"]]
    else:
        metadata.pop("actor_type")
    _replace_event_payloads(members, payloads)
    _write_members(hostile, members)

    with pytest.raises(package.StatePackageValidationError):
        package.verify_state_package(hostile)


def test_conversation_parent_cycle_is_rejected(tmp_path: Path) -> None:
    initialized, identifiers = _workspace_with_conversations(tmp_path)
    source = tmp_path / "source.zip"
    hostile = tmp_path / "cycle.zip"
    _export(initialized, source)
    members = _read_members(source)
    payloads = _event_payloads(members)
    by_id = {cast(str, payload["id"]): payload for payload in payloads}
    first_metadata = cast(dict[str, object], by_id[identifiers["first_event"]]["metadata"])
    first_metadata["parent_event_ids"] = [identifiers["second_event"]]
    _replace_event_payloads(members, payloads)
    _write_members(hostile, members)

    with pytest.raises(package.StatePackageValidationError):
        package.verify_state_package(hostile)
