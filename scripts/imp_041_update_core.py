from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise RuntimeError(f"unexpected anchor count in {path}: {old[:80]!r}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def main() -> None:
    registry = ROOT / "src/doll/state_package_registry.py"
    replace_once(
        registry,
        '''PACKAGE_RECORD_REGISTRIES: Mapping[int, AuthoritativeRecordRegistry] = MappingProxyType(
    {
        1: AuthoritativeRecordRegistry(1, _CURRENT_RECORD_CATEGORIES),
        2: AuthoritativeRecordRegistry(2, _CURRENT_RECORD_CATEGORIES),
    }
)
''',
        '''_V2_RECORD_CATEGORIES = (
    *_CURRENT_RECORD_CATEGORIES,
    AuthoritativeRecordCategory(
        "work_item",
        "records/work-items.jsonl",
        False,
        "work_item",
    ),
)

PACKAGE_RECORD_REGISTRIES: Mapping[int, AuthoritativeRecordRegistry] = MappingProxyType(
    {
        1: AuthoritativeRecordRegistry(1, _CURRENT_RECORD_CATEGORIES),
        2: AuthoritativeRecordRegistry(2, _V2_RECORD_CATEGORIES),
    }
)
''',
    )

    work_item = ROOT / "src/doll/work_item.py"
    replace_once(
        work_item,
        '''        work_status = _work_status(_required_string(record.metadata, "status"))
        priority = _priority(record.metadata.get("priority"))
''',
        '''        work_status = _work_status(_required_string(record.metadata, "status"))
        if work_status != "proposed" and record.provenance not in {
            "user-created",
            "user-confirmed",
        }:
            raise WorkItemValidationError("accepted work requires trusted provenance")
        priority = _priority(record.metadata.get("priority"))
''',
    )

    tests = ROOT / "tests/test_work_item.py"
    replace_once(tests, "import io\n", "")
    replace_once(
        tests,
        "from doll.state import StaleRevisionError\n",
        "from doll.state import StaleRevisionError\nfrom doll.state_repository import StateRepository\n",
    )
    replace_once(
        tests,
        "    WorkItemCorruptError,\n",
        "    WorkItemCorruptError,\n    WorkItemStatus,\n",
    )
    replace_once(
        tests,
        'def _project(repository: state.StateRepository, name: str = "Project") -> str:\n',
        'def _project(repository: StateRepository, name: str = "Project") -> str:\n',
    )
    replace_once(
        tests,
        '                    to_status=cast("str", target),\n',
        "                    to_status=cast(WorkItemStatus, target),\n",
    )


if __name__ == "__main__":
    main()
