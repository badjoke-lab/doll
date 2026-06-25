from __future__ import annotations
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def rep(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise RuntimeError(f"anchor mismatch in {path}: {old[:80]!r}")
    path.write_text(text.replace(old, new), encoding="utf-8")

def main() -> None:
    roadmap = ROOT / "docs/spec/09-development-roadmap.md"
    rep(roadmap, "- IMP-030 through IMP-040;", "- IMP-030 through IMP-041;")
    rep(roadmap,
        "and ProjectRecord v2 with v1 read compatibility, verified backup",
        "ProjectRecord v2 with v1 read compatibility, and WorkItemRecord v1 lifecycle and dependency integrity, verified backup")
    rep(roadmap,
        "- the next bounded Phase 4B implementation issue receives IMP-041;",
        "- IMP-041 adds WorkItemRecord v1 lifecycle, dependency, blocker, acceptance-criterion, and verification-state integrity;\n- the next bounded Phase 4B implementation issue receives IMP-042;")
    rep(roadmap, "Status: in progress through IMP-040.", "Status: in progress through IMP-041.")
    rep(roadmap,
        "- IMP-040 — ProjectRecord v2 with neutral ProjectRecord v1 read compatibility.\n",
        "- IMP-040 — ProjectRecord v2 with neutral ProjectRecord v1 read compatibility.\n- IMP-041 — WorkItemRecord v1 lifecycle and dependency integrity.\n")
    rep(roadmap,
'''1. WorkItemRecord lifecycle, dependencies, blockers, acceptance criteria, and verification state;
2. ProcedureRecord lifecycle, versioning, non-authority rule, validation, and rollback description;
3. ProjectCheckpointRecord basis revisions, deterministic fingerprint, confirmation, and stale detection;
4. deterministic `doll project status` view;
5. deterministic project-scoped Resume Bundle with manifest, checksums, machine-readable records, and generated HANDOFF.md;
6. package, backup, restore, fresh-process, hostile-import, and secret-safe output coverage;
7. PROJ-001 through PROJ-012 acceptance evidence.''',
'''1. ProcedureRecord lifecycle, versioning, non-authority rule, validation, and rollback description;
2. ProjectCheckpointRecord basis revisions, deterministic fingerprint, confirmation, and stale detection;
3. deterministic `doll project status` view;
4. deterministic project-scoped Resume Bundle with manifest, checksums, machine-readable records, and generated HANDOFF.md;
5. package, backup, restore, fresh-process, hostile-import, and secret-safe output coverage;
6. PROJ-001 through PROJ-012 acceptance evidence.''')
    status = ROOT / "website/project-status.json"
    rep(status, '"next_implementation": 41', '"next_implementation": 42')
    checker = ROOT / "scripts/check-public-site-status.mjs"
    rep(checker, "status.phase?.next_implementation === 41", "status.phase?.next_implementation === 42")
    rep(checker,
        "project-status.json must mark Phase 4B in progress from IMP-038 with IMP-041 next",
        "project-status.json must mark Phase 4B in progress from IMP-038 with IMP-042 next")
    rep(checker,
        "the next bounded Phase 4B implementation issue receives IMP-041",
        "the next bounded Phase 4B implementation issue receives IMP-042")
    rep(checker,
        "roadmap must identify IMP-041 as next after IMP-040",
        "roadmap must identify IMP-042 as next after IMP-041")

if __name__ == "__main__":
    main()
