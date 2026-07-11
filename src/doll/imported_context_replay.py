"""Replay explicitly selected imported conversation context through a local runtime."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import cast

from doll.generic_import_publication import GenericImportPublicationState
from doll.instruction_origin import InstructionOriginService, InstructionSource
from doll.local_conversation import (
    LocalConversationResult,
    LocalConversationService,
    _message_text,
    _operation_id,
)
from doll.state import ConversationEventRecord, RecordSensitivity, StateError
from doll.state_repository import StateRepository

_MAX_SELECTED_EVENTS = 32
_MAX_ITEM_CHARS = 16_000
_MAX_TOTAL_CHARS = 65_536
_ALLOWED_EVENT_KINDS = frozenset(
    {
        "user_message",
        "assistant_message",
        "system_context_snapshot",
    }
)
_IMPORTED_SOURCE_PREFIX = "imported-source:"


class ImportedContextReplayError(StateError):
    """Base class for imported-context replay failures."""


class ImportedContextReplayValidationError(ImportedContextReplayError):
    """Raised before runtime execution when imported context is invalid."""


@dataclass(frozen=True, slots=True)
class ImportedContextReplayResult:
    """Content-free result for one imported-context local replay turn."""

    source_conversation_id: str
    target_conversation_id: str
    selected_event_ids: tuple[str, ...]
    context_instruction_ids: tuple[str, ...]
    selected_event_count: int
    selected_character_count: int
    target_binding_id: str
    target_runtime_manifest_id: str
    target_model_manifest_id: str
    outcome: str
    prompt_injection_finding_count: int
    secret_redaction_count: int


@dataclass(frozen=True, slots=True)
class _ResolvedImportedContext:
    event: ConversationEventRecord
    text: str
    source_identifier: str
    content_hash: str


@dataclass(slots=True)
class ImportedContextReplayService:
    """Resolve imported canonical events as untrusted context for one local turn."""

    repository: StateRepository
    local_conversation: LocalConversationService
    max_selected_events: int = _MAX_SELECTED_EVENTS
    max_item_chars: int = _MAX_ITEM_CHARS
    max_total_chars: int = _MAX_TOTAL_CHARS

    def __post_init__(self) -> None:
        if self.local_conversation.repository is not self.repository:
            raise ImportedContextReplayValidationError(
                "local conversation service must use the same repository"
            )
        _bounded_positive_int(
            "selected event limit",
            self.max_selected_events,
            maximum=_MAX_SELECTED_EVENTS,
        )
        _bounded_positive_int(
            "item character limit",
            self.max_item_chars,
            maximum=_MAX_ITEM_CHARS,
        )
        _bounded_positive_int(
            "total character limit",
            self.max_total_chars,
            maximum=_MAX_TOTAL_CHARS,
        )
        if self.max_item_chars > self.max_total_chars:
            raise ImportedContextReplayValidationError(
                "item character limit exceeds total character limit"
            )

    def execute_turn(
        self,
        *,
        source_conversation_id: str,
        selected_event_ids: Sequence[str],
        target_conversation_id: str,
        scope_type: str,
        scope_key: str,
        user_text: str,
        operation_id: str,
        parent_event_id: str | None = None,
        max_output_chars: int = 65_536,
        timeout_seconds: float = 60.0,
        sensitivity: RecordSensitivity = "personal",
    ) -> ImportedContextReplayResult:
        """Execute one local turn using only explicit imported text events as context."""

        safe_operation_id = _operation_id(operation_id)
        _message_text("user message", user_text)
        self.local_conversation._require_unused_operation(safe_operation_id)
        self._validate_conversations(
            source_conversation_id=source_conversation_id,
            target_conversation_id=target_conversation_id,
        )
        selected_ids = self._selected_event_ids(selected_event_ids)
        resolved = self._resolve_context(
            source_conversation_id=source_conversation_id,
            selected_event_ids=selected_ids,
        )
        total_chars = sum(len(item.text) for item in resolved)
        retrieval_operation_id = _retrieval_operation_id(safe_operation_id)
        self._require_unused_retrieval_operation(retrieval_operation_id)

        instruction_service = InstructionOriginService(self.repository)
        context_instruction_ids: list[str] = []
        for index, item in enumerate(resolved, start=1):
            origin = instruction_service.create(
                title=f"Imported conversation context {index}",
                content=item.text,
                source=InstructionSource(
                    origin_class="imported_data",
                    actor_type="importer",
                    acquisition_method="import",
                    source_identifier=item.source_identifier,
                    parent_operation_id=retrieval_operation_id,
                    session_id=source_conversation_id,
                    content_hash=item.content_hash,
                    observed_at=item.event.occurred_at,
                ),
                operation_id=retrieval_operation_id,
                sensitivity=sensitivity,
            )
            context_instruction_ids.append(origin.record_id)

        local_result = self.local_conversation.execute_turn(
            conversation_id=target_conversation_id,
            scope_type=scope_type,
            scope_key=scope_key,
            user_text=user_text,
            operation_id=safe_operation_id,
            parent_event_id=parent_event_id,
            context_instruction_ids=tuple(context_instruction_ids),
            max_output_chars=max_output_chars,
            timeout_seconds=timeout_seconds,
            sensitivity=sensitivity,
        )
        return _result(
            source_conversation_id=source_conversation_id,
            target_conversation_id=target_conversation_id,
            selected_event_ids=selected_ids,
            context_instruction_ids=tuple(context_instruction_ids),
            selected_character_count=total_chars,
            local_result=local_result,
        )

    def _validate_conversations(
        self,
        *,
        source_conversation_id: str,
        target_conversation_id: str,
    ) -> None:
        if source_conversation_id == target_conversation_id:
            raise ImportedContextReplayValidationError(
                "source and target conversations must be distinct"
            )
        try:
            source = self.repository.get_record(source_conversation_id)
            target = self.repository.get_record(target_conversation_id)
            self.repository.get_conversation(source_conversation_id)
            self.repository.get_conversation(target_conversation_id)
        except KeyError as exc:
            raise ImportedContextReplayValidationError(
                "source or target conversation does not exist"
            ) from exc
        if source.record_type != "conversation" or source.provenance != "imported":
            raise ImportedContextReplayValidationError(
                "source conversation must be an imported canonical conversation"
            )
        if source.status != "active" or target.status != "active":
            raise ImportedContextReplayValidationError("conversation is not active")

    def _selected_event_ids(self, value: Sequence[str]) -> tuple[str, ...]:
        if isinstance(value, str | bytes):
            raise ImportedContextReplayValidationError("selected event IDs must be a sequence")
        items = tuple(value)
        if not items:
            raise ImportedContextReplayValidationError(
                "at least one imported event must be selected"
            )
        if len(items) > self.max_selected_events:
            raise ImportedContextReplayValidationError(
                "selected event count exceeds the configured limit"
            )
        if any(not isinstance(item, str) or not item.strip() for item in items):
            raise ImportedContextReplayValidationError("selected event ID is invalid")
        if len(set(items)) != len(items):
            raise ImportedContextReplayValidationError("selected event IDs contain duplicates")
        return items

    def _resolve_context(
        self,
        *,
        source_conversation_id: str,
        selected_event_ids: tuple[str, ...],
    ) -> tuple[_ResolvedImportedContext, ...]:
        publication = GenericImportPublicationState(self.repository)
        resolved: list[_ResolvedImportedContext] = []
        total_chars = 0
        for event_id in selected_event_ids:
            try:
                envelope = self.repository.get_record(event_id)
                event = self.repository.get_conversation_event(event_id)
            except KeyError as exc:
                raise ImportedContextReplayValidationError(
                    "selected imported event does not exist"
                ) from exc
            if envelope.record_type != "conversation_event" or envelope.provenance != "imported":
                raise ImportedContextReplayValidationError(
                    "selected event must be an imported canonical event"
                )
            if envelope.status != "active":
                raise ImportedContextReplayValidationError("selected event is not active")
            if event.conversation_id != source_conversation_id:
                raise ImportedContextReplayValidationError(
                    "selected event belongs to another conversation"
                )
            if event.origin_class != "imported_data":
                raise ImportedContextReplayValidationError("selected event is not imported data")
            if event.event_kind not in _ALLOWED_EVENT_KINDS:
                raise ImportedContextReplayValidationError(
                    "selected event kind is unsupported for replay"
                )
            mapping_id = _mapping_id(event.content_reference)
            try:
                mapping = publication.get_source_mapping(mapping_id)
            except KeyError as exc:
                raise ImportedContextReplayValidationError(
                    "selected event source mapping does not exist"
                ) from exc
            if (
                mapping.canonical_record_id != event.event_id
                or mapping.canonical_record_type != "conversation_event"
                or mapping.authority_class != "external_data"
            ):
                raise ImportedContextReplayValidationError(
                    "selected event source mapping does not match the canonical event"
                )
            if (
                event.source_environment_id is not None
                and mapping.source_environment_id != event.source_environment_id
            ):
                raise ImportedContextReplayValidationError(
                    "selected event source environment does not match its mapping"
                )
            text = _payload_text(mapping.payload_json)
            if len(text) > self.max_item_chars:
                raise ImportedContextReplayValidationError(
                    "selected imported context item exceeds the configured character limit"
                )
            total_chars += len(text)
            if total_chars > self.max_total_chars:
                raise ImportedContextReplayValidationError(
                    "selected imported context exceeds the configured total character limit"
                )
            resolved.append(
                _ResolvedImportedContext(
                    event=event,
                    text=text,
                    source_identifier=mapping.source_object_id,
                    content_hash=f"sha256:{hashlib.sha256(text.encode('utf-8')).hexdigest()}",
                )
            )
        return tuple(resolved)

    def _require_unused_retrieval_operation(self, retrieval_operation_id: str) -> None:
        row = self.repository.connection.execute(
            "SELECT 1 FROM records WHERE record_type = 'instruction_origin' "
            "AND json_extract(metadata_json, '$.parent_operation_id') = ? LIMIT 1",
            (retrieval_operation_id,),
        ).fetchone()
        if row is not None:
            raise ImportedContextReplayValidationError(
                "imported context retrieval operation already exists"
            )


def _mapping_id(content_reference: str | None) -> str:
    if content_reference is None or not content_reference.startswith(_IMPORTED_SOURCE_PREFIX):
        raise ImportedContextReplayValidationError(
            "selected event does not reference an imported source mapping"
        )
    mapping_id = content_reference.removeprefix(_IMPORTED_SOURCE_PREFIX)
    if not mapping_id:
        raise ImportedContextReplayValidationError(
            "selected event imported source mapping reference is invalid"
        )
    return mapping_id


def _payload_text(payload_json: str) -> str:
    try:
        payload = json.loads(payload_json)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ImportedContextReplayValidationError(
            "selected event source payload is invalid"
        ) from exc
    if not isinstance(payload, dict):
        raise ImportedContextReplayValidationError(
            "selected event source payload must be an object"
        )
    text = payload.get("text")
    if not isinstance(text, str) or not text.strip():
        raise ImportedContextReplayValidationError(
            "selected event source payload has no supported text"
        )
    return text


def _retrieval_operation_id(operation_id: str) -> str:
    digest = hashlib.sha256(operation_id.encode("utf-8")).hexdigest()[:32]
    return f"imp061.context.{digest}"


def _bounded_positive_int(name: str, value: object, *, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
        raise ImportedContextReplayValidationError(f"{name} is invalid")
    return value


def _result(
    *,
    source_conversation_id: str,
    target_conversation_id: str,
    selected_event_ids: tuple[str, ...],
    context_instruction_ids: tuple[str, ...],
    selected_character_count: int,
    local_result: LocalConversationResult,
) -> ImportedContextReplayResult:
    return ImportedContextReplayResult(
        source_conversation_id=source_conversation_id,
        target_conversation_id=target_conversation_id,
        selected_event_ids=selected_event_ids,
        context_instruction_ids=context_instruction_ids,
        selected_event_count=len(selected_event_ids),
        selected_character_count=selected_character_count,
        target_binding_id=local_result.binding_id,
        target_runtime_manifest_id=local_result.runtime_manifest_id,
        target_model_manifest_id=local_result.model_manifest_id,
        outcome=cast(str, local_result.outcome),
        prompt_injection_finding_count=local_result.prompt_injection_finding_count,
        secret_redaction_count=local_result.secret_redaction_count,
    )
