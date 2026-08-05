"""Explicit bounded local PDF text extraction through an optional in-process adapter."""

from __future__ import annotations

import hashlib
import importlib
import io
import os
import stat
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol, cast

LOCAL_PDF_REPORT_SCHEMA_VERSION: Final = 1
LOCAL_PDF_ORIGIN_CLASS: Final = "external_content"
LOCAL_PDF_ACTOR_TYPE: Final = "extractor"
LOCAL_PDF_ACQUISITION_METHOD: Final = "extraction"
LOCAL_PDF_AUTHORITY_CLASS: Final = "untrusted_data"

_MAX_SOURCE_BYTES = 8_388_608
_MAX_DOCUMENT_PAGES = 200
_MAX_SELECTED_PAGES = 100
_MAX_PAGE_CHARACTERS = 100_000
_MAX_AGGREGATE_CHARACTERS = 1_000_000


class LocalPdfError(RuntimeError):
    """Base class for bounded local PDF extraction failures."""


class LocalPdfValidationError(LocalPdfError):
    """Raised when a selected PDF or extraction request is invalid."""


class LocalPdfReadError(LocalPdfError):
    """Raised when a selected PDF cannot be read safely."""


class LocalPdfAdapterUnavailableError(LocalPdfError):
    """Raised when the optional PDF adapter is not installed."""


class _PdfPage(Protocol):
    def extract_text(self) -> str | None: ...


class _PdfReader(Protocol):
    @property
    def is_encrypted(self) -> bool: ...

    @property
    def pages(self) -> Sequence[_PdfPage]: ...


class PdfTextAdapter(Protocol):
    """Replaceable in-process PDF text extraction adapter contract."""

    adapter_id: str
    adapter_version: str

    def open_reader(self, source_bytes: bytes) -> _PdfReader: ...


@dataclass(frozen=True, slots=True)
class PypdfTextAdapter:
    """Optional pypdf-backed in-process adapter loaded only when invoked."""

    adapter_id: str = "pypdf"
    adapter_version: str = "unavailable"

    @classmethod
    def load(cls) -> PypdfTextAdapter:
        try:
            module = importlib.import_module("pypdf")
        except ModuleNotFoundError as exc:
            raise LocalPdfAdapterUnavailableError(
                "optional local PDF adapter is not installed"
            ) from exc
        version = getattr(module, "__version__", None)
        if not isinstance(version, str) or not version.strip():
            raise LocalPdfAdapterUnavailableError(
                "optional local PDF adapter version is unavailable"
            )
        return cls(adapter_version=version)

    def open_reader(self, source_bytes: bytes) -> _PdfReader:
        try:
            module = importlib.import_module("pypdf")
        except ModuleNotFoundError as exc:
            raise LocalPdfAdapterUnavailableError(
                "optional local PDF adapter is not installed"
            ) from exc
        reader_class = getattr(module, "PdfReader", None)
        if reader_class is None:
            raise LocalPdfAdapterUnavailableError(
                "optional local PDF adapter does not expose PdfReader"
            )
        try:
            reader = reader_class(io.BytesIO(source_bytes), strict=True)
        except Exception as exc:
            raise LocalPdfValidationError("local PDF structure is invalid") from exc
        return cast(_PdfReader, reader)


@dataclass(frozen=True, slots=True)
class LocalPdfOrigin:
    """Fixed instruction-origin classification for extracted PDF text."""

    origin_class: str = LOCAL_PDF_ORIGIN_CLASS
    actor_type: str = LOCAL_PDF_ACTOR_TYPE
    acquisition_method: str = LOCAL_PDF_ACQUISITION_METHOD
    authority_class: str = LOCAL_PDF_AUTHORITY_CLASS

    def to_dict(self) -> dict[str, str]:
        return {
            "origin_class": self.origin_class,
            "actor_type": self.actor_type,
            "acquisition_method": self.acquisition_method,
            "authority_class": self.authority_class,
        }


@dataclass(frozen=True, slots=True)
class LocalPdfPageText:
    """One selected page's bounded extracted text."""

    page_number: int
    text: str

    @property
    def character_count(self) -> int:
        return len(self.text)

    @property
    def has_extractable_text(self) -> bool:
        return bool(self.text.strip())

    def to_dict(self, *, include_text: bool) -> dict[str, object]:
        payload: dict[str, object] = {
            "page_number": self.page_number,
            "character_count": self.character_count,
            "has_extractable_text": self.has_extractable_text,
        }
        if include_text:
            payload["text"] = self.text
        return payload


@dataclass(frozen=True, slots=True)
class LocalPdfExtraction:
    """Deterministic non-persistent extraction result for one selected PDF."""

    adapter_id: str
    adapter_version: str
    source_byte_count: int
    source_sha256: str
    document_page_count: int
    selected_page_numbers: tuple[int, ...]
    pages: tuple[LocalPdfPageText, ...]
    origin: LocalPdfOrigin = LocalPdfOrigin()

    @property
    def selected_page_count(self) -> int:
        return len(self.pages)

    @property
    def aggregate_character_count(self) -> int:
        return sum(page.character_count for page in self.pages)

    @property
    def empty_text_page_numbers(self) -> tuple[int, ...]:
        return tuple(page.page_number for page in self.pages if not page.has_extractable_text)

    def to_dict(self, *, include_text: bool = True) -> dict[str, object]:
        return {
            "schema_version": LOCAL_PDF_REPORT_SCHEMA_VERSION,
            "adapter_id": self.adapter_id,
            "adapter_version": self.adapter_version,
            "source_byte_count": self.source_byte_count,
            "source_sha256": self.source_sha256,
            "document_page_count": self.document_page_count,
            "selected_page_count": self.selected_page_count,
            "selected_page_numbers": list(self.selected_page_numbers),
            "aggregate_character_count": self.aggregate_character_count,
            "empty_text_page_numbers": list(self.empty_text_page_numbers),
            "pages": [page.to_dict(include_text=include_text) for page in self.pages],
            "origin": self.origin.to_dict(),
            "source_persisted": False,
            "output_persisted": False,
            "source_overwritten": False,
            "workspace_mutated": False,
            "state_mutated": False,
            "ocr_used": False,
            "image_extraction_used": False,
            "model_execution_used": False,
            "process_launch_used": False,
            "network_access_used": False,
        }


@dataclass(frozen=True, slots=True)
class _FileState:
    device: int
    inode: int
    size: int
    modified_ns: int


def extract_local_pdf_text(
    path: Path,
    *,
    selected_pages: tuple[int, ...] = (),
    adapter: PdfTextAdapter | None = None,
) -> LocalPdfExtraction:
    """Extract selected page text without persistence, OCR, models, or network access."""

    source_bytes = _read_pdf_source(path)
    active_adapter = adapter or PypdfTextAdapter.load()
    try:
        reader = active_adapter.open_reader(source_bytes)
    except LocalPdfError:
        raise
    except Exception as exc:
        raise LocalPdfValidationError("local PDF could not be parsed") from exc

    try:
        encrypted = bool(reader.is_encrypted)
    except Exception as exc:
        raise LocalPdfValidationError("local PDF encryption state is unavailable") from exc
    if encrypted:
        raise LocalPdfValidationError("encrypted local PDFs are not supported")
    try:
        document_page_count = len(reader.pages)
    except Exception as exc:
        raise LocalPdfValidationError("local PDF page inventory is unavailable") from exc
    if document_page_count < 1:
        raise LocalPdfValidationError("local PDF must contain at least one page")
    if document_page_count > _MAX_DOCUMENT_PAGES:
        raise LocalPdfValidationError("local PDF exceeds the page limit")

    page_numbers = _selected_page_numbers(selected_pages, document_page_count)
    pages: list[LocalPdfPageText] = []
    aggregate_characters = 0
    for page_number in page_numbers:
        try:
            extracted = reader.pages[page_number - 1].extract_text()
        except Exception as exc:
            raise LocalPdfValidationError("local PDF page text extraction failed") from exc
        if extracted is None:
            text = ""
        elif isinstance(extracted, str):
            text = extracted
        else:
            raise LocalPdfValidationError("local PDF adapter returned invalid page text")
        _validate_extracted_text(text)
        if len(text) > _MAX_PAGE_CHARACTERS:
            raise LocalPdfValidationError("local PDF page text exceeds the character limit")
        aggregate_characters += len(text)
        if aggregate_characters > _MAX_AGGREGATE_CHARACTERS:
            raise LocalPdfValidationError(
                "local PDF extracted text exceeds the aggregate character limit"
            )
        pages.append(LocalPdfPageText(page_number=page_number, text=text))

    return LocalPdfExtraction(
        adapter_id=_bounded_adapter_field(active_adapter.adapter_id, "identifier"),
        adapter_version=_bounded_adapter_field(active_adapter.adapter_version, "version"),
        source_byte_count=len(source_bytes),
        source_sha256=hashlib.sha256(source_bytes).hexdigest(),
        document_page_count=document_page_count,
        selected_page_numbers=page_numbers,
        pages=tuple(pages),
    )


def _read_pdf_source(path: Path) -> bytes:
    selected = Path(path)
    if selected.suffix.casefold() != ".pdf":
        raise LocalPdfValidationError("local PDF input must use the .pdf extension")
    before_path = _path_state(selected)
    if before_path.size > _MAX_SOURCE_BYTES:
        raise LocalPdfValidationError("local PDF exceeds the maximum byte size")

    try:
        with selected.open("rb") as source:
            before_handle = _handle_state(source.fileno())
            if not _same_identity(before_path, before_handle):
                raise LocalPdfReadError("local PDF changed before reading")
            raw = source.read(_MAX_SOURCE_BYTES + 1)
            after_handle = _handle_state(source.fileno())
    except LocalPdfError:
        raise
    except OSError as exc:
        raise LocalPdfReadError("local PDF could not be read") from exc

    if len(raw) > _MAX_SOURCE_BYTES:
        raise LocalPdfValidationError("local PDF exceeds the maximum byte size")
    after_path = _path_state(selected)
    if not _stable_read(before_path, before_handle, after_handle, after_path):
        raise LocalPdfReadError("local PDF changed while being read")
    if not raw.startswith(b"%PDF-"):
        raise LocalPdfValidationError("local PDF signature is invalid")
    return raw


def _selected_page_numbers(
    selected_pages: tuple[int, ...],
    document_page_count: int,
) -> tuple[int, ...]:
    if not selected_pages:
        return tuple(range(1, document_page_count + 1))
    if len(selected_pages) > _MAX_SELECTED_PAGES:
        raise LocalPdfValidationError("too many local PDF pages were selected")
    if any(isinstance(page, bool) or page < 1 for page in selected_pages):
        raise LocalPdfValidationError("local PDF page selections must be positive integers")
    if len(set(selected_pages)) != len(selected_pages):
        raise LocalPdfValidationError("local PDF page selections must be unique")
    if any(page > document_page_count for page in selected_pages):
        raise LocalPdfValidationError("selected local PDF page does not exist")
    return selected_pages


def _bounded_adapter_field(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 80:
        raise LocalPdfValidationError(f"local PDF adapter {field} is invalid")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise LocalPdfValidationError(f"local PDF adapter {field} is invalid")
    return value


def _validate_extracted_text(text: str) -> None:
    if "\x00" in text:
        raise LocalPdfValidationError("local PDF extracted text contains a NUL byte")
    for character in text:
        codepoint = ord(character)
        if codepoint < 32 and character not in {"\n", "\r", "\t", "\f"}:
            raise LocalPdfValidationError(
                "local PDF extracted text contains a prohibited control character"
            )
        if codepoint == 127:
            raise LocalPdfValidationError(
                "local PDF extracted text contains a prohibited control character"
            )


def _path_state(path: Path) -> _FileState:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise LocalPdfReadError("local PDF is unavailable") from exc
    if stat.S_ISLNK(metadata.st_mode):
        raise LocalPdfValidationError("local PDF symlinks are not supported")
    if not stat.S_ISREG(metadata.st_mode):
        raise LocalPdfValidationError("local PDF must be a regular file")
    return _state_from_stat(metadata)


def _handle_state(file_descriptor: int) -> _FileState:
    try:
        metadata = os.fstat(file_descriptor)
    except OSError as exc:
        raise LocalPdfReadError("local PDF state could not be verified") from exc
    if not stat.S_ISREG(metadata.st_mode):
        raise LocalPdfValidationError("local PDF must be a regular file")
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


__all__ = [
    "LOCAL_PDF_ACQUISITION_METHOD",
    "LOCAL_PDF_ACTOR_TYPE",
    "LOCAL_PDF_AUTHORITY_CLASS",
    "LOCAL_PDF_ORIGIN_CLASS",
    "LOCAL_PDF_REPORT_SCHEMA_VERSION",
    "LocalPdfAdapterUnavailableError",
    "LocalPdfError",
    "LocalPdfExtraction",
    "LocalPdfOrigin",
    "LocalPdfPageText",
    "LocalPdfReadError",
    "LocalPdfValidationError",
    "PdfTextAdapter",
    "PypdfTextAdapter",
    "extract_local_pdf_text",
]
