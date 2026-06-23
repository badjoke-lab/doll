#!/usr/bin/env python3
"""Apply the one-time WEB-008 homepage status markup migration."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "website/index.html"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one old block, found {count}")
    return text.replace(old, new, 1)


def main() -> None:
    text = INDEX.read_text(encoding="utf-8")

    text = replace_once(
        text,
        """      <p><strong>Current:</strong> <span id="project-current">Loading current implementation from GitHub.</span></p>
      <p><strong>Next:</strong> <span id="project-next">Loading next implementation from GitHub.</span></p>
""",
        """      <p><strong>Current:</strong> <span id="project-current">Loading current implementation from GitHub.</span></p>
      <p><strong>Last completed:</strong> <span id="project-last-completed">Loading the last completed implementation from GitHub.</span></p>
      <p><strong>Next:</strong> <span id="project-next">Loading next implementation from GitHub.</span></p>
""",
        "header activity",
    )

    text = replace_once(
        text,
        """      <p>
        <strong>Current implementation:</strong>
        <span id="development-current">Loading current implementation from GitHub.</span>
      </p>
      <p>
        <strong>Next implementation:</strong>
        <span id="development-next">Loading next implementation from GitHub.</span>
      </p>
""",
        """      <p>
        <strong>Current implementation:</strong>
        <span id="development-current">Loading current implementation from GitHub.</span>
      </p>
      <p>
        <strong>Last completed implementation:</strong>
        <span id="development-last-completed">Loading the last completed implementation from GitHub.</span>
      </p>
      <p>
        <strong>Next implementation:</strong>
        <span id="development-next">Loading next implementation from GitHub.</span>
      </p>
""",
        "development activity",
    )

    text = replace_once(
        text,
        """      <ol>
        <li>Phase 0 — Specification and principles — Complete</li>
        <li>Phase 1 — Local state foundation — Complete</li>
        <li>Phase 2 — Continuity, transfer, backup, and restore — Complete</li>
        <li>Phase 3 — Safety boundary — In progress</li>
        <li>Phase 4A — AI environment portability foundation — Planned</li>
        <li>Phase 4B — Project continuity foundation — Planned</li>
        <li>Phase 5 — Local runtime and model integration — Planned</li>
        <li>Phase 6 — Local AI portability and daily-use integration — Planned</li>
        <li>Phase 7 — Optional cloud and multiple models — Planned</li>
        <li>Phase 8 — Tools and external services — Planned</li>
        <li>Phase 9 — Distribution, encryption, and long-term operation — Planned</li>
      </ol>
""",
        """      <ol>
        <li data-roadmap-phase="0">Phase 0 — Specification and principles — <span data-roadmap-state>Loading</span></li>
        <li data-roadmap-phase="1">Phase 1 — Local state foundation — <span data-roadmap-state>Loading</span></li>
        <li data-roadmap-phase="2">Phase 2 — Continuity, transfer, backup, and restore — <span data-roadmap-state>Loading</span></li>
        <li data-roadmap-phase="3">Phase 3 — Safety boundary — <span data-roadmap-state>Loading</span></li>
        <li data-roadmap-phase="4A">Phase 4A — AI environment portability foundation — <span data-roadmap-state>Loading</span></li>
        <li data-roadmap-phase="4B">Phase 4B — Project continuity foundation — <span data-roadmap-state>Loading</span></li>
        <li data-roadmap-phase="5">Phase 5 — Local runtime and model integration — <span data-roadmap-state>Loading</span></li>
        <li data-roadmap-phase="6">Phase 6 — Local AI portability and daily-use integration — <span data-roadmap-state>Loading</span></li>
        <li data-roadmap-phase="7">Phase 7 — Optional cloud and multiple models — <span data-roadmap-state>Loading</span></li>
        <li data-roadmap-phase="8">Phase 8 — Tools and external services — <span data-roadmap-state>Loading</span></li>
        <li data-roadmap-phase="9">Phase 9 — Distribution, encryption, and long-term operation — <span data-roadmap-state>Loading</span></li>
      </ol>
""",
        "roadmap status",
    )

    INDEX.write_text(text, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
