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


def test_memory_cli_full_lifecycle_and_export(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    root = initialized.root

    created = runner.invoke(
        app,
        [
            "memory",
            "create",
            "表示言語",
            "--content",
            "ユーザーは日本語を好む。",
            "--confidence",
            "0.95",
            "--workspace",
            str(root),
            "--operation-id",
            "cli-memory-create",
        ],
    )
    assert created.exit_code == 0
    assert str(root) not in created.output
    item_id = record_id(created.output)

    inspected = runner.invoke(
        app,
        ["memory", "get", item_id, "--workspace", str(root)],
    )
    assert inspected.exit_code == 0
    assert "ユーザーは日本語を好む。" in inspected.output
    assert str(root) not in inspected.output

    listed = runner.invoke(app, ["memory", "list", str(root)])
    assert listed.exit_code == 0
    assert "subject=表示言語" in listed.output
    assert str(root) not in listed.output

    before = state.open_state_repository(root, read_only=True)
    with before as repository:
        revision_before = repository.status().state_revision

    exported = runner.invoke(
        app,
        ["memory", "export", item_id, "--workspace", str(root)],
    )
    assert exported.exit_code == 0
    decoded = json.loads(exported.output)
    assert decoded["record"]["memory"]["content"] == "ユーザーは日本語を好む。"
    assert str(root) not in exported.output

    with state.open_state_repository(root, read_only=True) as repository:
        assert repository.status().state_revision == revision_before

    updated = runner.invoke(
        app,
        [
            "memory",
            "update",
            item_id,
            "--revision",
            "1",
            "--subject",
            "表示言語",
            "--content",
            "ユーザーは簡潔な日本語を好む。",
            "--source-type",
            "user_statement",
            "--confidence",
            "1",
            "--workspace",
            str(root),
            "--operation-id",
            "cli-memory-update",
        ],
    )
    assert updated.exit_code == 0
    assert "Revision: 2" in updated.output

    archived = runner.invoke(
        app,
        [
            "memory",
            "archive",
            item_id,
            "--revision",
            "2",
            "--workspace",
            str(root),
            "--operation-id",
            "cli-memory-archive",
        ],
    )
    assert archived.exit_code == 0

    empty = runner.invoke(app, ["memory", "list", str(root)])
    assert empty.exit_code == 0
    assert "No confirmed memories." in empty.output

    included = runner.invoke(
        app,
        ["memory", "list", str(root), "--include-archived"],
    )
    assert included.exit_code == 0
    assert "status=archived" in included.output


def test_memory_cli_errors_hide_workspace_path(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    root = initialized.root

    invalid = runner.invoke(
        app,
        [
            "memory",
            "create",
            "bad",
            "--content",
            "/private/path",
            "--workspace",
            str(root),
        ],
    )
    assert invalid.exit_code == 2
    assert "memory creation failed" in invalid.output
    assert str(root) not in invalid.output

    missing = runner.invoke(
        app,
        ["memory", "get", "missing-id", "--workspace", str(root)],
    )
    assert missing.exit_code == 2
    assert str(root) not in missing.output


def test_secret_memory_cli_export_is_denied(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    root = initialized.root
    created = runner.invoke(
        app,
        [
            "memory",
            "create",
            "secret category",
            "--content",
            "synthetic fact",
            "--sensitivity",
            "secret",
            "--workspace",
            str(root),
        ],
    )
    assert created.exit_code == 0
    item_id = record_id(created.output)

    exported = runner.invoke(
        app,
        ["memory", "export", item_id, "--workspace", str(root)],
    )
    assert exported.exit_code == 2
    assert "memory export failed" in exported.output
    assert str(root) not in exported.output
