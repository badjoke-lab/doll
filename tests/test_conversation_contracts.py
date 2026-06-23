from __future__ import annotations

from uuid import uuid4

import pytest

from doll import state


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
