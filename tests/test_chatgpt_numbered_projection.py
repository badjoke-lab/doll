from __future__ import annotations

import json
from pathlib import Path

import pytest

import doll.chatgpt_numbered_projection as projection_module
from doll.chatgpt_numbered_aggregation import (
    ChatGPTNumberedAggregationError,
    ChatGPTNumberedConversationAggregator,
    ChatGPTNumberedMember,
)
from doll.chatgpt_numbered_projection import (
    ChatGPTNumberedPathMember,
    ChatGPTNumberedSequentialProjector,
)


def _conversation(conversation_id: str, text: str = "hello") -> dict[str, object]:
    return {
        "id": conversation_id,
        "conversation_id": conversation_id,
        "title": f"title-{conversation_id}",
        "create_time": 1_700_000_000.0,
        "update_time": 1_700_000_001.0,
        "mapping": {
            "root": {
                "id": "root",
                "message": None,
                "parent": None,
                "children": ["user"],
            },
            "user": {
                "id": "user",
                "message": {
                    "id": f"message-{conversation_id}",
                    "author": {"role": "user", "name": None, "metadata": {}},
                    "create_time": 1_700_000_000.0,
                    "update_time": None,
                    "content": {"content_type": "text", "parts": [text]},
                    "status": "finished_successfully",
                    "end_turn": True,
                    "weight": 1.0,
                    "metadata": {},
                    "recipient": "all",
                    "channel": None,
                },
                "parent": "root",
                "children": [],
            },
        },
        "current_node": "user",
    }


def _bytes(conversations: list[object]) -> bytes:
    return json.dumps(
        conversations,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _write_member(path: Path, conversations: list[object]) -> bytes:
    source = _bytes(conversations)
    path.write_bytes(source)
    return source


def test_sequential_projection_matches_in_memory_aggregate(tmp_path: Path) -> None:
    first_path = tmp_path / "conversations-1.json"
    second_path = tmp_path / "conversations-2.json"
    first_bytes = _write_member(first_path, [_conversation("selected")])
    second_bytes = _write_member(second_path, [_conversation("unselected")])

    expected = ChatGPTNumberedConversationAggregator().aggregate(
        (
            ChatGPTNumberedMember("conversations-2.json", second_bytes),
            ChatGPTNumberedMember("conversations-1.json", first_bytes),
        )
    )
    actual = ChatGPTNumberedSequentialProjector().project(
        (
            ChatGPTNumberedPathMember("conversations-2.json", second_path),
            ChatGPTNumberedPathMember("conversations-1.json", first_path),
        ),
        ("selected",),
    )

    assert actual.aggregate_source_hash == expected.aggregate_source_hash
    assert actual.member_set_root_hash == expected.member_set_root_hash
    assert actual.input_conversation_count == expected.input_conversation_count
    assert actual.output_conversation_count == expected.output_conversation_count
    assert actual.exact_duplicate_conversation_count == 0
    projected = json.loads(actual.selected_projection_bytes)
    assert [item["conversation_id"] for item in projected] == ["selected"]
    assert actual.canonical_summary()["processing_mode"] == (
        "sequential-member-selected-projection"
    )


def test_sequential_projection_collapses_exact_duplicate(tmp_path: Path) -> None:
    duplicate = _conversation("duplicate")
    first_path = tmp_path / "conversations-1.json"
    second_path = tmp_path / "conversations-2.json"
    _write_member(first_path, [duplicate])
    _write_member(second_path, [duplicate])

    result = ChatGPTNumberedSequentialProjector().project(
        (
            ChatGPTNumberedPathMember(first_path.name, first_path),
            ChatGPTNumberedPathMember(second_path.name, second_path),
        ),
        ("duplicate",),
    )

    assert result.input_conversation_count == 2
    assert result.output_conversation_count == 1
    assert result.exact_duplicate_conversation_count == 1
    assert len(json.loads(result.selected_projection_bytes)) == 1


def test_sequential_projection_rejects_conflicting_duplicate(tmp_path: Path) -> None:
    first_path = tmp_path / "conversations-1.json"
    second_path = tmp_path / "conversations-2.json"
    _write_member(first_path, [_conversation("duplicate", "first")])
    _write_member(second_path, [_conversation("duplicate", "changed")])

    with pytest.raises(
        ChatGPTNumberedAggregationError,
        match="conflicting duplicate conversation identity",
    ):
        ChatGPTNumberedSequentialProjector().project(
            (
                ChatGPTNumberedPathMember(first_path.name, first_path),
                ChatGPTNumberedPathMember(second_path.name, second_path),
            ),
            ("duplicate",),
        )


def test_sequential_projection_byte_limit_is_enforced(tmp_path: Path) -> None:
    member_path = tmp_path / "conversations-1.json"
    _write_member(member_path, [_conversation("selected")])

    with pytest.raises(ChatGPTNumberedAggregationError, match="selected projection"):
        ChatGPTNumberedSequentialProjector(max_selected_projection_bytes=1).project(
            (ChatGPTNumberedPathMember(member_path.name, member_path),),
            ("selected",),
        )


def test_sequential_projection_summary_contains_no_private_content_or_path(
    tmp_path: Path,
) -> None:
    member_path = tmp_path / "conversations-1.json"
    _write_member(
        member_path,
        [_conversation("private-id-should-not-leak", "private-text-should-not-leak")],
    )

    result = ChatGPTNumberedSequentialProjector().project(
        (ChatGPTNumberedPathMember(member_path.name, member_path),),
        ("private-id-should-not-leak",),
    )

    summary = json.dumps(result.canonical_summary(), sort_keys=True)
    assert "private-id-should-not-leak" not in summary
    assert "private-text-should-not-leak" not in summary
    assert str(tmp_path) not in summary


def test_sequential_projection_rejects_invalid_json(tmp_path: Path) -> None:
    member_path = tmp_path / "conversations-1.json"
    member_path.write_bytes(b"{")

    with pytest.raises(ChatGPTNumberedAggregationError, match="supported JSON conversation list"):
        ChatGPTNumberedSequentialProjector().project(
            (ChatGPTNumberedPathMember(member_path.name, member_path),),
            ("selected",),
        )


def test_sequential_projection_rejects_excessive_nesting(tmp_path: Path) -> None:
    member_path = tmp_path / "conversations-1.json"
    _write_member(member_path, [_conversation("selected")])

    with pytest.raises(ChatGPTNumberedAggregationError, match="nesting exceeds limit"):
        ChatGPTNumberedSequentialProjector(max_nesting_depth=1).project(
            (ChatGPTNumberedPathMember(member_path.name, member_path),),
            ("selected",),
        )


def test_sequential_projection_rejects_conversation_count_limit(tmp_path: Path) -> None:
    member_path = tmp_path / "conversations-1.json"
    _write_member(member_path, [_conversation("selected")])

    with pytest.raises(ChatGPTNumberedAggregationError, match="conversation count exceeds limit"):
        ChatGPTNumberedSequentialProjector(max_conversation_count=0).project(
            (ChatGPTNumberedPathMember(member_path.name, member_path),),
            ("selected",),
        )


def test_sequential_projection_rejects_invalid_conversation_identity(tmp_path: Path) -> None:
    member_path = tmp_path / "conversations-1.json"
    invalid = _conversation("selected")
    invalid.pop("id")
    invalid.pop("conversation_id")
    _write_member(member_path, [invalid])

    with pytest.raises(ChatGPTNumberedAggregationError, match="invalid conversation identity"):
        ChatGPTNumberedSequentialProjector().project(
            (ChatGPTNumberedPathMember(member_path.name, member_path),),
            ("selected",),
        )


def test_sequential_projection_rejects_missing_selection(tmp_path: Path) -> None:
    member_path = tmp_path / "conversations-1.json"
    _write_member(member_path, [_conversation("present")])

    with pytest.raises(ChatGPTNumberedAggregationError, match="selected conversation ids were not found"):
        ChatGPTNumberedSequentialProjector().project(
            (ChatGPTNumberedPathMember(member_path.name, member_path),),
            ("missing",),
        )


def test_sequential_projection_rejects_member_changed_during_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    member_path = tmp_path / "conversations-1.json"
    source = _write_member(member_path, [_conversation("selected")])

    def changed_hash(path: Path) -> tuple[int, str]:
        return len(source), "0" * 64

    monkeypatch.setattr(projection_module, "_hash_path", changed_hash)

    with pytest.raises(ChatGPTNumberedAggregationError, match="changed during sequential projection"):
        ChatGPTNumberedSequentialProjector().project(
            (ChatGPTNumberedPathMember(member_path.name, member_path),),
            ("selected",),
        )


@pytest.mark.parametrize(
    ("members_factory", "message"),
    [
        (
            lambda root: (
                ChatGPTNumberedPathMember("conversations.json", root / "conversations.json"),
            ),
            "label is unsupported",
        ),
        (
            lambda root: (
                ChatGPTNumberedPathMember("conversations-1.json", root / "conversations-1.json"),
                ChatGPTNumberedPathMember("conversations-01.json", root / "conversations-01.json"),
            ),
            "indices contain duplicates",
        ),
        (
            lambda root: (
                ChatGPTNumberedPathMember("conversations-1.json", root / "shared.json"),
                ChatGPTNumberedPathMember("conversations-2.json", root / "shared.json"),
            ),
            "paths contain duplicates",
        ),
        (
            lambda root: (
                ChatGPTNumberedPathMember("conversations-1.json", root / "missing.json"),
            ),
            "path is not a file",
        ),
        (
            lambda root: (
                ChatGPTNumberedPathMember("conversations-2.json", root / "conversations-2.json"),
            ),
            "sequence must start at zero or one",
        ),
        (
            lambda root: (
                ChatGPTNumberedPathMember("conversations-1.json", root / "conversations-1.json"),
                ChatGPTNumberedPathMember("conversations-3.json", root / "conversations-3.json"),
            ),
            "sequence contains a gap",
        ),
    ],
)
def test_sequential_projection_rejects_invalid_member_layouts(
    tmp_path: Path,
    members_factory: object,
    message: str,
) -> None:
    for name in (
        "conversations.json",
        "conversations-1.json",
        "conversations-01.json",
        "conversations-2.json",
        "conversations-3.json",
        "shared.json",
    ):
        _write_member(tmp_path / name, [_conversation("selected")])

    factory = members_factory
    assert callable(factory)
    members = factory(tmp_path)

    with pytest.raises(ChatGPTNumberedAggregationError, match=message):
        ChatGPTNumberedSequentialProjector().project(members, ("selected",))


def test_sequential_projection_rejects_total_input_byte_limit(tmp_path: Path) -> None:
    member_path = tmp_path / "conversations-1.json"
    _write_member(member_path, [_conversation("selected")])

    with pytest.raises(ChatGPTNumberedAggregationError, match="aggregate numbered input"):
        ChatGPTNumberedSequentialProjector(max_total_input_bytes=1).project(
            (ChatGPTNumberedPathMember(member_path.name, member_path),),
            ("selected",),
        )
