from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

import doll.restore as restore
from doll import state
from doll.backup import BackupInspection
from doll.cli import app


def _inspection() -> BackupInspection:
    return BackupInspection(
        backup_format_version=1,
        backup_kind="state",
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
        file_size_bytes=1,
        file_sha256="sha256:" + "0" * 64,
    )


def test_backup_cli_create_and_list_fail_safely(tmp_path: Path) -> None:
    runner = CliRunner()
    missing = tmp_path / "missing-workspace"

    state_created = runner.invoke(
        app,
        [
            "backup",
            "create-state",
            str(tmp_path / "state-backup.zip"),
            "--workspace",
            str(missing),
        ],
    )
    assert state_created.exit_code == 2
    assert "state backup creation failed" in state_created.stderr

    workspace_created = runner.invoke(
        app,
        [
            "backup",
            "create-workspace",
            str(tmp_path / "workspace-backup.zip"),
            "--workspace",
            str(missing),
        ],
    )
    assert workspace_created.exit_code == 2
    assert "workspace backup creation failed" in workspace_created.stderr

    listed = runner.invoke(app, ["backup", "list", "--workspace", str(missing)])
    assert listed.exit_code == 2
    assert "backup listing failed" in listed.stderr


def test_verified_member_reload_detects_changed_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backup_path = tmp_path / "backup.zip"
    backup_path.write_bytes(b"x")

    def changed(
        path: Path,
        *,
        maximum: int,
        label: str,
    ) -> bytes:
        return b"x"

    monkeypatch.setattr(restore, "_read_regular_file", changed)
    with pytest.raises(restore.BackupIntegrityError):
        restore._read_verified_members(backup_path, _inspection())


def test_write_new_file_ignores_chmod_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "value.bin"

    def fail_chmod(self: Path, mode: int) -> None:
        raise OSError("synthetic")

    monkeypatch.setattr(Path, "chmod", fail_chmod)
    restore._write_new_file(path, b"value")
    assert path.read_bytes() == b"value"


def test_rollback_removes_staging_and_published_target(tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "partial").write_text("partial", encoding="utf-8")
    target = tmp_path / "target"
    target.mkdir()
    (target / "published").write_text("published", encoding="utf-8")

    restore._rollback_restore(
        staging,
        target,
        empty_backup=None,
        published=True,
        target_existed=False,
    )

    assert not staging.exists()
    assert not target.exists()


def test_rollback_restores_original_empty_target(tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    target = tmp_path / "target"
    empty_backup = tmp_path / ".target.empty"
    empty_backup.mkdir()

    restore._rollback_restore(
        staging,
        target,
        empty_backup=empty_backup,
        published=True,
        target_existed=True,
    )

    assert target.is_dir()
    assert list(target.iterdir()) == []
    assert not empty_backup.exists()


def test_rollback_recreates_missing_original_empty_target(tmp_path: Path) -> None:
    restore._rollback_restore(
        tmp_path / "missing-staging",
        tmp_path / "target",
        empty_backup=None,
        published=True,
        target_existed=True,
    )

    target = tmp_path / "target"
    assert target.is_dir()
    assert list(target.iterdir()) == []


def test_rollback_wraps_cleanup_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    staging = tmp_path / "staging"
    staging.mkdir()

    def fail_remove(path: Path) -> None:
        raise OSError("synthetic")

    monkeypatch.setattr(restore.shutil, "rmtree", fail_remove)
    with pytest.raises(restore.RestorePublicationError):
        restore._rollback_restore(
            staging,
            tmp_path / "target",
            empty_backup=None,
            published=False,
            target_existed=False,
        )
