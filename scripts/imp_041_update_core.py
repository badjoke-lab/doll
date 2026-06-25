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
    replace_once(
        work_item,
        '''        if safe_status == "completed":
            started_at = started_at or timestamp
            completed_at = timestamp
        elif safe_status != "completed":
            completed_at = None
''',
        '''        if safe_status == "completed":
            started_at = started_at or timestamp
            completed_at = timestamp
        else:
            completed_at = None
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
        'def _project(repository: state.StateRepository, name: str = "Project") -> str:\n',
        'def _project(repository: StateRepository, name: str = "Project") -> str:\n',
    )
    replace_once(
        tests,
        '                    to_status=cast("str", target),\n',
        "                    to_status=target,\n",
    )
    replace_once(
        tests,
        '        created_at="2026-06-26T04:00:00Z",\n',
        '        created_at="2026-06-25T20:00:00Z",\n',
    )

    registry_tests = ROOT / "tests/test_state_package_registry.py"
    replace_once(
        registry_tests,
        '''    assert version_one.record_types == version_two.record_types
    assert version_one.required_member_paths == version_two.required_member_paths
    assert version_one.optional_member_paths == version_two.optional_member_paths
''',
        '''    assert version_two.record_types - version_one.record_types == {"work_item"}
    assert version_one.required_member_paths == version_two.required_member_paths
    assert version_two.optional_member_paths - version_one.optional_member_paths == {
        "records/work-items.jsonl"
    }
''',
    )
    replace_once(
        registry_tests,
        '            categories.append("work_item")\n',
        '            categories.append("procedure")\n',
    )
    replace_once(
        registry_tests,
        '    members[f"{package.PACKAGE_ROOT}/records/work-items.jsonl"] = b""\n',
        '    members[f"{package.PACKAGE_ROOT}/records/procedures.jsonl"] = b""\n',
    )


if __name__ == "__main__":
    main()
