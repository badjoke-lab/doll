from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from doll import state, workspace
from doll.cli import app
from doll.memory import ConfirmedMemoryService

runner = CliRunner()


def initialized_workspace(tmp_path: Path) -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(tmp_path / "workspace")
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def test_state_package_cli_round_trip_and_no_path_output(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        ConfirmedMemoryService(repository).create(
            subject="CLI memory",
            content="日本語",
        )
    package = tmp_path / "cli.zip"
    exported = runner.invoke(
        app,
        [
            "state-package",
            "export",
            str(package),
            "--workspace",
            str(initialized.root),
        ],
    )
    assert exported.exit_code == 0
    assert "exported and verified" in exported.output
    assert str(initialized.root) not in exported.output
    assert str(package) not in exported.output

    verified = runner.invoke(app, ["state-package", "verify", str(package)])
    inspected = runner.invoke(app, ["state-package", "inspect", str(package)])
    assert verified.exit_code == 0
    assert inspected.exit_code == 0
    assert str(package) not in verified.output
    assert str(package) not in inspected.output

    target = tmp_path / "imported"
    imported = runner.invoke(
        app,
        [
            "state-package",
            "import",
            str(package),
            "--target",
            str(target),
        ],
    )
    assert imported.exit_code == 0
    assert "imported and verified" in imported.output
    assert str(package) not in imported.output
    assert str(target) not in imported.output


def test_state_package_cli_errors_hide_paths(tmp_path: Path) -> None:
    missing = tmp_path / "missing.zip"
    result = runner.invoke(app, ["state-package", "verify", str(missing)])
    assert result.exit_code == 2
    assert "StatePackageValidationError" in result.output
    assert str(missing) not in result.output
