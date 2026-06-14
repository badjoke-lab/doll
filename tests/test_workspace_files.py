from __future__ import annotations

import os
from pathlib import Path

import pytest

from doll import workspace_files
from doll.workspace_files import (
    ArtifactSizeLimitError,
    ManagedFileDigest,
    ManagedFileExistsError,
    UnsafeManagedPathError,
    publish_new_workspace_file,
    validate_managed_path,
    verify_workspace_file,
)


def artifacts_root(tmp_path: Path) -> Path:
    root = tmp_path / "artifacts"
    root.mkdir(mode=0o700)
    return root


def test_validate_managed_path_accepts_portable_unicode() -> None:
    result = validate_managed_path("reports/日本語/結果.txt")
    assert result.as_posix() == "reports/日本語/結果.txt"


@pytest.mark.parametrize(
    "value",
    [
        "",
        "/absolute.txt",
        "../escape.txt",
        "reports/../escape.txt",
        "reports/./file.txt",
        "reports//file.txt",
        r"reports\file.txt",
        r"C:\private\file.txt",
        "C:relative.txt",
        "//server/share.txt",
        "CON",
        "aux.txt",
        "reports/name.",
        "reports/ name.txt",
        "reports/name?.txt",
        "reports/.doll-tmp-reserved",
        "reports/a\x00b.txt",
        "a" * 121,
        "a/" * 260 + "file.txt",
    ],
)
def test_validate_managed_path_rejects_unsafe_values(value: str) -> None:
    with pytest.raises(UnsafeManagedPathError):
        validate_managed_path(value)


def test_publish_create_new_hash_size_and_permissions(tmp_path: Path) -> None:
    root = artifacts_root(tmp_path)
    content = "静かな成果物\n".encode()

    published = publish_new_workspace_file(root, "reports/結果.txt", content)
    try:
        assert published.path.read_bytes() == content
        assert published.managed_path == "reports/結果.txt"
        assert published.size_bytes == len(content)
        assert published.content_hash.startswith("sha256:")
        verified = verify_workspace_file(root, published.managed_path)
        assert verified.content_hash == published.content_hash
        if os.name != "nt":
            assert published.path.stat().st_mode & 0o777 == 0o600
            assert published.path.parent.stat().st_mode & 0o777 == 0o700
    finally:
        published.close()


def test_publish_never_overwrites_existing_destination(tmp_path: Path) -> None:
    root = artifacts_root(tmp_path)
    first = publish_new_workspace_file(root, "same.txt", b"first")
    first.close()

    with pytest.raises(ManagedFileExistsError):
        publish_new_workspace_file(root, "same.txt", b"second")

    assert (root / "same.txt").read_bytes() == b"first"
    assert not any(path.name.startswith(".doll-tmp-") for path in root.iterdir())


def test_size_limits_fail_before_file_creation(tmp_path: Path) -> None:
    root = artifacts_root(tmp_path)
    with pytest.raises(ArtifactSizeLimitError):
        publish_new_workspace_file(root, "large.bin", b"1234", max_bytes=3)
    with pytest.raises(ArtifactSizeLimitError):
        publish_new_workspace_file(root, "bad.bin", b"", max_bytes=0)
    assert list(root.iterdir()) == []


def test_symlink_parent_escape_is_rejected_when_supported(tmp_path: Path) -> None:
    root = artifacts_root(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    link = root / "escape"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlink creation is unavailable on this platform")

    with pytest.raises(UnsafeManagedPathError):
        publish_new_workspace_file(root, "escape/pwned.txt", b"blocked")

    assert not (outside / "pwned.txt").exists()


def test_interrupted_temporary_write_is_cleaned_up(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = artifacts_root(tmp_path)

    def fail_write(descriptor: int, content: bytes) -> ManagedFileDigest:
        os.write(descriptor, content[:2])
        raise RuntimeError("synthetic interruption")

    monkeypatch.setattr(workspace_files, "_write_complete_file", fail_write)

    with pytest.raises(RuntimeError, match="synthetic interruption"):
        publish_new_workspace_file(root, "nested/file.txt", b"content")

    assert not (root / "nested" / "file.txt").exists()
    assert not any(root.rglob(".doll-tmp-*"))
    assert not (root / "nested").exists()


def test_verify_rejects_links_and_missing_files(tmp_path: Path) -> None:
    root = artifacts_root(tmp_path)
    with pytest.raises(UnsafeManagedPathError):
        verify_workspace_file(root, "missing.txt")

    target = root / "target.txt"
    target.write_text("target", encoding="utf-8")
    link = root / "link.txt"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("file symlink creation is unavailable on this platform")
    with pytest.raises(UnsafeManagedPathError):
        verify_workspace_file(root, "link.txt")
