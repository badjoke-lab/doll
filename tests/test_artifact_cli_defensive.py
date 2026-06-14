from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from doll import state, workspace
from doll.cli import app

runner = CliRunner()


def initialized_workspace(tmp_path: Path) -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(tmp_path / "workspace")
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def test_artifact_list_missing_workspace_is_safe(tmp_path: Path) -> None:
    missing = runner.invoke(app, ["artifact", "list", str(tmp_path / "missing")])
    assert missing.exit_code == 2
    assert "artifact listing failed: WorkspaceRecordError" in missing.output
    assert str(tmp_path / "missing") not in missing.output


def test_artifact_verify_missing_record_is_safe(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    result = runner.invoke(
        app,
        [
            "artifact",
            "verify",
            "missing-artifact",
            "--workspace",
            str(initialized.root),
        ],
    )
    assert result.exit_code == 2
    assert "artifact verification failed: KeyError" in result.output
    assert str(initialized.root) not in result.output
