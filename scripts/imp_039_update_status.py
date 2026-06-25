from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, found {count}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def main() -> None:
    roadmap = ROOT / "docs/spec/09-development-roadmap.md"
    replace_once(roadmap, "- IMP-030 through IMP-038;", "- IMP-030 through IMP-039;")
    replace_once(
        roadmap,
        "state-package v2 export with v1 read compatibility, verified backup",
        "state-package v2 export with v1 read compatibility and a versioned authoritative record registry, verified backup",
    )
    replace_once(
        roadmap,
        "- the next bounded Phase 4B implementation issue receives IMP-039;",
        "- IMP-039 adds the versioned authoritative record registry used by package export, manifest validation, typed-validator selection, and source-version inventory checks;\n"
        "- the next bounded Phase 4B implementation issue receives IMP-040;",
    )
    replace_once(
        roadmap,
        "Status: in progress through IMP-038.",
        "Status: in progress through IMP-039.",
    )
    replace_once(
        roadmap,
        "- IMP-038 — Doll State Package format v2 foundation and supported format v1 read compatibility.\n",
        "- IMP-038 — Doll State Package format v2 foundation and supported format v1 read compatibility.\n"
        "- IMP-039 — versioned authoritative record registry for package validation.\n",
    )
    replace_once(
        roadmap,
        "1. versioned authoritative record registry for package validation;\n"
        "2. ProjectRecord v2 while preserving readable ProjectRecord v1;\n"
        "3. WorkItemRecord lifecycle, dependencies, blockers, acceptance criteria, and verification state;\n"
        "4. ProcedureRecord lifecycle, versioning, non-authority rule, validation, and rollback description;\n"
        "5. ProjectCheckpointRecord basis revisions, deterministic fingerprint, confirmation, and stale detection;\n"
        "6. deterministic `doll project status` view;\n"
        "7. deterministic project-scoped Resume Bundle with manifest, checksums, machine-readable records, and generated HANDOFF.md;\n"
        "8. package, backup, restore, fresh-process, hostile-import, and secret-safe output coverage;\n"
        "9. PROJ-001 through PROJ-012 acceptance evidence.",
        "1. ProjectRecord v2 while preserving readable ProjectRecord v1;\n"
        "2. WorkItemRecord lifecycle, dependencies, blockers, acceptance criteria, and verification state;\n"
        "3. ProcedureRecord lifecycle, versioning, non-authority rule, validation, and rollback description;\n"
        "4. ProjectCheckpointRecord basis revisions, deterministic fingerprint, confirmation, and stale detection;\n"
        "5. deterministic `doll project status` view;\n"
        "6. deterministic project-scoped Resume Bundle with manifest, checksums, machine-readable records, and generated HANDOFF.md;\n"
        "7. package, backup, restore, fresh-process, hostile-import, and secret-safe output coverage;\n"
        "8. PROJ-001 through PROJ-012 acceptance evidence.",
    )

    status = ROOT / "website/project-status.json"
    replace_once(status, '"next_implementation": 39', '"next_implementation": 40')

    checker = ROOT / "scripts/check-public-site-status.mjs"
    replace_once(
        checker,
        "status.phase?.next_implementation === 39",
        "status.phase?.next_implementation === 40",
    )
    replace_once(
        checker,
        "project-status.json must mark Phase 4B in progress from IMP-038 with IMP-039 next",
        "project-status.json must mark Phase 4B in progress from IMP-038 with IMP-040 next",
    )
    replace_once(
        checker,
        "the next bounded Phase 4B implementation issue receives IMP-039",
        "the next bounded Phase 4B implementation issue receives IMP-040",
    )
    replace_once(
        checker,
        "roadmap must identify IMP-039 as next after IMP-038",
        "roadmap must identify IMP-040 as next after IMP-039",
    )


if __name__ == "__main__":
    main()
