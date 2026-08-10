from pathlib import Path

path = Path("tests/test_imp_082_multiple_writing_attachments.py")
text = path.read_text(encoding="utf-8")
marker = '''        with pytest.raises(LocalWritingWorkflowValidationError, match="attachments are invalid"):
            service.execute(
                mode="summarize",
                conversation_id=conversation_id,
                scope_type="conversation",
                scope_key="writing",
                request_text="Summarize.",
                source_attachments=cast(Sequence[LocalWritingAttachment], "bad"),
                operation_id="imp082.attachments.shape",
            )
        assert adapter.prompts == []
        assert _origin_count(repository) == before
'''
addition = '''        with pytest.raises(LocalWritingWorkflowValidationError, match="attachments are invalid"):
            service.execute(
                mode="summarize",
                conversation_id=conversation_id,
                scope_type="conversation",
                scope_key="writing",
                request_text="Summarize.",
                source_attachments=cast(Sequence[LocalWritingAttachment], "bad"),
                operation_id="imp082.attachments.shape",
            )
        with pytest.raises(LocalWritingWorkflowValidationError, match="source attachment is invalid"):
            _execute(
                service,
                conversation_id=conversation_id,
                attachments=(
                    cast(LocalWritingAttachment, object()),
                    LocalWritingAttachment(kind="document", path=second),
                ),
                operation_id="imp082.attachment.member.invalid",
            )
        with pytest.raises(LocalWritingWorkflowValidationError, match="PDF pages are invalid"):
            _execute(
                service,
                conversation_id=conversation_id,
                attachments=(
                    LocalWritingAttachment(
                        kind="pdf",
                        path=first,
                        pdf_pages=cast(tuple[int, ...], (True,)),
                    ),
                    LocalWritingAttachment(kind="document", path=second),
                ),
                operation_id="imp082.pdf.pages.type.invalid",
            )
        with pytest.raises(LocalWritingWorkflowValidationError, match="delimiter profile is invalid"):
            _execute(
                service,
                conversation_id=conversation_id,
                attachments=(
                    LocalWritingAttachment(
                        kind="csv",
                        path=first,
                        csv_delimiter_profile=cast(str, 1),
                    ),
                    LocalWritingAttachment(kind="document", path=second),
                ),
                operation_id="imp082.csv.delimiter.type.invalid",
            )
        with pytest.raises(LocalWritingWorkflowValidationError, match="selected columns are invalid"):
            _execute(
                service,
                conversation_id=conversation_id,
                attachments=(
                    LocalWritingAttachment(
                        kind="csv",
                        path=first,
                        csv_selected_columns=cast(tuple[str, ...], (1,)),
                    ),
                    LocalWritingAttachment(kind="document", path=second),
                ),
                operation_id="imp082.csv.columns.type.invalid",
            )
        with pytest.raises(
            LocalWritingWorkflowValidationError,
            match="attachment CSV header renames are invalid",
        ):
            _execute(
                service,
                conversation_id=conversation_id,
                attachments=(
                    LocalWritingAttachment(
                        kind="csv",
                        path=first,
                        csv_header_renames=cast(
                            tuple[tuple[str, str], ...],
                            (("name",),),
                        ),
                    ),
                    LocalWritingAttachment(kind="document", path=second),
                ),
                operation_id="imp082.csv.rename.shape.invalid",
            )
        assert adapter.prompts == []
        assert _origin_count(repository) == before
'''
if text.count(marker) != 1:
    raise SystemExit(f"coverage insertion marker count={text.count(marker)}")
path.write_text(text.replace(marker, addition, 1), encoding="utf-8")
