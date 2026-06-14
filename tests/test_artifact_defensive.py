from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest

from doll import state, workspace
from doll.artifact import (
    ArtifactCorruptError,
    ArtifactCreator,
    ArtifactIntegrityError,
    ArtifactRegistrationError,
    ArtifactValidationError,
    WorkspaceFileService,
    _artifact_from_record,
    _optional_string,
    _provenance_for_creator,
    _required_string,
    _validate_identifier,
    _validate_media_type,
    _validate_title,
)
from doll.state import RecordEnvelope


def initialized_workspace(tmp_path: Path) -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(tmp_path / "workspace")
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def test_direct_validation_and_provenance_branches() -> None:
    with pytest.raises(ArtifactValidationError):
        _validate_title(cast(str, 123))
    with pytest.raises(ArtifactValidationError):
        _validate_title("bad\x00title")
    with pytest.raises(ArtifactValidationError):
        _validate_identifier("type", cast(str, 123), 20)
    with pytest.raises(ArtifactValidationError):
        _validate_identifier("type", "bad type", 20)
    with pytest.raises(ArtifactValidationError):
        _validate_media_type("x" * 121)

    assert _provenance_for_creator("model") == "model-proposed"
    assert _provenance_for_creator("runtime") == "system-generated"

    with pytest.raises(ArtifactCorruptError):
        _required_string({}, "missing")
    with pytest.raises(ArtifactCorruptError):
        _required_string({"value": 1}, "value")
    with pytest.raises(ArtifactCorruptError):
        _optional_string({"value": 1}, "value")
    assert _optional_string({}, "value") is None


def test_create_rejects_non_bytes_non_text_and_bad_creator(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        service = WorkspaceFileService(repository)

        with pytest.raises(ArtifactValidationError):
            service.create_bytes(
                managed_path="x.bin",
                content=cast(bytes, "not-bytes"),
                title="X",
                artifact_type="binary",
            )
        with pytest.raises(ArtifactValidationError):
            service.create_text(
                managed_path="x.txt",
                text=cast(str, b"not-text"),
                title="X",
            )
        with pytest.raises(ArtifactValidationError):
            service.create_bytes(
                managed_path="x.bin",
                content=b"x",
                title="X",
                artifact_type="binary",
                created_by=cast(ArtifactCreator, "bogus"),
            )


def test_real_database_registration_failure_rolls_back_file(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        repository.connection.execute(
            """
            CREATE TRIGGER reject_artifact_record
            BEFORE INSERT ON records
            WHEN NEW.record_type = 'artifact'
            BEGIN
                SELECT RAISE(ABORT, 'synthetic artifact registration failure');
            END
            """
        )

        with pytest.raises(ArtifactRegistrationError):
            WorkspaceFileService(repository).create_text(
                managed_path="failed/record.txt",
                text="temporary",
                title="Failure",
                artifact_type="text",
                operation_id="operation-db-failure",
            )

        assert repository.status().state_revision == 0
        audit_count = repository.connection.execute("SELECT COUNT(*) FROM audit_events").fetchone()
        assert audit_count is not None
        assert audit_count[0] == 0

    assert not (initialized.root / "artifacts" / "failed").exists()


def test_get_wrong_record_type_and_missing_file_verification(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        service = WorkspaceFileService(repository)
        other = repository.create_record(record_type="other")
        with pytest.raises(KeyError):
            service.get(other.id)

        artifact = service.create_text(
            managed_path="missing.txt",
            text="content",
            title="Missing",
            artifact_type="text",
        )

    (initialized.root / "artifacts" / "missing.txt").unlink()

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        with pytest.raises(ArtifactIntegrityError):
            WorkspaceFileService(repository).verify(artifact.artifact_id)


def base_record() -> RecordEnvelope:
    return RecordEnvelope(
        id="artifact-id",
        record_type="artifact",
        schema_version=1,
        created_at="2026-06-14T00:00:00Z",
        updated_at="2026-06-14T00:00:00Z",
        revision=1,
        status="active",
        provenance="user-created",
        sensitivity="personal",
        title="Artifact",
        metadata={
            "artifact_type": "text",
            "managed_path": "artifact.txt",
            "content_hash": "sha256:" + "0" * 64,
            "size_bytes": 1,
            "created_by": "user",
            "operation_id": "operation-1",
            "format": "txt",
            "media_type": "text/plain",
        },
    )


@pytest.mark.parametrize(
    ("metadata_updates", "title"),
    [
        ({"content_hash": "bad"}, "Artifact"),
        ({"size_bytes": True}, "Artifact"),
        ({"created_by": "bogus"}, "Artifact"),
        ({"operation_id": "bad operation"}, "Artifact"),
        ({"format": "bad format"}, "Artifact"),
        ({"media_type": "invalid"}, "Artifact"),
        ({}, None),
    ],
)
def test_corrupt_artifact_record_variants(
    metadata_updates: dict[str, object],
    title: str | None,
) -> None:
    record = base_record()
    metadata = dict(record.metadata)
    metadata.update(metadata_updates)
    record = replace(record, metadata=metadata, title=title)

    with pytest.raises(ArtifactCorruptError):
        _artifact_from_record(record)
