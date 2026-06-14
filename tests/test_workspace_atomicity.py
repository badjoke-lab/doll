from __future__ import annotations

import os
from pathlib import Path

import pytest

from doll import workspace


def test_failed_record_write_removes_new_workspace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "workspace"

    def fail_write(path: Path, record: workspace.WorkspaceRecord) -> None:
        raise OSError("simulated write failure")

    monkeypatch.setattr(workspace, "_write_record_atomic", fail_write)

    with pytest.raises(OSError, match="simulated write failure"):
        workspace.initialize_workspace(target)

    assert not target.exists()


def test_failed_record_write_preserves_existing_empty_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "workspace"
    target.mkdir()

    def fail_write(path: Path, record: workspace.WorkspaceRecord) -> None:
        raise OSError("simulated write failure")

    monkeypatch.setattr(workspace, "_write_record_atomic", fail_write)

    with pytest.raises(OSError, match="simulated write failure"):
        workspace.initialize_workspace(target)

    assert target.is_dir()
    assert list(target.iterdir()) == []


def test_atomic_record_write_removes_temporary_file_after_replace_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "workspace"
    target.mkdir()
    record = workspace.WorkspaceRecord.create(
        instance_label="primary",
        profile_preference="lite",
    )

    def fail_replace(source: Path | str, destination: Path | str) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr(os, "replace", fail_replace)

    with pytest.raises(OSError, match="simulated replace failure"):
        workspace._write_record_atomic(target / workspace.WORKSPACE_RECORD_NAME, record)

    assert not (target / workspace.WORKSPACE_RECORD_NAME).exists()
    assert list(target.iterdir()) == []
