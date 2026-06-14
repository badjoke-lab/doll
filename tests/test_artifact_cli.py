from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from doll import state, workspace
from doll.cli import app

runner = CliRunner()


def initialized_workspace(tmp_path: Path) -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(tmp_path / "artifact-workspace")
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def test_artifact_cli_create_list_and_verify_without_absolute_paths(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    operation_id = "cli-artifact-operation"

    created = runner.invoke(
        app,
        [
            "artifact",
            "create",
            "reports/結果.txt",
            "--workspace",
            str(initialized.root),
            "--title",
            "CLI Report",
            "--artifact-type",
            "report",
            "--operation-id",
            operation_id,
        ],
        input="CLIからの本文\n",
    )

    assert created.exit_code == 0
    assert "Artifact created." in created.stdout
    assert "Managed path: reports/結果.txt" in created.stdout
    assert f"Operation ID: {operation_id}" in created.stdout
    assert str(initialized.root) not in created.stdout
    artifact_id = next(
        line.removeprefix("Artifact ID: ")
        for line in created.stdout.splitlines()
        if line.startswith("Artifact ID: ")
    )

    listed = runner.invoke(app, ["artifact", "list", str(initialized.root)])
    assert listed.exit_code == 0
    assert artifact_id in listed.stdout
    assert "path=reports/結果.txt" in listed.stdout
    assert f"operation={operation_id}" in listed.stdout
    assert str(initialized.root) not in listed.stdout

    verified = runner.invoke(
        app,
        [
            "artifact",
            "verify",
            artifact_id,
            "--workspace",
            str(initialized.root),
        ],
    )
    assert verified.exit_code == 0
    assert "Artifact verified." in verified.stdout
    assert "Managed path: reports/結果.txt" in verified.stdout
    assert str(initialized.root) not in verified.stdout


def test_artifact_cli_duplicate_and_unsafe_paths_are_rejected_safely(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    command = [
        "artifact",
        "create",
        "same.txt",
        "--workspace",
        str(initialized.root),
        "--title",
        "Same",
    ]
    assert runner.invoke(app, command, input="first").exit_code == 0

    duplicate = runner.invoke(app, command, input="second")
    assert duplicate.exit_code == 2
    assert "artifact creation rejected" in duplicate.output
    assert str(initialized.root) not in duplicate.output

    escaped = runner.invoke(
        app,
        [
            "artifact",
            "create",
            "../escape.txt",
            "--workspace",
            str(initialized.root),
            "--title",
            "Escape",
        ],
        input="blocked",
    )
    assert escaped.exit_code == 2
    assert "artifact creation rejected" in escaped.output
    assert str(initialized.root) not in escaped.output
    assert not (tmp_path / "escape.txt").exists()


def test_artifact_cli_empty_listing_and_missing_state_are_safe(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    empty = runner.invoke(app, ["artifact", "list", str(initialized.root)])
    assert empty.exit_code == 0
    assert empty.stdout.strip() == "No artifacts."

    missing = runner.invoke(
        app,
        [
            "artifact",
            "create",
            "x.txt",
            "--workspace",
            str(tmp_path / "missing"),
            "--title",
            "Missing",
        ],
        input="x",
    )
    assert missing.exit_code == 2
    assert "artifact creation failed: WorkspaceRecordError" in missing.output
    assert str(tmp_path / "missing") not in missing.output
