from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def rep(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise RuntimeError(f"anchor mismatch in {path}: {old[:80]!r}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def main() -> None:
    registry_tests = ROOT / "tests/test_state_package_registry.py"
    rep(
        registry_tests,
        '''    assert version_two.record_types - version_one.record_types == {
        "work_item",
        "procedure",
    }
''',
        '''    assert version_two.record_types - version_one.record_types == {
        "work_item",
        "procedure",
        "project_checkpoint",
    }
''',
    )
    rep(
        registry_tests,
        '''    assert version_two.optional_member_paths - version_one.optional_member_paths == {
        "records/work-items.jsonl",
        "records/procedures.jsonl",
    }
''',
        '''    assert version_two.optional_member_paths - version_one.optional_member_paths == {
        "records/work-items.jsonl",
        "records/procedures.jsonl",
        "records/project-checkpoints.jsonl",
    }
''',
    )
    rep(
        registry_tests,
        '            categories.append("project_checkpoint")\n',
        '            categories.append("future_category")\n',
    )
    rep(
        registry_tests,
        '    members[f"{package.PACKAGE_ROOT}/records/project-checkpoints.jsonl"] = b""\n',
        '    members[f"{package.PACKAGE_ROOT}/records/future-category.jsonl"] = b""\n',
    )

    v1_tests = ROOT / "tests/test_state_package_v2.py"
    rep(
        v1_tests,
        '    members.pop(f"{package.PACKAGE_ROOT}/records/procedures.jsonl")\n',
        '    members.pop(f"{package.PACKAGE_ROOT}/records/procedures.jsonl")\n'
        '    members.pop(f"{package.PACKAGE_ROOT}/records/project-checkpoints.jsonl")\n',
    )
    rep(
        v1_tests,
        '    included.remove("procedure")\n',
        '    included.remove("procedure")\n'
        '    included.remove("project_checkpoint")\n',
    )
    rep(
        v1_tests,
        '    cast(dict[str, int], manifest["record_counts"]).pop("procedure")\n',
        '    cast(dict[str, int], manifest["record_counts"]).pop("procedure")\n'
        '    cast(dict[str, int], manifest["record_counts"]).pop("project_checkpoint")\n',
    )
    rep(
        v1_tests,
        '    cast(dict[str, int], manifest["omitted_secret_counts"]).pop("procedure")\n',
        '    cast(dict[str, int], manifest["omitted_secret_counts"]).pop("procedure")\n'
        '    cast(dict[str, int], manifest["omitted_secret_counts"]).pop("project_checkpoint")\n',
    )


if __name__ == "__main__":
    main()
