from __future__ import annotations

from pathlib import Path


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

    start = text.index("def update_writing_context() -> None:\n")
    end = text.index("\ndef update_local_writing() -> None:\n", start)
    segment = text[start:end]
    lines = segment.splitlines()
    matches: list[int] = []

    for index, line in enumerate(lines):
        if line != "    replace_once(":
            continue
        nearby = lines[index + 1 : index + 10]
        if any("project_ids: tuple[str, ...]" in candidate for candidate in nearby):
            matches.append(index)

    if len(matches) != 2:
        raise SystemExit(
            "expected two duplicated dataclass replacement calls inside "
            f"update_writing_context, found {len(matches)}"
        )

    lines[matches[0]] = "    replace_first("
    corrected_segment = "\n".join(lines)
    corrected = text[:start] + corrected_segment + text[end:]
    path.write_text(corrected, encoding="utf-8")
    print("IMP-066 helper scope corrected")


if __name__ == "__main__":
    main()
