from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

import doll.restore as restore
from doll import state, workspace
from doll.artifact import ArtifactCorruptError, WorkspaceFileService
from doll.audit import AuditService
from doll.backup import BackupError, create_state_backup, create_workspace_backup
from doll.backup_manifest import BackupManifestService
from doll.cli import app
from doll.memory import ConfirmedMemoryService
from doll.settings import PreferenceService


def _initialized(tmp_path: Path, name: str = "workspace") -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(tmp_path / name)
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def _populate(
    initialized: workspace.InitializedWorkspace,
    *,
    secret: bool = False,
) -> tuple[str, str]:
    with state.open_state_repository(initialized.root) as repository:
        preference = PreferenceService(repository).create(
            key="output.language",
            value={"language": "日本語"},
            description="表示言語",
            operation_id="restore-preference",
        )
        ConfirmedMemoryService(repository).create(
            subject="継続方針",
            content="ローカル優先で復旧可能にする。",
            operation_id="restore-memory",
        )
        artifact = WorkspaceFileService(repository).create_text(
            managed_path="restore/報告.txt",
            text="restored artifact bytes\n",
            title="復元報告",
            operation_id="restore-artifact",
        )
        if secret:
            PreferenceService(repository).create(
                key="private.synthetic",
                value="must-not-restore",
                sensitivity="secret",
                operation_id="restore-secret",
            )
    return preference.record_id, artifact.artifact_id


def test_restore_state_backup_to_absent_target_with_fresh_process(tmp_path: Path) -> None:
    initialized = _initialized(tmp_path)
    preference_id, artifact_id = _populate(initialized, secret=True)
    backup_path = tmp_path / "state-backup.zip"
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        source_revision = repository.status().state_revision
    create_state_backup(initialized.root, backup_path, operation_id="restore-state-backup")

    target = tmp_path / "restored-state"
    result = restore.restore_state_backup(backup_path, target)

    assert result.backup_kind == "state"
    assert result.source_state_revision == source_revision
    assert result.restored_state_revision == source_revision + 1
    assert result.fresh_process_validated is True
    assert target.is_dir()
    assert not any(path.name.startswith(".doll-restore-") for path in tmp_path.iterdir())
    with state.open_state_repository(target, read_only=True) as repository:
        assert repository.status().state_revision == source_revision + 1
        assert PreferenceService(repository).get(preference_id).value == {"language": "日本語"}
        assert repository.connection.execute(
            "SELECT COUNT(*) FROM records WHERE sensitivity = 'secret'"
        ).fetchone() == (0,)
        assert len(AuditService(repository).list(action="state.import")) == 1
        verified = WorkspaceFileService(repository).verify(artifact_id)
        assert verified.actual_size_bytes == len(b"restored artifact bytes\n")
    assert (target / "artifacts" / "restore" / "報告.txt").read_bytes() == (
        b"restored artifact bytes\n"
    )


def test_restore_workspace_backup_preserves_snapshot_inventory_and_audit(tmp_path: Path) -> None:
    initialized = _initialized(tmp_path)
    _, artifact_id = _populate(initialized)
    prior_backup = tmp_path / "prior-state.zip"
    create_state_backup(initialized.root, prior_backup, operation_id="prior-backup")
    workspace_backup = tmp_path / "workspace-backup.zip"
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        source_revision = repository.status().state_revision
        source_records = repository.status().record_count
        source_audits = len(AuditService(repository).list(limit=200))
        source_inventory = len(BackupManifestService(repository).list(limit=200))
    create_workspace_backup(
        initialized.root,
        workspace_backup,
        operation_id="workspace-restore-source",
    )

    target = tmp_path / "restored-workspace"
    result = restore.restore_workspace_backup(workspace_backup, target)

    assert result.source_state_revision == source_revision
    assert result.restored_state_revision == source_revision
    assert result.record_count == source_records
    assert result.audit_event_count == source_audits
    assert result.backup_inventory_count == source_inventory == 1
    with state.open_state_repository(target, read_only=True) as repository:
        assert repository.status().record_count == source_records
        assert len(AuditService(repository).list(limit=200)) == source_audits
        assert len(BackupManifestService(repository).list(limit=200)) == source_inventory
        WorkspaceFileService(repository).verify(artifact_id)
    assert (target / "artifacts" / "restore" / "報告.txt").read_bytes() == (
        b"restored artifact bytes\n"
    )


def test_restore_accepts_and_preserves_existing_empty_target(tmp_path: Path) -> None:
    initialized = _initialized(tmp_path)
    _populate(initialized)
    backup_path = tmp_path / "state.zip"
    create_state_backup(initialized.root, backup_path)
    target = tmp_path / "empty-target"
    target.mkdir()

    result = restore.restore_state_backup(backup_path, target)

    assert result.fresh_process_validated
    assert result.restored_state_revision == result.source_state_revision + 1
    assert (target / workspace.WORKSPACE_RECORD_NAME).is_file()
    assert not any(path.name.startswith(f".{target.name}.empty-") for path in tmp_path.iterdir())


def test_restore_rejects_existing_file_and_nonempty_directory(tmp_path: Path) -> None:
    initialized = _initialized(tmp_path)
    backup_path = tmp_path / "state.zip"
    create_state_backup(initialized.root, backup_path)
    file_target = tmp_path / "file-target"
    file_target.write_text("keep", encoding="utf-8")
    directory_target = tmp_path / "directory-target"
    directory_target.mkdir()
    marker = directory_target / "keep.txt"
    marker.write_text("keep", encoding="utf-8")

    with pytest.raises(restore.RestoreConflictError):
        restore.restore_state_backup(backup_path, file_target)
    with pytest.raises(restore.RestoreConflictError):
        restore.restore_state_backup(backup_path, directory_target)

    assert file_target.read_text(encoding="utf-8") == "keep"
    assert marker.read_text(encoding="utf-8") == "keep"


def test_restore_rejects_symbolic_link_target(tmp_path: Path) -> None:
    initialized = _initialized(tmp_path)
    backup_path = tmp_path / "state.zip"
    create_state_backup(initialized.root, backup_path)
    real_target = tmp_path / "real-target"
    real_target.mkdir()
    link_target = tmp_path / "linked-target"
    try:
        link_target.symlink_to(real_target, target_is_directory=True)
    except OSError:
        pytest.skip("symbolic links are not available")

    with pytest.raises(BackupError):
        restore.restore_state_backup(backup_path, link_target)

    assert list(real_target.iterdir()) == []


def test_restore_rejects_target_with_file_parent(tmp_path: Path) -> None:
    initialized = _initialized(tmp_path)
    backup_path = tmp_path / "state.zip"
    create_state_backup(initialized.root, backup_path)
    parent = tmp_path / "parent-file"
    parent.write_text("keep", encoding="utf-8")

    with pytest.raises((OSError, BackupError)):
        restore.restore_state_backup(backup_path, parent / "target")

    assert parent.read_text(encoding="utf-8") == "keep"


def test_restore_rejects_wrong_backup_kind_without_target_residue(tmp_path: Path) -> None:
    initialized = _initialized(tmp_path)
    workspace_backup = tmp_path / "workspace.zip"
    create_workspace_backup(initialized.root, workspace_backup)
    target = tmp_path / "wrong-kind"

    with pytest.raises(restore.RestoreValidationError):
        restore.restore_state_backup(workspace_backup, target)

    assert not target.exists()


def test_restore_rejects_tampered_backup_before_target_mutation(tmp_path: Path) -> None:
    initialized = _initialized(tmp_path)
    backup_path = tmp_path / "state.zip"
    create_state_backup(initialized.root, backup_path)
    content = bytearray(backup_path.read_bytes())
    content[len(content) // 2] ^= 1
    backup_path.write_bytes(content)
    target = tmp_path / "tampered-target"

    with pytest.raises(BackupError):
        restore.restore_state_backup(backup_path, target)

    assert not target.exists()
    assert not any(path.name.startswith(".doll-restore-") for path in tmp_path.iterdir())


def test_fresh_process_failure_rolls_back_absent_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initialized = _initialized(tmp_path)
    backup_path = tmp_path / "state.zip"
    create_state_backup(initialized.root, backup_path)
    target = tmp_path / "failed-target"

    def fail(*args: object, **kwargs: object) -> restore.RestoreValidation:
        raise restore.RestoreValidationError("synthetic fresh-process failure")

    monkeypatch.setattr(restore, "_validate_in_fresh_process", fail)
    with pytest.raises(restore.RestoreValidationError):
        restore.restore_state_backup(backup_path, target)

    assert not target.exists()
    assert not any(path.name.startswith(".doll-restore-") for path in tmp_path.iterdir())


def test_fresh_process_failure_restores_preexisting_empty_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initialized = _initialized(tmp_path)
    backup_path = tmp_path / "state.zip"
    create_state_backup(initialized.root, backup_path)
    target = tmp_path / "empty-target"
    target.mkdir()

    def fail(*args: object, **kwargs: object) -> restore.RestoreValidation:
        raise restore.RestoreValidationError("synthetic fresh-process failure")

    monkeypatch.setattr(restore, "_validate_in_fresh_process", fail)
    with pytest.raises(restore.RestoreValidationError):
        restore.restore_state_backup(backup_path, target)

    assert target.is_dir()
    assert list(target.iterdir()) == []
    assert not any(path.name.startswith(f".{target.name}.empty-") for path in tmp_path.iterdir())


def test_fresh_process_mismatch_rolls_back_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initialized = _initialized(tmp_path)
    backup_path = tmp_path / "workspace.zip"
    create_workspace_backup(initialized.root, backup_path)
    target = tmp_path / "mismatch-target"
    original = restore._validate_in_fresh_process

    def mismatch(*args: object, **kwargs: object) -> restore.RestoreValidation:
        result = original(*args, **kwargs)
        return restore.RestoreValidation(
            workspace_id=result.workspace_id,
            schema_version=result.schema_version,
            state_revision=result.state_revision,
            record_count=result.record_count + 1,
            artifact_count=result.artifact_count,
            backup_inventory_count=result.backup_inventory_count,
            audit_event_count=result.audit_event_count,
        )

    monkeypatch.setattr(restore, "_validate_in_fresh_process", mismatch)
    with pytest.raises(restore.RestoreValidationError):
        restore.restore_workspace_backup(backup_path, target)

    assert not target.exists()


def test_fresh_process_nonzero_and_invalid_output_are_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inspection = SimpleNamespace(
        workspace_id="00000000-0000-0000-0000-000000000000",
        schema_version=1,
    )

    monkeypatch.setattr(
        restore.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args=[], returncode=2, stdout="", stderr=""),
    )
    with pytest.raises(restore.RestoreValidationError):
        restore._validate_in_fresh_process(
            tmp_path,
            inspection,
            expected_state_revision=0,
        )

    monkeypatch.setattr(
        restore.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=[], returncode=0, stdout="not-json", stderr=""
        ),
    )
    with pytest.raises(restore.RestoreValidationError):
        restore._validate_in_fresh_process(
            tmp_path,
            inspection,
            expected_state_revision=0,
        )


def test_workspace_restore_staging_failure_leaves_no_residue(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initialized = _initialized(tmp_path)
    _populate(initialized)
    backup_path = tmp_path / "workspace.zip"
    create_workspace_backup(initialized.root, backup_path)
    target = tmp_path / "workspace-target"

    original = restore._write_new_file
    calls = 0

    def fail_second(path: Path, content: bytes) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise restore.RestorePublicationError("synthetic staging failure")
        original(path, content)

    monkeypatch.setattr(restore, "_write_new_file", fail_second)
    with pytest.raises(restore.RestorePublicationError):
        restore.restore_workspace_backup(backup_path, target)

    assert not target.exists()
    assert not any(path.name.startswith(".doll-restore-") for path in tmp_path.iterdir())


def test_stage_helpers_reject_missing_required_members(tmp_path: Path) -> None:
    with pytest.raises(BackupError):
        restore._stage_state_restore({}, tmp_path / "state-staging")
    with pytest.raises(BackupError):
        restore._stage_workspace_restore({}, tmp_path / "workspace-staging")


def test_restore_cli_reports_portable_result_without_target_path(tmp_path: Path) -> None:
    initialized = _initialized(tmp_path)
    _populate(initialized)
    backup_path = tmp_path / "state.zip"
    create_state_backup(initialized.root, backup_path)
    target = tmp_path / "cli-target"

    result = CliRunner().invoke(
        app,
        ["backup", "restore-state", str(backup_path), "--target", str(target)],
    )

    assert result.exit_code == 0
    assert "Fresh-process validation: passed" in result.stdout
    assert "Workspace ID:" in result.stdout
    assert str(target) not in result.stdout
    assert str(tmp_path) not in result.stdout


def test_validation_detects_artifact_corruption(tmp_path: Path) -> None:
    initialized = _initialized(tmp_path)
    _, artifact_id = _populate(initialized)
    backup_path = tmp_path / "workspace.zip"
    create_workspace_backup(initialized.root, backup_path)
    target = tmp_path / "restored"
    result = restore.restore_workspace_backup(backup_path, target)
    artifact_path = target / "artifacts" / "restore" / "報告.txt"
    artifact_path.write_bytes(b"changed")

    with pytest.raises(restore.RestoreValidationError):
        restore.validate_restored_workspace(
            target,
            expected_workspace_id=result.workspace_id,
            expected_schema_version=state.CURRENT_SCHEMA_VERSION,
            expected_state_revision=result.restored_state_revision,
        )
    with state.open_state_repository(target, read_only=True) as repository:
        with pytest.raises(ArtifactCorruptError):
            WorkspaceFileService(repository).verify(artifact_id)


def test_validation_rejects_wrong_expected_identity_and_revision(tmp_path: Path) -> None:
    initialized = _initialized(tmp_path)
    backup_path = tmp_path / "workspace.zip"
    create_workspace_backup(initialized.root, backup_path)
    target = tmp_path / "restored"
    result = restore.restore_workspace_backup(backup_path, target)

    with pytest.raises(restore.RestoreValidationError):
        restore.validate_restored_workspace(
            target,
            expected_workspace_id="00000000-0000-0000-0000-000000000000",
            expected_schema_version=state.CURRENT_SCHEMA_VERSION,
            expected_state_revision=result.restored_state_revision,
        )
    with pytest.raises(restore.RestoreValidationError):
        restore.validate_restored_workspace(
            target,
            expected_workspace_id=result.workspace_id,
            expected_schema_version=state.CURRENT_SCHEMA_VERSION,
            expected_state_revision=result.restored_state_revision + 1,
        )


def test_restore_does_not_copy_backup_archive_into_target(tmp_path: Path) -> None:
    initialized = _initialized(tmp_path)
    backup_path = tmp_path / "workspace.zip"
    create_workspace_backup(initialized.root, backup_path)
    target = tmp_path / "restored"

    restore.restore_workspace_backup(backup_path, target)

    assert not any(path.suffix == ".zip" for path in target.rglob("*"))
