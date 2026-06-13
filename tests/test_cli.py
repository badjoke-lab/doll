"""Tests for the doll CLI."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from pytest import MonkeyPatch
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


def test_help_and_version_do_not_initialize_workspace(monkeypatch: MonkeyPatch) -> None:
    import doll.cli as cli_module

    monkeypatch.setattr(
        cli_module,
        "initialize_workspace",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unexpected init")),
    )

    help_result = runner.invoke(app, ["--help"])
    version_result = runner.invoke(app, ["version"])

    assert help_result.exit_code == 0
    assert version_result.exit_code == 0


def test_initial_import_and_create_app_have_no_workspace_side_effect(tmp_path: Path) -> None:
    home = tmp_path / "home"
    xdg_data_home = tmp_path / "xdg-data"
    local_app_data = tmp_path / "local-app-data"
    app_data = tmp_path / "app-data"
    home.mkdir()
    xdg_data_home.mkdir()
    local_app_data.mkdir()
    app_data.mkdir()
    environment = {
        **os.environ,
        "HOME": str(home),
        "XDG_DATA_HOME": str(xdg_data_home),
        "LOCALAPPDATA": str(local_app_data),
        "APPDATA": str(app_data),
    }

    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "import doll; import doll.cli; from doll.api import create_app; create_app()",
        ],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert completed.returncode == 0, completed.stderr
    assert not list(tmp_path.rglob("workspace.json"))
    assert not list(tmp_path.rglob("workspace"))
