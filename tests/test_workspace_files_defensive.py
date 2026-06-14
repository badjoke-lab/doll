from __future__ import annotations

import errno
import os
from pathlib import Path
from typing import cast

import pytest

from doll import workspace_files
from doll.workspace_files import (
    ArtifactSizeLimitError,
    AtomicPublicationError,
    PublishedFileCleanupError,
    PublishedWorkspaceFile,
    UnsafeManagedPathError,
    publish_new_workspace_file,
    validate_managed_path,
    verify_workspace_file,
)


def artifacts_root(tmp_path: Path) -> Path:
    root = tmp_path / "artifacts"
    root.mkdir(mode=0o700)
    return root


def test_published_file_close_is_idempotent_and_path_cleanup_works(
    tmp_path: Path,
) -> None:
    root = artifacts_root(tmp_path)
    parent = root / "created"
    parent.mkdir()
    target = parent / "file.txt"
    target.write_text("synthetic", encoding="utf-8")

    published = PublishedWorkspaceFile(
        path=target,
        managed_path="created/file.txt",
        content_hash="sha256:" + "0" * 64,
        size_bytes=9,
        created_directories=(parent,),
    )
    published.cleanup()
    published.close()

    assert not target.exists()
    assert not parent.exists()


def test_cleanup_refuses_symlink_when_supported(tmp_path: Path) -> None:
    root = artifacts_root(tmp_path)
    target = root / "target.txt"
    target.write_text("target", encoding="utf-8")
    link = root / "link.txt"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlink creation is unavailable")

    published = PublishedWorkspaceFile(
        path=link,
        managed_path="link.txt",
        content_hash="sha256:" + "0" * 64,
        size_bytes=0,
        created_directories=(),
    )
    with pytest.raises(PublishedFileCleanupError):
        published.cleanup()
    assert link.is_symlink()
    assert target.read_text(encoding="utf-8") == "target"


def test_public_validation_rejects_non_text_non_bytes_and_bad_limits(
    tmp_path: Path,
) -> None:
    root = artifacts_root(tmp_path)

    with pytest.raises(UnsafeManagedPathError):
        validate_managed_path(cast(str, 123))
    with pytest.raises(TypeError):
        publish_new_workspace_file(root, "x.bin", cast(bytes, "not-bytes"))
    with pytest.raises(ArtifactSizeLimitError):
        publish_new_workspace_file(
            root,
            "x.bin",
            b"x",
            max_bytes=workspace_files.DEFAULT_MAX_ARTIFACT_BYTES + 1,
        )
    with pytest.raises(ArtifactSizeLimitError):
        verify_workspace_file(
            root,
            "missing.bin",
            max_bytes=workspace_files.DEFAULT_MAX_ARTIFACT_BYTES + 1,
        )


def test_artifacts_root_and_existing_target_validation(tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    with pytest.raises(UnsafeManagedPathError):
        publish_new_workspace_file(missing, "x.txt", b"x")

    root = artifacts_root(tmp_path)
    directory_target = root / "directory"
    directory_target.mkdir()
    with pytest.raises(UnsafeManagedPathError):
        verify_workspace_file(root, "directory")

    outside = tmp_path / "outside"
    outside.mkdir()
    with pytest.raises(UnsafeManagedPathError):
        workspace_files._require_within_root(root, outside)

    regular_file = root / "not-a-directory"
    regular_file.write_text("x", encoding="utf-8")
    with pytest.raises(UnsafeManagedPathError):
        workspace_files._validate_existing_directory(
            root,
            regular_file,
            root.stat().st_dev,
        )


def test_symlink_artifacts_root_is_rejected_when_supported(tmp_path: Path) -> None:
    real_root = artifacts_root(tmp_path)
    link_root = tmp_path / "artifact-link"
    try:
        link_root.symlink_to(real_root, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlink creation is unavailable")

    with pytest.raises(UnsafeManagedPathError):
        publish_new_workspace_file(link_root, "x.txt", b"x")


def test_low_level_write_and_fsync_failure_branches(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "temporary.bin"
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        monkeypatch.setattr(os, "write", lambda fd, data: 0)
        with pytest.raises(AtomicPublicationError, match="did not make progress"):
            workspace_files._write_complete_file(descriptor, b"x")
    finally:
        os.close(descriptor)

    def ignored_fsync(descriptor: int) -> None:
        raise OSError(errno.EINVAL, "synthetic unsupported fsync")

    monkeypatch.setattr(os, "fsync", ignored_fsync)
    workspace_files._fsync_directory_fd(1)

    def failing_fsync(descriptor: int) -> None:
        raise OSError(errno.EPERM, "synthetic denied fsync")

    monkeypatch.setattr(os, "fsync", failing_fsync)
    with pytest.raises(OSError):
        workspace_files._fsync_directory_fd(1)


def test_verify_enforces_read_size_limit(tmp_path: Path) -> None:
    root = artifacts_root(tmp_path)
    target = root / "large.txt"
    target.write_bytes(b"1234")

    with pytest.raises(ArtifactSizeLimitError):
        verify_workspace_file(root, "large.txt", max_bytes=3)
