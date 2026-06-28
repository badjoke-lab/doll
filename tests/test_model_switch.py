from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from doll import state, workspace
from doll.model_manifest import ModelBindingInfo, ModelManifestService
from doll.model_switch import (
    DuplicateModelSwitchOperationError,
    ModelSwitchService,
    ModelSwitchValidationError,
)
from doll.runtime_adapter import (
    LocalRuntimeBoundary,
    RuntimeAdapterContext,
    RuntimeAdapterDeclaration,
    RuntimeAdapterFailure,
    RuntimeAdapterRegistry,
    RuntimeAdapterResponse,
    RuntimeGenerationRequest,
    RuntimeHealth,
    RuntimeInventorySnapshot,
    RuntimeStreamEvent,
)
from doll.state import ReadOnlyStateError


@dataclass(slots=True)
class SwitchAdapter:
    adapter_id: str = "switch.local"
    adapter_version: str = "1.0.0"
    responses: list[str | RuntimeAdapterFailure] = field(default_factory=list)
    prompts: list[str] = field(default_factory=list)
    models: list[str] = field(default_factory=list)
    mismatch_after_generations: int | None = None

    def declaration(self) -> RuntimeAdapterDeclaration:
        adapter_version = self.adapter_version
        if (
            self.mismatch_after_generations is not None
            and len(self.prompts) >= self.mismatch_after_generations
        ):
            adapter_version = "9.9.9"
        return RuntimeAdapterDeclaration(
            adapter_id=self.adapter_id,
            adapter_version=adapter_version,
            runtime_class="switch.local",
            connection_kind="local_socket",
            supported_operations=("generate",),
        )

    def health(self) -> RuntimeHealth:
        return RuntimeHealth(self.adapter_id, "switch.runtime", "ready")

    def inventory(self, context: RuntimeAdapterContext) -> RuntimeInventorySnapshot:
        return RuntimeInventorySnapshot("switch.runtime", ())

    def generate(
        self,
        request: RuntimeGenerationRequest,
        context: RuntimeAdapterContext,
    ) -> RuntimeAdapterResponse:
        del context
        self.prompts.append(request.input_text)
        self.models.append(request.model_id)
        response = self.responses.pop(0) if self.responses else "DOLL_SWITCH_OK"
        if isinstance(response, RuntimeAdapterFailure):
            raise response
        return RuntimeAdapterResponse(
            runtime_id="switch.runtime",
            model_id=request.model_id,
            output_text=response,
        )

    def stream(
        self,
        request: RuntimeGenerationRequest,
        context: RuntimeAdapterContext,
    ) -> Iterable[RuntimeStreamEvent]:
        del request, context
        return ()


def _workspace(tmp_path: Path) -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(tmp_path / "workspace")
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def _verified_runtime(
    service: ModelManifestService,
    adapter: SwitchAdapter,
) -> str:
    declaration = adapter.declaration()
    runtime = service.create_runtime(
        label="Switch runtime",
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
    return service.verify_runtime(
        runtime.runtime_manifest_id,
        expected_revision=runtime.revision,
    ).runtime_manifest_id


def _verified_model(
    service: ModelManifestService,
    runtime_id: str,
    name: str,
) -> str:
    model = service.create_model(
        runtime_manifest_id=runtime_id,
        runtime_private_locator=name,
        display_name=name,
        exact_revision=f"revision-{name}",
        checksums={"sha256": hashlib.sha256(name.encode("utf-8")).hexdigest()},
        license_id="test-license",
        model_format="test",
        platforms=("test",),
    )
    model = service.review_model_license(
        model.model_manifest_id,
        expected_revision=model.revision,
        review_state="reviewed_compatible",
    )
    return service.verify_model(
        model.model_manifest_id,
        expected_revision=model.revision,
    ).model_manifest_id


def _binding(
    service: ModelManifestService,
    runtime_id: str,
    model_id: str,
    *,
    scope_key: str = "default",
    active: bool = False,
) -> ModelBindingInfo:
    binding = service.create_binding(
        scope_type="conversation",
        scope_key=scope_key,
        runtime_manifest_id=runtime_id,
        model_manifest_id=model_id,
    )
    if active:
        binding = service.set_smoke_test(
            binding.binding_id,
            expected_revision=binding.revision,
            status="passed",
        )
        binding = service.activate_binding(
            binding.binding_id,
            expected_revision=binding.revision,
        )
    return binding


def _setup(
    repository: state.StateRepository,
    adapter: SwitchAdapter,
) -> tuple[ModelManifestService, ModelBindingInfo, ModelBindingInfo]:
    manifests = ModelManifestService(repository)
    runtime_id = _verified_runtime(manifests, adapter)
    first_model = _verified_model(manifests, runtime_id, "model.a")
    second_model = _verified_model(manifests, runtime_id, "model.b")
    active = _binding(manifests, runtime_id, first_model, active=True)
    target = _binding(manifests, runtime_id, second_model)
    return manifests, active, target


def _service(
    repository: state.StateRepository,
    adapter: SwitchAdapter,
) -> ModelSwitchService:
    return ModelSwitchService(
        repository,
        LocalRuntimeBoundary(RuntimeAdapterRegistry((adapter,))),
    )


def _record_types(repository: state.StateRepository) -> set[str]:
    return {
        str(row[0])
        for row in repository.connection.execute(
            "SELECT DISTINCT record_type FROM records"
        ).fetchall()
    }


def test_explicit_switch_runs_two_bounded_probes_and_preserves_previous(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    adapter = SwitchAdapter()
    with state.open_state_repository(initialized.root) as repository:
        manifests, active, target = _setup(repository, adapter)
        before_types = _record_types(repository)
        result = _service(repository, adapter).switch_binding(
            scope_type="conversation",
            scope_key="default",
            target_binding_id=target.binding_id,
            operation_id="switch.success",
        )

        assert result.outcome == "switched"
        assert result.previous_binding_id == active.binding_id
        assert result.active_binding_id == target.binding_id
        assert result.target_binding_id == target.binding_id
        assert result.failure_code is None
        assert result.fallback_selected is False
        assert result.scope_key_hash.startswith("sha256:")
        assert "default" not in repr(result)
        assert "DOLL_SWITCH_OK" not in repr(result)
        assert result.target_runtime_manifest_id == target.runtime_manifest_id
        assert result.target_model_manifest_id == target.model_manifest_id
        assert manifests.get_binding(active.binding_id).binding_state == "previous"
        assert manifests.get_binding(target.binding_id).binding_state == "active"
        resolved, _, _ = manifests.resolve_active_binding(
            scope_type="conversation", scope_key="default"
        )
        assert resolved.binding_id == target.binding_id
        assert len(adapter.prompts) == 2
        assert adapter.prompts[0] == adapter.prompts[1]
        assert "local_model_switch_smoke_test" in adapter.prompts[0]
        assert adapter.models == ["model.b", "model.b"]
        after_types = _record_types(repository)
        assert after_types == before_types
        assert "conversation_event" not in after_types
        assert "instruction_origin" not in after_types


def test_target_and_fallback_lists_are_deterministic_and_validated(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    adapter = SwitchAdapter()
    with state.open_state_repository(initialized.root) as repository:
        manifests, active, first = _setup(repository, adapter)
        runtime_id = first.runtime_manifest_id
        third_model = _verified_model(manifests, runtime_id, "model.c")
        second = _binding(manifests, runtime_id, third_model)
        first = manifests.set_smoke_test(
            first.binding_id, expected_revision=first.revision, status="passed"
        )
        first = manifests.set_fallback(
            first.binding_id, expected_revision=first.revision, priority=20
        )
        second = manifests.set_smoke_test(
            second.binding_id, expected_revision=second.revision, status="passed"
        )
        second = manifests.set_fallback(
            second.binding_id, expected_revision=second.revision, priority=10
        )
        service = _service(repository, adapter)

        targets = service.list_switch_targets(scope_type="conversation", scope_key="default")
        assert {item.binding_id for item in targets} == {
            first.binding_id,
            second.binding_id,
        }
        assert active.binding_id not in {item.binding_id for item in targets}
        fallbacks = service.list_fallback_candidates(scope_type="conversation", scope_key="default")
        assert [item.binding_id for item in fallbacks] == [
            second.binding_id,
            first.binding_id,
        ]


def test_explicit_fallback_switch_requires_eligible_selected_binding(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    adapter = SwitchAdapter()
    with state.open_state_repository(initialized.root) as repository:
        manifests, active, target = _setup(repository, adapter)
        service = _service(repository, adapter)
        with pytest.raises(ModelSwitchValidationError, match="eligible fallback"):
            service.switch_to_fallback(
                scope_type="conversation",
                scope_key="default",
                target_binding_id=target.binding_id,
                operation_id="switch.not-fallback",
            )
        target = manifests.set_smoke_test(
            target.binding_id, expected_revision=target.revision, status="passed"
        )
        target = manifests.set_fallback(
            target.binding_id, expected_revision=target.revision, priority=1
        )
        result = service.switch_to_fallback(
            scope_type="conversation",
            scope_key="default",
            target_binding_id=target.binding_id,
            operation_id="switch.fallback",
        )
        assert result.outcome == "switched"
        assert result.fallback_selected is True
        assert result.previous_binding_id == active.binding_id


def test_failed_preflight_leaves_active_binding_unchanged(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    adapter = SwitchAdapter(responses=[""])
    with state.open_state_repository(initialized.root) as repository:
        manifests, active, target = _setup(repository, adapter)
        result = _service(repository, adapter).switch_binding(
            scope_type="conversation",
            scope_key="default",
            target_binding_id=target.binding_id,
            operation_id="switch.preflight-fail",
        )
        assert result.outcome == "preflight_failed"
        assert result.failure_code == "invalid_response"
        assert result.active_binding_id == active.binding_id
        assert manifests.get_binding(active.binding_id).binding_state == "active"
        failed = manifests.get_binding(target.binding_id)
        assert failed.binding_state == "candidate"
        assert failed.smoke_test_status == "failed"
        assert len(adapter.prompts) == 1


def test_runtime_failure_preflight_is_bounded(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    adapter = SwitchAdapter(responses=[RuntimeAdapterFailure("timeout")])
    with state.open_state_repository(initialized.root) as repository:
        _, active, target = _setup(repository, adapter)
        result = _service(repository, adapter).switch_binding(
            scope_type="conversation",
            scope_key="default",
            target_binding_id=target.binding_id,
            operation_id="switch.timeout",
        )
        assert result.outcome == "preflight_failed"
        assert result.failure_code == "timeout"
        assert result.active_binding_id == active.binding_id


def test_failed_post_activation_probe_restores_exact_previous_binding(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    adapter = SwitchAdapter(responses=["DOLL_SWITCH_OK", ""])
    with state.open_state_repository(initialized.root) as repository:
        manifests, active, target = _setup(repository, adapter)
        unrelated = repository.create_record(
            record_type="test_record",
            title="Unrelated",
            metadata={"value": "unchanged"},
            provenance="user-created",
            sensitivity="internal",
        )
        result = _service(repository, adapter).switch_binding(
            scope_type="conversation",
            scope_key="default",
            target_binding_id=target.binding_id,
            operation_id="switch.rollback",
        )
        assert result.outcome == "rolled_back"
        assert result.failure_code == "invalid_response"
        assert result.active_binding_id == active.binding_id
        restored, _, _ = manifests.resolve_active_binding(
            scope_type="conversation", scope_key="default"
        )
        assert restored.binding_id == active.binding_id
        rejected = manifests.get_binding(target.binding_id)
        assert rejected.binding_state == "rolled_back"
        assert rejected.smoke_test_status == "failed"
        assert repository.get_record(unrelated.id) == unrelated


def test_post_activation_declaration_mismatch_rolls_back(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    adapter = SwitchAdapter(mismatch_after_generations=1)
    with state.open_state_repository(initialized.root) as repository:
        manifests, active, target = _setup(repository, adapter)
        result = _service(repository, adapter).switch_binding(
            scope_type="conversation",
            scope_key="default",
            target_binding_id=target.binding_id,
            operation_id="switch.post-declaration-mismatch",
        )
        assert result.outcome == "rolled_back"
        assert result.failure_code == "invalid_response"
        assert result.active_binding_id == active.binding_id
        restored, _, _ = manifests.resolve_active_binding(
            scope_type="conversation", scope_key="default"
        )
        assert restored.binding_id == active.binding_id
        rejected = manifests.get_binding(target.binding_id)
        assert rejected.binding_state == "rolled_back"
        assert rejected.smoke_test_status == "failed"
        assert len(adapter.prompts) == 1


def test_probe_output_and_raw_scope_key_are_not_persisted(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    adapter = SwitchAdapter()
    with state.open_state_repository(initialized.root) as repository:
        manifests = ModelManifestService(repository)
        runtime_id = _verified_runtime(manifests, adapter)
        active_model = _verified_model(manifests, runtime_id, "model.private-a")
        target_model = _verified_model(manifests, runtime_id, "model.private-b")
        _binding(
            manifests,
            runtime_id,
            active_model,
            scope_key="sensitive-scope-key",
            active=True,
        )
        target = _binding(
            manifests,
            runtime_id,
            target_model,
            scope_key="sensitive-scope-key",
        )
        result = _service(repository, adapter).switch_binding(
            scope_type="conversation",
            scope_key="sensitive-scope-key",
            target_binding_id=target.binding_id,
            operation_id="switch.private-metadata",
        )
        assert result.outcome == "switched"
        rows = repository.connection.execute(
            "SELECT action, metadata_json FROM audit_events "
            "WHERE operation_id LIKE 'switch.private-metadata%'"
        ).fetchall()
        serialized = "\n".join(f"{row[0]} {row[1]}" for row in rows)
        assert "DOLL_SWITCH_OK" not in serialized
        assert "local_model_switch_smoke_test" not in serialized
        assert "sensitive-scope-key" not in serialized


def test_invalid_scope_current_target_and_adapter_mismatch_call_no_runtime(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    adapter = SwitchAdapter()
    with state.open_state_repository(initialized.root) as repository:
        manifests, active, target = _setup(repository, adapter)
        other = _binding(
            manifests,
            target.runtime_manifest_id,
            target.model_manifest_id,
            scope_key="other",
        )
        service = _service(repository, adapter)
        with pytest.raises(ModelSwitchValidationError, match="already active"):
            service.switch_binding(
                scope_type="conversation",
                scope_key="default",
                target_binding_id=active.binding_id,
                operation_id="switch.current",
            )
        with pytest.raises(ModelSwitchValidationError, match="another scope"):
            service.switch_binding(
                scope_type="conversation",
                scope_key="default",
                target_binding_id=other.binding_id,
                operation_id="switch.cross-scope",
            )
        mismatch = SwitchAdapter(adapter_version="2.0.0")
        with pytest.raises(ModelSwitchValidationError, match="does not match"):
            _service(repository, mismatch).switch_binding(
                scope_type="conversation",
                scope_key="default",
                target_binding_id=target.binding_id,
                operation_id="switch.mismatch",
            )
        assert adapter.prompts == []
        assert mismatch.prompts == []


def test_duplicate_operation_is_rejected_after_failed_or_successful_attempt(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    adapter = SwitchAdapter(responses=[""])
    with state.open_state_repository(initialized.root) as repository:
        _, _, target = _setup(repository, adapter)
        service = _service(repository, adapter)
        service.switch_binding(
            scope_type="conversation",
            scope_key="default",
            target_binding_id=target.binding_id,
            operation_id="switch.duplicate",
        )
        with pytest.raises(DuplicateModelSwitchOperationError):
            service.switch_binding(
                scope_type="conversation",
                scope_key="default",
                target_binding_id=target.binding_id,
                operation_id="switch.duplicate",
            )


def test_read_only_and_invalid_constructor_or_operation_are_rejected(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    adapter = SwitchAdapter()
    with state.open_state_repository(initialized.root) as repository:
        _, _, target = _setup(repository, adapter)
        with pytest.raises(ModelSwitchValidationError, match="runtime boundary"):
            ModelSwitchService(repository, object())  # type: ignore[arg-type]
        with pytest.raises(ModelSwitchValidationError, match="operation ID"):
            _service(repository, adapter).switch_binding(
                scope_type="conversation",
                scope_key="default",
                target_binding_id=target.binding_id,
                operation_id="bad operation",
            )
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        target = ModelManifestService(repository).list_bindings()[1]
        with pytest.raises(ReadOnlyStateError):
            _service(repository, adapter).switch_binding(
                scope_type="conversation",
                scope_key="default",
                target_binding_id=target.binding_id,
                operation_id="switch.readonly",
            )


def test_listing_skips_unregistered_target_and_missing_active_is_bounded(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    adapter = SwitchAdapter()
    with state.open_state_repository(initialized.root) as repository:
        manifests, _, target = _setup(repository, adapter)
        other_adapter = SwitchAdapter(adapter_id="switch.other")
        other_runtime = _verified_runtime(manifests, other_adapter)
        other_model = _verified_model(manifests, other_runtime, "model.other")
        unregistered = _binding(manifests, other_runtime, other_model)
        targets = _service(repository, adapter).list_switch_targets(
            scope_type="conversation", scope_key="default"
        )
        assert [item.binding_id for item in targets] == [target.binding_id]
        assert unregistered.binding_id not in {item.binding_id for item in targets}
        with pytest.raises(ModelSwitchValidationError, match="active local"):
            _service(repository, adapter).list_switch_targets(
                scope_type="conversation", scope_key="missing"
            )
