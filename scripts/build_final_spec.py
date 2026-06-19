#!/usr/bin/env python3
"""Build the deterministic combined doll specification.

The source documents under docs/spec are authoritative. DOLL_FINAL_SPEC.md is a
reading copy and must never be edited by hand.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

SPEC_VERSION = "0.2"
DEFAULT_OUTPUT = Path("DOLL_FINAL_SPEC.md")
SOURCE_FILES = (
    Path("docs/spec/00-index.md"),
    Path("docs/spec/00-decisions-baseline.md"),
    Path("docs/spec/01-product-and-continuity-contract.md"),
    Path("docs/spec/02-architecture-and-data-flow.md"),
    Path("docs/spec/03-doll-state-memory-and-storage.md"),
    Path("docs/spec/03a-ai-environment-portability.md"),
    Path("docs/spec/03b-project-continuity-and-resumption.md"),
    Path("docs/spec/04-security-permissions-and-threat-model.md"),
    Path("docs/spec/05-model-vault-lifecycle-evaluation.md"),
    Path("docs/spec/06-platform-install-update-and-recovery.md"),
    Path("docs/spec/07-release-scope-and-profiles.md"),
    Path("docs/spec/08-acceptance-and-continuity-tests.md"),
    Path("docs/spec/08a-ai-environment-portability-acceptance.md"),
    Path("docs/spec/08b-project-continuity-acceptance.md"),
    Path("docs/spec/09-development-roadmap.md"),
)

HEADER = """# DOLL FINAL SPECIFICATION

> **Generated file — do not edit directly.**
>
> The authoritative sources are the Markdown files under `docs/spec/`.
> Regenerate this file with `python scripts/build_final_spec.py`.

**Specification set version:** {version}  
**Generation:** deterministic; no timestamp is embedded

## Included source documents

{source_list}

---
"""


def repository_root() -> Path:
    return Path(__file__).resolve().parents[1]


def normalize_text(path: Path) -> str:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError(f"UTF-8 BOM is not allowed: {path}")
    text = raw.decode("utf-8")
    return text.replace("\r\n", "\n").replace("\r", "\n").rstrip() + "\n"


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build(root: Path) -> str:
    missing = [str(path) for path in SOURCE_FILES if not (root / path).is_file()]
    if missing:
        raise FileNotFoundError("Missing specification source files: " + ", ".join(missing))

    sections: list[str] = []
    source_lines: list[str] = []

    for relative in SOURCE_FILES:
        text = normalize_text(root / relative)
        source_lines.append(f"- `{relative.as_posix()}` — SHA-256 `{digest(text)}`")
        sections.append(
            "\n".join(
                (
                    f"<!-- BEGIN SOURCE: {relative.as_posix()} -->",
                    text.rstrip(),
                    f"<!-- END SOURCE: {relative.as_posix()} -->",
                )
            )
        )

    header = HEADER.format(version=SPEC_VERSION, source_list="\n".join(source_lines)).rstrip()
    return header + "\n\n" + "\n\n---\n\n".join(sections) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output path relative to repository root (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail when the committed output is missing or stale; do not modify files.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = repository_root()
    output = args.output if args.output.is_absolute() else root / args.output

    try:
        expected = build(root)
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"spec build failed: {exc}", file=sys.stderr)
        return 2

    if args.check:
        if not output.is_file():
            print(f"generated specification is missing: {output}", file=sys.stderr)
            return 1
        try:
            current = normalize_text(output)
        except (OSError, UnicodeError, ValueError) as exc:
            print(f"cannot read generated specification: {exc}", file=sys.stderr)
            return 2
        if current != expected:
            print(
                "generated specification is stale; run "
                "`python scripts/build_final_spec.py` and commit the result",
                file=sys.stderr,
            )
            return 1
        print(f"generated specification is current: {output.relative_to(root)}")
        return 0

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(expected, encoding="utf-8", newline="\n")
    print(f"wrote {output.relative_to(root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
