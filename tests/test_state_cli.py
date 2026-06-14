"""CLI tests for explicit SQLite state operations."""

from __future__ import annotations

from pathlib import Path

from pytest import MonkeyPatch
from typer.testing import CliRunner

from doll.cli import app
from doll.state import STATE_DATABASE_NAME

runner = CliRunner()


def test_workspace_init_does_not_create_state_database(tmp_path: Path) -> None:
    target = tmp_path / "workspace"

    result = runner.invoke(app, ["init", str(target)])

    assert result.exit_code == 0
    assert not (target / "state" / STATE_DATABASE_NAME).exists()


def test_state_cli_init_and_read_only_status(tmp_path: Path) -> None:
    target = tmp_path / "workspace"
    assert runner.invoke(app, ["init", str(target)]).exit_code == 0

    initialized = runner.invoke(app, ["state", "init", str(target)])

    assert initialized.exit_code == 0
    assert "Schema version: 1" in initialized.stdout
    assert "State revision: 0" in initialized.stdout

    status = runner.invoke(app, ["state", "status", str(target)])

    assert status.exit_code == 0
    assert "State database: ready" in status.stdout
    assert "Record count: 0" in status.stdout
    assert "Mode: read-only" in status.stdout


def test_state_cli_reports_missing_and_duplicate_state(tmp_path: Path) -> None:
    missing = runner.invoke(app, ["state", "status", str(tmp_path / "missing")])

    assert missing.exit_code == 2
    assert "state inspection failed" in missing.output

    target = tmp_path / "workspace"
    assert runner.invoke(app, ["init", str(target)]).exit_code == 0
    assert runner.invoke(app, ["state", "init", str(target)]).exit_code == 0

    duplicate = runner.invoke(app, ["state", "init", str(target)])

    assert duplicate.exit_code == 2
    assert "state initialization failed" in duplicate.output


def test_help_and_version_do_not_initialize_state(monkeypatch: MonkeyPatch) -> None:
    import doll.cli as cli_module

    monkeypatch.setattr(
        cli_module,
        "initialize_state_repository",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unexpected state init")),
    )

    assert runner.invoke(app, ["--help"]).exit_code == 0
    assert runner.invoke(app, ["version"]).exit_code == 0
