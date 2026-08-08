"""Acceptance coverage for IMP-077 optional local raster-image OCR."""

from __future__ import annotations

import binascii
import hashlib
import importlib
import importlib.metadata
import json
import sys
import zlib
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import cast

import pytest
from pytest import MonkeyPatch
from typer.testing import CliRunner

from doll import local_ocr as local_ocr_module
from doll import local_ocr_cli as local_ocr_cli_module
from doll.cli import app
from doll.local_ocr import (
    LOCAL_OCR_ACQUISITION_METHOD,
    LOCAL_OCR_ACTOR_TYPE,
    LOCAL_OCR_AUTHORITY_CLASS,
    LOCAL_OCR_ORIGIN_CLASS,
    LOCAL_OCR_REPORT_SCHEMA_VERSION,
    LocalOcrAdapterUnavailableError,
    LocalOcrExtraction,
    LocalOcrLine,
    LocalOcrOrigin,
    LocalOcrReadError,
    LocalOcrValidationError,
    OcrmacAdapter,
    extract_local_image_ocr,
)
from doll.state import initialize_state_repository
from doll.workspace import initialize_workspace

runner = CliRunner()


@dataclass(slots=True)
class _FakeAdapter:
    lines: object = ("Hello OCR",)
    failure: bool = False
    adapter_id: str = "synthetic-ocr"
    adapter_version: str = "1.0"

    def recognize(self, source_bytes: bytes) -> tuple[str, ...]:
        assert source_bytes.startswith((b"\x89PNG", b"\xff\xd8\xff"))
        if self.failure:
            raise ValueError("synthetic OCR failure")
        return cast(tuple[str, ...], self.lines)


def _chunk(chunk_type: bytes, data: bytes) -> bytes:
    crc = binascii.crc32(chunk_type + data) & 0xFFFFFFFF
    return len(data).to_bytes(4, "big") + chunk_type + data + crc.to_bytes(4, "big")


def _png_bytes(*, width: int = 120, height: int = 40, animated: bool = False) -> bytes:
    ihdr = width.to_bytes(4, "big") + height.to_bytes(4, "big") + bytes((8, 2, 0, 0, 0))
    chunks = [_chunk(b"IHDR", ihdr)]
    if animated:
        chunks.append(_chunk(b"acTL", (2).to_bytes(4, "big") + (0).to_bytes(4, "big")))
    scanline = b"\x00" + (b"\xff\xff\xff" * max(width, 1))
    chunks.append(_chunk(b"IDAT", zlib.compress(scanline * max(height, 1))))
    chunks.append(_chunk(b"IEND", b""))
    return b"\x89PNG\r\n\x1a\n" + b"".join(chunks)


def _jpeg_bytes(*, width: int = 120, height: int = 40) -> bytes:
    app0 = b"JFIF\x00" + b"\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    sof = b"\x08" + height.to_bytes(2, "big") + width.to_bytes(2, "big") + b"\x01\x01\x11\x00"
    sos = b"\x01\x01\x00\x00\x3f\x00"
    return (
        b"\xff\xd8"
        + b"\xff\xe0"
        + (len(app0) + 2).to_bytes(2, "big")
        + app0
        + b"\xff\xc0"
        + (len(sof) + 2).to_bytes(2, "big")
        + sof
        + b"\xff\xda"
        + (len(sos) + 2).to_bytes(2, "big")
        + sos
        + b"\x00\xff\xd9"
    )


def _source(tmp_path: Path, *, suffix: str = ".png", raw: bytes | None = None) -> Path:
    source = tmp_path / f"image{suffix}"
    source.write_bytes(raw if raw is not None else _png_bytes())
    return source


def _workspace_snapshot(root: Path) -> dict[str, tuple[int, bytes]]:
    return {
        path.relative_to(root).as_posix(): (path.stat().st_mtime_ns, path.read_bytes())
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_png_ocr_preserves_order_unicode_and_metadata(tmp_path: Path) -> None:
    source = _source(tmp_path)
    adapter = _FakeAdapter(("First line", "日本語のOCR", "Unicode café"))

    result = extract_local_image_ocr(source, adapter=adapter)

    assert result.adapter_id == "synthetic-ocr"
    assert result.adapter_version == "1.0"
    assert result.image_format == "png"
    assert (result.width, result.height, result.pixel_count) == (120, 40, 4_800)
    assert [line.text for line in result.lines] == ["First line", "日本語のOCR", "Unicode café"]
    assert result.line_count == 3
    assert result.aggregate_character_count == sum(len(line.text) for line in result.lines)
    assert result.empty_text is False
    raw = source.read_bytes()
    assert result.source_byte_count == len(raw)
    assert result.source_sha256 == hashlib.sha256(raw).hexdigest()
    assert result.origin.origin_class == LOCAL_OCR_ORIGIN_CLASS
    assert result.origin.actor_type == LOCAL_OCR_ACTOR_TYPE
    assert result.origin.acquisition_method == LOCAL_OCR_ACQUISITION_METHOD
    assert result.origin.authority_class == LOCAL_OCR_AUTHORITY_CLASS
    payload = result.to_dict()
    assert payload["schema_version"] == LOCAL_OCR_REPORT_SCHEMA_VERSION
    assert payload["source_persisted"] is False
    assert payload["output_persisted"] is False
    assert payload["process_launch_used"] is False
    assert payload["network_access_used"] is False
    assert payload["automatic_download_used"] is False


def test_jpeg_and_metadata_only_are_deterministic(tmp_path: Path) -> None:
    source = _source(tmp_path, suffix=".jpeg", raw=_jpeg_bytes(width=64, height=32))
    result = extract_local_image_ocr(source, adapter=_FakeAdapter(("jpeg",)))
    metadata = result.to_dict(include_text=False)

    assert result.image_format == "jpeg"
    assert (result.width, result.height) == (64, 32)
    assert metadata["lines"] == [{"line_number": 1, "character_count": 4}]


def test_empty_ocr_result_is_success(tmp_path: Path) -> None:
    source = _source(tmp_path)

    no_lines = extract_local_image_ocr(source, adapter=_FakeAdapter(()))
    blank_line = extract_local_image_ocr(source, adapter=_FakeAdapter(("   ",)))

    assert no_lines.empty_text is True
    assert no_lines.line_count == 0
    assert blank_line.empty_text is True


def test_rejects_bad_extension_signature_mismatch_and_structures(tmp_path: Path) -> None:
    unsupported = _source(tmp_path, suffix=".gif")
    with pytest.raises(LocalOcrValidationError, match="extension"):
        extract_local_image_ocr(unsupported, adapter=_FakeAdapter())

    invalid = _source(tmp_path, raw=b"not an image")
    with pytest.raises(LocalOcrValidationError, match="signature"):
        extract_local_image_ocr(invalid, adapter=_FakeAdapter())

    mismatch = _source(tmp_path, suffix=".jpg", raw=_png_bytes())
    with pytest.raises(LocalOcrValidationError, match="does not match"):
        extract_local_image_ocr(mismatch, adapter=_FakeAdapter())

    bad_crc = bytearray(_png_bytes())
    bad_crc[29] ^= 0x01
    with pytest.raises(LocalOcrValidationError, match="PNG structure"):
        extract_local_image_ocr(_source(tmp_path, raw=bytes(bad_crc)), adapter=_FakeAdapter())

    truncated_png = _source(tmp_path, raw=b"\x89PNG\r\n\x1a\n" + b"\x00" * 12)
    with pytest.raises(LocalOcrValidationError, match="PNG structure"):
        extract_local_image_ocr(truncated_png, adapter=_FakeAdapter())

    truncated_jpeg = _source(tmp_path, suffix=".jpg", raw=b"\xff\xd8\xff\xe0\x00")
    with pytest.raises(LocalOcrValidationError, match="JPEG structure"):
        extract_local_image_ocr(truncated_jpeg, adapter=_FakeAdapter())


def test_rejects_animated_dimension_pixel_and_source_byte_limits(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    animated = _source(tmp_path, raw=_png_bytes(animated=True))
    with pytest.raises(LocalOcrValidationError, match="animated"):
        extract_local_image_ocr(animated, adapter=_FakeAdapter())

    monkeypatch.setattr(local_ocr_module, "_MAX_IMAGE_WIDTH", 10)
    wide = _source(tmp_path, raw=_png_bytes(width=11, height=1))
    with pytest.raises(LocalOcrValidationError, match="dimension"):
        extract_local_image_ocr(wide, adapter=_FakeAdapter())

    monkeypatch.setattr(local_ocr_module, "_MAX_IMAGE_WIDTH", 10_000)
    monkeypatch.setattr(local_ocr_module, "_MAX_IMAGE_PIXELS", 10)
    pixels = _source(tmp_path, raw=_png_bytes(width=4, height=3))
    with pytest.raises(LocalOcrValidationError, match="pixel"):
        extract_local_image_ocr(pixels, adapter=_FakeAdapter())

    monkeypatch.setattr(local_ocr_module, "_MAX_SOURCE_BYTES", 16)
    oversized = _source(tmp_path, raw=_png_bytes(width=1, height=1))
    with pytest.raises(LocalOcrValidationError, match="maximum byte size"):
        extract_local_image_ocr(oversized, adapter=_FakeAdapter())


def test_rejects_missing_directory_symlink_and_changed_source(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    with pytest.raises(LocalOcrReadError, match="unavailable"):
        extract_local_image_ocr(tmp_path / "missing.png", adapter=_FakeAdapter())

    directory = tmp_path / "folder.png"
    directory.mkdir()
    with pytest.raises(LocalOcrValidationError, match="regular file"):
        extract_local_image_ocr(directory, adapter=_FakeAdapter())

    target = _source(tmp_path)
    link = tmp_path / "link.png"
    try:
        link.symlink_to(target)
    except OSError:
        pass
    else:
        with pytest.raises(LocalOcrValidationError, match="symlinks"):
            extract_local_image_ocr(link, adapter=_FakeAdapter())

    monkeypatch.setattr(local_ocr_module, "_stable_read", lambda *args: False)
    with pytest.raises(LocalOcrReadError, match="changed while"):
        extract_local_image_ocr(target, adapter=_FakeAdapter())


def test_rejects_adapter_failure_invalid_output_metadata_and_text_limits(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    source = _source(tmp_path)

    with pytest.raises(LocalOcrValidationError, match="recognition failed"):
        extract_local_image_ocr(source, adapter=_FakeAdapter(failure=True))

    with pytest.raises(LocalOcrValidationError, match="invalid recognized text"):
        extract_local_image_ocr(source, adapter=_FakeAdapter("not-a-sequence"))
    with pytest.raises(LocalOcrValidationError, match="invalid recognized text"):
        extract_local_image_ocr(source, adapter=_FakeAdapter((cast(str, 123),)))

    for adapter in (
        _FakeAdapter(adapter_id=""),
        _FakeAdapter(adapter_version="x" * 81),
        _FakeAdapter(adapter_id="bad\x01id"),
    ):
        with pytest.raises(LocalOcrValidationError, match="adapter"):
            extract_local_image_ocr(source, adapter=adapter)

    monkeypatch.setattr(local_ocr_module, "_MAX_RECOGNIZED_LINES", 1)
    with pytest.raises(LocalOcrValidationError, match="line limit"):
        extract_local_image_ocr(source, adapter=_FakeAdapter(("one", "two")))

    monkeypatch.setattr(local_ocr_module, "_MAX_RECOGNIZED_LINES", 1_000)
    monkeypatch.setattr(local_ocr_module, "_MAX_LINE_CHARACTERS", 3)
    with pytest.raises(LocalOcrValidationError, match="line exceeds"):
        extract_local_image_ocr(source, adapter=_FakeAdapter(("four",)))

    monkeypatch.setattr(local_ocr_module, "_MAX_LINE_CHARACTERS", 20_000)
    monkeypatch.setattr(local_ocr_module, "_MAX_AGGREGATE_CHARACTERS", 5)
    with pytest.raises(LocalOcrValidationError, match="aggregate"):
        extract_local_image_ocr(source, adapter=_FakeAdapter(("abc", "def")))

    for text in ("a\n", "a\r", "a\x00b", "a\x01b", "a\x7fb"):
        with pytest.raises(LocalOcrValidationError, match="control"):
            extract_local_image_ocr(source, adapter=_FakeAdapter((text,)))


def test_optional_adapter_absence_is_clean_and_help_does_not_load_it(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    source = _source(tmp_path)
    original_import = importlib.import_module
    monkeypatch.setattr(local_ocr_module.sys, "platform", "darwin")

    def missing(name: str) -> ModuleType:
        if name.startswith("ocrmac") or name == "PIL.Image":
            raise ModuleNotFoundError(name)
        return original_import(name)

    monkeypatch.setattr(importlib, "import_module", missing)

    help_result = runner.invoke(app, ["ocr", "--help"])
    command_result = runner.invoke(app, ["ocr", "extract", str(source), "--json"])

    assert help_result.exit_code == 0
    assert "raster image" in help_result.stdout
    assert command_result.exit_code == 2
    payload = json.loads(command_result.stdout)
    assert payload["error_class"] == "LocalOcrAdapterUnavailableError"
    assert str(source) not in command_result.stdout


def test_ocrmac_adapter_load_and_recognize_contract(monkeypatch: MonkeyPatch) -> None:
    original_platform = sys.platform
    monkeypatch.setattr(local_ocr_module.sys, "platform", "linux")
    with pytest.raises(LocalOcrAdapterUnavailableError, match="platform"):
        OcrmacAdapter.load()

    monkeypatch.setattr(local_ocr_module.sys, "platform", "darwin")
    ocr_module = ModuleType("ocrmac.ocrmac")
    image_module = ModuleType("PIL.Image")

    class FakeImage:
        def load(self) -> object:
            return None

        def copy(self) -> object:
            return object()

        def close(self) -> None:
            return None

    class FakeEngine:
        def recognize(self) -> tuple[object, ...]:
            return (("Alpha", 0.9, (0, 0, 1, 1)), ("日本語", 0.8, (0, 0, 1, 1)))

    image_module.__dict__["open"] = lambda source: FakeImage()
    ocr_module.__dict__["OCR"] = lambda image, **kwargs: FakeEngine()

    def fake_import(name: str) -> ModuleType:
        if name == "ocrmac.ocrmac":
            return ocr_module
        if name == "PIL.Image":
            return image_module
        raise ModuleNotFoundError(name)

    monkeypatch.setattr(importlib, "import_module", fake_import)
    monkeypatch.setattr(importlib.metadata, "version", lambda name: "1.0.1")

    adapter = OcrmacAdapter.load()
    assert adapter.adapter_version == "1.0.1"
    assert adapter.recognize(_png_bytes()) == ("Alpha", "日本語")

    monkeypatch.setattr(importlib.metadata, "version", lambda name: "")
    with pytest.raises(LocalOcrAdapterUnavailableError, match="version"):
        OcrmacAdapter.load()
    monkeypatch.setattr(local_ocr_module.sys, "platform", original_platform)


def test_ocrmac_adapter_rejects_missing_callables_and_bad_annotations(
    monkeypatch: MonkeyPatch,
) -> None:
    ocr_module = ModuleType("ocrmac.ocrmac")
    image_module = ModuleType("PIL.Image")

    def fake_import(name: str) -> ModuleType:
        return ocr_module if name == "ocrmac.ocrmac" else image_module

    monkeypatch.setattr(importlib, "import_module", fake_import)
    adapter = OcrmacAdapter(adapter_version="1.0.1")

    with pytest.raises(LocalOcrAdapterUnavailableError, match="decoder"):
        adapter.recognize(_png_bytes())

    class FakeImage:
        def load(self) -> object:
            return None

        def copy(self) -> object:
            return object()

        def close(self) -> None:
            return None

    image_module.__dict__["open"] = lambda source: FakeImage()
    with pytest.raises(LocalOcrAdapterUnavailableError, match="OCR class"):
        adapter.recognize(_png_bytes())

    class BadEngine:
        def recognize(self) -> object:
            return "bad"

    ocr_module.__dict__["OCR"] = lambda image, **kwargs: BadEngine()
    with pytest.raises(LocalOcrValidationError, match="annotations"):
        adapter.recognize(_png_bytes())

    class BadAnnotationEngine:
        def recognize(self) -> tuple[object, ...]:
            return ((123, 0.9),)

    ocr_module.__dict__["OCR"] = lambda image, **kwargs: BadAnnotationEngine()
    with pytest.raises(LocalOcrValidationError, match="annotations"):
        adapter.recognize(_png_bytes())


def test_cli_success_metadata_only_and_path_free_failure(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    source = _source(tmp_path)
    synthetic = LocalOcrExtraction(
        adapter_id="synthetic-ocr",
        adapter_version="1.0",
        source_byte_count=10,
        source_sha256="a" * 64,
        image_format="png",
        width=100,
        height=50,
        lines=(LocalOcrLine(1, "Hello"), LocalOcrLine(2, "日本語")),
        origin=LocalOcrOrigin(),
    )
    monkeypatch.setattr(local_ocr_cli_module, "extract_local_image_ocr", lambda path: synthetic)

    human = runner.invoke(app, ["ocr", "extract", str(source)])
    metadata = runner.invoke(
        app,
        ["ocr", "extract", str(source), "--json", "--metadata-only"],
    )

    assert human.exit_code == 0
    assert "OCR extraction: lines=2" in human.stdout
    assert "Hello" in human.stdout
    assert "日本語" in human.stdout
    assert metadata.exit_code == 0
    payload = json.loads(metadata.stdout)
    assert payload["lines"] == [
        {"character_count": 5, "line_number": 1},
        {"character_count": 3, "line_number": 2},
    ]
    assert str(source) not in metadata.stdout

    def reject(path: Path) -> LocalOcrExtraction:
        raise LocalOcrValidationError("private path must not be rendered")

    monkeypatch.setattr(local_ocr_cli_module, "extract_local_image_ocr", reject)
    failed = runner.invoke(app, ["ocr", "extract", str(source), "--json"])
    assert failed.exit_code == 2
    assert str(source) not in failed.stdout
    assert "private path" not in failed.stdout


def test_source_workspace_and_state_remain_unchanged(tmp_path: Path) -> None:
    initialized = initialize_workspace(tmp_path / "workspace")
    with initialize_state_repository(initialized.root):
        pass
    source = _source(tmp_path)
    source_before = source.read_bytes()
    workspace_before = _workspace_snapshot(initialized.root)

    result = extract_local_image_ocr(source, adapter=_FakeAdapter(("safe",)))

    assert result.lines[0].text == "safe"
    assert source.read_bytes() == source_before
    assert _workspace_snapshot(initialized.root) == workspace_before
