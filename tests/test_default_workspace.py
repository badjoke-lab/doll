from __future__ import annotations

from pathlib import Path

from pytest import MonkeyPatch

from doll import workspace


def test_initialize_workspace_uses_default_path(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    expected = tmp_path / "default-workspace"
    monkeypatch.setattr(workspace, "default_workspace_path", lambda: expected)

    result = workspace.initialize_workspace()

    assert result.root == expected.resolve()
    assert (expected / workspace.WORKSPACE_RECORD_NAME).is_file()
