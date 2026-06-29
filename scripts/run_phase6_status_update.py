"""Run the Phase 6 status update with robust public-check edits."""

from __future__ import annotations

from pathlib import Path

from apply_phase6_status_after_imp057 import update_public_status, update_roadmap

CHECK = Path("scripts/check-public-site-status.mjs")


def replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise RuntimeError(f"unexpected public-check replacement count: {old!r}")
    return text.replace(old, new, 1)


def update_public_status_check() -> None:
    text = CHECK.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "    status.phase?.next_implementation === 57,",
        "    status.phase?.next_implementation === 58,",
    )
    text = replace_once(
        text,
        '  "project-status.json must mark Phase 6 in progress through IMP-056 with IMP-057 next",',
        '  "project-status.json must mark Phase 6 in progress through IMP-057 with IMP-058 next",',
    )
    text = replace_once(
        text,
        '  roadmap.includes("the next bounded Phase 6 implementation receives IMP-057 when its issue is opened"),',
        '  roadmap.includes("the next bounded implementation receives IMP-058 only when a new implementation issue is opened"),',
    )
    text = replace_once(
        text,
        '  "roadmap must identify IMP-057 as the next implementation identifier",',
        '  "roadmap must identify IMP-058 as the next unallocated implementation identifier",',
    )
    text = replace_once(
        text,
        '  roadmap.includes("The required order after IMP-056 is:"),',
        '  roadmap.includes("The required order after the IMP-057 harness merge is:"),',
    )
    text = replace_once(
        text,
        '  "roadmap must advance immediate work beyond IMP-056",',
        '  "roadmap must record the real-machine gate after IMP-057",',
    )
    marker = '''expect(
  roadmap.includes("### IMP-056 — Explicit loopback Ollama chat session capture"),
  "roadmap must record the IMP-056 explicit local capture path",
);
'''
    addition = marker + '''expect(
  roadmap.includes("### IMP-057 — Local-portability migration harness"),
  "roadmap must record the IMP-057 local-portability harness",
);
'''
    text = replace_once(text, marker, addition)
    CHECK.write_text(text, encoding="utf-8")


def main() -> int:
    update_roadmap()
    update_public_status()
    update_public_status_check()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
