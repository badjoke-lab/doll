"""Explicit bounded local raster-image OCR through an optional in-process adapter."""

from __future__ import annotations

import binascii
import hashlib
import importlib
import importlib.metadata
import io
import os
import stat
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Final, Protocol, cast

LOCAL_OCR_REPORT_SCHEMA_VERSION: Final = 1
LOCAL_OCR_ORIGIN_CLASS: Final = "external_content"
LOCAL_OCR_ACTOR_TYPE: Final = "extractor"
LOCAL_OCR_ACQUISITION_METHOD: Final = "ocr"
LOCAL_OCR_AUTHORITY_CLASS: Final = "untrusted_data"

_MAX_SOURCE_BYTES = 8_388_608
_MAX_IMAGE_WIDTH = 10_000
_MAX_IMAGE_HEIGHT = 10_000
_MAX_IMAGE_PIXELS = 25_000_000
_MAX_RECOGNIZED_LINES = 1_000
_MAX_LINE_CHARACTERS = 20_000
_MAX_AGGREGATE_CHARACTERS = 200_000
_ALLOWED_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg"})


class LocalOcrError(RuntimeError):
    """Base class for bounded local OCR failures."""


class LocalOcrValidationError(LocalOcrError):
    """Raised when a selected image, adapter result, or OCR request is invalid."""


class LocalOcrReadError(LocalOcrError):
    """Raised when a selected image cannot be read safely."""


class LocalOcrAdapterUnavailableError(LocalOcrError):
    """Raised when the optional local OCR adapter is unavailable."""


class OcrAdapter(Protocol):
    """Replaceable in-process OCR adapter contract."""

    adapter_id: str
    adapter_version: str

    def recognize(self, source_bytes: bytes) -> Sequence[str]: ...


class _PillowImage(Protocol):
    def load(self) -> object: ...

    def copy(self) -> object: ...

    def close(self) -> None: ...


class _OcrmacEngine(Protocol):
    def recognize(self) -> Sequence[object]: ...


@dataclass(frozen=True, slots=True)
class OcrmacAdapter:
    """Optional macOS Vision adapter loaded only when OCR is invoked."""

    adapter_id: str = "ocrmac-vision"
    adapter_version: str = "unavailable"

    @classmethod
    def load(cls) -> OcrmacAdapter:
        if sys.platform != "darwin":
            raise LocalOcrAdapterUnavailableError(
                "optional local OCR adapter is unavailable on this platform"
            )
        try:
            importlib.import_module("ocrmac.ocrmac")
            importlib.import_module("PIL.Image")
            version = importlib.metadata.version("ocrmac")
        except (ModuleNotFoundError, importlib.metadata.PackageNotFoundError) as exc:
            raise LocalOcrAdapterUnavailableError(
                "optional local OCR adapter is not installed"
            ) from exc
        if not version.strip():
            raise LocalOcrAdapterUnavailableError(
                "optional local OCR adapter version is unavailable"
            )
        return cls(adapter_version=version)

    def recognize(self, source_bytes: bytes) -> Sequence[str]:
        try:
            ocr_module = importlib.import_module("ocrmac.ocrmac")
            image_module = importlib.import_module("PIL.Image")
        except ModuleNotFoundError as exc:
            raise LocalOcrAdapterUnavailableError(
                "optional local OCR adapter is not installed"
            ) from exc

        image_open = _required_callable(image_module, "open", "Pillow image decoder")
        ocr_class = _required_callable(ocr_module, "OCR", "ocrmac OCR class")
        try:
            image = cast(_PillowImage, image_open(io.BytesIO(source_bytes)))
            try:
                image.load()
                image_copy = image.copy()
            finally:
                image.close()
            engine = cast(
                _OcrmacEngine,
                ocr_class(
                    image_copy,
                    framework="vision",
                    recognition_level="accurate",
                ),
            )
            annotations = engine.recognize()
        except LocalOcrError:
            raise
        except Exception as exc:
            raise LocalOcrValidationError("local OCR recognition failed") from exc

        if isinstance(annotations, (str, bytes)) or not isinstance(annotations, Sequence):
            raise LocalOcrValidationError("local OCR adapter returned invalid annotations")
        lines: list[str] = []
        for annotation in annotations:
            if (
                isinstance(annotation, (str, bytes))
                or not isinstance(annotation, Sequence)
                or len(annotation) < 1
                or not isinstance(annotation[0], str)
            ):
                raise LocalOcrValidationError("local OCR adapter returned invalid annotations")
            lines.append(annotation[0])
        return tuple(lines)


@dataclass(frozen=True, slots=True)
class LocalOcrOrigin:
    """Fixed instruction-origin classification for OCR-recognized text."""

    origin_class: str = LOCAL_OCR_ORIGIN_CLASS
    actor_type: str = LOCAL_OCR_ACTOR_TYPE
    acquisition_method: str = LOCAL_OCR_ACQUISITION_METHOD
    authority_class: str = LOCAL_OCR_AUTHORITY_CLASS

    def to_dict(self) -> dict[str, str]:
        return {
            "origin_class": self.origin_class,
            "actor_type": self.actor_type,
            "acquisition_method": self.acquisition_method,
            "authority_class": self.authority_class,
        }


@dataclass(frozen=True, slots=True)
class LocalOcrLine:
    """One ordered bounded line returned by the OCR adapter."""

    line_number: int
    text: str

    @property
    def character_count(self) -> int:
        return len(self.text)

    def to_dict(self, *, include_text: bool) -> dict[str, object]:
        payload: dict[str, object] = {
            "line_number": self.line_number,
            "character_count": self.character_count,
        }
        if include_text:
            payload["text"] = self.text
        return payload


@dataclass(frozen=True, slots=True)
class LocalOcrExtraction:
    """Deterministic non-persistent OCR result for one selected image."""

    adapter_id: str
    adapter_version: str
    source_byte_count: int
    source_sha256: str
    image_format: str
    width: int
    height: int
    lines: tuple[LocalOcrLine, ...]
    origin: LocalOcrOrigin = LocalOcrOrigin()

    @property
    def pixel_count(self) -> int:
        return self.width * self.height

    @property
    def line_count(self) -> int:
        return len(self.lines)

    @property
    def aggregate_character_count(self) -> int:
        return sum(line.character_count for line in self.lines)

    @property
    def empty_text(self) -> bool:
        return not any(line.text.strip() for line in self.lines)

    def to_dict(self, *, include_text: bool = True) -> dict[str, object]:
        return {
            "schema_version": LOCAL_OCR_REPORT_SCHEMA_VERSION,
            "adapter_id": self.adapter_id,
            "adapter_version": self.adapter_version,
            "source_byte_count": self.source_byte_count,
            "source_sha256": self.source_sha256,
            "image_format": self.image_format,
            "width": self.width,
            "height": self.height,
            "pixel_count": self.pixel_count,
            "line_count": self.line_count,
            "aggregate_character_count": self.aggregate_character_count,
            "empty_text": self.empty_text,
            "lines": [line.to_dict(include_text=include_text) for line in self.lines],
            "origin": self.origin.to_dict(),
            "source_persisted": False,
            "output_persisted": False,
            "source_overwritten": False,
            "workspace_mutated": False,
            "state_mutated": False,
            "artifact_mutated": False,
            "audit_mutated": False,
            "index_mutated": False,
            "context_injected": False,
            "model_execution_used": False,
            "process_launch_used": False,
            "network_access_used": False,
            "cloud_access_used": False,
            "automatic_download_used": False,
        }


@dataclass(frozen=True, slots=True)
class _FileState:
    device: int
    inode: int
    size: int
    modified_ns: int


@dataclass(frozen=True, slots=True)
class _ImageInfo:
    image_format: str
    width: int
    height: int
    animated: bool = False


def extract_local_image_ocr(
    path: Path,
    *,
    adapter: OcrAdapter | None = None,
) -> LocalOcrExtraction:
    """Recognize bounded image text without persistence, subprocesses, or network access."""

    source_bytes, image_info = _read_image_source(path)
    _validate_image_info(image_info)
    active_adapter = adapter or OcrmacAdapter.load()
    try:
        recognized = active_adapter.recognize(source_bytes)
    except LocalOcrError:
        raise
    except Exception as exc:
        raise LocalOcrValidationError("local OCR recognition failed") from exc

    if isinstance(recognized, (str, bytes)) or not isinstance(recognized, Sequence):
        raise LocalOcrValidationError("local OCR adapter returned invalid recognized text")
    if len(recognized) > _MAX_RECOGNIZED_LINES:
        raise LocalOcrValidationError("local OCR recognized text exceeds the line limit")

    lines: list[LocalOcrLine] = []
    aggregate_characters = 0
    for line_number, text in enumerate(recognized, start=1):
        if not isinstance(text, str):
            raise LocalOcrValidationError("local OCR adapter returned invalid recognized text")
        _validate_recognized_line(text)
        if len(text) > _MAX_LINE_CHARACTERS:
            raise LocalOcrValidationError("local OCR line exceeds the character limit")
        aggregate_characters += len(text)
        if aggregate_characters > _MAX_AGGREGATE_CHARACTERS:
            raise LocalOcrValidationError(
                "local OCR text exceeds the aggregate character limit"
            )
        lines.append(LocalOcrLine(line_number=line_number, text=text))

    return LocalOcrExtraction(
        adapter_id=_bounded_adapter_field(active_adapter.adapter_id, "identifier"),
        adapter_version=_bounded_adapter_field(active_adapter.adapter_version, "version"),
        source_byte_count=len(source_bytes),
        source_sha256=hashlib.sha256(source_bytes).hexdigest(),
        image_format=image_info.image_format,
        width=image_info.width,
        height=image_info.height,
        lines=tuple(lines),
    )


def _read_image_source(path: Path) -> tuple[bytes, _ImageInfo]:
    selected = Path(path)
    extension = selected.suffix.casefold()
    if extension not in _ALLOWED_EXTENSIONS:
        raise LocalOcrValidationError("local OCR input must use a PNG or JPEG extension")
    before_path = _path_state(selected)
    if before_path.size > _MAX_SOURCE_BYTES:
        raise LocalOcrValidationError("local OCR image exceeds the maximum byte size")

    try:
        with selected.open("rb") as source:
            before_handle = _handle_state(source.fileno())
            if not _same_identity(before_path, before_handle):
                raise LocalOcrReadError("local OCR image changed before reading")
            raw = source.read(_MAX_SOURCE_BYTES + 1)
            after_handle = _handle_state(source.fileno())
    except LocalOcrError:
        raise
    except OSError as exc:
        raise LocalOcrReadError("local OCR image could not be read") from exc

    if len(raw) > _MAX_SOURCE_BYTES:
        raise LocalOcrValidationError("local OCR image exceeds the maximum byte size")
    after_path = _path_state(selected)
    if not _stable_read(before_path, before_handle, after_handle, after_path):
        raise LocalOcrReadError("local OCR image changed while being read")

    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        image_info = _inspect_png(raw)
    elif raw.startswith(b"\xff\xd8\xff"):
        image_info = _inspect_jpeg(raw)
    else:
        raise LocalOcrValidationError("local OCR image signature is invalid")

    expected_format = "png" if extension == ".png" else "jpeg"
    if image_info.image_format != expected_format:
        raise LocalOcrValidationError("local OCR image extension does not match its content")
    return raw, image_info


def _inspect_png(raw: bytes) -> _ImageInfo:
    offset = 8
    width: int | None = None
    height: int | None = None
    saw_idat = False
    animated = False
    chunk_number = 0
    while offset + 12 <= len(raw):
        length = int.from_bytes(raw[offset : offset + 4], "big")
        chunk_type = raw[offset + 4 : offset + 8]
        data_start = offset + 8
        data_end = data_start + length
        crc_end = data_end + 4
        if data_end < data_start or crc_end > len(raw):
            raise LocalOcrValidationError("local OCR PNG structure is invalid")
        data = raw[data_start:data_end]
        expected_crc = int.from_bytes(raw[data_end:crc_end], "big")
        actual_crc = binascii.crc32(chunk_type + data) & 0xFFFFFFFF
        if actual_crc != expected_crc:
            raise LocalOcrValidationError("local OCR PNG structure is invalid")
        chunk_number += 1
        if chunk_number == 1:
            if chunk_type != b"IHDR" or length != 13:
                raise LocalOcrValidationError("local OCR PNG structure is invalid")
            width = int.from_bytes(data[0:4], "big")
            height = int.from_bytes(data[4:8], "big")
        elif chunk_type == b"IHDR":
            raise LocalOcrValidationError("local OCR PNG structure is invalid")
        if chunk_type == b"acTL":
            animated = True
        elif chunk_type == b"IDAT":
            saw_idat = True
        elif chunk_type == b"IEND":
            if length != 0 or crc_end != len(raw) or width is None or height is None or not saw_idat:
                raise LocalOcrValidationError("local OCR PNG structure is invalid")
            return _ImageInfo(
                image_format="png",
                width=width,
                height=height,
                animated=animated,
            )
        offset = crc_end
    raise LocalOcrValidationError("local OCR PNG structure is invalid")


def _inspect_jpeg(raw: bytes) -> _ImageInfo:
    offset = 2
    width: int | None = None
    height: int | None = None
    sof_markers = frozenset(range(0xC0, 0xD0)) - {0xC4, 0xC8, 0xCC}
    while offset < len(raw):
        if raw[offset] != 0xFF:
            raise LocalOcrValidationError("local OCR JPEG structure is invalid")
        while offset < len(raw) and raw[offset] == 0xFF:
            offset += 1
        if offset >= len(raw):
            break
        marker = raw[offset]
        offset += 1
        if marker == 0xD9:
            break
        if marker in {0x01, *range(0xD0, 0xD8)}:
            continue
        if marker == 0xDA:
            if width is None or height is None or raw.rfind(b"\xff\xd9") < offset:
                raise LocalOcrValidationError("local OCR JPEG structure is invalid")
            return _ImageInfo(image_format="jpeg", width=width, height=height)
        if offset + 2 > len(raw):
            raise LocalOcrValidationError("local OCR JPEG structure is invalid")
        segment_length = int.from_bytes(raw[offset : offset + 2], "big")
        if segment_length < 2 or offset + segment_length > len(raw):
            raise LocalOcrValidationError("local OCR JPEG structure is invalid")
        if marker in sof_markers:
            if segment_length < 7:
                raise LocalOcrValidationError("local OCR JPEG structure is invalid")
            segment = raw[offset + 2 : offset + segment_length]
            height = int.from_bytes(segment[1:3], "big")
            width = int.from_bytes(segment[3:5], "big")
        offset += segment_length
    raise LocalOcrValidationError("local OCR JPEG structure is invalid")


def _validate_image_info(image_info: _ImageInfo) -> None:
    if image_info.animated:
        raise LocalOcrValidationError("animated or multi-frame local OCR images are not supported")
    if image_info.width < 1 or image_info.height < 1:
        raise LocalOcrValidationError("local OCR image dimensions are invalid")
    if image_info.width > _MAX_IMAGE_WIDTH or image_info.height > _MAX_IMAGE_HEIGHT:
        raise LocalOcrValidationError("local OCR image exceeds the dimension limit")
    if image_info.width * image_info.height > _MAX_IMAGE_PIXELS:
        raise LocalOcrValidationError("local OCR image exceeds the pixel limit")


def _bounded_adapter_field(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 80:
        raise LocalOcrValidationError(f"local OCR adapter {field} is invalid")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise LocalOcrValidationError(f"local OCR adapter {field} is invalid")
    return value


def _validate_recognized_line(text: str) -> None:
    for character in text:
        codepoint = ord(character)
        if character in {"\n", "\r"} or codepoint == 0 or codepoint == 127:
            raise LocalOcrValidationError(
                "local OCR recognized line contains a prohibited control character"
            )
        if codepoint < 32 and character != "\t":
            raise LocalOcrValidationError(
                "local OCR recognized line contains a prohibited control character"
            )


def _required_callable(module: ModuleType, name: str, description: str) -> Callable[..., object]:
    value = getattr(module, name, None)
    if not callable(value):
        raise LocalOcrAdapterUnavailableError(
            f"optional local OCR adapter does not expose {description}"
        )
    return cast(Callable[..., object], value)


def _path_state(path: Path) -> _FileState:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise LocalOcrReadError("local OCR image is unavailable") from exc
    if stat.S_ISLNK(metadata.st_mode):
        raise LocalOcrValidationError("local OCR image symlinks are not supported")
    if not stat.S_ISREG(metadata.st_mode):
        raise LocalOcrValidationError("local OCR image must be a regular file")
    return _state_from_stat(metadata)


def _handle_state(file_descriptor: int) -> _FileState:
    try:
        metadata = os.fstat(file_descriptor)
    except OSError as exc:
        raise LocalOcrReadError("local OCR image state could not be verified") from exc
    if not stat.S_ISREG(metadata.st_mode):
        raise LocalOcrValidationError("local OCR image must be a regular file")
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
    "LOCAL_OCR_ACQUISITION_METHOD",
    "LOCAL_OCR_ACTOR_TYPE",
    "LOCAL_OCR_AUTHORITY_CLASS",
    "LOCAL_OCR_ORIGIN_CLASS",
    "LOCAL_OCR_REPORT_SCHEMA_VERSION",
    "LocalOcrAdapterUnavailableError",
    "LocalOcrError",
    "LocalOcrExtraction",
    "LocalOcrLine",
    "LocalOcrOrigin",
    "LocalOcrReadError",
    "LocalOcrValidationError",
    "OcrAdapter",
    "OcrmacAdapter",
    "extract_local_image_ocr",
]
