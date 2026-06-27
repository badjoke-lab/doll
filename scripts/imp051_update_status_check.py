from __future__ import annotations

from pathlib import Path

path = Path("scripts/check-public-site-status.mjs")
text = path.read_text(encoding="utf-8")

old_phase = '''  status.phase?.id === "5" &&
    status.phase?.name === "Local runtime and model integration" &&
    status.phase?.state === "in_progress" &&
    status.phase?.started_by_implementation === 48 &&
    status.phase?.next_implementation === 51,
  "project-status.json must mark Phase 5 in progress from IMP-048 with IMP-051 next",
'''
new_phase = '''  status.phase?.id === "5" &&
    status.phase?.name === "Local runtime and model integration" &&
    status.phase?.state === "in_progress" &&
    status.phase?.started_by_implementation === 48 &&
    status.phase?.next_implementation === 52,
  "project-status.json must mark Phase 5 in progress from IMP-048 with IMP-052 next",
'''

old_roadmap = '''expect(
  roadmap.includes("canonical local conversation receives IMP-051 when opened"),
  "roadmap must identify IMP-051 as the next implementation identifier",
);
'''
new_roadmap = '''expect(
  roadmap.includes("IMP-051 adds the first canonical non-streaming local conversation path"),
  "roadmap must record the IMP-051 canonical local conversation path",
);
expect(
  roadmap.includes("The required order after IMP-051 is:"),
  "roadmap must advance immediate work beyond IMP-051",
);
'''

for label, old, new in (
    ("phase expectation", old_phase, new_phase),
    ("roadmap expectation", old_roadmap, new_roadmap),
):
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label} expected one match, found {count}")
    text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
