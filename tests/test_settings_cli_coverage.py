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


def extract_record_id(output: str) -> str:
    return next(
        line.removeprefix("Record ID: ")
        for line in output.splitlines()
        if line.startswith("Record ID: ")
    )


def assert_private_output(result_output: str, root: Path) -> None:
    assert str(root) not in result_output


def test_preference_cli_update_archive_and_error_paths(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    root = initialized.root

    created = runner.invoke(
        app,
        [
            "preference",
            "create",
            "verbosity",
            "--value-json",
            '"normal"',
            "--description",
            "初期値",
            "--workspace",
            str(root),
            "--operation-id",
            "pref-create",
        ],
    )
    assert created.exit_code == 0
    item_id = extract_record_id(created.output)

    updated = runner.invoke(
        app,
        [
            "preference",
            "update",
            item_id,
            "--revision",
            "1",
            "--value-json",
            '"high"',
            "--description",
            "更新値",
            "--workspace",
            str(root),
            "--operation-id",
            "pref-update",
        ],
    )
    assert updated.exit_code == 0
    assert "Revision: 2" in updated.output

    archived = runner.invoke(
        app,
        [
            "preference",
            "archive",
            item_id,
            "--revision",
            "2",
            "--workspace",
            str(root),
            "--operation-id",
            "pref-archive",
        ],
    )
    assert archived.exit_code == 0

    empty = runner.invoke(app, ["preference", "list", str(root)])
    assert empty.exit_code == 0
    assert "No preferences." in empty.output

    included = runner.invoke(
        app,
        ["preference", "list", str(root), "--include-archived"],
    )
    assert included.exit_code == 0
    assert "status=archived" in included.output

    stale = runner.invoke(
        app,
        [
            "preference",
            "update",
            item_id,
            "--revision",
            "1",
            "--value-json",
            '"x"',
            "--workspace",
            str(root),
        ],
    )
    assert stale.exit_code == 2
    assert "preference update failed" in stale.output

    missing = runner.invoke(
        app,
        ["preference", "get", "missing-id", "--workspace", str(root)],
    )
    assert missing.exit_code == 2
    assert "preference inspection failed" in missing.output

    for output in (
        created.output,
        updated.output,
        archived.output,
        empty.output,
        included.output,
        stale.output,
        missing.output,
    ):
        assert_private_output(output, root)


def test_policy_cli_full_lifecycle(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    root = initialized.root

    created = runner.invoke(
        app,
        [
            "policy",
            "create",
            "network.no-post",
            "--rule",
            "外部POSTを実行しない",
            "--workspace",
            str(root),
            "--operation-id",
            "policy-create",
        ],
    )
    assert created.exit_code == 0
    item_id = extract_record_id(created.output)

    inspected = runner.invoke(
        app,
        ["policy", "get", item_id, "--workspace", str(root)],
    )
    assert inspected.exit_code == 0
    assert "Enabled: true" in inspected.output
    assert "外部POSTを実行しない" in inspected.output

    updated = runner.invoke(
        app,
        [
            "policy",
            "update",
            item_id,
            "--revision",
            "1",
            "--rule",
            "状態変更通信は承認なしに実行しない",
            "--disabled",
            "--workspace",
            str(root),
            "--operation-id",
            "policy-update",
        ],
    )
    assert updated.exit_code == 0

    listed = runner.invoke(app, ["policy", "list", str(root)])
    assert listed.exit_code == 0
    assert "enabled=false" in listed.output

    archived = runner.invoke(
        app,
        [
            "policy",
            "archive",
            item_id,
            "--revision",
            "2",
            "--workspace",
            str(root),
            "--operation-id",
            "policy-archive",
        ],
    )
    assert archived.exit_code == 0

    empty = runner.invoke(app, ["policy", "list", str(root)])
    assert empty.exit_code == 0
    assert "No policies." in empty.output

    included = runner.invoke(
        app,
        ["policy", "list", str(root), "--include-archived"],
    )
    assert included.exit_code == 0
    assert "status=archived" in included.output

    missing = runner.invoke(
        app,
        ["policy", "get", "missing-id", "--workspace", str(root)],
    )
    assert missing.exit_code == 2

    for output in (
        created.output,
        inspected.output,
        updated.output,
        listed.output,
        archived.output,
        empty.output,
        included.output,
        missing.output,
    ):
        assert_private_output(output, root)


def test_permission_cli_update_list_archive_resolve_and_failures(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    root = initialized.root
    scope = '{"kind":"project","project_id":"p-1"}'

    missing = runner.invoke(
        app,
        [
            "permission",
            "resolve",
            "artifact.create",
            "--scope-json",
            scope,
            "--workspace",
            str(root),
        ],
    )
    assert missing.exit_code == 0
    assert "Effective mode: denied" in missing.output
    assert "Reason: no_record" in missing.output

    created = runner.invoke(
        app,
        [
            "permission",
            "create",
            "artifact.create",
            "--mode",
            "ask",
            "--scope-json",
            scope,
            "--workspace",
            str(root),
            "--operation-id",
            "permission-create",
        ],
    )
    assert created.exit_code == 0
    item_id = extract_record_id(created.output)

    updated = runner.invoke(
        app,
        [
            "permission",
            "update",
            item_id,
            "--revision",
            "1",
            "--mode",
            "scoped",
            "--workspace",
            str(root),
            "--operation-id",
            "permission-update",
        ],
    )
    assert updated.exit_code == 0
    assert "mode=scoped" in updated.output

    listed = runner.invoke(app, ["permission", "list", str(root)])
    assert listed.exit_code == 0
    assert "mode=scoped" in listed.output
    assert "scope_kind=project" in listed.output

    inspected = runner.invoke(
        app,
        ["permission", "get", item_id, "--workspace", str(root)],
    )
    assert inspected.exit_code == 0
    assert "Effective mode: scoped" in inspected.output

    resolved = runner.invoke(
        app,
        [
            "permission",
            "resolve",
            "artifact.create",
            "--scope-json",
            scope,
            "--workspace",
            str(root),
        ],
    )
    assert resolved.exit_code == 0
    assert "Effective mode: scoped" in resolved.output
    assert f"Record ID: {item_id}" in resolved.output

    archived = runner.invoke(
        app,
        [
            "permission",
            "archive",
            item_id,
            "--revision",
            "2",
            "--workspace",
            str(root),
            "--operation-id",
            "permission-archive",
        ],
    )
    assert archived.exit_code == 0

    empty = runner.invoke(app, ["permission", "list", str(root)])
    assert empty.exit_code == 0
    assert "No permissions." in empty.output

    included = runner.invoke(
        app,
        ["permission", "list", str(root), "--include-archived"],
    )
    assert included.exit_code == 0
    assert "status=archived" in included.output

    bad_scope = runner.invoke(
        app,
        [
            "permission",
            "create",
            "artifact.create",
            "--mode",
            "ask",
            "--scope-json",
            "[]",
            "--workspace",
            str(root),
        ],
    )
    assert bad_scope.exit_code == 2
    assert "permission creation failed" in bad_scope.output

    missing_get = runner.invoke(
        app,
        ["permission", "get", "missing-id", "--workspace", str(root)],
    )
    assert missing_get.exit_code == 2

    for output in (
        missing.output,
        created.output,
        updated.output,
        listed.output,
        inspected.output,
        resolved.output,
        archived.output,
        empty.output,
        included.output,
        bad_scope.output,
        missing_get.output,
    ):
        assert_private_output(output, root)


def test_permission_consume_failure_cli(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    root = initialized.root

    created = runner.invoke(
        app,
        [
            "permission",
            "create",
            "artifact.create",
            "--mode",
            "denied",
            "--scope-json",
            '{"kind":"global"}',
            "--workspace",
            str(root),
        ],
    )
    assert created.exit_code == 0
    item_id = extract_record_id(created.output)

    consumed = runner.invoke(
        app,
        [
            "permission",
            "consume-once",
            item_id,
            "--revision",
            "1",
            "--operation-id",
            "invalid-consume",
            "--workspace",
            str(root),
        ],
    )
    assert consumed.exit_code == 2
    assert "permission consumption failed" in consumed.output
    assert_private_output(consumed.output, root)
