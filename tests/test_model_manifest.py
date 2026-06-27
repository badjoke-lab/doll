from __future__ import annotations

from pathlib import Path

import pytest

import doll.restore as restore
from doll import state, workspace
from doll.audit import AuditService
from doll.backup import create_state_backup
from doll.model_manifest import (
    ModelBindingInfo,
    ModelManifestCorruptError,
    ModelManifestInfo,
    ModelManifestService,
    ModelManifestValidationError,
    RuntimeManifestInfo,
    _binding_from_record,
    _model_from_record,
    _runtime_from_record,
)
from doll.state import RecordEnvelope, StaleRevisionError
from doll.state_package import (
    export_state_package,
    import_state_package,
    inspect_state_package,
    verify_state_package,
)
from doll.state_package_registry import get_authoritative_record_registry


def _workspace(tmp_path: Path, name: str = "workspace") -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(tmp_path / name)
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def _runtime(service: ModelManifestService, *, actor_type: str = "user") -> RuntimeManifestInfo:
    return service.create_runtime(
        label="Local Ollama",
        adapter_id="ollama.local",
        adapter_version="1",
        runtime_class="ollama",
        connection_kind="loopback_http",
        operations=("health", "inventory", "generate", "stream", "cancel"),
        offline_capable=True,
        cloud_fallback=False,
        automatic_download=False,
        runtime_version="0.9.0",
        platforms=("darwin-x86_64", "linux-x86_64", "windows-x86_64"),
        compatibility=("ollama-api-v1",),
        source_references=("official:ollama-api",),
        actor_type=actor_type,  # type: ignore[arg-type]
    )


def _verified_runtime(service: ModelManifestService) -> RuntimeManifestInfo:
    runtime = _runtime(service)
    return service.verify_runtime(runtime.runtime_manifest_id, expected_revision=runtime.revision)


def _model(
    service: ModelManifestService, runtime_id: str, *, actor_type: str = "user"
) -> ModelManifestInfo:
    return service.create_model(
        runtime_manifest_id=runtime_id,
        runtime_private_locator="qwen2.5:7b",
        display_name="Qwen 2.5 7B",
        exact_revision="sha256-model-revision-1",
        checksums={"sha256": "a" * 64},
        license_id="apache-2.0",
        model_format="gguf",
        size_bytes=4_000_000_000,
        context_limit=32768,
        capabilities=("chat", "stream"),
        platforms=("darwin-x86_64", "linux-x86_64"),
        compatibility=("ollama-api-v1",),
        source_references=("official:model-card",),
        actor_type=actor_type,  # type: ignore[arg-type]
    )


def _verified_model(service: ModelManifestService, runtime_id: str) -> ModelManifestInfo:
    model = _model(service, runtime_id)
    model = service.review_model_license(
        model.model_manifest_id,
        expected_revision=model.revision,
        review_state="reviewed_compatible",
    )
    return service.verify_model(model.model_manifest_id, expected_revision=model.revision)


def _passed_binding(
    service: ModelManifestService, runtime_id: str, model_id: str, scope: str
) -> ModelBindingInfo:
    binding = service.create_binding(
        scope_type="project",
        scope_key=scope,
        runtime_manifest_id=runtime_id,
        model_manifest_id=model_id,
    )
    return service.set_smoke_test(
        binding.binding_id,
        expected_revision=binding.revision,
        status="passed",
    )


def test_schema_three_and_indexes_are_created(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        assert repository.status().schema_version == 3
        indexes = {
            row[0]
            for row in repository.connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            ).fetchall()
        }
    assert {
        "runtime_manifest_state_idx",
        "model_manifest_runtime_idx",
        "model_binding_scope_state_idx",
        "model_binding_one_active_scope_idx",
    } <= indexes


def test_create_verify_and_audit_records(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        service = ModelManifestService(repository)
        runtime = _verified_runtime(service)
        model = _verified_model(service, runtime.runtime_manifest_id)
        binding = _passed_binding(
            service,
            runtime.runtime_manifest_id,
            model.model_manifest_id,
            "project-alpha",
        )
        binding = service.activate_binding(binding.binding_id, expected_revision=binding.revision)
        actions = {event.action for event in AuditService(repository).list(limit=50)}

    assert runtime.manifest_state == "verified"
    assert model.manifest_state == "verified"
    assert model.license_review_state == "reviewed_compatible"
    assert binding.binding_state == "active"
    assert binding.activated_at is not None
    assert runtime.declaration_fingerprint.startswith("sha256:")
    assert {
        "runtime_manifest.create",
        "runtime_manifest.verify",
        "model_manifest.create",
        "model_manifest.review_license",
        "model_manifest.verify",
        "model_binding.create",
        "model_binding.smoke_test",
        "model_binding.activate",
    } <= actions


def test_untrusted_actor_cannot_verify_review_activate_fallback_or_rollback(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        service = ModelManifestService(repository)
        runtime = _runtime(service, actor_type="model")
        assert runtime.provenance == "model-proposed"
        with pytest.raises(ModelManifestValidationError, match="requires the user path"):
            service.verify_runtime(
                runtime.runtime_manifest_id,
                expected_revision=runtime.revision,
                actor_type="model",
            )

        runtime = service.verify_runtime(
            runtime.runtime_manifest_id, expected_revision=runtime.revision
        )
        model = _model(service, runtime.runtime_manifest_id, actor_type="importer")
        assert model.provenance == "imported"
        with pytest.raises(ModelManifestValidationError, match="requires the user path"):
            service.review_model_license(
                model.model_manifest_id,
                expected_revision=model.revision,
                review_state="reviewed_compatible",
                actor_type="importer",
            )


def test_local_only_runtime_is_required_for_verification(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        service = ModelManifestService(repository)
        runtime = service.create_runtime(
            label="Unsafe runtime",
            adapter_id="unsafe.runtime",
            adapter_version="1",
            runtime_class="test",
            connection_kind="remote_http",
            operations=("health",),
            offline_capable=False,
            cloud_fallback=True,
            automatic_download=True,
        )
        with pytest.raises(ModelManifestValidationError, match="not local-only"):
            service.verify_runtime(runtime.runtime_manifest_id, expected_revision=runtime.revision)


def test_license_and_verified_runtime_gate_model_verification(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        service = ModelManifestService(repository)
        runtime = _runtime(service)
        model = _model(service, runtime.runtime_manifest_id)
        with pytest.raises(ModelManifestValidationError, match="runtime is not verified"):
            service.verify_model(model.model_manifest_id, expected_revision=model.revision)
        runtime = service.verify_runtime(
            runtime.runtime_manifest_id, expected_revision=runtime.revision
        )
        with pytest.raises(ModelManifestValidationError, match="license has not"):
            service.verify_model(model.model_manifest_id, expected_revision=model.revision)
        model = service.review_model_license(
            model.model_manifest_id,
            expected_revision=model.revision,
            review_state="rejected",
        )
        with pytest.raises(ModelManifestValidationError, match="license has not"):
            service.verify_model(model.model_manifest_id, expected_revision=model.revision)


def test_quarantine_blocks_activation(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        service = ModelManifestService(repository)
        runtime = _verified_runtime(service)
        model = _verified_model(service, runtime.runtime_manifest_id)
        binding = _passed_binding(
            service,
            runtime.runtime_manifest_id,
            model.model_manifest_id,
            "project-quarantine",
        )
        model = service.quarantine_model(
            model.model_manifest_id,
            expected_revision=model.revision,
            reason="Synthetic checksum mismatch",
        )
        assert model.manifest_state == "quarantined"
        with pytest.raises(ModelManifestValidationError, match="model is not verified"):
            service.activate_binding(binding.binding_id, expected_revision=binding.revision)


def test_binding_activation_retains_previous_and_rolls_back_scope_only(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        service = ModelManifestService(repository)
        runtime = _verified_runtime(service)
        first_model = _verified_model(service, runtime.runtime_manifest_id)
        first = _passed_binding(
            service,
            runtime.runtime_manifest_id,
            first_model.model_manifest_id,
            "project-scope",
        )
        first = service.activate_binding(first.binding_id, expected_revision=first.revision)

        second_model = _verified_model(service, runtime.runtime_manifest_id)
        second = _passed_binding(
            service,
            runtime.runtime_manifest_id,
            second_model.model_manifest_id,
            "project-scope",
        )
        second = service.activate_binding(second.binding_id, expected_revision=second.revision)
        first = service.get_binding(first.binding_id)
        assert first.binding_state == "previous"
        assert second.previous_binding_id == first.binding_id

        other = _passed_binding(
            service,
            runtime.runtime_manifest_id,
            second_model.model_manifest_id,
            "other-scope",
        )
        other = service.activate_binding(other.binding_id, expected_revision=other.revision)
        other_revision = other.revision

        rolled_back = service.rollback_binding(
            second.binding_id,
            expected_revision=second.revision,
            reason="Synthetic regression",
        )
        restored = service.get_binding(first.binding_id)
        unchanged_other = service.get_binding(other.binding_id)

    assert rolled_back.binding_state == "rolled_back"
    assert rolled_back.rollback_target_id == first.binding_id
    assert restored.binding_state == "active"
    assert unchanged_other.binding_state == "active"
    assert unchanged_other.revision == other_revision


def test_one_active_binding_per_scope_is_database_enforced(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        service = ModelManifestService(repository)
        runtime = _verified_runtime(service)
        model = _verified_model(service, runtime.runtime_manifest_id)
        first = _passed_binding(
            service, runtime.runtime_manifest_id, model.model_manifest_id, "one"
        )
        first = service.activate_binding(first.binding_id, expected_revision=first.revision)
        second = _passed_binding(
            service, runtime.runtime_manifest_id, model.model_manifest_id, "one"
        )
        # The service moves the previous active binding deterministically.
        second = service.activate_binding(second.binding_id, expected_revision=second.revision)
        assert service.get_binding(first.binding_id).binding_state == "previous"
        assert second.binding_state == "active"
        count = repository.connection.execute(
            "SELECT COUNT(*) FROM records WHERE record_type = 'model_binding' "
            "AND json_extract(metadata_json, '$.scope_key') = 'one' "
            "AND json_extract(metadata_json, '$.binding_state') = 'active'"
        ).fetchone()[0]
        assert count == 1


def test_fallback_requires_user_verified_manifests_and_passed_smoke_test(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        service = ModelManifestService(repository)
        runtime = _verified_runtime(service)
        model = _verified_model(service, runtime.runtime_manifest_id)
        binding = service.create_binding(
            scope_type="global",
            scope_key="default",
            runtime_manifest_id=runtime.runtime_manifest_id,
            model_manifest_id=model.model_manifest_id,
        )
        with pytest.raises(ModelManifestValidationError, match="smoke test"):
            service.set_fallback(binding.binding_id, expected_revision=binding.revision, priority=1)
        binding = service.set_smoke_test(
            binding.binding_id,
            expected_revision=binding.revision,
            status="passed",
        )
        with pytest.raises(ModelManifestValidationError, match="requires the user path"):
            service.set_fallback(
                binding.binding_id,
                expected_revision=binding.revision,
                priority=1,
                actor_type="model",
            )
        binding = service.set_fallback(
            binding.binding_id,
            expected_revision=binding.revision,
            priority=10,
        )
    assert binding.binding_state == "fallback"
    assert binding.fallback_eligible is True
    assert binding.fallback_priority == 10


def test_stale_revision_failure_preserves_record(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        service = ModelManifestService(repository)
        runtime = _runtime(service)
        verified = service.verify_runtime(
            runtime.runtime_manifest_id, expected_revision=runtime.revision
        )
        before = repository.status().state_revision
        with pytest.raises(StaleRevisionError):
            service.quarantine_runtime(
                runtime.runtime_manifest_id,
                expected_revision=runtime.revision,
                reason="Stale request",
                actor_type="user",
            )
        after = service.get_runtime(runtime.runtime_manifest_id)
        assert after == verified
        assert repository.status().state_revision == before


def test_private_locator_url_and_secret_shaped_metadata_are_rejected(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        service = ModelManifestService(repository)
        runtime = _verified_runtime(service)
        for locator in ("https://example.invalid/model", "/Users/alice/model.gguf", "token@host"):
            with pytest.raises(ModelManifestValidationError, match="unsafe"):
                service.create_model(
                    runtime_manifest_id=runtime.runtime_manifest_id,
                    runtime_private_locator=locator,
                    display_name="Unsafe",
                    exact_revision="revision",
                    checksums={"sha256": "a" * 64},
                    license_id="unknown",
                    model_format="gguf",
                )


def test_corrupt_records_are_rejected() -> None:
    base = dict(
        id="00000000-0000-4000-8000-000000000001",
        schema_version=1,
        created_at="2026-06-26T00:00:00Z",
        updated_at="2026-06-26T00:00:00Z",
        revision=1,
        status="active",
        provenance="user-created",
        sensitivity="personal",
        title="bad",
    )
    for parser, record_type in (
        (_runtime_from_record, "runtime_manifest"),
        (_model_from_record, "model_manifest"),
        (_binding_from_record, "model_binding"),
    ):
        record = RecordEnvelope(record_type=record_type, metadata={}, **base)  # type: ignore[arg-type]
        with pytest.raises(ModelManifestCorruptError):
            parser(record)


def test_state_package_v2_round_trip_and_v1_registry_neutrality(tmp_path: Path) -> None:
    source = _workspace(tmp_path, "source")
    with state.open_state_repository(source.root) as repository:
        service = ModelManifestService(repository)
        runtime = _verified_runtime(service)
        model = _verified_model(service, runtime.runtime_manifest_id)
        binding = _passed_binding(
            service,
            runtime.runtime_manifest_id,
            model.model_manifest_id,
            "portable-scope",
        )
        service.activate_binding(binding.binding_id, expected_revision=binding.revision)

    package_path = tmp_path / "state.zip"
    with state.open_state_repository(source.root, read_only=True) as repository:
        inspection = export_state_package(repository, package_path)
    verified = verify_state_package(package_path)
    inspected = inspect_state_package(package_path)
    assert verified.record_counts["runtime_manifest"] == 1
    assert verified.record_counts["model_manifest"] == 1
    assert verified.record_counts["model_binding"] == 1
    assert inspected == verified == inspection

    target = tmp_path / "target"
    result = import_state_package(package_path, target)
    with state.open_state_repository(target, read_only=True) as repository:
        service = ModelManifestService(repository)
        assert len(service.list_runtimes()) == 1
        assert len(service.list_models()) == 1
        assert service.list_bindings()[0].binding_state == "active"
        assert repository.status().state_revision == result.imported_state_revision

    v1 = get_authoritative_record_registry(1)
    v2 = get_authoritative_record_registry(2)
    assert "runtime_manifest" not in v1.record_types
    assert {"runtime_manifest", "model_manifest", "model_binding"} <= v2.record_types


def test_selectable_bindings_block_manifest_deactivation(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        service = ModelManifestService(repository)
        runtime = _verified_runtime(service)
        model = _verified_model(service, runtime.runtime_manifest_id)
        binding = _passed_binding(
            service,
            runtime.runtime_manifest_id,
            model.model_manifest_id,
            "deactivation-scope",
        )
        binding = service.activate_binding(binding.binding_id, expected_revision=binding.revision)
        with pytest.raises(ModelManifestValidationError, match="must be disabled"):
            service.quarantine_model(
                model.model_manifest_id,
                expected_revision=model.revision,
                reason="Synthetic issue",
            )
        with pytest.raises(ModelManifestValidationError, match="must be disabled"):
            service.mark_runtime_unavailable(
                runtime.runtime_manifest_id,
                expected_revision=runtime.revision,
            )
        binding = service.disable_binding(binding.binding_id, expected_revision=binding.revision)
        model = service.quarantine_model(
            model.model_manifest_id,
            expected_revision=model.revision,
            reason="Synthetic issue",
        )
        runtime = service.mark_runtime_unavailable(
            runtime.runtime_manifest_id,
            expected_revision=runtime.revision,
        )
    assert binding.binding_state == "disabled"
    assert model.manifest_state == "quarantined"
    assert runtime.manifest_state == "unavailable"


def test_verified_model_identity_and_license_review_are_immutable(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        service = ModelManifestService(repository)
        runtime = _verified_runtime(service)
        model = _verified_model(service, runtime.runtime_manifest_id)
        before = repository.get_record(model.model_manifest_id)
        with pytest.raises(ModelManifestValidationError, match="immutable"):
            service.review_model_license(
                model.model_manifest_id,
                expected_revision=model.revision,
                review_state="rejected",
            )
        after = repository.get_record(model.model_manifest_id)
    assert after == before
    assert after.metadata["exact_revision"] == "sha256-model-revision-1"
    assert after.metadata["checksums"] == [{"algorithm": "sha256", "value": "a" * 64}]


def test_state_backup_restore_and_fresh_process_preserve_bindings_without_runtime(
    tmp_path: Path,
) -> None:
    initialized = _workspace(tmp_path, "backup-source")
    with state.open_state_repository(initialized.root) as repository:
        service = ModelManifestService(repository)
        runtime = _verified_runtime(service)
        model = _verified_model(service, runtime.runtime_manifest_id)
        binding = _passed_binding(
            service,
            runtime.runtime_manifest_id,
            model.model_manifest_id,
            "backup-scope",
        )
        binding = service.activate_binding(binding.binding_id, expected_revision=binding.revision)
        binding_id = binding.binding_id

    backup_path = tmp_path / "manifest-state-backup.zip"
    create_state_backup(
        initialized.root,
        backup_path,
        created_at="2026-06-26T18:00:00Z",
        operation_id="imp-050-state-backup",
    )
    target = tmp_path / "backup-restored"
    result = restore.restore_state_backup(backup_path, target)
    assert result.fresh_process_validated is True

    with state.open_state_repository(target, read_only=True) as repository:
        service = ModelManifestService(repository)
        restored = service.get_binding(binding_id)
        assert restored.binding_state == "active"
        assert len(service.list_runtimes()) == 1
        assert len(service.list_models()) == 1
        assert repository.status().schema_version == state.CURRENT_SCHEMA_VERSION
