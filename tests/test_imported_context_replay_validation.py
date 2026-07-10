from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import uuid4

import pytest

from doll import state
from doll.imported_context_replay import (
    ImportedContextReplayService,
    ImportedContextReplayValidationError,
    _payload_text,
)
from doll.instruction_origin import InstructionOriginService, InstructionSource
from doll.local_conversation import LocalConversationService
from doll.runtime_adapter import LocalRuntimeBoundary, RuntimeAdapterRegistry
from doll.state import ConversationEventRecord, ConversationRecord
from tests.test_imported_context_replay import (
    FakeTargetAdapter,
    _activate_target_binding,
    _publish_imported_source,
    _service,
    _source_bytes,
    _target_conversation,
    _workspace,
)


def test_service_requires_same_repository_and_valid_limits(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    adapter = FakeTargetAdapter()
    with state.open_state_repository(initialized.root) as first:
        with state.open_state_repository(initialized.root) as second:
            local = LocalConversationService(
                second,
                LocalRuntimeBoundary(RuntimeAdapterRegistry((adapter,))),
            )
            with pytest.raises(
                ImportedContextReplayValidationError,
                match="same repository",
            ):
                ImportedContextReplayService(first, local)

        local = LocalConversationService(
            first,
            LocalRuntimeBoundary(RuntimeAdapterRegistry((adapter,))),
        )
        with pytest.raises(ImportedContextReplayValidationError, match="limit"):
            ImportedContextReplayService(first, local, max_selected_events=0)
        with pytest.raises(
            ImportedContextReplayValidationError,
            match="item character limit exceeds",
        ):
            ImportedContextReplayService(
                first,
                local,
                max_item_chars=100,
                max_total_chars=50,
            )


def test_conversation_and_selection_validation_fail_before_runtime(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    adapter = FakeTargetAdapter()
    with state.open_state_repository(initialized.root) as repository:
        source, events = _publish_imported_source(repository, _source_bytes(str(uuid4())))
        target = _target_conversation(repository)
        service = _service(repository, adapter)

        with pytest.raises(ImportedContextReplayValidationError, match="must be distinct"):
            service.execute_turn(
                source_conversation_id=source.conversation_id,
                selected_event_ids=(events[0].event_id,),
                target_conversation_id=source.conversation_id,
                scope_type="conversation",
                scope_key="unused",
                user_text="Do not run.",
                operation_id="imp061.validation.same-conversation",
            )

        with pytest.raises(ImportedContextReplayValidationError, match="does not exist"):
            service.execute_turn(
                source_conversation_id=source.conversation_id,
                selected_event_ids=(events[0].event_id,),
                target_conversation_id=str(uuid4()),
                scope_type="conversation",
                scope_key="unused",
                user_text="Do not run.",
                operation_id="imp061.validation.missing-target",
            )

        user_source = ConversationRecord(conversation_id=str(uuid4()))
        repository.save_conversation(user_source)
        with pytest.raises(ImportedContextReplayValidationError, match="imported canonical"):
            service.execute_turn(
                source_conversation_id=user_source.conversation_id,
                selected_event_ids=(events[0].event_id,),
                target_conversation_id=target.conversation_id,
                scope_type="conversation",
                scope_key="unused",
                user_text="Do not run.",
                operation_id="imp061.validation.user-source",
            )

        source_record = repository.get_record(source.conversation_id)
        repository.update_record(
            source.conversation_id,
            expected_revision=source_record.revision,
            status="archived",
        )
        with pytest.raises(ImportedContextReplayValidationError, match="not active"):
            service.execute_turn(
                source_conversation_id=source.conversation_id,
                selected_event_ids=(events[0].event_id,),
                target_conversation_id=target.conversation_id,
                scope_type="conversation",
                scope_key="unused",
                user_text="Do not run.",
                operation_id="imp061.validation.archived-source",
            )
        repository.update_record(
            source.conversation_id,
            expected_revision=source_record.revision + 1,
            status="active",
        )

        for selected, pattern, operation in (
            ("not-a-sequence", "must be a sequence", "string-selection"),
            ((), "at least one", "empty-selection"),
            (("",), "ID is invalid", "invalid-selection"),
        ):
            with pytest.raises(ImportedContextReplayValidationError, match=pattern):
                service.execute_turn(
                    source_conversation_id=source.conversation_id,
                    selected_event_ids=selected,
                    target_conversation_id=target.conversation_id,
                    scope_type="conversation",
                    scope_key="unused",
                    user_text="Do not run.",
                    operation_id=f"imp061.validation.{operation}",
                )

        with pytest.raises(ImportedContextReplayValidationError, match="event count"):
            service.execute_turn(
                source_conversation_id=source.conversation_id,
                selected_event_ids=tuple(str(uuid4()) for _ in range(33)),
                target_conversation_id=target.conversation_id,
                scope_type="conversation",
                scope_key="unused",
                user_text="Do not run.",
                operation_id="imp061.validation.too-many-events",
            )

        assert adapter.prompts == []


def test_event_state_mapping_and_total_limit_fail_closed(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    adapter = FakeTargetAdapter()
    with state.open_state_repository(initialized.root) as repository:
        source, events = _publish_imported_source(repository, _source_bytes(str(uuid4())))
        target = _target_conversation(repository)
        _activate_target_binding(repository, adapter)
        service = _service(repository, adapter)

        with pytest.raises(ImportedContextReplayValidationError, match="does not exist"):
            service.execute_turn(
                source_conversation_id=source.conversation_id,
                selected_event_ids=(str(uuid4()),),
                target_conversation_id=target.conversation_id,
                scope_type="conversation",
                scope_key="imported-replay-target",
                user_text="Do not run.",
                operation_id="imp061.validation.missing-event",
            )

        event_record = repository.get_record(events[0].event_id)
        repository.update_record(
            events[0].event_id,
            expected_revision=event_record.revision,
            status="archived",
        )
        with pytest.raises(ImportedContextReplayValidationError, match="not active"):
            service.execute_turn(
                source_conversation_id=source.conversation_id,
                selected_event_ids=(events[0].event_id,),
                target_conversation_id=target.conversation_id,
                scope_type="conversation",
                scope_key="imported-replay-target",
                user_text="Do not run.",
                operation_id="imp061.validation.archived-event",
            )
        repository.update_record(
            events[0].event_id,
            expected_revision=event_record.revision + 1,
            status="active",
        )

        wrong_origin = ConversationEventRecord(
            event_id=str(uuid4()),
            conversation_id=source.conversation_id,
            event_kind="user_message",
            actor_type="user",
            origin_class="current_user_instruction",
        )
        repository.save_conversation_event(wrong_origin, provenance="imported")
        with pytest.raises(ImportedContextReplayValidationError, match="not imported data"):
            service.execute_turn(
                source_conversation_id=source.conversation_id,
                selected_event_ids=(wrong_origin.event_id,),
                target_conversation_id=target.conversation_id,
                scope_type="conversation",
                scope_key="imported-replay-target",
                user_text="Do not run.",
                operation_id="imp061.validation.wrong-origin",
            )

        missing_mapping = ConversationEventRecord(
            event_id=str(uuid4()),
            conversation_id=source.conversation_id,
            event_kind="user_message",
            actor_type="user",
            origin_class="imported_data",
            content_reference=f"imported-source:{uuid4()}",
        )
        repository.save_conversation_event(missing_mapping, provenance="imported")
        with pytest.raises(ImportedContextReplayValidationError, match="mapping does not exist"):
            service.execute_turn(
                source_conversation_id=source.conversation_id,
                selected_event_ids=(missing_mapping.event_id,),
                target_conversation_id=target.conversation_id,
                scope_type="conversation",
                scope_key="imported-replay-target",
                user_text="Do not run.",
                operation_id="imp061.validation.missing-mapping",
            )

        limited = ImportedContextReplayService(
            repository,
            service.local_conversation,
            max_item_chars=40,
            max_total_chars=60,
        )
        with pytest.raises(ImportedContextReplayValidationError, match="total character limit"):
            limited.execute_turn(
                source_conversation_id=source.conversation_id,
                selected_event_ids=tuple(event.event_id for event in events),
                target_conversation_id=target.conversation_id,
                scope_type="conversation",
                scope_key="imported-replay-target",
                user_text="Do not run.",
                operation_id="imp061.validation.total-limit",
            )

        assert adapter.prompts == []


def test_duplicate_retrieval_operation_fails_before_runtime(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    adapter = FakeTargetAdapter()
    with state.open_state_repository(initialized.root) as repository:
        source, events = _publish_imported_source(repository, _source_bytes(str(uuid4())))
        target = _target_conversation(repository)
        _activate_target_binding(repository, adapter)
        operation_id = "imp061.validation.duplicate-retrieval"
        digest = hashlib.sha256(operation_id.encode("utf-8")).hexdigest()[:32]
        retrieval_id = f"imp061.context.{digest}"
        InstructionOriginService(repository).create(
            title="Existing imported context",
            content="Existing context",
            source=InstructionSource(
                origin_class="imported_data",
                actor_type="importer",
                acquisition_method="import",
                source_identifier="synthetic-source",
                parent_operation_id=retrieval_id,
            ),
            operation_id=retrieval_id,
        )

        with pytest.raises(ImportedContextReplayValidationError, match="already exists"):
            _service(repository, adapter).execute_turn(
                source_conversation_id=source.conversation_id,
                selected_event_ids=(events[0].event_id,),
                target_conversation_id=target.conversation_id,
                scope_type="conversation",
                scope_key="imported-replay-target",
                user_text="Do not run.",
                operation_id=operation_id,
            )
        assert adapter.prompts == []


def test_payload_text_rejects_invalid_shapes() -> None:
    for payload, pattern in (
        ("not-json", "payload is invalid"),
        ("[]", "must be an object"),
        ("{}", "no supported text"),
    ):
        with pytest.raises(ImportedContextReplayValidationError, match=pattern):
            _payload_text(payload)
