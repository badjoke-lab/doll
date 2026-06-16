from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from doll import state, workspace
from doll.cli import app
from doll.settings import PreferenceService

runner = CliRunner()


def _initialized(tmp_path: Path) -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(tmp_path / "workspace")
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def test_backup_cli_state_create_verify_inspect_list_without_path_leakage(
    tmp_path: Path,
) -> None:
    initialized = _initialized(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        PreferenceService(repository).create(
            key="cli.language",
            value="日本語",
        )
    output = tmp_path / "cli-state.zip"
    created = runner.invoke(
        app,
        [
            "backup",
            "create-state",
            str(output),
            "--workspace",
            str(initialized.root),
            "--operation-id",
            "cli-state-backup",
        ],
    )
    assert created.exit_code == 0
    assert "created, verified, and registered" in created.output
    assert "Backup ID:" in created.output
    assert "File name: cli-state.zip" in created.output
    assert str(initialized.root) not in created.output
    assert str(output) not in created.output

    verified = runner.invoke(app, ["backup", "verify", str(output)])
    inspected = runner.invoke(app, ["backup", "inspect", str(output)])
    listed = runner.invoke(
        app,
        ["backup", "list", "--workspace", str(initialized.root)],
    )
    assert verified.exit_code == 0
    assert inspected.exit_code == 0
    assert listed.exit_code == 0
    assert "Backup verification: passed" in verified.output
    assert "Backup: verified" in inspected.output
    assert "kind=state" in listed.output
    assert "file=cli-state.zip" in listed.output
    for result in (verified, inspected, listed):
        assert str(initialized.root) not in result.output
        assert str(output) not in result.output


def test_backup_cli_workspace_create(tmp_path: Path) -> None:
    initialized = _initialized(tmp_path)
    output = tmp_path / "cli-workspace.zip"
    created = runner.invoke(
        app,
        [
            "backup",
            "create-workspace",
            str(output),
            "--workspace",
            str(initialized.root),
        ],
    )
    assert created.exit_code == 0
    assert "Workspace backup created" in created.output
    assert "File name: cli-workspace.zip" in created.output
    assert str(initialized.root) not in created.output
    assert str(output) not in created.output


def test_backup_cli_errors_hide_paths(tmp_path: Path) -> None:
    missing = tmp_path / "missing.zip"
    verified = runner.invoke(app, ["backup", "verify", str(missing)])
    inspected = runner.invoke(app, ["backup", "inspect", str(missing)])
    assert verified.exit_code == 2
    assert inspected.exit_code == 2
    assert "BackupValidationError" in verified.output
    assert "BackupValidationError" in inspected.output
    assert str(missing) not in verified.output
    assert str(missing) not in inspected.output

    initialized = _initialized(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        PreferenceService(repository).create(
            key="cli.secret",
            value="secret",
            sensitivity="secret",
        )
    output = tmp_path / "refused.zip"
    refused = runner.invoke(
        app,
        [
            "backup",
            "create-workspace",
            str(output),
            "--workspace",
            str(initialized.root),
        ],
    )
    assert refused.exit_code == 2
    assert "BackupValidationError" in refused.output
    assert str(initialized.root) not in refused.output
    assert str(output) not in refused.output


def test_backup_cli_empty_list_and_limit_error(tmp_path: Path) -> None:
    initialized = _initialized(tmp_path)
    empty = runner.invoke(
        app,
        ["backup", "list", "--workspace", str(initialized.root)],
    )
    assert empty.exit_code == 0
    assert "No registered backups." in empty.output

    invalid = runner.invoke(
        app,
        ["backup", "list", "--workspace", str(initialized.root), "--limit", "0"],
    )
    assert invalid.exit_code != 0
    assert str(initialized.root) not in invalid.output
