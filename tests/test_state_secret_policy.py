from __future__ import annotations

from pathlib import Path

import pytest

from doll import state, workspace


def _reference_metadata() -> dict[str, object]:
    return {
        "reference_id": "credential:test:primary",
        "credential_class": "password",
        "store_adapter_class": "test.synthetic",
        "label": "Synthetic test credential",
        "status": "active",
        "allowed_operation_scope": ["test.read"],
        "allowed_destination_scope": ["service.test.invalid"],
    }


def test_state_create_rejects_secret_value_without_advancing_revision(
    tmp_path: Path,
) -> None:
    initialized = workspace.initialize_workspace(tmp_path / "workspace")
    with state.initialize_state_repository(initialized.root) as repository:
        with pytest.raises(
            state.RecordValidationError,
            match="does not permit secret values",
        ):
            repository.create_record(
                record_type="memory",
                sensitivity="secret",
                metadata={"content": "synthetic secret-shaped value"},
            )
        status = repository.status()
        assert status.record_count == 0
        assert status.state_revision == 0
    assert workspace.load_workspace(initialized.root).record.state_revision == 0


def test_state_create_accepts_only_validated_secret_reference(tmp_path: Path) -> None:
    initialized = workspace.initialize_workspace(tmp_path / "workspace")
    with state.initialize_state_repository(initialized.root) as repository:
        record = repository.create_record(
            record_type="secret_reference",
            sensitivity="secret",
            metadata=_reference_metadata(),
        )
        assert record.sensitivity == "secret"
        assert record.metadata == _reference_metadata()
        assert repository.status().state_revision == 1

        invalid = _reference_metadata()
        invalid["token"] = "synthetic-not-a-real-token"
        with pytest.raises(state.RecordValidationError, match="field is prohibited"):
            repository.create_record(
                record_type="secret_reference",
                sensitivity="secret",
                metadata=invalid,
            )
        assert repository.status().record_count == 1
        assert repository.status().state_revision == 1


def test_state_create_rejects_reference_with_non_sensitive_label(tmp_path: Path) -> None:
    initialized = workspace.initialize_workspace(tmp_path / "workspace")
    with state.initialize_state_repository(initialized.root) as repository:
        with pytest.raises(
            state.RecordValidationError,
            match="require sensitive or secret sensitivity",
        ):
            repository.create_record(
                record_type="secret_reference",
                sensitivity="personal",
                metadata=_reference_metadata(),
            )
        assert repository.status().record_count == 0
        assert repository.status().state_revision == 0


def test_state_update_rejects_secret_reference_value_atomically(tmp_path: Path) -> None:
    initialized = workspace.initialize_workspace(tmp_path / "workspace")
    with state.initialize_state_repository(initialized.root) as repository:
        record = repository.create_record(
            record_type="secret_reference",
            sensitivity="sensitive",
            metadata=_reference_metadata(),
        )
        updated_metadata = _reference_metadata()
        updated_metadata["label"] = "Rotated synthetic reference"
        updated = repository.update_record(
            record.id,
            expected_revision=1,
            metadata=updated_metadata,
        )
        assert updated.revision == 2
        assert repository.status().state_revision == 2

        invalid = dict(updated_metadata)
        invalid["private_key"] = "synthetic-not-a-real-key"
        with pytest.raises(state.RecordValidationError, match="field is prohibited"):
            repository.update_record(
                record.id,
                expected_revision=2,
                metadata=invalid,
            )
        persisted = repository.get_record(record.id)
        assert persisted.revision == 2
        assert persisted.metadata == updated_metadata
        assert repository.status().state_revision == 2
    assert workspace.load_workspace(initialized.root).record.state_revision == 2
