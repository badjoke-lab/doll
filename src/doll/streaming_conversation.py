"""Canonical local conversation execution from a bounded streaming transcript."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from doll.audit import AuditService
from doll.instruction_origin import (
    InstructionOriginError,
    InstructionOriginService,
    InstructionSource,
)
from doll.local_conversation import (
    LocalConversationError,
    LocalConversationPersistenceError,
    LocalConversationResult,
    LocalConversationRollbackError,
    LocalConversationService,
    LocalConversationValidationError,
    _context_ids,
    _CreatedTurnState,
    _message_text,
    _operation_id,
    _render_prompt,
    _runtime_model_id,
    _sha256_text,
)
from doll.model_manifest import ModelManifestService, ModelManifestValidationError
from doll.prompt_injection import PromptDefenseService, PromptInjectionError
from doll.runtime_adapter import (
    MAX_RUNTIME_INPUT_CHARS,
    RuntimeCancellationToken,
    RuntimeContractError,
    RuntimeFailureCode,
    RuntimeGenerationRequest,
    RuntimeGenerationResult,
    RuntimeStreamEvent,
    RuntimeStreamResult,
)
from doll.secret_detection import redact_text
from doll.state import ReadOnlyStateError, RecordSensitivity


@dataclass(frozen=True, slots=True)
class LocalStreamingConversationResult:
    """Canonical turn result plus a transient presentation-only stream transcript."""

    turn: LocalConversationResult
    display_events: tuple[RuntimeStreamEvent, ...] = field(repr=False)


@dataclass(slots=True)
class LocalStreamingConversationService(LocalConversationService):
    """Execute one local turn from a validated stream without persisting partial deltas."""

    def execute_streaming_turn(
        self,
        *,
        conversation_id: str,
        scope_type: str,
        scope_key: str,
        user_text: str,
        operation_id: str,
        parent_event_id: str | None = None,
        context_instruction_ids: Sequence[str] = (),
        max_output_chars: int = 65_536,
        timeout_seconds: float = 60.0,
        cancellation: RuntimeCancellationToken | None = None,
        sensitivity: RecordSensitivity = "personal",
    ) -> LocalStreamingConversationResult:
        if self.repository.read_only:
            raise ReadOnlyStateError("state repository is open in read-only mode")
        safe_operation_id = _operation_id(operation_id)
        safe_user_text = _message_text("user message", user_text)
        self._require_unused_operation(safe_operation_id)
        self.repository.get_conversation(conversation_id)
        parents = self._validate_parent(conversation_id, parent_event_id)
        sequence = self._next_sequence(conversation_id)

        manifests = ModelManifestService(self.repository)
        try:
            binding, runtime_manifest, model_manifest = manifests.resolve_active_binding(
                scope_type=scope_type,
                scope_key=scope_key,
            )
        except (KeyError, ModelManifestValidationError) as exc:
            raise LocalConversationValidationError(
                "active local model binding is unavailable"
            ) from exc
        self._validate_adapter_declaration(runtime_manifest)
        model_id = _runtime_model_id(model_manifest.runtime_private_locator)

        created = _CreatedTurnState()
        origins = InstructionOriginService(self.repository)
        try:
            user_origin = origins.create(
                title="Current user message",
                content=safe_user_text,
                source=InstructionSource(
                    origin_class="current_user_instruction",
                    actor_type="user",
                    acquisition_method="user_entry",
                    parent_operation_id=safe_operation_id,
                    session_id=conversation_id,
                    content_hash=_sha256_text(safe_user_text),
                ),
                operation_id=safe_operation_id,
                sensitivity=sensitivity,
            )
            created.record_ids.append(user_origin.record_id)

            defense = PromptDefenseService(origins)
            defense.require_authority(user_origin.record_id, purpose="task_instruction")
            context_ids = _context_ids(context_instruction_ids, user_origin.record_id)
            package = defense.package_context(context_ids)
            prompt_text = _render_prompt(package)
            if len(prompt_text) > MAX_RUNTIME_INPUT_CHARS:
                raise LocalConversationValidationError(
                    "rendered local context exceeds runtime limit"
                )

            stream_result = self.runtime_boundary.stream(
                runtime_manifest.adapter_id,
                RuntimeGenerationRequest(
                    operation_id=safe_operation_id,
                    model_id=model_id,
                    input_text=prompt_text,
                    max_output_chars=max_output_chars,
                    timeout_seconds=timeout_seconds,
                    cancellation=(
                        cancellation if cancellation is not None else RuntimeCancellationToken()
                    ),
                ),
            )
            normalized_result, assistant_text, display_events = _normalize_stream_result(
                stream_result,
                operation_id=safe_operation_id,
                adapter_id=runtime_manifest.adapter_id,
                model_id=model_id,
            )

            exposed_text = stream_result.output_text
            output_scan = redact_text(exposed_text) if exposed_text else None
            if output_scan is not None and (
                output_scan.changed or output_scan.finding_limit_reached
            ):
                normalized_result = RuntimeGenerationResult(
                    operation_id=safe_operation_id,
                    adapter_id=runtime_manifest.adapter_id,
                    runtime_id=stream_result.runtime_id,
                    model_id=model_id,
                    outcome="failed",
                    failure_code="invalid_response",
                )
                assistant_text = None
                display_events = _sanitized_failure_events(
                    safe_operation_id, "invalid_response"
                )

            runtime_origin_id: str | None = None
            if assistant_text is not None:
                runtime_origin = origins.create(
                    title="Local runtime output",
                    content=assistant_text,
                    source=InstructionSource(
                        origin_class="runtime_output",
                        actor_type="runtime",
                        acquisition_method="runtime_execution",
                        parent_operation_id=safe_operation_id,
                        session_id=conversation_id,
                        content_hash=_sha256_text(assistant_text),
                        model_manifest_id=model_manifest.model_manifest_id,
                        runtime_adapter_id=runtime_manifest.adapter_id,
                    ),
                    operation_id=safe_operation_id,
                    sensitivity=sensitivity,
                )
                runtime_origin_id = runtime_origin.record_id
                created.record_ids.append(runtime_origin_id)

            prompt_hash = _sha256_text(prompt_text)
            turn = self._persist_turn(
                created=created,
                conversation_id=conversation_id,
                operation_id=safe_operation_id,
                parent_event_ids=parents,
                starting_sequence=sequence,
                sensitivity=sensitivity,
                user_text=safe_user_text,
                user_origin_id=user_origin.record_id,
                package=package,
                prompt_hash=prompt_hash,
                binding=binding,
                runtime_manifest=runtime_manifest,
                model_manifest=model_manifest,
                runtime_result=normalized_result,
                assistant_text=assistant_text,
                runtime_origin_id=runtime_origin_id,
            )
            AuditService(self.repository).append(
                action="local_conversation.stream_turn",
                result=(
                    "success"
                    if turn.outcome == "completed"
                    else "cancelled"
                    if turn.outcome == "cancelled"
                    else "failed"
                ),
                actor_type="system",
                operation_id=safe_operation_id,
                target_type="conversation",
                target_id=conversation_id,
                metadata={
                    "binding_id": binding.binding_id,
                    "outcome": turn.outcome,
                    "failure_code": turn.failure_code,
                    "stream_event_count": len(display_events),
                    "finding_count": turn.prompt_injection_finding_count,
                    "redaction_count": turn.secret_redaction_count,
                },
            )
            return LocalStreamingConversationResult(turn, display_events)
        except BaseException as exc:
            if created.record_ids or created.artifacts:
                try:
                    self._rollback_created(created)
                except BaseException as rollback_exc:
                    raise LocalConversationRollbackError(
                        "local streaming conversation cleanup did not complete"
                    ) from rollback_exc
            if isinstance(
                exc,
                (
                    LocalConversationError,
                    ReadOnlyStateError,
                    ModelManifestValidationError,
                ),
            ):
                raise
            if isinstance(
                exc,
                (InstructionOriginError, PromptInjectionError, RuntimeContractError, KeyError),
            ):
                raise LocalConversationValidationError(
                    "local streaming conversation input or context was rejected"
                ) from exc
            raise LocalConversationPersistenceError(
                "local streaming conversation turn did not persist"
            ) from exc


def _normalize_stream_result(
    result: RuntimeStreamResult,
    *,
    operation_id: str,
    adapter_id: str,
    model_id: str,
) -> tuple[RuntimeGenerationResult, str | None, tuple[RuntimeStreamEvent, ...]]:
    if not isinstance(result, RuntimeStreamResult):
        raise RuntimeContractError("streaming boundary returned an invalid result")
    if (
        result.operation_id != operation_id
        or result.adapter_id != adapter_id
        or result.model_id != model_id
    ):
        return (
            RuntimeGenerationResult(
                operation_id=operation_id,
                adapter_id=adapter_id,
                runtime_id=result.runtime_id,
                model_id=model_id,
                outcome="failed",
                failure_code="invalid_response",
            ),
            None,
            _sanitized_failure_events(operation_id, "invalid_response"),
        )

    if result.outcome == "completed":
        output_text = result.output_text
        terminal = result.events[-1]
        if not output_text.strip() or terminal.kind != "complete":
            return (
                RuntimeGenerationResult(
                    operation_id=operation_id,
                    adapter_id=adapter_id,
                    runtime_id=result.runtime_id,
                    model_id=model_id,
                    outcome="failed",
                    failure_code="invalid_response",
                ),
                None,
                _sanitized_failure_events(operation_id, "invalid_response"),
            )
        return (
            RuntimeGenerationResult(
                operation_id=operation_id,
                adapter_id=adapter_id,
                runtime_id=result.runtime_id,
                model_id=model_id,
                outcome="completed",
                output_text=output_text,
                finish_reason=terminal.finish_reason,
            ),
            output_text,
            result.events,
        )

    failure_code = result.failure_code or "invalid_response"
    return (
        RuntimeGenerationResult(
            operation_id=operation_id,
            adapter_id=adapter_id,
            runtime_id=result.runtime_id,
            model_id=model_id,
            outcome=result.outcome,
            failure_code=failure_code,
        ),
        None,
        result.events,
    )


def _sanitized_failure_events(
    operation_id: str,
    failure_code: RuntimeFailureCode,
) -> tuple[RuntimeStreamEvent, ...]:
    return (
        RuntimeStreamEvent(operation_id, 0, "start"),
        RuntimeStreamEvent(
            operation_id,
            1,
            "error",
            failure_code=failure_code,
        ),
    )


__all__ = [
    "LocalStreamingConversationResult",
    "LocalStreamingConversationService",
]
