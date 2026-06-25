from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise RuntimeError(f"{path.name}: expected one match")
    path.write_text(text.replace(old, new), encoding="utf-8")


def main() -> None:
    roadmap = ROOT / "docs/spec/09-development-roadmap.md"
    replace_once(roadmap, "- IMP-030 through IMP-037;", "- IMP-030 through IMP-038;")
    replace_once(
        roadmap,
        "decisions, state-package export/import, verified backup",
        "decisions, state-package v2 export with v1 read compatibility, verified backup",
    )
    replace_once(
        roadmap,
        "- the next implementation issue receives IMP-038 when its first bounded Phase 4B slice is scheduled;",
        "- IMP-038 establishes Doll State Package format v2 for new exports while preserving supported format v1 inspection, verification, planning, and import;\n"
        "- the next bounded Phase 4B implementation issue receives IMP-039;",
    )
    replace_once(
        roadmap,
        "Required implementation slices, with identifiers assigned only when scheduled:\n\n"
        "1. Doll State Package format v2 foundation and supported v1 read compatibility;\n"
        "2. versioned authoritative record registry for package validation;",
        "Status: in progress through IMP-038.\n\n"
        "Completed implementation slices:\n\n"
        "- IMP-038 — Doll State Package format v2 foundation and supported format v1 read compatibility.\n\n"
        "Remaining implementation slices, with identifiers assigned only when scheduled:\n\n"
        "1. versioned authoritative record registry for package validation;",
    )
    for old, new in (
        ("3. ProjectRecord v2", "2. ProjectRecord v2"),
        ("4. WorkItemRecord", "3. WorkItemRecord"),
        ("5. ProcedureRecord", "4. ProcedureRecord"),
        ("6. ProjectCheckpointRecord", "5. ProjectCheckpointRecord"),
        ("7. deterministic `doll project status`", "6. deterministic `doll project status`"),
        ("8. deterministic project-scoped Resume Bundle", "7. deterministic project-scoped Resume Bundle"),
        ("9. package, backup, restore", "8. package, backup, restore"),
        ("10. PROJ-001 through PROJ-012", "9. PROJ-001 through PROJ-012"),
    ):
        replace_once(roadmap, old, new)

    status = ROOT / "website/project-status.json"
    replace_once(status, '"state": "ready"', '"state": "in_progress"')
    replace_once(status, '"started_by_implementation": null', '"started_by_implementation": 38')
    replace_once(status, '"next_implementation": 38', '"next_implementation": 39')
    replace_once(status, '"last_reviewed": "2026-06-25"', '"last_reviewed": "2026-06-26"')

    checker = ROOT / "scripts/check-public-site-status.mjs"
    replace_once(checker, 'status.phase?.state === "ready"', 'status.phase?.state === "in_progress"')
    replace_once(checker, "status.phase?.started_by_implementation === null", "status.phase?.started_by_implementation === 38")
    replace_once(checker, "status.phase?.next_implementation === 38", "status.phase?.next_implementation === 39")
    replace_once(checker, "project-status.json must mark Phase 4B ready with IMP-038 next", "project-status.json must mark Phase 4B in progress from IMP-038 with IMP-039 next")
    replace_once(checker, "the next implementation issue after IMP-037 is IMP-038", "the next bounded Phase 4B implementation issue receives IMP-039")
    replace_once(checker, "roadmap must identify IMP-038 as next", "roadmap must identify IMP-039 as next after IMP-038")


if __name__ == "__main__":
    main()
