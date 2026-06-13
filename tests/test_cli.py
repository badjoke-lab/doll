"""Tests for the doll CLI."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from typer.testing import CliRunner

from doll import __version__
from doll.cli import app
from doll.workspace import WORKSPACE_RECORD_NAME

runner = CliRunner()


def test_cli_help() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "personal AI continuity system" in result.stdout
    assert "init" in result.stdout
    assert "version" in result.stdout


def test_cli_version() -> None:
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == __version__


def test_cli_init_explicit_path(tmp_path: Path) -> None:
    target = tmp_path / "workspace"

    result = runner.invoke(
        app,
        ["init", str(target), "--instance-label", "test machine", "--profile", "lite"],
    )

    assert result.exit_code == 0
    assert "Workspace initialized:" in result.stdout
    assert "Workspace ID:" in result.stdout
    assert (target / WORKSPACE_RECORD_NAME).is_file()


def test_cli_init_rejects_invalid_profile(tmp_path: Path) -> None:
    target = tmp_path / "workspace"

    result = runner.invoke(app, ["init", str(target), "--profile", "invalid"])

    assert result.exit_code == 2
    assert "profile must be one of" in result.stderr
    assert not target.exists()


def test_cli_init_reports_existing_workspace(tmp_path: Path) -> None:
    target = tmp_path / "workspace"
    first = runner.invoke(app, ["init", str(target)])

    second = runner.invoke(app, ["init", str(target)])

    assert first.exit_code == 0
    assert second.exit_code == 2
    assert "workspace already initialized" in second.stderr


def test_python_module_help() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "doll", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert "personal AI continuity system" in completed.stdout
