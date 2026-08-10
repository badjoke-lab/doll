from pathlib import Path

path = Path("src/doll/local_writing.py")
text = path.read_text(encoding="utf-8")
old = '''        source_instruction_ids_list: list[str] = []
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
'''
new = '''        source_operation_ids = tuple(
            (
                _source_operation_id(safe_operation_id)
                if len(prepared_sources) == 1
                else _attachment_source_operation_id(safe_operation_id, index)
            )
            for index in range(1, len(prepared_sources) + 1)
        )
        for source_operation_id in source_operation_ids:
            self._require_unused_source_operation(source_operation_id)

        source_instruction_ids_list: list[str] = []
        for index, (prepared_source, source_operation_id) in enumerate(
            zip(prepared_sources, source_operation_ids, strict=True),
            start=1,
        ):
            if prepared_source.text is None:
                continue
            source_origin = InstructionOriginService(self.repository).create(
'''
if text.count(old) != 1:
    raise SystemExit(f"atomic origin marker count={text.count(old)}")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
