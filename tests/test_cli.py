"""Tests for the minimal doll CLI."""

from __future__ import annotations

import subprocess
import sys

from typer.testing import CliRunner

from doll import __version__
from doll.cli import app

runner = CliRunner()


def test_cli_help() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "personal AI continuity system" in result.stdout
    assert "version" in result.stdout


def test_cli_version() -> None:
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == __version__


def test_python_module_help() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "doll", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert "personal AI continuity system" in completed.stdout
