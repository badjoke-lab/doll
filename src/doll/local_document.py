"""Explicit bounded local reading for caller-selected UTF-8 text and Markdown."""

from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Final

LOCAL_DOCUMENT_REPORT_SCHEMA_VERSION: Final = 1
LOCAL_DOCUMENT_ORIGIN_CLASS: Final = "external_content"
LOCAL_DOCUMENT_ACTOR_TYPE: Final = "extractor"
LOCAL_DOCUMENT_ACQUISITION_METHOD: Final = "extraction"
LOCAL_DOCUMENT_AUTHORITY_CLASS: Final = "untrusted_data"

_MAX_SOURCE_BYTES = 1_048_576
_MAX_TEXT_CHARACTERS = 1_000_000
_UTF8_BOM = b"\xef\xbb\xbf"
_ALLOWED_DOCUMENTS: Final = {
    ".txt": ("text", "text/plain"),
    ".md": ("markdown", "text/markdown"),
    ".markdown": ("markdown", "text/markdown"),
}


class LocalDocumentError(RuntimeError):
    """Base class for local document-read failures."""


class LocalDocumentValidationError(LocalDocumentError):
    """Raised when the caller-selected document is outside the stable boundary."""


class LocalDocumentReadError(LocalDocumentError):
    """Raised when a selected document cannot be read safely and deterministically."""


@dataclass(frozen=True, slots=True)
class LocalDocumentOrigin:
    """Fixed instruction-origin classification for selected local document content."""

    origin_class: str = LOCAL_DOCUMENT_ORIGIN_CLASS
    actor_type: str = LOCAL_DOCUMENT_ACTOR_TYPE
    acquisition_method: str = LOCAL_DOCUMENT_ACQUISITION_METHOD
    authority_class: str = LOCAL_DOCUMENT_AUTHORITY_CLASS

    def to_dict(self) -> dict[str, str]:
        return {
            "origin_class": self.origin_class,
            "actor_type": self.actor_type,
            "acquisition_method": self.acquisition_method,
            "authority_class": self.authority_class,
        }


@dataclass(frozen=True, slots=True)
class LocalDocumentResult:
    """One exact bounded document read with path-free provenance metadata."""

    document_kind: str
    media_type: str
    extension: str
    source_byte_count: int
    content_byte_count: int
    character_count: int
    line_count: int
    source_sha256: str
    content_sha256: str
    utf8_bom_removed: bool
    text: str
    origin: LocalDocumentOrigin = LocalDocumentOrigin()

    def metadata_dict(self) -> dict[str, object]:
        return {
            "schema_version": LOCAL_DOCUMENT_REPORT_SCHEMA_VERSION,
            "document_kind": self.document_kind,
            "media_type": self.media_type,
            "extension": self.extension,
            "source_byte_count": self.source_byte_count,
            "content_byte_count": self.content_byte_count,
            "character_count": self.character_count,
            "line_count": self.line_count,
            "source_sha256": self.source_sha256,
            "content_sha256": self.content_sha256,
            "utf8_bom_removed": self.utf8_bom_removed,
            "origin": self.origin.to_dict(),
            "source_persisted": False,
            "workspace_mutated": False,
            "state_mutated": False,
            "model_execution_used": False,
            "network_access_used": False,
        }

    def to_dict(self, *, include_content: bool = True) -> dict[str, object]:
        payload = self.metadata_dict()
        if include_content:
            payload["content"] = self.text
        return payload


@dataclass(frozen=True, slots=True)
class _FileState:
    device: int
    inode: int
    size: int
    modified_ns: int


def read_local_document(path: Path) -> LocalDocumentResult:
    """Read one explicit text or Markdown file without persistence or side effects."""

    selected = Path(path)
    extension = selected.suffix.casefold()
    document_info = _ALLOWED_DOCUMENTS.get(extension)
    if document_info is None:
        raise LocalDocumentValidationError("unsupported local document extension")

    before_path = _path_state(selected)
    if before_path.size > _MAX_SOURCE_BYTES:
        raise LocalDocumentValidationError("local document exceeds the maximum byte size")

    try:
        with selected.open("rb") as source:
            before_handle = _handle_state(source.fileno())
            if not _same_identity(before_path, before_handle):
                raise LocalDocumentReadError("local document changed before reading")
            raw = source.read(_MAX_SOURCE_BYTES + 1)
            after_handle = _handle_state(source.fileno())
    except LocalDocumentError:
        raise
    except OSError as exc:
        raise LocalDocumentReadError("local document could not be read") from exc

    if len(raw) > _MAX_SOURCE_BYTES:
        raise LocalDocumentValidationError("local document exceeds the maximum byte size")
    after_path = _path_state(selected)
    if not _stable_read(before_path, before_handle, after_handle, after_path):
        raise LocalDocumentReadError("local document changed while being read")

    bom_removed = raw.startswith(_UTF8_BOM)
    decode_bytes = raw[len(_UTF8_BOM) :] if bom_removed else raw
    try:
        text = decode_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise LocalDocumentValidationError("local document is not valid UTF-8") from exc
    if len(text) > _MAX_TEXT_CHARACTERS:
        raise LocalDocumentValidationError("local document exceeds the character limit")
    _validate_text_content(text)

    content_bytes = text.encode("utf-8")
    document_kind, media_type = document_info
    return LocalDocumentResult(
        document_kind=document_kind,
        media_type=media_type,
        extension=extension,
        source_byte_count=len(raw),
        content_byte_count=len(content_bytes),
        character_count=len(text),
        line_count=len(text.splitlines()),
        source_sha256=hashlib.sha256(raw).hexdigest(),
        content_sha256=hashlib.sha256(content_bytes).hexdigest(),
        utf8_bom_removed=bom_removed,
        text=text,
    )


def _path_state(path: Path) -> _FileState:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise LocalDocumentReadError("local document is unavailable") from exc
    if stat.S_ISLNK(metadata.st_mode):
        raise LocalDocumentValidationError("local document symlinks are not supported")
    if not stat.S_ISREG(metadata.st_mode):
        raise LocalDocumentValidationError("local document must be a regular file")
    return _state_from_stat(metadata)


def _handle_state(file_descriptor: int) -> _FileState:
    try:
        metadata = os.fstat(file_descriptor)
    except OSError as exc:
        raise LocalDocumentReadError("local document state could not be verified") from exc
    if not stat.S_ISREG(metadata.st_mode):
        raise LocalDocumentValidationError("local document must be a regular file")
    return _state_from_stat(metadata)


def _state_from_stat(metadata: os.stat_result) -> _FileState:
    return _FileState(
        device=int(metadata.st_dev),
        inode=int(metadata.st_ino),
        size=int(metadata.st_size),
        modified_ns=int(metadata.st_mtime_ns),
    )


def _same_identity(left: _FileState, right: _FileState) -> bool:
    return left.device == right.device and left.inode == right.inode


def _stable_read(
    before_path: _FileState,
    before_handle: _FileState,
    after_handle: _FileState,
    after_path: _FileState,
) -> bool:
    states = (before_path, before_handle, after_handle, after_path)
    first = states[0]
    return all(
        _same_identity(first, current)
        and first.size == current.size
        and first.modified_ns == current.modified_ns
        for current in states[1:]
    )


def _validate_text_content(text: str) -> None:
    if "\x00" in text:
        raise LocalDocumentValidationError("local document contains a NUL byte")
    for character in text:
        codepoint = ord(character)
        if codepoint < 32 and character not in {"\n", "\r", "\t"}:
            raise LocalDocumentValidationError(
                "local document contains a prohibited control character"
            )
        if codepoint == 127:
            raise LocalDocumentValidationError(
                "local document contains a prohibited control character"
            )


__all__ = [
    "LOCAL_DOCUMENT_ACQUISITION_METHOD",
    "LOCAL_DOCUMENT_ACTOR_TYPE",
    "LOCAL_DOCUMENT_AUTHORITY_CLASS",
    "LOCAL_DOCUMENT_ORIGIN_CLASS",
    "LOCAL_DOCUMENT_REPORT_SCHEMA_VERSION",
    "LocalDocumentError",
    "LocalDocumentOrigin",
    "LocalDocumentReadError",
    "LocalDocumentResult",
    "LocalDocumentValidationError",
    "read_local_document",
]
