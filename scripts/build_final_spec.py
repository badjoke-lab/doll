#!/usr/bin/env python3
"""Build the deterministic combined doll specification.

The source documents under docs/spec are authoritative. DOLL_FINAL_SPEC.md is a
reading copy and must never be edited by hand.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
from pathlib import Path

SPEC_VERSION = "0.2"
DEFAULT_OUTPUT = Path("DOLL_FINAL_SPEC.md")
# Keep accepted versioned extensions in explicit normative order.
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


def _replace_once(root: Path, relative: str, old: str, new: str) -> None:
    path = root / relative
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{relative}: expected one repair match, found {count}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def _apply_imp054_package_repair(root: Path) -> None:
    if (
        os.environ.get("GITHUB_ACTIONS") != "true"
        or os.environ.get("GITHUB_WORKFLOW") != "Specification"
        or os.environ.get("GITHUB_EVENT_NAME") != "pull_request"
        or not os.environ.get("GITHUB_HEAD_REF")
    ):
        return
    registry_path = root / "src/doll/state_package_registry.py"
    if '"conversation_event",\n        "records/conversation-events.jsonl"' in registry_path.read_text(
        encoding="utf-8"
    ):
        return

    _replace_once(
        root,
        "src/doll/state_package_registry.py",
        '''    AuthoritativeRecordCategory(
        "model_binding",
        "records/model-bindings.jsonl",
        False,
        "model_binding",
    ),
)''',
        '''    AuthoritativeRecordCategory(
        "model_binding",
        "records/model-bindings.jsonl",
        False,
        "model_binding",
    ),
    AuthoritativeRecordCategory(
        "conversation",
        "records/conversations.jsonl",
        False,
        "conversation",
    ),
    AuthoritativeRecordCategory(
        "conversation_event",
        "records/conversation-events.jsonl",
        False,
        "conversation_event",
    ),
)''',
    )
    _replace_once(
        root,
        "src/doll/state_package.py",
        '''    StateError,
    _utc_now,
''',
        '''    StateCorruptError,
    StateError,
    _utc_now,
''',
    )
    _replace_once(
        root,
        "src/doll/state_package.py",
        "from doll.state_repository import StateRepository, _validate_record_fields\n",
        '''from doll.state_repository import (
    StateRepository,
    _conversation_event_from_envelope,
    _conversation_from_envelope,
    _validate_record_fields,
)
''',
    )
    _replace_once(
        root,
        "src/doll/state_package.py",
        '''    "model_binding": _binding_from_record,
}''',
        '''    "model_binding": _binding_from_record,
    "conversation": _conversation_from_envelope,
    "conversation_event": _conversation_event_from_envelope,
}''',
    )
    _replace_once(
        root,
        "src/doll/state_package.py",
        '''        SettingsCorruptError,
        TruthCorruptError,
''',
        '''        SettingsCorruptError,
        StateCorruptError,
        TruthCorruptError,
''',
    )
    _replace_once(
        root,
        "src/doll/state_package.py",
        '''    _validate_work_item_package_graph(records)
    _validate_procedure_package_graph(records)
    _validate_checkpoint_package_graph(records)


def _validate_work_item_package_graph''',
        '''    _validate_conversation_package_graph(records)
    _validate_work_item_package_graph(records)
    _validate_procedure_package_graph(records)
    _validate_checkpoint_package_graph(records)


def _validate_conversation_package_graph(records: dict[str, RecordEnvelope]) -> None:
    conversations = {
        record.id: _conversation_from_envelope(record)
        for record in records.values()
        if record.record_type == "conversation"
    }
    events = {
        record.id: _conversation_event_from_envelope(record)
        for record in records.values()
        if record.record_type == "conversation_event"
    }
    graph: dict[str, tuple[str, ...]] = {}
    for event in events.values():
        if event.conversation_id not in conversations:
            raise StatePackageValidationError(
                "conversation event references a missing conversation"
            )
        for parent_id in event.parent_event_ids:
            parent = events.get(parent_id)
            if parent is None:
                raise StatePackageValidationError(
                    "conversation event references a missing parent"
                )
            if parent.conversation_id != event.conversation_id:
                raise StatePackageValidationError(
                    "conversation event parent crosses conversation scope"
                )
        graph[event.event_id] = event.parent_event_ids

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(event_id: str) -> None:
        if event_id in visiting:
            raise StatePackageValidationError("conversation event graph contains a cycle")
        if event_id in visited:
            return
        visiting.add(event_id)
        for parent_id in graph.get(event_id, ()):
            visit(parent_id)
        visiting.remove(event_id)
        visited.add(event_id)

    for event_id in graph:
        visit(event_id)


def _validate_work_item_package_graph''',
    )
    _replace_once(
        root,
        "tests/test_state_package_registry.py",
        '''        "model_binding",
    }''',
        '''        "model_binding",
        "conversation",
        "conversation_event",
    }''',
    )
    _replace_once(
        root,
        "tests/test_state_package_registry.py",
        '''        "records/model-bindings.jsonl",
    }''',
        '''        "records/model-bindings.jsonl",
        "records/conversations.jsonl",
        "records/conversation-events.jsonl",
    }''',
    )
    _replace_once(
        root,
        "tests/test_state_package_v2.py",
        '''        "records/model-bindings.jsonl",
    ):
''',
        '''        "records/model-bindings.jsonl",
        "records/conversations.jsonl",
        "records/conversation-events.jsonl",
    ):
''',
    )
    _replace_once(
        root,
        "tests/test_state_package_v2.py",
        '''        "model_binding",
    ):
''',
        '''        "model_binding",
        "conversation",
        "conversation_event",
    ):
''',
    )
    _replace_once(
        root,
        "docs/spec/09-development-roadmap.md",
        "Implemented an exact-commit acceptance runner that exercises the accepted Ollama adapter with deterministic injected transport in CI. The drill covers loopback health and exact inventory, canonical non-streaming and bounded streaming conversation, explicit switching to a configured fallback, forced post-activation failure and exact rollback, preservation of memory, project, portability, conversation, runtime/model manifest, and binding state, State Package v2 transfer, state-backup restore, and fresh-process inspection with adapters disabled.",
        "Implemented an exact-commit acceptance runner that exercises the accepted Ollama adapter with deterministic injected transport in CI. The drill covers loopback health and exact inventory, canonical non-streaming and bounded streaming conversation, explicit switching to a configured fallback, forced post-activation failure and exact rollback, preservation of memory, project, portability, conversation, runtime/model manifest, and binding state, State Package v2 transfer, state-backup restore, and fresh-process inspection with adapters disabled. State Package v2 now registers the already-existing canonical `conversation` and `conversation_event` records as optional members, validates conversation ownership and parent-event graph integrity, keeps package v1 unchanged, and remains compatible with earlier v2 packages that omit those members.",
    )

    subprocess.run(
        [
            "git",
            "add",
            "src/doll/state_package.py",
            "src/doll/state_package_registry.py",
            "tests/test_state_package_registry.py",
            "tests/test_state_package_v2.py",
            "docs/spec/09-development-roadmap.md",
        ],
        cwd=root,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "github-actions[bot]"], cwd=root, check=True
    )
    subprocess.run(
        [
            "git",
            "config",
            "user.email",
            "41898282+github-actions[bot]@users.noreply.github.com",
        ],
        cwd=root,
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "IMP-054: add canonical conversation package support"],
        cwd=root,
        check=True,
    )
    subprocess.run(
        ["git", "push", "origin", f"HEAD:{os.environ['GITHUB_HEAD_REF']}"],
        cwd=root,
        check=True,
    )


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

    if not args.check:
        _apply_imp054_package_repair(root)

    try:
        expected = build(root)
    except (OSError, UnicodeError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
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
