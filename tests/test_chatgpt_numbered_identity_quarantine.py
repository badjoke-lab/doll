from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from doll.chatgpt_numbered_aggregation import (
    ChatGPTNumberedAggregationError,
)
from doll.chatgpt_numbered_projection import (
    ChatGPTNumberedPathMember,
    ChatGPTNumberedSequentialProjector,
)


def _conversation(
    conversation_id: str,
    text: str = "hello",
) -> dict[str, object]:
    return {
        "id": conversation_id,
        "conversation_id": conversation_id,
        "title": f"title-{conversation_id}",
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
                    "author": {
                        "role": "user",
                        "name": None,
                        "metadata": {},
                    },
                    "content": {
                        "content_type": "text",
                        "parts": [text],
                    },
                    "metadata": {},
                    "recipient": "all",
                },
                "parent": "root",
                "children": [],
            },
        },
        "current_node": "user",
    }


def _write_member(
    path: Path,
    conversations: list[object],
) -> bytes:
    source = json.dumps(
        conversations,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    path.write_bytes(source)

    return source


def test_identityless_records_are_quarantined_and_bound(
    tmp_path: Path,
) -> None:
    first_path = tmp_path / "conversations-1.json"

    second_path = tmp_path / "conversations-2.json"

    first_bytes = _write_member(
        first_path,
        [
            {
                "title": "identityless-one",
                "mapping": {},
            },
            _conversation("selected"),
        ],
    )

    second_bytes = _write_member(
        second_path,
        [
            _conversation("unselected"),
            {
                "title": "identityless-two",
                "mapping": {},
            },
        ],
    )

    result = ChatGPTNumberedSequentialProjector().project(
        (
            ChatGPTNumberedPathMember(
                first_path.name,
                first_path,
            ),
            ChatGPTNumberedPathMember(
                second_path.name,
                second_path,
            ),
        ),
        ("selected",),
    )

    assert result.input_conversation_count == 4
    assert result.output_conversation_count == 2

    assert result.identity_quarantine_count == 2

    assert result.identity_quarantine_member_count == 2

    assert result.members[0].conversation_count == 2

    assert result.members[0].sha256 == hashlib.sha256(first_bytes).hexdigest()

    assert result.members[1].sha256 == hashlib.sha256(second_bytes).hexdigest()

    summary = result.canonical_summary()

    assert summary["aggregate_hash_scope"] == "identity-valid-first-unique-conversations"

    assert summary["identity_quarantine_count"] == 2

    projected = json.loads(result.selected_projection_bytes)

    assert len(projected) == 1

    assert projected[0]["conversation_id"] == "selected"


@pytest.mark.parametrize(
    "invalid_record",
    [
        {
            "id": "first",
            "conversation_id": "second",
        },
        {
            "id": 123,
        },
        "not-an-object",
    ],
)
def test_non_identityless_identity_errors_still_fail_closed(
    tmp_path: Path,
    invalid_record: object,
) -> None:
    member_path = tmp_path / "conversations-1.json"

    _write_member(
        member_path,
        [
            _conversation("selected"),
            invalid_record,
        ],
    )

    with pytest.raises(
        ChatGPTNumberedAggregationError,
        match="invalid conversation identity",
    ):
        (
            ChatGPTNumberedSequentialProjector().project(
                (
                    ChatGPTNumberedPathMember(
                        member_path.name,
                        member_path,
                    ),
                ),
                ("selected",),
            )
        )
