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
from doll.generic_import_publication import (
    GenericImportPublicationError,
    GenericImportPublisher,
)
from doll.ollama_session_import import (
    OllamaSessionImportError,
    OllamaSessionSourceAdapter,
    OllamaSessionStageResult,
    ollama_session_source_contract,
)
from doll.portability import PortabilityContractError, SourceAdapterContract
from tests.import_publication_support import _initialized

STARTED = "2026-06-28T17:00:00Z"
COMPLETED = "2026-06-28T17:00:01Z"


def _message(
    message_id: str,
    role: str,
    content: str,
    *,
    parents: list[str] | None = None,
    model: str | None = "synthetic-local-model",
    created_at: str | None = STARTED,
    attachments: list[object] | None = None,
    tool_calls: list[object] | None = None,
) -> dict[str, object]:
    return {
        "message_id": message_id,
        "role": role,
        "content": content,
        "created_at": created_at,
        "parent_message_ids": parents or [],
        "model": model,
        "attachments": attachments or [],
        "tool_calls": tool_calls or [],
    }


def _conversation(
    conversation_id: str = "conversation-a",
    *,
    messages: list[object] | None = None,
) -> dict[str, object]:
    return {
        "conversation_id": conversation_id,
        "title": "Synthetic local session",
        "created_at": STARTED,
        "messages": messages
        or [
            _message("message-1", "user", "hello"),
            _message("message-2", "assistant", "world", parents=["message-1"]),
        ],
    }


def _bundle(
    environment_id: str,
    *,
    conversations: list[object] | None = None,
    runtime_version: str | None = "test-runtime",
    exported_at: str = STARTED,
    format_name: str = "ollama-api-chat-session",
    format_version: str = "1",
) -> bytes:
    return json.dumps(
        {
            "format": format_name,
            "format_version": format_version,
            "source_environment_id": environment_id,
            "runtime_version": runtime_version,
            "exported_at": exported_at,
            "conversations": conversations if conversations is not None else [_conversation()],
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()


def _rich_bundle(environment_id: str) -> bytes:
    attachment = {
        "attachment_id": "attachment-1",
        "name": "diagram.png",
        "media_type": "image/png",
        "size_bytes": 123,
        "sha256": "a" * 64,
    }
    tool_call = {
        "tool_call_id": "tool-1",
        "name": "lookup",
        "arguments": {"query": "synthetic"},
    }
    return _bundle(
        environment_id,
        conversations=[
            _conversation(
                messages=[
                    _message("message-1", "user", "hello", model=None, created_at=None),
                    _message(
                        "message-2",
                        "assistant",
                        "world",
                        parents=["message-1"],
                        attachments=[attachment],
                        tool_calls=[tool_call],
                    ),
                ]
            )
        ],
    )


def _stage(
    source_bytes: bytes,
    *,
    batch_id: str | None = None,
    adapter: OllamaSessionSourceAdapter | None = None,
) -> OllamaSessionStageResult:
    return (adapter or OllamaSessionSourceAdapter()).stage(
        source_bytes,
        import_batch_id=batch_id or str(uuid4()),
        started_at=STARTED,
    )


def test_contract_and_supported_bundle_inventory_are_deterministic() -> None:
    environment_id = str(uuid4())
    batch_id = str(uuid4())
    source_bytes = _rich_bundle(environment_id)
    adapter = OllamaSessionSourceAdapter()

    first = _stage(source_bytes, batch_id=batch_id, adapter=adapter)
    second = _stage(source_bytes, batch_id=batch_id, adapter=adapter)

    assert first == second
    assert adapter.contract.adapter_id == "ollama-api-session"
    assert adapter.contract.adapter_version == "1.0.0"
    assert adapter.contract.network_behavior == "none"
    assert adapter.contract.attachment_behavior == "metadata_only"
    assert adapter.contract.branch_behavior == "preserve"
    assert first.source_environment.environment_id == environment_id
    assert first.source_environment.environment_class == "local-ai-runtime-session"
    assert first.source_environment.provider_id is None
    assert first.source_environment.application_id == "ollama"
    assert first.source_environment.interface_id == "ollama.api"
    assert first.source_environment.runtime_id == "ollama.local"
    assert first.source_environment.export_format == "ollama-api-chat-session"
    assert first.source_environment.export_version == "1"

    inventory = first.inventory
    assert inventory.source_root_hash == hashlib.sha256(source_bytes).hexdigest()
    assert inventory.format_version == "1"
    assert inventory.runtime_version == "test-runtime"
    assert inventory.conversation_count == 1
    assert inventory.message_count == 2
    assert inventory.attachment_count == 1
    assert inventory.tool_call_count == 1
    assert inventory.source_object_count == 5
    assert "hello" not in json.dumps(inventory.canonical_summary())

    staged = first.stage_result
    assert staged.source_root_hash == inventory.source_root_hash
    assert staged.import_batch.source_root_hash == inventory.source_root_hash
    assert staged.import_batch.adapter_id == "ollama-api-session"
    assert staged.import_batch.adapter_version == "1.0.0"
    assert staged.mapping_report.total_object_count == 5
    assert staged.mapping_report.mapped_without_known_loss_count == 4
    assert staged.mapping_report.mapped_with_transformation_count == 1
    assert staged.mapping_report.material_loss_count == 1
    assert {loss.category for loss in staged.loss_records} == {
        "attachment-metadata-only"
    }
    assert [item.source_type for item in staged.staged_objects] == [
        "attachment",
        "conversation",
        "user-message",
        "assistant-message",
        "tool-request",
    ]
    summary = first.canonical_summary()
    assert summary["source_environment"] == first.source_environment.canonical_metadata()
    json.dumps(summary, allow_nan=False)


def test_publication_preserves_source_and_reimport_is_idempotent(tmp_path: Path) -> None:
    environment_id = str(uuid4())
    source_bytes = _rich_bundle(environment_id)
    first = _stage(source_bytes)
    initialized = _initialized(tmp_path)

    with state.initialize_state_repository(initialized.root) as repository:
        publisher = GenericImportPublisher(repository, first.source_environment)
        preview = publisher.preview(
            first.stage_result,
            source_bytes,
            preserve_source=True,
        )
        assert preview.conflicts == ()
        assert len(preview.created_canonical_record_ids) == 5
        result = publisher.publish(
            preview,
            source_bytes,
            approved_plan_hash=preview.plan_hash,
            completed_at=COMPLETED,
        )
        assert result.import_batch.status == "published"
        assert result.source_snapshot.preservation_state == "managed_snapshot"
        assert result.source_snapshot.source_root_hash == first.inventory.source_root_hash
        assert result.source_snapshot.managed_path is not None
        assert len(result.created_canonical_record_ids) == 5

        second = _stage(source_bytes)
        second_publisher = GenericImportPublisher(repository, second.source_environment)
        second_preview = second_publisher.preview(
            second.stage_result,
            source_bytes,
            preserve_source=False,
        )
        assert second_preview.conflicts == ()
        assert second_preview.created_canonical_record_ids == ()
        assert len(second_preview.reused_canonical_record_ids) == 5
        second_result = second_publisher.publish(
            second_preview,
            source_bytes,
            approved_plan_hash=second_preview.plan_hash,
            completed_at="2026-06-28T17:00:02Z",
        )
        assert second_result.created_canonical_record_ids == ()
        assert len(second_result.reused_canonical_record_ids) == 5

        counts = {
            str(row[0]): int(row[1])
            for row in repository.connection.execute(
                "SELECT record_type, COUNT(*) FROM records GROUP BY record_type"
            ).fetchall()
        }
        assert counts["conversation"] == 1
        assert counts["conversation_event"] == 4
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


def test_changed_source_creates_review_conflict_without_overwrite(tmp_path: Path) -> None:
    environment_id = str(uuid4())
    original = _bundle(environment_id)
    changed = _bundle(
        environment_id,
        conversations=[
            _conversation(
                messages=[
                    _message("message-1", "user", "changed"),
                    _message("message-2", "assistant", "world", parents=["message-1"]),
                ]
            )
        ],
    )
    initialized = _initialized(tmp_path)

    with state.initialize_state_repository(initialized.root) as repository:
        first = _stage(original)
        publisher = GenericImportPublisher(repository, first.source_environment)
        preview = publisher.preview(first.stage_result, original, preserve_source=False)
        publisher.publish(
            preview,
            original,
            approved_plan_hash=preview.plan_hash,
            completed_at=COMPLETED,
        )

        second = _stage(changed)
        changed_preview = GenericImportPublisher(
            repository, second.source_environment
        ).preview(second.stage_result, changed, preserve_source=False)
        assert {conflict.reason for conflict in changed_preview.conflicts} == {
            "changed-source-object"
        }
        with pytest.raises(GenericImportPublicationError, match="unresolved conflicts"):
            GenericImportPublisher(repository, second.source_environment).publish(
                changed_preview,
                changed,
                approved_plan_hash=changed_preview.plan_hash,
                completed_at="2026-06-28T17:00:02Z",
            )
        row = repository.connection.execute(
            "SELECT COUNT(*) FROM records WHERE record_type = 'conversation_event'"
        ).fetchone()
        assert row is not None
        assert int(row[0]) == 2


def test_duplicate_missing_cycle_and_unsupported_role_are_quarantined() -> None:
    environment_id = str(uuid4())

    repeated_conversation = _conversation(
        messages=[
            _message("message-1", "user", "same"),
            _message("message-2", "assistant", "same", parents=["message-1"]),
        ]
    )
    identical = _bundle(
        environment_id,
        conversations=[repeated_conversation, repeated_conversation],
    )
    identical_result = _stage(identical).stage_result
    assert identical_result.duplicate_object_count == 3
    assert len(identical_result.staged_objects) == 3

    conflicting = _bundle(
        environment_id,
        conversations=[
            _conversation(
                messages=[
                    _message("message-1", "user", "a"),
                    _message("message-1", "user", "b"),
                ]
            )
        ],
    )
    conflicting_result = _stage(conflicting).stage_result
    assert {item.reason for item in conflicting_result.quarantined_objects} == {
        "conflicting-duplicate"
    }

    missing = _bundle(
        environment_id,
        conversations=[
            _conversation(
                messages=[
                    _message("message-1", "user", "missing", parents=["absent"]),
                ]
            )
        ],
    )
    missing_result = _stage(missing).stage_result
    assert {item.reason for item in missing_result.quarantined_objects} == {
        "missing-parent-dependency"
    }

    cycle = _bundle(
        environment_id,
        conversations=[
            _conversation(
                messages=[
                    _message("message-1", "user", "a", parents=["message-2"]),
                    _message("message-2", "assistant", "b", parents=["message-1"]),
                ]
            )
        ],
    )
    cycle_result = _stage(cycle).stage_result
    assert {item.reason for item in cycle_result.quarantined_objects} == {
        "cyclic-parent-relationship"
    }

    unsupported = _bundle(
        environment_id,
        conversations=[
            _conversation(messages=[_message("message-1", "developer", "data")])
        ],
    )
    unsupported_result = _stage(unsupported).stage_result
    assert {item.reason for item in unsupported_result.quarantined_objects} == {
        "unsupported-source-type"
    }
    assert unsupported_result.mapping_report.unsupported_but_preserved_count == 1
    assert all(
        item.authority_class == "external_data"
        for item in unsupported_result.staged_objects
    )


@pytest.mark.parametrize(
    ("source_bytes", "message"),
    [
        (b"", "must not be empty"),
        (b"\xff", "UTF-8"),
        (b"[]", "source root must be an object"),
        (b'{"value":NaN}', "canonical JSON"),
        (
            b'{"format":"a","format":"b"}',
            "canonical JSON",
        ),
    ],
)
def test_root_parser_rejects_invalid_bytes(source_bytes: bytes, message: str) -> None:
    with pytest.raises(OllamaSessionImportError, match=message):
        _stage(source_bytes)


def test_root_contract_and_resource_limits_fail_closed() -> None:
    environment_id = str(uuid4())
    valid = json.loads(_bundle(environment_id))

    cases: list[tuple[dict[str, object], str]] = []
    missing = dict(valid)
    missing.pop("runtime_version")
    cases.append((missing, "source root shape"))
    wrong_format = dict(valid)
    wrong_format["format"] = "other"
    cases.append((wrong_format, "format is unsupported"))
    wrong_version = dict(valid)
    wrong_version["format_version"] = "2"
    cases.append((wrong_version, "version is unsupported"))
    wrong_runtime = dict(valid)
    wrong_runtime["runtime_version"] = 1
    cases.append((wrong_runtime, "runtime version must be text"))
    wrong_time = dict(valid)
    wrong_time["exported_at"] = "2026-06-28"
    cases.append((wrong_time, "timezone"))
    wrong_conversations = dict(valid)
    wrong_conversations["conversations"] = {}
    cases.append((wrong_conversations, "conversations must be a list"))

    for payload, message in cases:
        with pytest.raises(
            (OllamaSessionImportError, PortabilityContractError), match=message
        ):
            _stage(json.dumps(payload, separators=(",", ":")).encode())

    with pytest.raises(OllamaSessionImportError, match="source bytes must be bytes"):
        _stage(cast(Any, "text"))
    small_input = OllamaSessionSourceAdapter(
        ollama_session_source_contract(max_input_bytes=10)
    )
    with pytest.raises(OllamaSessionImportError, match="byte limit"):
        _stage(_bundle(environment_id), adapter=small_input)
    small_objects = OllamaSessionSourceAdapter(
        ollama_session_source_contract(max_object_count=1)
    )
    with pytest.raises(OllamaSessionImportError, match="object count"):
        _stage(_bundle(environment_id), adapter=small_objects)


def test_conversation_and_message_contracts_fail_closed() -> None:
    environment_id = str(uuid4())

    bad_conversations: list[object] = [
        "bad",
        {
            "conversation_id": "conversation-a",
            "title": "title",
            "created_at": STARTED,
        },
        {
            **_conversation(),
            "conversation_id": "bad\nid",
        },
        {
            **_conversation(),
            "title": 1,
        },
        {
            **_conversation(),
            "created_at": "bad",
        },
        {
            **_conversation(),
            "messages": {},
        },
    ]
    for conversation in bad_conversations:
        with pytest.raises(OllamaSessionImportError):
            _stage(_bundle(environment_id, conversations=[conversation]))

    base = _message("message-1", "user", "content")
    bad_messages: list[object] = [
        "bad",
        {key: value for key, value in base.items() if key != "model"},
        {**base, "message_id": "bad\nid"},
        {**base, "role": 1},
        {**base, "content": 1},
        {**base, "created_at": "bad"},
        {**base, "model": 1},
        {**base, "parent_message_ids": {}},
        {**base, "parent_message_ids": [1]},
    ]
    for message in bad_messages:
        with pytest.raises(OllamaSessionImportError):
            _stage(
                _bundle(
                    environment_id,
                    conversations=[_conversation(messages=[message])],
                )
            )


def test_attachment_and_tool_call_contracts_fail_closed() -> None:
    environment_id = str(uuid4())
    attachment = {
        "attachment_id": "attachment-1",
        "name": "file",
        "media_type": None,
        "size_bytes": 0,
        "sha256": None,
    }
    tool_call = {
        "tool_call_id": "tool-1",
        "name": "lookup",
        "arguments": {},
    }

    bad_attachments: list[object] = [
        "bad",
        {key: value for key, value in attachment.items() if key != "sha256"},
        {**attachment, "attachment_id": "bad\nid"},
        {**attachment, "name": 1},
        {**attachment, "media_type": 1},
        {**attachment, "size_bytes": True},
        {**attachment, "size_bytes": -1},
        {**attachment, "sha256": "bad"},
    ]
    for item in bad_attachments:
        with pytest.raises(OllamaSessionImportError):
            _stage(
                _bundle(
                    environment_id,
                    conversations=[
                        _conversation(
                            messages=[
                                _message(
                                    "message-1",
                                    "user",
                                    "content",
                                    attachments=[item],
                                )
                            ]
                        )
                    ],
                )
            )

    bad_tools: list[object] = [
        "bad",
        {key: value for key, value in tool_call.items() if key != "arguments"},
        {**tool_call, "tool_call_id": "bad\nid"},
        {**tool_call, "name": 1},
        {**tool_call, "arguments": []},
    ]
    for item in bad_tools:
        with pytest.raises(OllamaSessionImportError):
            _stage(
                _bundle(
                    environment_id,
                    conversations=[
                        _conversation(
                            messages=[
                                _message(
                                    "message-1",
                                    "assistant",
                                    "content",
                                    tool_calls=[item],
                                )
                            ]
                        )
                    ],
                )
            )


def test_adapter_rejects_incompatible_contract() -> None:
    base = ollama_session_source_contract()
    incompatible: list[SourceAdapterContract] = [
        replace(base, adapter_id="other"),
        replace(base, adapter_version="2"),
        replace(base, source_environment_class="other"),
        replace(base, network_behavior="declared_read_only"),
    ]
    for contract in incompatible:
        with pytest.raises(OllamaSessionImportError, match="incompatible"):
            OllamaSessionSourceAdapter(contract)


def test_module_has_no_network_process_or_runtime_dependency() -> None:
    source = Path("src/doll/ollama_session_import.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported.update(
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    )
    assert "socket" not in imported
    assert "subprocess" not in imported
    assert "urllib" not in imported
    assert "requests" not in imported
    assert "httpx" not in imported
    assert "doll.ollama_adapter" not in imported
    assert "doll.runtime_adapter" not in imported
