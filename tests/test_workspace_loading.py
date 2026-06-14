"""Tests for loading and revision updates of initialized workspaces."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from doll import workspace


def test_load_workspace_and_update_revision(tmp_path: Path) -> None:
    initialized = workspace.initialize_workspace(tmp_path / "workspace")

    loaded = workspace.load_workspace(initialized.root)

    assert loaded.record.workspace_id == initialized.record.workspace_id

    updated = workspace.update_workspace_state_revision(initialized.root, 2)

    assert updated.state_revision == 2
    assert workspace.load_workspace(initialized.root).record.state_revision == 2
    assert workspace.update_workspace_state_revision(initialized.root, 2).state_revision == 2

    with pytest.raises(workspace.WorkspaceRevisionError):
        workspace.update_workspace_state_revision(initialized.root, 1)


def test_load_workspace_rejects_missing_invalid_and_future_records(tmp_path: Path) -> None:
    with pytest.raises(workspace.WorkspaceRecordError):
        workspace.load_workspace(tmp_path / "missing")

    target = tmp_path / "workspace"
    initialized = workspace.initialize_workspace(target)
    record_path = target / workspace.WORKSPACE_RECORD_NAME

    record_path.write_text("not-json", encoding="utf-8")
    with pytest.raises(workspace.WorkspaceRecordError):
        workspace.load_workspace(target)

    workspace._write_record_atomic(
        record_path,
        initialized.record.model_copy(update={"schema_version": 2}),
    )
    with pytest.raises(workspace.WorkspaceRecordError):
        workspace.load_workspace(target)


def test_load_workspace_rejects_unreadable_record_and_missing_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "workspace"
    workspace.initialize_workspace(target)
    record_path = target / workspace.WORKSPACE_RECORD_NAME
    original_read_text = Path.read_text

    def unreadable(
        self: Path,
        encoding: str | None = None,
        errors: str | None = None,
    ) -> str:
        if self == record_path:
            raise OSError("permission denied")
        return original_read_text(self, encoding=encoding, errors=errors)

    monkeypatch.setattr(Path, "read_text", unreadable)
    with pytest.raises(workspace.WorkspaceRecordError):
        workspace.load_workspace(target)

    monkeypatch.undo()
    (target / "state").rmdir()
    with pytest.raises(workspace.WorkspaceRecordError):
        workspace.load_workspace(target)


def test_workspace_record_rejects_negative_revision() -> None:
    record = workspace.WorkspaceRecord.create(
        instance_label="primary",
        profile_preference="lite",
    )
    payload = record.model_dump()
    payload["state_revision"] = -1

    with pytest.raises(ValidationError):
        workspace.WorkspaceRecord.model_validate(payload)


def test_workspace_revision_json_remains_valid(tmp_path: Path) -> None:
    initialized = workspace.initialize_workspace(tmp_path / "workspace")

    workspace.update_workspace_state_revision(initialized.root, 1)

    payload = json.loads(
        (initialized.root / workspace.WORKSPACE_RECORD_NAME).read_text(encoding="utf-8")
    )
    assert payload["state_revision"] == 1
