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
    "from collections.abc import Sequence\n",
    "from collections.abc import Mapping, Sequence\n",
)
once(
    "from doll.local_conversation import (\n",
    "from doll.local_csv import LocalCsvError, LocalCsvTransformation, transform_local_csv\n"
    "from doll.local_conversation import (\n",
)
once(
    'WritingSourceKind = Literal["none", "inline", "document", "pdf", "ocr"]',
    'WritingSourceKind = Literal["none", "inline", "document", "pdf", "ocr", "csv"]',
)
once(
    "    pdf: LocalPdfExtraction | None = None\n"
    "    ocr: LocalOcrExtraction | None = None\n",
    "    pdf: LocalPdfExtraction | None = None\n"
    "    ocr: LocalOcrExtraction | None = None\n"
    "    csv: LocalCsvTransformation | None = None\n",
)
once(
    "    source_ocr_recognized_character_count: int\n"
    "    selected_context_instruction_ids: tuple[str, ...]\n",
    "    source_ocr_recognized_character_count: int\n"
    "    source_csv_delimiter_profile: str | None\n"
    "    source_csv_source_byte_count: int\n"
    "    source_csv_source_sha256: str | None\n"
    "    source_csv_content_sha256: str | None\n"
    "    source_csv_utf8_bom_removed: bool\n"
    "    source_csv_row_count: int\n"
    "    source_csv_source_column_count: int\n"
    "    source_csv_output_column_count: int\n"
    "    source_csv_blank_cell_count: int\n"
    "    source_csv_potential_formula_cell_count: int\n"
    "    source_csv_output_byte_count: int\n"
    "    source_csv_output_character_count: int\n"
    "    source_csv_output_sha256: str | None\n"
    "    selected_context_instruction_ids: tuple[str, ...]\n",
)
once(
    "        source_image_path: Path | None = None,\n"
    "        target_language: str | None = None,\n",
    "        source_image_path: Path | None = None,\n"
    "        source_csv_path: Path | None = None,\n"
    "        source_csv_delimiter_profile: str = \"comma\",\n"
    "        source_csv_selected_columns: Sequence[str] = (),\n"
    "        source_csv_header_renames: Mapping[str, str] | None = None,\n"
    "        target_language: str | None = None,\n",
)
once(
    "            source_image_path=source_image_path,\n"
    "        )\n"
    "        inline_source = _source_text(source_text) if source_kind == \"inline\" else None\n"
    "        safe_pdf_pages = _pdf_page_selection(source_pdf_pages) if source_kind == \"pdf\" else ()\n",
    "            source_image_path=source_image_path,\n"
    "            source_csv_path=source_csv_path,\n"
    "            source_csv_delimiter_profile=source_csv_delimiter_profile,\n"
    "            source_csv_selected_columns=source_csv_selected_columns,\n"
    "            source_csv_header_renames=source_csv_header_renames,\n"
    "        )\n"
    "        inline_source = _source_text(source_text) if source_kind == \"inline\" else None\n"
    "        safe_pdf_pages = _pdf_page_selection(source_pdf_pages) if source_kind == \"pdf\" else ()\n"
    "        safe_csv_delimiter = (\n"
    "            _csv_delimiter_profile(source_csv_delimiter_profile)\n"
    "            if source_kind == \"csv\"\n"
    "            else \"comma\"\n"
    "        )\n"
    "        safe_csv_columns = (\n"
    "            _csv_selected_columns(source_csv_selected_columns)\n"
    "            if source_kind == \"csv\"\n"
    "            else ()\n"
    "        )\n"
    "        safe_csv_renames = (\n"
    "            _csv_header_renames(source_csv_header_renames)\n"
    "            if source_kind == \"csv\"\n"
    "            else {}\n"
    "        )\n",
)
once(
    "            source_image_path=source_image_path,\n"
    "        )\n",
    "            source_image_path=source_image_path,\n"
    "            source_csv_path=source_csv_path,\n"
    "            source_csv_delimiter_profile=safe_csv_delimiter,\n"
    "            source_csv_selected_columns=safe_csv_columns,\n"
    "            source_csv_header_renames=safe_csv_renames,\n"
    "        )\n",
)
once(
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
    "    source_pdf_pages: object,\n"
    "    source_image_path: object,\n"
    "    source_csv_path: object,\n"
    "    source_csv_delimiter_profile: object,\n"
    "    source_csv_selected_columns: object,\n"
    "    source_csv_header_renames: object,\n"
    ") -> WritingSourceKind:\n"
    "    has_inline = source_text is not None\n"
    "    has_document = source_document_path is not None\n"
    "    has_pdf = source_pdf_path is not None\n"
    "    has_pdf_pages = bool(source_pdf_pages)\n"
    "    has_image = source_image_path is not None\n"
    "    has_csv = source_csv_path is not None\n"
    "    has_csv_options = (\n"
    "        source_csv_delimiter_profile != \"comma\"\n"
    "        or bool(source_csv_selected_columns)\n"
    "        or source_csv_header_renames is not None\n"
    "    )\n"
    "    if mode == \"draft\":\n"
    "        if (\n"
    "            has_inline\n"
    "            or has_document\n"
    "            or has_pdf\n"
    "            or has_pdf_pages\n"
    "            or has_image\n"
    "            or has_csv\n"
    "            or has_csv_options\n"
    "        ):\n",
)
once(
    "    if has_pdf_pages and not has_pdf:\n"
    "        raise LocalWritingWorkflowValidationError(\n"
    "            \"PDF page selection requires a PDF primary source\"\n"
    "        )\n"
    "    if sum((has_inline, has_document, has_pdf, has_image)) != 1:\n",
    "    if has_pdf_pages and not has_pdf:\n"
    "        raise LocalWritingWorkflowValidationError(\n"
    "            \"PDF page selection requires a PDF primary source\"\n"
    "        )\n"
    "    if has_csv_options and not has_csv:\n"
    "        raise LocalWritingWorkflowValidationError(\n"
    "            \"CSV options require a CSV primary source\"\n"
    "        )\n"
    "    if sum((has_inline, has_document, has_pdf, has_image, has_csv)) != 1:\n",
)
once(
    "    if has_image:\n"
    "        if not isinstance(source_image_path, Path):\n"
    "            raise LocalWritingWorkflowValidationError(\"writing source OCR image path is invalid\")\n"
    "        return \"ocr\"\n"
    "    return \"inline\"\n",
    "    if has_image:\n"
    "        if not isinstance(source_image_path, Path):\n"
    "            raise LocalWritingWorkflowValidationError(\"writing source OCR image path is invalid\")\n"
    "        return \"ocr\"\n"
    "    if has_csv:\n"
    "        if not isinstance(source_csv_path, Path):\n"
    "            raise LocalWritingWorkflowValidationError(\"writing source CSV path is invalid\")\n"
    "        return \"csv\"\n"
    "    return \"inline\"\n",
)
once(
    "def _pdf_page_selection(value: object) -> tuple[int, ...]:\n",
    "def _csv_delimiter_profile(value: object) -> str:\n"
    "    if not isinstance(value, str):\n"
    "        raise LocalWritingWorkflowValidationError(\n"
    "            \"writing source CSV delimiter profile is invalid\"\n"
    "        )\n"
    "    return value\n\n\n"
    "def _csv_selected_columns(value: object) -> tuple[str, ...]:\n"
    "    if isinstance(value, str | bytes) or not isinstance(value, Sequence):\n"
    "        raise LocalWritingWorkflowValidationError(\n"
    "            \"writing source CSV selected columns are invalid\"\n"
    "        )\n"
    "    columns = tuple(value)\n"
    "    if any(not isinstance(column, str) for column in columns):\n"
    "        raise LocalWritingWorkflowValidationError(\n"
    "            \"writing source CSV selected columns are invalid\"\n"
    "        )\n"
    "    return columns\n\n\n"
    "def _csv_header_renames(value: object) -> dict[str, str]:\n"
    "    if value is None:\n"
    "        return {}\n"
    "    if not isinstance(value, Mapping):\n"
    "        raise LocalWritingWorkflowValidationError(\n"
    "            \"writing source CSV header renames are invalid\"\n"
    "        )\n"
    "    renames = dict(value)\n"
    "    if any(\n"
    "        not isinstance(source, str) or not isinstance(target, str)\n"
    "        for source, target in renames.items()\n"
    "    ):\n"
    "        raise LocalWritingWorkflowValidationError(\n"
    "            \"writing source CSV header renames are invalid\"\n"
    "        )\n"
    "    return renames\n\n\n"
    "def _pdf_page_selection(value: object) -> tuple[int, ...]:\n",
)
once(
    "    source_pdf_pages: tuple[int, ...],\n"
    "    source_image_path: Path | None,\n"
    ") -> _PreparedWritingSource:\n",
    "    source_pdf_pages: tuple[int, ...],\n"
    "    source_image_path: Path | None,\n"
    "    source_csv_path: Path | None,\n"
    "    source_csv_delimiter_profile: str,\n"
    "    source_csv_selected_columns: tuple[str, ...],\n"
    "    source_csv_header_renames: Mapping[str, str],\n"
    ") -> _PreparedWritingSource:\n",
)
once(
    "    if source_image_path is None:\n"
    "        raise LocalWritingWorkflowValidationError(\"writing source OCR image is unavailable\")\n"
    "    try:\n"
    "        ocr = extract_local_image_ocr(source_image_path)\n"
    "        flattened = \"\\n\".join(line.text for line in ocr.lines)\n"
    "        safe_text = _source_text(flattened)\n"
    "    except (LocalOcrError, LocalWritingWorkflowValidationError) as exc:\n"
    "        raise LocalWritingWorkflowValidationError(\"writing source OCR image is invalid\") from exc\n"
    "    return _PreparedWritingSource(kind=\"ocr\", text=safe_text, ocr=ocr)\n",
    "    if source_kind == \"ocr\":\n"
    "        if source_image_path is None:\n"
    "            raise LocalWritingWorkflowValidationError(\"writing source OCR image is unavailable\")\n"
    "        try:\n"
    "            ocr = extract_local_image_ocr(source_image_path)\n"
    "            flattened = \"\\n\".join(line.text for line in ocr.lines)\n"
    "            safe_text = _source_text(flattened)\n"
    "        except (LocalOcrError, LocalWritingWorkflowValidationError) as exc:\n"
    "            raise LocalWritingWorkflowValidationError(\n"
    "                \"writing source OCR image is invalid\"\n"
    "            ) from exc\n"
    "        return _PreparedWritingSource(kind=\"ocr\", text=safe_text, ocr=ocr)\n"
    "    if source_csv_path is None:\n"
    "        raise LocalWritingWorkflowValidationError(\"writing source CSV is unavailable\")\n"
    "    try:\n"
    "        csv_result = transform_local_csv(\n"
    "            source_csv_path,\n"
    "            delimiter_profile=source_csv_delimiter_profile,\n"
    "            selected_columns=source_csv_selected_columns,\n"
    "            header_renames=source_csv_header_renames,\n"
    "        )\n"
    "        safe_text = _source_text(csv_result.output_csv)\n"
    "    except (LocalCsvError, LocalWritingWorkflowValidationError) as exc:\n"
    "        raise LocalWritingWorkflowValidationError(\"writing source CSV is invalid\") from exc\n"
    "    return _PreparedWritingSource(kind=\"csv\", text=safe_text, csv=csv_result)\n",
)
once(
    "    ocr = prepared_source.ocr\n"
    "    return LocalWritingWorkflowResult(\n",
    "    ocr = prepared_source.ocr\n"
    "    csv_result = prepared_source.csv\n"
    "    return LocalWritingWorkflowResult(\n",
)
once(
    "        source_ocr_recognized_character_count=(\n"
    "            ocr.aggregate_character_count if ocr is not None else 0\n"
    "        ),\n"
    "        selected_context_instruction_ids=(\n",
    "        source_ocr_recognized_character_count=(\n"
    "            ocr.aggregate_character_count if ocr is not None else 0\n"
    "        ),\n"
    "        source_csv_delimiter_profile=(\n"
    "            csv_result.source.delimiter_profile if csv_result is not None else None\n"
    "        ),\n"
    "        source_csv_source_byte_count=(\n"
    "            csv_result.source.source_byte_count if csv_result is not None else 0\n"
    "        ),\n"
    "        source_csv_source_sha256=(\n"
    "            csv_result.source.source_sha256 if csv_result is not None else None\n"
    "        ),\n"
    "        source_csv_content_sha256=(\n"
    "            csv_result.source.content_sha256 if csv_result is not None else None\n"
    "        ),\n"
    "        source_csv_utf8_bom_removed=(\n"
    "            csv_result.source.utf8_bom_removed if csv_result is not None else False\n"
    "        ),\n"
    "        source_csv_row_count=(csv_result.source.row_count if csv_result is not None else 0),\n"
    "        source_csv_source_column_count=(\n"
    "            csv_result.source.column_count if csv_result is not None else 0\n"
    "        ),\n"
    "        source_csv_output_column_count=(\n"
    "            len(csv_result.output_headers) if csv_result is not None else 0\n"
    "        ),\n"
    "        source_csv_blank_cell_count=(\n"
    "            csv_result.source.blank_cell_count if csv_result is not None else 0\n"
    "        ),\n"
    "        source_csv_potential_formula_cell_count=(\n"
    "            csv_result.source.potential_formula_cell_count\n"
    "            if csv_result is not None\n"
    "            else 0\n"
    "        ),\n"
    "        source_csv_output_byte_count=(\n"
    "            csv_result.output_byte_count if csv_result is not None else 0\n"
    "        ),\n"
    "        source_csv_output_character_count=(\n"
    "            csv_result.output_character_count if csv_result is not None else 0\n"
    "        ),\n"
    "        source_csv_output_sha256=(\n"
    "            csv_result.output_sha256 if csv_result is not None else None\n"
    "        ),\n"
    "        selected_context_instruction_ids=(\n",
)

path.write_text(text, encoding="utf-8")
