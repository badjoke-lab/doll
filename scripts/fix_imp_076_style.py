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

checker_path = ROOT / "scripts/check-public-site-status.mjs"
checker = checker_path.read_text(encoding="utf-8")
old_heading = '''expect(
  roadmap.includes("### IMP-075 — Explicit local CSV inspection and transformation"),
  "roadmap must record the IMP-075 local-CSV boundary",
);
'''
new_heading = old_heading + '''expect(
  roadmap.includes("### IMP-076 — Optional local PDF text extraction adapter"),
  "roadmap must record the IMP-076 local-PDF boundary",
);
'''
if checker.count(old_heading) != 1:
    raise RuntimeError("expected one IMP-075 roadmap checker block")
checker = checker.replace(old_heading, new_heading, 1)
old_next = (
    'roadmap.includes("the next bounded implementation receives IMP-076 only when a new '
    'implementation issue is opened")'
)
new_next = (
    'roadmap.includes("the next bounded implementation receives IMP-077 only when a new '
    'implementation issue is opened")'
)
if checker.count(old_next) != 1:
    raise RuntimeError("expected one old next-implementation roadmap assertion")
checker = checker.replace(old_next, new_next, 1)
old_message = (
    '"roadmap must identify IMP-076 as the next unallocated implementation identifier"'
)
new_message = (
    '"roadmap must identify IMP-077 as the next unallocated implementation identifier"'
)
if checker.count(old_message) != 1:
    raise RuntimeError("expected one old next-implementation checker message")
checker_path.write_text(
    checker.replace(old_message, new_message, 1),
    encoding="utf-8",
    newline="\n",
)
