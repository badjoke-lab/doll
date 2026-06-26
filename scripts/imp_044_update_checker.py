from pathlib import Path

path = Path(__file__).resolve().parents[1] / "scripts/check-public-site-status.mjs"
text = path.read_text(encoding="utf-8")
replacements = (
    ("status.phase?.next_implementation === 44", "status.phase?.next_implementation === 45"),
    ("project-status.json must mark Phase 4B in progress from IMP-038 with IMP-044 next", "project-status.json must mark Phase 4B in progress from IMP-038 with IMP-045 next"),
    ("the next bounded Phase 4B implementation issue receives IMP-044", "the next bounded Phase 4B implementation issue receives IMP-045"),
    ("roadmap must identify IMP-044 as next after IMP-043", "roadmap must identify IMP-045 as next after IMP-044"),
)
for old, new in replacements:
    if old not in text:
        raise RuntimeError(f"checker anchor missing: {old}")
    text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")
