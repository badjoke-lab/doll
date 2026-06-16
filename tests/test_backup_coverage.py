from __future__ import annotations

import copy
import json
import os
import sqlite3
import stat
import zipfile
from dataclasses import replace
from pathlib import Path
from typing import cast
from uuid import uuid4

import pytest

import doll.backup as backup
import doll.backup_manifest as backup_manifest
from doll import state, workspace
from doll.artifact import WorkspaceFileService


def _initialized(tmp_path: Path, name: str = "workspace") -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(tmp_path / name)
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def _archive_members(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path, "r") as archive:
        return {info.filename: archive.read(info) for info in archive.infolist()}


def _state_context(
    tmp_path: Path,
) -> tuple[dict[str, bytes], dict[str, object], backup._ManifestInspection]:
    initialized = _initialized(tmp_path, "state-context")
    output = tmp_path / "state-context.zip"
    backup.create_state_backup(
        initialized.root,
        output,
        created_at="2026-06-15T08:00:00Z",
    )
    members = _archive_members(output)
    manifest = cast(
        dict[str, object],
        json.loads(members[f"{backup.BACKUP_ROOT}/manifest.json"]),
    )
    return members, manifest, backup._validate_manifest(manifest)


def _workspace_context(
    tmp_path: Path,
) -> tuple[dict[str, bytes], dict[str, object], backup._ManifestInspection]:
    initialized = _initialized(tmp_path, "workspace-context")
    with state.open_state_repository(initialized.root) as repository:
        WorkspaceFileService(repository).create_text(
            managed_path="coverage/file.txt",
            text="coverage\n",
            title="coverage",
        )
    output = tmp_path / "workspace-context.zip"
    backup.create_workspace_backup(
        initialized.root,
        output,
        created_at="2026-06-15T09:00:00Z",
    )
    members = _archive_members(output)
    manifest = cast(
        dict[str, object],
        json.loads(members[f"{backup.BACKUP_ROOT}/manifest.json"]),
    )
    return members, manifest, backup._validate_manifest(manifest)


def _manifest_payload(kind: str = "state") -> dict[str, object]:
    included = (
        ["doll_state_package"]
        if kind == "state"
        else ["authoritative_artifacts", "sqlite_state_snapshot", "workspace_identity"]
    )
    excluded = (
        [
            "backup_history",
            "caches",
            "model_assets",
            "reproducible_indexes",
            "runtime_assets",
            "secrets",
            "temporary_files",
        ]
        if kind == "state"
        else [
            "audit_directory_files",
            "backup_history",
            "caches",
            "configuration_files",
            "model_assets",
            "reproducible_indexes",
            "runtime_assets",
            "secrets",
            "temporary_files",
        ]
    )
    return {
        "backup_format_version": 1,
        "backup_kind": kind,
        "workspace_id": str(uuid4()),
        "source_workspace_schema_version": 1,
        "source_state_schema_version": state.CURRENT_SCHEMA_VERSION,
        "source_state_revision": 0,
        "created_at": "2026-06-15T00:00:00Z",
        "checksum_algorithm": "sha256",
        "encryption_state": "none",
        "included_categories": included,
        "excluded_categories": excluded,
        "payload_file_count": 1 if kind == "state" else 2,
        "total_payload_size_bytes": 0,
    }


def test_manifest_validation_rejects_each_contract_violation() -> None:
    assert backup._validate_manifest(_manifest_payload()).backup_kind == "state"
    assert backup._validate_manifest(_manifest_payload("workspace")).backup_kind == "workspace"

    invalid_values: list[dict[str, object]] = [
        {"backup_format_version": 2},
        {"backup_kind": "cloud"},
        {"workspace_id": "bad"},
        {"source_workspace_schema_version": 999},
        {"source_state_schema_version": 999},
        {"source_state_revision": -1},
        {"created_at": "not-utc"},
        {"checksum_algorithm": "md5"},
        {"encryption_state": "encrypted"},
        {"included_categories": []},
        {"excluded_categories": []},
        {"payload_file_count": 0},
        {"total_payload_size_bytes": -1},
    ]
    for update in invalid_values:
        payload = _manifest_payload()
        payload.update(update)
        with pytest.raises(backup.BackupValidationError):
            backup._validate_manifest(payload)


def test_member_checksum_and_required_value_validation() -> None:
    for value in (
        f"{backup.BACKUP_ROOT}/bad\nname",
        f"{backup.BACKUP_ROOT}//bad",
        "other-root/member",
    ):
        with pytest.raises(backup.BackupUnsafePathError):
            backup._validate_member_name(value)

    valid_path = f"{backup.BACKUP_ROOT}/manifest.json"
    valid_entry = {"path": valid_path, "sha256": "1" * 64, "size_bytes": 1}
    assert (
        backup._validate_checksums({"algorithm": "sha256", "entries": [valid_entry]})[valid_path][
            "size_bytes"
        ]
        == 1
    )

    invalid_checksums: list[object] = [
        {"algorithm": "sha256", "entries": [1]},
        {"algorithm": "sha256", "entries": [{"path": 1, "sha256": "1" * 64, "size_bytes": 1}]},
        {
            "algorithm": "sha256",
            "entries": [
                {
                    "path": f"{backup.BACKUP_ROOT}/checksums.json",
                    "sha256": "1" * 64,
                    "size_bytes": 1,
                }
            ],
        },
        {
            "algorithm": "sha256",
            "entries": [valid_entry, valid_entry],
        },
        {
            "algorithm": "sha256",
            "entries": [{"path": valid_path, "sha256": "bad", "size_bytes": 1}],
        },
        {
            "algorithm": "sha256",
            "entries": [{"path": valid_path, "sha256": "1" * 64, "size_bytes": True}],
        },
    ]
    for checksum_value in invalid_checksums:
        with pytest.raises(backup.BackupValidationError):
            backup._validate_checksums(checksum_value)

    with pytest.raises(backup.BackupIntegrityError):
        backup._required_member({}, "missing")
    with pytest.raises(backup.BackupValidationError):
        backup._required_string({"x": 1}, "x")
    with pytest.raises(backup.BackupValidationError):
        backup._required_categories({"x": "bad"}, "x")
    with pytest.raises(backup.BackupValidationError):
        backup._required_categories({"x": [1]}, "x")


def test_json_size_and_regular_file_change_detection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(backup, "MAX_JSON_BYTES", 1)
    with pytest.raises(backup.BackupLimitError):
        backup._load_json_bytes(b"{}", "json")
    monkeypatch.undo()

    directory = tmp_path / "directory"
    directory.mkdir()
    with pytest.raises(backup.BackupUnsafePathError):
        backup._read_regular_file(directory, maximum=100, label="directory")

    oversized = tmp_path / "oversized"
    oversized.write_bytes(b"xx")
    with pytest.raises(backup.BackupLimitError):
        backup._read_regular_file(oversized, maximum=1, label="oversized")

    changing = tmp_path / "changing"
    changing.write_bytes(b"x")
    original_read = Path.read_bytes

    def mutate_after_read(path: Path) -> bytes:
        content = original_read(path)
        if path == changing:
            path.write_bytes(content + b"x")
        return content

    monkeypatch.setattr(Path, "read_bytes", mutate_after_read)
    with pytest.raises(backup.BackupIntegrityError):
        backup._read_regular_file(changing, maximum=10, label="changing")


def test_archive_inventory_and_kind_paths_cover_remaining_rejections(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = zipfile.ZipInfo(f"{backup.BACKUP_ROOT}/x")
    first.file_size = 1
    first.compress_size = 1
    duplicate = zipfile.ZipInfo(first.filename)
    duplicate.file_size = 1
    duplicate.compress_size = 1
    with pytest.raises(backup.BackupUnsafePathError):
        backup._validate_archive_inventory([first, duplicate])

    monkeypatch.setattr(backup, "MAX_BACKUP_MEMBERS", 1)
    with pytest.raises(backup.BackupLimitError):
        backup._validate_archive_inventory([first, zipfile.ZipInfo(f"{backup.BACKUP_ROOT}/y")])
    monkeypatch.undo()

    zero_compressed = zipfile.ZipInfo(f"{backup.BACKUP_ROOT}/zero")
    zero_compressed.file_size = 1
    zero_compressed.compress_size = 0
    with pytest.raises(backup.BackupLimitError):
        backup._validate_archive_inventory([zero_compressed])

    fifo = zipfile.ZipInfo(f"{backup.BACKUP_ROOT}/fifo")
    fifo.external_attr = (stat.S_IFIFO | 0o600) << 16
    with pytest.raises(backup.BackupUnsafePathError):
        backup._validate_archive_inventory([fifo])

    fixed = {
        f"{backup.BACKUP_ROOT}/manifest.json",
        f"{backup.BACKUP_ROOT}/checksums.json",
        f"{backup.BACKUP_ROOT}/README.txt",
    }
    with pytest.raises(backup.BackupIntegrityError):
        backup._validate_member_paths_for_kind(fixed, "state")
    with pytest.raises(backup.BackupIntegrityError):
        backup._validate_member_paths_for_kind(
            {
                *fixed,
                f"{backup.BACKUP_ROOT}/payload/state-package.zip",
                f"{backup.BACKUP_ROOT}/payload/extra",
            },
            "state",
        )
    with pytest.raises(backup.BackupIntegrityError):
        backup._validate_member_paths_for_kind(fixed, "workspace")
    with pytest.raises(backup.BackupIntegrityError):
        backup._validate_member_paths_for_kind(
            {
                *fixed,
                f"{backup.BACKUP_ROOT}/payload/workspace.json",
                f"{backup.BACKUP_ROOT}/payload/state/{state.STATE_DATABASE_NAME}",
                f"{backup.BACKUP_ROOT}/unsupported",
            },
            "workspace",
        )


def test_workspace_layout_and_artifact_tree_special_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initialized = _initialized(tmp_path, "layout-file")
    artifacts = initialized.root / "artifacts"
    artifacts.rmdir()
    artifacts.write_text("not-directory", encoding="utf-8")
    with pytest.raises(backup.BackupValidationError):
        backup._validate_workspace_layout(initialized.root)

    initialized = _initialized(tmp_path, "identity-directory")
    identity = initialized.root / workspace.WORKSPACE_RECORD_NAME
    identity.unlink()
    identity.mkdir()
    with pytest.raises(backup.BackupValidationError):
        backup._validate_workspace_layout(initialized.root)

    initialized = _initialized(tmp_path, "sidecar-directory")
    sidecar = initialized.root / "state" / f"{state.STATE_DATABASE_NAME}-shm"
    sidecar.mkdir()
    with pytest.raises(backup.BackupUnsafePathError):
        backup._validate_workspace_layout(initialized.root)

    collision_tree = tmp_path / "collision-tree"
    collision_tree.mkdir()
    (collision_tree / "A.txt").write_text("a", encoding="utf-8")
    monkeypatch.setattr(
        os,
        "walk",
        lambda root, followlinks=False: [(str(collision_tree), [], ["A.txt", "a.TXT"])],
    )
    with pytest.raises(backup.BackupUnsafePathError):
        backup._artifact_file_paths(collision_tree)
    monkeypatch.undo()

    symlink_tree = tmp_path / "symlink-tree"
    symlink_tree.mkdir()
    target = tmp_path / "target"
    target.mkdir()
    link = symlink_tree / "link-dir"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        return
    with pytest.raises(backup.BackupUnsafePathError):
        backup._artifact_file_paths(symlink_tree)


def _write_snapshot(
    path: Path,
    source: backup._SourceIdentity,
    *,
    metadata: bool = True,
    mismatched: bool = False,
    secret: bool = False,
) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            "CREATE TABLE schema_metadata ("
            "singleton INTEGER PRIMARY KEY, workspace_id TEXT, "
            "schema_version INTEGER, state_revision INTEGER)"
        )
        connection.execute("CREATE TABLE records (sensitivity TEXT)")
        connection.execute("CREATE TABLE audit_events (value INTEGER)")
        if metadata:
            connection.execute(
                "INSERT INTO schema_metadata VALUES (1, ?, ?, ?)",
                (
                    str(uuid4()) if mismatched else source.workspace_id,
                    source.schema_version,
                    source.state_revision,
                ),
            )
        if secret:
            connection.execute("INSERT INTO records VALUES ('secret')")
        connection.commit()
    finally:
        connection.close()


def test_snapshot_and_workspace_identity_failure_modes(tmp_path: Path) -> None:
    initialized = _initialized(tmp_path, "snapshot-source")
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        source = backup._source_identity(repository)

    valid = tmp_path / "valid.sqlite3"
    _write_snapshot(valid, source)
    assert backup._verify_sqlite_snapshot(valid, source).record_count == 0

    missing = tmp_path / "missing-metadata.sqlite3"
    _write_snapshot(missing, source, metadata=False)
    with pytest.raises(backup.BackupIntegrityError):
        backup._verify_sqlite_snapshot(missing, source)

    mismatch = tmp_path / "mismatch.sqlite3"
    _write_snapshot(mismatch, source, mismatched=True)
    with pytest.raises(backup.BackupIntegrityError):
        backup._verify_sqlite_snapshot(mismatch, source)

    secret = tmp_path / "secret.sqlite3"
    _write_snapshot(secret, source, secret=True)
    with pytest.raises(backup.BackupIntegrityError):
        backup._verify_sqlite_snapshot(secret, source)

    corrupt = tmp_path / "corrupt.sqlite3"
    corrupt.write_bytes(b"not sqlite")
    with pytest.raises(backup.BackupIntegrityError):
        backup._verify_sqlite_snapshot(corrupt, source)

    identity = initialized.root / workspace.WORKSPACE_RECORD_NAME
    original = cast(dict[str, object], json.loads(identity.read_text(encoding="utf-8")))
    identity.write_text("not-json", encoding="utf-8")
    with pytest.raises(backup.BackupValidationError):
        backup._read_workspace_identity(initialized.root, source)
    original["workspace_id"] = str(uuid4())
    identity.write_text(json.dumps(original), encoding="utf-8")
    with pytest.raises(backup.BackupIntegrityError):
        backup._read_workspace_identity(initialized.root, source)


def test_state_payload_validation_failure_modes(tmp_path: Path) -> None:
    members, manifest, inspection = _state_context(tmp_path)
    state_member = f"{backup.BACKUP_ROOT}/payload/state-package.zip"

    invalid_nested = dict(members)
    invalid_nested[state_member] = b"invalid"
    with pytest.raises(backup.BackupIntegrityError):
        backup._validate_state_payload(invalid_nested, manifest, inspection)

    with pytest.raises(backup.BackupIntegrityError):
        backup._validate_state_payload(
            members,
            manifest,
            replace(inspection, workspace_id=str(uuid4())),
        )

    invalid_metadata = copy.deepcopy(manifest)
    invalid_metadata["state_package"] = None
    with pytest.raises(backup.BackupValidationError):
        backup._validate_state_payload(members, invalid_metadata, inspection)

    for key in (
        "path",
        "record_count",
        "authoritative_file_count",
        "omitted_secret_record_count",
    ):
        changed = copy.deepcopy(manifest)
        metadata = cast(dict[str, object], changed["state_package"])
        metadata[key] = "bad" if key == "path" else 999999
        with pytest.raises(backup.BackupError):
            backup._validate_state_payload(members, changed, inspection)

    with pytest.raises(backup.BackupIntegrityError):
        backup._validate_state_payload(
            members,
            manifest,
            replace(inspection, payload_file_count=2),
        )


def test_workspace_payload_validation_failure_modes(tmp_path: Path) -> None:
    members, manifest, inspection = _workspace_context(tmp_path)
    workspace_member = f"{backup.BACKUP_ROOT}/payload/workspace.json"
    artifact_member = f"{backup.BACKUP_ROOT}/payload/artifacts/coverage/file.txt"

    invalid_workspace = dict(members)
    invalid_workspace[workspace_member] = b"not-json"
    with pytest.raises(backup.BackupValidationError):
        backup._validate_workspace_payload(invalid_workspace, manifest, inspection)

    with pytest.raises(backup.BackupIntegrityError):
        backup._validate_workspace_payload(
            members,
            manifest,
            replace(inspection, workspace_id=str(uuid4())),
        )

    missing_artifact = dict(members)
    missing_artifact.pop(artifact_member)
    with pytest.raises(backup.BackupIntegrityError):
        backup._validate_workspace_payload(missing_artifact, manifest, inspection)

    changed_artifact = dict(members)
    changed_artifact[artifact_member] = b"changed"
    with pytest.raises(backup.BackupIntegrityError):
        backup._validate_workspace_payload(changed_artifact, manifest, inspection)

    invalid_metadata = copy.deepcopy(manifest)
    invalid_metadata["workspace_snapshot"] = None
    with pytest.raises(backup.BackupValidationError):
        backup._validate_workspace_payload(members, invalid_metadata, inspection)

    for key in (
        "workspace_path",
        "database_path",
        "record_count",
        "audit_event_count",
        "artifact_file_count",
    ):
        changed = copy.deepcopy(manifest)
        metadata = cast(dict[str, object], changed["workspace_snapshot"])
        metadata[key] = "bad" if key.endswith("_path") else 999999
        with pytest.raises(backup.BackupError):
            backup._validate_workspace_payload(members, changed, inspection)

    with pytest.raises(backup.BackupIntegrityError):
        backup._validate_workspace_payload(
            members,
            manifest,
            replace(inspection, payload_file_count=99),
        )


def test_zip_end_record_and_whole_file_integrity(tmp_path: Path) -> None:
    archive = tmp_path / "raw.zip"
    backup._write_deterministic_zip(
        archive,
        {f"{backup.BACKUP_ROOT}/x": b"x"},
    )
    raw = archive.read_bytes()
    backup._validate_zip_end_record(raw)

    for mutated in (
        raw[:-1],
        raw + b"x",
        raw[:-2] + b"\x01\x00",
    ):
        with pytest.raises(backup.BackupIntegrityError):
            backup._validate_zip_end_record(mutated)


def test_publication_mismatch_and_generic_failure_roll_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inspection = backup.BackupInspection(
        backup_format_version=1,
        backup_kind="state",
        workspace_id=str(uuid4()),
        schema_version=state.CURRENT_SCHEMA_VERSION,
        source_state_revision=0,
        created_at="2026-06-15T00:00:00Z",
        included_categories=("doll_state_package",),
        excluded_categories=("secrets",),
        member_count=1,
        payload_file_count=1,
        total_payload_size_bytes=1,
        manifest_hash="sha256:" + "1" * 64,
        file_size_bytes=1,
        file_sha256="sha256:" + "2" * 64,
    )
    changed = replace(inspection, file_sha256="sha256:" + "3" * 64)
    results = iter((inspection, changed))
    monkeypatch.setattr(backup, "verify_backup", lambda path: next(results))
    output = tmp_path / "mismatch.zip"
    with pytest.raises(backup.BackupIntegrityError):
        backup._publish_verified_backup(
            output,
            {f"{backup.BACKUP_ROOT}/x": b"x"},
        )
    assert not output.exists()

    monkeypatch.undo()
    monkeypatch.setattr(
        backup,
        "_write_deterministic_zip",
        lambda path, members: (_ for _ in ()).throw(OSError("synthetic")),
    )
    with pytest.raises(backup.BackupCreationError):
        backup._publish_verified_backup(
            tmp_path / "generic.zip",
            {f"{backup.BACKUP_ROOT}/x": b"x"},
        )


def test_publication_refuses_a_racing_existing_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    members, _, _ = _state_context(tmp_path)
    output = tmp_path / "racing-output.zip"
    existing = b"created-by-another-process"
    original_link = os.link

    def create_destination_then_link(source: Path, destination: Path) -> None:
        Path(destination).write_bytes(existing)
        original_link(source, destination)

    monkeypatch.setattr(os, "link", create_destination_then_link)
    with pytest.raises(backup.BackupCreationError):
        backup._publish_verified_backup(output, members)

    assert output.read_bytes() == existing
    assert not list(tmp_path.glob(f".{output.name}.*.backup.tmp"))


def test_backup_manifest_additional_validation(tmp_path: Path) -> None:
    initialized = _initialized(tmp_path, "manifest-extra")
    with state.open_state_repository(initialized.root) as repository:
        status = repository.status()
        service = backup_manifest.BackupManifestService(repository)
        with pytest.raises(backup_manifest.BackupManifestValidationError):
            service.register_verified(
                backup_kind="state",
                backup_format_version=1,
                workspace_id=status.workspace_id,
                schema_version=status.schema_version,
                source_state_revision=status.state_revision,
                created_at="2026-06-15T01:00:00Z",
                verified_at="2026-06-15T00:00:00Z",
                manifest_hash="sha256:" + "1" * 64,
                file_name="backup.zip",
                file_size_bytes=1,
                file_sha256="sha256:" + "2" * 64,
                included_categories=("state",),
                excluded_categories=("secrets",),
            )
        with pytest.raises(backup_manifest.BackupManifestValidationError):
            service.register_verified(
                backup_kind="state",
                backup_format_version=1,
                workspace_id=status.workspace_id,
                schema_version=status.schema_version,
                source_state_revision=status.state_revision,
                created_at="2026-06-15T00:00:00Z",
                verified_at="2026-06-15T00:01:00Z",
                manifest_hash="sha256:" + "1" * 64,
                file_name="backup.zip",
                file_size_bytes=1,
                file_sha256="sha256:" + "2" * 64,
                included_categories=("same",),
                excluded_categories=("same",),
            )

    with pytest.raises(backup_manifest.BackupManifestValidationError):
        backup_manifest._validate_file_name(1)
    with pytest.raises(backup_manifest.BackupManifestValidationError):
        backup_manifest._validate_file_name("x" * 256)
    with pytest.raises(backup_manifest.BackupManifestValidationError):
        backup_manifest._validate_file_name("bad\nname")
    with pytest.raises(backup_manifest.BackupManifestValidationError):
        backup_manifest._validate_categories("x", tuple("x" for _ in range(65)))
    with pytest.raises(backup_manifest.BackupManifestCorruptError):
        backup_manifest._required_string({}, "x")
    with pytest.raises(backup_manifest.BackupManifestCorruptError):
        backup_manifest._required_int({"x": True}, "x")
    with pytest.raises(backup_manifest.BackupManifestCorruptError):
        backup_manifest._required_string_list({"x": [1]}, "x")
