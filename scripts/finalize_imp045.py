#!/usr/bin/env python3
"""One-shot branch finalizer for IMP-045.

This script is removed by the workflow that runs it. It reconstructs reviewed
source and test files, advances roadmap/public status metadata, and regenerates
the deterministic combined specification.
"""

from __future__ import annotations

import base64
import json
import re
import subprocess
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

RESUME_BUNDLE_ZB64 = "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"

HARDENING_TEST_ZB64 = "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"


def write_payload(relative: str, encoded: str) -> None:
    target = ROOT / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(zlib.decompress(base64.b64decode(encoded)))


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one match in {path}: {old!r}; found {count}")
    path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


def patch_existing_tests() -> None:
    path = ROOT / "tests/test_resume_bundle.py"
    text = path.read_text(encoding="utf-8")
    text, count = re.subn(
        r"\n    secret = work\.create\(.*?\n    \)\n    procedure =",
        "\n    procedure =",
        text,
        count=1,
        flags=re.DOTALL,
    )
    if count != 1:
        raise RuntimeError("could not remove invalid secret-sensitivity fixture")
    text = text.replace('        "secret": secret.work_item_id,\n', "")
    text = text.replace('    assert b"SECRET BUNDLE TEXT" not in entire_bundle\n', "")
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_roadmap() -> None:
    path = ROOT / "docs/spec/09-development-roadmap.md"
    replace_once(path, "- IMP-030 through IMP-044;", "- IMP-030 through IMP-045;")
    replace_once(
        path,
        "ProjectCheckpointRecord v1 confirmation and freshness, and deterministic derived project status, verified backup",
        "ProjectCheckpointRecord v1 confirmation and freshness, deterministic derived project status, and deterministic project-scoped Resume Bundle export, verified backup",
    )
    replace_once(
        path,
        "- IMP-044 adds deterministic read-only derived project status and fresh-process CLI inspection;\n- the next bounded Phase 4B implementation issue receives IMP-045;",
        "- IMP-044 adds deterministic read-only derived project status and fresh-process CLI inspection;\n- IMP-045 adds deterministic project-scoped Resume Bundle export, generated HANDOFF.md, and checksum verification;\n- the next bounded Phase 4B implementation issue receives IMP-046;",
    )
    replace_once(
        path,
        "Status: in progress through IMP-044.",
        "Status: in progress through IMP-045.",
    )
    replace_once(
        path,
        "- IMP-044 — deterministic read-only derived project status.\n\nRemaining implementation slices",
        "- IMP-044 — deterministic read-only derived project status.\n- IMP-045 — deterministic project-scoped Resume Bundle.\n\nRemaining implementation slices",
    )
    replace_once(
        path,
        "1. deterministic project-scoped Resume Bundle with manifest, checksums, machine-readable records, and generated HANDOFF.md;\n2. package, backup, restore, fresh-process, hostile-import, and secret-safe output coverage;\n3. PROJ-001 through PROJ-012 acceptance evidence.",
        "1. package, backup, restore, fresh-process, hostile-import, and secret-safe output coverage;\n2. PROJ-001 through PROJ-012 acceptance evidence.",
    )


def patch_public_status() -> None:
    path = ROOT / "website/project-status.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if data["phase"]["next_implementation"] != 45:
        raise RuntimeError("unexpected public next implementation")
    data["phase"]["next_implementation"] = 46
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n")

    check = ROOT / "scripts/check-public-site-status.mjs"
    replace_once(
        check,
        "status.phase?.next_implementation === 45,\n  \"project-status.json must mark Phase 4B in progress from IMP-038 with IMP-045 next\"",
        "status.phase?.next_implementation === 46,\n  \"project-status.json must mark Phase 4B in progress from IMP-038 with IMP-046 next\"",
    )
    replace_once(
        check,
        'roadmap.includes("the next bounded Phase 4B implementation issue receives IMP-045"),\n  "roadmap must identify IMP-045 as next after IMP-044"',
        'roadmap.includes("the next bounded Phase 4B implementation issue receives IMP-046"),\n  "roadmap must identify IMP-046 as next after IMP-045"',
    )


def main() -> None:
    write_payload("src/doll/resume_bundle.py", RESUME_BUNDLE_ZB64)
    write_payload("tests/test_resume_bundle_hardening.py", HARDENING_TEST_ZB64)
    patch_existing_tests()
    patch_roadmap()
    patch_public_status()
    subprocess.run(
        ["python", "scripts/build_final_spec.py"],
        cwd=ROOT,
        check=True,
    )


if __name__ == "__main__":
    main()
