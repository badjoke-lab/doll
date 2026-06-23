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


def test_contract_rejects_invalid_behaviors() -> None:
    with pytest.raises(PortabilityContractError, match="network behavior"):
        _source_contract(network_behavior="invalid")
    with pytest.raises(PortabilityContractError, match="attachment behavior"):
        _source_contract(attachment_behavior="invalid")
    with pytest.raises(PortabilityContractError, match="branch behavior"):
        _source_contract(branch_behavior="invalid")


def test_contract_rejects_invalid_declarations() -> None:
    with pytest.raises(PortabilityContractError, match="must not be empty"):
        _source_contract(supported_source_versions=())
    with pytest.raises(PortabilityContractError, match="contains duplicates"):
        _source_contract(supported_event_types=("message", "message"))
    with pytest.raises(PortabilityContractError, match="must be a tuple"):
        _source_contract(supported_event_types=cast(Any, ["message"]))
    with pytest.raises(PortabilityContractError, match="adapter id is invalid"):
        _source_contract(adapter_id="Bad Adapter")
    with pytest.raises(PortabilityContractError, match="adapter version is invalid"):
        _source_contract(adapter_version="bad version")


def test_resource_limits_reject_invalid_values() -> None:
    with pytest.raises(PortabilityContractError, match="positive bounded integer"):
        AdapterResourceLimits(
            max_input_bytes=0,
            max_object_count=1,
            max_attachment_bytes=1,
            max_nesting_depth=1,
        )
    with pytest.raises(PortabilityContractError, match="positive bounded integer"):
        AdapterResourceLimits(
            max_input_bytes=cast(Any, True),
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
    with pytest.raises(PortabilityContractError, match="timezone-aware"):
        SourceEnvironmentRecord(
            environment_id=str(uuid4()),
            environment_class="generic-file-export",
            observed_at="2026-06-24T01:00:00",
        )


def test_source_environment_reader_rejects_invalid_records(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.initialize_state_repository(initialized.root) as repository:
        portability = PortabilityState(repository)
        generic = repository.create_record(record_type="note")
        with pytest.raises(
            PortabilityStateCorruptError,
            match="supported source environment",
        ):
            portability.get_source_environment(generic.id)

        record = SourceEnvironmentRecord(
            environment_id=str(uuid4()),
            environment_class="generic-file-export",
        )
        portability.save_source_environment(record)
        repository.connection.execute(
            "UPDATE records SET metadata_json = ? WHERE id = ?",
            (json.dumps({"unexpected": True}), record.environment_id),
        )
        with pytest.raises(PortabilityStateCorruptError, match="metadata shape"):
            portability.get_source_environment(record.environment_id)


def test_source_environment_list_limit_rejects_invalid_values(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path)
    with state.initialize_state_repository(initialized.root) as repository:
        portability = PortabilityState(repository)
        with pytest.raises(PortabilityContractError, match="list limit"):
            portability.list_source_environments(limit=0)
        with pytest.raises(PortabilityContractError, match="list limit"):
            portability.list_source_environments(limit=cast(Any, True))
