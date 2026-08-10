from pathlib import Path

path = Path("tests/test_imp_082_multiple_writing_attachments.py")
text = path.read_text(encoding="utf-8")

replacements = {
    "from doll.local_conversation import LocalConversationService\n": (
        "from doll.local_conversation import LocalConversationService\n"
        "from doll.local_document import LocalDocumentResult, read_local_document\n"
    ),
    "    LocalWritingWorkflowService,\n    LocalWritingWorkflowValidationError,\n": (
        "    LocalWritingWorkflowResult,\n"
        "    LocalWritingWorkflowService,\n"
        "    LocalWritingWorkflowValidationError,\n"
    ),
    "    target_language: str | None = None,\n):\n": (
        "    target_language: str | None = None,\n"
        ") -> LocalWritingWorkflowResult:\n"
    ),
    "    original = local_writing_module.read_local_document\n\n    def counted_read(path: Path):\n": (
        "    original = read_local_document\n\n"
        "    def counted_read(path: Path) -> LocalDocumentResult:\n"
    ),
    "    monkeypatch.setattr(local_writing_module, \"read_local_document\", counted_read)\n": (
        "    monkeypatch.setattr(\"doll.local_writing.read_local_document\", counted_read)\n"
    ),
    "        assert _origin_count(repository) == before + 4\n": (
        "        assert len(set(result.source_instruction_ids)) == 4\n"
        "        assert all(\n"
        "            InstructionOriginService(repository).get(record_id).data_only is True\n"
        "            for record_id in result.source_instruction_ids\n"
        "        )\n"
    ),
    "        service = _service(repository, adapter)\n        before = _origin_count(repository)\n\n        with pytest.raises(LocalWritingWorkflowValidationError, match=\"between 2 and 4\"):\n": (
        "        service = _service(repository, adapter)\n\n"
        "        with pytest.raises(LocalWritingWorkflowValidationError, match=\"between 2 and 4\"):\n"
    ),
}
for old, new in replacements.items():
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"focused-fix marker count={count}: {old!r}")
    text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")
