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


def test_backup_cli_create_workspace_and_list_fail_safely(tmp_path: Path) -> None:
    runner = CliRunner()
    missing = tmp_path / "missing-workspace"

    created = runner.invoke(
        app,
        [
            "backup",
            "create-workspace",
            str(tmp_path / "backup.zip"),
            "--workspace",
            str(missing),
        ],
    )
    assert created.exit_code == 2
    assert "workspace backup creation failed" in created.stderr

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
