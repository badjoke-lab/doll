from __future__ import annotations

import json
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


def record_id(output: str) -> str:
    return next(
        line.removeprefix("Record ID: ")
        for line in output.splitlines()
        if line.startswith("Record ID: ")
    )


def test_project_and_decision_cli_lifecycle(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    root = initialized.root

    project_create = runner.invoke(
        app,
        [
            "project",
            "create",
            "継続基盤",
            "--description",
            "ローカル状態を保持する。",
            "--status",
            "active",
            "--started-at",
            "2026-06-14T00:00:00Z",
            "--workspace",
            str(root),
        ],
    )
    assert project_create.exit_code == 0
    assert str(root) not in project_create.output
    project_id = record_id(project_create.output)

    decision_create = runner.invoke(
        app,
        [
            "decision",
            "create",
            "memoryを先に作る",
            "--reason",
            "継続性が先だから。",
            "--status",
            "accepted",
            "--decided-at",
            "2026-06-14T01:00:00Z",
            "--project-id",
            project_id,
            "--workspace",
            str(root),
        ],
    )
    assert decision_create.exit_code == 0
    assert str(root) not in decision_create.output
    decision_id = record_id(decision_create.output)

    project_get = runner.invoke(
        app,
        ["project", "get", project_id, "--workspace", str(root)],
    )
    decision_get = runner.invoke(
        app,
        ["decision", "get", decision_id, "--workspace", str(root)],
    )
    assert project_get.exit_code == 0
    assert "ローカル状態を保持する。" in project_get.output
    assert decision_get.exit_code == 0
    assert "継続性が先だから。" in decision_get.output

    project_export = runner.invoke(
        app,
        ["project", "export", project_id, "--workspace", str(root)],
    )
    decision_export = runner.invoke(
        app,
        ["decision", "export", decision_id, "--workspace", str(root)],
    )
    assert json.loads(project_export.output)["record"]["record_type"] == "project"
    assert json.loads(decision_export.output)["record"]["record_type"] == "decision"
    assert str(root) not in project_export.output
    assert str(root) not in decision_export.output

    project_update = runner.invoke(
        app,
        [
            "project",
            "update",
            project_id,
            "--revision",
            "1",
            "--name",
            "継続基盤",
            "--description",
            "更新済み。",
            "--status",
            "active",
            "--started-at",
            "2026-06-14T00:00:00Z",
            "--decision-id",
            decision_id,
            "--workspace",
            str(root),
        ],
    )
    assert project_update.exit_code == 0
    assert "Revision: 2" in project_update.output

    decision_archive = runner.invoke(
        app,
        [
            "decision",
            "archive",
            decision_id,
            "--revision",
            "1",
            "--workspace",
            str(root),
        ],
    )
    project_archive = runner.invoke(
        app,
        [
            "project",
            "archive",
            project_id,
            "--revision",
            "2",
            "--workspace",
            str(root),
        ],
    )
    assert decision_archive.exit_code == 0
    assert project_archive.exit_code == 0

    assert (
        "No projects."
        in runner.invoke(
            app,
            ["project", "list", "--workspace", str(root)],
        ).output
    )
    assert (
        "No decisions."
        in runner.invoke(
            app,
            ["decision", "list", "--workspace", str(root)],
        ).output
    )
    assert (
        "lifecycle=archived"
        in runner.invoke(
            app,
            [
                "project",
                "list",
                "--include-archived",
                "--workspace",
                str(root),
            ],
        ).output
    )


def test_project_decision_cli_errors_hide_paths(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    root = initialized.root

    bad_project = runner.invoke(
        app,
        [
            "project",
            "create",
            "bad",
            "--description",
            "/private/local/path",
            "--status",
            "planned",
            "--started-at",
            "2026-06-14T00:00:00Z",
            "--workspace",
            str(root),
        ],
    )
    assert bad_project.exit_code == 2
    assert "project creation failed" in bad_project.output
    assert str(root) not in bad_project.output

    missing = "00000000-0000-0000-0000-000000000001"
    bad_decision = runner.invoke(
        app,
        [
            "decision",
            "get",
            missing,
            "--workspace",
            str(root),
        ],
    )
    assert bad_decision.exit_code == 2
    assert "decision inspection failed" in bad_decision.output
    assert str(root) not in bad_decision.output
