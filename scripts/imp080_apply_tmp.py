from __future__ import annotations

from pathlib import Path


path = Path("src/doll/local_writing.py")
text = path.read_text(encoding="utf-8")


def once(old: str, new: str) -> None:
    global text
    if old not in text:
        raise SystemExit(f"missing patch marker: {old[:120]!r}")
    text = text.replace(old, new, 1)


once(
    "from doll.local_document import LocalDocumentError, LocalDocumentResult, read_local_document\n"
    "from doll.local_pdf import LocalPdfError, LocalPdfExtraction, extract_local_pdf_text\n",
    "from doll.local_document import LocalDocumentError, LocalDocumentResult, read_local_document\n"
    "from doll.local_ocr import LocalOcrError, LocalOcrExtraction, extract_local_image_ocr\n"
    "from doll.local_pdf import LocalPdfError, LocalPdfExtraction, extract_local_pdf_text\n",
)
once(
    'WritingSourceKind = Literal["none", "inline", "document", "pdf"]',
    'WritingSourceKind = Literal["none", "inline", "document", "pdf", "ocr"]',
)
once(
    "    document: LocalDocumentResult | None = None\n"
    "    pdf: LocalPdfExtraction | None = None\n",
    "    document: LocalDocumentResult | None = None\n"
    "    pdf: LocalPdfExtraction | None = None\n"
    "    ocr: LocalOcrExtraction | None = None\n",
)
once(
    "    source_pdf_extracted_character_count: int\n"
    "    selected_context_instruction_ids: tuple[str, ...]\n",
    "    source_pdf_extracted_character_count: int\n"
    "    source_ocr_adapter_id: str | None\n"
    "    source_ocr_adapter_version: str | None\n"
    "    source_ocr_source_byte_count: int\n"
    "    source_ocr_source_sha256: str | None\n"
    "    source_ocr_image_format: str | None\n"
    "    source_ocr_width: int\n"
    "    source_ocr_height: int\n"
    "    source_ocr_pixel_count: int\n"
    "    source_ocr_line_count: int\n"
    "    source_ocr_recognized_character_count: int\n"
    "    selected_context_instruction_ids: tuple[str, ...]\n",
)
once(
    "        source_pdf_path: Path | None = None,\n"
    "        source_pdf_pages: Sequence[int] = (),\n"
    "        target_language: str | None = None,\n",
    "        source_pdf_path: Path | None = None,\n"
    "        source_pdf_pages: Sequence[int] = (),\n"
    "        source_image_path: Path | None = None,\n"
    "        target_language: str | None = None,\n",
)
once(
    "            source_pdf_path=source_pdf_path,\n"
    "            source_pdf_pages=source_pdf_pages,\n"
    "        )\n",
    "            source_pdf_path=source_pdf_path,\n"
    "            source_pdf_pages=source_pdf_pages,\n"
    "            source_image_path=source_image_path,\n"
    "        )\n",
)
once(
    "            source_pdf_path=source_pdf_path,\n"
    "            source_pdf_pages=safe_pdf_pages,\n"
    "        )\n",
    "            source_pdf_path=source_pdf_path,\n"
    "            source_pdf_pages=safe_pdf_pages,\n"
    "            source_image_path=source_image_path,\n"
    "        )\n",
)
once(
    '                    acquisition_method="extraction",\n',
    '                    acquisition_method=_source_acquisition_method(prepared_source.kind),\n',
)
once(
    "    source_pdf_path: object,\n"
    "    source_pdf_pages: object,\n"
    ") -> WritingSourceKind:\n"
    "    has_inline = source_text is not None\n"
    "    has_document = source_document_path is not None\n"
    "    has_pdf = source_pdf_path is not None\n"
    "    has_pdf_pages = bool(source_pdf_pages)\n"
    "    if mode == \"draft\":\n"
    "        if has_inline or has_document or has_pdf or has_pdf_pages:\n",
    "    source_pdf_path: object,\n"
    "    source_pdf_pages: object,\n"
    "    source_image_path: object,\n"
    ") -> WritingSourceKind:\n"
    "    has_inline = source_text is not None\n"
    "    has_document = source_document_path is not None\n"
    "    has_pdf = source_pdf_path is not None\n"
    "    has_pdf_pages = bool(source_pdf_pages)\n"
    "    has_image = source_image_path is not None\n"
    "    if mode == \"draft\":\n"
    "        if has_inline or has_document or has_pdf or has_pdf_pages or has_image:\n",
)
once(
    "    if sum((has_inline, has_document, has_pdf)) != 1:\n",
    "    if sum((has_inline, has_document, has_pdf, has_image)) != 1:\n",
)
once(
    "    if has_pdf:\n"
    "        if not isinstance(source_pdf_path, Path):\n"
    "            raise LocalWritingWorkflowValidationError(\"writing source PDF path is invalid\")\n"
    "        return \"pdf\"\n"
    "    return \"inline\"\n",
    "    if has_pdf:\n"
    "        if not isinstance(source_pdf_path, Path):\n"
    "            raise LocalWritingWorkflowValidationError(\"writing source PDF path is invalid\")\n"
    "        return \"pdf\"\n"
    "    if has_image:\n"
    "        if not isinstance(source_image_path, Path):\n"
    "            raise LocalWritingWorkflowValidationError(\"writing source OCR image path is invalid\")\n"
    "        return \"ocr\"\n"
    "    return \"inline\"\n",
)
once(
    "def _source_for_mode(mode: WritingMode, value: object) -> str | None:\n",
    "def _source_acquisition_method(source_kind: WritingSourceKind) -> str:\n"
    "    return \"ocr\" if source_kind == \"ocr\" else \"extraction\"\n\n\n"
    "def _source_for_mode(mode: WritingMode, value: object) -> str | None:\n",
)
once(
    "    source_pdf_path: Path | None,\n"
    "    source_pdf_pages: tuple[int, ...],\n"
    ") -> _PreparedWritingSource:\n",
    "    source_pdf_path: Path | None,\n"
    "    source_pdf_pages: tuple[int, ...],\n"
    "    source_image_path: Path | None,\n"
    ") -> _PreparedWritingSource:\n",
)
once(
    "    if source_pdf_path is None:\n"
    "        raise LocalWritingWorkflowValidationError(\"writing source PDF is unavailable\")\n"
    "    try:\n"
    "        pdf = extract_local_pdf_text(source_pdf_path, selected_pages=source_pdf_pages)\n"
    "        flattened = \"\\n\\n\".join(page.text for page in pdf.pages)\n"
    "        safe_text = _source_text(flattened)\n"
    "    except (LocalPdfError, LocalWritingWorkflowValidationError) as exc:\n"
    "        raise LocalWritingWorkflowValidationError(\"writing source PDF is invalid\") from exc\n"
    "    return _PreparedWritingSource(kind=\"pdf\", text=safe_text, pdf=pdf)\n",
    "    if source_kind == \"pdf\":\n"
    "        if source_pdf_path is None:\n"
    "            raise LocalWritingWorkflowValidationError(\"writing source PDF is unavailable\")\n"
    "        try:\n"
    "            pdf = extract_local_pdf_text(source_pdf_path, selected_pages=source_pdf_pages)\n"
    "            flattened = \"\\n\\n\".join(page.text for page in pdf.pages)\n"
    "            safe_text = _source_text(flattened)\n"
    "        except (LocalPdfError, LocalWritingWorkflowValidationError) as exc:\n"
    "            raise LocalWritingWorkflowValidationError(\"writing source PDF is invalid\") from exc\n"
    "        return _PreparedWritingSource(kind=\"pdf\", text=safe_text, pdf=pdf)\n"
    "    if source_image_path is None:\n"
    "        raise LocalWritingWorkflowValidationError(\"writing source OCR image is unavailable\")\n"
    "    try:\n"
    "        ocr = extract_local_image_ocr(source_image_path)\n"
    "        flattened = \"\\n\".join(line.text for line in ocr.lines)\n"
    "        safe_text = _source_text(flattened)\n"
    "    except (LocalOcrError, LocalWritingWorkflowValidationError) as exc:\n"
    "        raise LocalWritingWorkflowValidationError(\n"
    "            \"writing source OCR image is invalid\"\n"
    "        ) from exc\n"
    "    return _PreparedWritingSource(kind=\"ocr\", text=safe_text, ocr=ocr)\n",
)
once(
    "    document = prepared_source.document\n"
    "    pdf = prepared_source.pdf\n"
    "    return LocalWritingWorkflowResult(\n",
    "    document = prepared_source.document\n"
    "    pdf = prepared_source.pdf\n"
    "    ocr = prepared_source.ocr\n"
    "    return LocalWritingWorkflowResult(\n",
)
once(
    "        source_pdf_extracted_character_count=(\n"
    "            pdf.aggregate_character_count if pdf is not None else 0\n"
    "        ),\n"
    "        selected_context_instruction_ids=(\n",
    "        source_pdf_extracted_character_count=(\n"
    "            pdf.aggregate_character_count if pdf is not None else 0\n"
    "        ),\n"
    "        source_ocr_adapter_id=ocr.adapter_id if ocr is not None else None,\n"
    "        source_ocr_adapter_version=ocr.adapter_version if ocr is not None else None,\n"
    "        source_ocr_source_byte_count=ocr.source_byte_count if ocr is not None else 0,\n"
    "        source_ocr_source_sha256=ocr.source_sha256 if ocr is not None else None,\n"
    "        source_ocr_image_format=ocr.image_format if ocr is not None else None,\n"
    "        source_ocr_width=ocr.width if ocr is not None else 0,\n"
    "        source_ocr_height=ocr.height if ocr is not None else 0,\n"
    "        source_ocr_pixel_count=ocr.pixel_count if ocr is not None else 0,\n"
    "        source_ocr_line_count=ocr.line_count if ocr is not None else 0,\n"
    "        source_ocr_recognized_character_count=(\n"
    "            ocr.aggregate_character_count if ocr is not None else 0\n"
    "        ),\n"
    "        selected_context_instruction_ids=(\n",
)

path.write_text(text, encoding="utf-8")
