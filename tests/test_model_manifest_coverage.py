from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from doll import state, workspace
from doll.model_manifest import (
    ModelManifestCorruptError,
    ModelManifestService,
    ModelManifestValidationError,
    _binding_from_record,
    _binding_state,
    _bool,
    _checksum_payload,
    _checksums,
    _fingerprint,
    _license_state,
    _list,
    _locator,
    _manifest_state,
    _model_from_record,
    _optional_positive_int,
    _optional_text,
    _optional_timestamp,
    _optional_token,
    _optional_uuid,
    _positive_int,
    _references,
    _runtime_from_record,
    _scope_key,
    _smoke_state,
    _text,
    _token,
    _tokens,
    _uuid,
    _uuid_list,
)
from doll.state import ReadOnlyStateError, RecordEnvelope


def _workspace(tmp_path: Path, name: str = "workspace") -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(tmp_path / name)
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def _runtime(
    service: ModelManifestService,
    *,
    platforms: tuple[str, ...] = ("linux-x86_64",),
    verify: bool = True,
) -> Any:
    runtime = service.create_runtime(
        label="Local runtime",
        adapter_id="ollama.local",
        adapter_version="1",
        runtime_class="ollama",
        connection_kind="loopback_http",
        operations=("health", "inventory", "generate"),
        offline_capable=True,
        cloud_fallback=False,
        automatic_download=False,
        platforms=platforms,
        compatibility=("ollama-api-v1",),
    )
    if verify:
        runtime = service.verify_runtime(
            runtime.runtime_manifest_id,
            expected_revision=runtime.revision,
        )
    return runtime


def _model(
    service: ModelManifestService,
    runtime_id: str,
    *,
    platforms: tuple[str, ...] = ("linux-x86_64",),
    verify: bool = True,
) -> Any:
    model = service.create_model(
        runtime_manifest_id=runtime_id,
        runtime_private_locator=f"model-{uuid4()}:latest",
        display_name="Local model",
        exact_revision=f"revision-{uuid4()}",
        checksums={"sha256": "a" * 64},
        license_id="apache-2.0",
        model_format="gguf",
        platforms=platforms,
        compatibility=("ollama-api-v1",),
    )
    if verify:
        model = service.review_model_license(
            model.model_manifest_id,
            expected_revision=model.revision,
            review_state="reviewed_restricted",
        )
        model = service.verify_model(
            model.model_manifest_id,
            expected_revision=model.revision,
        )
    return model


def _binding(service: ModelManifestService, runtime_id: str, model_id: str) -> Any:
    return service.create_binding(
        scope_type="project",
        scope_key=f"scope-{uuid4()}",
        runtime_manifest_id=runtime_id,
        model_manifest_id=model_id,
    )


def _envelope(record_type: str, metadata: dict[str, object]) -> RecordEnvelope:
    return RecordEnvelope(
        id=str(uuid4()),
        record_type=record_type,
        schema_version=1,
        created_at="2026-06-27T00:00:00Z",
        updated_at="2026-06-27T00:00:00Z",
        revision=1,
        status="active",
        provenance="user-created",
        sensitivity="personal",
        title="Synthetic",
        metadata=metadata,
    )


def test_validation_helpers_cover_closed_failure_paths() -> None:
    invalid_calls: tuple[Callable[[], object], ...] = (
        lambda: _fingerprint("sha256:not-a-digest"),
        lambda: _checksums({}),
        lambda: _checksums({"sha256": "z" * 64}),
        lambda: _checksum_payload("not-a-list"),
        lambda: _checksum_payload([{"algorithm": "sha256"}]),
        lambda: _checksum_payload(
            [
                {"algorithm": "sha256", "value": "a" * 64},
                {"algorithm": "sha256", "value": "b" * 64},
            ]
        ),
        lambda: _locator("https://example.invalid/model"),
        lambda: _scope_key("/Users/alice/private"),
        lambda: _references(["ref"] * 129),
        lambda: _references(["/home/alice/private"]),
        lambda: _references(["duplicate", "duplicate"]),
        lambda: _tokens("values", [str(index) for index in range(129)]),
        lambda: _tokens("values", ["duplicate", "duplicate"]),
        lambda: _tokens("operations", ["unknown"], allowed=frozenset({"health"})),
        lambda: _token("token", "contains space"),
        lambda: _text("text", " padded ", 20),
        lambda: _text("text", "\x00", 20),
        lambda: _bool("flag", 1),
        lambda: _positive_int("count", True),
        lambda: _uuid("ID", 3),
        lambda: _uuid("ID", "not-a-uuid"),
        lambda: _uuid("ID", str(uuid4()).upper()),
        lambda: _uuid_list("IDs", [str(uuid4())] * 129),
        lambda: _list(()),
        lambda: _manifest_state("invalid"),
        lambda: _license_state("invalid"),
        lambda: _binding_state("invalid"),
        lambda: _smoke_state("invalid"),
        lambda: _optional_timestamp("2026-06-27"),
    )
    for call in invalid_calls:
        with pytest.raises(ModelManifestValidationError):
            call()

    duplicate_id = str(uuid4())
    with pytest.raises(ModelManifestValidationError, match="duplicates"):
        _uuid_list("IDs", [duplicate_id, duplicate_id])

    assert _optional_token("token", None) is None
    assert _optional_text("text", None, 10) is None
    assert _optional_positive_int("count", None) is None
    assert _optional_uuid("ID", None) is None
    assert _optional_timestamp(None) is None


def test_manifest_lifecycle_authority_and_archived_listing(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        service = ModelManifestService(repository)
        runtime = _runtime(service)
        model = _model(service, runtime.runtime_manifest_id)

        with pytest.raises(ModelManifestValidationError, match="requires the user path"):
            service.deprecate_runtime(
                runtime.runtime_manifest_id,
                expected_revision=runtime.revision,
                actor_type="model",
            )
        with pytest.raises(ModelManifestValidationError, match="authority"):
            service.mark_runtime_unavailable(
                runtime.runtime_manifest_id,
                expected_revision=runtime.revision,
                actor_type="runtime",
            )
        with pytest.raises(ModelManifestValidationError, match="authority"):
            service.mark_model_unavailable(
                model.model_manifest_id,
                expected_revision=model.revision,
                actor_type="importer",
            )
        with pytest.raises(ModelManifestValidationError, match="authority"):
            service.quarantine_runtime(
                runtime.runtime_manifest_id,
                expected_revision=runtime.revision,
                reason="Synthetic",
                actor_type="model",
            )

        model = service.deprecate_model(
            model.model_manifest_id,
            expected_revision=model.revision,
        )
        runtime = service.mark_runtime_unavailable(
            runtime.runtime_manifest_id,
            expected_revision=runtime.revision,
        )
        assert model.manifest_state == "deprecated"
        assert runtime.manifest_state == "unavailable"

        runtime_record = repository.get_record(runtime.runtime_manifest_id)
        repository.update_record(
            runtime.runtime_manifest_id,
            expected_revision=runtime_record.revision,
            status="archived",
        )
        assert service.list_runtimes() == ()
        assert len(service.list_runtimes(include_archived=True)) == 1
        for limit in (0, True, 501):
            with pytest.raises(ModelManifestValidationError, match="limit"):
                service.list_runtimes(limit=limit)


def test_verification_evidence_platform_and_state_gates(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        service = ModelManifestService(repository)
        candidate_runtime = _runtime(service, verify=False)
        with pytest.raises(ModelManifestValidationError, match="does not exist"):
            service.verify_runtime(
                candidate_runtime.runtime_manifest_id,
                expected_revision=candidate_runtime.revision,
                evidence_ids=(str(uuid4()),),
            )
        candidate_runtime = service.verify_runtime(
            candidate_runtime.runtime_manifest_id,
            expected_revision=candidate_runtime.revision,
        )
        with pytest.raises(ModelManifestValidationError, match="cannot be verified"):
            service.verify_runtime(
                candidate_runtime.runtime_manifest_id,
                expected_revision=candidate_runtime.revision,
            )

        evidence = repository.create_record(
            record_type="note",
            sensitivity="personal",
            title="not evidence",
        )
        candidate = _model(
            service,
            candidate_runtime.runtime_manifest_id,
            platforms=("windows-arm64",),
            verify=False,
        )
        with pytest.raises(ModelManifestValidationError, match="unreviewed"):
            service.review_model_license(
                candidate.model_manifest_id,
                expected_revision=candidate.revision,
                review_state="unreviewed",
            )
        candidate = service.review_model_license(
            candidate.model_manifest_id,
            expected_revision=candidate.revision,
            review_state="reviewed_compatible",
        )
        with pytest.raises(ModelManifestValidationError, match="incompatible"):
            service.verify_model(
                candidate.model_manifest_id,
                expected_revision=candidate.revision,
            )

        compatible = _model(
            service,
            candidate_runtime.runtime_manifest_id,
            verify=False,
        )
        compatible = service.review_model_license(
            compatible.model_manifest_id,
            expected_revision=compatible.revision,
            review_state="reviewed_compatible",
        )
        with pytest.raises(ModelManifestValidationError, match="not active and portable"):
            service.verify_model(
                compatible.model_manifest_id,
                expected_revision=compatible.revision,
                evidence_ids=(evidence.id,),
            )


def test_binding_failure_states_and_read_only_paths(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        service = ModelManifestService(repository)
        runtime = _runtime(service)
        other_runtime = _runtime(service)
        model = _model(service, runtime.runtime_manifest_id)
        with pytest.raises(ModelManifestValidationError, match="another runtime"):
            service.create_binding(
                scope_type="project",
                scope_key="wrong-runtime",
                runtime_manifest_id=other_runtime.runtime_manifest_id,
                model_manifest_id=model.model_manifest_id,
            )

        binding = _binding(service, runtime.runtime_manifest_id, model.model_manifest_id)
        with pytest.raises(ModelManifestValidationError, match="smoke test"):
            service.activate_binding(binding.binding_id, expected_revision=binding.revision)
        with pytest.raises(ModelManifestValidationError, match="priority"):
            passed = service.set_smoke_test(
                binding.binding_id,
                expected_revision=binding.revision,
                status="passed",
            )
            service.set_fallback(
                passed.binding_id, expected_revision=passed.revision, priority=True
            )
        active = service.activate_binding(passed.binding_id, expected_revision=passed.revision)
        with pytest.raises(ModelManifestValidationError, match="cannot become fallback"):
            service.set_fallback(active.binding_id, expected_revision=active.revision, priority=1)
        with pytest.raises(ModelManifestValidationError, match="no rollback target"):
            service.rollback_binding(
                active.binding_id,
                expected_revision=active.revision,
                reason="No previous binding",
            )

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        service = ModelManifestService(repository)
        with pytest.raises(ReadOnlyStateError):
            service.create_runtime(
                label="Read only",
                adapter_id="ollama.local",
                adapter_version="1",
                runtime_class="ollama",
                connection_kind="loopback_http",
                operations=("health",),
                offline_capable=True,
                cloud_fallback=False,
                automatic_download=False,
            )
        existing = service.list_bindings()[0]
        with pytest.raises(ReadOnlyStateError):
            service.set_smoke_test(
                existing.binding_id,
                expected_revision=existing.revision,
                status="failed",
            )


def test_corrupt_manifest_consistency_checks(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        service = ModelManifestService(repository)
        runtime = _runtime(service)
        model = _model(service, runtime.runtime_manifest_id)
        binding = _binding(service, runtime.runtime_manifest_id, model.model_manifest_id)
        runtime_record = repository.get_record(runtime.runtime_manifest_id)
        model_record = repository.get_record(model.model_manifest_id)
        binding_record = repository.get_record(binding.binding_id)

    runtime_metadata = dict(runtime_record.metadata)
    runtime_metadata["declaration_fingerprint"] = "sha256:" + "0" * 64
    with pytest.raises(ModelManifestCorruptError):
        _runtime_from_record(_envelope("runtime_manifest", runtime_metadata))

    runtime_metadata = dict(runtime_record.metadata)
    runtime_metadata["quarantine_reason"] = "unexpected"
    with pytest.raises(ModelManifestCorruptError):
        _runtime_from_record(_envelope("runtime_manifest", runtime_metadata))

    model_metadata = dict(model_record.metadata)
    model_metadata["quarantine_reason"] = "unexpected"
    with pytest.raises(ModelManifestCorruptError):
        _model_from_record(_envelope("model_manifest", model_metadata))

    binding_metadata = dict(binding_record.metadata)
    binding_metadata["binding_state"] = "active"
    with pytest.raises(ModelManifestCorruptError):
        _binding_from_record(_envelope("model_binding", binding_metadata))

    binding_metadata = dict(binding_record.metadata)
    binding_metadata.update(
        {"binding_state": "fallback", "fallback_eligible": False, "fallback_priority": None}
    )
    with pytest.raises(ModelManifestCorruptError):
        _binding_from_record(_envelope("model_binding", binding_metadata))

    binding_metadata = dict(binding_record.metadata)
    binding_metadata.update({"fallback_eligible": True, "fallback_priority": 1})
    with pytest.raises(ModelManifestCorruptError):
        _binding_from_record(_envelope("model_binding", binding_metadata))
