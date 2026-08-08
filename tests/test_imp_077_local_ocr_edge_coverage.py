"""Focused edge coverage for the bounded IMP-077 OCR boundary."""

from __future__ import annotations

import binascii
import importlib
import os
import stat
import zlib
from pathlib import Path
from types import ModuleType

import pytest
from pytest import MonkeyPatch
from typer.testing import CliRunner

from doll import local_ocr as local_ocr_module
from doll import local_ocr_cli as local_ocr_cli_module
from doll.cli import app
from doll.local_ocr import (
    LocalOcrAdapterUnavailableError,
    LocalOcrExtraction,
    LocalOcrOrigin,
    LocalOcrReadError,
    LocalOcrValidationError,
    OcrmacAdapter,
    extract_local_image_ocr,
)

runner = CliRunner()


def _chunk(chunk_type: bytes, data: bytes) -> bytes:
    crc = binascii.crc32(chunk_type + data) & 0xFFFFFFFF
    return len(data).to_bytes(4, "big") + chunk_type + data + crc.to_bytes(4, "big")


def _png(*, width: int = 2, height: int = 2) -> bytes:
    ihdr = width.to_bytes(4, "big") + height.to_bytes(4, "big") + bytes((8, 2, 0, 0, 0))
    row = b"\x00" + (b"\xff\xff\xff" * width)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", zlib.compress(row * height))
        + _chunk(b"IEND", b"")
    )


def test_ocrmac_recognize_import_and_runtime_failures(monkeypatch: MonkeyPatch) -> None:
    adapter = OcrmacAdapter(adapter_version="1.0.1")
    original_import = importlib.import_module

    def missing(name: str) -> ModuleType:
        if name == "ocrmac.ocrmac":
            raise ModuleNotFoundError(name)
        return original_import(name)

    monkeypatch.setattr(importlib, "import_module", missing)
    with pytest.raises(LocalOcrAdapterUnavailableError, match="not installed"):
        adapter.recognize(_png())

    ocr_module = ModuleType("ocrmac.ocrmac")
    image_module = ModuleType("PIL.Image")

    class FakeImage:
        def load(self) -> object:
            return None

        def copy(self) -> object:
            return object()

        def close(self) -> None:
            return None

    class RuntimeFailure:
        def recognize(self) -> object:
            raise ValueError("synthetic engine failure")

    image_module.__dict__["open"] = lambda source: FakeImage()
    ocr_module.__dict__["OCR"] = lambda image, **kwargs: RuntimeFailure()

    def fake_import(name: str) -> ModuleType:
        return ocr_module if name == "ocrmac.ocrmac" else image_module

    monkeypatch.setattr(importlib, "import_module", fake_import)
    with pytest.raises(LocalOcrValidationError, match="recognition failed"):
        adapter.recognize(_png())

    class BoundedFailure:
        def recognize(self) -> object:
            raise LocalOcrValidationError("bounded failure")

    ocr_module.__dict__["OCR"] = lambda image, **kwargs: BoundedFailure()
    with pytest.raises(LocalOcrValidationError, match="bounded failure"):
        adapter.recognize(_png())


def test_png_parser_rejects_additional_structural_failures() -> None:
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = (2).to_bytes(4, "big") + (2).to_bytes(4, "big") + bytes((8, 2, 0, 0, 0))

    invalid_documents = (
        signature + _chunk(b"IDAT", b"x") + _chunk(b"IEND", b""),
        signature + _chunk(b"IHDR", ihdr) + _chunk(b"IHDR", ihdr),
        signature + _chunk(b"IHDR", ihdr) + _chunk(b"IEND", b""),
        _png() + b"trailing",
    )
    for raw in invalid_documents:
        with pytest.raises(LocalOcrValidationError, match="PNG structure"):
            local_ocr_module._inspect_png(raw)


def test_jpeg_parser_rejects_additional_structural_failures() -> None:
    invalid_documents = (
        b"\xff\xd8x",
        b"\xff\xd8\xff",
        b"\xff\xd8\xff\xd9",
        b"\xff\xd8\xff\xd0\xff\xd9",
        b"\xff\xd8\xff\xda\x00\x02",
        b"\xff\xd8\xff\xe0\x00",
        b"\xff\xd8\xff\xe0\x00\x01",
        b"\xff\xd8\xff\xc0\x00\x06\x00\x00\x00\x00",
    )
    for raw in invalid_documents:
        with pytest.raises(LocalOcrValidationError, match="JPEG structure"):
            local_ocr_module._inspect_jpeg(raw)


def test_dimension_handle_and_identity_edge_failures(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    with pytest.raises(LocalOcrValidationError, match="dimensions"):
        local_ocr_module._validate_image_info(local_ocr_module._ImageInfo("png", 0, 1))

    monkeypatch.setattr(local_ocr_module, "_MAX_IMAGE_HEIGHT", 1)
    with pytest.raises(LocalOcrValidationError, match="dimension limit"):
        local_ocr_module._validate_image_info(local_ocr_module._ImageInfo("png", 1, 2))

    def failed_fstat(file_descriptor: int) -> os.stat_result:
        raise OSError(file_descriptor)

    monkeypatch.setattr(os, "fstat", failed_fstat)
    with pytest.raises(LocalOcrReadError, match="state could not be verified"):
        local_ocr_module._handle_state(1)

    monkeypatch.setattr(
        os,
        "fstat",
        lambda file_descriptor: os.stat_result((stat.S_IFDIR, 0, 0, 0, 0, 0, 0, 0, 0, 0)),
    )
    with pytest.raises(LocalOcrValidationError, match="regular file"):
        local_ocr_module._handle_state(1)

    monkeypatch.undo()
    source = tmp_path / "identity.png"
    source.write_bytes(_png())
    monkeypatch.setattr(local_ocr_module, "_same_identity", lambda left, right: False)
    with pytest.raises(LocalOcrReadError, match="changed before reading"):
        extract_local_image_ocr(source)


def test_cli_empty_result_and_human_failure_are_bounded(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    source = tmp_path / "source.png"
    source.write_bytes(_png())
    empty = LocalOcrExtraction(
        adapter_id="synthetic-ocr",
        adapter_version="1.0",
        source_byte_count=len(source.read_bytes()),
        source_sha256="a" * 64,
        image_format="png",
        width=2,
        height=2,
        lines=(),
        origin=LocalOcrOrigin(),
    )
    monkeypatch.setattr(local_ocr_cli_module, "extract_local_image_ocr", lambda path: empty)

    completed = runner.invoke(app, ["ocr", "extract", str(source)])

    assert completed.exit_code == 0
    assert "No text recognized." in completed.stdout

    def reject(path: Path) -> LocalOcrExtraction:
        raise LocalOcrReadError("private detail")

    monkeypatch.setattr(local_ocr_cli_module, "extract_local_image_ocr", reject)
    failed = runner.invoke(app, ["ocr", "extract", str(source)])

    assert failed.exit_code == 2
    assert "LocalOcrReadError" in failed.stderr
    assert "private detail" not in failed.stderr
    assert str(source) not in failed.stderr
