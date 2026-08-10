from __future__ import annotations

from pathlib import Path

path = Path("src/doll/local_writing.py")
text = path.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one marker, found {count}")
    text = text.replace(old, new, 1)


replace_once(
    'WritingMode = Literal["draft", "revise", "summarize", "translate"]\nWritingSourceKind = Literal["none", "inline", "document", "pdf", "ocr", "csv"]\n\n_ALLOWED_MODES =',
    'WritingMode = Literal["draft", "revise", "summarize", "translate"]\nWritingAttachmentKind = Literal["document", "pdf", "ocr", "csv"]\nWritingSourceKind = Literal["none", "inline", "document", "pdf", "ocr", "csv", "multiple"]\n\n_ALLOWED_MODES =',
    "source kind aliases",
)
replace_once(
    '_MAX_SOURCE_CHARS = 16_000\n_MAX_TARGET_LANGUAGE_CHARS = 80',
    '_MAX_SOURCE_CHARS = 16_000\n_MAX_WRITING_ATTACHMENTS = 4\n_MAX_TARGET_LANGUAGE_CHARS = 80',
    "attachment limit",
)
replace_once(
    'class LocalWritingWorkflowValidationError(LocalWritingWorkflowError):\n    """Raised before runtime execution when a writing workflow is invalid."""\n\n\n@dataclass(frozen=True, slots=True)\nclass _PreparedWritingSource:',
    '''class LocalWritingWorkflowValidationError(LocalWritingWorkflowError):
    """Raised before runtime execution when a writing workflow is invalid."""


@dataclass(frozen=True, slots=True)
class LocalWritingAttachment:
    """One explicit local attachment specification for a bounded multi-source turn."""

    kind: WritingAttachmentKind
    path: Path
    pdf_pages: tuple[int, ...] = ()
    csv_delimiter_profile: str = "comma"
    csv_selected_columns: tuple[str, ...] = ()
    csv_header_renames: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class _PreparedWritingSource:''',
    "attachment dataclass",
)
replace_once(
    '    source_character_count: int\n    source_kind: WritingSourceKind\n    source_document_kind: str | None',
    '''    source_character_count: int
    source_kind: WritingSourceKind
    source_instruction_ids: tuple[str, ...]
    source_kinds: tuple[WritingAttachmentKind | Literal["inline"], ...]
    source_character_counts: tuple[int, ...]
    source_content_sha256s: tuple[str, ...]
    source_document_kind: str | None''',
    "result aggregate metadata",
)
replace_once(
    '        source_csv_header_renames: Mapping[str, str] | None = None,\n        target_language: str | None = None,',
    '        source_csv_header_renames: Mapping[str, str] | None = None,\n        source_attachments: Sequence[LocalWritingAttachment] = (),\n        target_language: str | None = None,',
    "execute attachments argument",
)
replace_once(
    '        safe_mode = _mode(mode)\n        safe_request = _request_text(request_text)\n        source_kind = _source_kind_for_mode(',
    '        safe_mode = _mode(mode)\n        safe_request = _request_text(request_text)\n        safe_attachments = _writing_attachments(source_attachments)\n        source_kind = _source_kind_for_mode(',
    "attachment validation call",
)
replace_once(
    '            source_csv_selected_columns=source_csv_selected_columns,\n            source_csv_header_renames=source_csv_header_renames,\n        )',
    '            source_csv_selected_columns=source_csv_selected_columns,\n            source_csv_header_renames=source_csv_header_renames,\n            source_attachments=safe_attachments,\n        )',
    "source-kind attachments argument",
)
replace_once(
    '''        prepared_source = _prepare_source_after_preflight(
            source_kind=source_kind,
            inline_source=inline_source,
            source_document_path=source_document_path,
            source_pdf_path=source_pdf_path,
            source_pdf_pages=safe_pdf_pages,
            source_image_path=source_image_path,
            source_csv_path=source_csv_path,
            source_csv_delimiter_profile=safe_csv_delimiter,
            source_csv_selected_columns=safe_csv_columns,
            source_csv_header_renames=safe_csv_renames,
        )

        selected_service =''',
    '''        if source_kind == "multiple":
            prepared_sources = tuple(
                _prepare_attachment_after_preflight(attachment)
                for attachment in safe_attachments
            )
            aggregate_source_characters = sum(
                len(source.text or "") for source in prepared_sources
            )
            if aggregate_source_characters > _MAX_SOURCE_CHARS:
                raise LocalWritingWorkflowValidationError(
                    "writing source attachments exceed the configured aggregate character limit"
                )
        else:
            prepared_source = _prepare_source_after_preflight(
                source_kind=source_kind,
                inline_source=inline_source,
                source_document_path=source_document_path,
                source_pdf_path=source_pdf_path,
                source_pdf_pages=safe_pdf_pages,
                source_image_path=source_image_path,
                source_csv_path=source_csv_path,
                source_csv_delimiter_profile=safe_csv_delimiter,
                source_csv_selected_columns=safe_csv_columns,
                source_csv_header_renames=safe_csv_renames,
            )
            prepared_sources = (
                (prepared_source,) if prepared_source.text is not None else ()
            )

        selected_service =''',
    "prepare multiple sources",
)
replace_once(
    '''        source_instruction_id: str | None = None
        source_instruction_ids: tuple[str, ...] = ()
        if prepared_source.text is not None:
            source_operation_id = _source_operation_id(safe_operation_id)
            self._require_unused_source_operation(source_operation_id)
            source_origin = InstructionOriginService(self.repository).create(
                title=f"Local writing {safe_mode} source",
                content=prepared_source.text,
                source=InstructionSource(
                    origin_class="external_content",
                    actor_type="extractor",
                    acquisition_method=_source_acquisition_method(prepared_source.kind),
                    source_identifier=source_operation_id,
                    parent_operation_id=source_operation_id,
                    session_id=conversation_id,
                    content_hash=_sha256_text(prepared_source.text),
                ),
                operation_id=source_operation_id,
                sensitivity=sensitivity,
            )
            source_instruction_id = source_origin.record_id
            source_instruction_ids = (source_origin.record_id,)
''',
    '''        source_instruction_ids_list: list[str] = []
        for index, prepared_source in enumerate(prepared_sources, start=1):
            if prepared_source.text is None:
                continue
            source_operation_id = (
                _source_operation_id(safe_operation_id)
                if len(prepared_sources) == 1
                else _attachment_source_operation_id(safe_operation_id, index)
            )
            self._require_unused_source_operation(source_operation_id)
            source_origin = InstructionOriginService(self.repository).create(
                title=(
                    f"Local writing {safe_mode} source"
                    if len(prepared_sources) == 1
                    else f"Local writing {safe_mode} attachment {index}"
                ),
                content=prepared_source.text,
                source=InstructionSource(
                    origin_class="external_content",
                    actor_type="extractor",
                    acquisition_method=_source_acquisition_method(prepared_source.kind),
                    source_identifier=source_operation_id,
                    parent_operation_id=source_operation_id,
                    session_id=conversation_id,
                    content_hash=_sha256_text(prepared_source.text),
                ),
                operation_id=source_operation_id,
                sensitivity=sensitivity,
            )
            source_instruction_ids_list.append(source_origin.record_id)
        source_instruction_ids = tuple(source_instruction_ids_list)
''',
    "origin loop",
)
replace_once(
    '''        return _result(
            mode=safe_mode,
            target_language=safe_target_language,
            source_instruction_id=source_instruction_id,
            prepared_source=prepared_source,
            selected_result=selected_result,
            bundle_result=bundle_result,
            local_result=local_result,
        )''',
    '''        return _result(
            mode=safe_mode,
            target_language=safe_target_language,
            source_kind=source_kind,
            source_instruction_ids=source_instruction_ids,
            prepared_sources=prepared_sources,
            selected_result=selected_result,
            bundle_result=bundle_result,
            local_result=local_result,
        )''',
    "result call",
)
replace_once(
    '    source_csv_selected_columns: object,\n    source_csv_header_renames: object,\n) -> WritingSourceKind:',
    '    source_csv_selected_columns: object,\n    source_csv_header_renames: object,\n    source_attachments: tuple[LocalWritingAttachment, ...],\n) -> WritingSourceKind:',
    "source-kind signature",
)
replace_once(
    '    has_csv = source_csv_path is not None\n    has_csv_options = (',
    '    has_csv = source_csv_path is not None\n    has_attachments = bool(source_attachments)\n    has_csv_options = (',
    "source kind has attachments",
)
replace_once(
    '''            or has_csv
            or has_csv_options
        ):
''',
    '''            or has_csv
            or has_csv_options
            or has_attachments
        ):
''',
    "draft attachment rejection",
)
replace_once(
    '''    if has_pdf_pages and not has_pdf:
        raise LocalWritingWorkflowValidationError(
            "PDF page selection requires a PDF primary source"
        )
    if has_csv_options and not has_csv:
        raise LocalWritingWorkflowValidationError("CSV options require a CSV primary source")
    if sum((has_inline, has_document, has_pdf, has_image, has_csv)) != 1:
''',
    '''    if has_attachments:
        if any((has_inline, has_document, has_pdf, has_pdf_pages, has_image, has_csv, has_csv_options)):
            raise LocalWritingWorkflowValidationError(
                "multiple attachments cannot be combined with legacy primary source arguments"
            )
        return "multiple"
    if has_pdf_pages and not has_pdf:
        raise LocalWritingWorkflowValidationError(
            "PDF page selection requires a PDF primary source"
        )
    if has_csv_options and not has_csv:
        raise LocalWritingWorkflowValidationError("CSV options require a CSV primary source")
    if sum((has_inline, has_document, has_pdf, has_image, has_csv)) != 1:
''',
    "multiple source kind branch",
)
replace_once(
    'def _source_acquisition_method(\n    source_kind: WritingSourceKind,\n) -> Literal["extraction", "ocr"]:\n    return "ocr" if source_kind == "ocr" else "extraction"\n',
    'def _source_acquisition_method(\n    source_kind: WritingSourceKind,\n) -> Literal["extraction", "ocr"]:\n    if source_kind == "multiple":\n        raise LocalWritingWorkflowValidationError("aggregate writing source has no acquisition method")\n    return "ocr" if source_kind == "ocr" else "extraction"\n',
    "aggregate acquisition guard",
)
insert_before = '\ndef _source_for_mode(mode: WritingMode, value: object) -> str | None:\n'
if text.count(insert_before) != 1:
    raise SystemExit("attachment helper insertion marker missing")
helpers = r'''

def _writing_attachments(value: object) -> tuple[LocalWritingAttachment, ...]:
    if isinstance(value, str | bytes) or not isinstance(value, Sequence):
        raise LocalWritingWorkflowValidationError("writing source attachments are invalid")
    attachments = tuple(value)
    if not attachments:
        return ()
    if len(attachments) < 2 or len(attachments) > _MAX_WRITING_ATTACHMENTS:
        raise LocalWritingWorkflowValidationError(
            "writing source attachments must contain between 2 and 4 items"
        )
    normalized: list[LocalWritingAttachment] = []
    for attachment in attachments:
        if not isinstance(attachment, LocalWritingAttachment):
            raise LocalWritingWorkflowValidationError("writing source attachment is invalid")
        if attachment.kind not in ("document", "pdf", "ocr", "csv"):
            raise LocalWritingWorkflowValidationError("writing source attachment kind is invalid")
        if not isinstance(attachment.path, Path):
            raise LocalWritingWorkflowValidationError("writing source attachment path is invalid")
        safe_pdf_pages = _pdf_page_selection(attachment.pdf_pages)
        safe_csv_delimiter = _csv_delimiter_profile(attachment.csv_delimiter_profile)
        safe_csv_columns = _csv_selected_columns(attachment.csv_selected_columns)
        safe_csv_renames = _attachment_header_renames(attachment.csv_header_renames)
        if attachment.kind != "pdf" and safe_pdf_pages:
            raise LocalWritingWorkflowValidationError(
                "PDF page selection requires a PDF attachment"
            )
        has_csv_options = (
            safe_csv_delimiter != "comma"
            or bool(safe_csv_columns)
            or bool(safe_csv_renames)
        )
        if attachment.kind != "csv" and has_csv_options:
            raise LocalWritingWorkflowValidationError(
                "CSV options require a CSV attachment"
            )
        normalized.append(
            LocalWritingAttachment(
                kind=attachment.kind,
                path=attachment.path,
                pdf_pages=safe_pdf_pages,
                csv_delimiter_profile=safe_csv_delimiter,
                csv_selected_columns=safe_csv_columns,
                csv_header_renames=safe_csv_renames,
            )
        )
    return tuple(normalized)


def _attachment_header_renames(value: object) -> tuple[tuple[str, str], ...]:
    if isinstance(value, str | bytes) or not isinstance(value, Sequence):
        raise LocalWritingWorkflowValidationError(
            "writing source attachment CSV header renames are invalid"
        )
    pairs = tuple(value)
    normalized: list[tuple[str, str]] = []
    for pair in pairs:
        if (
            isinstance(pair, str | bytes)
            or not isinstance(pair, Sequence)
            or len(pair) != 2
            or not isinstance(pair[0], str)
            or not isinstance(pair[1], str)
        ):
            raise LocalWritingWorkflowValidationError(
                "writing source attachment CSV header renames are invalid"
            )
        normalized.append((pair[0], pair[1]))
    return tuple(normalized)
'''
text = text.replace(insert_before, helpers + insert_before, 1)

insert_before = '\ndef _target_language_for_mode(mode: WritingMode, value: object) -> str | None:\n'
if text.count(insert_before) != 1:
    raise SystemExit("attachment preparation insertion marker missing")
preparer = r'''

def _prepare_attachment_after_preflight(
    attachment: LocalWritingAttachment,
) -> _PreparedWritingSource:
    return _prepare_source_after_preflight(
        source_kind=attachment.kind,
        inline_source=None,
        source_document_path=attachment.path if attachment.kind == "document" else None,
        source_pdf_path=attachment.path if attachment.kind == "pdf" else None,
        source_pdf_pages=attachment.pdf_pages,
        source_image_path=attachment.path if attachment.kind == "ocr" else None,
        source_csv_path=attachment.path if attachment.kind == "csv" else None,
        source_csv_delimiter_profile=attachment.csv_delimiter_profile,
        source_csv_selected_columns=attachment.csv_selected_columns,
        source_csv_header_renames=dict(attachment.csv_header_renames),
    )
'''
text = text.replace(insert_before, preparer + insert_before, 1)

replace_once(
    '''def _source_operation_id(operation_id: str) -> str:
    digest = hashlib.sha256(operation_id.encode("utf-8")).hexdigest()[:32]
    return f"imp063.source.{digest}"


def _sha256_text''',
    '''def _source_operation_id(operation_id: str) -> str:
    digest = hashlib.sha256(operation_id.encode("utf-8")).hexdigest()[:32]
    return f"imp063.source.{digest}"


def _attachment_source_operation_id(operation_id: str, index: int) -> str:
    digest = hashlib.sha256(operation_id.encode("utf-8")).hexdigest()[:32]
    return f"imp082.source.{digest}.{index:02d}"


def _sha256_text''',
    "attachment operation id",
)
replace_once(
    '''def _result(
    *,
    mode: WritingMode,
    target_language: str | None,
    source_instruction_id: str | None,
    prepared_source: _PreparedWritingSource,
    selected_result: SelectedWritingContextResult,
    bundle_result: ResumeBundleWritingContextResult,
    local_result: LocalConversationResult,
) -> LocalWritingWorkflowResult:
    document = prepared_source.document
    pdf = prepared_source.pdf
    ocr = prepared_source.ocr
    csv_result = prepared_source.csv
    return LocalWritingWorkflowResult(''',
    '''def _result(
    *,
    mode: WritingMode,
    target_language: str | None,
    source_kind: WritingSourceKind,
    source_instruction_ids: tuple[str, ...],
    prepared_sources: tuple[_PreparedWritingSource, ...],
    selected_result: SelectedWritingContextResult,
    bundle_result: ResumeBundleWritingContextResult,
    local_result: LocalConversationResult,
) -> LocalWritingWorkflowResult:
    single_source = prepared_sources[0] if len(prepared_sources) == 1 else None
    document = single_source.document if single_source is not None else None
    pdf = single_source.pdf if single_source is not None else None
    ocr = single_source.ocr if single_source is not None else None
    csv_result = single_source.csv if single_source is not None else None
    return LocalWritingWorkflowResult(''',
    "result signature",
)
replace_once(
    '''        source_instruction_id=source_instruction_id,
        source_instruction_count=1 if source_instruction_id is not None else 0,
        source_character_count=len(prepared_source.text) if prepared_source.text is not None else 0,
        source_kind=prepared_source.kind,
        source_document_kind=document.document_kind if document is not None else None,''',
    '''        source_instruction_id=(
            source_instruction_ids[0] if len(source_instruction_ids) == 1 else None
        ),
        source_instruction_count=len(source_instruction_ids),
        source_character_count=sum(len(source.text or "") for source in prepared_sources),
        source_kind=source_kind,
        source_instruction_ids=source_instruction_ids,
        source_kinds=tuple(
            cast(WritingAttachmentKind | Literal["inline"], source.kind)
            for source in prepared_sources
        ),
        source_character_counts=tuple(
            len(source.text or "") for source in prepared_sources
        ),
        source_content_sha256s=tuple(
            _sha256_text(source.text or "") for source in prepared_sources
        ),
        source_document_kind=document.document_kind if document is not None else None,''',
    "result source metadata",
)

path.write_text(text, encoding="utf-8")
