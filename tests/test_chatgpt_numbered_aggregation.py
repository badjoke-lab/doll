from __future__ import annotations

import json

import pytest

from doll.chatgpt_numbered_aggregation import (
    ChatGPTNumberedAggregationError,
    ChatGPTNumberedConversationAggregator,
    ChatGPTNumberedMember,
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


def _member(label: str, conversations: list[object]) -> ChatGPTNumberedMember:
    return ChatGPTNumberedMember(
        label=label,
        source_bytes=json.dumps(
            conversations,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8"),
    )


def test_aggregation_orders_members_by_numeric_index() -> None:
    members = tuple(
        _member(f"conversations-{index}.json", [_conversation(f"c-{index}")])
        for index in (10, 2, 1, 9, 8, 7, 6, 5, 4, 3)
    )

    result = ChatGPTNumberedConversationAggregator().aggregate(members)

    assert [member.index for member in result.members] == list(range(1, 11))
    aggregate = json.loads(result.aggregated_bytes)
    assert [item["conversation_id"] for item in aggregate] == [
        f"c-{index}" for index in range(1, 11)
    ]
    assert result.input_conversation_count == 10
    assert result.output_conversation_count == 10
    assert result.exact_duplicate_conversation_count == 0


def test_zero_based_member_sequence_is_supported() -> None:
    result = ChatGPTNumberedConversationAggregator().aggregate(
        (
            _member("conversations-1.json", [_conversation("second")]),
            _member("conversations-0.json", [_conversation("first")]),
        )
    )

    assert [member.index for member in result.members] == [0, 1]


def test_argument_order_does_not_change_aggregate() -> None:
    first = _member("conversations-1.json", [_conversation("first")])
    second = _member("conversations-2.json", [_conversation("second")])
    aggregator = ChatGPTNumberedConversationAggregator()

    forward = aggregator.aggregate((first, second))
    reverse = aggregator.aggregate((second, first))

    assert forward.aggregated_bytes == reverse.aggregated_bytes
    assert forward.aggregate_source_hash == reverse.aggregate_source_hash
    assert forward.member_set_root_hash == reverse.member_set_root_hash
    assert forward.canonical_summary() == reverse.canonical_summary()


def test_exact_duplicate_conversation_is_collapsed_and_reported() -> None:
    duplicate = _conversation("duplicate")

    result = ChatGPTNumberedConversationAggregator().aggregate(
        (
            _member("conversations-1.json", [duplicate]),
            _member("conversations-2.json", [duplicate]),
        )
    )

    assert result.input_conversation_count == 2
    assert result.output_conversation_count == 1
    assert result.exact_duplicate_conversation_count == 1


def test_conflicting_duplicate_conversation_fails_closed() -> None:
    with pytest.raises(
        ChatGPTNumberedAggregationError,
        match="conflicting duplicate conversation identity",
    ):
        ChatGPTNumberedConversationAggregator().aggregate(
            (
                _member("conversations-1.json", [_conversation("duplicate", "first")]),
                _member("conversations-2.json", [_conversation("duplicate", "changed")]),
            )
        )


@pytest.mark.parametrize(
    ("members", "message"),
    [
        ((), "non-empty tuple"),
        (
            (_member("conversations.json", [_conversation("c")]),),
            "label is unsupported",
        ),
        (
            (
                _member("conversations-1.json", [_conversation("a")]),
                _member("conversations-01.json", [_conversation("b")]),
            ),
            "indices contain duplicates",
        ),
        (
            (
                _member("conversations-1.json", [_conversation("a")]),
                _member("conversations-3.json", [_conversation("b")]),
            ),
            "sequence contains a gap",
        ),
        (
            (_member("conversations-2.json", [_conversation("a")]),),
            "sequence must start at zero or one",
        ),
    ],
)
def test_invalid_member_layouts_fail_closed(
    members: tuple[ChatGPTNumberedMember, ...],
    message: str,
) -> None:
    with pytest.raises(ChatGPTNumberedAggregationError, match=message):
        ChatGPTNumberedConversationAggregator().aggregate(members)


def test_invalid_json_member_fails_closed() -> None:
    member = ChatGPTNumberedMember(
        label="conversations-1.json",
        source_bytes=b"{",
    )

    with pytest.raises(ChatGPTNumberedAggregationError, match="supported JSON conversation list"):
        ChatGPTNumberedConversationAggregator().aggregate((member,))


def test_non_list_member_root_fails_closed() -> None:
    member = ChatGPTNumberedMember(
        label="conversations-1.json",
        source_bytes=b"{}",
    )

    with pytest.raises(ChatGPTNumberedAggregationError, match="supported JSON conversation list"):
        ChatGPTNumberedConversationAggregator().aggregate((member,))


def test_duplicate_json_key_member_fails_closed() -> None:
    member = ChatGPTNumberedMember(
        label="conversations-1.json",
        source_bytes=b'[{"id":"a","id":"b"}]',
    )

    with pytest.raises(ChatGPTNumberedAggregationError, match="supported JSON conversation list"):
        ChatGPTNumberedConversationAggregator().aggregate((member,))


def test_non_finite_json_constant_member_fails_closed() -> None:
    member = ChatGPTNumberedMember(
        label="conversations-1.json",
        source_bytes=b'[{"id":"a","value":NaN}]',
    )

    with pytest.raises(ChatGPTNumberedAggregationError, match="supported JSON conversation list"):
        ChatGPTNumberedConversationAggregator().aggregate((member,))


def test_default_aggregate_byte_limit_is_one_gib() -> None:
    aggregator = ChatGPTNumberedConversationAggregator()

    assert aggregator.max_total_input_bytes == 1024 * 1024 * 1024


def test_aggregate_byte_limit_is_enforced() -> None:
    member = _member("conversations-1.json", [_conversation("a")])
    aggregator = ChatGPTNumberedConversationAggregator(max_total_input_bytes=1)

    with pytest.raises(ChatGPTNumberedAggregationError, match="byte limit"):
        aggregator.aggregate((member,))


def test_aggregate_conversation_limit_is_enforced() -> None:
    member = _member(
        "conversations-1.json",
        [_conversation("a"), _conversation("b")],
    )
    aggregator = ChatGPTNumberedConversationAggregator(max_conversation_count=1)

    with pytest.raises(ChatGPTNumberedAggregationError, match="conversation count exceeds limit"):
        aggregator.aggregate((member,))


def test_manifest_contains_no_private_path_or_content() -> None:
    result = ChatGPTNumberedConversationAggregator().aggregate(
        (_member("conversations-1.json", [_conversation("private-id", "private-text")]),)
    )

    summary = json.dumps(result.canonical_summary(), sort_keys=True)
    assert "private-id" not in summary
    assert "private-text" not in summary
    assert "/Users/" not in summary
    assert result.members[0].label == "conversations-1.json"
