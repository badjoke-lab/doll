from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import cast
from uuid import uuid4

import pytest

import doll.backup_manifest as manifest
from doll import state, workspace
from doll.audit import AuditService
from doll.state import RecordEnvelope, StaleRevisionError


def _initialized(tmp_path: Path) -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(tmp_path / "workspace")
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def _register(
    repository: state.StateRepository,
    *,
    revision: int | None = None,
    backup_id: str | None = None,
) -> manifest.BackupManifestRecord:
    status = repository.status()
    return manifest.BackupManifestService(repository).register_verified(
        backup_kind="state",
        backup_format_version=1,
        workspace_id=status.workspace_id,
        schema_version=status.schema_version,
        source_state_revision=status.state_revision if revision is None else revision,
        created_at="2026-06-15T00:00:00Z",
        verified_at="2026-06-15T00:01:00Z",
        manifest_hash="sha256:" + "1" * 64,
        file_name="state-20260615.doll-backup.zip",
        file_size_bytes=123,
        file_sha256="sha256:" + "2" * 64,
        included_categories=("doll_state_package",),
        excluded_categories=("secrets", "temporary_files"),
        operation_id="backup-manifest-test",
        backup_id=backup_id,
    )


def test_register_get_list_and_audit_are_atomic(tmp_path: Path) -> None:
    initialized = _initialized(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        before = repository.status().state_revision
        record = _register(repository)
        assert repository.status().state_revision == before + 1
        assert record.backup_kind == "state"
        assert record.source_state_revision == before
        assert record.verification_status == "verified"
        assert manifest.BackupManifestService(repository).get(record.backup_id) == record
        assert manifest.BackupManifestService(repository).list() == (record,)
        events = AuditService(repository).list(action="backup.create")
        assert len(events) == 1
        assert events[0].target_id == record.backup_id
        assert events[0].metadata["file_name"] == record.file_name

        envelope = repository.get_record(record.backup_id)
        assert envelope.record_type == "backup_manifest"
        assert envelope.sensitivity == "internal"
        assert envelope.provenance == "system-generated"
        assert manifest._backup_manifest_from_record(envelope) == record


def test_register_rejects_read_only_stale_and_wrong_workspace(tmp_path: Path) -> None:
    initialized = _initialized(tmp_path)
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        with pytest.raises(state.ReadOnlyStateError):
            _register(repository)

    with state.open_state_repository(initialized.root) as repository:
        status = repository.status()
        with pytest.raises(manifest.BackupManifestValidationError):
            manifest.BackupManifestService(repository).register_verified(
                backup_kind="state",
                backup_format_version=1,
                workspace_id=str(uuid4()),
                schema_version=status.schema_version,
                source_state_revision=status.state_revision,
                created_at="2026-06-15T00:00:00Z",
                verified_at="2026-06-15T00:01:00Z",
                manifest_hash="sha256:" + "1" * 64,
                file_name="backup.zip",
                file_size_bytes=1,
                file_sha256="sha256:" + "2" * 64,
                included_categories=("doll_state_package",),
                excluded_categories=("secrets",),
            )
        with pytest.raises(StaleRevisionError):
            _register(repository, revision=status.state_revision + 1)
        assert repository.status().record_count == 0
        assert not AuditService(repository).list(action="backup.create")


def test_registration_database_failure_rolls_back(tmp_path: Path) -> None:
    initialized = _initialized(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        before = repository.status()
        repository.connection.execute(
            """
            CREATE TRIGGER fail_backup_audit
            BEFORE INSERT ON audit_events
            WHEN NEW.action = 'backup.create'
            BEGIN
                SELECT RAISE(ABORT, 'synthetic');
            END
            """
        )
        with pytest.raises(manifest.BackupManifestRegistrationError):
            _register(repository)
        after = repository.status()
        assert after.state_revision == before.state_revision
        assert after.record_count == before.record_count


def _envelope(**updates: object) -> RecordEnvelope:
    backup_id = str(uuid4())
    metadata: dict[str, object] = {
        "backup_id": backup_id,
        "backup_kind": "workspace",
        "backup_format_version": 1,
        "workspace_id": str(uuid4()),
        "schema_version": 2,
        "source_state_revision": 7,
        "created_at": "2026-06-15T00:00:00Z",
        "verified_at": "2026-06-15T00:01:00Z",
        "manifest_hash": "sha256:" + "1" * 64,
        "file_name": "workspace.zip",
        "file_size_bytes": 999,
        "file_sha256": "sha256:" + "2" * 64,
        "verification_status": "verified",
        "included_categories": ["sqlite_state_snapshot", "workspace_identity"],
        "excluded_categories": ["secrets"],
    }
    metadata_updates = cast(dict[str, object], updates.pop("metadata", {}))
    metadata.update(metadata_updates)
    values: dict[str, object] = {
        "id": backup_id,
        "record_type": "backup_manifest",
        "schema_version": 1,
        "created_at": "2026-06-15T00:00:00Z",
        "updated_at": "2026-06-15T00:01:00Z",
        "revision": 1,
        "status": "active",
        "provenance": "system-generated",
        "sensitivity": "internal",
        "title": "Verified workspace backup",
        "metadata": metadata,
    }
    values.update(updates)
    return RecordEnvelope(**values)  # type: ignore[arg-type]


def test_record_conversion_accepts_imported_and_archived() -> None:
    record = _envelope(status="archived", provenance="imported")
    parsed = manifest._backup_manifest_from_record(record)
    assert parsed.backup_kind == "workspace"
    restored = replace(record, provenance="restored")
    assert manifest._backup_manifest_from_record(restored).backup_id == record.id


@pytest.mark.parametrize(
    ("updates", "metadata"),
    [
        ({"record_type": "artifact"}, {}),
        ({"schema_version": 2}, {}),
        ({"status": "deleted"}, {}),
        ({"provenance": "user-created"}, {}),
        ({"sensitivity": "secret"}, {}),
        ({}, {"backup_id": str(uuid4())}),
        ({}, {"backup_kind": "cloud"}),
        ({}, {"backup_format_version": 0}),
        ({}, {"verified_at": "2026-06-14T23:59:00Z"}),
        ({}, {"manifest_hash": "bad"}),
        ({}, {"file_name": "../bad"}),
        ({}, {"verification_status": "failed"}),
        ({}, {"included_categories": ["secrets"], "excluded_categories": ["secrets"]}),
    ],
)
def test_record_conversion_rejects_corruption(
    updates: dict[str, object], metadata: dict[str, object]
) -> None:
    record = _envelope(**updates, metadata=metadata)
    with pytest.raises(manifest.BackupManifestCorruptError):
        manifest._backup_manifest_from_record(record)


def test_validation_helpers_and_list_limits(tmp_path: Path) -> None:
    with pytest.raises(manifest.BackupManifestValidationError):
        manifest._validate_backup_kind("cloud")
    with pytest.raises(manifest.BackupManifestValidationError):
        manifest._validate_uuid("x", 1)
    with pytest.raises(manifest.BackupManifestValidationError):
        manifest._validate_uuid("x", "bad")
    with pytest.raises(manifest.BackupManifestValidationError):
        manifest._validate_positive_int("x", True)
    with pytest.raises(manifest.BackupManifestValidationError):
        manifest._validate_nonnegative_int("x", -1)
    with pytest.raises(manifest.BackupManifestValidationError):
        manifest._validate_utc_timestamp("2026-06-15", "x")
    with pytest.raises(manifest.BackupManifestValidationError):
        manifest._validate_utc_timestamp("invalidZ", "x")
    with pytest.raises(manifest.BackupManifestValidationError):
        manifest._validate_digest("x", "sha256:bad")
    for bad in ("", ".", "..", "a/b", "a\\b", "x\x00"):
        with pytest.raises(manifest.BackupManifestValidationError):
            manifest._validate_file_name(bad)
    with pytest.raises(manifest.BackupManifestValidationError):
        manifest._validate_categories("x", "not-list")
    with pytest.raises(manifest.BackupManifestValidationError):
        manifest._validate_categories("x", ("bad-value!",))
    with pytest.raises(manifest.BackupManifestValidationError):
        manifest._validate_categories("x", ("same", "same"))

    initialized = _initialized(tmp_path)
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        service = manifest.BackupManifestService(repository)
        with pytest.raises(manifest.BackupManifestValidationError):
            service.list(limit=0)
        with pytest.raises(manifest.BackupManifestValidationError):
            service.list(limit=201)
