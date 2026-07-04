from __future__ import annotations

import ast
import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import pytest

from doll import state
from doll.chatgpt_export_import import (
    ChatGPTExportImportError,
    ChatGPTExportSourceAdapter,
    ChatGPTExportStageResult,
    chatgpt_export_source_contract,
)
from doll.generic_import_publication import (
    GenericImportPublicationError,
    GenericImportPublisher,
)
from tests.import_publication_support import _initialized

STARTED = "2026-07-04T00:00:00Z"
COMPLETED = "2026-07-04T00:00:01Z"


def _message(
    message_id: str,
    role: str,
    text: str,
    *,
    content_type: str = "text",
    metadata: dict[str, object] | None = None,
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    value: dict[str, object] = {
        "id": message_id,
        "author": {"role": role, "name": None, "metadata": {}},
        "create_time": 1_700_000_000.0,
        "update_time": None,
        "content": {"content_type": content_type, "parts": [text]},
        "status": "finished_successfully",
        "end_turn": True,
        "weight": 1.0,
        "metadata": metadata or {"model_slug": "synthetic-provider-model"},
        "recipient": "all",
        "channel": None,
    }
    if extra:
        value.update(extra)
    return value


def _node(
    node_id: str,
    message: dict[str, object] | None,
    *,
    parent: str | None,
    children: list[str] | None = None,
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    value: dict[str, object] = {
        "id": node_id,
        "message": message,
        "parent": parent,
        "children": children or [],
    }
    if extra:
        value.update(extra)
    return value


def _conversation(
    conversation_id: str,
    *,
    user_text: str = "synthetic user text",
    assistant_text: str = "synthetic assistant text",
    assistant_role: str = "assistant",
    assistant_content_type: str = "text",
    extra_conversation: dict[str, object] | None = None,
    extra_message: dict[str, object] | None = None,
    assistant_metadata: dict[str, object] | None = None,
) -> dict[str, object]:
    mapping = {
        "root": _node("root", None, parent=None, children=["user"]),
        "user": _node(
            "user",
            _message("message-user", "user", user_text),
            parent="root",
            children=["assistant", "branch"],
        ),
        "assistant": _node(
            "assistant",
            _message(
                "message-assistant",
                assistant_role,
                assistant_text,
                content_type=assistant_content_type,
                metadata=assistant_metadata,
                extra=extra_message,
            ),
            parent="user",
        ),
        "branch": _node(
            "branch",
            _message("message-branch", "assistant", "synthetic branch text"),
            parent="user",
        ),
    }
    value: dict[str, object] = {
        "id": conversation_id,
        "conversation_id": conversation_id,
        "title": "Synthetic conversation",
        "create_time": 1_700_000_000.0,
        "update_time": 1_700_000_001.0,
        "mapping": mapping,
        "current_node": "assistant",
    }
    if extra_conversation:
        value.update(extra_conversation)
    return value


def _source(*conversations: object) -> bytes:
    return json.dumps(
        list(conversations),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _stage(
    source_bytes: bytes,
    selected: tuple[str, ...] = ("selected",),
    *,
    adapter: ChatGPTExportSourceAdapter | None = None,
    environment_id: str | None = None,
    batch_id: str | None = None,
) -> ChatGPTExportStageResult:
    return (adapter or ChatGPTExportSourceAdapter()).stage(
        source_bytes,
        source_environment_id=environment_id or str(uuid4()),
        selected_conversation_ids=selected,
        import_batch_id=batch_id or str(uuid4()),
        started_at=STARTED,
        observed_at=STARTED,
    )


def test_contract_and_selected_inventory_are_deterministic() -> None:
    environment_id = str(uuid4())
    batch_id = str(uuid4())
    source = _source(
        _conversation("selected"),
        _conversation("not-selected", user_text="private unselected marker"),
    )
    adapter = ChatGPTExportSourceAdapter()

    first = _stage(
        source,
        adapter=adapter,
        environment_id=environment_id,
        batch_id=batch_id,
    )
    second = _stage(
        source,
        adapter=adapter,
        environment_id=environment_id,
        batch_id=batch_id,
    )

    assert first == second
    assert adapter.contract.adapter_id == "chatgpt-conversations"
    assert adapter.contract.adapter_version == "1.0.0"
    assert adapter.contract.network_behavior == "none"
    assert adapter.contract.branch_behavior == "preserve"
    assert adapter.contract.attachment_behavior == "metadata_only"

    environment = first.source_environment
    assert environment.environment_id == environment_id
    assert environment.environment_class == "cloud-ai-history-export"
    assert environment.provider_id == "openai"
    assert environment.application_id == "chatgpt"
    assert environment.interface_id == "chatgpt.export"
    assert environment.runtime_id is None
    assert environment.export_format == "chatgpt-conversations-json"
    assert environment.export_version == "observed-v1"

    inventory = first.inventory
    assert inventory.source_root_hash == hashlib.sha256(source).hexdigest()
    assert inventory.conversation_count == 2
    assert inventory.selected_conversation_count == 1
    assert inventory.node_count == 8
    assert inventory.message_count == 6
    assert inventory.selected_message_count == 3
    assert inventory.supported_message_count == 3
    assert inventory.unsupported_message_count == 0
    assert inventory.source_object_count == 4
    assert "private unselected marker" not in json.dumps(first.canonical_summary())

    staged = first.stage_result
    assert staged.source_root_hash == inventory.source_root_hash
    assert staged.import_batch.source_root_hash == inventory.source_root_hash
    assert staged.import_batch.adapter_id == "chatgpt-conversations"
    assert staged.import_batch.adapter_version == "1.0.0"
    assert staged.mapping_report.total_object_count == 4
    assert staged.mapping_report.mapped_without_known_loss_count == 4
    assert staged.mapping_report.material_loss_count == 0
    assert [item.source_type for item in staged.staged_objects] == [
        "conversation",
        "assistant-message",
        "assistant-message",
        "user-message",
    ]
    assert all(item.authority_class == "external_data" for item in staged.staged_objects)


def test_publication_preserves_exact_json_and_reimport_is_idempotent(tmp_path: Path) -> None:
    environment_id = str(uuid4())
    source = _source(_conversation("selected"))
    first = _stage(source, environment_id=environment_id)
    initialized = _initialized(tmp_path)

    with state.initialize_state_repository(initialized.root) as repository:
        publisher = GenericImportPublisher(repository, first.source_environment)
        preview = publisher.preview(first.stage_result, source, preserve_source=True)
        assert preview.conflicts == ()
        assert len(preview.created_canonical_record_ids) == 4
        result = publisher.publish(
            preview,
            source,
            approved_plan_hash=preview.plan_hash,
            completed_at=COMPLETED,
        )
        assert result.import_batch.status == "published"
        assert result.source_snapshot.preservation_state == "managed_snapshot"
        assert result.source_snapshot.source_root_hash == first.inventory.source_root_hash
        assert result.source_snapshot.managed_path is not None
        assert result.source_snapshot.managed_path.endswith(".json")

        second = _stage(source, environment_id=environment_id)
        second_publisher = GenericImportPublisher(repository, second.source_environment)
        second_preview = second_publisher.preview(
            second.stage_result,
            source,
            preserve_source=False,
        )
        assert second_preview.conflicts == ()
        assert second_preview.created_canonical_record_ids == ()
        assert len(second_preview.reused_canonical_record_ids) == 4
        second_result = second_publisher.publish(
            second_preview,
            source,
            approved_plan_hash=second_preview.plan_hash,
            completed_at="2026-07-04T00:00:02Z",
        )
        assert second_result.created_canonical_record_ids == ()
        assert len(second_result.reused_canonical_record_ids) == 4

        counts = {
            str(row[0]): int(row[1])
            for row in repository.connection.execute(
                "SELECT record_type, COUNT(*) FROM records GROUP BY record_type"
            ).fetchall()
        }
        assert counts["conversation"] == 1
        assert counts["conversation_event"] == 3
        for forbidden in (
            "memory",
            "policy",
            "permission",
            "credential",
            "capability",
            "model_binding",
            "project_checkpoint",
        ):
            assert counts.get(forbidden, 0) == 0


def test_changed_selected_source_creates_conflict_without_overwrite(tmp_path: Path) -> None:
    environment_id = str(uuid4())
    original = _source(_conversation("selected"))
    changed = _source(_conversation("selected", user_text="changed selected text"))
    initialized = _initialized(tmp_path)

    with state.initialize_state_repository(initialized.root) as repository:
        first = _stage(original, environment_id=environment_id)
        publisher = GenericImportPublisher(repository, first.source_environment)
        preview = publisher.preview(first.stage_result, original, preserve_source=False)
        publisher.publish(
            preview,
            original,
            approved_plan_hash=preview.plan_hash,
            completed_at=COMPLETED,
        )

        second = _stage(changed, environment_id=environment_id)
        changed_publisher = GenericImportPublisher(repository, second.source_environment)
        changed_preview = changed_publisher.preview(
            second.stage_result,
            changed,
            preserve_source=False,
        )
        assert {item.reason for item in changed_preview.conflicts} == {"changed-source-object"}
        with pytest.raises(GenericImportPublicationError, match="unresolved conflicts"):
            changed_publisher.publish(
                changed_preview,
                changed,
                approved_plan_hash=changed_preview.plan_hash,
                completed_at="2026-07-04T00:00:02Z",
            )
        row = repository.connection.execute(
            "SELECT COUNT(*) FROM records WHERE record_type = 'conversation_event'"
        ).fetchone()
        assert row is not None
        assert int(row[0]) == 3


def test_unsupported_unknown_and_attachment_surfaces_are_reported() -> None:
    source = _source(
        _conversation(
            "selected",
            assistant_role="developer",
            assistant_content_type="multimodal_text",
            extra_conversation={"provider_future_field": {"not": "trusted"}},
            extra_message={"provider_message_field": True},
            assistant_metadata={
                "model_slug": "synthetic-provider-model",
                "attachments": [{"file_id": "synthetic-file"}],
            },
        )
    )
    result = _stage(source)
    inventory = result.inventory

    assert inventory.unsupported_message_count == 1
    assert inventory.attachment_reference_count == 1
    assert inventory.unknown_field_count == 2
    assert inventory.source_object_count == 7
    assert result.stage_result.mapping_report.material_loss_count == 4
    assert result.stage_result.mapping_report.unsupported_but_preserved_count == 4
    assert {item.reason for item in result.stage_result.quarantined_objects} == {
        "unsupported-source-type"
    }
    assert {item.category for item in result.stage_result.loss_records} == {
        "unsupported-source-type"
    }


def test_missing_parent_cycle_and_malformed_message_are_quarantined() -> None:
    missing = _conversation("selected")
    missing_mapping = cast(dict[str, Any], missing["mapping"])
    cast(dict[str, Any], missing_mapping["user"])["parent"] = "absent"
    missing_result = _stage(_source(missing)).stage_result
    assert {item.reason for item in missing_result.quarantined_objects} == {
        "missing-parent-dependency"
    }

    cycle = _conversation("selected")
    cycle_mapping = cast(dict[str, Any], cycle["mapping"])
    cast(dict[str, Any], cycle_mapping["user"])["parent"] = "assistant"
    cast(dict[str, Any], cycle_mapping["assistant"])["parent"] = "user"
    cycle_result = _stage(_source(cycle)).stage_result
    assert "cyclic-parent-relationship" in {
        item.reason for item in cycle_result.quarantined_objects
    }

    malformed = _conversation("selected")
    malformed_mapping = cast(dict[str, Any], malformed["mapping"])
    cast(dict[str, Any], malformed_mapping["assistant"])["message"] = {
        "id": "broken",
        "author": "not-an-object",
        "content": {"content_type": "text", "parts": ["ignored"]},
    }
    malformed_result = _stage(_source(malformed))
    assert malformed_result.inventory.malformed_object_count == 1
    assert malformed_result.inventory.unsupported_message_count == 1
    assert "unsupported-source-type" in {
        item.reason for item in malformed_result.stage_result.quarantined_objects
    }


@pytest.mark.parametrize(
    ("source", "selected", "match"),
    [
        (b"", ("selected",), "must not be empty"),
        (b"\xff", ("selected",), "valid UTF-8"),
        (b"{}", ("selected",), "source root must be a list"),
        (b"[NaN]", ("selected",), "valid JSON"),
        (
            b'[{"id":"selected","id":"duplicate"}]',
            ("selected",),
            "valid JSON",
        ),
        (_source(_conversation("selected")), (), "selected conversation ids are invalid"),
        (
            _source(_conversation("selected")),
            ("selected", "selected"),
            "contain duplicates",
        ),
        (
            _source(_conversation("selected")),
            ("missing",),
            "were not found",
        ),
    ],
)
def test_invalid_inputs_fail_closed(
    source: bytes,
    selected: tuple[str, ...],
    match: str,
) -> None:
    with pytest.raises(ChatGPTExportImportError, match=match):
        _stage(source, selected)


def test_conflicting_ids_invalid_timestamp_and_resource_limits_fail() -> None:
    conflict = _conversation("selected")
    conflict["conversation_id"] = "different"
    with pytest.raises(ChatGPTExportImportError, match="identifiers conflict"):
        _stage(_source(conflict))

    invalid_time = _conversation("selected")
    invalid_time["create_time"] = -1
    with pytest.raises(ChatGPTExportImportError, match="create time is invalid"):
        _stage(_source(invalid_time))

    tiny_input = ChatGPTExportSourceAdapter(chatgpt_export_source_contract(max_input_bytes=4))
    with pytest.raises(ChatGPTExportImportError, match="byte limit"):
        _stage(_source(_conversation("selected")), adapter=tiny_input)

    tiny_objects = ChatGPTExportSourceAdapter(chatgpt_export_source_contract(max_object_count=2))
    with pytest.raises(ChatGPTExportImportError, match="object count exceeds adapter limit"):
        _stage(_source(_conversation("selected")), adapter=tiny_objects)

    shallow = ChatGPTExportSourceAdapter(chatgpt_export_source_contract(max_nesting_depth=2))
    with pytest.raises(ChatGPTExportImportError, match="nesting"):
        _stage(_source(_conversation("selected")), adapter=shallow)


def test_incompatible_contract_and_static_network_boundary() -> None:
    contract = chatgpt_export_source_contract()
    incompatible = replace(contract, adapter_id="wrong")
    with pytest.raises(ChatGPTExportImportError, match="contract is incompatible"):
        ChatGPTExportSourceAdapter(incompatible)

    source_path = Path(__file__).resolve().parents[1] / "src" / "doll" / "chatgpt_export_import.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imports = {
        alias.name.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imports.update(
        node.module.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    )
    assert not imports & {"httpx", "requests", "socket", "subprocess", "urllib"}


def test_invalid_source_envelopes_fail_closed() -> None:
    invalid_sources = (
        b"",
        b"{",
        b"{}",
        b"[]",
        cast(bytes, "not-bytes"),
    )

    for source in invalid_sources:
        with pytest.raises(ChatGPTExportImportError):
            _stage(source)


def test_unselected_malformed_inventory_is_counted_without_publication() -> None:
    selected = _conversation("selected")
    selected_mapping = cast(dict[str, Any], selected["mapping"])
    cast(dict[str, Any], selected_mapping["root"])["provider_future_node_field"] = True

    unselected = _conversation(
        "not-selected",
        user_text="private unselected marker",
    )
    mapping = cast(dict[str, Any], unselected["mapping"])

    mapping["bad-node"] = "not-an-object"

    mapping["bad-message"] = {
        "id": "bad-message",
        "message": "not-an-object",
    }

    mapping["bad-author"] = {
        "id": "bad-author",
        "message": {
            "id": "bad-author-message",
            "author": "not-an-object",
            "content": {
                "content_type": "text",
                "parts": ["private malformed marker"],
            },
            "metadata": {},
        },
    }

    mapping["bad-content"] = {
        "id": "bad-content",
        "message": {
            "id": "bad-content-message",
            "author": {"role": "user"},
            "content": "not-an-object",
            "metadata": {},
        },
    }

    result = _stage(_source(selected, unselected))

    assert result.inventory.conversation_count == 2
    assert result.inventory.malformed_object_count == 5
    assert result.inventory.unknown_field_count == 1

    summary = json.dumps(result.canonical_summary())
    assert "private unselected marker" not in summary
    assert "private malformed marker" not in summary
