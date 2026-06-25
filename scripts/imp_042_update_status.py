from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise RuntimeError(f"anchor mismatch in {path}: {old[:100]!r}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def main() -> None:
    roadmap = ROOT / "docs/spec/09-development-roadmap.md"
    replace_once(roadmap, "- IMP-030 through IMP-041;", "- IMP-030 through IMP-042;")
    replace_once(
        roadmap,
        "and WorkItemRecord v1 lifecycle and dependency integrity, verified backup",
        "WorkItemRecord v1 lifecycle and dependency integrity, and ProcedureRecord v1 lifecycle and non-authority guarantees, verified backup",
    )
    replace_once(
        roadmap,
        "- the next bounded Phase 4B implementation issue receives IMP-042;",
        "- IMP-042 adds ProcedureRecord v1 lifecycle, versioning, validation, rollback description, and non-authority guarantees;\n"
        "- the next bounded Phase 4B implementation issue receives IMP-043;",
    )
    replace_once(
        roadmap,
        "Status: in progress through IMP-041.",
        "Status: in progress through IMP-042.",
    )
    replace_once(
        roadmap,
        "- IMP-041 — WorkItemRecord v1 lifecycle and dependency integrity.\n",
        "- IMP-041 — WorkItemRecord v1 lifecycle and dependency integrity.\n"
        "- IMP-042 — ProcedureRecord v1 lifecycle and non-authority guarantees.\n",
    )
    replace_once(
        roadmap,
        '''1. ProcedureRecord lifecycle, versioning, non-authority rule, validation, and rollback description;
2. ProjectCheckpointRecord basis revisions, deterministic fingerprint, confirmation, and stale detection;
3. deterministic `doll project status` view;
4. deterministic project-scoped Resume Bundle with manifest, checksums, machine-readable records, and generated HANDOFF.md;
5. package, backup, restore, fresh-process, hostile-import, and secret-safe output coverage;
6. PROJ-001 through PROJ-012 acceptance evidence.''',
        '''1. ProjectCheckpointRecord basis revisions, deterministic fingerprint, confirmation, and stale detection;
2. deterministic `doll project status` view;
3. deterministic project-scoped Resume Bundle with manifest, checksums, machine-readable records, and generated HANDOFF.md;
4. package, backup, restore, fresh-process, hostile-import, and secret-safe output coverage;
5. PROJ-001 through PROJ-012 acceptance evidence.''',
    )

    status = ROOT / "website/project-status.json"
    replace_once(status, '"next_implementation": 42', '"next_implementation": 43')

    checker = ROOT / "scripts/check-public-site-status.mjs"
    replace_once(
        checker,
        "status.phase?.next_implementation === 42",
        "status.phase?.next_implementation === 43",
    )
    replace_once(
        checker,
        "project-status.json must mark Phase 4B in progress from IMP-038 with IMP-042 next",
        "project-status.json must mark Phase 4B in progress from IMP-038 with IMP-043 next",
    )
    replace_once(
        checker,
        "the next bounded Phase 4B implementation issue receives IMP-042",
        "the next bounded Phase 4B implementation issue receives IMP-043",
    )
    replace_once(
        checker,
        "roadmap must identify IMP-042 as next after IMP-041",
        "roadmap must identify IMP-043 as next after IMP-042",
    )


if __name__ == "__main__":
    main()
