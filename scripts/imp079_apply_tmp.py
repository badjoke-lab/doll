from __future__ import annotations

from pathlib import Path


path = Path("src/doll/local_writing.py")
text = path.read_text(encoding="utf-8")


def replace_once(old: str, new: str) -> None:
    global text
    if old not in text:
        raise SystemExit(f"missing patch marker: {old[:100]!r}")
    text = text.replace(old, new, 1)


replace_once(
    "from doll.local_document import LocalDocumentError, LocalDocumentResult, read_local_document\n",
    "from doll.local_document import LocalDocumentError, LocalDocumentResult, read_local_document\n"
    "from doll.local_pdf import LocalPdfError, LocalPdfExtraction, extract_local_pdf_text\n",
)
replace_once(
    'WritingSourceKind = Literal["none", "inline", "document"]',
    'WritingSourceKind = Literal["none", "inline", "document", "pdf"]',
)
replace_once(
    "class _PreparedWritingSource:\n"
    "    kind: WritingSourceKind\n"
    "    text: str | None\n"
    "    document: LocalDocumentResult | None = None\n",
    "class _PreparedWritingSource:\n"
    "    kind: WritingSourceKind\n"
    "    text: str | None\n"
    "    document: LocalDocumentResult | None = None\n"
    "    pdf: LocalPdfExtraction | None = None\n",
)
replace_once(
    "    source_document_utf8_bom_removed: bool\n"
    "    selected_context_instruction_ids: tuple[str, ...]\n",
    "    source_document_utf8_bom_removed: bool\n"
    "    source_pdf_adapter_id: str | None\n"
    "    source_pdf_adapter_version: str | None\n"
    "    source_pdf_source_byte_count: int\n"
    "    source_pdf_source_sha256: str | None\n"
    "    source_pdf_document_page_count: int\n"
    "    source_pdf_selected_page_numbers: tuple[int, ...]\n"
    "    source_pdf_empty_text_page_numbers: tuple[int, ...]\n"
    "    source_pdf_extracted_character_count: int\n"
    "    selected_context_instruction_ids: tuple[str, ...]\n",
)
replace_once(
    "        source_text: str | None = None,\n"
    "        source_document_path: Path | None = None,\n"
    "        target_language: str | None = None,\n",
    "        source_text: str | None = None,\n"
    "        source_document_path: Path | None = None,\n"
    "        source_pdf_path: Path | None = None,\n"
    "        source_pdf_pages: Sequence[int] = (),\n"
    "        target_language: str | None = None,\n",
)
replace_once(
    "            source_text=source_text,\n"
    "            source_document_path=source_document_path,\n"
    "        )\n"
    "        inline_source = _source_text(source_text) if source_kind == \"inline\" else None\n",
    "            source_text=source_text,\n"
    "            source_document_path=source_document_path,\n"
    "            source_pdf_path=source_pdf_path,\n"
    "            source_pdf_pages=source_pdf_pages,\n"
    "        )\n"
    "        inline_source = _source_text(source_text) if source_kind == \"inline\" else None\n"
    "        safe_pdf_pages = _pdf_page_selection(source_pdf_pages) if source_kind == \"pdf\" else ()\n",
)
replace_once(
    "            inline_source=inline_source,\n"
    "            source_document_path=source_document_path,\n"
    "        )\n",
    "            inline_source=inline_source,\n"
    "            source_document_path=source_document_path,\n"
    "            source_pdf_path=source_pdf_path,\n"
    "            source_pdf_pages=safe_pdf_pages,\n"
    "        )\n",
)
replace_once(
    "def _source_kind_for_mode(\n"
    "    mode: WritingMode,\n"
    "    *,\n"
    "    source_text: object,\n"
    "    source_document_path: object,\n"
    ") -> WritingSourceKind:\n"
    "    has_inline = source_text is not None\n"
    "    has_document = source_document_path is not None\n"
    "    if mode == \"draft\":\n"
    "        if has_inline or has_document:\n"
    "            raise LocalWritingWorkflowValidationError(\n"
    "                \"draft mode does not accept primary source material\"\n"
    "            )\n"
    "        return \"none\"\n"
    "    if has_inline == has_document:\n"
    "        raise LocalWritingWorkflowValidationError(\n"
    "            f\"{mode} mode requires exactly one primary source\"\n"
    "        )\n"
    "    if has_document:\n"
    "        if not isinstance(source_document_path, Path):\n"
    "            raise LocalWritingWorkflowValidationError(\"writing source document path is invalid\")\n"
    "        return \"document\"\n"
    "    return \"inline\"\n",
    "def _source_kind_for_mode(\n"
    "    mode: WritingMode,\n"
    "    *,\n"
    "    source_text: object,\n"
    "    source_document_path: object,\n"
    "    source_pdf_path: object,\n"
    "    source_pdf_pages: object,\n"
    ") -> WritingSourceKind:\n"
    "    has_inline = source_text is not None\n"
    "    has_document = source_document_path is not None\n"
    "    has_pdf = source_pdf_path is not None\n"
    "    has_pdf_pages = bool(source_pdf_pages)\n"
    "    if mode == \"draft\":\n"
    "        if has_inline or has_document or has_pdf or has_pdf_pages:\n"
    "            raise LocalWritingWorkflowValidationError(\n"
    "                \"draft mode does not accept primary source material\"\n"
    "            )\n"
    "        return \"none\"\n"
    "    if has_pdf_pages and not has_pdf:\n"
    "        raise LocalWritingWorkflowValidationError(\n"
    "            \"PDF page selection requires a PDF primary source\"\n"
    "        )\n"
    "    if sum((has_inline, has_document, has_pdf)) != 1:\n"
    "        raise LocalWritingWorkflowValidationError(\n"
    "            f\"{mode} mode requires exactly one primary source\"\n"
    "        )\n"
    "    if has_document:\n"
    "        if not isinstance(source_document_path, Path):\n"
    "            raise LocalWritingWorkflowValidationError(\"writing source document path is invalid\")\n"
    "        return \"document\"\n"
    "    if has_pdf:\n"
    "        if not isinstance(source_pdf_path, Path):\n"
    "            raise LocalWritingWorkflowValidationError(\"writing source PDF path is invalid\")\n"
    "        return \"pdf\"\n"
    "    return \"inline\"\n",
)
replace_once(
    "def _prepare_source_after_preflight(\n"
    "    *,\n"
    "    source_kind: WritingSourceKind,\n"
    "    inline_source: str | None,\n"
    "    source_document_path: Path | None,\n"
    ") -> _PreparedWritingSource:\n",
    "def _pdf_page_selection(value: object) -> tuple[int, ...]:\n"
    "    if isinstance(value, str | bytes) or not isinstance(value, Sequence):\n"
    "        raise LocalWritingWorkflowValidationError(\"writing source PDF pages are invalid\")\n"
    "    pages = tuple(value)\n"
    "    if any(isinstance(page, bool) or not isinstance(page, int) for page in pages):\n"
    "        raise LocalWritingWorkflowValidationError(\"writing source PDF pages are invalid\")\n"
    "    return pages\n\n\n"
    "def _prepare_source_after_preflight(\n"
    "    *,\n"
    "    source_kind: WritingSourceKind,\n"
    "    inline_source: str | None,\n"
    "    source_document_path: Path | None,\n"
    "    source_pdf_path: Path | None,\n"
    "    source_pdf_pages: tuple[int, ...],\n"
    ") -> _PreparedWritingSource:\n",
)
replace_once(
    "    if source_document_path is None:\n"
    "        raise LocalWritingWorkflowValidationError(\"writing source document is unavailable\")\n"
    "    try:\n"
    "        document = read_local_document(source_document_path)\n"
    "        safe_text = _source_text(document.text)\n"
    "    except (LocalDocumentError, LocalWritingWorkflowValidationError) as exc:\n"
    "        raise LocalWritingWorkflowValidationError(\"writing source document is invalid\") from exc\n"
    "    return _PreparedWritingSource(kind=\"document\", text=safe_text, document=document)\n",
    "    if source_kind == \"document\":\n"
    "        if source_document_path is None:\n"
    "            raise LocalWritingWorkflowValidationError(\"writing source document is unavailable\")\n"
    "        try:\n"
    "            document = read_local_document(source_document_path)\n"
    "            safe_text = _source_text(document.text)\n"
    "        except (LocalDocumentError, LocalWritingWorkflowValidationError) as exc:\n"
    "            raise LocalWritingWorkflowValidationError(\n"
    "                \"writing source document is invalid\"\n"
    "            ) from exc\n"
    "        return _PreparedWritingSource(kind=\"document\", text=safe_text, document=document)\n"
    "    if source_pdf_path is None:\n"
    "        raise LocalWritingWorkflowValidationError(\"writing source PDF is unavailable\")\n"
    "    try:\n"
    "        pdf = extract_local_pdf_text(source_pdf_path, selected_pages=source_pdf_pages)\n"
    "        flattened = \"\\n\\n\".join(page.text for page in pdf.pages)\n"
    "        safe_text = _source_text(flattened)\n"
    "    except (LocalPdfError, LocalWritingWorkflowValidationError) as exc:\n"
    "        raise LocalWritingWorkflowValidationError(\"writing source PDF is invalid\") from exc\n"
    "    return _PreparedWritingSource(kind=\"pdf\", text=safe_text, pdf=pdf)\n",
)
replace_once(
    "    document = prepared_source.document\n"
    "    return LocalWritingWorkflowResult(\n",
    "    document = prepared_source.document\n"
    "    pdf = prepared_source.pdf\n"
    "    return LocalWritingWorkflowResult(\n",
)
replace_once(
    "        source_document_utf8_bom_removed=(\n"
    "            document.utf8_bom_removed if document is not None else False\n"
    "        ),\n"
    "        selected_context_instruction_ids=(\n",
    "        source_document_utf8_bom_removed=(\n"
    "            document.utf8_bom_removed if document is not None else False\n"
    "        ),\n"
    "        source_pdf_adapter_id=pdf.adapter_id if pdf is not None else None,\n"
    "        source_pdf_adapter_version=pdf.adapter_version if pdf is not None else None,\n"
    "        source_pdf_source_byte_count=pdf.source_byte_count if pdf is not None else 0,\n"
    "        source_pdf_source_sha256=pdf.source_sha256 if pdf is not None else None,\n"
    "        source_pdf_document_page_count=pdf.document_page_count if pdf is not None else 0,\n"
    "        source_pdf_selected_page_numbers=(\n"
    "            pdf.selected_page_numbers if pdf is not None else ()\n"
    "        ),\n"
    "        source_pdf_empty_text_page_numbers=(\n"
    "            pdf.empty_text_page_numbers if pdf is not None else ()\n"
    "        ),\n"
    "        source_pdf_extracted_character_count=(\n"
    "            pdf.aggregate_character_count if pdf is not None else 0\n"
    "        ),\n"
    "        selected_context_instruction_ids=(\n",
)

path.write_text(text, encoding="utf-8")
