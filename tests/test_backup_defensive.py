from __future__ import annotations

import hashlib
import json
import os
import stat
import zipfile
from pathlib import Path
from typing import cast

import pytest

import doll.backup as backup
from doll import state, workspace
from doll.artifact import WorkspaceFileService
from doll.backup_manifest import BackupManifestRegistrationError, BackupManifestService


def _initialized(tmp_path: Path, name: str = "workspace") -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(tmp_path / name)
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def _artifact(initialized: workspace.InitializedWorkspace) -> str:
    with state.open_state_repository(initialized.root) as repository:
        value = WorkspaceFileService(repository).create_text(
            managed_path="defensive/file.txt",
            text="defensive\n",
            title="defensive",
        )
    return value.artifact_id


def _state_backup(tmp_path: Path) -> tuple[workspace.InitializedWorkspace, Path]:
    initialized = _initialized(tmp_path)
    _artifact(initialized)
    output = tmp_path / "source.zip"
    backup.create_state_backup(
        initialized.root,
        output,
        created_at="2026-06-15T07:00:00Z",
    )
    return initialized, output


def _read_members(path: Path) -> dict[str, tuple[zipfile.ZipInfo, bytes]]:
    with zipfile.ZipFile(path, "r") as archive:
        return {info.filename: (info, archive.read(info)) for info in archive.infolist()}


def _write_members(
    path: Path,
    members: dict[str, tuple[zipfile.ZipInfo, bytes]],
) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for _, (info, content) in sorted(members.items()):
            archive.writestr(info, content)


def test_create_rejects_existing_output_and_unsafe_locations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initialized = _initialized(tmp_path)
    existing = tmp_path / "existing.zip"
    existing.write_bytes(b"keep")
    with pytest.raises(backup.BackupCreationError):
        backup.create_state_backup(initialized.root, existing)
    assert existing.read_bytes() == b"keep"

    outside_backups = initialized.root / "state-backup.zip"
    with pytest.raises(backup.BackupUnsafePathError):
        backup.create_state_backup(initialized.root, outside_backups)

    monkeypatch.setattr(backup, "find_doll_repository_ancestor", lambda path: path)
    with pytest.raises(backup.BackupUnsafePathError):
        backup.create_state_backup(initialized.root, tmp_path / "inside-repository.zip")


def test_workspace_layout_rejects_unknown_and_config_content(tmp_path: Path) -> None:
    initialized = _initialized(tmp_path, "unknown")
    (initialized.root / "unknown.dat").write_text("unknown", encoding="utf-8")
    with pytest.raises(backup.BackupError):
        backup.create_workspace_backup(initialized.root, tmp_path / "unknown.zip")

    initialized = _initialized(tmp_path, "config")
    (initialized.root / "config" / "accepted-later.json").write_text("{}", encoding="utf-8")
    with pytest.raises(backup.BackupError):
        backup.create_workspace_backup(initialized.root, tmp_path / "config.zip")

    initialized = _initialized(tmp_path, "audit")
    (initialized.root / "audit" / "event.log").write_text("event", encoding="utf-8")
    with pytest.raises(backup.BackupError):
        backup.create_workspace_backup(initialized.root, tmp_path / "audit.zip")


def test_workspace_layout_rejects_missing_database_and_unknown_state_file(
    tmp_path: Path,
) -> None:
    initialized = _initialized(tmp_path, "missing-db")
    database = initialized.root / "state" / state.STATE_DATABASE_NAME
    database.unlink()
    with pytest.raises(backup.BackupError):
        backup.create_workspace_backup(initialized.root, tmp_path / "missing-db.zip")

    initialized = _initialized(tmp_path, "state-extra")
    (initialized.root / "state" / "unknown.db").write_bytes(b"x")
    with pytest.raises(backup.BackupError):
        backup.create_workspace_backup(initialized.root, tmp_path / "state-extra.zip")


def test_workspace_layout_rejects_symlinks(tmp_path: Path) -> None:
    initialized = _initialized(tmp_path)
    target = initialized.root / "temporary" / "target"
    target.write_text("x", encoding="utf-8")
    link = initialized.root / "temporary" / "link"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symbolic links are unavailable")
    with pytest.raises(backup.BackupError):
        backup.create_workspace_backup(initialized.root, tmp_path / "symlink.zip")


def test_unknown_or_missing_artifact_files_are_rejected(tmp_path: Path) -> None:
    initialized = _initialized(tmp_path, "extra-artifact")
    _artifact(initialized)
    (initialized.root / "artifacts" / "extra.txt").write_text("extra", encoding="utf-8")
    with pytest.raises(backup.BackupError):
        backup.create_workspace_backup(initialized.root, tmp_path / "extra-artifact.zip")

    initialized = _initialized(tmp_path, "missing-artifact")
    artifact_id = _artifact(initialized)
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        record = repository.get_record(artifact_id)
        managed_path = cast(str, record.metadata["managed_path"])
    (initialized.root / "artifacts" / managed_path).unlink()
    with pytest.raises(backup.BackupError):
        backup.create_workspace_backup(initialized.root, tmp_path / "missing-artifact.zip")


def test_source_change_and_registration_failure_leave_no_backup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initialized = _initialized(tmp_path, "source-change")
    output = tmp_path / "source-change.zip"
    monkeypatch.setattr(
        backup,
        "_ensure_source_unchanged",
        lambda repository, source: (_ for _ in ()).throw(
            backup.BackupIntegrityError("synthetic source mutation")
        ),
    )
    with pytest.raises(backup.BackupIntegrityError):
        backup.create_state_backup(initialized.root, output)
    assert not output.exists()

    monkeypatch.undo()
    initialized = _initialized(tmp_path, "registration")
    output = tmp_path / "registration.zip"
    monkeypatch.setattr(
        BackupManifestService,
        "register_verified",
        lambda self, **kwargs: (_ for _ in ()).throw(BackupManifestRegistrationError("synthetic")),
    )
    with pytest.raises(backup.BackupRegistrationError):
        backup.create_state_backup(initialized.root, output)
    assert not output.exists()
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        assert BackupManifestService(repository).list() == ()


def test_publication_durability_failure_rolls_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initialized = _initialized(tmp_path)
    output = tmp_path / "durability.zip"
    original = backup._fsync_directory
    calls = 0

    def fail_once(path: Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise backup.BackupCreationError("synthetic fsync failure")
        original(path)

    monkeypatch.setattr(backup, "_fsync_directory", fail_once)
    with pytest.raises(backup.BackupCreationError):
        backup.create_state_backup(initialized.root, output)
    assert not output.exists()


def test_verify_rejects_mutation_removal_addition_and_bad_checksum(tmp_path: Path) -> None:
    _, source = _state_backup(tmp_path)
    payload = f"{backup.BACKUP_ROOT}/payload/state-package.zip"
    checksum = f"{backup.BACKUP_ROOT}/checksums.json"

    members = _read_members(source)
    info, content = members[payload]
    members[payload] = (info, content + b"x")
    mutated = tmp_path / "mutated.zip"
    _write_members(mutated, members)
    with pytest.raises(backup.BackupIntegrityError):
        backup.verify_backup(mutated)

    members = _read_members(source)
    members.pop(payload)
    removed = tmp_path / "removed.zip"
    _write_members(removed, members)
    with pytest.raises(backup.BackupIntegrityError):
        backup.verify_backup(removed)

    members = _read_members(source)
    extra_info = zipfile.ZipInfo(f"{backup.BACKUP_ROOT}/payload/extra.bin")
    members[extra_info.filename] = (extra_info, b"extra")
    added = tmp_path / "added.zip"
    _write_members(added, members)
    with pytest.raises(backup.BackupIntegrityError):
        backup.verify_backup(added)

    members = _read_members(source)
    info, content = members[checksum]
    checksums = cast(dict[str, object], json.loads(content))
    entries = cast(list[dict[str, object]], checksums["entries"])
    entries[0]["sha256"] = "0" * 64
    members[checksum] = (info, backup._json_bytes(checksums))
    bad_checksum = tmp_path / "bad-checksum.zip"
    _write_members(bad_checksum, members)
    with pytest.raises(backup.BackupIntegrityError):
        backup.verify_backup(bad_checksum)


def test_verify_rejects_unsafe_symlink_and_casefold_members(tmp_path: Path) -> None:
    unsafe = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(unsafe, "w") as archive:
        archive.writestr("../escape", b"x")
    with pytest.raises(backup.BackupUnsafePathError):
        backup.verify_backup(unsafe)

    symlink = tmp_path / "symlink-entry.zip"
    info = zipfile.ZipInfo(f"{backup.BACKUP_ROOT}/manifest.json")
    info.create_system = 3
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(symlink, "w") as archive:
        archive.writestr(info, b"x")
    with pytest.raises(backup.BackupUnsafePathError):
        backup.verify_backup(symlink)

    collision = tmp_path / "collision.zip"
    with zipfile.ZipFile(collision, "w") as archive:
        archive.writestr(f"{backup.BACKUP_ROOT}/A", b"a")
        archive.writestr(f"{backup.BACKUP_ROOT}/a", b"b")
    with pytest.raises(backup.BackupUnsafePathError):
        backup.verify_backup(collision)


class _DirectoryInfo(zipfile.ZipInfo):
    def is_dir(self) -> bool:
        return True


def test_archive_limits_and_entry_types(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(backup.BackupLimitError):
        backup._validate_archive_inventory([])

    info = zipfile.ZipInfo(f"{backup.BACKUP_ROOT}/x")
    info.file_size = 2
    info.compress_size = 1
    monkeypatch.setattr(backup, "MAX_BACKUP_MEMBER_BYTES", 1)
    with pytest.raises(backup.BackupLimitError):
        backup._validate_archive_inventory([info])
    monkeypatch.undo()

    monkeypatch.setattr(backup, "MAX_BACKUP_TOTAL_BYTES", 1)
    with pytest.raises(backup.BackupLimitError):
        backup._validate_archive_inventory([info])
    monkeypatch.undo()

    monkeypatch.setattr(backup, "MAX_COMPRESSION_RATIO", 1)
    with pytest.raises(backup.BackupLimitError):
        backup._validate_archive_inventory([info])
    monkeypatch.undo()

    directory = _DirectoryInfo(f"{backup.BACKUP_ROOT}/directory")
    directory.file_size = 0
    directory.compress_size = 0
    with pytest.raises(backup.BackupUnsafePathError):
        backup._validate_archive_inventory([directory])


def test_validation_helpers_cover_fail_closed_paths(tmp_path: Path) -> None:
    for value in (
        "",
        "/absolute",
        "C:/drive",
        f"{backup.BACKUP_ROOT}/../escape",
        f"{backup.BACKUP_ROOT}/bad\\path",
        f"{backup.BACKUP_ROOT}/bad\x00path",
    ):
        with pytest.raises(backup.BackupUnsafePathError):
            backup._validate_member_name(value)

    with pytest.raises(backup.BackupValidationError):
        backup._validate_checksums([])
    with pytest.raises(backup.BackupValidationError):
        backup._validate_checksums({"algorithm": "md5", "entries": []})
    with pytest.raises(backup.BackupValidationError):
        backup._validate_checksums({"algorithm": "sha256", "entries": {}})
    with pytest.raises(backup.BackupValidationError):
        backup._required_nonnegative_int({"x": True}, "x")
    with pytest.raises(backup.BackupValidationError):
        backup._required_positive_int({"x": 0}, "x")
    with pytest.raises(backup.BackupValidationError):
        backup._required_uuid({"x": "bad"}, "x")
    with pytest.raises(backup.BackupValidationError):
        backup._required_categories({"x": ["same", "same"]}, "x")
    with pytest.raises(backup.BackupValidationError):
        backup._validate_utc_timestamp("invalid", "x")
    with pytest.raises(backup.BackupValidationError):
        backup._json_bytes(float("nan"))
    with pytest.raises(backup.BackupValidationError):
        backup._load_json_bytes(b"\xff", "json")
    with pytest.raises(backup.BackupValidationError):
        backup._load_json_bytes(b"NaN", "json")

    missing = tmp_path / "missing"
    with pytest.raises(backup.BackupValidationError):
        backup._read_regular_file(missing, maximum=1, label="missing")


def test_complete_file_hash_changes_after_one_byte_mutation(tmp_path: Path) -> None:
    _, source = _state_backup(tmp_path)
    original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    data = bytearray(source.read_bytes())
    data[-1] ^= 1
    mutated = tmp_path / "one-byte.zip"
    mutated.write_bytes(data)
    assert hashlib.sha256(mutated.read_bytes()).hexdigest() != original_hash
    with pytest.raises(backup.BackupError):
        backup.verify_backup(mutated)


def test_fsync_and_zip_failures_are_wrapped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    existing = tmp_path / "existing.zip"
    existing.write_bytes(b"x")
    with pytest.raises(backup.BackupCreationError):
        backup._write_deterministic_zip(existing, {"x": b"x"})

    with pytest.raises(backup.BackupCreationError):
        backup._fsync_file(tmp_path / "missing")
    if os.name != "nt":
        with pytest.raises(backup.BackupCreationError):
            backup._fsync_directory(tmp_path / "missing-directory")
    monkeypatch.setattr(os, "name", "nt")
    backup._fsync_directory(tmp_path / "missing-directory")
