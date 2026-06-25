from __future__ import annotations

from pathlib import Path


PATH = Path(__file__).resolve().parents[1] / "src/doll/state_package.py"


def replace_once(text: str, old: str, new: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one match, found {count}: {old[:100]!r}")
    return text.replace(old, new)


def main() -> None:
    text = PATH.read_text(encoding="utf-8")

    text = replace_once(
        text,
        ''') -> dict[str, bytes]:
    records_by_type: dict[str, list[dict[str, object]]] = {
        record_type: [] for record_type in _SUPPORTED_RECORD_TYPES
    }
    omitted_secret_counts: dict[str, int] = {
        record_type: 0 for record_type in _SUPPORTED_RECORD_TYPES
    }
''',
        ''') -> dict[str, bytes]:
    registry = _package_record_registry(PACKAGE_FORMAT_VERSION)
    _validate_registry_validators(registry)
    records_by_type: dict[str, list[dict[str, object]]] = {
        category.record_type: [] for category in registry.categories
    }
    omitted_secret_counts: dict[str, int] = {
        category.record_type: 0 for category in registry.categories
    }
''',
    )
    text = replace_once(
        text,
        '''        record_type = cast(str, row["record_type"])
        if record_type not in _SUPPORTED_RECORD_TYPES:
            raise StatePackageValidationError("unsupported authoritative record type")
        record = repository.get_record(record_id)
''',
        '''        record_type = cast(str, row["record_type"])
        category = registry.by_record_type.get(record_type)
        if category is None:
            raise StatePackageValidationError("unsupported authoritative record type")
        record = repository.get_record(record_id)
''',
    )
    text = replace_once(
        text,
        "        _validate_export_record(record)\n",
        "        _validate_export_record(record, category.validator_id)\n",
    )
    text = replace_once(
        text,
        '''    for record_type, member_path in _RECORD_PATHS.items():
        members[member_path] = _jsonl_bytes(records_by_type[record_type])
''',
        '''    for category in registry.categories:
        members[category.member_path] = _jsonl_bytes(
            records_by_type[category.record_type]
        )
''',
    )
    text = replace_once(
        text,
        '''    record_counts = {
        record_type: len(records_by_type[record_type])
        for record_type in sorted(_SUPPORTED_RECORD_TYPES)
    }
''',
        '''    record_counts = {
        record_type: len(records_by_type[record_type])
        for record_type in sorted(registry.record_types)
    }
''',
    )
    text = replace_once(
        text,
        '''        "included_categories": sorted(
            [*record_counts, "audit_events", "migration_history", "authoritative_files"]
        ),
''',
        '''        "included_categories": sorted(
            [*record_counts, *PACKAGE_SYSTEM_CATEGORIES]
        ),
''',
    )

    text = replace_once(
        text,
        '''    checksum_entries = _validate_checksums(checksums_value)
    _validate_member_inventory_paths(set(checksum_entries))
    expected_members = {checksums_path, *checksum_entries}
''',
        '''    checksum_entries = _validate_checksums(checksums_value)
    manifest_path = f"{PACKAGE_ROOT}/manifest.json"
    manifest = _load_json_bytes(_required_member(members, manifest_path), "manifest")
    if not isinstance(manifest, dict):
        raise StatePackageValidationError("manifest must be a JSON object")
    package_format_version = _validate_package_format_version(manifest)
    registry = _package_record_registry(package_format_version)
    _validate_registry_validators(registry)
    _validate_member_inventory_paths(set(checksum_entries), registry)
    expected_members = {checksums_path, *checksum_entries}
''',
    )
    text = replace_once(
        text,
        '''    manifest_path = f"{PACKAGE_ROOT}/manifest.json"
    manifest = _load_json_bytes(_required_member(members, manifest_path), "manifest")
    workspace_path = f"{PACKAGE_ROOT}/records/workspace.json"
''',
        '''    workspace_path = f"{PACKAGE_ROOT}/records/workspace.json"
''',
    )
    text = replace_once(
        text,
        "    data = _validate_package_payloads(manifest, workspace_payload, members)\n",
        "    data = _validate_package_payloads(manifest, workspace_payload, members, registry)\n",
    )

    old_inventory = '''def _validate_member_inventory_paths(paths: set[str]) -> None:
    fixed = {f"{PACKAGE_ROOT}/{path}" for path in _ALWAYS_MEMBER_PATHS}
    if not fixed.issubset(paths):
        raise StatePackageIntegrityError("required package member is missing")
    optional = {
        f"{PACKAGE_ROOT}/{_RECORD_PATHS[record_type]}" for record_type in _OPTIONAL_RECORD_TYPES
    }
    artifact_prefix = f"{PACKAGE_ROOT}/files/authoritative/"
    for path in paths - fixed - optional:
        if not path.startswith(artifact_prefix) or path == artifact_prefix:
            raise StatePackageIntegrityError("package contains an unsupported member")
'''
    new_inventory = '''def _validate_member_inventory_paths(
    paths: set[str],
    registry: AuthoritativeRecordRegistry | None = None,
) -> None:
    selected = registry or _package_record_registry(PACKAGE_FORMAT_VERSION)
    fixed = {f"{PACKAGE_ROOT}/{path}" for path in _FIXED_MEMBER_PATHS}
    fixed.update(
        f"{PACKAGE_ROOT}/{path}" for path in selected.required_member_paths
    )
    if not fixed.issubset(paths):
        raise StatePackageIntegrityError("required package member is missing")
    optional = {
        f"{PACKAGE_ROOT}/{path}" for path in selected.optional_member_paths
    }
    artifact_prefix = f"{PACKAGE_ROOT}/files/authoritative/"
    for path in paths - fixed - optional:
        if not path.startswith(artifact_prefix) or path == artifact_prefix:
            raise StatePackageIntegrityError("package contains an unsupported member")
'''
    text = replace_once(text, old_inventory, new_inventory)

    text = replace_once(
        text,
        '''def _validate_package_format_version(manifest: dict[str, object]) -> int:
    version = _required_positive_int(manifest, "package_format_version")
    required_fields = _PACKAGE_FORMAT_REQUIRED_FIELDS.get(version)
''',
        '''def _validate_package_format_version(manifest: dict[str, object]) -> int:
    version = _required_positive_int(manifest, "package_format_version")
    _package_record_registry(version)
    required_fields = _PACKAGE_FORMAT_REQUIRED_FIELDS.get(version)
''',
    )

    category_helpers = '''

def _required_unique_string_list(
    mapping: dict[str, object],
    key: str,
) -> tuple[str, ...]:
    value = mapping.get(key)
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item for item in value
    ):
        raise StatePackageValidationError(f"{key} must be a string list")
    result = tuple(value)
    if len(result) != len(set(result)):
        raise StatePackageValidationError(f"{key} contains duplicates")
    return result


def _validate_manifest_categories(
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
        raise StatePackageValidationError(
            "manifest included and excluded categories overlap"
        )
'''
    text = replace_once(
        text,
        "    return version\n\n\ndef _validate_package_payloads(\n",
        "    return version\n" + category_helpers + "\n\ndef _validate_package_payloads(\n",
    )
    text = replace_once(
        text,
        '''def _validate_package_payloads(
    manifest_value: object,
    workspace_value: object,
    members: dict[str, bytes],
) -> _PackageData:
''',
        '''def _validate_package_payloads(
    manifest_value: object,
    workspace_value: object,
    members: dict[str, bytes],
    registry: AuthoritativeRecordRegistry | None = None,
) -> _PackageData:
''',
    )
    text = replace_once(
        text,
        '''    manifest = cast(dict[str, object], manifest_value)
    package_format_version = _validate_package_format_version(manifest)
    if manifest.get("checksum_algorithm") != CHECKSUM_ALGORITHM:
''',
        '''    manifest = cast(dict[str, object], manifest_value)
    package_format_version = _validate_package_format_version(manifest)
    selected_registry = _package_record_registry(package_format_version)
    if (
        registry is not None
        and registry.package_format_version != package_format_version
    ):
        raise StatePackageIntegrityError("package registry version does not match manifest")
    registry = selected_registry
    _validate_registry_validators(registry)
    _validate_manifest_categories(manifest, registry)
    if manifest.get("checksum_algorithm") != CHECKSUM_ALGORITHM:
''',
    )
    old_loop = '''    for record_type, relative_path in _RECORD_PATHS.items():
        member_name = f"{PACKAGE_ROOT}/{relative_path}"
        member = members.get(member_name)
        if member is None and record_type in _OPTIONAL_RECORD_TYPES:
            payloads = []
        else:
            payloads = _load_jsonl_bytes(
                _required_member(members, member_name),
                relative_path,
            )
        actual_counts[record_type] = len(payloads)
        for payload in payloads:
            record = _envelope_from_payload(payload, record_type)
            if record.id in records_by_id:
                raise StatePackageValidationError("duplicate authoritative record ID")
            records_by_id[record.id] = record
            records.append(record)

    expected_counts = {
        key: _mapping_record_count(record_counts_value, key)
        for key in sorted(_SUPPORTED_RECORD_TYPES)
    }
'''
    new_loop = '''    for category in registry.categories:
        member_name = f"{PACKAGE_ROOT}/{category.member_path}"
        member = members.get(member_name)
        if member is None and not category.required_member:
            payloads = []
        else:
            payloads = _load_jsonl_bytes(
                _required_member(members, member_name),
                category.member_path,
            )
        actual_counts[category.record_type] = len(payloads)
        for payload in payloads:
            record = _envelope_from_payload(
                payload,
                category.record_type,
                category.validator_id,
            )
            if record.id in records_by_id:
                raise StatePackageValidationError("duplicate authoritative record ID")
            records_by_id[record.id] = record
            records.append(record)

    expected_counts = {
        category.record_type: _mapping_record_count(
            record_counts_value,
            category.record_type,
            required=category.required_member,
        )
        for category in registry.categories
    }
'''
    text = replace_once(text, old_loop, new_loop)
    text = replace_once(
        text,
        '''    omitted_counts = {
        key: _mapping_record_count(omitted_value, key) for key in sorted(_SUPPORTED_RECORD_TYPES)
    }
''',
        '''    omitted_counts = {
        category.record_type: _mapping_record_count(
            omitted_value,
            category.record_type,
            required=category.required_member,
        )
        for category in registry.categories
    }
''',
    )

    text = replace_once(
        text,
        "def _envelope_from_payload(payload: object, expected_type: str) -> RecordEnvelope:\n",
        "def _envelope_from_payload(\n"
        "    payload: object,\n"
        "    expected_type: str,\n"
        "    validator_id: str | None = None,\n"
        ") -> RecordEnvelope:\n",
    )
    old_dispatch = '''    try:
        if record_type == "preference":
            _preference_from_record(record)
        elif record_type == "policy":
            _policy_from_record(record)
        elif record_type == "permission":
            _permission_from_record(record)
        elif record_type == "memory":
            _memory_from_record(record)
        elif record_type == "claim":
            _claim_from_record(record)
        elif record_type == "evidence":
            _evidence_from_record(record)
        elif record_type == "inference":
            _inference_from_record(record)
        elif record_type == "trust_assessment":
            _trust_assessment_from_record(record)
        elif record_type == "instruction_origin":
            _instruction_origin_from_record(record)
        elif record_type == "project":
            _project_from_record(record)
        elif record_type == "decision":
            _decision_from_record(record)
        elif record_type == "artifact":
            _artifact_from_record(record)
        elif record_type == "backup_manifest":
            _backup_manifest_from_record(record)
        else:  # pragma: no cover - expected type is selected from a fixed mapping.
            raise StatePackageValidationError("record type is unsupported")
'''
    new_dispatch = '''    validator = _PACKAGE_RECORD_VALIDATORS.get(validator_id or record_type)
    if validator is None:
        raise StatePackageValidationError("typed record validator is unavailable")
    try:
        validator(record)
'''
    text = replace_once(text, old_dispatch, new_dispatch)

    text = replace_once(
        text,
        '''def _mapping_record_count(mapping: dict[object, object], key: str) -> int:
    if key in _OPTIONAL_RECORD_TYPES and key not in mapping:
        return 0
    return _mapping_nonnegative_int(mapping, key)
''',
        '''def _mapping_record_count(
    mapping: dict[object, object],
    key: str,
    *,
    required: bool = True,
) -> int:
    if not required and key not in mapping:
        return 0
    return _mapping_nonnegative_int(mapping, key)
''',
    )
    text = replace_once(
        text,
        '''def _validate_export_record(record: RecordEnvelope) -> None:
    if record.status not in _ALLOWED_LIFECYCLE:
        raise StatePackageValidationError("unsupported record lifecycle for export")
    _envelope_from_payload(_record_payload(record), record.record_type)
''',
        '''def _validate_export_record(record: RecordEnvelope, validator_id: str) -> None:
    if record.status not in _ALLOWED_LIFECYCLE:
        raise StatePackageValidationError("unsupported record lifecycle for export")
    _envelope_from_payload(
        _record_payload(record),
        record.record_type,
        validator_id,
    )
''',
    )

    PATH.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
