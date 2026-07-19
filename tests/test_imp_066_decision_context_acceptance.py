from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

import pytest

from doll import state, workspace
from doll.local_conversation import LocalConversationService
from doll.local_writing import (
    LocalWritingWorkflowService,
    LocalWritingWorkflowValidationError,
    WritingMode,
)
from doll.model_manifest import ModelManifestService
from doll.project_state import DecisionInfo, DecisionService
from doll.runtime_adapter import (
    LocalRuntimeBoundary,
    RuntimeAdapterContext,
    RuntimeAdapterDeclaration,
    RuntimeAdapterRegistry,
    RuntimeAdapterResponse,
    RuntimeGenerationRequest,
    RuntimeHealth,
    RuntimeInventorySnapshot,
    RuntimeStreamEvent,
)
from doll.state import ConversationRecord


@dataclass(slots=True)
class FakeImp066Adapter:
    adapter_id: str = "fake.imp066.local"
    output_text: str = "Finished IMP-066 writing result"
    prompts: list[str] = field(default_factory=list)

    def declaration(self) -> RuntimeAdapterDeclaration:
        return RuntimeAdapterDeclaration(
            adapter_id=self.adapter_id,
            adapter_version="1.0.0",
            runtime_class="fake.imp066.local",
            connection_kind="local_socket",
            supported_operations=("generate",),
        )

    def health(self) -> RuntimeHealth:
        return RuntimeHealth(self.adapter_id, "fake.imp066.runtime", "ready")

    def inventory(self, context: RuntimeAdapterContext) -> RuntimeInventorySnapshot:
        return RuntimeInventorySnapshot("fake.imp066.runtime", ())

    def generate(
        self,
        request: RuntimeGenerationRequest,
        context: RuntimeAdapterContext,
    ) -> RuntimeAdapterResponse:
        self.prompts.append(request.input_text)
        return RuntimeAdapterResponse(
            runtime_id="fake.imp066.runtime",
            model_id=request.model_id,
            output_text=self.output_text,
        )

    def stream(
        self,
        request: RuntimeGenerationRequest,
        context: RuntimeAdapterContext,
    ) -> Iterable[RuntimeStreamEvent]:
        return ()


def _workspace(tmp_path: Path) -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(tmp_path / "workspace")
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def _active_binding(
    repository: state.StateRepository,
    adapter: FakeImp066Adapter,
) -> None:
    service = ModelManifestService(repository)
    declaration = adapter.declaration()
    runtime = service.create_runtime(
        label="Fake IMP-066 runtime",
        adapter_id=declaration.adapter_id,
        adapter_version=declaration.adapter_version,
        runtime_class=declaration.runtime_class,
        connection_kind=declaration.connection_kind,
        operations=("cancel", "generate", "health"),
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
        runtime_private_locator="fake.imp066.model.1",
        display_name="Fake IMP-066 model",
        exact_revision="revision-1",
        checksums={"sha256": "d" * 64},
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
        scope_key="imp066-acceptance",
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


def _service(
    repository: state.StateRepository,
    adapter: FakeImp066Adapter,
) -> LocalWritingWorkflowService:
    return LocalWritingWorkflowService(
        repository,
        LocalConversationService(
            repository,
            LocalRuntimeBoundary(RuntimeAdapterRegistry((adapter,))),
        ),
    )


def _decision(
    repository: state.StateRepository,
    *,
    operation_id: str,
    reason: str = "Local continuity remains the governing constraint.",
) -> DecisionInfo:
    return DecisionService(repository).create(
        decision="Keep local state authoritative.",
        reason=reason,
        decision_status="accepted",
        decided_at="2026-07-17T00:00:00Z",
        alternatives=("Depend on one cloud provider.",),
        constraints=("No automatic cloud fallback.",),
        operation_id=operation_id,
    )


def _instruction_origin_count(repository: state.StateRepository) -> int:
    row = repository.connection.execute(
        "SELECT COUNT(*) FROM records WHERE record_type = 'instruction_origin'"
    ).fetchone()
    assert row is not None
    return int(row[0])


@pytest.mark.parametrize(
    ("mode", "source_text"),
    (
        ("draft", None),
        ("revise", "Revise this bounded local source."),
        ("summarize", "Summarize this bounded local source."),
    ),
)
def test_explicit_decision_context_works_in_all_writing_modes(
    tmp_path: Path,
    mode: WritingMode,
    source_text: str | None,
) -> None:
    initialized = _workspace(tmp_path)
    adapter = FakeImp066Adapter()
    conversation_id = str(uuid4())

    with state.open_state_repository(initialized.root) as repository:
        repository.save_conversation(
            ConversationRecord(conversation_id=conversation_id)
        )
        _active_binding(repository, adapter)
        decision = _decision(
            repository,
            operation_id=f"imp066.all-modes.{mode}.decision",
        )

        result = _service(repository, adapter).execute(
            mode=mode,
            conversation_id=conversation_id,
            scope_type="conversation",
            scope_key="imp066-acceptance",
            request_text=f"Run bounded {mode} mode with explicit decision context.",
            source_text=source_text,
            decision_ids=(decision.decision_id,),
            operation_id=f"imp066.all-modes.{mode}.execute",
        )

        assert result.outcome == "completed"
        assert result.mode == mode
        assert result.selected_decision_ids == (decision.decision_id,)
        assert result.selected_decision_revisions == (decision.revision,)

        prompt = json.loads(adapter.prompts[0])
        task = json.loads(
            prompt["channels"]["current_user_instruction"][0]["content"]
        )
        assert task["mode"] == mode
        assert task["selected_decision_count"] == 1

        snapshots = [
            json.loads(item["content"])
            for item in prompt["channels"]["untrusted_content"]
        ]
        decision_snapshots = [
            item for item in snapshots if item.get("context_kind") == "decision"
        ]
        assert len(decision_snapshots) == 1
        assert decision_snapshots[0]["record_id"] == decision.decision_id
        assert decision_snapshots[0]["revision"] == decision.revision


def test_oversized_decision_context_fails_before_runtime_or_origin_creation(
    tmp_path: Path,
) -> None:
    initialized = _workspace(tmp_path)
    adapter = FakeImp066Adapter()
    conversation_id = str(uuid4())

    with state.open_state_repository(initialized.root) as repository:
        repository.save_conversation(
            ConversationRecord(conversation_id=conversation_id)
        )
        _active_binding(repository, adapter)
        decision_ids = tuple(
            _decision(
                repository,
                operation_id=f"imp066.oversized.decision.{index}",
                reason=f"Large bounded reason {index}: " + ("x" * 5_800),
            ).decision_id
            for index in range(5)
        )
        before = _instruction_origin_count(repository)

        with pytest.raises(LocalWritingWorkflowValidationError):
            _service(repository, adapter).execute(
                mode="draft",
                conversation_id=conversation_id,
                scope_type="conversation",
                scope_key="imp066-acceptance",
                request_text="This oversized context must fail before execution.",
                decision_ids=decision_ids,
                operation_id="imp066.oversized.execute",
            )

        assert adapter.prompts == []
        assert _instruction_origin_count(repository) == before
