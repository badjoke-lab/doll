from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATE_PACKAGE = ROOT / "src/doll/state_package.py"
REGISTRY_TESTS = ROOT / "tests/test_state_package_registry.py"


def replace_once(text: str, old: str, new: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one match, found {count}: {old[:100]!r}")
    return text.replace(old, new)


def main() -> None:
    text = STATE_PACKAGE.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '''def _validate_manifest_categories(
    manifest: dict[str, object],
    registry: AuthoritativeRecordRegistry,
) -> None:
    included = _required_unique_string_list(manifest, "included_categories")
    expected = registry.record_types | PACKAGE_SYSTEM_CATEGORIES
    if set(included) != expected:
        raise StatePackageValidationError(
            "manifest included categories do not match the package registry"
        )
    excluded = _required_unique_string_list(manifest, "excluded_categories")
    if set(included).intersection(excluded):
        raise StatePackageValidationError("manifest included and excluded categories overlap")
''',
        '''def _validate_manifest_categories(
    manifest: dict[str, object],
    registry: AuthoritativeRecordRegistry,
) -> frozenset[str]:
    included = frozenset(
        _required_unique_string_list(manifest, "included_categories")
    )
    allowed = registry.record_types | PACKAGE_SYSTEM_CATEGORIES
    if not included.issubset(allowed):
        raise StatePackageValidationError(
            "manifest includes a category outside the package registry"
        )
    required = PACKAGE_SYSTEM_CATEGORIES | frozenset(
        category.record_type
        for category in registry.categories
        if category.required_member
    )
    if not required.issubset(included):
        raise StatePackageValidationError(
            "manifest omits a required package category"
        )
    excluded = frozenset(
        _required_unique_string_list(manifest, "excluded_categories")
    )
    if included.intersection(excluded):
        raise StatePackageValidationError(
            "manifest included and excluded categories overlap"
        )
    return included
''',
    )
    text = replace_once(
        text,
        "    _validate_manifest_categories(manifest, registry)\n",
        "    included_categories = _validate_manifest_categories(manifest, registry)\n",
    )
    text = replace_once(
        text,
        '''    for category in registry.categories:
        member_name = f"{PACKAGE_ROOT}/{category.member_path}"
        member = members.get(member_name)
        if member is None and not category.required_member:
            payloads = []
        else:
            payloads = _load_jsonl_bytes(
                _required_member(members, member_name),
                category.member_path,
            )
''',
        '''    for category in registry.categories:
        member_name = f"{PACKAGE_ROOT}/{category.member_path}"
        member = members.get(member_name)
        declared = category.record_type in included_categories
        if not declared:
            if (
                member is not None
                or category.record_type in record_counts_value
                or category.record_type in omitted_value
            ):
                raise StatePackageValidationError(
                    "package contains an undeclared authoritative category"
                )
            payloads = []
        elif member is None and not category.required_member:
            payloads = []
        else:
            payloads = _load_jsonl_bytes(
                _required_member(members, member_name),
                category.member_path,
            )
''',
    )
    text = replace_once(
        text,
        "def _validate_export_record(record: RecordEnvelope, validator_id: str) -> None:\n",
        "def _validate_export_record(\n"
        "    record: RecordEnvelope,\n"
        "    validator_id: str | None = None,\n"
        ") -> None:\n",
    )
    text = replace_once(
        text,
        '''        record.record_type,
        validator_id,
    )
''',
        '''        record.record_type,
        validator_id or record.record_type,
    )
''',
    )
    STATE_PACKAGE.write_text(text, encoding="utf-8")

    tests = REGISTRY_TESTS.read_text(encoding="utf-8")
    addition = '''


def test_registry_definition_rejects_invalid_fields() -> None:
    with pytest.raises(StatePackageRegistryError):
        AuthoritativeRecordRegistry(0, ())
    with pytest.raises(StatePackageRegistryError):
        AuthoritativeRecordRegistry(1, ())
    with pytest.raises(StatePackageRegistryError):
        AuthoritativeRecordCategory(
            "Invalid-Type", "records/invalid.jsonl", True, "invalid"
        )
    with pytest.raises(StatePackageRegistryError):
        AuthoritativeRecordCategory(
            "invalid", "records/invalid.jsonl", True, "Invalid-Validator"
        )
    with pytest.raises(StatePackageRegistryError):
        AuthoritativeRecordCategory(
            "invalid", "records/invalid.jsonl", cast(bool, 1), "invalid"
        )
    with pytest.raises(StatePackageRegistryError):
        AuthoritativeRecordCategory(
            "invalid", "/records/invalid.jsonl", True, "invalid"
        )


def test_undeclared_optional_category_member_is_rejected(tmp_path: Path) -> None:
    source = _export_package(tmp_path)
    members = _read_members(source)
    manifest_name = f"{package.PACKAGE_ROOT}/manifest.json"
    manifest = cast(dict[str, object], json.loads(members[manifest_name]))
    included = cast(list[str], manifest["included_categories"])
    included.remove("backup_manifest")
    members[manifest_name] = package._json_bytes(manifest)
    target = tmp_path / "undeclared-optional.zip"
    _write_members(target, members)

    with pytest.raises(package.StatePackageValidationError):
        package.verify_state_package(target)
'''
    if "def test_registry_definition_rejects_invalid_fields" in tests:
        raise RuntimeError("IMP-039 compatibility tests already applied")
    REGISTRY_TESTS.write_text(tests.rstrip() + addition + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
