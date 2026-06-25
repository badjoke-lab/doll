from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise RuntimeError(f"anchor mismatch in {path}: {old[:100]!r}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def main() -> None:
    registry = ROOT / "src/doll/state_package_registry.py"
    replace_once(
        registry,
        '''    AuthoritativeRecordCategory(
        "work_item",
        "records/work-items.jsonl",
        False,
        "work_item",
    ),
)
''',
        '''    AuthoritativeRecordCategory(
        "work_item",
        "records/work-items.jsonl",
        False,
        "work_item",
    ),
    AuthoritativeRecordCategory(
        "procedure",
        "records/procedures.jsonl",
        False,
        "procedure",
    ),
)
''',
    )

    procedure = ROOT / "src/doll/procedure.py"
    replace_once(
        procedure,
        '''            actor_type,
            _validate_audit_token("action", action, 120),
''',
        '''            _audit_actor(actor_type),
            _validate_audit_token("action", action, 120),
''',
    )
    replace_once(
        procedure,
        '''def _draft_provenance(actor_type: ProcedureActor) -> RecordProvenance:
''',
        '''def _audit_actor(actor_type: ProcedureActor) -> str:
    return "system" if actor_type == "importer" else actor_type


def _draft_provenance(actor_type: ProcedureActor) -> RecordProvenance:
''',
    )

    registry_tests = ROOT / "tests/test_state_package_registry.py"
    replace_once(
        registry_tests,
        '    assert version_two.record_types - version_one.record_types == {"work_item"}\n',
        '    assert version_two.record_types - version_one.record_types == {\n'
        '        "work_item",\n'
        '        "procedure",\n'
        '    }\n',
    )
    replace_once(
        registry_tests,
        '''    assert version_two.optional_member_paths - version_one.optional_member_paths == {
        "records/work-items.jsonl"
    }
''',
        '''    assert version_two.optional_member_paths - version_one.optional_member_paths == {
        "records/work-items.jsonl",
        "records/procedures.jsonl",
    }
''',
    )
    replace_once(
        registry_tests,
        '            categories.append("procedure")\n',
        '            categories.append("project_checkpoint")\n',
    )
    replace_once(
        registry_tests,
        '    members[f"{package.PACKAGE_ROOT}/records/procedures.jsonl"] = b""\n',
        '    members[f"{package.PACKAGE_ROOT}/records/project-checkpoints.jsonl"] = b""\n',
    )

    v1_tests = ROOT / "tests/test_state_package_v2.py"
    replace_once(
        v1_tests,
        '    members.pop(f"{package.PACKAGE_ROOT}/records/work-items.jsonl")\n',
        '    members.pop(f"{package.PACKAGE_ROOT}/records/work-items.jsonl")\n'
        '    members.pop(f"{package.PACKAGE_ROOT}/records/procedures.jsonl")\n',
    )
    replace_once(
        v1_tests,
        '    included.remove("work_item")\n',
        '    included.remove("work_item")\n'
        '    included.remove("procedure")\n',
    )
    replace_once(
        v1_tests,
        '    cast(dict[str, int], manifest["record_counts"]).pop("work_item")\n',
        '    cast(dict[str, int], manifest["record_counts"]).pop("work_item")\n'
        '    cast(dict[str, int], manifest["record_counts"]).pop("procedure")\n',
    )
    replace_once(
        v1_tests,
        '    cast(dict[str, int], manifest["omitted_secret_counts"]).pop("work_item")\n',
        '    cast(dict[str, int], manifest["omitted_secret_counts"]).pop("work_item")\n'
        '    cast(dict[str, int], manifest["omitted_secret_counts"]).pop("procedure")\n',
    )


if __name__ == "__main__":
    main()
