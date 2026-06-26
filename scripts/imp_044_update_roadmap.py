from __future__ import annotations

from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "docs/spec/09-development-roadmap.md"


def rep(text: str, old: str, new: str) -> str:
    if old not in text:
        raise RuntimeError(f"roadmap anchor missing: {old[:80]!r}")
    return text.replace(old, new, 1)


def main() -> None:
    text = PATH.read_text(encoding="utf-8")
    text = rep(text, "- IMP-030 through IMP-043;", "- IMP-030 through IMP-044;")
    text = rep(
        text,
        "and ProjectCheckpointRecord v1 confirmation and freshness, verified backup",
        "ProjectCheckpointRecord v1 confirmation and freshness, and deterministic derived project status, verified backup",
    )
    text = rep(
        text,
        "- the next bounded Phase 4B implementation issue receives IMP-044;",
        "- IMP-044 adds deterministic read-only derived project status and fresh-process CLI inspection;\n- the next bounded Phase 4B implementation issue receives IMP-045;",
    )
    text = rep(
        text,
        "Status: in progress through IMP-043.",
        "Status: in progress through IMP-044.",
    )
    text = rep(
        text,
        "- IMP-043 — ProjectCheckpointRecord v1 confirmation and freshness.\n",
        "- IMP-043 — ProjectCheckpointRecord v1 confirmation and freshness.\n- IMP-044 — deterministic read-only derived project status.\n",
    )
    text = rep(
        text,
        "1. deterministic `doll project status` view;\n2. deterministic project-scoped Resume Bundle with manifest, checksums, machine-readable records, and generated HANDOFF.md;\n3. package, backup, restore, fresh-process, hostile-import, and secret-safe output coverage;\n4. PROJ-001 through PROJ-012 acceptance evidence.",
        "1. deterministic project-scoped Resume Bundle with manifest, checksums, machine-readable records, and generated HANDOFF.md;\n2. package, backup, restore, fresh-process, hostile-import, and secret-safe output coverage;\n3. PROJ-001 through PROJ-012 acceptance evidence.",
    )
    PATH.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
