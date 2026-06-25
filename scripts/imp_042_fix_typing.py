from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise RuntimeError(f"typing anchor mismatch in {path}: {old[:100]!r}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def main() -> None:
    state_package = ROOT / "src/doll/state_package.py"
    replace_once(
        state_package,
        '''            for key in ("supersedes_id", "superseded_by_id"):
                linked_id = _metadata_optional_id(metadata, key)
                if linked_id is not None:
                    _require_link_type(records, linked_id, "procedure")
''',
        '''            for key in ("supersedes_id", "superseded_by_id"):
                optional_link_id = _metadata_optional_id(metadata, key)
                if optional_link_id is not None:
                    _require_link_type(records, optional_link_id, "procedure")
''',
    )

    tests = ROOT / "tests/test_procedure.py"
    replace_once(
        tests,
        "from typing import cast\n",
        "from typing import TypedDict, cast\n",
    )
    replace_once(
        tests,
        '''def _complete_values() -> dict[str, object]:
''',
        '''class CompleteValues(TypedDict):
    prerequisites: tuple[str, ...]
    ordered_steps: tuple[str, ...]
    required_capability_ids: tuple[str, ...]
    expected_outputs: tuple[str, ...]
    validation_steps: tuple[str, ...]
    rollback_steps: tuple[str, ...]
    platform_constraints: tuple[str, ...]


def _complete_values() -> CompleteValues:
''',
    )


if __name__ == "__main__":
    main()
