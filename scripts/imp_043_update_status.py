from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(text: str, old: str, new: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"required status text is missing: {old[:100]!r}")
    return text.replace(old, new, 1)


def main() -> None:
    roadmap_path = ROOT / "docs/spec/09-development-roadmap.md"
    roadmap = roadmap_path.read_text(encoding="utf-8")
    roadmap = replace_once(
        roadmap,
        "- IMP-030 through IMP-042;",
        "- IMP-030 through IMP-043;",
    )
    roadmap = replace_once(
        roadmap,
        "ProcedureRecord v1 lifecycle and non-authority guarantees, verified backup",
        "ProcedureRecord v1 lifecycle and non-authority guarantees, "
        "and ProjectCheckpointRecord v1 confirmation and freshness, verified backup",
    )
    roadmap = replace_once(
        roadmap,
        "- the next bounded Phase 4B implementation issue receives IMP-043;",
        "- IMP-043 adds ProjectCheckpointRecord v1 basis revisions, deterministic "
        "fingerprinting, trusted confirmation, and stale detection;\n"
        "- the next bounded Phase 4B implementation issue receives IMP-044;",
    )
    roadmap = replace_once(
        roadmap,
        "Status: in progress through IMP-042.",
        "Status: in progress through IMP-043.",
    )
    roadmap = replace_once(
        roadmap,
        "- IMP-042 — ProcedureRecord v1 lifecycle and non-authority guarantees.\n",
        "- IMP-042 — ProcedureRecord v1 lifecycle and non-authority guarantees.\n"
        "- IMP-043 — ProjectCheckpointRecord v1 confirmation and freshness.\n",
    )
    remaining_pattern = re.compile(
        r"1\. ProjectCheckpointRecord basis revisions, deterministic fingerprint, "
        r"confirmation, and stale detection;\n"
        r"2\. deterministic `doll project status` view;\n"
        r"3\. deterministic project-scoped Resume Bundle with manifest, checksums, "
        r"machine-readable records, and generated HANDOFF\.md;\n"
        r"4\. package, backup, restore, fresh-process, hostile-import, and secret-safe "
        r"output coverage;\n"
        r"5\. PROJ-001 through PROJ-012 acceptance evidence\."
    )
    replacement = (
        "1. deterministic `doll project status` view;\n"
        "2. deterministic project-scoped Resume Bundle with manifest, checksums, "
        "machine-readable records, and generated HANDOFF.md;\n"
        "3. package, backup, restore, fresh-process, hostile-import, and secret-safe "
        "output coverage;\n"
        "4. PROJ-001 through PROJ-012 acceptance evidence."
    )
    if replacement not in roadmap:
        roadmap, count = remaining_pattern.subn(replacement, roadmap, count=1)
        if count != 1:
            raise RuntimeError("remaining Phase 4B sequence could not be updated")
    roadmap_path.write_text(roadmap, encoding="utf-8")

    status_path = ROOT / "website/project-status.json"
    status = status_path.read_text(encoding="utf-8")
    status = replace_once(
        status,
        '"next_implementation": 43',
        '"next_implementation": 44',
    )
    status_path.write_text(status, encoding="utf-8")

    checker_path = ROOT / "scripts/check-public-site-status.mjs"
    checker = checker_path.read_text(encoding="utf-8")
    checker = replace_once(
        checker,
        "status.phase?.next_implementation === 43",
        "status.phase?.next_implementation === 44",
    )
    checker = replace_once(
        checker,
        "project-status.json must mark Phase 4B in progress from IMP-038 with IMP-043 next",
        "project-status.json must mark Phase 4B in progress from IMP-038 with IMP-044 next",
    )
    checker = replace_once(
        checker,
        "the next bounded Phase 4B implementation issue receives IMP-043",
        "the next bounded Phase 4B implementation issue receives IMP-044",
    )
    checker = replace_once(
        checker,
        "roadmap must identify IMP-043 as next after IMP-042",
        "roadmap must identify IMP-044 as next after IMP-043",
    )
    checker_path.write_text(checker, encoding="utf-8")


if __name__ == "__main__":
    main()
