from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

import pytest

from doll import state, workspace
from doll import streaming_conversation as streaming_module
from doll.instruction_origin import InstructionOriginService
from doll.local_conversation import (
    DuplicateConversationOperationError,
    LocalConversationPersistenceError,
    LocalConversationRollbackError,
    LocalConversationValidationError,
)
from doll.model_manifest import ModelManifestService
from doll.runtime_adapter import (
    MAX_RUNTIME_INPUT_CHARS,
    LocalRuntimeBoundary,
    RuntimeAdapterContext,
    RuntimeAdapterDeclaration,
    RuntimeAdapterFailure,
    RuntimeAdapterRegistry,
    RuntimeAdapterResponse,
    RuntimeCancellationToken,
    RuntimeContractError,
    RuntimeGenerationRequest,
    RuntimeHealth,
    RuntimeInventorySnapshot,
    RuntimeStreamEvent,
    RuntimeStreamResult,
)
from doll.state import ConversationRecord
from doll.streaming_conversation import (
    LocalStreamingConversationService,
    _normalize_stream_result,
)


@dataclass(slots=True)
class FakeStreamingAdapter:
    adapter_id: str = "fake.stream"
    adapter_version: str = "1.0.0"
    chunks: tuple[str, ...] = ("Streamed ", "answer")
    failure: str | None = None
    prompts: list[str] = field(default_factory=list)

    def declaration(self) -> RuntimeAdapterDeclaration:
        return RuntimeAdapterDeclaration(
            adapter_id=self.adapter_id,
            adapter_version=self.adapter_version,
            runtime_class="fake.stream",
            connection_kind="local_socket",
            supported_operations=("stream",),
        )

    def health(self) -> RuntimeHealth:
        return RuntimeHealth(self.adapter_id, "fake.runtime", "ready")

    def inventory(self, context: RuntimeAdapterContext) -> RuntimeInventorySnapshot:
        return RuntimeInventorySnapshot("fake.runtime", ())

    def generate(
        self,
        request: RuntimeGenerationRequest,
        context: RuntimeAdapterContext,
    ) -> RuntimeAdapterResponse:
        return RuntimeAdapterResponse(
            runtime_id="fake.runtime",
            model_id=request.model_id,
            output_text="unused",
        )

    def stream(
        self,
        request: RuntimeGenerationRequest,
        context: RuntimeAdapterContext,
    ) -> Iterable[RuntimeStreamEvent]:
        self.prompts.append(request.input_text)
        yield RuntimeStreamEvent(request.operation_id, 0, "start")
        sequence = 1
        for chunk in self.chunks:
            yield RuntimeStreamEvent(request.operation_id, sequence, "delta", text=chunk)
            sequence += 1
            if self.failure == "after_delta":
                raise RuntimeError("provider detail must not escape")
        if self.failure == "cancelled":
            raise RuntimeAdapterFailure("cancelled")
        if self.failure == "timeout":
            raise RuntimeAdapterFailure("timeout")
        if self.failure == "resource_limit":
            raise RuntimeAdapterFailure("resource_limit")
        if self.failure == "raise":
            raise RuntimeError("provider detail must not escape")
        if self.failure == "invalid_event":
            yield RuntimeStreamEvent(
                request.operation_id,
                sequence + 1,
                "complete",
                finish_reason="stop",
            )
            return
        yield RuntimeStreamEvent(request.operation_id, sequence, "complete", finish_reason="stop")


class RaisingBoundary(LocalRuntimeBoundary):
    def stream(
        self,
        adapter_id: str,
        request: RuntimeGenerationRequest,
    ) -> RuntimeStreamResult:
        raise RuntimeContractError("closed boundary failure")


class InvalidBoundary(LocalRuntimeBoundary):
    def stream(  # type: ignore[override]
        self,
        adapter_id: str,
        request: RuntimeGenerationRequest,
    ) -> object:
        return object()


def _workspace(tmp_path: Path) -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(tmp_path / "workspace")
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def _active_binding(
    repository: state.StateRepository,
    adapter: FakeStreamingAdapter,
) -> tuple[str, str]:
    service = ModelManifestService(repository)
    declaration = adapter.declaration()
    runtime = service.create_runtime(
        label="Fake streaming runtime",
        adapter_id=declaration.adapter_id,
        adapter_version=declaration.adapter_version,
        runtime_class=declaration.runtime_class,
        connection_kind=declaration.connection_kind,
        operations=("cancel", "health", "stream"),
        offline_capable=True,
        cloud_fallback=False,
        automatic_download=False,
        platforms=("test",),
    )
    runtime = service.verify_runtime(
        runtime.runtime_manifest_id,
        expected_revision=runtime.revision,
    )
    model = service.create_model(
        runtime_manifest_id=runtime.runtime_manifest_id,
        runtime_private_locator="fake.model.1",
        display_name="Fake streaming model",
        exact_revision="revision-1",
        checksums={"sha256": "b" * 64},
        license_id="test-license",
        model_format="test",
        platforms=("test",),
    )
    model = service.review_model_license(
        model.model_manifest_id,
        expected_revision=model.revision,
        review_state="reviewed_compatible",
    )
    model = service.verify_model(
        model.model_manifest_id,
        expected_revision=model.revision,
    )
    binding = service.create_binding(
        scope_type="conversation",
        scope_key="default",
        runtime_manifest_id=runtime.runtime_manifest_id,
        model_manifest_id=model.model_manifest_id,
    )
    binding = service.set_smoke_test(
        binding.binding_id,
        expected_revision=binding.revision,
        status="passed",
    )
    service.activate_binding(
        binding.binding_id,
        expected_revision=binding.revision,
    )
    return runtime.runtime_manifest_id, model.model_manifest_id


def _service(
    repository: state.StateRepository,
    adapter: FakeStreamingAdapter,
    *,
    maximum_artifact_bytes: int = 1_048_576,
) -> LocalStreamingConversationService:
    return LocalStreamingConversationService(
        repository,
        LocalRuntimeBoundary(RuntimeAdapterRegistry((adapter,))),
        maximum_artifact_bytes=maximum_artifact_bytes,
    )


def _artifact_paths(
    repository: state.StateRepository,
    root: Path,
    conversation_id: str,
) -> list[Path]:
    paths: list[Path] = []
    for event in repository.list_conversation_events(conversation_id):
        if event.content_reference is None:
            continue
        artifact_id = event.content_reference.removeprefix("artifact:")
        record = repository.get_record(artifact_id)
        paths.append(root / "artifacts" / str(record.metadata["managed_path"]))
    return paths


def test_completed_stream_commits_one_canonical_assistant_message(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    adapter = FakeStreamingAdapter()
    conversation_id = str(uuid4())
    with state.open_state_repository(initialized.root) as repository:
        repository.save_conversation(
            ConversationRecord(conversation_id=conversation_id, title="Streaming chat")
        )
        runtime_id, model_id = _active_binding(repository, adapter)
        result = _service(repository, adapter).execute_streaming_turn(
            conversation_id=conversation_id,
            scope_type="conversation",
            scope_key="default",
            user_text="Explain streaming continuity.",
            operation_id="stream.complete.1",
        )

        assert result.turn.outcome == "completed"
        assert result.turn.runtime_manifest_id == runtime_id
        assert result.turn.model_manifest_id == model_id
        assert result.turn.assistant_event_id is not None
        assert result.turn.error_event_id is None
        assert [event.kind for event in result.display_events] == [
            "start",
            "delta",
            "delta",
            "complete",
        ]
        assert "Streamed answer" not in repr(result)

        events = repository.list_conversation_events(conversation_id)
        assert [event.event_kind for event in events] == [
            "user_message",
            "system_context_snapshot",
            "assistant_message",
        ]
        assert events[2].parent_event_ids == (events[1].event_id,)
        assert events[2].origin_class == "runtime_output"
        assert events[2].runtime_adapter_id == adapter.adapter_id
        paths = _artifact_paths(repository, initialized.root, conversation_id)
        assert len(paths) == 3
        assert paths[-1].read_text(encoding="utf-8") == "Streamed answer"
        assert not any("stream" in path.name for path in paths)

        prompt = json.loads(adapter.prompts[0])
        assert prompt["purpose"] == "local_conversation_turn"
        assert prompt["channels"]["current_user_instruction"][0]["authority_active"] is True

        runtime_origins = [
            item
            for item in InstructionOriginService(repository).list(limit=20)
            if item.origin_class == "runtime_output"
        ]
        assert len(runtime_origins) == 1
        assert runtime_origins[0].data_only is True
        assert runtime_origins[0].authority_class == "untrusted_data"


def test_failed_stream_keeps_partial_delta_transient(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    adapter = FakeStreamingAdapter(chunks=("partial only",), failure="after_delta")
    conversation_id = str(uuid4())
    with state.open_state_repository(initialized.root) as repository:
        repository.save_conversation(ConversationRecord(conversation_id=conversation_id))
        _active_binding(repository, adapter)
        result = _service(repository, adapter).execute_streaming_turn(
            conversation_id=conversation_id,
            scope_type="conversation",
            scope_key="default",
            user_text="Fail after one delta.",
            operation_id="stream.partial-failure.1",
        )

        assert result.turn.outcome == "failed"
        assert result.turn.failure_code == "invalid_response"
        assert result.turn.assistant_event_id is None
        assert result.turn.error_event_id is not None
        assert any(event.text == "partial only" for event in result.display_events)
        events = repository.list_conversation_events(conversation_id)
        assert [event.event_kind for event in events] == [
            "user_message",
            "system_context_snapshot",
            "error",
        ]
        paths = _artifact_paths(repository, initialized.root, conversation_id)
        assert len(paths) == 2
        assert all("partial only" not in path.read_text(encoding="utf-8") for path in paths)
        assert not [
            item
            for item in InstructionOriginService(repository).list(limit=20)
            if item.origin_class == "runtime_output"
        ]


@pytest.mark.parametrize(
    ("failure", "expected_outcome"),
    (("cancelled", "cancelled"), ("timeout", "timeout"), ("resource_limit", "failed")),
)
def test_terminal_stream_failures_create_only_bounded_error(
    tmp_path: Path,
    failure: str,
    expected_outcome: str,
) -> None:
    initialized = _workspace(tmp_path)
    adapter = FakeStreamingAdapter(chunks=(), failure=failure)
    conversation_id = str(uuid4())
    with state.open_state_repository(initialized.root) as repository:
        repository.save_conversation(ConversationRecord(conversation_id=conversation_id))
        _active_binding(repository, adapter)
        result = _service(repository, adapter).execute_streaming_turn(
            conversation_id=conversation_id,
            scope_type="conversation",
            scope_key="default",
            user_text="Exercise terminal failure.",
            operation_id=f"stream.{failure}.1",
        )

        assert result.turn.outcome == expected_outcome
        assert result.turn.failure_code == failure
        assert result.turn.assistant_event_id is None
        assert result.display_events[-1].failure_code == failure
        assert [event.event_kind for event in repository.list_conversation_events(conversation_id)][
            -1
        ] == "error"


def test_pre_cancelled_stream_never_calls_adapter(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    adapter = FakeStreamingAdapter()
    cancellation = RuntimeCancellationToken()
    cancellation.cancel()
    conversation_id = str(uuid4())
    with state.open_state_repository(initialized.root) as repository:
        repository.save_conversation(ConversationRecord(conversation_id=conversation_id))
        _active_binding(repository, adapter)
        result = _service(repository, adapter).execute_streaming_turn(
            conversation_id=conversation_id,
            scope_type="conversation",
            scope_key="default",
            user_text="Cancel before execution.",
            operation_id="stream.pre-cancelled.1",
            cancellation=cancellation,
        )
        assert result.turn.outcome == "cancelled"
        assert result.turn.failure_code == "cancelled"
        assert adapter.prompts == []
        assert result.display_events[-1].kind == "cancelled"


def test_secret_bearing_completed_stream_is_rejected_and_sanitized(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    secret = "sk-1234567890abcdefghijklmnop"
    adapter = FakeStreamingAdapter(chunks=("unsafe ", secret))
    conversation_id = str(uuid4())
    with state.open_state_repository(initialized.root) as repository:
        repository.save_conversation(ConversationRecord(conversation_id=conversation_id))
        _active_binding(repository, adapter)
        result = _service(repository, adapter).execute_streaming_turn(
            conversation_id=conversation_id,
            scope_type="conversation",
            scope_key="default",
            user_text="Reject secret output.",
            operation_id="stream.secret.1",
        )

        assert result.turn.outcome == "failed"
        assert result.turn.failure_code == "invalid_response"
        assert result.turn.assistant_event_id is None
        assert [event.kind for event in result.display_events] == ["start", "error"]
        assert all(event.text is None for event in result.display_events)
        assert secret not in repr(result)
        paths = _artifact_paths(repository, initialized.root, conversation_id)
        assert all(secret not in path.read_text(encoding="utf-8") for path in paths)
        assert not [
            item
            for item in InstructionOriginService(repository).list(limit=20)
            if item.origin_class == "runtime_output"
        ]


def test_blank_and_invalid_streams_fail_closed(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    conversation_id = str(uuid4())
    with state.open_state_repository(initialized.root) as repository:
        repository.save_conversation(ConversationRecord(conversation_id=conversation_id))
        blank = FakeStreamingAdapter(chunks=())
        _active_binding(repository, blank)
        blank_result = _service(repository, blank).execute_streaming_turn(
            conversation_id=conversation_id,
            scope_type="conversation",
            scope_key="default",
            user_text="Reject blank output.",
            operation_id="stream.blank.1",
        )
        assert blank_result.turn.failure_code == "invalid_response"
        assert [event.kind for event in blank_result.display_events] == ["start", "error"]

        invalid = FakeStreamingAdapter(failure="invalid_event")
        invalid_result = _service(repository, invalid).execute_streaming_turn(
            conversation_id=conversation_id,
            scope_type="conversation",
            scope_key="default",
            user_text="Reject bad ordering.",
            operation_id="stream.invalid-event.1",
        )
        assert invalid_result.turn.outcome == "failed"
        assert invalid_result.turn.failure_code == "invalid_response"
        assert invalid_result.turn.assistant_event_id is None


def test_duplicate_mismatch_read_only_and_boundary_errors_fail_closed(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    adapter = FakeStreamingAdapter()
    conversation_id = str(uuid4())
    with state.open_state_repository(initialized.root) as repository:
        repository.save_conversation(ConversationRecord(conversation_id=conversation_id))
        _active_binding(repository, adapter)
        service = _service(repository, adapter)
        service.execute_streaming_turn(
            conversation_id=conversation_id,
            scope_type="conversation",
            scope_key="default",
            user_text="First operation.",
            operation_id="stream.duplicate.1",
        )
        with pytest.raises(DuplicateConversationOperationError):
            service.execute_streaming_turn(
                conversation_id=conversation_id,
                scope_type="conversation",
                scope_key="default",
                user_text="Duplicate operation.",
                operation_id="stream.duplicate.1",
            )

        mismatched = FakeStreamingAdapter(adapter_version="2.0.0")
        with pytest.raises(LocalConversationValidationError, match="declaration"):
            _service(repository, mismatched).execute_streaming_turn(
                conversation_id=conversation_id,
                scope_type="conversation",
                scope_key="default",
                user_text="Mismatched adapter.",
                operation_id="stream.mismatch.1",
            )

        raising = LocalStreamingConversationService(
            repository,
            RaisingBoundary(RuntimeAdapterRegistry((adapter,))),
        )
        with pytest.raises(LocalConversationValidationError, match="rejected"):
            raising.execute_streaming_turn(
                conversation_id=conversation_id,
                scope_type="conversation",
                scope_key="default",
                user_text="Boundary raises.",
                operation_id="stream.boundary-error.1",
            )

        invalid_boundary = LocalStreamingConversationService(
            repository,
            InvalidBoundary(RuntimeAdapterRegistry((adapter,))),
        )
        with pytest.raises(LocalConversationValidationError, match="rejected"):
            invalid_boundary.execute_streaming_turn(
                conversation_id=conversation_id,
                scope_type="conversation",
                scope_key="default",
                user_text="Boundary returns an invalid result.",
                operation_id="stream.boundary-invalid.1",
            )

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        with pytest.raises(state.ReadOnlyStateError):
            _service(repository, adapter).execute_streaming_turn(
                conversation_id=conversation_id,
                scope_type="conversation",
                scope_key="default",
                user_text="Read only.",
                operation_id="stream.readonly.1",
            )


def test_persistence_failure_rolls_back_all_stream_turn_state(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    adapter = FakeStreamingAdapter()
    conversation_id = str(uuid4())
    with state.open_state_repository(initialized.root) as repository:
        repository.save_conversation(ConversationRecord(conversation_id=conversation_id))
        _active_binding(repository, adapter)
        with pytest.raises(LocalConversationPersistenceError, match="persist"):
            _service(repository, adapter, maximum_artifact_bytes=8).execute_streaming_turn(
                conversation_id=conversation_id,
                scope_type="conversation",
                scope_key="default",
                user_text="This user message exceeds eight bytes.",
                operation_id="stream.rollback.1",
            )
        assert repository.list_conversation_events(conversation_id) == ()
        rows = repository.connection.execute(
            "SELECT id FROM records WHERE "
            "json_extract(metadata_json, '$.operation_id') = ? "
            "OR json_extract(metadata_json, '$.parent_operation_id') = ?",
            ("stream.rollback.1", "stream.rollback.1"),
        ).fetchall()
        assert rows == []
        assert not any((initialized.root / "artifacts").rglob("*.txt"))


def test_prompt_limit_and_rollback_failure_are_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initialized = _workspace(tmp_path)
    adapter = FakeStreamingAdapter()
    conversation_id = str(uuid4())
    with state.open_state_repository(initialized.root) as repository:
        repository.save_conversation(ConversationRecord(conversation_id=conversation_id))
        _active_binding(repository, adapter)
        monkeypatch.setattr(
            streaming_module,
            "_render_prompt",
            lambda package: "x" * (MAX_RUNTIME_INPUT_CHARS + 1),
        )
        with pytest.raises(LocalConversationValidationError, match="runtime limit"):
            _service(repository, adapter).execute_streaming_turn(
                conversation_id=conversation_id,
                scope_type="conversation",
                scope_key="default",
                user_text="Oversized prompt.",
                operation_id="stream.prompt-limit.1",
            )

        monkeypatch.setattr(streaming_module, "_render_prompt", lambda package: "valid prompt")
        monkeypatch.setattr(
            LocalStreamingConversationService,
            "_rollback_created",
            lambda self, created: (_ for _ in ()).throw(RuntimeError("cleanup failed")),
        )
        with pytest.raises(LocalConversationRollbackError, match="cleanup"):
            _service(repository, adapter, maximum_artifact_bytes=8).execute_streaming_turn(
                conversation_id=conversation_id,
                scope_type="conversation",
                scope_key="default",
                user_text="Rollback failure after persistence starts.",
                operation_id="stream.rollback-failure.1",
            )


def test_normalization_rejects_identity_mismatch_and_non_results() -> None:
    mismatched = RuntimeStreamResult(
        operation_id="other.operation",
        adapter_id="fake.stream",
        runtime_id="fake.runtime",
        model_id="fake.model.1",
        outcome="completed",
        events=(
            RuntimeStreamEvent("other.operation", 0, "start"),
            RuntimeStreamEvent("other.operation", 1, "delta", text="answer"),
            RuntimeStreamEvent("other.operation", 2, "complete", finish_reason="stop"),
        ),
    )
    normalized, assistant_text, events = _normalize_stream_result(
        mismatched,
        operation_id="expected.operation",
        adapter_id="fake.stream",
        model_id="fake.model.1",
    )
    assert normalized.outcome == "failed"
    assert normalized.failure_code == "invalid_response"
    assert assistant_text is None
    assert [event.kind for event in events] == ["start", "error"]

    with pytest.raises(RuntimeContractError, match="invalid result"):
        _normalize_stream_result(
            object(),  # type: ignore[arg-type]
            operation_id="expected.operation",
            adapter_id="fake.stream",
            model_id="fake.model.1",
        )
