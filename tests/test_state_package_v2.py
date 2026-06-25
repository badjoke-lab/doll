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


def _source_workspace(
    tmp_path: Path,
) -> tuple[workspace.InitializedWorkspace, str]:
    initialized = workspace.initialize_workspace(tmp_path / "source")
    with state.initialize_state_repository(initialized.root):
        pass
    with state.open_state_repository(initialized.root) as repository:
        preference = PreferenceService(repository).create(
            key="package.v2.compatibility",
            value={"enabled": True},
            description="Synthetic package compatibility fixture",
            operation_id="imp-038-preference",
        )
    return initialized, preference.record_id


def _export(
    initialized: workspace.InitializedWorkspace,
    output: Path,
) -> package.PackageInspection:
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        return package.export_state_package(
            repository,
            output,
            exported_at="2026-06-26T00:00:00Z",
        )


def _read_members(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path, "r") as archive:
        return {info.filename: archive.read(info) for info in archive.infolist()}


def _write_members(path: Path, members: dict[str, bytes]) -> None:
    updated = dict(members)
    checksum_name = f"{package.PACKAGE_ROOT}/checksums.json"
    updated.pop(checksum_name, None)
    checksums: dict[str, object] = {
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
    updated[checksum_name] = package._json_bytes(checksums)
    package._write_deterministic_zip(path, updated)


def _write_v1_fixture(v2_package: Path, v1_package: Path) -> None:
    members = _read_members(v2_package)
    manifest_name = f"{package.PACKAGE_ROOT}/manifest.json"
    manifest = cast(dict[str, object], json.loads(members[manifest_name]))
    manifest["package_format_version"] = 1
    manifest["compatibility_notes"] = [
        "Import requires package format version 1 and a supported state schema.",
        "checksums.json is the inventory and is not self-hashed.",
    ]
    members[manifest_name] = package._json_bytes(manifest)
    readme_name = f"{package.PACKAGE_ROOT}/README.txt"
    members[readme_name] = members[readme_name].replace(
        b"Format version: 2",
        b"Format version: 1",
    )
    _write_members(v1_package, members)


def _rewrite_manifest_version(source: Path, target: Path, version: int) -> None:
    members = _read_members(source)
    manifest_name = f"{package.PACKAGE_ROOT}/manifest.json"
    manifest = cast(dict[str, object], json.loads(members[manifest_name]))
    manifest["package_format_version"] = version
    members[manifest_name] = package._json_bytes(manifest)
    _write_members(target, members)


def test_new_exports_use_v2_and_remain_deterministic(tmp_path: Path) -> None:
    initialized, _ = _source_workspace(tmp_path)
    first = tmp_path / "first.zip"
    second = tmp_path / "second.zip"

    first_inspection = _export(initialized, first)
    second_inspection = _export(initialized, second)

    assert package.PACKAGE_FORMAT_VERSION == 2
    assert package.SUPPORTED_PACKAGE_FORMAT_VERSIONS == frozenset({1, 2})
    assert first_inspection.package_format_version == 2
    assert second_inspection == first_inspection
    assert first.read_bytes() == second.read_bytes()
    assert b"Format version: 2" in _read_members(first)[
        f"{package.PACKAGE_ROOT}/README.txt"
    ]


def test_supported_v1_fixture_inspects_plans_and_imports(tmp_path: Path) -> None:
    initialized, preference_id = _source_workspace(tmp_path)
    v2_package = tmp_path / "source-v2.zip"
    v1_package = tmp_path / "fixture-v1.zip"
    _export(initialized, v2_package)
    _write_v1_fixture(v2_package, v1_package)

    inspection = package.inspect_state_package(v1_package)
    assert inspection.package_format_version == 1
    assert package.verify_state_package(v1_package) == inspection

    target = tmp_path / "imported-v1"
    plan = package.plan_state_package_import(v1_package, target)
    assert plan.inspection.package_format_version == 1
    assert plan.target_empty is True
    assert plan.conflicts == ()

    result = package.import_state_package(v1_package, target)
    assert result.workspace_id == inspection.workspace_id
    with state.open_state_repository(target, read_only=True) as repository:
        imported = PreferenceService(repository).get(preference_id)
        assert imported.value == {"enabled": True}
        row = repository.connection.execute(
            "SELECT metadata_json FROM audit_events "
            "WHERE action = 'state-package.import' ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        assert row is not None
        metadata = json.loads(cast(str, row["metadata_json"]))
        assert metadata["package_format_version"] == 1


def test_unsupported_package_version_fails_before_target_mutation(tmp_path: Path) -> None:
    initialized, _ = _source_workspace(tmp_path)
    supported = tmp_path / "supported.zip"
    unsupported = tmp_path / "unsupported.zip"
    _export(initialized, supported)
    _rewrite_manifest_version(supported, unsupported, 3)

    target = tmp_path / "target"
    target.mkdir()
    marker = target / "marker.txt"
    marker.write_text("unchanged", encoding="utf-8")

    with pytest.raises(package.StatePackageValidationError):
        package.import_state_package(unsupported, target)
    assert marker.read_text(encoding="utf-8") == "unchanged"


def test_version_specific_manifest_requirements_fail_closed(tmp_path: Path) -> None:
    initialized, _ = _source_workspace(tmp_path)
    source = tmp_path / "source.zip"
    invalid = tmp_path / "invalid.zip"
    _export(initialized, source)
    members = _read_members(source)
    manifest_name = f"{package.PACKAGE_ROOT}/manifest.json"
    manifest = cast(dict[str, object], json.loads(members[manifest_name]))
    del manifest["compatibility_notes"]
    members[manifest_name] = package._json_bytes(manifest)
    _write_members(invalid, members)

    with pytest.raises(package.StatePackageValidationError):
        package.verify_state_package(invalid)
