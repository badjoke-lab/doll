from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import cast

import pytest

import doll.state_package as package
from doll import state, workspace
from doll.settings import PreferenceService
from doll.state_package_registry import (
    PACKAGE_SYSTEM_CATEGORIES,
    AuthoritativeRecordCategory,
    AuthoritativeRecordRegistry,
    StatePackageRegistryError,
    get_authoritative_record_registry,
)


def _export_package(tmp_path: Path) -> Path:
    initialized = workspace.initialize_workspace(tmp_path / "source")
    with state.initialize_state_repository(initialized.root):
        pass
    with state.open_state_repository(initialized.root) as repository:
        PreferenceService(repository).create(
            key="registry.test",
            value={"enabled": True},
            operation_id="imp-039-registry",
        )
    output = tmp_path / "state.zip"
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        package.export_state_package(
            repository,
            output,
            exported_at="2026-06-26T01:00:00Z",
        )
    return output


def _read_members(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path, "r") as archive:
        return {info.filename: archive.read(info) for info in archive.infolist()}


def _write_members(path: Path, members: dict[str, bytes]) -> None:
    updated = dict(members)
    checksum_name = f"{package.PACKAGE_ROOT}/checksums.json"
    updated.pop(checksum_name, None)
    updated[checksum_name] = package._json_bytes(
        {
            "algorithm": package.CHECKSUM_ALGORITHM,
            "entries": [
                {
                    "path": name,
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "size_bytes": len(content),
                }
                for name, content in sorted(updated.items())
            ],
        }
    )
    package._write_deterministic_zip(path, updated)


def test_supported_registries_are_explicit_and_immutable() -> None:
    version_one = get_authoritative_record_registry(1)
    version_two = get_authoritative_record_registry(2)

    assert version_one.package_format_version == 1
    assert version_two.package_format_version == 2
    assert version_two.record_types - version_one.record_types == {"work_item"}
    assert version_one.required_member_paths == version_two.required_member_paths
    assert version_two.optional_member_paths - version_one.optional_member_paths == {
        "records/work-items.jsonl"
    }
    assert package._package_record_registry(1) == version_one
    assert package._package_record_registry(2) == version_two

    with pytest.raises(TypeError):
        version_two.by_record_type["new"] = version_two.categories[0]  # type: ignore[index]
    with pytest.raises(StatePackageRegistryError):
        get_authoritative_record_registry(3)


def test_registry_definition_rejects_duplicates_and_unsafe_paths() -> None:
    first = AuthoritativeRecordCategory("first", "records/first.jsonl", True, "first")
    with pytest.raises(StatePackageRegistryError):
        AuthoritativeRecordRegistry(2, (first, first))
    with pytest.raises(StatePackageRegistryError):
        AuthoritativeRecordRegistry(
            2,
            (
                first,
                AuthoritativeRecordCategory("second", "records/first.jsonl", False, "second"),
            ),
        )
    with pytest.raises(StatePackageRegistryError):
        AuthoritativeRecordCategory("unsafe", "records/../unsafe.jsonl", True, "unsafe")


def test_v2_export_inventory_and_manifest_come_from_registry(tmp_path: Path) -> None:
    source = _export_package(tmp_path)
    members = _read_members(source)
    registry = get_authoritative_record_registry(2)
    manifest = cast(
        dict[str, object],
        json.loads(members[f"{package.PACKAGE_ROOT}/manifest.json"]),
    )

    assert manifest["package_format_version"] == 2
    assert set(cast(list[str], manifest["included_categories"])) == (
        registry.record_types | PACKAGE_SYSTEM_CATEGORIES
    )
    assert set(cast(dict[str, int], manifest["record_counts"])) == registry.record_types
    for category in registry.categories:
        assert f"{package.PACKAGE_ROOT}/{category.member_path}" in members


def test_manifest_categories_must_match_versioned_registry(tmp_path: Path) -> None:
    source = _export_package(tmp_path)
    original = _read_members(source)
    manifest_name = f"{package.PACKAGE_ROOT}/manifest.json"

    for index, mutate in enumerate(("missing", "unknown", "duplicate")):
        members = dict(original)
        manifest = cast(dict[str, object], json.loads(members[manifest_name]))
        categories = cast(list[str], manifest["included_categories"])
        if mutate == "missing":
            categories.remove("preference")
        elif mutate == "unknown":
            categories.append("procedure")
        else:
            categories.append(categories[0])
        members[manifest_name] = package._json_bytes(manifest)
        target = tmp_path / f"invalid-categories-{index}.zip"
        _write_members(target, members)
        with pytest.raises(package.StatePackageValidationError):
            package.verify_state_package(target)


def test_unknown_authoritative_member_fails_before_target_mutation(tmp_path: Path) -> None:
    source = _export_package(tmp_path)
    members = _read_members(source)
    members[f"{package.PACKAGE_ROOT}/records/procedures.jsonl"] = b""
    hostile = tmp_path / "unknown-member.zip"
    _write_members(hostile, members)

    target = tmp_path / "target"
    target.mkdir()
    marker = target / "marker.txt"
    marker.write_text("unchanged", encoding="utf-8")

    with pytest.raises(package.StatePackageIntegrityError):
        package.import_state_package(hostile, target)
    assert marker.read_text(encoding="utf-8") == "unchanged"


def test_missing_registered_validator_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _export_package(tmp_path)
    monkeypatch.delitem(package._PACKAGE_RECORD_VALIDATORS, "preference")

    with pytest.raises(package.StatePackageValidationError):
        package.verify_state_package(source)


def test_registry_definition_rejects_invalid_fields() -> None:
    with pytest.raises(StatePackageRegistryError):
        AuthoritativeRecordRegistry(0, ())
    with pytest.raises(StatePackageRegistryError):
        AuthoritativeRecordRegistry(1, ())
    with pytest.raises(StatePackageRegistryError):
        AuthoritativeRecordCategory("Invalid-Type", "records/invalid.jsonl", True, "invalid")
    with pytest.raises(StatePackageRegistryError):
        AuthoritativeRecordCategory("invalid", "records/invalid.jsonl", True, "Invalid-Validator")
    with pytest.raises(StatePackageRegistryError):
        AuthoritativeRecordCategory("invalid", "records/invalid.jsonl", cast(bool, 1), "invalid")
    with pytest.raises(StatePackageRegistryError):
        AuthoritativeRecordCategory("invalid", "/records/invalid.jsonl", True, "invalid")


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
