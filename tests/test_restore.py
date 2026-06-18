from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Literal

import pytest
from typer.testing import CliRunner

import doll.restore as restore
import doll.restore_validation as restore_validation
from doll import state, workspace
from doll.artifact import ArtifactIntegrityError, WorkspaceFileService
from doll.audit import AuditService
from doll.backup import (
    BackupError,
    BackupInspection,
    create_state_backup,
    create_workspace_backup,
)
from doll.backup_manifest import BackupManifestService
from doll.cli import app
from doll.memory import ConfirmedMemoryService
from doll.settings import PreferenceService
from doll.state_package import StatePackageImportError


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


def _inspection(
    *,
    kind: Literal["state", "workspace"] = "state",
) -> BackupInspection:
    return BackupInspection(
        backup_format_version=1,
        backup_kind=kind,
        workspace_id="00000000-0000-0000-0000-000000000000",
        schema_version=state.CURRENT_SCHEMA_VERSION,
        source_state_revision=0,
        created_at="2026-06-17T00:00:00Z",
        included_categories=(),
        excluded_categories=(),
        member_count=0,
        payload_file_count=0,
        total_payload_size_bytes=0,
        manifest_hash="sha256:" + "0" * 64,
        file_size_bytes=0,
        file_sha256="sha256:" + "0" * 64,
    )


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
    with state.open_state_repository(target, read_only=True) as repository:
        assert repository.status().state_revision == source_revision + 1
        assert PreferenceService(repository).get(preference_id).value == {"language": "日本語"}
        row = repository.connection.execute(
            "SELECT COUNT(*) FROM records WHERE sensitivity = 'secret'"
        ).fetchone()
        assert row is not None
        assert int(row[0]) == 0
        WorkspaceFileService(repository).verify(artifact_id)
    assert (target / "artifacts" / "restore" / "報告.txt").read_bytes() == (
        b"restored artifact bytes\n"
    )


def test_restore_workspace_backup_preserves_snapshot_inventory_and_audit(tmp_path: Path) -> None:
    initialized = _initialized(tmp_path)
    _, artifact_id = _populate(initialized)
    prior_backup = tmp_path / "prior-state.zip"
    create_state_backup(initialized.root, prior_backup, operation_id="prior-backup")
    backup_path = tmp_path / "workspace-backup.zip"
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        source_revision = repository.status().state_revision
        source_records = repository.status().record_count
        source_audits = len(AuditService(repository).list(limit=200))
        source_inventory = len(BackupManifestService(repository).list(limit=200))
    create_workspace_backup(initialized.root, backup_path)

    target = tmp_path / "restored-workspace"
    result = restore.restore_workspace_backup(backup_path, target)

    assert result.restored_state_revision == source_revision
    assert result.record_count == source_records
    assert result.audit_event_count == source_audits
    assert result.backup_inventory_count == source_inventory == 1
    with state.open_state_repository(target, read_only=True) as repository:
        assert repository.status().record_count == source_records
        assert len(AuditService(repository).list(limit=200)) == source_audits
        assert len(BackupManifestService(repository).list(limit=200)) == source_inventory
        WorkspaceFileService(repository).verify(artifact_id)


def test_restore_accepts_existing_empty_target(tmp_path: Path) -> None:
    initialized = _initialized(tmp_path)
    backup_path = tmp_path / "state.zip"
    create_state_backup(initialized.root, backup_path)
    target = tmp_path / "empty-target"
    target.mkdir()

    result = restore.restore_state_backup(backup_path, target)

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


def test_restore_rejects_wrong_kind_and_tampering(tmp_path: Path) -> None:
    initialized = _initialized(tmp_path)
    workspace_backup = tmp_path / "workspace.zip"
    create_workspace_backup(initialized.root, workspace_backup)
    with pytest.raises(restore.RestoreValidationError):
        restore.restore_state_backup(workspace_backup, tmp_path / "wrong-kind")

    state_backup = tmp_path / "state.zip"
    create_state_backup(initialized.root, state_backup)
    content = bytearray(state_backup.read_bytes())
    content[len(content) // 2] ^= 1
    state_backup.write_bytes(content)
    with pytest.raises(BackupError):
        restore.restore_state_backup(state_backup, tmp_path / "tampered-target")


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


def test_fresh_process_mismatch_rolls_back_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initialized = _initialized(tmp_path)
    backup_path = tmp_path / "workspace.zip"
    create_workspace_backup(initialized.root, backup_path)
    target = tmp_path / "mismatch-target"
    original = restore._validate_in_fresh_process

    def mismatch(*args: Any, **kwargs: Any) -> restore.RestoreValidation:
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


def test_restore_cli_reports_portable_result_without_paths(tmp_path: Path) -> None:
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
    assert str(target) not in result.stdout
    assert str(tmp_path) not in result.stdout


def test_restore_workspace_cli_and_restore_failures(tmp_path: Path) -> None:
    initialized = _initialized(tmp_path)
    backup_path = tmp_path / "workspace.zip"
    create_workspace_backup(initialized.root, backup_path)
    target = tmp_path / "workspace-target"

    success = CliRunner().invoke(
        app,
        ["backup", "restore-workspace", str(backup_path), "--target", str(target)],
    )
    assert success.exit_code == 0
    assert "Workspace backup restored" in success.stdout

    missing_state = CliRunner().invoke(
        app,
        ["backup", "restore-state", str(tmp_path / "missing.zip"), "--target", str(target)],
    )
    assert missing_state.exit_code == 2
    assert "state backup restore failed" in missing_state.stderr

    missing_workspace = CliRunner().invoke(
        app,
        [
            "backup",
            "restore-workspace",
            str(tmp_path / "missing-workspace.zip"),
            "--target",
            str(tmp_path / "another-target"),
        ],
    )
    assert missing_workspace.exit_code == 2
    assert "workspace backup restore failed" in missing_workspace.stderr


def test_validation_detects_artifact_corruption(tmp_path: Path) -> None:
    initialized = _initialized(tmp_path)
    _, artifact_id = _populate(initialized)
    backup_path = tmp_path / "workspace.zip"
    create_workspace_backup(initialized.root, backup_path)
    target = tmp_path / "restored"
    result = restore.restore_workspace_backup(backup_path, target)
    (target / "artifacts" / "restore" / "報告.txt").write_bytes(b"changed")

    with pytest.raises(restore.RestoreValidationError):
        restore.validate_restored_workspace(
            target,
            expected_workspace_id=result.workspace_id,
            expected_schema_version=state.CURRENT_SCHEMA_VERSION,
            expected_state_revision=result.restored_state_revision,
        )
    with state.open_state_repository(target, read_only=True) as repository:
        with pytest.raises(ArtifactIntegrityError):
            WorkspaceFileService(repository).verify(artifact_id)


def test_validation_rejects_wrong_identity_and_revision(tmp_path: Path) -> None:
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


def test_stage_helpers_reject_missing_required_members(tmp_path: Path) -> None:
    with pytest.raises(BackupError):
        restore._stage_state_restore({}, tmp_path / "state-staging")
    with pytest.raises(BackupError):
        restore._stage_workspace_restore({}, tmp_path / "workspace-staging")


def test_fresh_process_rejects_nonzero_invalid_and_os_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inspection = _inspection()

    def nonzero(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=[], returncode=2, stdout="", stderr="")

    monkeypatch.setattr(restore.subprocess, "run", nonzero)
    with pytest.raises(restore.RestoreValidationError):
        restore._validate_in_fresh_process(tmp_path, inspection, expected_state_revision=0)

    def invalid(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="not-json", stderr="")

    monkeypatch.setattr(restore.subprocess, "run", invalid)
    with pytest.raises(restore.RestoreValidationError):
        restore._validate_in_fresh_process(tmp_path, inspection, expected_state_revision=0)

    def os_failure(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise OSError("synthetic")

    monkeypatch.setattr(restore.subprocess, "run", os_failure)
    with pytest.raises(restore.RestoreValidationError):
        restore._validate_in_fresh_process(tmp_path, inspection, expected_state_revision=0)


def test_fresh_process_accepts_valid_portable_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inspection = _inspection()
    payload = {
        "workspace_id": inspection.workspace_id,
        "schema_version": inspection.schema_version,
        "state_revision": 4,
        "record_count": 3,
        "artifact_count": 1,
        "backup_inventory_count": 0,
        "audit_event_count": 2,
    }

    def valid(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json.dumps(payload), stderr=""
        )

    monkeypatch.setattr(restore.subprocess, "run", valid)
    result = restore._validate_in_fresh_process(
        tmp_path,
        inspection,
        expected_state_revision=4,
    )
    assert result.record_count == 3
    assert result.artifact_count == 1


def test_count_rejects_missing_row() -> None:
    class MissingRowConnection:
        def execute(self, query: str) -> MissingRowConnection:
            return self

        def fetchone(self) -> None:
            return None

    with pytest.raises(restore.RestoreValidationError):
        restore._count(MissingRowConnection(), "SELECT 1")


def test_state_stage_wraps_import_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_import(package: Path, target: Path) -> None:
        raise StatePackageImportError("synthetic")

    monkeypatch.setattr(restore, "import_state_package", fail_import)
    with pytest.raises(restore.RestoreValidationError):
        restore._stage_state_restore(
            {restore._STATE_MEMBER: b"not-a-package"},
            tmp_path / "staging",
        )


def test_write_new_file_wraps_open_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_open(self: Path, *args: object, **kwargs: object) -> Any:
        raise OSError("synthetic")

    monkeypatch.setattr(Path, "open", fail_open)
    with pytest.raises(restore.RestorePublicationError):
        restore._write_new_file(tmp_path / "file", b"value")


def test_publish_target_rejects_races(tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    staging.mkdir()
    target = tmp_path / "target"
    target.mkdir()
    (target / "appeared").write_text("keep", encoding="utf-8")
    with pytest.raises(restore.RestoreConflictError):
        restore._publish_target(staging, target, target_existed=True)
    assert (target / "appeared").read_text(encoding="utf-8") == "keep"

    staging_two = tmp_path / "staging-two"
    staging_two.mkdir()
    target_two = tmp_path / "target-two"
    target_two.write_text("appeared", encoding="utf-8")
    with pytest.raises(restore.RestoreConflictError):
        restore._publish_target(staging_two, target_two, target_existed=False)


def test_publish_target_rolls_back_when_post_publish_fsync_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "new").write_text("new", encoding="utf-8")
    target = tmp_path / "target"
    target.mkdir()

    def fail_fsync(path: Path) -> None:
        raise restore.RestorePublicationError("synthetic")

    monkeypatch.setattr(restore, "_fsync_directory", fail_fsync)
    with pytest.raises(restore.RestorePublicationError):
        restore._publish_target(staging, target, target_existed=True)
    assert target.is_dir()
    assert list(target.iterdir()) == []


def test_generic_restore_failure_is_wrapped_and_cleaned(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backup = tmp_path / "backup.zip"
    backup.write_bytes(b"placeholder")
    inspection = _inspection(kind="workspace")

    def verified(path: Path) -> BackupInspection:
        return inspection

    def members(path: Path, value: BackupInspection) -> dict[str, bytes]:
        return {}

    def fail_stage(staged_members: dict[str, bytes], staging: Path) -> None:
        raise ValueError("synthetic")

    monkeypatch.setattr(restore, "verify_backup", verified)
    monkeypatch.setattr(restore, "_read_verified_members", members)
    monkeypatch.setattr(restore, "_stage_workspace_restore", fail_stage)
    with pytest.raises(restore.RestoreError):
        restore.restore_workspace_backup(backup, tmp_path / "target")


def test_fsync_directory_wraps_os_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if os.name == "nt":
        pytest.skip("Windows intentionally skips directory fsync")

    def fail_open(path: Path, flags: int) -> int:
        raise OSError("synthetic")

    monkeypatch.setattr(restore.os, "open", fail_open)
    with pytest.raises(restore.RestorePublicationError):
        restore._fsync_directory(tmp_path)


def test_restore_validation_main_reports_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [
            "restore-validation",
            "--workspace",
            str(tmp_path / "missing"),
            "--workspace-id",
            "00000000-0000-0000-0000-000000000000",
            "--schema-version",
            "1",
            "--state-revision",
            "0",
        ],
    )
    assert restore_validation.main() == 2
    assert "Error" in capsys.readouterr().out
