from __future__ import annotations

import hashlib
import json
import sqlite3
import zipfile
from pathlib import Path
from typing import cast

import pytest

import doll.backup as backup
import doll.state_package as state_package
from doll import state, workspace
from doll.artifact import WorkspaceFileService
from doll.audit import AuditService
from doll.backup_manifest import BackupManifestService
from doll.memory import ConfirmedMemoryService
from doll.settings import PreferenceService


def _initialized(tmp_path: Path, name: str = "workspace") -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(tmp_path / name)
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def _populate(
    initialized: workspace.InitializedWorkspace,
    *,
    secret: bool = False,
) -> tuple[str, str]:
    with state.open_state_repository(initialized.root) as repository:
        preference = PreferenceService(repository).create(
            key="output.language",
            value={"language": "日本語"},
            description="表示言語",
            operation_id="backup-preference",
        )
        ConfirmedMemoryService(repository).create(
            subject="継続方針",
            content="ローカル優先で復旧可能にする。",
            operation_id="backup-memory",
        )
        artifact = WorkspaceFileService(repository).create_text(
            managed_path="backup/報告.txt",
            text="verified backup artifact\n",
            title="バックアップ報告",
            operation_id="backup-artifact",
        )
        if secret:
            PreferenceService(repository).create(
                key="private.synthetic",
                value="omitted",
                sensitivity="secret",
                operation_id="backup-secret",
            )
    return preference.record_id, artifact.artifact_id


def _members(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path, "r") as archive:
        return {item.filename: archive.read(item) for item in archive.infolist()}


def test_state_backup_create_verify_register_and_state_package_compatibility(
    tmp_path: Path,
) -> None:
    initialized = _initialized(tmp_path)
    preference_id, artifact_id = _populate(initialized, secret=True)
    output = tmp_path / "state-backup.zip"

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        source_revision = repository.status().state_revision
        source_records = repository.status().record_count
        source_audits = len(AuditService(repository).list(limit=200))

    result = backup.create_state_backup(
        initialized.root,
        output,
        created_at="2026-06-15T03:00:00Z",
        operation_id="backup-state-create",
    )
    inspection = result.inspection
    assert output.is_file()
    assert inspection.backup_kind == "state"
    assert inspection.workspace_id == str(initialized.record.workspace_id)
    assert inspection.source_state_revision == source_revision
    assert inspection.included_categories == ("doll_state_package",)
    assert inspection.file_sha256 == "sha256:" + hashlib.sha256(output.read_bytes()).hexdigest()
    assert backup.verify_backup(output) == inspection
    assert backup.inspect_backup(output) == inspection
    assert result.inventory.manifest_hash == inspection.manifest_hash
    assert result.inventory.file_name == output.name
    assert result.inventory.source_state_revision == source_revision

    members = _members(output)
    nested = tmp_path / "nested.zip"
    nested.write_bytes(members[f"{backup.BACKUP_ROOT}/payload/state-package.zip"])
    nested_inspection = state_package.verify_state_package(nested)
    assert nested_inspection.state_revision == source_revision
    assert nested_inspection.omitted_secret_counts["preference"] == 1

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        assert repository.status().state_revision == source_revision + 1
        assert repository.status().record_count == source_records + 1
        inventory = BackupManifestService(repository).list()
        assert inventory == (result.inventory,)
        events = AuditService(repository).list(action="backup.create")
        assert len(events) == 1
        assert len(AuditService(repository).list(limit=200)) == source_audits + 1
        assert PreferenceService(repository).get(preference_id).value == {"language": "日本語"}
        WorkspaceFileService(repository).verify(artifact_id)

    portable = tmp_path / "post-backup-state-package.zip"
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        package_inspection = state_package.export_state_package(
            repository,
            portable,
            exported_at="2026-06-15T04:00:00Z",
        )
    assert package_inspection.record_counts["backup_manifest"] == 1
    target = tmp_path / "imported"
    imported = state_package.import_state_package(portable, target)
    assert imported.imported_record_count == sum(package_inspection.record_counts.values())
    with state.open_state_repository(target, read_only=True) as repository:
        imported_inventory = BackupManifestService(repository).list()
        assert len(imported_inventory) == 1
        assert imported_inventory[0].backup_id == result.inventory.backup_id

    archive_bytes = output.read_bytes()
    assert str(initialized.root).encode() not in archive_bytes
    assert str(output).encode() not in archive_bytes


def test_workspace_backup_contains_consistent_snapshot_and_artifacts(tmp_path: Path) -> None:
    initialized = _initialized(tmp_path)
    _, artifact_id = _populate(initialized)
    output = initialized.root / "backups" / "workspace-backup.zip"

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        source_revision = repository.status().state_revision
        source_record_count = repository.status().record_count
        source_audit_count = len(AuditService(repository).list(limit=200))

    result = backup.create_workspace_backup(
        initialized.root,
        output,
        created_at="2026-06-15T05:00:00Z",
        operation_id="backup-workspace-create",
    )
    inspection = result.inspection
    assert inspection.backup_kind == "workspace"
    assert inspection.source_state_revision == source_revision
    assert inspection.payload_file_count == 3
    assert backup.verify_backup(output) == inspection

    members = _members(output)
    workspace_payload = json.loads(members[f"{backup.BACKUP_ROOT}/payload/workspace.json"])
    assert workspace_payload["workspace_id"] == str(initialized.record.workspace_id)
    artifact_bytes = members[f"{backup.BACKUP_ROOT}/payload/artifacts/backup/報告.txt"]
    assert artifact_bytes == b"verified backup artifact\n"

    snapshot = tmp_path / "snapshot.sqlite3"
    snapshot.write_bytes(members[f"{backup.BACKUP_ROOT}/payload/state/{state.STATE_DATABASE_NAME}"])
    connection = sqlite3.connect(snapshot)
    try:
        metadata = connection.execute(
            "SELECT workspace_id, state_revision FROM schema_metadata WHERE singleton = 1"
        ).fetchone()
        assert metadata == (str(initialized.record.workspace_id), source_revision)
        assert connection.execute("SELECT COUNT(*) FROM records").fetchone() == (
            source_record_count,
        )
        assert connection.execute("SELECT COUNT(*) FROM audit_events").fetchone() == (
            source_audit_count,
        )
        assert connection.execute(
            "SELECT COUNT(*) FROM records WHERE id = ?", (artifact_id,)
        ).fetchone() == (1,)
    finally:
        connection.close()

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        assert repository.status().state_revision == source_revision + 1
        assert BackupManifestService(repository).get(result.inventory.backup_id) == result.inventory
        assert len(AuditService(repository).list(action="backup.create")) == 1


def test_workspace_backup_rejects_secrets_without_publication_or_inventory(
    tmp_path: Path,
) -> None:
    initialized = _initialized(tmp_path)
    _populate(initialized, secret=True)
    output = tmp_path / "refused.zip"
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        before = repository.status()
        audit_before = len(AuditService(repository).list(limit=200))

    with pytest.raises(backup.BackupValidationError):
        backup.create_workspace_backup(initialized.root, output)
    assert not output.exists()
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        after = repository.status()
        assert after.state_revision == before.state_revision
        assert after.record_count == before.record_count
        assert len(AuditService(repository).list(limit=200)) == audit_before
        assert BackupManifestService(repository).list() == ()


def test_old_state_package_without_backup_manifest_member_remains_valid(
    tmp_path: Path,
) -> None:
    initialized = _initialized(tmp_path)
    current = tmp_path / "current.zip"
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        state_package.export_state_package(
            repository,
            current,
            exported_at="2026-06-15T06:00:00Z",
        )
    members = _members(current)
    root = state_package.PACKAGE_ROOT
    optional = f"{root}/records/backup-manifests.jsonl"
    members.pop(optional)
    manifest_name = f"{root}/manifest.json"
    manifest_value = cast(dict[str, object], json.loads(members[manifest_name]))
    counts = cast(dict[str, object], manifest_value["record_counts"])
    omitted = cast(dict[str, object], manifest_value["omitted_secret_counts"])
    counts.pop("backup_manifest")
    omitted.pop("backup_manifest")
    manifest_value["included_categories"] = [
        item
        for item in cast(list[str], manifest_value["included_categories"])
        if item != "backup_manifest"
    ]
    manifest_value["total_payload_size_bytes"] = cast(
        int, manifest_value["total_payload_size_bytes"]
    ) - len(b"")
    members[manifest_name] = state_package._json_bytes(manifest_value)
    checksum_name = f"{root}/checksums.json"
    members.pop(checksum_name)
    checksums: dict[str, object] = {
        "algorithm": state_package.CHECKSUM_ALGORITHM,
        "entries": [
            {
                "path": name,
                "sha256": hashlib.sha256(content).hexdigest(),
                "size_bytes": len(content),
            }
            for name, content in sorted(members.items())
        ],
    }
    members[checksum_name] = state_package._json_bytes(checksums)
    legacy = tmp_path / "legacy.zip"
    state_package._write_deterministic_zip(legacy, members)
    inspection = state_package.verify_state_package(legacy)
    assert inspection.record_counts["backup_manifest"] == 0
    assert inspection.omitted_secret_counts["backup_manifest"] == 0
