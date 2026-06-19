from __future__ import annotations

import zlib
from collections.abc import Callable
from pathlib import Path

import pytest

from doll import restore


@pytest.mark.parametrize(
    "operation",
    [restore.restore_state_backup, restore.restore_workspace_backup],
)
def test_restore_normalizes_decompression_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    operation: Callable[[Path, Path], restore.RestoreResult],
) -> None:
    def fail_verification(backup_path: Path) -> restore.BackupInspection:
        raise zlib.error("synthetic damaged deflate stream")

    monkeypatch.setattr(restore, "verify_backup", fail_verification)
    target = tmp_path / "target"
    with pytest.raises(restore.BackupValidationError, match="backup ZIP is unreadable"):
        operation(tmp_path / "backup.zip", target)
    assert not target.exists()
