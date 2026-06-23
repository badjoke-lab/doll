from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from doll import state, workspace
from doll.portability import (
    AdapterResourceLimits,
    PortabilityState,
    SourceAdapterContract,
    SourceEnvironmentRecord,
    TargetAdapterContract,
)


def _limits() -> AdapterResourceLimits:
    return AdapterResourceLimits(
        max_input_bytes=10_000_000,
        max_object_count=100_000,
        max_attachment_bytes=5_000_000,
        max_nesting_depth=32,
    )


def _workspace(tmp_path: Path) -> workspace.InitializedWorkspace:
    return workspace.initialize_workspace(tmp_path / "workspace")


def test_source_adapter_contract_is_deterministic_and_declarative() -> None:
    first = SourceAdapterContract(
        adapter_id="generic-json",
        adapter_version="1.0.0",
        source_environment_class="generic-file-export",
        supported_source_versions=("2", "1"),
        supported_event_types=("assistant-message", "user-message"),
        attachment_behavior="preserve_reference",
        branch_behavior="preserve",
        resource_limits=_limits(),
        network_behavior="none",
        loss_categories=("unsupported-event", "missing-attachment"),
    )
    second = SourceAdapterContract(
        adapter_id="generic-json",
        adapter_version="1.0.0",
        source_environment_class="generic-file-export",
        supported_source_versions=("1", "2"),
        supported_event_types=("user-message", "assistant-message"),
        attachment_behavior="preserve_reference",
        branch_behavior="preserve",
        resource_limits=_limits(),
        network_behavior="none",
        loss_categories=("missing-attachment", "unsupported-event"),
    )

    assert first.supported_source_versions == ("1", "2")
    assert first.supported_event_types == ("assistant-message", "user-message")
    assert first.fingerprint == second.fingerprint
    assert first.canonical_payload()["contract_kind"] == "source"
    assert not hasattr(first, "parse")
    assert not hasattr(first, "execute")


def test_target_adapter_contract_is_distinct_from_source_contract() -> None:
    target = TargetAdapterContract(
        adapter_id="generic-json-export",
        adapter_version="1.0.0",
        target_environment_class="generic-file-export",
        supported_target_versions=("1",),
        supported_record_types=("conversation", "conversation-event"),
        attachment_behavior="preserve_managed_copy",
        branch_behavior="linearize_with_loss",
        resource_limits=_limits(),
        network_behavior="none",
        loss_categories=("branch-linearized",),
    )

    payload = target.canonical_payload()
    assert payload["contract_kind"] == "target"
    assert payload["supported_record_types"] == [
        "conversation",
        "conversation-event",
    ]
    assert "supported_event_types" not in payload
    assert len(target.fingerprint) == 64


def test_source_environment_keeps_identity_categories_separate_and_unknown() -> None:
    record = SourceEnvironmentRecord(
        environment_id=str(uuid4()),
        environment_class="local-ai-application",
        provider_id="provider-a",
        application_id="application-b",
        interface_id="interface-c",
        runtime_id="runtime-d",
        export_format="generic-json",
        export_version="1.0",
        observed_at="2026-06-24T01:00:00Z",
    )
    unknown = SourceEnvironmentRecord(
        environment_id=str(uuid4()),
        environment_class="unknown-environment",
    )

    assert record.canonical_metadata() == {
        "environment_class": "local-ai-application",
        "provider_id": "provider-a",
        "application_id": "application-b",
        "interface_id": "interface-c",
        "runtime_id": "runtime-d",
        "export_format": "generic-json",
        "export_version": "1.0",
        "observed_at": "2026-06-24T01:00:00Z",
    }
    assert unknown.provider_id is None
    assert unknown.application_id is None
    assert unknown.interface_id is None
    assert unknown.runtime_id is None
    assert not {
        "policy",
        "permission",
        "capability",
        "confirmation",
        "credential_scope",
        "confirmed_memory",
        "confirmed_fact",
        "instruction_authority",
    } & set(record.canonical_metadata())


def test_source_environment_survives_read_only_reopen(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    record = SourceEnvironmentRecord(
        environment_id=str(uuid4()),
        environment_class="cloud-service-export",
        provider_id="provider-a",
        application_id="application-b",
        export_format="json",
        export_version="2026.1",
        observed_at="2026-06-24T01:00:00+09:00",
    )

    with state.initialize_state_repository(initialized.root) as repository:
        portability = PortabilityState(repository)
        assert portability.save_source_environment(record) == record
        assert portability.list_source_environments() == (record,)

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        portability = PortabilityState(repository)
        assert portability.get_source_environment(record.environment_id) == record
        with pytest.raises(state.ReadOnlyStateError):
            portability.save_source_environment(
                SourceEnvironmentRecord(
                    environment_id=str(uuid4()),
                    environment_class="generic-file-export",
                )
            )


def test_duplicate_source_environment_preserves_state_revision(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    record = SourceEnvironmentRecord(
        environment_id=str(uuid4()),
        environment_class="generic-file-export",
    )

    with state.initialize_state_repository(initialized.root) as repository:
        portability = PortabilityState(repository)
        portability.save_source_environment(record)
        revision = repository.status().state_revision
        with pytest.raises(state.RecordValidationError, match="already exists"):
            portability.save_source_environment(record)
        assert repository.status().state_revision == revision
