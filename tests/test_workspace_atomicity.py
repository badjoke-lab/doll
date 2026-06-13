from __future__ import annotations

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
