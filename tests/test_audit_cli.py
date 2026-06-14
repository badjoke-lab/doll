from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from doll import state, workspace
from doll.audit import AuditService
from doll.cli import app

runner = CliRunner()


def initialized_workspace(tmp_path: Path) -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(tmp_path / "監査-workspace")
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def test_audit_cli_lists_safe_fields_and_filters(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        service = AuditService(repository)
        service.append(
            operation_id="operation-visible",
            actor_type="user",
            actor_id="private-actor-id",
            action="memory.confirm",
            target_type="memory",
            target_id="private-target-id",
            result="success",
            summary="Confirmed synthetic memory",
            metadata={"source": "synthetic"},
        )
        service.append(
            operation_id="operation-other",
            actor_type="system",
            action="memory.verify",
            target_type="memory",
            target_id="other-private-target",
            result="failed",
            summary="Synthetic verification failed",
            error=RuntimeError("secret=must-not-print"),
        )

    result = runner.invoke(
        app,
        [
            "audit",
            "list",
            str(initialized.root),
            "--operation-id",
            "operation-visible",
            "--actor-type",
            "user",
            "--result",
            "success",
            "--limit",
            "10",
        ],
    )

    assert result.exit_code == 0
    assert "operation=operation-visible" in result.stdout
    assert "success user memory.confirm" in result.stdout
    assert "target=memory" in result.stdout
    assert "Confirmed synthetic memory" in result.stdout
    assert "private-actor-id" not in result.stdout
    assert "private-target-id" not in result.stdout
    assert str(initialized.root) not in result.stdout
    assert "must-not-print" not in result.stdout
    assert "operation-other" not in result.stdout


def test_audit_cli_empty_invalid_and_missing_results(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)

    empty = runner.invoke(app, ["audit", "list", str(initialized.root)])
    assert empty.exit_code == 0
    assert empty.stdout.strip() == "No audit events."

    invalid = runner.invoke(
        app,
        ["audit", "list", str(initialized.root), "--actor-type", "bogus"],
    )
    assert invalid.exit_code == 2
    assert "audit listing failed" in invalid.output

    missing = runner.invoke(app, ["audit", "list", str(tmp_path / "missing")])
    assert missing.exit_code == 2
    assert "audit listing failed" in missing.output


def test_audit_cli_read_only_listing_does_not_mutate_files(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        AuditService(repository).append(action="audit.inspect", result="success")

    database_path = initialized.root / "state" / state.STATE_DATABASE_NAME
    workspace_path = initialized.root / workspace.WORKSPACE_RECORD_NAME
    before_database = database_path.stat().st_mtime_ns
    before_workspace = workspace_path.stat().st_mtime_ns

    result = runner.invoke(app, ["audit", "list", str(initialized.root)])

    assert result.exit_code == 0
    assert "audit.inspect" in result.stdout
    assert database_path.stat().st_mtime_ns == before_database
    assert workspace_path.stat().st_mtime_ns == before_workspace
