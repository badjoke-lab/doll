from __future__ import annotations

from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import pytest

from doll import state, workspace


def _workspace(tmp_path: Path) -> workspace.InitializedWorkspace:
    return workspace.initialize_workspace(tmp_path / "workspace")


def _valid_event(
    conversation_id: str,
    *,
    parent_event_ids: tuple[str, ...] = (),
) -> state.ConversationEventRecord:
    return state.ConversationEventRecord(
        event_id=str(uuid4()),
        conversation_id=conversation_id,
        event_kind="assistant_message",
        actor_type="assistant",
        origin_class="model_proposal",
        parent_event_ids=parent_event_ids,
        occurred_at="2026-06-23T12:00:00Z",
    )


def test_noncanonical_record_identifier_is_rejected(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.initialize_state_repository(initialized.root) as repository:
        revision = repository.status().state_revision
        with pytest.raises(
            state.RecordValidationError,
            match="canonical UUID text",
        ):
            repository.create_record(
                record_id=str(uuid4()).upper(),
                record_type="conversation",
            )
        assert repository.status().state_revision == revision


def test_wrong_record_types_are_rejected_as_corrupt(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.initialize_state_repository(initialized.root) as repository:
        generic = repository.create_record(record_type="note")
        with pytest.raises(state.StateCorruptError, match="supported canonical conversation"):
            repository.get_conversation(generic.id)

        conversation = state.ConversationRecord(conversation_id=str(uuid4()))
        repository.save_conversation(conversation)
        with pytest.raises(
            state.StateCorruptError,
            match="supported canonical conversation event",
        ):
            repository.get_conversation_event(conversation.conversation_id)


def test_invalid_conversation_payload_is_rejected_as_corrupt(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    conversation_id = str(uuid4())
    with state.initialize_state_repository(initialized.root) as repository:
        repository.create_record(
            record_id=conversation_id,
            record_type="conversation",
            title="bad\x01title",
            metadata={
                "source_environment_id": None,
                "source_conversation_id": None,
            },
        )
        with pytest.raises(state.StateCorruptError, match="metadata is invalid"):
            repository.get_conversation(conversation_id)


def test_event_payload_shape_failures_are_detected(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    conversation = state.ConversationRecord(conversation_id=str(uuid4()))
    with state.initialize_state_repository(initialized.root) as repository:
        repository.save_conversation(conversation)
        template = _valid_event(conversation.conversation_id).canonical_metadata()

        missing_key = dict(template)
        missing_key.pop("operation_id")
        shape_id = str(uuid4())
        repository.create_record(
            record_id=shape_id,
            record_type="conversation_event",
            metadata=missing_key,
        )
        with pytest.raises(state.StateCorruptError, match="metadata shape"):
            repository.get_conversation_event(shape_id)

        parent_id = str(uuid4())
        invalid_parent = dict(template)
        invalid_parent["parent_event_ids"] = parent_id
        parent_record_id = str(uuid4())
        repository.create_record(
            record_id=parent_record_id,
            record_type="conversation_event",
            metadata=invalid_parent,
        )
        with pytest.raises(state.StateCorruptError, match="parent metadata"):
            repository.get_conversation_event(parent_record_id)

        invalid_extensions = dict(template)
        invalid_extensions["extensions"] = []
        extension_record_id = str(uuid4())
        repository.create_record(
            record_id=extension_record_id,
            record_type="conversation_event",
            metadata=invalid_extensions,
        )
        with pytest.raises(state.StateCorruptError, match="extensions are invalid"):
            repository.get_conversation_event(extension_record_id)

        invalid_kind = dict(template)
        invalid_kind["event_kind"] = "future-provider-event"
        kind_record_id = str(uuid4())
        repository.create_record(
            record_id=kind_record_id,
            record_type="conversation_event",
            metadata=invalid_kind,
        )
        with pytest.raises(state.StateCorruptError, match="event metadata is invalid"):
            repository.get_conversation_event(kind_record_id)


def test_missing_persisted_conversation_is_detected(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    event = _valid_event(str(uuid4()))
    with state.initialize_state_repository(initialized.root) as repository:
        repository.create_record(
            record_id=event.event_id,
            record_type="conversation_event",
            metadata=event.canonical_metadata(),
        )
        with pytest.raises(state.StateCorruptError, match="conversation is missing"):
            repository.get_conversation_event(event.event_id)


def test_missing_and_cross_conversation_persisted_parents_are_detected(
    tmp_path: Path,
) -> None:
    initialized = _workspace(tmp_path)
    first = state.ConversationRecord(conversation_id=str(uuid4()))
    second = state.ConversationRecord(conversation_id=str(uuid4()))
    parent = _valid_event(first.conversation_id)

    with state.initialize_state_repository(initialized.root) as repository:
        repository.save_conversation(first)
        repository.save_conversation(second)
        repository.save_conversation_event(parent)

        missing = _valid_event(
            first.conversation_id,
            parent_event_ids=(str(uuid4()),),
        )
        repository.create_record(
            record_id=missing.event_id,
            record_type="conversation_event",
            metadata=missing.canonical_metadata(),
        )
        with pytest.raises(state.StateCorruptError, match="parent event is missing"):
            repository.get_conversation_event(missing.event_id)

        cross = _valid_event(
            second.conversation_id,
            parent_event_ids=(parent.event_id,),
        )
        repository.create_record(
            record_id=cross.event_id,
            record_type="conversation_event",
            metadata=cross.canonical_metadata(),
        )
        with pytest.raises(state.StateCorruptError, match="another conversation"):
            repository.get_conversation_event(cross.event_id)


def test_invalid_conversation_list_limits_are_rejected(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    conversation = state.ConversationRecord(conversation_id=str(uuid4()))
    with state.initialize_state_repository(initialized.root) as repository:
        repository.save_conversation(conversation)
        with pytest.raises(state.ConversationValidationError, match="list limit"):
            repository.list_conversations(limit=0)
        with pytest.raises(state.ConversationValidationError, match="list limit"):
            repository.list_conversation_events(
                conversation.conversation_id,
                limit=cast(Any, True),
            )


def test_contract_validation_covers_text_enum_parent_and_extension_failures() -> None:
    with pytest.raises(state.ConversationValidationError, match="must be text"):
        state.ConversationRecord(
            conversation_id=str(uuid4()),
            title=cast(Any, 7),
        )
    with pytest.raises(state.ConversationValidationError, match="must not be blank"):
        state.ConversationRecord(
            conversation_id=str(uuid4()),
            source_environment_id="   ",
        )
    with pytest.raises(state.ConversationValidationError, match="maximum length"):
        state.ConversationRecord(
            conversation_id=str(uuid4()),
            title="x" * 241,
        )
    with pytest.raises(state.ConversationValidationError, match="control character"):
        state.ConversationRecord(
            conversation_id=str(uuid4()),
            title="bad\x01title",
        )

    common: dict[str, object] = {
        "event_id": str(uuid4()),
        "conversation_id": str(uuid4()),
        "event_kind": "user_message",
        "actor_type": "user",
        "origin_class": "current_user_instruction",
    }
    with pytest.raises(state.ConversationValidationError, match="actor type"):
        state.ConversationEventRecord(
            **cast(dict[str, Any], {**common, "actor_type": "future-actor"})
        )
    with pytest.raises(state.ConversationValidationError, match="origin class"):
        state.ConversationEventRecord(
            **cast(dict[str, Any], {**common, "origin_class": "future-origin"})
        )
    with pytest.raises(state.ConversationValidationError, match="must be a tuple"):
        state.ConversationEventRecord(
            **cast(dict[str, Any], {**common, "parent_event_ids": []})
        )
    with pytest.raises(state.ConversationValidationError, match="non-negative"):
        state.ConversationEventRecord(
            **cast(dict[str, Any], {**common, "sequence_hint": -1})
        )
    with pytest.raises(state.ConversationValidationError, match="occurred at is invalid"):
        state.ConversationEventRecord(
            **cast(dict[str, Any], {**common, "occurred_at": "not-a-time"})
        )
    with pytest.raises(state.ConversationValidationError, match="extension key"):
        state.ConversationEventRecord(
            **cast(dict[str, Any], {**common, "extensions": {"Bad Key": True}})
        )
    with pytest.raises(state.ConversationValidationError, match="JSON-compatible"):
        state.ConversationEventRecord(
            **cast(dict[str, Any], {**common, "extensions": {"vendor.value": object()}})
        )
