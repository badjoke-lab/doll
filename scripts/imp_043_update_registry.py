from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise RuntimeError(f"anchor mismatch in {path}: {old[:80]!r}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def main() -> None:
    registry = ROOT / "src/doll/state_package_registry.py"
    replace_once(
        registry,
        '''    AuthoritativeRecordCategory(
        "procedure",
        "records/procedures.jsonl",
        False,
        "procedure",
    ),
)
''',
        '''    AuthoritativeRecordCategory(
        "procedure",
        "records/procedures.jsonl",
        False,
        "procedure",
    ),
    AuthoritativeRecordCategory(
        "project_checkpoint",
        "records/project-checkpoints.jsonl",
        False,
        "project_checkpoint",
    ),
)
''',
    )


if __name__ == "__main__":
    main()
