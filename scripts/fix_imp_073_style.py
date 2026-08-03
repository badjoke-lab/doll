from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise RuntimeError(f"expected exactly one match in {path}: {old!r}")
    path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


replace_once(
    ROOT / "src/doll/local_search.py",
    '        "".join("?" if ord(character) < 32 or ord(character) == 127 else character for character in value)\n',
    '        "".join(\n'
    '            "?"\n'
    '            if ord(character) < 32 or ord(character) == 127\n'
    '            else character\n'
    '            for character in value\n'
    '        )\n',
)
replace_once(
    ROOT / "tests/test_imp_073_local_search.py",
    '        title="Straße ＡＩ 計画",\n',
    '        title="Straße \\uFF21\\uFF29 計画",\n',
)

print("IMP-073 style fixes applied")
