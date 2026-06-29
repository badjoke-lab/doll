"""Apply backward-compatible State Package private helper wrappers."""

from __future__ import annotations

from pathlib import Path

TARGET = Path("src/doll/state_package.py")


def _replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise RuntimeError("unexpected State Package compatibility patch context")
    return text.replace(old, new, 1)


def main() -> int:
    text = TARGET.read_text(encoding="utf-8")
    text = _replace_once(
        text,
        '''from doll.artifact import (
    ArtifactCorruptError,
    WorkspaceFileService,
    _artifact_from_record,
)
''',
        '''from doll.artifact import (
    ArtifactCorruptError,
    ArtifactInfo,
    WorkspaceFileService,
    _artifact_from_record,
)
''',
    )
    text = _replace_once(
        text,
        '''def _validate_artifact_members(
    expected_paths: dict[str, tuple[str, int, str]],
    members: dict[str, bytes],
) -> dict[str, bytes]:
    actual_members = {
        name.removeprefix(f"{PACKAGE_ROOT}/files/authoritative/"): content
        for name, content in members.items()
        if name.startswith(f"{PACKAGE_ROOT}/files/authoritative/")
    }
    if set(actual_members) != set(expected_paths):
        raise StatePackageIntegrityError("authoritative file inventory does not match records")
    for path, (_, size_bytes, content_hash) in expected_paths.items():
        content = actual_members[path]
        if len(content) != size_bytes:
            raise StatePackageIntegrityError("authoritative file size does not match record")
        digest = f"sha256:{hashlib.sha256(content).hexdigest()}"
        if digest != content_hash:
            raise StatePackageIntegrityError("authoritative file hash does not match record")
    return actual_members
''',
        '''def _validate_artifact_members(
    artifacts: dict[str, ArtifactInfo] | dict[str, tuple[str, int, str]],
    members: dict[str, bytes],
) -> dict[str, bytes]:
    expected_paths: dict[str, tuple[str, int, str]] = {}
    for value in artifacts.values():
        if isinstance(value, ArtifactInfo):
            managed_path = value.managed_path
            size_bytes = value.size_bytes
            content_hash = value.content_hash
        else:
            managed_path, size_bytes, content_hash = value
        path = validate_managed_path(managed_path).as_posix()
        if path in expected_paths:
            raise StatePackageValidationError("duplicate artifact managed path")
        expected_paths[path] = (path, size_bytes, content_hash)

    actual_members = {
        name.removeprefix(f"{PACKAGE_ROOT}/files/authoritative/"): content
        for name, content in members.items()
        if name.startswith(f"{PACKAGE_ROOT}/files/authoritative/")
    }
    if set(actual_members) != set(expected_paths):
        raise StatePackageIntegrityError("authoritative file inventory does not match records")
    for path, (_, size_bytes, content_hash) in expected_paths.items():
        content = actual_members[path]
        if len(content) != size_bytes:
            raise StatePackageIntegrityError("authoritative file size does not match record")
        digest = f"sha256:{hashlib.sha256(content).hexdigest()}"
        if digest != content_hash:
            raise StatePackageIntegrityError("authoritative file hash does not match record")
    return actual_members
''',
    )
    text = _replace_once(
        text,
        '''def _read_authoritative_file_bytes(
    repository: StateRepository,
    managed_path: str,
    size_bytes: int,
    content_hash: str,
) -> bytes:
''',
        '''def _read_artifact_bytes(
    repository: StateRepository,
    artifact: ArtifactInfo,
) -> bytes:
    """Retain the pre-generalization artifact helper contract for callers and tests."""

    return _read_authoritative_file_bytes(
        repository,
        artifact.managed_path,
        artifact.size_bytes,
        artifact.content_hash,
    )


def _read_authoritative_file_bytes(
    repository: StateRepository,
    managed_path: str,
    size_bytes: int,
    content_hash: str,
) -> bytes:
''',
    )
    TARGET.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
