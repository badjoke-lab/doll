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


def record_id(output: str) -> str:
    return next(
        line.removeprefix("Record ID: ")
        for line in output.splitlines()
        if line.startswith("Record ID: ")
    )


def test_preference_cli_lifecycle_and_no_path_disclosure(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    created = runner.invoke(
        app,
        [
            "preference",
            "create",
            "output.language",
            "--value-json",
            '{"language":"日本語"}',
            "--workspace",
            str(initialized.root),
        ],
    )
    assert created.exit_code == 0
    assert str(initialized.root) not in created.output
    item_id = record_id(created.output)

    inspected = runner.invoke(
        app,
        ["preference", "get", item_id, "--workspace", str(initialized.root)],
    )
    assert inspected.exit_code == 0
    assert "日本語" in inspected.output
    assert str(initialized.root) not in inspected.output

    listed = runner.invoke(app, ["preference", "list", str(initialized.root)])
    assert listed.exit_code == 0
    assert "key=output.language" in listed.output
    assert str(initialized.root) not in listed.output


def test_policy_and_permission_cli_management(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    policy = runner.invoke(
        app,
        [
            "policy",
            "create",
            "network.no-post",
            "--rule",
            "外部POSTを実行しない",
            "--workspace",
            str(initialized.root),
        ],
    )
    assert policy.exit_code == 0
    assert str(initialized.root) not in policy.output

    permission = runner.invoke(
        app,
        [
            "permission",
            "create",
            "artifact.create",
            "--mode",
            "allow_once",
            "--scope-json",
            '{"kind":"global"}',
            "--workspace",
            str(initialized.root),
        ],
    )
    assert permission.exit_code == 0
    permission_id = record_id(permission.output)
    assert "Mode: allow_once" in permission.output
    assert str(initialized.root) not in permission.output

    resolved = runner.invoke(
        app,
        [
            "permission",
            "resolve",
            "artifact.create",
            "--scope-json",
            '{"kind":"global"}',
            "--workspace",
            str(initialized.root),
        ],
    )
    assert resolved.exit_code == 0
    assert "Effective mode: allow_once" in resolved.output

    consumed = runner.invoke(
        app,
        [
            "permission",
            "consume-once",
            permission_id,
            "--revision",
            "1",
            "--operation-id",
            "cli-consume",
            "--workspace",
            str(initialized.root),
        ],
    )
    assert consumed.exit_code == 0
    assert str(initialized.root) not in consumed.output

    inspected = runner.invoke(
        app,
        ["permission", "get", permission_id, "--workspace", str(initialized.root)],
    )
    assert inspected.exit_code == 0
    assert "Effective mode: denied" in inspected.output


def test_cli_rejects_allow_all_and_invalid_json_without_side_effect(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    invalid = runner.invoke(
        app,
        [
            "permission",
            "create",
            "artifact.create",
            "--mode",
            "allow_all",
            "--scope-json",
            '{"kind":"global"}',
            "--workspace",
            str(initialized.root),
        ],
    )
    assert invalid.exit_code == 2
    assert "permission creation failed" in invalid.output
    assert str(initialized.root) not in invalid.output

    bad_json = runner.invoke(
        app,
        [
            "preference",
            "create",
            "x",
            "--value-json",
            "{bad",
            "--workspace",
            str(initialized.root),
        ],
    )
    assert bad_json.exit_code == 2
    assert str(initialized.root) not in bad_json.output

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        assert repository.status().record_count == 0
        assert repository.status().state_revision == 0
