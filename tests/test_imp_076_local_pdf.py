"""Acceptance coverage for IMP-076 optional local PDF text extraction."""

from __future__ import annotations

import hashlib
import importlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import pytest
from pytest import MonkeyPatch
from typer.testing import CliRunner

from doll import local_pdf as local_pdf_module
from doll.cli import app
from doll.local_pdf import (
    LOCAL_PDF_ACQUISITION_METHOD,
    LOCAL_PDF_ACTOR_TYPE,
    LOCAL_PDF_AUTHORITY_CLASS,
    LOCAL_PDF_ORIGIN_CLASS,
    LOCAL_PDF_REPORT_SCHEMA_VERSION,
    LocalPdfAdapterUnavailableError,
    LocalPdfReadError,
    LocalPdfValidationError,
    PypdfTextAdapter,
    extract_local_pdf_text,
)
from doll.state import initialize_state_repository
from doll.workspace import initialize_workspace

runner = CliRunner()


@dataclass(slots=True)
class _FakePage:
    text: object
    failure: bool = False

    def extract_text(self) -> str | None:
        if self.failure:
            raise ValueError("synthetic extraction failure")
        return cast(str | None, self.text)


@dataclass(slots=True)
class _FakeReader:
    page_texts: tuple[object, ...]
    is_encrypted: bool = False
    inventory_failure: bool = False

    @property
    def pages(self) -> tuple[_FakePage, ...]:
        if self.inventory_failure:
            raise ValueError("synthetic inventory failure")
        return tuple(_FakePage(text) for text in self.page_texts)


@dataclass(slots=True)
class _FakeAdapter:
    page_texts: tuple[object, ...]
    encrypted: bool = False
    inventory_failure: bool = False
    open_failure: bool = False
    adapter_id: str = "synthetic-pdf"
    adapter_version: str = "1.0"

    def open_reader(self, source_bytes: bytes) -> _FakeReader:
        assert source_bytes.startswith(b"%PDF-")
        if self.open_failure:
            raise ValueError("synthetic open failure")
        return _FakeReader(
            page_texts=self.page_texts,
            is_encrypted=self.encrypted,
            inventory_failure=self.inventory_failure,
        )


def _workspace_snapshot(root: Path) -> dict[str, tuple[int, bytes]]:
    return {
        path.relative_to(root).as_posix(): (path.stat().st_mtime_ns, path.read_bytes())
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _escape_pdf_text(value: str) -> bytes:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)").encode()


def _pdf_bytes(page_texts: tuple[str | None, ...]) -> bytes:
    if not page_texts:
        raise ValueError("fixture requires at least one page")
    font_object_number = 3 + (2 * len(page_texts))
    object_bodies: list[bytes] = []
    object_bodies.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    page_references = " ".join(f"{3 + (2 * index)} 0 R" for index in range(len(page_texts)))
    object_bodies.append(
        f"<< /Type /Pages /Kids [{page_references}] /Count {len(page_texts)} >>".encode()
    )
    for index, text in enumerate(page_texts):
        page_number = 3 + (2 * index)
        content_number = page_number + 1
        object_bodies.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                f"/Resources << /Font << /F1 {font_object_number} 0 R >> >> "
                f"/Contents {content_number} 0 R >>"
            ).encode()
        )
        if text is None:
            stream = b""
        else:
            stream = b"BT\n/F1 12 Tf\n72 720 Td\n(" + _escape_pdf_text(text) + b") Tj\nET"
        object_bodies.append(
            f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream"
        )
    object_bodies.append(
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"
    )

    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for object_number, body in enumerate(object_bodies, start=1):
        offsets.append(len(output))
        output.extend(f"{object_number} 0 obj\n".encode())
        output.extend(body)
        output.extend(b"\nendobj\n")
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(object_bodies) + 1}\n".encode())
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(
        (
            f"trailer\n<< /Size {len(object_bodies) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode()
    )
    return bytes(output)


def _source(tmp_path: Path, *, pages: tuple[str | None, ...] = ("Hello PDF",)) -> Path:
    source = tmp_path / "document.pdf"
    source.write_bytes(_pdf_bytes(pages))
    return source


def test_real_pypdf_adapter_extracts_text_and_reports_metadata(tmp_path: Path) -> None:
    source = _source(tmp_path, pages=("Hello PDF", None, "Page Three"))

    result = extract_local_pdf_text(source)

    assert result.adapter_id == "pypdf"
    assert result.adapter_version
    assert result.document_page_count == 3
    assert result.selected_page_numbers == (1, 2, 3)
    assert result.selected_page_count == 3
    assert "Hello PDF" in result.pages[0].text
    assert result.pages[1].text == ""
    assert "Page Three" in result.pages[2].text
    assert result.empty_text_page_numbers == (2,)
    raw = source.read_bytes()
    assert result.source_byte_count == len(raw)
    assert result.source_sha256 == hashlib.sha256(raw).hexdigest()
    assert result.origin.origin_class == LOCAL_PDF_ORIGIN_CLASS
    assert result.origin.actor_type == LOCAL_PDF_ACTOR_TYPE
    assert result.origin.acquisition_method == LOCAL_PDF_ACQUISITION_METHOD
    assert result.origin.authority_class == LOCAL_PDF_AUTHORITY_CLASS
    payload = result.to_dict()
    assert payload["schema_version"] == LOCAL_PDF_REPORT_SCHEMA_VERSION
    assert payload["ocr_used"] is False
    assert payload["image_extraction_used"] is False
    assert payload["process_launch_used"] is False
    assert payload["network_access_used"] is False


def test_exact_page_selection_preserves_caller_order_and_metadata_only(tmp_path: Path) -> None:
    source = _source(tmp_path, pages=("First", "Second", "Third"))

    result = extract_local_pdf_text(source, selected_pages=(3, 1))
    metadata = result.to_dict(include_text=False)

    assert result.selected_page_numbers == (3, 1)
    assert [page.page_number for page in result.pages] == [3, 1]
    assert "Third" in result.pages[0].text
    assert "First" in result.pages[1].text
    assert all("text" not in page for page in cast(list[dict[str, object]], metadata["pages"]))


def test_synthetic_adapter_preserves_unicode_and_japanese_text(tmp_path: Path) -> None:
    source = _source(tmp_path)
    adapter = _FakeAdapter(("日本語の本文\nUnicode café", ""))

    result = extract_local_pdf_text(source, adapter=adapter)

    assert result.adapter_id == "synthetic-pdf"
    assert result.adapter_version == "1.0"
    assert result.pages[0].text == "日本語の本文\nUnicode café"
    assert result.empty_text_page_numbers == (2,)


def test_optional_adapter_absence_is_clean_and_cli_help_does_not_load_it(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    source = _source(tmp_path)
    original_import = importlib.import_module

    def missing(name: str) -> object:
        if name == "pypdf":
            raise ModuleNotFoundError(name)
        return original_import(name)

    monkeypatch.setattr(importlib, "import_module", missing)

    help_result = runner.invoke(app, ["pdf", "--help"])
    command_result = runner.invoke(app, ["pdf", "extract", str(source), "--json"])

    assert help_result.exit_code == 0
    assert "Extract text" in help_result.stdout
    assert "PDF" in help_result.stdout
    assert command_result.exit_code == 2
    payload = json.loads(command_result.stdout)
    assert payload["error_class"] == "LocalPdfAdapterUnavailableError"
    assert str(source) not in command_result.stdout


def test_pypdf_adapter_load_rejects_missing_version_or_reader(monkeypatch: MonkeyPatch) -> None:
    class MissingVersion:
        PdfReader = object

    monkeypatch.setattr(
        importlib,
        "import_module",
        lambda name: MissingVersion(),
    )
    with pytest.raises(LocalPdfAdapterUnavailableError, match="version"):
        PypdfTextAdapter.load()

    class MissingReader:
        __version__ = "6.7.0"

    monkeypatch.setattr(
        importlib,
        "import_module",
        lambda name: MissingReader(),
    )
    adapter = PypdfTextAdapter.load()
    with pytest.raises(LocalPdfAdapterUnavailableError, match="PdfReader"):
        adapter.open_reader(b"%PDF-1.4\n")


def test_rejects_invalid_page_selections(tmp_path: Path) -> None:
    source = _source(tmp_path, pages=("One", "Two"))
    adapter = _FakeAdapter(("One", "Two"))

    for selection in ((0,), (-1,), (True,), (1, 1), (3,)):
        with pytest.raises(LocalPdfValidationError):
            extract_local_pdf_text(source, selected_pages=selection, adapter=adapter)

    too_many = tuple(range(1, 102))
    with pytest.raises(LocalPdfValidationError, match="too many"):
        extract_local_pdf_text(source, selected_pages=too_many, adapter=adapter)


def test_rejects_encrypted_empty_excessive_and_unavailable_inventory(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    source = _source(tmp_path)

    with pytest.raises(LocalPdfValidationError, match="encrypted"):
        extract_local_pdf_text(source, adapter=_FakeAdapter(("text",), encrypted=True))
    with pytest.raises(LocalPdfValidationError, match="at least one page"):
        extract_local_pdf_text(source, adapter=_FakeAdapter(()))
    with pytest.raises(LocalPdfValidationError, match="inventory"):
        extract_local_pdf_text(
            source,
            adapter=_FakeAdapter(("text",), inventory_failure=True),
        )

    monkeypatch.setattr(local_pdf_module, "_MAX_DOCUMENT_PAGES", 1)
    with pytest.raises(LocalPdfValidationError, match="page limit"):
        extract_local_pdf_text(source, adapter=_FakeAdapter(("one", "two")))


def test_rejects_adapter_and_page_extraction_failures(tmp_path: Path) -> None:
    source = _source(tmp_path)

    with pytest.raises(LocalPdfValidationError, match="could not be parsed"):
        extract_local_pdf_text(source, adapter=_FakeAdapter(("text",), open_failure=True))

    class FailingPageAdapter(_FakeAdapter):
        def open_reader(self, source_bytes: bytes) -> _FakeReader:
            del source_bytes
            reader_pages = (_FakePage("", failure=True),)

            class Reader:
                is_encrypted = False
                pages = reader_pages

            return cast(_FakeReader, Reader())

    with pytest.raises(LocalPdfValidationError, match="extraction failed"):
        extract_local_pdf_text(source, adapter=FailingPageAdapter(("text",)))

    with pytest.raises(LocalPdfValidationError, match="invalid page text"):
        extract_local_pdf_text(source, adapter=_FakeAdapter((123,)))


def test_rejects_extracted_text_and_adapter_metadata_limits(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    source = _source(tmp_path)

    for text in ("a\x00b", "a\x01b", "a\x7fb"):
        with pytest.raises(LocalPdfValidationError):
            extract_local_pdf_text(source, adapter=_FakeAdapter((text,)))

    monkeypatch.setattr(local_pdf_module, "_MAX_PAGE_CHARACTERS", 3)
    with pytest.raises(LocalPdfValidationError, match="page text"):
        extract_local_pdf_text(source, adapter=_FakeAdapter(("four",)))

    monkeypatch.setattr(local_pdf_module, "_MAX_PAGE_CHARACTERS", 100_000)
    monkeypatch.setattr(local_pdf_module, "_MAX_AGGREGATE_CHARACTERS", 5)
    with pytest.raises(LocalPdfValidationError, match="aggregate"):
        extract_local_pdf_text(source, adapter=_FakeAdapter(("abc", "def")))

    for adapter in (
        _FakeAdapter(("text",), adapter_id=""),
        _FakeAdapter(("text",), adapter_version="x" * 81),
        _FakeAdapter(("text",), adapter_id="bad\x01id"),
    ):
        with pytest.raises(LocalPdfValidationError, match="adapter"):
            extract_local_pdf_text(source, adapter=adapter)


def test_rejects_missing_directory_symlink_oversize_changed_signature_and_malformed(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    with pytest.raises(LocalPdfReadError, match="unavailable"):
        extract_local_pdf_text(tmp_path / "missing.pdf", adapter=_FakeAdapter(("x",)))

    directory = tmp_path / "folder.pdf"
    directory.mkdir()
    with pytest.raises(LocalPdfValidationError, match="regular file"):
        extract_local_pdf_text(directory, adapter=_FakeAdapter(("x",)))

    target = _source(tmp_path)
    link = tmp_path / "link.pdf"
    try:
        link.symlink_to(target)
    except OSError:
        pass
    else:
        with pytest.raises(LocalPdfValidationError, match="symlinks"):
            extract_local_pdf_text(link, adapter=_FakeAdapter(("x",)))

    unsupported = tmp_path / "document.txt"
    unsupported.write_bytes(_pdf_bytes(("text",)))
    with pytest.raises(LocalPdfValidationError, match="extension"):
        extract_local_pdf_text(unsupported, adapter=_FakeAdapter(("x",)))

    invalid_signature = tmp_path / "signature.pdf"
    invalid_signature.write_bytes(b"not a PDF")
    with pytest.raises(LocalPdfValidationError, match="signature"):
        extract_local_pdf_text(invalid_signature, adapter=_FakeAdapter(("x",)))

    malformed = tmp_path / "malformed.pdf"
    malformed.write_bytes(b"%PDF-1.4\nnot valid")
    with pytest.raises(LocalPdfValidationError, match="structure"):
        extract_local_pdf_text(malformed)

    oversized = tmp_path / "large.pdf"
    oversized.write_bytes(b"%PDF-" + b"x" * 20)
    monkeypatch.setattr(local_pdf_module, "_MAX_SOURCE_BYTES", 16)
    with pytest.raises(LocalPdfValidationError, match="maximum byte size"):
        extract_local_pdf_text(oversized, adapter=_FakeAdapter(("x",)))

    monkeypatch.setattr(local_pdf_module, "_MAX_SOURCE_BYTES", 8_388_608)
    changed = _source(tmp_path, pages=("changed",))
    monkeypatch.setattr(local_pdf_module, "_stable_read", lambda *args: False)
    with pytest.raises(LocalPdfReadError, match="changed while"):
        extract_local_pdf_text(changed, adapter=_FakeAdapter(("x",)))


def test_source_workspace_and_state_remain_unchanged(tmp_path: Path) -> None:
    initialized = initialize_workspace(tmp_path / "workspace")
    with initialize_state_repository(initialized.root):
        pass
    source = _source(tmp_path, pages=("External PDF",))
    source_before = source.read_bytes()
    workspace_before = _workspace_snapshot(initialized.root)
    siblings_before = sorted(path.name for path in tmp_path.iterdir())

    result = extract_local_pdf_text(source)

    assert "External PDF" in result.pages[0].text
    assert source.read_bytes() == source_before
    assert _workspace_snapshot(initialized.root) == workspace_before
    assert sorted(path.name for path in tmp_path.iterdir()) == siblings_before


def test_cli_human_json_metadata_and_path_safe_failures(tmp_path: Path) -> None:
    source = _source(tmp_path, pages=("First", None, "Third"))

    human = runner.invoke(app, ["pdf", "extract", str(source), "--page", "2"])
    machine = runner.invoke(
        app,
        ["pdf", "extract", str(source), "--page", "3", "--page", "1", "--json"],
    )
    metadata = runner.invoke(
        app,
        ["pdf", "extract", str(source), "--json", "--metadata-only"],
    )
    missing = tmp_path / "private-missing.pdf"
    failure = runner.invoke(app, ["pdf", "extract", str(missing), "--json"])

    assert human.exit_code == 0
    assert "PDF extraction: pages=1/3" in human.stdout
    assert "Pages with no extractable text: 2" in human.stdout
    assert "external_content/untrusted_data" in human.stdout
    payload = json.loads(machine.stdout)
    assert payload["selected_page_numbers"] == [3, 1]
    assert "Third" in payload["pages"][0]["text"]
    metadata_payload = json.loads(metadata.stdout)
    assert all("text" not in page for page in metadata_payload["pages"])
    assert failure.exit_code == 2
    assert json.loads(failure.stdout)["error"] == "local_pdf_extraction_failed"
    assert str(missing) not in failure.stdout
    assert str(tmp_path) not in failure.stdout
