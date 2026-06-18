from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import doll.restore as restore


def test_directory_fsync_contract_on_all_ci_platforms(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[tuple[str, int]] = []

    def open_directory(path: Path, flags: int) -> int:
        events.append(("open", flags))
        return 41

    def sync_directory(descriptor: int) -> None:
        events.append(("fsync", descriptor))

    def close_directory(descriptor: int) -> None:
        events.append(("close", descriptor))

    platform_os = SimpleNamespace(
        name="posix",
        O_RDONLY=0,
        open=open_directory,
        fsync=sync_directory,
        close=close_directory,
    )
    monkeypatch.setattr(restore, "os", platform_os)

    restore._fsync_directory(tmp_path)

    assert events == [("open", 0), ("fsync", 41), ("close", 41)]
