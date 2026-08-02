from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise RuntimeError(f"expected exactly one match in {path}")
    path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


doctor = ROOT / "src/doll/doctor.py"
replace_once(
    doctor,
    '                    "Use a verified backup in an empty compatible target when the workspace identity cannot be recovered.",',
    '                    "Use a verified backup in an empty compatible target when the "\n                    "workspace identity cannot be recovered.",',
)
replace_once(
    doctor,
    "        name for name in WORKSPACE_DIRECTORIES if not _safe_workspace_directory(workspace.root, name)",
    "        name\n        for name in WORKSPACE_DIRECTORIES\n        if not _safe_workspace_directory(workspace.root, name)",
)
replace_once(
    doctor,
    '                    "Restore a verified workspace backup into an empty compatible target when required directories are unavailable.",',
    '                    "Restore a verified workspace backup into an empty compatible target "\n                    "when required directories are unavailable.",',
)
replace_once(
    doctor,
    '                        "Stop the diagnostic run and reopen the workspace through the read-only recovery path.",',
    '                        "Stop the diagnostic run and reopen the workspace through the "\n                        "read-only recovery path.",',
)
replace_once(
    doctor,
    '                        "Use a compatible doll version or perform the documented migration outside doctor mode.",',
    '                        "Use a compatible doll version or perform the documented migration "\n                        "outside doctor mode.",',
)
replace_once(
    doctor,
    '                    "Verify the most recent backup before attempting restore into an empty compatible target.",',
    '                    "Verify the most recent backup before attempting restore into an empty "\n                    "compatible target.",',
)

tests = ROOT / "tests/test_imp_072_doctor.py"
replace_once(
    tests,
    '    record_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8")',
    '    record_path.write_text(\n        json.dumps(payload, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8"\n    )',
)

print("IMP-072 style normalization applied")
