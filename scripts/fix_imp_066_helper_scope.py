from __future__ import annotations

import ast
from pathlib import Path


def _target_calls(tree: ast.AST) -> list[ast.Call]:
    function = next(
        (
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and node.name == "update_writing_context"
        ),
        None,
    )
    if function is None:
        raise SystemExit("update_writing_context function was not found")

    result: list[ast.Call] = []
    for node in ast.walk(function):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != "replace_once":
            continue
        if len(node.args) < 3:
            continue
        old = node.args[1]
        new = node.args[2]
        if not isinstance(old, ast.Constant) or not isinstance(old.value, str):
            continue
        if not isinstance(new, ast.Constant) or not isinstance(new.value, str):
            continue
        if not old.value.startswith(
            "    project_ids: tuple[str, ...]\n"
            "    memory_revisions: tuple[int, ...]\n"
        ):
            continue
        if "    decision_ids: tuple[str, ...]\n" not in new.value:
            continue
        result.append(node)
    return sorted(result, key=lambda item: item.lineno)


def main() -> None:
    path = Path("scripts/apply_imp_066_decision_context.py")
    text = path.read_text(encoding="utf-8")

    append_marker = "def append_once(path: Path, marker: str, addition: str) -> None:\n"
    replace_first_function = '''def replace_first(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count < 1:
        raise SystemExit(
            f"{path}: expected at least one replacement target, found {count}"
        )
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


'''

    if "def replace_first(" not in text:
        if text.count(append_marker) != 1:
            raise SystemExit("append_once marker was not found exactly once")
        text = text.replace(append_marker, replace_first_function + append_marker, 1)

    tree = ast.parse(text, filename=str(path))
    calls = _target_calls(tree)
    if len(calls) != 2:
        raise SystemExit(
            "expected two duplicated dataclass replacement calls, "
            f"found {len(calls)}"
        )

    lines = text.splitlines()
    first_line_index = calls[0].lineno - 1
    if lines[first_line_index] != "    replace_once(":
        raise SystemExit("first target call did not start with replace_once")
    lines[first_line_index] = "    replace_first("

    corrected = "\n".join(lines) + "\n"
    ast.parse(corrected, filename=str(path))
    path.write_text(corrected, encoding="utf-8")
    print("IMP-066 helper corrected with AST-scoped targeting")


if __name__ == "__main__":
    main()
