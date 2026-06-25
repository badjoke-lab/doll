from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def rep(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise RuntimeError(f"status anchor mismatch in {path}: {old[:80]!r}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def main() -> None:
    roadmap = ROOT / "docs/spec/09-development-roadmap.md"
    rep(roadmap, "- IMP-030 through IMP-042;", "- IMP-030 through IMP-043;")
    rep(
        roadmap,
        "and ProcedureRecord v1 lifecycle and non-authority guarantees, verified backup",
        "ProcedureRecord v1 lifecycle and non-authority guarantees, and ProjectCheckpointRecord v1 confirmation and freshness, verified backup",
    )
    rep(
        roadmap,
        "- the next bounded Phase 4B implementation issue receives IMP-043;",
        "- IMP-043 adds ProjectCheckpointRecord v1 basis revisions, deterministic fingerprinting, trusted confirmation, and stale detection;\n"
        "- the next bounded Phase 4B implementation issue receives IMP-044;",
    )
    rep(
        roadmap,
        "Status: in progress through IMP-042.",
        "Status: in progress through IMP-043.",
    )
    rep(
        roadmap,
        "- IMP-042 — ProcedureRecord v1 lifecycle and non-authority guarantees.\n",
        "- IMP-042 — ProcedureRecord v1 lifecycle and non-authority guarantees.\n"
        "- IMP-043 — ProjectCheckpointRecord v1 confirmation and freshness.\n",
    )
    rep(
        roadmap,
        '''1. ProjectCheckpointRecord basis revisions, deterministic fingerprint, confirmation, and stale detection;
2. deterministic `doll project status` view;
3. deterministic project-scoped Resume Bundle with manifest, checksums, machine-readable records, and generated HANDOFF.md;
4. package, backup, restore, fresh-process, hostile-import, and secret-safe output coverage;
5. PROJ-001 through PROJ-012 acceptance evidence.''',
        '''1. deterministic `doll project status` view;
2. deterministic project-scoped Resume Bundle with manifest, checksums, machine-readable records, and generated HANDOFF.md;
3. package, backup, restore, fresh-process, hostile-import, and secret-safe output coverage;
4. PROJ-001 through PROJ-012 acceptance evidence.''',
    )

    status = ROOT / "website/project-status.json"
    rep(status, '"next_implementation": 43', '"next_implementation": 44')

    checker = ROOT / "scripts/check-public-site-status.mjs"
    rep(
        checker,
        "status.phase?.next_implementation === 43",
        "status.phase?.next_implementation === 44",
    )
    rep(
        checker,
        "project-status.json must mark Phase 4B in progress from IMP-038 with IMP-043 next",
        "project-status.json must mark Phase 4B in progress from IMP-038 with IMP-044 next",
    )
    rep(
        checker,
        "the next bounded Phase 4B implementation issue receives IMP-043",
        "the next bounded Phase 4B implementation issue receives IMP-044",
    )
    rep(
        checker,
        "roadmap must identify IMP-043 as next after IMP-042",
        "roadmap must identify IMP-044 as next after IMP-043",
    )


if __name__ == "__main__":
    main()
