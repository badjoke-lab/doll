from __future__ import annotations

from pathlib import Path

import pytest

from doll import state, state_schema, workspace
from doll.artifact import WorkspaceFileService


def test_database_commit_survives_workspace_revision_sync_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initialized = workspace.initialize_workspace(tmp_path / "workspace")
    with state.initialize_state_repository(initialized.root):
        pass

    with state.open_state_repository(initialized.root) as repository:
        service = WorkspaceFileService(repository)

        def fail_sync(root: Path, revision: int) -> workspace.WorkspaceRecord:
            raise workspace.WorkspaceRevisionError("synthetic sync failure")

        monkeypatch.setattr(state_schema, "update_workspace_state_revision", fail_sync)
        monkeypatch.setattr(
            "doll.state_repository.update_workspace_state_revision",
            fail_sync,
        )
        with pytest.raises(workspace.WorkspaceRevisionError):
            service.create_text(
                managed_path="committed.txt",
                text="committed",
                title="Committed",
                artifact_type="text",
                operation_id="operation-sync-failure",
            )

        row = repository.connection.execute(
            "SELECT id FROM records WHERE record_type = 'artifact'"
        ).fetchone()
        assert row is not None
        assert (
            repository.connection.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]
            == 1
        )

    assert (initialized.root / "artifacts" / "committed.txt").read_text() == "committed"

    with state.open_state_repository(initialized.root) as repository:
        assert repository.status().state_revision == 1
    assert workspace.load_workspace(initialized.root).record.state_revision == 1
