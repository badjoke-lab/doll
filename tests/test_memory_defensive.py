from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from doll import state, workspace
from doll.memory import (
    ConfirmedMemoryService,
    MemoryCorruptError,
    MemoryValidationError,
    _metadata_list,
    _optional_string,
    _required_string,
    _validate_confidence,
    _validate_optional_identifier,
    _validate_optional_utc,
    _validate_reference_ids,
    _validate_source_type,
    _validate_text,
)


def initialized_workspace(tmp_path: Path) -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(tmp_path / "workspace")
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def test_text_identifier_timestamp_and_confidence_defensive_branches() -> None:
    with pytest.raises(MemoryValidationError):
        _validate_text("x", cast(str, 1), 10)
    with pytest.raises(MemoryValidationError):
        _validate_text("x", "", 10)
    with pytest.raises(MemoryValidationError):
        _validate_text("x", "x" * 11, 10)
    with pytest.raises(MemoryValidationError):
        _validate_text("x", "bad\x00", 10)

    with pytest.raises(MemoryValidationError):
        _validate_optional_identifier("id", cast(str, 1))
    with pytest.raises(MemoryValidationError):
        _validate_optional_identifier("id", "")
    with pytest.raises(MemoryValidationError):
        _validate_optional_identifier("id", "bad id")
    assert _validate_optional_identifier("id", None) is None

    with pytest.raises(MemoryValidationError):
        _validate_optional_utc("time", "2026-06-14T00:00:00")
    with pytest.raises(MemoryValidationError):
        _validate_optional_utc("time", "not-a-dateZ")
    assert _validate_optional_utc("time", None) is None

    with pytest.raises(MemoryValidationError):
        _validate_confidence(True)
    with pytest.raises(MemoryValidationError):
        _validate_confidence("high")
    assert _validate_confidence(1) == 1.0


def test_source_and_reference_validation_defensive_branches() -> None:
    with pytest.raises(MemoryValidationError):
        _validate_source_type("suggested")
    with pytest.raises(MemoryValidationError):
        _validate_reference_ids("refs", cast(object, "id"))  # type: ignore[arg-type]
    with pytest.raises(MemoryValidationError):
        _validate_reference_ids("refs", [cast(str, 1)])
    with pytest.raises(MemoryValidationError):
        _validate_reference_ids(
            "refs",
            ["00000000-0000-0000-0000-000000000001"] * 2,
        )
    with pytest.raises(MemoryValidationError):
        _validate_reference_ids(
            "refs",
            [f"00000000-0000-0000-0000-{index:012d}" for index in range(101)],
        )


def test_metadata_extractors_defensive_branches() -> None:
    with pytest.raises(MemoryValidationError):
        _required_string({}, "x")
    with pytest.raises(MemoryValidationError):
        _required_string({"x": 1}, "x")
    assert _optional_string({}, "x") is None
    with pytest.raises(MemoryValidationError):
        _optional_string({"x": 1}, "x")
    with pytest.raises(MemoryValidationError):
        _metadata_list({}, "x")


def test_list_limits_and_corrupt_common_fields(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        service = ConfirmedMemoryService(repository)
        with pytest.raises(MemoryValidationError):
            service.list(limit=0)
        with pytest.raises(MemoryValidationError):
            service.list(limit=201)

        inconsistent = repository.create_record(
            record_type="memory",
            title="wrong title",
            provenance="user-confirmed",
            metadata={
                "memory_class": "confirmed",
                "subject": "subject",
                "content": "content",
                "source_type": "user_statement",
                "confirmation_state": "confirmed",
                "valid_from": None,
                "valid_until": None,
                "confidence": 1.0,
                "related_memory_ids": [],
                "contradicts_memory_ids": [],
                "source_reference": None,
                "model_manifest_id": None,
                "runtime_adapter_id": None,
                "session_id": None,
                "origin_operation_id": None,
            },
        )
        with pytest.raises(MemoryCorruptError):
            service.get(inconsistent.id)

        bad_refs = repository.create_record(
            record_type="memory",
            title="bad refs",
            provenance="user-confirmed",
            metadata={
                "memory_class": "confirmed",
                "subject": "bad refs",
                "content": "content",
                "source_type": "user_statement",
                "confirmation_state": "confirmed",
                "valid_from": None,
                "valid_until": None,
                "confidence": 1.0,
                "related_memory_ids": "not-a-list",
                "contradicts_memory_ids": [],
                "source_reference": None,
                "model_manifest_id": None,
                "runtime_adapter_id": None,
                "session_id": None,
                "origin_operation_id": None,
            },
        )
        with pytest.raises(MemoryCorruptError):
            service.get(bad_refs.id)


def test_list_database_failure_is_normalized(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        repository.connection.execute("DROP TABLE records")
        with pytest.raises(state.StateCorruptError):
            ConfirmedMemoryService(repository).list()
