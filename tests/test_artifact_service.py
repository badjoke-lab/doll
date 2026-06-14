from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import pytest

from doll import state, workspace
from doll.artifact import (
    ArtifactCorruptError,
    ArtifactIntegrityError,
    ArtifactRegistrationError,
    ArtifactValidationError,
    WorkspaceFileService,
)
from doll.audit import AuditService
from doll.workspace_files import ArtifactSizeLimitError, ManagedFileExistsError


def initialized_workspace(tmp_path: Path) -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(tmp_path / "workspace")
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def test_create_text_indexes_hashes_audits_and_reopens(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    content = "成果物の本文\n"
    operation_id = "artifact-operation-1"

    with state.open_state_repository(initialized.root) as repository:
        service = WorkspaceFileService(repository)
        artifact = service.create_text(
            managed_path="reports/日本語.txt",
            text=content,
            title="日本語レポート",
            artifact_type="report",
            operation_id=operation_id,
            format="txt",
            media_type="text/plain",
        )

        expected_hash = f"sha256:{hashlib.sha256(content.encode()).hexdigest()}"
        assert artifact.managed_path == "reports/日本語.txt"
        assert artifact.content_hash == expected_hash
        assert artifact.size_bytes == len(content.encode())
        assert artifact.operation_id == operation_id
        assert artifact.created_by == "user"
        assert artifact.sensitivity == "personal"
        assert service.get(artifact.artifact_id) == artifact
        assert service.list() == (artifact,)
        verification = service.verify(artifact.artifact_id)
        assert verification.actual_hash == expected_hash
        assert repository.status().state_revision == 1

        events = AuditService(repository).list(operation_id=operation_id)
        assert len(events) == 1
        assert events[0].action == "artifact.create"
        assert events[0].target_id == artifact.artifact_id
        assert events[0].result == "success"

    assert (initialized.root / "artifacts" / "reports" / "日本語.txt").read_text(
        encoding="utf-8"
    ) == content
    assert workspace.load_workspace(initialized.root).record.state_revision == 1

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        service = WorkspaceFileService(repository)
        assert service.get(artifact.artifact_id) == artifact
        assert service.verify(artifact.artifact_id).actual_size_bytes == len(content.encode())


def test_duplicate_path_preserves_original_and_state(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        service = WorkspaceFileService(repository)
        first = service.create_text(
            managed_path="same.txt",
            text="first",
            title="First",
            artifact_type="text",
            operation_id="operation-first",
        )
        with pytest.raises(ManagedFileExistsError):
            service.create_text(
                managed_path="same.txt",
                text="second",
                title="Second",
                artifact_type="text",
                operation_id="operation-second",
            )

        assert service.list() == (first,)
        assert repository.status().state_revision == 1
        assert len(AuditService(repository).list()) == 1

    assert (initialized.root / "artifacts" / "same.txt").read_text() == "first"


def test_registration_failure_removes_published_file_and_empty_parents(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        service = WorkspaceFileService(repository)

        def fail_register(*args: object, **kwargs: object) -> int:
            raise sqlite3.DatabaseError("synthetic registration failure")

        monkeypatch.setattr(service, "_register", fail_register)
        with pytest.raises(ArtifactRegistrationError):
            service.create_text(
                managed_path="failed/nested.txt",
                text="temporary",
                title="Failure",
                artifact_type="text",
                operation_id="operation-failed",
            )

        assert repository.status().state_revision == 0
        assert service.list() == ()
        assert AuditService(repository).list() == ()

    assert not (initialized.root / "artifacts" / "failed").exists()
    assert not any((initialized.root / "artifacts").rglob(".doll-tmp-*"))


def test_read_only_creation_is_rejected_without_side_effect(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        with pytest.raises(state.ReadOnlyStateError):
            WorkspaceFileService(repository).create_text(
                managed_path="blocked.txt",
                text="blocked",
                title="Blocked",
                artifact_type="text",
            )
    assert not (initialized.root / "artifacts" / "blocked.txt").exists()


def test_tampered_file_fails_verification(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        service = WorkspaceFileService(repository)
        artifact = service.create_text(
            managed_path="tampered.txt",
            text="original",
            title="Tamper test",
            artifact_type="text",
        )

    (initialized.root / "artifacts" / "tampered.txt").write_text("changed")

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        with pytest.raises(ArtifactIntegrityError):
            WorkspaceFileService(repository).verify(artifact.artifact_id)


def test_service_and_per_call_size_limits(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        with pytest.raises(ArtifactValidationError):
            WorkspaceFileService(repository, maximum_bytes=0)
        with pytest.raises(ArtifactValidationError):
            WorkspaceFileService(repository, maximum_bytes=17 * 1024 * 1024)

        service = WorkspaceFileService(repository, maximum_bytes=5)
        with pytest.raises(ArtifactSizeLimitError):
            service.create_bytes(
                managed_path="large.bin",
                content=b"123456",
                title="Large",
                artifact_type="binary",
            )
        with pytest.raises(ArtifactValidationError):
            service.create_bytes(
                managed_path="invalid-limit.bin",
                content=b"1",
                title="Limit",
                artifact_type="binary",
                max_bytes=6,
            )


def test_validation_and_corrupt_record_detection(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        service = WorkspaceFileService(repository)
        invalid_calls = (
            {"managed_path": "x.txt", "content": b"x", "title": "", "artifact_type": "text"},
            {
                "managed_path": "x.txt",
                "content": b"x",
                "title": "Title",
                "artifact_type": "bad type",
            },
            {
                "managed_path": "x.txt",
                "content": b"x",
                "title": "Title",
                "artifact_type": "text",
                "created_by": "bogus",
            },
            {
                "managed_path": "x.txt",
                "content": b"x",
                "title": "Title",
                "artifact_type": "text",
                "media_type": "invalid",
            },
        )
        for kwargs in invalid_calls:
            with pytest.raises(ArtifactValidationError):
                service.create_bytes(**kwargs)  # type: ignore[arg-type]

        record = repository.create_record(
            record_type="artifact",
            title="Corrupt",
            metadata={
                "artifact_type": "text",
                "managed_path": "corrupt.txt",
                "content_hash": "bad",
                "size_bytes": 1,
                "created_by": "user",
                "operation_id": "operation-corrupt",
            },
        )
        with pytest.raises(ArtifactCorruptError):
            service.get(record.id)


def test_list_limit_and_index_failure(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        service = WorkspaceFileService(repository)
        with pytest.raises(ArtifactValidationError):
            service.list(limit=0)
        with pytest.raises(ArtifactValidationError):
            service.list(limit=201)

        repository.connection.execute("DROP TABLE records")
        with pytest.raises(state.StateCorruptError, match="artifact index"):
            service.list()
