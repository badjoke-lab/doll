from __future__ import annotations

from pathlib import Path

from doll import workspace


def test_unicode_workspace_path(tmp_path: Path) -> None:
    target = tmp_path / "日本語"

    result = workspace.initialize_workspace(target)

    assert result.root == target.resolve()
    assert (target / workspace.WORKSPACE_RECORD_NAME).is_file()
