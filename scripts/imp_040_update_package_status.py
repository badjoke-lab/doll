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
    state_package = ROOT / "src/doll/state_package.py"
    replace_once(
        state_package,
        '''        elif record.record_type == "project":
            for linked_id in _metadata_id_list(metadata, "decision_ids"):
                _require_link_type(records, linked_id, "decision")
            for linked_id in _metadata_id_list(metadata, "memory_ids"):
                _require_link_type(records, linked_id, "memory")
            for linked_id in _metadata_id_list(metadata, "artifact_ids"):
                _require_link_type(records, linked_id, "artifact")
''',
        '''        elif record.record_type == "project":
            for linked_id in _metadata_id_list(metadata, "decision_ids"):
                _require_link_type(records, linked_id, "decision")
            for linked_id in _metadata_id_list(metadata, "memory_ids"):
                _require_link_type(records, linked_id, "memory")
            for linked_id in _metadata_id_list(metadata, "artifact_ids"):
                _require_link_type(records, linked_id, "artifact")
            if record.schema_version == 2:
                for linked_id in _metadata_id_list(
                    metadata,
                    "governing_policy_ids",
                ):
                    _require_link_type(records, linked_id, "policy")
''',
    )

    roadmap = ROOT / "docs/spec/09-development-roadmap.md"
    replace_once(roadmap, "- IMP-030 through IMP-039;", "- IMP-030 through IMP-040;")
    replace_once(
        roadmap,
        "state-package v2 export with v1 read compatibility and a versioned authoritative record registry, verified backup",
        "state-package v2 export with v1 read compatibility, a versioned authoritative record registry, and ProjectRecord v2 with v1 read compatibility, verified backup",
    )
    replace_once(
        roadmap,
        "- the next bounded Phase 4B implementation issue receives IMP-040;",
        "- IMP-040 adds ProjectRecord v2 charters and preserves neutral ProjectRecord v1 read compatibility;\n"
        "- the next bounded Phase 4B implementation issue receives IMP-041;",
    )
    replace_once(
        roadmap,
        "Status: in progress through IMP-039.",
        "Status: in progress through IMP-040.",
    )
    replace_once(
        roadmap,
        "- IMP-039 — versioned authoritative record registry for package validation.\n",
        "- IMP-039 — versioned authoritative record registry for package validation.\n"
        "- IMP-040 — ProjectRecord v2 with neutral ProjectRecord v1 read compatibility.\n",
    )
    replace_once(
        roadmap,
        "1. ProjectRecord v2 while preserving readable ProjectRecord v1;\n"
        "2. WorkItemRecord lifecycle, dependencies, blockers, acceptance criteria, and verification state;\n"
        "3. ProcedureRecord lifecycle, versioning, non-authority rule, validation, and rollback description;\n"
        "4. ProjectCheckpointRecord basis revisions, deterministic fingerprint, confirmation, and stale detection;\n"
        "5. deterministic `doll project status` view;\n"
        "6. deterministic project-scoped Resume Bundle with manifest, checksums, machine-readable records, and generated HANDOFF.md;\n"
        "7. package, backup, restore, fresh-process, hostile-import, and secret-safe output coverage;\n"
        "8. PROJ-001 through PROJ-012 acceptance evidence.",
        "1. WorkItemRecord lifecycle, dependencies, blockers, acceptance criteria, and verification state;\n"
        "2. ProcedureRecord lifecycle, versioning, non-authority rule, validation, and rollback description;\n"
        "3. ProjectCheckpointRecord basis revisions, deterministic fingerprint, confirmation, and stale detection;\n"
        "4. deterministic `doll project status` view;\n"
        "5. deterministic project-scoped Resume Bundle with manifest, checksums, machine-readable records, and generated HANDOFF.md;\n"
        "6. package, backup, restore, fresh-process, hostile-import, and secret-safe output coverage;\n"
        "7. PROJ-001 through PROJ-012 acceptance evidence.",
    )

    status = ROOT / "website/project-status.json"
    replace_once(status, '"next_implementation": 40', '"next_implementation": 41')

    checker = ROOT / "scripts/check-public-site-status.mjs"
    replace_once(
        checker,
        "status.phase?.next_implementation === 40",
        "status.phase?.next_implementation === 41",
    )
    replace_once(
        checker,
        "project-status.json must mark Phase 4B in progress from IMP-038 with IMP-040 next",
        "project-status.json must mark Phase 4B in progress from IMP-038 with IMP-041 next",
    )
    replace_once(
        checker,
        "the next bounded Phase 4B implementation issue receives IMP-040",
        "the next bounded Phase 4B implementation issue receives IMP-041",
    )
    replace_once(
        checker,
        "roadmap must identify IMP-040 as next after IMP-039",
        "roadmap must identify IMP-041 as next after IMP-040",
    )


if __name__ == "__main__":
    main()
