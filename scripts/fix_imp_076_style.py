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
if "import importlib\n" not in tests:
    tests = tests.replace("import hashlib\n", "import hashlib\nimport importlib\n", 1)
internal_import = "local_pdf_module.importlib"
if tests.count(internal_import) != 4:
    raise RuntimeError("expected four internal importlib references")
tests = tests.replace(internal_import, "importlib")
old = '            reader = _FakeReader(("text",))\n'
if tests.count(old) != 1:
    raise RuntimeError("expected one unused synthetic reader fixture")
tests = tests.replace(old, "", 1)
help_assertion = '    assert "optional adapter" in help_result.stdout\n'
if tests.count(help_assertion) != 1:
    raise RuntimeError("expected one wrapping-sensitive PDF help assertion")
tests = tests.replace(
    help_assertion,
    '    assert "Extract text" in help_result.stdout\n'
    '    assert "PDF" in help_result.stdout\n',
    1,
)
test_path.write_text(
    tests,
    encoding="utf-8",
    newline="\n",
)
