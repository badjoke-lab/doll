from __future__ import annotations

from pathlib import Path

path = Path("tests/test_explicit_writing_context.py")
text = path.read_text(encoding="utf-8")

replacements = (
    (
        "from doll.memory import ConfirmedMemoryService\n",
        "from doll.memory import ConfirmedMemoryInfo, ConfirmedMemoryService\n",
    ),
    (
        "from doll.project_state import ProjectService\n",
        "from doll.project_state import ProjectInfo, ProjectService\n",
    ),
    (
        ") -> tuple[object, object]:\n",
        ") -> tuple[ConfirmedMemoryInfo, ProjectInfo]:\n",
    ),
)
for old, new in replacements:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"ERROR: expected one test match, found {count}: {old!r}")
    text = text.replace(old, new)

old_block = '''        invalid_calls = (
            {"memory_ids": (archived.record_id,)},
            {"memory_ids": (secret.record_id,)},
            {"project_ids": (archived_project.project_id,)},
            {"memory_ids": (str(uuid4()),)},
            {"memory_ids": (archived_project.project_id,)},
            {"memory_ids": (active.record_id, active.record_id)},
            {"memory_ids": tuple(str(uuid4()) for _ in range(9))},
        )
        for index, selected in enumerate(invalid_calls):
            with pytest.raises(LocalWritingWorkflowValidationError):
                service.execute(
                    mode="draft",
                    conversation_id=conversation_id,
                    scope_type="conversation",
                    scope_key="writing-context",
                    request_text="This must not execute.",
                    operation_id=f"imp065.invalid.selection.{index}",
                    **selected,
                )
'''
new_block = '''        def assert_invalid(
            index: int,
            *,
            memory_ids: tuple[str, ...] = (),
            project_ids: tuple[str, ...] = (),
        ) -> None:
            with pytest.raises(LocalWritingWorkflowValidationError):
                service.execute(
                    mode="draft",
                    conversation_id=conversation_id,
                    scope_type="conversation",
                    scope_key="writing-context",
                    request_text="This must not execute.",
                    operation_id=f"imp065.invalid.selection.{index}",
                    memory_ids=memory_ids,
                    project_ids=project_ids,
                )

        assert_invalid(0, memory_ids=(archived.record_id,))
        assert_invalid(1, memory_ids=(secret.record_id,))
        assert_invalid(2, project_ids=(archived_project.project_id,))
        assert_invalid(3, memory_ids=(str(uuid4()),))
        assert_invalid(4, memory_ids=(archived_project.project_id,))
        assert_invalid(5, memory_ids=(active.record_id, active.record_id))
        assert_invalid(6, memory_ids=tuple(str(uuid4()) for _ in range(9)))
'''
if text.count(old_block) != 1:
    raise SystemExit("ERROR: invalid-selection test block anchor missing")
text = text.replace(old_block, new_block)
path.write_text(text, encoding="utf-8")
print("IMP-065 test typing updates applied")
