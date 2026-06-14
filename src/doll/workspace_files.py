"""Cross-platform confined and atomic workspace file creation."""

from __future__ import annotations

import errno
import hashlib
import os
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from uuid import uuid4

DEFAULT_MAX_ARTIFACT_BYTES = 16 * 1024 * 1024
MAX_RELATIVE_PATH_LENGTH = 512
MAX_PATH_COMPONENT_LENGTH = 120
_TEMP_PREFIX = ".doll-tmp-"
_WINDOWS_RESERVED_NAMES = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{number}" for number in range(1, 10)),
        *(f"LPT{number}" for number in range(1, 10)),
    }
)
_WINDOWS_FORBIDDEN_CHARACTERS = frozenset('<>:"|?*')


class WorkspaceFileError(RuntimeError):
    """Base class for managed workspace file failures."""


class UnsafeManagedPathError(WorkspaceFileError):
    """Raised when a requested managed path is unsafe or non-portable."""


class ManagedFileExistsError(WorkspaceFileError):
    """Raised when create-new semantics encounter an existing destination."""


class ArtifactSizeLimitError(WorkspaceFileError):
    """Raised when content exceeds the accepted artifact size limit."""


class AtomicPublicationError(WorkspaceFileError):
    """Raised when a complete temporary file cannot be published safely."""


class PublishedFileCleanupError(WorkspaceFileError):
    """Raised when a newly published file cannot be removed after a later failure."""


@dataclass(slots=True)
class PublishedWorkspaceFile:
    """A complete managed file awaiting authoritative registration."""

    path: Path
    managed_path: str
    content_hash: str
    size_bytes: int
    created_directories: tuple[Path, ...]
    _parent_fd: int | None = None
    _final_name: str | None = None
    _closed: bool = False

    def close(self) -> None:
        if self._closed:
            return
        if self._parent_fd is not None:
            os.close(self._parent_fd)
        self._closed = True

    def cleanup(self) -> None:
        """Remove this exact newly published file and empty parents."""

        try:
            if self._parent_fd is not None and self._final_name is not None:
                os.unlink(self._final_name, dir_fd=self._parent_fd)
                _fsync_directory_fd(self._parent_fd)
            else:
                if not _is_link_or_reparse(self.path) and self.path.is_file():
                    self.path.unlink()
                    _fsync_directory_path(self.path.parent)
                elif self.path.exists() or self.path.is_symlink():
                    raise PublishedFileCleanupError(
                        "published artifact cleanup refused an unexpected file type"
                    )
        except FileNotFoundError:
            pass
        except OSError as exc:
            raise PublishedFileCleanupError(
                "published artifact could not be removed after registration failure"
            ) from exc
        finally:
            self.close()

        for directory in reversed(self.created_directories):
            try:
                directory.rmdir()
            except OSError:
                break


@dataclass(frozen=True, slots=True)
class ManagedFileDigest:
    """Verified file size and SHA-256 digest."""

    size_bytes: int
    content_hash: str


def validate_managed_path(value: str) -> PurePosixPath:
    """Validate a portable path relative to the workspace artifacts root."""

    if not isinstance(value, str):
        raise UnsafeManagedPathError("managed path must be text")
    if not value or len(value) > MAX_RELATIVE_PATH_LENGTH:
        raise UnsafeManagedPathError("managed path is empty or too long")
    if "\x00" in value or "\\" in value:
        raise UnsafeManagedPathError("managed path contains an unsafe separator or NUL")
    if PurePosixPath(value).is_absolute():
        raise UnsafeManagedPathError("absolute managed paths are not allowed")
    windows_path = PureWindowsPath(value)
    if windows_path.is_absolute() or windows_path.drive or value.startswith("//"):
        raise UnsafeManagedPathError("drive-qualified or UNC managed paths are not allowed")

    components = value.split("/")
    if not components or any(component in {"", ".", ".."} for component in components):
        raise UnsafeManagedPathError("managed path contains traversal or empty components")

    for component in components:
        _validate_component(component)

    return PurePosixPath(*components)


def publish_new_workspace_file(
    artifacts_root: Path,
    managed_path: str,
    content: bytes,
    *,
    max_bytes: int = DEFAULT_MAX_ARTIFACT_BYTES,
) -> PublishedWorkspaceFile:
    """Publish complete bytes atomically at a new confined managed path."""

    relative = validate_managed_path(managed_path)
    if not isinstance(content, bytes):
        raise TypeError("artifact content must be bytes")
    if max_bytes < 1 or max_bytes > DEFAULT_MAX_ARTIFACT_BYTES:
        raise ArtifactSizeLimitError("artifact size limit is outside the supported range")
    if len(content) > max_bytes:
        raise ArtifactSizeLimitError("artifact content exceeds the accepted size limit")

    root = artifacts_root
    _validate_artifacts_root(root)
    if os.name == "nt":
        return _publish_windows(root, relative, content)
    return _publish_posix(root, relative, content)


def verify_workspace_file(
    artifacts_root: Path,
    managed_path: str,
    *,
    max_bytes: int = DEFAULT_MAX_ARTIFACT_BYTES,
) -> ManagedFileDigest:
    """Re-read and hash one confined regular managed file."""

    relative = validate_managed_path(managed_path)
    if max_bytes < 1 or max_bytes > DEFAULT_MAX_ARTIFACT_BYTES:
        raise ArtifactSizeLimitError("artifact size limit is outside the supported range")
    root = artifacts_root
    _validate_artifacts_root(root)
    target = root.joinpath(*relative.parts)
    _validate_existing_target(root, target)
    return _hash_file(target, max_bytes=max_bytes)


def _validate_component(component: str) -> None:
    if len(component) > MAX_PATH_COMPONENT_LENGTH:
        raise UnsafeManagedPathError("managed path component is too long")
    if component != component.strip() or component.endswith((".", " ")):
        raise UnsafeManagedPathError("managed path component has unsafe surrounding characters")
    if any(ord(character) < 32 for character in component):
        raise UnsafeManagedPathError("managed path component contains control characters")
    if any(character in _WINDOWS_FORBIDDEN_CHARACTERS for character in component):
        raise UnsafeManagedPathError("managed path component is not cross-platform safe")
    if component.upper().split(".", 1)[0] in _WINDOWS_RESERVED_NAMES:
        raise UnsafeManagedPathError("managed path uses a Windows-reserved name")
    if component.startswith(_TEMP_PREFIX):
        raise UnsafeManagedPathError("managed path uses a reserved temporary-file prefix")


def _validate_artifacts_root(root: Path) -> None:
    if not root.is_dir() or _is_link_or_reparse(root):
        raise UnsafeManagedPathError("workspace artifacts root is missing or unsafe")
    resolved = root.resolve(strict=True)
    if resolved != root.resolve():
        raise UnsafeManagedPathError("workspace artifacts root could not be canonicalized")


def _is_link_or_reparse(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        is_junction = getattr(path, "is_junction", None)
        if is_junction is not None and is_junction():
            return True
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
        reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        return bool(reparse_flag and attributes & reparse_flag)
    except FileNotFoundError:
        return False


def _validate_existing_directory(root: Path, directory: Path, root_device: int) -> None:
    if _is_link_or_reparse(directory):
        raise UnsafeManagedPathError("managed parent directory is a link or reparse point")
    try:
        metadata = directory.stat()
    except OSError as exc:
        raise UnsafeManagedPathError("managed parent directory is unreadable") from exc
    if not stat.S_ISDIR(metadata.st_mode):
        raise UnsafeManagedPathError("managed parent component is not a directory")
    if metadata.st_dev != root_device or (directory != root and os.path.ismount(directory)):
        raise UnsafeManagedPathError("managed parent directory crosses a filesystem boundary")
    _require_within_root(root, directory.resolve(strict=True))


def _validate_existing_target(root: Path, target: Path) -> None:
    current = root
    root_device = root.stat().st_dev
    for component in target.relative_to(root).parts[:-1]:
        current = current / component
        _validate_existing_directory(root, current, root_device)
    if _is_link_or_reparse(target):
        raise UnsafeManagedPathError("managed file is a link or reparse point")
    try:
        metadata = target.stat()
    except OSError as exc:
        raise UnsafeManagedPathError("managed file is missing or unreadable") from exc
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_dev != root_device:
        raise UnsafeManagedPathError("managed target is not a confined regular file")
    _require_within_root(root, target.resolve(strict=True))


def _require_within_root(root: Path, candidate: Path) -> None:
    try:
        candidate.relative_to(root.resolve(strict=True))
    except ValueError as exc:
        raise UnsafeManagedPathError("managed path escapes the workspace artifacts root") from exc


def _write_complete_file(descriptor: int, content: bytes) -> ManagedFileDigest:
    digest = hashlib.sha256()
    view = memoryview(content)
    written = 0
    while written < len(view):
        count = os.write(descriptor, view[written:])
        if count <= 0:
            raise AtomicPublicationError("artifact temporary write did not make progress")
        digest.update(view[written : written + count])
        written += count
    os.fsync(descriptor)
    return ManagedFileDigest(size_bytes=written, content_hash=f"sha256:{digest.hexdigest()}")


def _publish_posix(  # pragma: no cover - exercised by native platform CI
    root: Path,
    relative: PurePosixPath,
    content: bytes,
) -> PublishedWorkspaceFile:
    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    file_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    root_fd = os.open(root, directory_flags)
    current_fd = root_fd
    current_path = root
    created_directories: list[Path] = []
    temp_name = f"{_TEMP_PREFIX}{uuid4().hex}"
    final_name = relative.name
    temp_created = False
    final_created = False

    try:
        root_device = os.fstat(root_fd).st_dev
        for component in relative.parts[:-1]:
            next_path = current_path / component
            try:
                os.mkdir(component, mode=0o700, dir_fd=current_fd)
                created_directories.append(next_path)
            except FileExistsError:
                pass
            try:
                next_fd = os.open(component, directory_flags, dir_fd=current_fd)
            except OSError as exc:
                raise UnsafeManagedPathError(
                    "managed parent directory is a link, unreadable, or unsafe"
                ) from exc
            metadata = os.fstat(next_fd)
            if not stat.S_ISDIR(metadata.st_mode) or metadata.st_dev != root_device:
                os.close(next_fd)
                raise UnsafeManagedPathError("managed parent directory escaped confinement")
            if current_fd != root_fd:
                os.close(current_fd)
            current_fd = next_fd
            current_path = next_path

        try:
            descriptor = os.open(temp_name, file_flags, 0o600, dir_fd=current_fd)
        except OSError as exc:
            raise AtomicPublicationError("artifact temporary file could not be created") from exc
        temp_created = True
        try:
            digest = _write_complete_file(descriptor, content)
        finally:
            os.close(descriptor)

        try:
            os.link(
                temp_name,
                final_name,
                src_dir_fd=current_fd,
                dst_dir_fd=current_fd,
                follow_symlinks=False,
            )
        except FileExistsError as exc:
            raise ManagedFileExistsError("managed artifact destination already exists") from exc
        except OSError as exc:
            raise AtomicPublicationError(
                "complete artifact could not be published atomically"
            ) from exc
        final_created = True
        os.unlink(temp_name, dir_fd=current_fd)
        temp_created = False
        _fsync_directory_fd(current_fd)

        metadata = os.stat(final_name, dir_fd=current_fd, follow_symlinks=False)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_dev != root_device:
            raise UnsafeManagedPathError("published artifact is not a confined regular file")

        final_path = root.joinpath(*relative.parts)
        verified = _hash_file(final_path, max_bytes=DEFAULT_MAX_ARTIFACT_BYTES)
        if verified != digest:
            raise AtomicPublicationError("published artifact verification failed")

        if current_fd == root_fd:
            retained_fd = os.dup(root_fd)
        else:
            retained_fd = current_fd
            current_fd = root_fd
        return PublishedWorkspaceFile(
            path=final_path,
            managed_path=relative.as_posix(),
            content_hash=digest.content_hash,
            size_bytes=digest.size_bytes,
            created_directories=tuple(created_directories),
            _parent_fd=retained_fd,
            _final_name=final_name,
        )
    except BaseException:
        if final_created:
            try:
                os.unlink(final_name, dir_fd=current_fd)
            except OSError:
                pass
        if temp_created:
            try:
                os.unlink(temp_name, dir_fd=current_fd)
            except OSError:
                pass
        for directory in reversed(created_directories):
            try:
                directory.rmdir()
            except OSError:
                break
        raise
    finally:
        if current_fd != root_fd:
            os.close(current_fd)
        os.close(root_fd)


def _publish_windows(  # pragma: no cover - exercised by native platform CI
    root: Path,
    relative: PurePosixPath,
    content: bytes,
) -> PublishedWorkspaceFile:
    root_device = root.stat().st_dev
    current = root
    created_directories: list[Path] = []
    for component in relative.parts[:-1]:
        current = current / component
        if os.path.lexists(current):
            _validate_existing_directory(root, current, root_device)
        else:
            current.mkdir(mode=0o700)
            created_directories.append(current)
            _validate_existing_directory(root, current, root_device)

    final_path = root.joinpath(*relative.parts)
    if os.path.lexists(final_path):
        raise ManagedFileExistsError("managed artifact destination already exists")
    temp_path = current / f"{_TEMP_PREFIX}{uuid4().hex}"
    descriptor: int | None = None
    final_created = False
    try:
        file_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
        descriptor = os.open(temp_path, file_flags, 0o600)
        digest = _write_complete_file(descriptor, content)
        os.close(descriptor)
        descriptor = None
        try:
            os.link(temp_path, final_path)
        except FileExistsError as exc:
            raise ManagedFileExistsError("managed artifact destination already exists") from exc
        except OSError as exc:
            raise AtomicPublicationError(
                "complete artifact could not be published atomically"
            ) from exc
        final_created = True
        temp_path.unlink()
        _validate_existing_target(root, final_path)
        verified = _hash_file(final_path, max_bytes=DEFAULT_MAX_ARTIFACT_BYTES)
        if verified != digest:
            raise AtomicPublicationError("published artifact verification failed")
        return PublishedWorkspaceFile(
            path=final_path,
            managed_path=relative.as_posix(),
            content_hash=digest.content_hash,
            size_bytes=digest.size_bytes,
            created_directories=tuple(created_directories),
        )
    except BaseException:
        if descriptor is not None:
            os.close(descriptor)
        temp_path.unlink(missing_ok=True)
        if final_created:
            final_path.unlink(missing_ok=True)
        for directory in reversed(created_directories):
            try:
                directory.rmdir()
            except OSError:
                break
        raise


def _hash_file(path: Path, *, max_bytes: int) -> ManagedFileDigest:
    digest = hashlib.sha256()
    size = 0
    try:
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                size += len(chunk)
                if size > max_bytes:
                    raise ArtifactSizeLimitError(
                        "managed artifact exceeds the supported size limit"
                    )
                digest.update(chunk)
    except ArtifactSizeLimitError:
        raise
    except OSError as exc:
        raise UnsafeManagedPathError("managed artifact could not be read safely") from exc
    return ManagedFileDigest(size_bytes=size, content_hash=f"sha256:{digest.hexdigest()}")


def _fsync_directory_fd(descriptor: int) -> None:
    try:
        os.fsync(descriptor)
    except OSError as exc:
        if exc.errno not in {errno.EINVAL, errno.ENOTSUP, errno.EBADF}:
            raise


def _fsync_directory_path(path: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        _fsync_directory_fd(descriptor)
    finally:
        os.close(descriptor)
