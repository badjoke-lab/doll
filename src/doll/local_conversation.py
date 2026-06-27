"""Canonical single-turn local conversation orchestration."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Literal, cast
from uuid import uuid4

from doll.artifact import ArtifactInfo, WorkspaceFileService
from doll.audit import AuditService
from doll.instruction_origin import (
    InstructionOriginError,
    InstructionOriginService,
    InstructionSource,
)
from doll.model_manifest import (
    ModelBindingInfo,
    ModelManifestInfo,
    ModelManifestService,
    ModelManifestValidationError,
    RuntimeManifestInfo,
    _runtime_fingerprint,
)
from doll.prompt_injection import (
    PromptContextItem,
    PromptContextPackage,
    PromptDefenseService,
    PromptInjectionError,
)
from doll.runtime_adapter import (
    MAX_RUNTIME_INPUT_CHARS,
    LocalRuntimeBoundary,
    RuntimeCancellationToken,
    RuntimeContractError,
    RuntimeFailureCode,
    RuntimeGenerationRequest,
    RuntimeGenerationResult,
)
from doll.secret_detection import redact_text
from doll.state import (
    ConversationEventRecord,
    ReadOnlyStateError,
    RecordSensitivity,
    StateError,
)
from doll.state_repository import StateRepository
from doll.workspace_files import validate_managed_path

LocalConversationOutcome = Literal["completed", "failed", "cancelled", "timeout"]

_OPERATION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_CHANNEL_NAMES = (
    "system_policy",
    "current_user_instruction",
    "durable_user_policy",
    "user_management_action",
    "untrusted_content",
    "model_proposals",
    "unknown_origin",
)
_RENDERER_VERSION = "doll.local-conversation.prompt.v1"
_CONTEXT_SNAPSHOT_VERSION = 1
_MAX_EVENTS_PER_CONVERSATION = 500
_MAX_MESSAGE_CHARS = 262_144
_MAX_ARTIFACT_BYTES = 1_048_576


class LocalConversationError(StateError):
    """Base class for canonical local conversation failures."""


class LocalConversationValidationError(LocalConversationError):
    """Raised before a runtime call when turn state is not executable."""


class DuplicateConversationOperationError(LocalConversationValidationError):
    """Raised when an operation ID has already been committed or started."""


class LocalConversationPersistenceError(LocalConversationError):
    """Raised when canonical turn persistence cannot complete."""


class LocalConversationRollbackError(LocalConversationError):
    """Raised when cleanup after a persistence failure is incomplete."""


@dataclass(frozen=True, slots=True)
class LocalConversationResult:
    """Bounded identifiers and outcome for one canonical local turn."""

    conversation_id: str
    operation_id: str
    binding_id: str
    binding_revision: int
    runtime_manifest_id: str
    runtime_manifest_revision: int
    model_manifest_id: str
    model_manifest_revision: int
    user_event_id: str
    context_event_id: str
    assistant_event_id: str | None
    error_event_id: str | None
    outcome: LocalConversationOutcome
    failure_code: RuntimeFailureCode | None
    prompt_injection_finding_count: int
    secret_redaction_count: int
    runtime_id: str | None = None


@dataclass(slots=True)
class _CreatedTurnState:
    record_ids: list[str] = field(default_factory=list)
    artifacts: list[ArtifactInfo] = field(default_factory=list)


@dataclass(slots=True)
class LocalConversationService:
    """Execute one non-streaming local turn without granting the model authority."""

    repository: StateRepository
    runtime_boundary: LocalRuntimeBoundary
    maximum_artifact_bytes: int = _MAX_ARTIFACT_BYTES

    def __post_init__(self) -> None:
        if not isinstance(self.runtime_boundary, LocalRuntimeBoundary):
            raise LocalConversationValidationError("runtime boundary is invalid")
        if (
            isinstance(self.maximum_artifact_bytes, bool)
            or not isinstance(self.maximum_artifact_bytes, int)
            or not 1 <= self.maximum_artifact_bytes <= _MAX_ARTIFACT_BYTES
        ):
            raise LocalConversationValidationError("artifact size limit is invalid")

    def execute_turn(
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
    ) -> LocalConversationResult:
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

            runtime_result = self.runtime_boundary.generate(
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
            normalized_result, assistant_text = _validate_runtime_result(runtime_result)

            runtime_origin_id: str | None = None
            if assistant_text is not None:
                output_scan = redact_text(assistant_text)
                if output_scan.changed or output_scan.finding_limit_reached:
                    normalized_result = RuntimeGenerationResult(
                        operation_id=safe_operation_id,
                        adapter_id=runtime_manifest.adapter_id,
                        runtime_id=runtime_result.runtime_id,
                        model_id=model_id,
                        outcome="failed",
                        failure_code="invalid_response",
                    )
                    assistant_text = None
                else:
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
            result = self._persist_turn(
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
                action="local_conversation.turn",
                result=(
                    "success"
                    if result.outcome == "completed"
                    else "cancelled"
                    if result.outcome == "cancelled"
                    else "failed"
                ),
                actor_type="system",
                operation_id=safe_operation_id,
                target_type="conversation",
                target_id=conversation_id,
                metadata={
                    "binding_id": binding.binding_id,
                    "outcome": result.outcome,
                    "failure_code": result.failure_code,
                    "finding_count": result.prompt_injection_finding_count,
                    "redaction_count": result.secret_redaction_count,
                },
            )
            return result
        except BaseException as exc:
            if created.record_ids or created.artifacts:
                try:
                    self._rollback_created(created)
                except BaseException as rollback_exc:
                    raise LocalConversationRollbackError(
                        "local conversation cleanup did not complete"
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
                    "local conversation input or context was rejected"
                ) from exc
            raise LocalConversationPersistenceError(
                "local conversation turn did not persist"
            ) from exc

    def _validate_adapter_declaration(self, runtime: RuntimeManifestInfo) -> None:
        declaration = self.runtime_boundary.declaration(runtime.adapter_id)
        if declaration is None:
            raise LocalConversationValidationError("bound local runtime adapter is unavailable")
        operations = tuple(sorted({*declaration.supported_operations, "health", "cancel"}))
        expected_fingerprint = _runtime_fingerprint(
            declaration.adapter_id,
            declaration.adapter_version,
            declaration.runtime_class,
            declaration.connection_kind,
            operations,
            declaration.offline_capable,
            declaration.cloud_fallback,
            declaration.automatic_download,
        )
        if (
            declaration.adapter_id != runtime.adapter_id
            or declaration.adapter_version != runtime.adapter_version
            or declaration.runtime_class != runtime.runtime_class
            or declaration.connection_kind != runtime.connection_kind
            or operations != runtime.operations
            or declaration.offline_capable != runtime.offline_capable
            or declaration.cloud_fallback != runtime.cloud_fallback
            or declaration.automatic_download != runtime.automatic_download
            or expected_fingerprint != runtime.declaration_fingerprint
        ):
            raise LocalConversationValidationError(
                "bound runtime declaration does not match the active manifest"
            )

    def _persist_turn(
        self,
        *,
        created: _CreatedTurnState,
        conversation_id: str,
        operation_id: str,
        parent_event_ids: tuple[str, ...],
        starting_sequence: int,
        sensitivity: RecordSensitivity,
        user_text: str,
        user_origin_id: str,
        package: PromptContextPackage,
        prompt_hash: str,
        binding: ModelBindingInfo,
        runtime_manifest: RuntimeManifestInfo,
        model_manifest: ModelManifestInfo,
        runtime_result: RuntimeGenerationResult,
        assistant_text: str | None,
        runtime_origin_id: str | None,
    ) -> LocalConversationResult:
        artifact_service = WorkspaceFileService(
            self.repository, maximum_bytes=self.maximum_artifact_bytes
        )
        path_prefix = _turn_path(conversation_id, operation_id)
        user_artifact = artifact_service.create_text(
            managed_path=f"{path_prefix}/user.txt",
            text=user_text,
            title="Local conversation user message",
            artifact_type="conversation_message",
            operation_id=operation_id,
            created_by="user",
            sensitivity=sensitivity,
            max_bytes=self.maximum_artifact_bytes,
        )
        created.artifacts.append(user_artifact)
        created.record_ids.append(user_artifact.artifact_id)

        snapshot_text = _context_snapshot(
            package=package,
            prompt_hash=prompt_hash,
            binding=binding,
            runtime=runtime_manifest,
            model=model_manifest,
        )
        context_artifact = artifact_service.create_text(
            managed_path=f"{path_prefix}/context.json",
            text=snapshot_text,
            title="Local conversation context snapshot",
            artifact_type="conversation_context_snapshot",
            operation_id=operation_id,
            created_by="system",
            sensitivity=sensitivity,
            format="json",
            media_type="application/json",
            max_bytes=self.maximum_artifact_bytes,
        )
        created.artifacts.append(context_artifact)
        created.record_ids.append(context_artifact.artifact_id)

        assistant_artifact: ArtifactInfo | None = None
        if assistant_text is not None:
            assistant_artifact = artifact_service.create_text(
                managed_path=f"{path_prefix}/assistant.txt",
                text=assistant_text,
                title="Local conversation assistant message",
                artifact_type="conversation_message",
                operation_id=operation_id,
                created_by="model",
                sensitivity=sensitivity,
                max_bytes=self.maximum_artifact_bytes,
            )
            created.artifacts.append(assistant_artifact)
            created.record_ids.append(assistant_artifact.artifact_id)

        user_event = ConversationEventRecord(
            event_id=str(uuid4()),
            conversation_id=conversation_id,
            event_kind="user_message",
            actor_type="user",
            origin_class="current_user_instruction",
            parent_event_ids=parent_event_ids,
            sequence_hint=starting_sequence,
            content_reference=f"artifact:{user_artifact.artifact_id}",
            operation_id=operation_id,
            extensions={"instruction_origin_id": user_origin_id},
        )
        self.repository.save_conversation_event(
            user_event, provenance="user-created", sensitivity=sensitivity
        )
        created.record_ids.append(user_event.event_id)

        context_event = ConversationEventRecord(
            event_id=str(uuid4()),
            conversation_id=conversation_id,
            event_kind="system_context_snapshot",
            actor_type="system",
            origin_class="current_user_instruction",
            parent_event_ids=(user_event.event_id,),
            sequence_hint=starting_sequence + 1,
            content_reference=f"artifact:{context_artifact.artifact_id}",
            model_manifest_id=model_manifest.model_manifest_id,
            runtime_adapter_id=runtime_manifest.adapter_id,
            operation_id=operation_id,
            extensions={
                "binding_id": binding.binding_id,
                "renderer_version": _RENDERER_VERSION,
            },
        )
        self.repository.save_conversation_event(
            context_event, provenance="system-generated", sensitivity=sensitivity
        )
        created.record_ids.append(context_event.event_id)

        if runtime_result.outcome == "completed":
            if assistant_artifact is None or runtime_origin_id is None:  # pragma: no cover
                raise LocalConversationPersistenceError("completed output is incomplete")
            assistant_event = ConversationEventRecord(
                event_id=str(uuid4()),
                conversation_id=conversation_id,
                event_kind="assistant_message",
                actor_type="assistant",
                origin_class="runtime_output",
                parent_event_ids=(context_event.event_id,),
                sequence_hint=starting_sequence + 2,
                content_reference=f"artifact:{assistant_artifact.artifact_id}",
                model_manifest_id=model_manifest.model_manifest_id,
                runtime_adapter_id=runtime_manifest.adapter_id,
                operation_id=operation_id,
                extensions={"instruction_origin_id": runtime_origin_id},
            )
            self.repository.save_conversation_event(
                assistant_event, provenance="model-proposed", sensitivity=sensitivity
            )
            created.record_ids.append(assistant_event.event_id)
            return _result(
                conversation_id=conversation_id,
                operation_id=operation_id,
                binding=binding,
                runtime=runtime_manifest,
                model=model_manifest,
                user_event_id=user_event.event_id,
                context_event_id=context_event.event_id,
                assistant_event_id=assistant_event.event_id,
                error_event_id=None,
                runtime_result=runtime_result,
                package=package,
            )

        error_event = ConversationEventRecord(
            event_id=str(uuid4()),
            conversation_id=conversation_id,
            event_kind="error",
            actor_type="runtime",
            origin_class="runtime_output",
            parent_event_ids=(context_event.event_id,),
            sequence_hint=starting_sequence + 2,
            model_manifest_id=model_manifest.model_manifest_id,
            runtime_adapter_id=runtime_manifest.adapter_id,
            operation_id=operation_id,
            extensions={
                "failure_code": runtime_result.failure_code,
                "outcome": runtime_result.outcome,
            },
        )
        self.repository.save_conversation_event(
            error_event, provenance="system-generated", sensitivity=sensitivity
        )
        created.record_ids.append(error_event.event_id)
        return _result(
            conversation_id=conversation_id,
            operation_id=operation_id,
            binding=binding,
            runtime=runtime_manifest,
            model=model_manifest,
            user_event_id=user_event.event_id,
            context_event_id=context_event.event_id,
            assistant_event_id=None,
            error_event_id=error_event.event_id,
            runtime_result=runtime_result,
            package=package,
        )

    def _require_unused_operation(self, operation_id: str) -> None:
        query = (
            "SELECT 1 FROM records WHERE "
            "(record_type = 'conversation_event' "
            "AND json_extract(metadata_json, '$.operation_id') = ?) "
            "OR (record_type = 'artifact' "
            "AND json_extract(metadata_json, '$.operation_id') = ?) "
            "OR (record_type = 'instruction_origin' "
            "AND json_extract(metadata_json, '$.parent_operation_id') = ?) LIMIT 1"
        )
        row = self.repository.connection.execute(
            query, (operation_id, operation_id, operation_id)
        ).fetchone()
        if row is not None:
            raise DuplicateConversationOperationError("conversation operation ID already exists")

    def _validate_parent(
        self, conversation_id: str, parent_event_id: str | None
    ) -> tuple[str, ...]:
        if parent_event_id is None:
            return ()
        try:
            parent = self.repository.get_conversation_event(parent_event_id)
        except KeyError as exc:
            raise LocalConversationValidationError("parent event does not exist") from exc
        if parent.conversation_id != conversation_id:
            raise LocalConversationValidationError("parent event belongs to another conversation")
        return (parent.event_id,)

    def _next_sequence(self, conversation_id: str) -> int:
        events = self.repository.list_conversation_events(
            conversation_id, limit=_MAX_EVENTS_PER_CONVERSATION
        )
        if len(events) >= _MAX_EVENTS_PER_CONVERSATION:
            raise LocalConversationValidationError("conversation event limit is reached")
        hints = tuple(event.sequence_hint for event in events if event.sequence_hint is not None)
        return (max(hints) + 1) if hints else 0

    def _rollback_created(self, created: _CreatedTurnState) -> None:
        record_ids = tuple(dict.fromkeys(reversed(created.record_ids)))
        connection = self.repository.connection
        try:
            connection.execute("BEGIN IMMEDIATE")
            for record_id in record_ids:
                connection.execute("DELETE FROM records WHERE id = ?", (record_id,))
            state_revision = self.repository._commit_state_revision()
            connection.execute("COMMIT")
        except BaseException:  # pragma: no cover - SQLite rollback guard
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        self.repository._sync_after_commit(state_revision)

        failures: list[str] = []
        root = self.repository.workspace.root / "artifacts"
        for artifact in reversed(created.artifacts):
            try:
                relative = validate_managed_path(artifact.managed_path)
                target = root.joinpath(*PurePosixPath(relative).parts)
                if target.is_symlink():
                    raise LocalConversationRollbackError("artifact cleanup path is unsafe")
                target.unlink(missing_ok=True)
                _remove_empty_parents(target.parent, root)
            except BaseException:
                failures.append(artifact.artifact_id)
        if failures:
            raise LocalConversationRollbackError("one or more managed files could not be removed")


def _validate_runtime_result(
    result: RuntimeGenerationResult,
) -> tuple[RuntimeGenerationResult, str | None]:
    if result.outcome != "completed":
        return result, None
    if result.output_text is None or not result.output_text.strip():
        return (
            RuntimeGenerationResult(
                operation_id=result.operation_id,
                adapter_id=result.adapter_id,
                runtime_id=result.runtime_id,
                model_id=result.model_id,
                outcome="failed",
                failure_code="invalid_response",
            ),
            None,
        )
    return result, result.output_text


def _render_prompt(package: PromptContextPackage) -> str:
    channels: dict[str, list[dict[str, object]]] = {}
    for channel_name in _CHANNEL_NAMES:
        items = cast(tuple[PromptContextItem, ...], getattr(package, channel_name))
        channels[channel_name] = [_prompt_item(item) for item in items]
    payload = {
        "schema_version": 1,
        "renderer_version": _RENDERER_VERSION,
        "purpose": "local_conversation_turn",
        "channels": channels,
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _prompt_item(item: PromptContextItem) -> dict[str, object]:
    return {
        "record_id": item.record_id,
        "title": item.title,
        "content": item.content,
        "origin_class": item.origin_class,
        "declared_authority_class": item.declared_authority_class,
        "effective_authority_class": item.effective_authority_class,
        "data_only": item.data_only,
        "authority_active": item.authority_active,
        "authority_failure": item.authority_failure,
        "transformations": list(item.transformations),
        "findings": [
            {"kind": finding.kind, "confidence": finding.confidence}
            for finding in item.prompt_injection_findings
        ],
        "secret_redaction_count": item.secret_redaction_count,
    }


def _context_snapshot(
    *,
    package: PromptContextPackage,
    prompt_hash: str,
    binding: ModelBindingInfo,
    runtime: RuntimeManifestInfo,
    model: ModelManifestInfo,
) -> str:
    channels: dict[str, list[dict[str, object]]] = {}
    for channel_name in _CHANNEL_NAMES:
        items = cast(tuple[PromptContextItem, ...], getattr(package, channel_name))
        channels[channel_name] = [
            {
                "record_id": item.record_id,
                "channel": item.channel,
                "origin_class": item.origin_class,
                "effective_authority_class": item.effective_authority_class,
                "data_only": item.data_only,
                "authority_active": item.authority_active,
                "content_hash": _sha256_text(item.content),
                "finding_kinds": sorted(
                    {finding.kind for finding in item.prompt_injection_findings}
                ),
                "secret_redaction_count": item.secret_redaction_count,
            }
            for item in items
        ]
    payload = {
        "schema_version": _CONTEXT_SNAPSHOT_VERSION,
        "renderer_version": _RENDERER_VERSION,
        "prompt_hash": prompt_hash,
        "binding": {"id": binding.binding_id, "revision": binding.revision},
        "runtime_manifest": {
            "id": runtime.runtime_manifest_id,
            "revision": runtime.revision,
            "declaration_fingerprint": runtime.declaration_fingerprint,
        },
        "model_manifest": {
            "id": model.model_manifest_id,
            "revision": model.revision,
            "exact_revision_hash": _sha256_text(model.exact_revision),
        },
        "totals": {
            "items": package.total_items,
            "prompt_injection_findings": package.prompt_injection_finding_count,
            "secret_redactions": package.secret_redaction_count,
        },
        "channels": channels,
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _result(
    *,
    conversation_id: str,
    operation_id: str,
    binding: ModelBindingInfo,
    runtime: RuntimeManifestInfo,
    model: ModelManifestInfo,
    user_event_id: str,
    context_event_id: str,
    assistant_event_id: str | None,
    error_event_id: str | None,
    runtime_result: RuntimeGenerationResult,
    package: PromptContextPackage,
) -> LocalConversationResult:
    return LocalConversationResult(
        conversation_id=conversation_id,
        operation_id=operation_id,
        binding_id=binding.binding_id,
        binding_revision=binding.revision,
        runtime_manifest_id=runtime.runtime_manifest_id,
        runtime_manifest_revision=runtime.revision,
        model_manifest_id=model.model_manifest_id,
        model_manifest_revision=model.revision,
        user_event_id=user_event_id,
        context_event_id=context_event_id,
        assistant_event_id=assistant_event_id,
        error_event_id=error_event_id,
        outcome=runtime_result.outcome,
        failure_code=runtime_result.failure_code,
        prompt_injection_finding_count=package.prompt_injection_finding_count,
        secret_redaction_count=package.secret_redaction_count,
        runtime_id=runtime_result.runtime_id,
    )


def _context_ids(values: Sequence[str], user_origin_id: str) -> tuple[str, ...]:
    if isinstance(values, str | bytes):
        raise LocalConversationValidationError("context instruction IDs must be a sequence")
    ids = tuple(values)
    if user_origin_id in ids or len(ids) != len(set(ids)):
        raise LocalConversationValidationError("context instruction IDs contain duplicates")
    return (*ids, user_origin_id)


def _operation_id(value: object) -> str:
    if not isinstance(value, str) or not _OPERATION_ID.fullmatch(value):
        raise LocalConversationValidationError("operation ID is invalid")
    return value


def _message_text(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise LocalConversationValidationError(f"{name} must be text")
    if not value.strip():
        raise LocalConversationValidationError(f"{name} must not be blank")
    if len(value) > _MAX_MESSAGE_CHARS:
        raise LocalConversationValidationError(f"{name} exceeds the size limit")
    if "\x00" in value:
        raise LocalConversationValidationError(f"{name} contains a null character")
    return value


def _runtime_model_id(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,127}", value):
        raise LocalConversationValidationError(
            "bound model locator is not an adapter-facing model identifier"
        )
    return value


def _sha256_text(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"


def _turn_path(conversation_id: str, operation_id: str) -> str:
    digest = hashlib.sha256(operation_id.encode("utf-8")).hexdigest()[:32]
    return f"conversations/{conversation_id}/turns/{digest}"


def _remove_empty_parents(path: Path, stop: Path) -> None:
    current = path
    while current != stop:
        try:
            current.rmdir()
        except OSError:
            return
        current = current.parent
