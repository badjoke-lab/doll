from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

updater_path = ROOT / "scripts/apply_imp_076.py"
updater = updater_path.read_text(encoding="utf-8")
if not updater.startswith("# ruff: noqa: E501\n"):
    updater_path.write_text(
        "# ruff: noqa: E501\n" + updater,
        encoding="utf-8",
        newline="\n",
    )

test_path = ROOT / "tests/test_imp_076_local_pdf.py"
tests = test_path.read_text(encoding="utf-8")
old = '            reader = _FakeReader(("text",))\n'
if tests.count(old) != 1:
    raise RuntimeError("expected one unused synthetic reader fixture")
test_path.write_text(
    tests.replace(old, "", 1),
    encoding="utf-8",
    newline="\n",
)
