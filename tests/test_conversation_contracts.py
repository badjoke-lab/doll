from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest

from doll import state, workspace


def test_canonical_conversation_contract_normalizes_source_identity() -> None:
    conversation = state.ConversationRecord(
        conversation_id=str(uuid4()),
        title="  Portable conversation  ",
        source_environment_id="local-app:alpha",
        source_conversation_id="conversation-42",
    )

    assert conversation.title == "Portable conversation"
    assert conversation.canonical_metadata() == {
        "source_environment_id": "local-app:alpha",
        "source_conversation_id": "conversation-42",
    }


def test_canonical_event_contract_preserves_graph_and_environment_fields() -> None:
    parent_id = str(uuid4())
    event = state.ConversationEventRecord(
        event_id=str(uuid4()),
        conversation_id=str(uuid4()),
        event_kind="assistant_message",
        actor_type="assistant",
        origin_class="model_proposal",
        parent_event_ids=(parent_id,),
        sequence_hint=8,
        content_reference="artifact:message-8",
        occurred_at="2026-06-23T10:00:00Z",
        provider_id="provider-a",
        application_id="application-b",
        interface_id="interface-c",
        model_manifest_id="model-d",
        runtime_adapter_id="runtime-e",
        extensions={"Vendor.Trace": "trace-1"},
    )

    metadata = event.canonical_metadata()
    assert metadata["parent_event_ids"] == [parent_id]
    assert metadata["provider_id"] == "provider-a"
    assert metadata["application_id"] == "application-b"
    assert metadata["interface_id"] == "interface-c"
    assert metadata["model_manifest_id"] == "model-d"
    assert metadata["runtime_adapter_id"] == "runtime-e"
    assert metadata["extensions"] == {"vendor.trace": "trace-1"}
    assert "provider_native_object" not in metadata


def test_canonical_event_contract_rejects_invalid_relationships() -> None:
    event_id = str(uuid4())
    with pytest.raises(state.ConversationValidationError, match="own parent"):
        state.ConversationEventRecord(
            event_id=event_id,
            conversation_id=str(uuid4()),
            event_kind="branch_creation",
            actor_type="user",
            origin_class="current_user_instruction",
            parent_event_ids=(event_id,),
        )

    parent_id = str(uuid4())
    with pytest.raises(state.ConversationValidationError, match="must be unique"):
        state.ConversationEventRecord(
            event_id=str(uuid4()),
            conversation_id=str(uuid4()),
            event_kind="edit_regeneration",
            actor_type="assistant",
            origin_class="model_proposal",
            parent_event_ids=(parent_id, parent_id),
        )


def test_canonical_event_contract_rejects_invalid_time_and_unknown_kind() -> None:
    with pytest.raises(state.ConversationValidationError, match="timezone-aware"):
        state.ConversationEventRecord(
            event_id=str(uuid4()),
            conversation_id=str(uuid4()),
            event_kind="user_message",
            actor_type="user",
            origin_class="current_user_instruction",
            occurred_at="2026-06-23T10:00:00",
        )

    with pytest.raises(state.ConversationValidationError, match="source event kind"):
        state.ConversationEventRecord(
            event_id=str(uuid4()),
            conversation_id=str(uuid4()),
            event_kind="imported_unknown_event",
            actor_type="importer",
            origin_class="imported_data",
        )


def _initialized_workspace(tmp_path: Path) -> workspace.InitializedWorkspace:
    return workspace.initialize_workspace(tmp_path / "workspace")


def test_conversation_state_survives_close_and_read_only_reopen(tmp_path: Path) -> None:
    initialized = _initialized_workspace(tmp_path)
    conversation = state.ConversationRecord(
        conversation_id=str(uuid4()),
        title="Portable history",
        source_environment_id="source-environment",
        source_conversation_id="source-conversation",
    )
    parent = state.ConversationEventRecord(
        event_id=str(uuid4()),
        conversation_id=conversation.conversation_id,
        event_kind="user_message",
        actor_type="user",
        origin_class="current_user_instruction",
        sequence_hint=1,
        content_reference="artifact:user-1",
        occurred_at="2026-06-23T10:00:00Z",
    )
    child = state.ConversationEventRecord(
        event_id=str(uuid4()),
        conversation_id=conversation.conversation_id,
        event_kind="assistant_message",
        actor_type="assistant",
        origin_class="model_proposal",
        parent_event_ids=(parent.event_id,),
        sequence_hint=2,
        content_reference="artifact:assistant-2",
        occurred_at="2026-06-23T10:00:01Z",
        provider_id="provider-a",
        application_id="application-b",
        interface_id="interface-c",
        model_manifest_id="model-d",
        runtime_adapter_id="runtime-e",
        operation_id="operation-f",
    )

    with state.initialize_state_repository(initialized.root) as repository:
        assert repository.save_conversation(conversation) == conversation
        assert repository.save_conversation_event(parent) == parent
        assert repository.save_conversation_event(child) == child

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        assert repository.get_conversation(conversation.conversation_id) == conversation
        assert repository.get_conversation_event(child.event_id) == child
        assert repository.list_conversations() == (conversation,)
        assert repository.list_conversation_events(conversation.conversation_id) == (
            parent,
            child,
        )
        with pytest.raises(state.ReadOnlyStateError):
            repository.save_conversation(state.ConversationRecord(conversation_id=str(uuid4())))


def test_conversation_event_listing_uses_deterministic_view_order(tmp_path: Path) -> None:
    initialized = _initialized_workspace(tmp_path)
    conversation = state.ConversationRecord(conversation_id=str(uuid4()))
    event_two = state.ConversationEventRecord(
        event_id=str(uuid4()),
        conversation_id=conversation.conversation_id,
        event_kind="assistant_message",
        actor_type="assistant",
        origin_class="model_proposal",
        sequence_hint=2,
        occurred_at="2026-06-23T10:00:02Z",
    )
    event_unsequenced = state.ConversationEventRecord(
        event_id=str(uuid4()),
        conversation_id=conversation.conversation_id,
        event_kind="error",
        actor_type="system",
        origin_class="runtime_output",
        occurred_at="2026-06-23T10:00:03Z",
    )
    event_one = state.ConversationEventRecord(
        event_id=str(uuid4()),
        conversation_id=conversation.conversation_id,
        event_kind="user_message",
        actor_type="user",
        origin_class="current_user_instruction",
        sequence_hint=1,
        occurred_at="2026-06-23T10:00:01Z",
    )

    with state.initialize_state_repository(initialized.root) as repository:
        repository.save_conversation(conversation)
        repository.save_conversation_event(event_two)
        repository.save_conversation_event(event_unsequenced)
        repository.save_conversation_event(event_one)
        assert repository.list_conversation_events(conversation.conversation_id) == (
            event_one,
            event_two,
            event_unsequenced,
        )
        assert repository.list_conversation_events(
            conversation.conversation_id,
            limit=2,
        ) == (event_one, event_two)


def test_rejected_relationships_and_duplicate_ids_preserve_revision(
    tmp_path: Path,
) -> None:
    initialized = _initialized_workspace(tmp_path)
    first = state.ConversationRecord(conversation_id=str(uuid4()))
    second = state.ConversationRecord(conversation_id=str(uuid4()))
    parent = state.ConversationEventRecord(
        event_id=str(uuid4()),
        conversation_id=first.conversation_id,
        event_kind="user_message",
        actor_type="user",
        origin_class="current_user_instruction",
    )

    with state.initialize_state_repository(initialized.root) as repository:
        repository.save_conversation(first)
        repository.save_conversation(second)
        repository.save_conversation_event(parent)
        revision = repository.status().state_revision

        with pytest.raises(state.RecordValidationError, match="already exists"):
            repository.save_conversation(first)
        assert repository.status().state_revision == revision

        missing_parent = state.ConversationEventRecord(
            event_id=str(uuid4()),
            conversation_id=first.conversation_id,
            event_kind="assistant_message",
            actor_type="assistant",
            origin_class="model_proposal",
            parent_event_ids=(str(uuid4()),),
        )
        with pytest.raises(state.ConversationValidationError, match="does not exist"):
            repository.save_conversation_event(missing_parent)
        assert repository.status().state_revision == revision

        cross_parent = state.ConversationEventRecord(
            event_id=str(uuid4()),
            conversation_id=second.conversation_id,
            event_kind="assistant_message",
            actor_type="assistant",
            origin_class="model_proposal",
            parent_event_ids=(parent.event_id,),
        )
        with pytest.raises(
            state.ConversationValidationError,
            match="different conversation",
        ):
            repository.save_conversation_event(cross_parent)
        assert repository.status().state_revision == revision


def test_conversation_state_rejects_corrupt_metadata(tmp_path: Path) -> None:
    initialized = _initialized_workspace(tmp_path)
    conversation = state.ConversationRecord(conversation_id=str(uuid4()))

    with state.initialize_state_repository(initialized.root) as repository:
        repository.save_conversation(conversation)
        repository.connection.execute(
            "UPDATE records SET metadata_json = ? WHERE id = ?",
            (json.dumps({"unexpected": True}), conversation.conversation_id),
        )
        with pytest.raises(state.StateCorruptError, match="metadata shape"):
            repository.get_conversation(conversation.conversation_id)


def test_explicit_record_identifier_validation_preserves_revision(tmp_path: Path) -> None:
    initialized = _initialized_workspace(tmp_path)
    with state.initialize_state_repository(initialized.root) as repository:
        revision = repository.status().state_revision
        with pytest.raises(state.RecordValidationError, match="identifier is invalid"):
            repository.create_record(
                record_id="not-a-uuid",
                record_type="conversation",
            )
        assert repository.status().state_revision == revision
