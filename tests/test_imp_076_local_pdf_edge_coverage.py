"""Additional cross-platform edge coverage for IMP-076 local PDF extraction."""

from __future__ import annotations

import importlib
import os
from pathlib import Path
from typing import cast

import pytest
from pytest import MonkeyPatch

from doll import local_pdf as local_pdf_module
from doll.local_pdf import (
    LocalPdfAdapterUnavailableError,
    LocalPdfReadError,
    LocalPdfValidationError,
    PdfTextAdapter,
    PypdfTextAdapter,
    extract_local_pdf_text,
)


class _EncryptionStateFailureReader:
    @property
    def is_encrypted(self) -> bool:
        raise ValueError("synthetic encryption-state failure")

    @property
    def pages(self) -> tuple[object, ...]:
        raise AssertionError("page inventory must not be read")


class _EncryptionStateFailureAdapter:
    adapter_id = "synthetic-pdf"
    adapter_version = "1.0"

    def open_reader(self, source_bytes: bytes) -> _EncryptionStateFailureReader:
        assert source_bytes.startswith(b"%PDF-")
        return _EncryptionStateFailureReader()


class _LocalErrorAdapter:
    adapter_id = "synthetic-pdf"
    adapter_version = "1.0"

    def open_reader(self, source_bytes: bytes) -> object:
        assert source_bytes.startswith(b"%PDF-")
        raise LocalPdfReadError("synthetic adapter read failure")


def _source(tmp_path: Path) -> Path:
    source = tmp_path / "document.pdf"
    source.write_bytes(b"%PDF-1.4\nsynthetic")
    return source


def test_pypdf_open_reader_reports_dependency_removed_after_load(
    monkeypatch: MonkeyPatch,
) -> None:
    adapter = PypdfTextAdapter(adapter_version="6.14.2")
    original_import = importlib.import_module

    def missing(name: str) -> object:
        if name == "pypdf":
            raise ModuleNotFoundError(name)
        return original_import(name)

    monkeypatch.setattr(importlib, "import_module", missing)

    with pytest.raises(LocalPdfAdapterUnavailableError, match="not installed"):
        adapter.open_reader(b"%PDF-1.4\n")


def test_adapter_local_pdf_error_is_preserved(tmp_path: Path) -> None:
    adapter = cast(PdfTextAdapter, _LocalErrorAdapter())

    with pytest.raises(LocalPdfReadError, match="synthetic adapter read failure"):
        extract_local_pdf_text(_source(tmp_path), adapter=adapter)


def test_encryption_state_failure_precedes_page_inventory(tmp_path: Path) -> None:
    adapter = cast(PdfTextAdapter, _EncryptionStateFailureAdapter())

    with pytest.raises(LocalPdfValidationError, match="encryption state"):
        extract_local_pdf_text(_source(tmp_path), adapter=adapter)


def test_file_handle_state_verification_failure_is_fail_closed(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    def fail_fstat(file_descriptor: int) -> object:
        del file_descriptor
        raise OSError("synthetic fstat failure")

    monkeypatch.setattr(os, "fstat", fail_fstat)
    adapter = cast(PdfTextAdapter, _LocalErrorAdapter())

    with pytest.raises(LocalPdfReadError, match="state could not be verified"):
        extract_local_pdf_text(_source(tmp_path), adapter=adapter)


def test_identity_change_before_read_is_fail_closed(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(local_pdf_module, "_same_identity", lambda left, right: False)
    adapter = cast(PdfTextAdapter, _LocalErrorAdapter())

    with pytest.raises(LocalPdfReadError, match="changed before reading"):
        extract_local_pdf_text(_source(tmp_path), adapter=adapter)
