from __future__ import annotations

import errno
import os
from pathlib import Path

import pytest

import doll.backup as backup
import doll.state_package as state_package
import doll.workspace_files as workspace_files


def test_posix_durability_helpers_are_exercised_portably(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    durable_file = tmp_path / "durable.bin"
    durable_file.write_bytes(b"durable")

    fsync_calls: list[int] = []
    open_calls: list[tuple[object, int]] = []
    close_calls: list[int] = []

    def fake_fsync(descriptor: int) -> None:
        fsync_calls.append(descriptor)

    def fake_open(path: object, flags: int) -> int:
        open_calls.append((path, flags))
        return 77

    def fake_close(descriptor: int) -> None:
        close_calls.append(descriptor)

    monkeypatch.setattr(os, "name", "posix")
    monkeypatch.setattr(os, "fsync", fake_fsync)

    state_package._fsync_file(durable_file)
    assert len(fsync_calls) == 1
    fsync_calls.clear()

    monkeypatch.setattr(os, "open", fake_open)
    monkeypatch.setattr(os, "close", fake_close)

    state_package._fsync_directory(tmp_path)
    backup._fsync_directory(tmp_path)
    workspace_files._fsync_directory_path(tmp_path)

    assert len(open_calls) == 3
    assert fsync_calls == [77, 77, 77]
    assert close_calls == [77, 77, 77]


def test_posix_durability_helpers_wrap_and_filter_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    durable_file = tmp_path / "durable.bin"
    durable_file.write_bytes(b"durable")

    def failing_fsync(descriptor: int) -> None:
        raise OSError(errno.EIO, f"synthetic fsync failure for {descriptor}")

    monkeypatch.setattr(os, "name", "posix")
    monkeypatch.setattr(os, "fsync", failing_fsync)

    with pytest.raises(state_package.StatePackageExportError):
        state_package._fsync_file(durable_file)

    monkeypatch.setattr(os, "open", lambda path, flags: 88)
    monkeypatch.setattr(os, "close", lambda descriptor: None)

    with pytest.raises(state_package.StatePackageError):
        state_package._fsync_directory(tmp_path)
    with pytest.raises(backup.BackupCreationError):
        backup._fsync_directory(tmp_path)

    def unsupported_fsync(descriptor: int) -> None:
        raise OSError(errno.EBADF, f"unsupported directory fsync for {descriptor}")

    monkeypatch.setattr(os, "fsync", unsupported_fsync)
    workspace_files._fsync_directory_path(tmp_path)
