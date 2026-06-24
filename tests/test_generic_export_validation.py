from __future__ import annotations

from typing import Any, cast
from uuid import UUID, uuid5

import pytest

import doll.generic_export as generic_export
from doll.state import ConversationRecord

STARTED = "2026-06-24T03:00:00Z"
COMPLETED = "2026-06-24T03:00:01Z"
NAMESPACE = UUID("d2539329-c20b-449c-86e7-198b462f0990")


def _id(name: str) -> str:
    return str(uuid5(NAMESPACE, name))


def _conversation() -> ConversationRecord:
    return ConversationRecord(conversation_id=_id("conversation"), title="Validation")


def test_builder_rejects_non_text_identifiers_and_batch_id() -> None:
    with pytest.raises(generic_export.GenericExportError, match="target adapter id"):
        generic_export.GenericExportBuilder(target_adapter_id=cast(Any, object()))
    with pytest.raises(generic_export.GenericExportError, match="target adapter version"):
        generic_export.GenericExportBuilder(target_adapter_version=cast(Any, object()))
    with pytest.raises(generic_export.GenericExportError, match="must be text"):
        generic_export.GenericExportBuilder().build(
            [_conversation()],
            [],
            export_batch_id=cast(Any, 1),
            started_at=STARTED,
            completed_at=COMPLETED,
        )


def test_builder_enforces_markdown_byte_limit() -> None:
    with pytest.raises(generic_export.GenericExportError, match="Markdown exceeds"):
        generic_export.GenericExportBuilder(max_markdown_bytes=1).build(
            [_conversation()],
            [],
            export_batch_id=_id("markdown-limit"),
            started_at=STARTED,
            completed_at=COMPLETED,
        )


def test_checksum_parser_rejects_encoding_and_duplicate_declarations() -> None:
    digest = "0" * 64
    with pytest.raises(generic_export.GenericExportError, match="not ASCII"):
        generic_export._parse_checksums(bytes([255]))
    with pytest.raises(generic_export.GenericExportError, match="contain duplicates"):
        generic_export._parse_checksums(
            f"{digest}  manifest.json\n{digest}  manifest.json\n".encode()
        )


def test_jsonl_parser_rejects_encoding_empty_input_and_bad_manifest() -> None:
    batch_id = _id("jsonl")
    with pytest.raises(generic_export.GenericExportError, match="not valid UTF-8"):
        generic_export._parse_jsonl_records(bytes([255]), batch_id)
    with pytest.raises(generic_export.GenericExportError, match="is empty"):
        generic_export._parse_jsonl_records(b"", batch_id)
    with pytest.raises(generic_export.GenericExportError, match="manifest is invalid"):
        generic_export._parse_jsonl_records(b"{}\n", batch_id)


def test_json_object_loader_rejects_encoding_shape_and_nonstandard_values() -> None:
    with pytest.raises(generic_export.GenericExportError, match="not valid UTF-8"):
        generic_export._load_json_object(bytes([255]), "fixture")
    with pytest.raises(generic_export.GenericExportError, match="must be an object"):
        generic_export._load_json_object(b"[]", "fixture")
    nonstandard = ('{"value":' + "NaN" + "}").encode()
    with pytest.raises(generic_export.GenericExportError, match="is invalid"):
        generic_export._load_json_object(nonstandard, "fixture")
