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


def _conversation_workspace(
    tmp_path: Path,
) -> tuple[
    workspace.InitializedWorkspace,
    state.ConversationRecord,
    state.ConversationRecord,
    state.ConversationEventRecord,
    state.ConversationEventRecord,
    state.ConversationEventRecord,
]:
    initialized = workspace.initialize_workspace(tmp_path / "source")
    first = state.ConversationRecord(
        conversation_id=str(uuid4()),
        title="Primary portable conversation",
    )
    second = state.ConversationRecord(
        conversation_id=str(uuid4()),
        title="Secondary portable conversation",
    )
    first_parent = state.ConversationEventRecord(
        event_id=str(uuid4()),
        conversation_id=first.conversation_id,
        event_kind="user_message",
        actor_type="user",
        origin_class="current_user_instruction",
        sequence_hint=1,
        occurred_at="2026-06-27T00:00:00Z",
    )
    first_child = state.ConversationEventRecord(
        event_id=str(uuid4()),
        conversation_id=first.conversation_id,
        event_kind="assistant_message",
        actor_type="assistant",
        origin_class="model_proposal",
        parent_event_ids=(first_parent.event_id,),
        sequence_hint=2,
        occurred_at="2026-06-27T00:00:01Z",
    )
    second_parent = state.ConversationEventRecord(
        event_id=str(uuid4()),
        conversation_id=second.conversation_id,
        event_kind="user_message",
        actor_type="user",
        origin_class="current_user_instruction",
        sequence_hint=1,
        occurred_at="2026-06-27T00:00:02Z",
    )
    with state.initialize_state_repository(initialized.root) as repository:
        repository.save_conversation(first)
        repository.save_conversation(second)
        repository.save_conversation_event(first_parent)
        repository.save_conversation_event(first_child)
        repository.save_conversation_event(second_parent)
    return initialized, first, second, first_parent, first_child, second_parent


def _export(initialized: workspace.InitializedWorkspace, output: Path) -> None:
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        package.export_state_package(
            repository,
            output,
            exported_at="2026-06-27T01:00:00Z",
        )


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


def test_state_package_v2_round_trips_canonical_conversations(tmp_path: Path) -> None:
    initialized, first, second, first_parent, first_child, second_parent = _conversation_workspace(
        tmp_path
    )
    output = tmp_path / "conversations.zip"
    _export(initialized, output)

    inspection = package.verify_state_package(output)
    assert inspection.package_format_version == 2
    assert inspection.record_counts["conversation"] == 2
    assert inspection.record_counts["conversation_event"] == 3

    target = tmp_path / "target"
    package.import_state_package(output, target)
    with state.open_state_repository(target, read_only=True) as repository:
        assert repository.get_conversation(first.conversation_id) == first
        assert repository.get_conversation(second.conversation_id) == second
        assert repository.list_conversation_events(first.conversation_id) == (
            first_parent,
            first_child,
        )
        assert repository.list_conversation_events(second.conversation_id) == (second_parent,)


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        ("invalid_kind", "typed record payload is invalid"),
        ("missing_conversation", "missing conversation"),
        ("missing_parent", "missing parent"),
        ("cross_conversation_parent", "crosses conversation scope"),
    ),
)
def test_state_package_rejects_invalid_conversation_graphs(
    tmp_path: Path,
    mutation: str,
    message: str,
) -> None:
    initialized, _, _, _, first_child, second_parent = _conversation_workspace(tmp_path)
    source = tmp_path / "source.zip"
    hostile = tmp_path / f"{mutation}.zip"
    _export(initialized, source)
    members = _read_members(source)
    payloads = _event_payloads(members)
    by_id = {cast(str, item["id"]): item for item in payloads}
    metadata = cast(dict[str, object], by_id[first_child.event_id]["metadata"])

    if mutation == "invalid_kind":
        metadata["event_kind"] = "future_invalid_kind"
    elif mutation == "missing_conversation":
        metadata["conversation_id"] = str(uuid4())
    elif mutation == "missing_parent":
        metadata["parent_event_ids"] = [str(uuid4())]
    else:
        metadata["parent_event_ids"] = [second_parent.event_id]

    _replace_event_payloads(members, payloads)
    _write_members(hostile, members)

    with pytest.raises(package.StatePackageValidationError, match=message):
        package.verify_state_package(hostile)


def test_conversation_parent_cycle_is_rejected(tmp_path: Path) -> None:
    initialized, _, _, first_parent, first_child, _ = _conversation_workspace(tmp_path)
    source = tmp_path / "source.zip"
    hostile = tmp_path / "cycle.zip"
    _export(initialized, source)
    members = _read_members(source)
    payloads = _event_payloads(members)
    by_id = {cast(str, item["id"]): item for item in payloads}
    first_metadata = cast(dict[str, object], by_id[first_parent.event_id]["metadata"])
    first_metadata["parent_event_ids"] = [first_child.event_id]
    _replace_event_payloads(members, payloads)
    _write_members(hostile, members)

    with pytest.raises(package.StatePackageValidationError, match="contains a cycle"):
        package.verify_state_package(hostile)


def test_earlier_v2_package_without_conversation_members_remains_readable(
    tmp_path: Path,
) -> None:
    initialized = workspace.initialize_workspace(tmp_path / "source")
    with state.initialize_state_repository(initialized.root):
        pass
    source = tmp_path / "source.zip"
    legacy = tmp_path / "legacy-v2.zip"
    _export(initialized, source)
    members = _read_members(source)
    manifest_name = f"{package.PACKAGE_ROOT}/manifest.json"
    manifest = cast(dict[str, object], json.loads(members[manifest_name]))

    for record_type, member_path in (
        ("conversation", "records/conversations.jsonl"),
        ("conversation_event", "records/conversation-events.jsonl"),
    ):
        members.pop(f"{package.PACKAGE_ROOT}/{member_path}")
        cast(list[str], manifest["included_categories"]).remove(record_type)
        cast(dict[str, int], manifest["record_counts"]).pop(record_type)
        cast(dict[str, int], manifest["omitted_secret_counts"]).pop(record_type)

    manifest["total_payload_size_bytes"] = sum(
        len(content)
        for name, content in members.items()
        if not name.endswith("/manifest.json") and not name.endswith("/checksums.json")
    )
    members[manifest_name] = package._json_bytes(manifest)
    _write_members(legacy, members)

    inspection = package.verify_state_package(legacy)
    assert inspection.package_format_version == 2
    assert inspection.record_counts["conversation"] == 0
    assert inspection.record_counts["conversation_event"] == 0
