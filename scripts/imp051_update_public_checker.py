from pathlib import Path

path = Path("scripts/check-public-site-status.mjs")
text = path.read_text(encoding="utf-8")
replacements = (
    (
        "status.phase?.next_implementation === 51",
        "status.phase?.next_implementation === 52",
    ),
    (
        "project-status.json must mark Phase 5 in progress from IMP-048 with IMP-051 next",
        "project-status.json must mark Phase 5 in progress from IMP-048 with IMP-052 next",
    ),
    (
        "canonical local conversation receives IMP-051 when opened",
        "IMP-051 adds the first canonical non-streaming local conversation path",
    ),
    (
        "roadmap must identify IMP-051 as the next implementation identifier",
        "roadmap must record the IMP-051 canonical local conversation path",
    ),
)
for old, new in replacements:
    if old not in text:
        raise SystemExit(f"missing checker replacement target: {old}")
    text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")
