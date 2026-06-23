from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import pytest

from doll import state, workspace
from doll.portability import (
    AdapterResourceLimits,
    PortabilityContractError,
    PortabilityState,
    PortabilityStateCorruptError,
    SourceAdapterContract,
    SourceEnvironmentRecord,
    TargetAdapterContract,
)


def _limits() -> AdapterResourceLimits:
    return AdapterResourceLimits(
        max_input_bytes=1024,
        max_object_count=100,
        max_attachment_bytes=512,
        max_nesting_depth=8,
    )


def _workspace(tmp_path: Path) -> workspace.InitializedWorkspace:
    return workspace.initialize_workspace(tmp_path / "workspace")


def _source_contract(**changes: object) -> SourceAdapterContract:
    values: dict[str, object] = {
        "adapter_id": "generic-json",
        "adapter_version": "1.0.0",
        "source_environment_class": "generic-file-export",
        "supported_source_versions": ("1",),
        "supported_event_types": ("user-message",),
        "attachment_behavior": "preserve_reference",
        "branch_behavior": "preserve",
        "resource_limits": _limits(),
        "network_behavior": "none",
        "loss_categories": (),
    }
    values.update(changes)
    return SourceAdapterContract(**cast(dict[str, Any], values))


def test_adapter_contract_rejects_undeclared_or_invalid_behaviors() -> None:
    with pytest.raises(PortabilityContractError, match="network behavior"):
        _source_contract(network_behavior="automatic-cloud-fallback")
    with pytest.raises(PortabilityContractError, match="attachment behavior"):
        _source_contract(attachment_behavior="execute-attachment")
    with pytest.raises(PortabilityContractError, match="branch behavior"):
        _source_contract(branch_behavior="discard")


def test_adapter_contract_rejects_empty_duplicate_and_ambiguous_declarations() -> None:
    with pytest.raises(PortabilityContractError, match="must not be empty"):
        _source_contract(supported_source_versions=())
    with pytest.raises(PortabilityContractError, match="must not be empty"):
        _source_contract(supported_event_types=())
    with pytest.raises(PortabilityContractError, match="contains duplicates"):
        _source_contract(supported_event_types=("message", "message"))
    with pytest.raises(PortabilityContractError, match="contains duplicates"):
        _source_contract(loss_categories=("unsupported", "unsupported"))
    with pytest.raises(PortabilityContractError, match="must be a tuple"):
        _source_contract(supported_event_types=cast(Any, ["message"]))


def test_adapter_contract_rejects_invalid_identifiers_and_versions() -> None:
    with pytest.raises(PortabilityContractError, match="adapter id is invalid"):
        _source_contract(adapter_id="Bad Adapter")
    with pytest.raises(PortabilityContractError, match="adapter version is invalid"):
        _source_contract(adapter_version="bad version")
    with pytest.raises(PortabilityContractError, match="source environment class is invalid"):
        _source_contract(source_environment_class="bad environment")
    with pytest.raises(PortabilityContractError, match="supported source versions is invalid"):
        _source_contract(supported_source_versions=("bad version",))


def test_target_adapter_rejects_invalid_required_declarations() -> None:
    with pytest.raises(PortabilityContractError, match="supported target versions must not be empty"):
        TargetAdapterContract(
            adapter_id="generic-export",
            adapter_version="1.0.0",
            target_environment_class="generic-file-export",
            supported_target_versions=(),
            supported_record_types=("conversation",),
            attachment_behavior="metadata_only",
            branch_behavior="preserve",
            resource_limits=_limits(),
            network_behavior="none",
        )
    with pytest.raises(PortabilityContractError, match="supported record types contains duplicates"):
        TargetAdapterContract(
            adapter_id="generic-export",
            adapter_version="1.0.0",
            target_environment_class="generic-file-export",
            supported_target_versions=("1",),
            supported_record_types=("conversation", "conversation"),
            attachment_behavior="metadata_only",
            branch_behavior="preserve",
            resource_limits=_limits(),
            network_behavior="none",
        )


@pytest.mark.parametrize(
    "field_name",
    [
        "max_input_bytes",
        "max_object_count",
        "max_attachment_bytes",
        "max_nesting_depth",
    ],
)
def test_resource_limits_reject_non_positive_values(field_name: str) -> None:
    values = {
        "max_input_bytes": 1,
        "max_object_count": 1,
        "max_attachment_bytes": 1,
        "max_nesting_depth": 1,
    }
    values[field_name] = 0
    with pytest.raises(PortabilityContractError, match="positive bounded integer"):
        AdapterResourceLimits(**values)


def test_resource_limits_reject_boolean_and_excessive_values() -> None:
    with pytest.raises(PortabilityContractError, match="positive bounded integer"):
        AdapterResourceLimits(
            max_input_bytes=cast(Any, True),
            max_object_count=1,
            max_attachment_bytes=1,
            max_nesting_depth=1,
        )
    with pytest.raises(PortabilityContractError, match="positive bounded integer"):
        AdapterResourceLimits(
            max_input_bytes=2**63,
            max_object_count=1,
            max_attachment_bytes=1,
            max_nesting_depth=1,
        )


def test_source_environment_rejects_invalid_identity_and_time() -> None:
    with pytest.raises(PortabilityContractError, match="canonical UUID text"):
        SourceEnvironmentRecord(
            environment_id=str(uuid4()).upper(),
            environment_class="generic-file-export",
        )
    with pytest.raises(PortabilityContractError, match="environment class is invalid"):
        SourceEnvironmentRecord(
            environment_id=str(uuid4()),
            environment_class="Bad Environment",
        )
    with pytest.raises(PortabilityContractError, match="provider id is invalid"):
        SourceEnvironmentRecord(
            environment_id=str(uuid4()),
            environment_class="generic-file-export",
            provider_id="bad provider",
        )
    with pytest.raises(PortabilityContractError, match="export version is invalid"):
        SourceEnvironmentRecord(
            environment_id=str(uuid4()),
            environment_class="generic-file-export",
            export_version="bad version",
        )
    with pytest.raises(PortabilityContractError, match="timezone-aware"):
        SourceEnvironmentRecord(
            environment_id=str(uuid4()),
            environment_class="generic-file-export",
            observed_at="2026-06-24T01:00:00",
        )
    with pytest.raises(PortabilityContractError, match="observed at is invalid"):
        SourceEnvironmentRecord(
            environment_id=str(uuid4()),
            environment_class="generic-file-export",
            observed_at="not-a-time",
        )


def test_source_environment_reader_rejects_wrong_record_type(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.initialize_state_repository(initialized.root) as repository:
        generic = repository.create_record(record_type="note")
        portability = PortabilityState(repository)
        with pytest.raises(
            PortabilityStateCorruptError,
            match="supported source environment",
        ):
            portability.get_source_environment(generic.id)


def test_source_environment_reader_rejects_corrupt_shape(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    record = SourceEnvironmentRecord(
        environment_id=str(uuid4()),
        environment_class="generic-file-export",
    )
    with state.initialize_state_repository(initialized.root) as repository:
        portability = PortabilityState(repository)
        portability.save_source_environment(record)
        repository.connection.execute(
            "UPDATE records SET metadata_json = ? WHERE id = ?",
            (json.dumps({"unexpected": True}), record.environment_id),
        )
        with pytest.raises(PortabilityStateCorruptError, match="metadata shape"):
            portability.get_source_environment(record.environment_id)


def test_source_environment_reader_rejects_invalid_values(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    record_id = str(uuid4())
    with state.initialize_state_repository(initialized.root) as repository:
        repository.create_record(
            record_id=record_id,
            record_type="source_environment",
            metadata={
                "environment_class": "Bad Environment",
                "provider_id": None,
                "application_id": None,
                "interface_id": None,
                "runtime_id": None,
                "export_format": None,
                "export_version": None,
                "observed_at": None,
            },
        )
        portability = PortabilityState(repository)
        with pytest.raises(PortabilityStateCorruptError, match="metadata is invalid"):
            portability.get_source_environment(record_id)


def test_source_environment_list_limit_rejects_invalid_values(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.initialize_state_repository(initialized.root) as repository:
        portability = PortabilityState(repository)
        with pytest.raises(PortabilityContractError, match="list limit"):
            portability.list_source_environments(limit=0)
        with pytest.raises(PortabilityContractError, match="list limit"):
            portability.list_source_environments(limit=cast(Any, True))
