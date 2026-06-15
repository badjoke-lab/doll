from __future__ import annotations

import copy
import hashlib
import json
import os
import sqlite3
import stat
import zipfile
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest
from typer.testing import CliRunner

import doll.state_package as package
from doll import state, workspace
from doll.artifact import ArtifactInfo, WorkspaceFileService
from doll.cli import app
from doll.settings import PreferenceService
from doll.state import (
    CURRENT_SCHEMA_VERSION,
    RecordEnvelope,
    StateRepository,
    StateStatus,
)
from doll.workspace import WORKSPACE_SCHEMA_VERSION

runner = CliRunner()


def _initialized_workspace(
    tmp_path: Path, name: str = "workspace"
) -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(tmp_path / name)
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def _export_package(
    tmp_path: Path,
    *,
    name: str = "workspace",
    preference_revision: int = 0,
    artifact: bool = False,
) -> tuple[workspace.InitializedWorkspace, Path, str | None]:
    initialized = _initialized_workspace(tmp_path, name)
    preference_id: str | None = None
    with state.open_state_repository(initialized.root) as repository:
        if preference_revision:
            preference = PreferenceService(repository).create(
                key="coverage.preference",
                value={"revision": 1},
            )
            preference_id = preference.record_id
            if preference_revision == 2:
                PreferenceService(repository).update(
                    preference.record_id,
                    expected_revision=1,
                    value={"revision": 2},
                )
        if artifact:
            WorkspaceFileService(repository).create_text(
                managed_path="coverage/file.txt",
                text="coverage artifact\n",
                title="coverage artifact",
            )
    output = tmp_path / f"{name}.zip"
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        package.export_state_package(
            repository,
            output,
            exported_at="2026-06-15T02:00:00Z",
        )
    return initialized, output, preference_id


def _read_members(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path, "r") as archive:
        return {info.filename: archive.read(info) for info in archive.infolist()}


def _write_members(path: Path, members: dict[str, bytes], *, recalculate: bool = True) -> None:
    updated = dict(members)
    checksum_name = f"{package.PACKAGE_ROOT}/checksums.json"
    if recalculate:
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


def _valid_payload_context(
    tmp_path: Path,
) -> tuple[dict[str, object], dict[str, object], dict[str, bytes]]:
    _, source, _ = _export_package(tmp_path)
    members = _read_members(source)
    manifest = cast(
        dict[str, object],
        json.loads(members[f"{package.PACKAGE_ROOT}/manifest.json"]),
    )
    workspace_payload = cast(
        dict[str, object],
        json.loads(members[f"{package.PACKAGE_ROOT}/records/workspace.json"]),
    )
    return manifest, workspace_payload, members


def _record(
    record_type: str,
    metadata: dict[str, object],
    *,
    record_id: str | None = None,
    status: state.RecordStatus = "active",
) -> RecordEnvelope:
    return RecordEnvelope(
        id=record_id or str(uuid4()),
        record_type=record_type,
        schema_version=1,
        created_at="2026-06-15T00:00:00Z",
        updated_at="2026-06-15T00:00:00Z",
        revision=1,
        status=status,
        provenance="user-created",
        sensitivity="personal",
        title="title",
        metadata=metadata,
    )


def _base_preference_payload() -> dict[str, object]:
    return {
        "id": str(uuid4()),
        "record_type": "preference",
        "schema_version": 1,
        "created_at": "2026-06-15T00:00:00Z",
        "updated_at": "2026-06-15T00:00:00Z",
        "revision": 1,
        "status": "active",
        "provenance": "user-created",
        "sensitivity": "personal",
        "title": "coverage.key",
        "metadata": {
            "preference_key": "coverage.key",
            "value": "value",
            "description": None,
        },
    }


def _base_audit(sequence: int = 1, event_id: str | None = None) -> dict[str, object]:
    return {
        "sequence": sequence,
        "event_id": event_id or str(uuid4()),
        "operation_id": "coverage-operation",
        "occurred_at": "2026-06-15T00:00:00Z",
        "actor_type": "user",
        "actor_id": None,
        "action": "coverage.action",
        "target_type": None,
        "target_id": None,
        "result": "success",
        "summary": None,
        "error_class": None,
        "metadata": {},
    }


def _base_migration(run_id: str | None = None) -> dict[str, object]:
    return {
        "migration_run_id": run_id or str(uuid4()),
        "migration_id": "coverage-migration",
        "from_schema_version": 1,
        "to_schema_version": 2,
        "started_at": "2026-06-15T00:00:00Z",
        "completed_at": "2026-06-15T00:01:00Z",
        "status": "completed",
        "error_class": None,
    }


def test_export_guards_and_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initialized = _initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as writable:
        with pytest.raises(package.StatePackageValidationError):
            package.export_state_package(writable, tmp_path / "writable.zip")

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        repository.workspace = workspace.InitializedWorkspace(
            root=repository.workspace.root,
            record=repository.workspace.record.model_copy(update={"state_revision": 1}),
        )
        with pytest.raises(package.StatePackageValidationError):
            package.export_state_package(repository, tmp_path / "revision.zip")

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        monkeypatch.setattr(package, "find_doll_repository_ancestor", lambda path: path)
        with pytest.raises(package.StatePackageUnsafePathError):
            package.export_state_package(repository, tmp_path / "inside.zip")

    monkeypatch.undo()
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        monkeypatch.setattr(
            package,
            "verify_state_package",
            lambda path: (_ for _ in ()).throw(package.StatePackageIntegrityError("synthetic")),
        )
        output = tmp_path / "verification.zip"
        with pytest.raises(package.StatePackageIntegrityError):
            package.export_state_package(repository, output)
        assert not output.exists()

    monkeypatch.undo()
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        monkeypatch.setattr(
            package,
            "_write_deterministic_zip",
            lambda path, members: (_ for _ in ()).throw(OSError("synthetic")),
        )
        output = tmp_path / "write.zip"
        with pytest.raises(package.StatePackageExportError):
            package.export_state_package(repository, output)
        assert not output.exists()


def test_build_export_members_database_and_artifact_branches(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initialized = _initialized_workspace(tmp_path, "records-corrupt")
    with state.open_state_repository(initialized.root) as repository:
        repository.connection.execute("DROP TABLE records")
        with pytest.raises(package.StatePackageValidationError):
            package._build_export_members(repository, "2026-06-15T02:00:00Z")

    initialized = _initialized_workspace(tmp_path, "duplicate-artifact")
    with state.open_state_repository(initialized.root) as repository:
        artifact = WorkspaceFileService(repository).create_text(
            managed_path="duplicate/file.txt",
            text="duplicate\n",
            title="duplicate",
        )
        original = repository.get_record(artifact.artifact_id)
        repository.create_record(
            record_type="artifact",
            provenance=original.provenance,
            sensitivity=original.sensitivity,
            title=original.title,
            metadata=original.metadata,
        )
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        with pytest.raises(package.StatePackageValidationError):
            package._build_export_members(repository, "2026-06-15T02:00:00Z")

    initialized = _initialized_workspace(tmp_path, "artifact-hash")
    with state.open_state_repository(initialized.root) as repository:
        WorkspaceFileService(repository).create_text(
            managed_path="hash/file.txt",
            text="hash\n",
            title="hash",
        )
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        monkeypatch.setattr(
            WorkspaceFileService,
            "verify",
            lambda self, artifact_id: SimpleNamespace(actual_hash="sha256:" + "0" * 64),
        )
        with pytest.raises(package.StatePackageIntegrityError):
            package._build_export_members(repository, "2026-06-15T02:00:00Z")


def test_zip_and_fsync_error_wrapping(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    existing = tmp_path / "existing.zip"
    existing.write_bytes(b"x")
    with pytest.raises(package.StatePackageExportError):
        package._write_deterministic_zip(existing, {"x": b"x"})
    with pytest.raises(package.StatePackageExportError):
        package._fsync_file(tmp_path / "missing")
    with pytest.raises(package.StatePackageError):
        package._fsync_directory(tmp_path / "missing-dir")
    monkeypatch.setattr(os, "name", "nt")
    package._fsync_directory(tmp_path / "missing-dir")


def test_load_package_regular_file_and_checksum_failures(tmp_path: Path) -> None:
    _, source, _ = _export_package(tmp_path)
    symlink = tmp_path / "package-link.zip"
    symlink.symlink_to(source)
    with pytest.raises(package.StatePackageValidationError):
        package.verify_state_package(symlink)

    bad = tmp_path / "bad.zip"
    bad.write_bytes(b"not-a-zip")
    with pytest.raises(package.StatePackageValidationError):
        package.verify_state_package(bad)

    members = _read_members(source)
    checksum_name = f"{package.PACKAGE_ROOT}/checksums.json"
    checksums = cast(dict[str, object], json.loads(members[checksum_name]))
    entries = cast(list[dict[str, object]], checksums["entries"])
    entries[0]["size_bytes"] = cast(int, entries[0]["size_bytes"]) + 1
    members[checksum_name] = package._json_bytes(checksums)
    wrong_size = tmp_path / "wrong-size.zip"
    _write_members(wrong_size, members, recalculate=False)
    with pytest.raises(package.StatePackageIntegrityError):
        package.verify_state_package(wrong_size)

    members = _read_members(source)
    checksums = cast(dict[str, object], json.loads(members[checksum_name]))
    entries = cast(list[dict[str, object]], checksums["entries"])
    entries[0]["sha256"] = "0" * 64
    members[checksum_name] = package._json_bytes(checksums)
    wrong_hash = tmp_path / "wrong-hash.zip"
    _write_members(wrong_hash, members, recalculate=False)
    with pytest.raises(package.StatePackageIntegrityError):
        package.verify_state_package(wrong_hash)


class _DirectoryInfo(zipfile.ZipInfo):
    def is_dir(self) -> bool:
        return True


def test_archive_inventory_all_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(package.StatePackageLimitError):
        package._validate_archive_inventory([])

    info = zipfile.ZipInfo(f"{package.PACKAGE_ROOT}/x")
    info.file_size = 1
    info.compress_size = 1
    monkeypatch.setattr(package, "MAX_PACKAGE_MEMBERS", 0)
    with pytest.raises(package.StatePackageLimitError):
        package._validate_archive_inventory([info])
    monkeypatch.undo()

    duplicate_a = zipfile.ZipInfo(f"{package.PACKAGE_ROOT}/x")
    duplicate_a.file_size = duplicate_a.compress_size = 1
    duplicate_b = zipfile.ZipInfo(f"{package.PACKAGE_ROOT}/x")
    duplicate_b.file_size = duplicate_b.compress_size = 1
    with pytest.raises(package.StatePackageUnsafePathError):
        package._validate_archive_inventory([duplicate_a, duplicate_b])

    directory = _DirectoryInfo(f"{package.PACKAGE_ROOT}/directory")
    directory.file_size = directory.compress_size = 1
    with pytest.raises(package.StatePackageUnsafePathError):
        package._validate_archive_inventory([directory])

    negative = zipfile.ZipInfo(f"{package.PACKAGE_ROOT}/negative")
    negative.file_size = -1
    negative.compress_size = 1
    with pytest.raises(package.StatePackageLimitError):
        package._validate_archive_inventory([negative])

    fifo = zipfile.ZipInfo(f"{package.PACKAGE_ROOT}/fifo")
    fifo.external_attr = (stat.S_IFIFO | 0o600) << 16
    fifo.file_size = fifo.compress_size = 1
    with pytest.raises(package.StatePackageUnsafePathError):
        package._validate_archive_inventory([fifo])

    too_large = zipfile.ZipInfo(f"{package.PACKAGE_ROOT}/large")
    too_large.file_size = 2
    too_large.compress_size = 1
    monkeypatch.setattr(package, "MAX_PACKAGE_MEMBER_BYTES", 1)
    with pytest.raises(package.StatePackageLimitError):
        package._validate_archive_inventory([too_large])
    monkeypatch.undo()

    first = zipfile.ZipInfo(f"{package.PACKAGE_ROOT}/first")
    first.file_size = first.compress_size = 1
    second = zipfile.ZipInfo(f"{package.PACKAGE_ROOT}/second")
    second.file_size = second.compress_size = 1
    monkeypatch.setattr(package, "MAX_PACKAGE_TOTAL_BYTES", 1)
    with pytest.raises(package.StatePackageLimitError):
        package._validate_archive_inventory([first, second])
    monkeypatch.undo()

    zero_compressed = zipfile.ZipInfo(f"{package.PACKAGE_ROOT}/zero")
    zero_compressed.file_size = 1
    zero_compressed.compress_size = 0
    with pytest.raises(package.StatePackageLimitError):
        package._validate_archive_inventory([zero_compressed])

    ratio = zipfile.ZipInfo(f"{package.PACKAGE_ROOT}/ratio")
    ratio.file_size = 2
    ratio.compress_size = 1
    monkeypatch.setattr(package, "MAX_COMPRESSION_RATIO", 1)
    with pytest.raises(package.StatePackageLimitError):
        package._validate_archive_inventory([ratio])


def test_member_and_checksum_validation_branches() -> None:
    assert package._validate_member_name(f"{package.PACKAGE_ROOT}/x") == (
        f"{package.PACKAGE_ROOT}/x"
    )
    for value in (
        f"{package.PACKAGE_ROOT}/bad\\path",
        f"{package.PACKAGE_ROOT}/bad\npath",
        "/absolute",
        "C:/absolute",
        f"{package.PACKAGE_ROOT}//x",
        "wrong-root/x",
    ):
        with pytest.raises(package.StatePackageUnsafePathError):
            package._validate_member_name(value)

    valid_entry: dict[str, object] = {
        "path": f"{package.PACKAGE_ROOT}/x",
        "sha256": "0" * 64,
        "size_bytes": 0,
    }
    assert package._validate_checksums({"algorithm": "sha256", "entries": [valid_entry]})
    invalid_entries: tuple[object, ...] = (
        "entry",
        {"path": 1, "sha256": "0" * 64, "size_bytes": 0},
        {
            "path": f"{package.PACKAGE_ROOT}/checksums.json",
            "sha256": "0" * 64,
            "size_bytes": 0,
        },
        {"path": f"{package.PACKAGE_ROOT}/x", "sha256": "bad", "size_bytes": 0},
        {"path": f"{package.PACKAGE_ROOT}/x", "sha256": "0" * 64, "size_bytes": True},
    )
    for invalid in invalid_entries:
        with pytest.raises(package.StatePackageValidationError):
            package._validate_checksums({"algorithm": "sha256", "entries": [invalid]})
    with pytest.raises(package.StatePackageValidationError):
        package._validate_checksums({"algorithm": "sha256", "entries": [valid_entry, valid_entry]})


def test_manifest_workspace_and_count_validation(tmp_path: Path) -> None:
    manifest, workspace_payload, members = _valid_payload_context(tmp_path)
    assert (
        package._validate_package_payloads(
            manifest,
            workspace_payload,
            members,
        ).inspection.workspace_id
        == manifest["workspace_id"]
    )

    with pytest.raises(package.StatePackageValidationError):
        package._validate_package_payloads([], workspace_payload, members)

    mutations: tuple[tuple[str, object], ...] = (
        ("package_format_version", 999),
        ("checksum_algorithm", "md5"),
        ("encryption_state", "encrypted"),
        ("workspace_id", "invalid"),
        ("exported_at", "not-utc"),
        ("source_state_schema_version", CURRENT_SCHEMA_VERSION + 1),
        ("source_state_schema_version", CURRENT_SCHEMA_VERSION - 1),
        ("record_counts", []),
        ("omitted_secret_counts", []),
    )
    for key, value in mutations:
        changed = copy.deepcopy(manifest)
        changed[key] = value
        with pytest.raises(package.StatePackageValidationError):
            package._validate_package_payloads(changed, workspace_payload, members)

    with pytest.raises(package.StatePackageValidationError):
        package._validate_package_payloads(manifest, [], members)
    with pytest.raises(package.StatePackageValidationError):
        package._validate_package_payloads(manifest, {}, members)

    duplicate_manifest = copy.deepcopy(manifest)
    duplicate_counts = cast(dict[str, object], duplicate_manifest["record_counts"])
    duplicate_counts["preference"] = 2
    duplicate_members = dict(members)
    duplicate_line = package._json_bytes(_base_preference_payload())
    duplicate_members[f"{package.PACKAGE_ROOT}/records/preferences.jsonl"] = (
        duplicate_line + duplicate_line
    )
    with pytest.raises(package.StatePackageValidationError):
        package._validate_package_payloads(
            duplicate_manifest,
            workspace_payload,
            duplicate_members,
        )

    changed_workspace = copy.deepcopy(workspace_payload)
    changed_workspace["schema_version"] = WORKSPACE_SCHEMA_VERSION + 1
    with pytest.raises(package.StatePackageValidationError):
        package._validate_package_payloads(manifest, changed_workspace, members)

    changed_workspace = copy.deepcopy(workspace_payload)
    changed_workspace["workspace_id"] = str(uuid4())
    with pytest.raises(package.StatePackageIntegrityError):
        package._validate_package_payloads(manifest, changed_workspace, members)

    changed_workspace = copy.deepcopy(workspace_payload)
    changed_workspace["state_revision"] = cast(int, manifest["state_revision"]) + 1
    with pytest.raises(package.StatePackageIntegrityError):
        package._validate_package_payloads(manifest, changed_workspace, members)

    for key in (
        "record_counts",
        "audit_event_count",
        "migration_history_count",
        "authoritative_file_count",
        "total_payload_size_bytes",
    ):
        changed = copy.deepcopy(manifest)
        if key == "record_counts":
            counts = cast(dict[str, object], changed[key])
            counts["memory"] = 1
        else:
            changed[key] = cast(int, changed[key]) + 1
        with pytest.raises(package.StatePackageIntegrityError):
            package._validate_package_payloads(changed, workspace_payload, members)


def test_envelope_validation_branches() -> None:
    base = _base_preference_payload()
    assert package._envelope_from_payload(base, "preference").record_type == "preference"

    with pytest.raises(package.StatePackageValidationError):
        package._envelope_from_payload([], "preference")

    variants: list[tuple[dict[str, object], str]] = []
    wrong_type = copy.deepcopy(base)
    wrong_type["record_type"] = "policy"
    variants.append((wrong_type, "preference"))
    reversed_time = copy.deepcopy(base)
    reversed_time["created_at"] = "2026-06-15T01:00:00Z"
    variants.append((reversed_time, "preference"))
    invalid_title = copy.deepcopy(base)
    invalid_title["title"] = 1
    variants.append((invalid_title, "preference"))
    invalid_metadata = copy.deepcopy(base)
    invalid_metadata["metadata"] = []
    variants.append((invalid_metadata, "preference"))
    invalid_status = copy.deepcopy(base)
    invalid_status["status"] = "deleted"
    variants.append((invalid_status, "preference"))
    secret = copy.deepcopy(base)
    secret["sensitivity"] = "secret"
    variants.append((secret, "preference"))
    for payload, expected_type in variants:
        with pytest.raises(package.StatePackageValidationError):
            package._envelope_from_payload(payload, expected_type)

    invalid_provenance = copy.deepcopy(base)
    invalid_provenance["provenance"] = "invalid"
    with pytest.raises(state.RecordValidationError):
        package._envelope_from_payload(invalid_provenance, "preference")

    for record_type in (
        "preference",
        "policy",
        "permission",
        "memory",
        "project",
        "decision",
        "artifact",
        "unknown",
    ):
        malformed = copy.deepcopy(base)
        malformed["record_type"] = record_type
        malformed["metadata"] = {}
        malformed["title"] = "title"
        with pytest.raises(package.StatePackageValidationError):
            package._envelope_from_payload(malformed, record_type)


def test_cross_record_links_and_setting_identities() -> None:
    missing = str(uuid4())
    memory = _record(
        "memory",
        {"related_memory_ids": [missing], "contradicts_memory_ids": []},
    )
    with pytest.raises(package.StatePackageValidationError):
        package._validate_cross_record_links({memory.id: memory})

    project = _record(
        "project",
        {"decision_ids": [missing], "memory_ids": [], "artifact_ids": []},
    )
    with pytest.raises(package.StatePackageValidationError):
        package._validate_cross_record_links({project.id: project})

    project = replace(
        project,
        metadata={"decision_ids": [], "memory_ids": [missing], "artifact_ids": []},
    )
    with pytest.raises(package.StatePackageValidationError):
        package._validate_cross_record_links({project.id: project})

    project = replace(
        project,
        metadata={"decision_ids": [], "memory_ids": [], "artifact_ids": [missing]},
    )
    with pytest.raises(package.StatePackageValidationError):
        package._validate_cross_record_links({project.id: project})

    decision = _record(
        "decision",
        {
            "project_id": missing,
            "supersedes_id": None,
            "memory_ids": [],
            "artifact_ids": [],
        },
    )
    with pytest.raises(package.StatePackageValidationError):
        package._validate_cross_record_links({decision.id: decision})

    self_superseding = replace(
        decision,
        metadata={
            "project_id": None,
            "supersedes_id": decision.id,
            "memory_ids": [],
            "artifact_ids": [],
        },
    )
    with pytest.raises(package.StatePackageValidationError):
        package._validate_cross_record_links({decision.id: self_superseding})

    unrelated = _record("other", {})
    package._validate_cross_record_links({unrelated.id: unrelated})

    preference_a = _record("preference", {"preference_key": "same"})
    preference_b = _record("preference", {"preference_key": "same"})
    with pytest.raises(package.StatePackageValidationError):
        package._validate_active_setting_identities([preference_a, preference_b])

    policy_a = _record("policy", {"policy_key": "same"})
    policy_b = _record("policy", {"policy_key": "same"})
    with pytest.raises(package.StatePackageValidationError):
        package._validate_active_setting_identities([policy_a, policy_b])

    permission_a = _record("permission", {"permission_identity": "same"})
    permission_b = _record("permission", {"permission_identity": "same"})
    with pytest.raises(package.StatePackageValidationError):
        package._validate_active_setting_identities([permission_a, permission_b])

    package._validate_active_setting_identities(
        [preference_a, replace(preference_b, status="archived"), unrelated]
    )


def test_artifact_member_validation() -> None:
    content = b"artifact"
    digest = f"sha256:{hashlib.sha256(content).hexdigest()}"
    first = ArtifactInfo(
        artifact_id=str(uuid4()),
        title="first",
        artifact_type="text",
        managed_path="same.txt",
        content_hash=digest,
        size_bytes=len(content),
        created_by="user",
        operation_id="coverage",
        created_at="2026-06-15T00:00:00Z",
        sensitivity="personal",
        format="txt",
        media_type="text/plain",
    )
    second = replace(first, artifact_id=str(uuid4()))
    with pytest.raises(package.StatePackageValidationError):
        package._validate_artifact_members(
            {first.artifact_id: first, second.artifact_id: second},
            {},
        )
    with pytest.raises(package.StatePackageIntegrityError):
        package._validate_artifact_members({first.artifact_id: first}, {})

    member_name = f"{package.PACKAGE_ROOT}/files/authoritative/same.txt"
    with pytest.raises(package.StatePackageIntegrityError):
        package._validate_artifact_members(
            {first.artifact_id: first},
            {member_name: content + b"x"},
        )
    wrong_hash = replace(first, content_hash="sha256:" + "0" * 64)
    with pytest.raises(package.StatePackageIntegrityError):
        package._validate_artifact_members(
            {wrong_hash.artifact_id: wrong_hash},
            {member_name: content},
        )
    assert package._validate_artifact_members(
        {first.artifact_id: first},
        {member_name: content},
    ) == {"same.txt": content}


def test_audit_and_migration_validation_branches() -> None:
    audit = _base_audit()
    assert package._validate_audit_events([audit]) == (audit,)
    invalid_audits: list[list[object]] = [
        ["bad"],
        [audit, copy.deepcopy(audit)],
        [audit, _base_audit(sequence=2, event_id=cast(str, audit["event_id"]))],
    ]
    invalid_actor = _base_audit()
    invalid_actor["actor_type"] = "invalid"
    invalid_audits.append([invalid_actor])
    invalid_result = _base_audit()
    invalid_result["result"] = "invalid"
    invalid_audits.append([invalid_result])
    invalid_metadata = _base_audit()
    invalid_metadata["metadata"] = []
    invalid_audits.append([invalid_metadata])
    invalid_optional = _base_audit()
    invalid_optional["actor_id"] = 1
    invalid_audits.append([invalid_optional])
    for payloads in invalid_audits:
        with pytest.raises(package.StatePackageValidationError):
            package._validate_audit_events(payloads)

    migration = _base_migration()
    assert package._validate_migration_history([migration]) == (migration,)
    with pytest.raises(package.StatePackageValidationError):
        package._validate_migration_history(["bad"])
    with pytest.raises(package.StatePackageValidationError):
        package._validate_migration_history([migration, copy.deepcopy(migration)])
    invalid_completed = _base_migration()
    invalid_completed["completed_at"] = 1
    with pytest.raises(package.StatePackageValidationError):
        package._validate_migration_history([invalid_completed])
    invalid_status = _base_migration()
    invalid_status["status"] = "invalid"
    with pytest.raises(package.StatePackageValidationError):
        package._validate_migration_history([invalid_status])
    invalid_error = _base_migration()
    invalid_error["error_class"] = 1
    with pytest.raises(package.StatePackageValidationError):
        package._validate_migration_history([invalid_error])


def test_target_conflict_categories(tmp_path: Path) -> None:
    _, source, preference_id = _export_package(
        tmp_path,
        name="source",
        preference_revision=1,
    )
    assert preference_id is not None
    data = package._load_package(source)

    assert package._target_conflicts(data, tmp_path / "absent") == ()
    file_target = tmp_path / "file-target"
    file_target.write_text("x", encoding="utf-8")
    assert package._target_conflicts(data, file_target)[0].kind == "target_not_directory"
    empty_target = tmp_path / "empty-target"
    empty_target.mkdir()
    assert package._target_conflicts(data, empty_target) == ()
    nonempty = tmp_path / "nonempty"
    nonempty.mkdir()
    (nonempty / "x").write_text("x", encoding="utf-8")
    assert package._target_conflicts(data, nonempty)[0].kind == "target_not_empty"

    different = _initialized_workspace(tmp_path, "different")
    assert package._target_conflicts(data, different.root)[0].kind == "workspace_id_conflict"

    imported = tmp_path / "imported"
    package.import_state_package(source, imported)
    conflict_kinds = {item.kind for item in package._target_conflicts(data, imported)}
    assert "existing_record" in conflict_kinds

    with state.open_state_repository(imported) as repository:
        PreferenceService(repository).update(
            preference_id,
            expected_revision=1,
            value={"revision": 2},
        )
    assert package._target_conflicts(data, imported)[0].kind == "newer_target_revision"

    imported_same = tmp_path / "imported-same"
    package.import_state_package(source, imported_same)
    with state.open_state_repository(imported_same) as repository:
        repository.connection.execute(
            "UPDATE records SET metadata_json = ? WHERE id = ?",
            (
                '{"description":null,"preference_key":"coverage.preference","value":"changed"}',
                preference_id,
            ),
        )
    assert package._target_conflicts(data, imported_same)[0].kind == (
        "same_revision_different_content"
    )

    _, source_v2, preference_v2 = _export_package(
        tmp_path,
        name="source-v2",
        preference_revision=2,
    )
    assert preference_v2 is not None
    data_v2 = package._load_package(source_v2)
    imported_old = tmp_path / "imported-old"
    package.import_state_package(source_v2, imported_old)
    with state.open_state_repository(imported_old) as repository:
        repository.connection.execute(
            "UPDATE records SET revision = 1 WHERE id = ?",
            (preference_v2,),
        )
    assert package._target_conflicts(data_v2, imported_old)[0].kind == "older_target_record"

    broken = tmp_path / "broken"
    package.import_state_package(source, broken)
    (broken / "state" / state.STATE_DATABASE_NAME).unlink()
    assert package._target_conflicts(data, broken)[0].kind == "target_state_unreadable"

    _, empty_source, _ = _export_package(tmp_path, name="empty-source")
    empty_data = package._load_package(empty_source)
    local_only = tmp_path / "local-only"
    package.import_state_package(empty_source, local_only)
    with state.open_state_repository(local_only) as repository:
        PreferenceService(repository).create(key="local.only", value=True)
    assert package._target_conflicts(empty_data, local_only)[0].kind == "target_not_empty"


def test_artifact_collision_and_read_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initialized, source, _ = _export_package(tmp_path, name="artifact-source", artifact=True)
    data = package._load_package(source)
    target = tmp_path / "artifact-imported"
    package.import_state_package(source, target)
    kinds = {item.kind for item in package._target_conflicts(data, target)}
    assert "artifact_path_collision" in kinds

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        artifact = WorkspaceFileService(repository).list()[0]
        path = initialized.root / "artifacts" / artifact.managed_path
        original = path.read_bytes()

        path.unlink()
        with pytest.raises(package.StatePackageIntegrityError):
            package._read_artifact_bytes(repository, artifact)
        path.write_bytes(original + b"x")
        with pytest.raises(package.StatePackageIntegrityError):
            package._read_artifact_bytes(repository, artifact)
        path.write_bytes(b"X" * len(original))
        with pytest.raises(package.StatePackageIntegrityError):
            package._read_artifact_bytes(repository, artifact)
        path.write_bytes(original)
        monkeypatch.setattr(package, "DEFAULT_MAX_ARTIFACT_BYTES", 1)
        with pytest.raises(package.StatePackageLimitError):
            package._read_artifact_bytes(repository, artifact)


def test_import_error_cleanup_and_unsafe_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, source, _ = _export_package(tmp_path)
    target = tmp_path / "target"
    monkeypatch.setattr(package, "find_doll_repository_ancestor", lambda path: path)
    with pytest.raises(package.StatePackageUnsafePathError):
        package.import_state_package(source, target)
    assert not target.exists()

    monkeypatch.undo()
    monkeypatch.setattr(
        package,
        "_initialize_import_workspace",
        lambda root, record: (_ for _ in ()).throw(
            package.StatePackageValidationError("synthetic")
        ),
    )
    with pytest.raises(package.StatePackageValidationError):
        package.import_state_package(source, target)
    assert not target.exists()

    monkeypatch.undo()
    monkeypatch.setattr(
        package,
        "_initialize_import_workspace",
        lambda root, record: (_ for _ in ()).throw(RuntimeError("synthetic")),
    )
    with pytest.raises(package.StatePackageImportError):
        package.import_state_package(source, target)
    assert not target.exists()


def test_initialize_and_publish_failure_branches(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "staging"
    root.mkdir()
    (root / "x").write_text("x", encoding="utf-8")
    record = workspace.WorkspaceRecord.create(
        instance_label="coverage",
        profile_preference="lite",
    )
    with pytest.raises(package.StatePackageImportError):
        package._initialize_import_workspace(root, record)

    staging = tmp_path / "publish-staging"
    staging.mkdir()
    target = tmp_path / "publish-target"
    target.mkdir()
    (target / "x").write_text("x", encoding="utf-8")
    with pytest.raises(package.StatePackageConflictError):
        package._publish_import_target(staging, target)

    staging = tmp_path / "generic-staging"
    staging.mkdir()
    target = tmp_path / "generic-target"
    original_replace = os.replace

    def fail_replace(source: Path, destination: Path) -> None:
        raise OSError("synthetic")

    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(package.StatePackageImportError):
        package._publish_import_target(staging, target)
    monkeypatch.setattr(os, "replace", original_replace)

    staging = tmp_path / "restore-staging"
    staging.mkdir()
    target = tmp_path / "restore-target"
    target.mkdir()
    calls = 0

    def conflict_second(source: Path, destination: Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise package.StatePackageConflictError("synthetic")
        original_replace(source, destination)

    monkeypatch.setattr(os, "replace", conflict_second)
    with pytest.raises(package.StatePackageConflictError):
        package._publish_import_target(staging, target)
    assert target.is_dir()


def test_database_export_and_import_failure_branches(tmp_path: Path) -> None:
    initialized = _initialized_workspace(tmp_path, "audit-corrupt")
    with state.open_state_repository(initialized.root) as repository:
        repository.connection.execute("DROP TABLE audit_events")
        with pytest.raises(package.StatePackageValidationError):
            package._export_audit_events(repository)

    initialized = _initialized_workspace(tmp_path, "audit-metadata")
    with state.open_state_repository(initialized.root) as repository:
        PreferenceService(repository).create(key="audit.metadata", value=True)
        repository.connection.execute("DROP TRIGGER audit_events_no_update")
        repository.connection.execute("UPDATE audit_events SET metadata_json = '[]'")
        with pytest.raises(package.StatePackageValidationError):
            package._export_audit_events(repository)

    initialized = _initialized_workspace(tmp_path, "migration-corrupt")
    with state.open_state_repository(initialized.root) as repository:
        repository.connection.execute("DROP TABLE migration_history")
        with pytest.raises(package.StatePackageValidationError):
            package._export_migration_history(repository)


class _FailingConnection:
    def __init__(self, error: BaseException) -> None:
        self.error = error
        self.in_transaction = False
        self.rolled_back = False

    def execute(self, sql: str, parameters: object = ()) -> None:
        if sql == "BEGIN IMMEDIATE":
            self.in_transaction = True
            return
        if sql == "ROLLBACK":
            self.in_transaction = False
            self.rolled_back = True
            return
        raise self.error


class _FakeRepository:
    def __init__(self, connection: _FailingConnection) -> None:
        self.connection = connection


def test_import_database_rollback_branches(tmp_path: Path) -> None:
    _, source, _ = _export_package(tmp_path)
    data = package._load_package(source)

    database_connection = _FailingConnection(sqlite3.DatabaseError("synthetic"))
    with pytest.raises(package.StatePackageImportError):
        package._import_database_rows(
            cast(StateRepository, _FakeRepository(database_connection)),
            data,
        )
    assert database_connection.rolled_back

    runtime_connection = _FailingConnection(RuntimeError("synthetic"))
    with pytest.raises(RuntimeError):
        package._import_database_rows(
            cast(StateRepository, _FakeRepository(runtime_connection)),
            data,
        )
    assert runtime_connection.rolled_back


class _StaticReadRepository:
    def __init__(
        self,
        status_value: StateStatus,
        records: dict[str, RecordEnvelope],
    ) -> None:
        self.status_value = status_value
        self.records = records

    def __enter__(self) -> _StaticReadRepository:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        return None

    def status(self) -> StateStatus:
        return self.status_value

    def get_record(self, record_id: str) -> RecordEnvelope:
        return self.records[record_id]


def test_validate_imported_workspace_error_branches(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, source, _ = _export_package(
        tmp_path,
        name="validation-source",
        preference_revision=1,
    )
    data = package._load_package(source)
    record = data.records[0]
    expected_revision = data.inspection.state_revision + 1

    def install(status_value: StateStatus, record_value: RecordEnvelope) -> None:
        fake = _StaticReadRepository(status_value, {record.id: record_value})
        monkeypatch.setattr(package, "open_state_repository", lambda *args, **kwargs: fake)

    base_status = StateStatus(
        workspace_id=data.inspection.workspace_id,
        schema_version=data.inspection.schema_version,
        state_revision=expected_revision,
        record_count=len(data.records),
        read_only=True,
        database_path=tmp_path / "fake.sqlite3",
    )

    install(replace(base_status, workspace_id=str(uuid4())), record)
    with pytest.raises(package.StatePackageIntegrityError):
        package._validate_imported_workspace(tmp_path, data, expected_revision)

    install(replace(base_status, state_revision=expected_revision + 1), record)
    with pytest.raises(package.StatePackageIntegrityError):
        package._validate_imported_workspace(tmp_path, data, expected_revision)

    install(replace(base_status, record_count=len(data.records) + 1), record)
    with pytest.raises(package.StatePackageIntegrityError):
        package._validate_imported_workspace(tmp_path, data, expected_revision)

    install(base_status, replace(record, title="changed"))
    with pytest.raises(package.StatePackageIntegrityError):
        package._validate_imported_workspace(tmp_path, data, expected_revision)

    def fail_open(*args: object, **kwargs: object) -> object:
        raise RuntimeError("synthetic")

    monkeypatch.setattr(package, "open_state_repository", fail_open)
    with pytest.raises(package.StatePackageImportError):
        package._validate_imported_workspace(tmp_path, data, expected_revision)


def test_json_and_metadata_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(package.StatePackageValidationError):
        package._load_json_text("NaN", "value")
    with pytest.raises(package.StatePackageValidationError):
        package._load_json_bytes(b"\xff", "value")
    with pytest.raises(package.StatePackageValidationError):
        package._load_jsonl_bytes(b"\xff", "value")
    monkeypatch.setattr(package, "MAX_JSONL_LINE_BYTES", 1)
    with pytest.raises(package.StatePackageLimitError):
        package._load_jsonl_bytes(b"{}\n", "value")

    with pytest.raises(package.StatePackageIntegrityError):
        package._required_member({}, "missing")
    with pytest.raises(package.StatePackageValidationError):
        package._required_string({"x": 1}, "x")
    with pytest.raises(package.StatePackageValidationError):
        package._required_uuid_string({"x": "invalid"}, "x")
    with pytest.raises(package.StatePackageValidationError):
        package._mapping_nonnegative_int({"x": True}, "x")
    with pytest.raises(package.StatePackageValidationError):
        package._validate_utc_timestamp("2026-06-15", "time")
    with pytest.raises(package.StatePackageValidationError):
        package._validate_utc_timestamp("not-a-dateZ", "time")
    assert package._parse_utc("2026-06-15T00:00:00Z").tzinfo is not None

    with pytest.raises(package.StatePackageValidationError):
        package._metadata_id_list({}, "ids")
    with pytest.raises(package.StatePackageValidationError):
        package._metadata_id_list({"ids": [1]}, "ids")
    with pytest.raises(package.StatePackageValidationError):
        package._metadata_id_list({"ids": ["invalid"]}, "ids")
    record_id = str(uuid4())
    with pytest.raises(package.StatePackageValidationError):
        package._metadata_id_list({"ids": [record_id, record_id]}, "ids")
    assert package._metadata_id_list({"ids": [record_id]}, "ids") == (record_id,)
    assert package._metadata_optional_id({}, "id") is None
    with pytest.raises(package.StatePackageValidationError):
        package._metadata_optional_id({"id": 1}, "id")
    with pytest.raises(package.StatePackageValidationError):
        package._metadata_optional_id({"id": "invalid"}, "id")
    with pytest.raises(package.StatePackageValidationError):
        package._metadata_string({}, "value")
    with pytest.raises(package.StatePackageValidationError):
        package._require_link_type({}, record_id, "memory")
    package._validate_export_record(
        _record("preference", {"preference_key": "key", "value": True, "description": None})
    )
    with pytest.raises(package.StatePackageValidationError):
        package._validate_export_record(
            _record(
                "preference",
                {"preference_key": "key", "value": True, "description": None},
                status="deleted",
            )
        )
    assert b"Doll State Package" in package._readme_bytes()


def test_state_package_cli_all_error_paths(tmp_path: Path) -> None:
    missing = tmp_path / "missing.zip"
    inspect_result = runner.invoke(app, ["state-package", "inspect", str(missing)])
    import_result = runner.invoke(
        app,
        ["state-package", "import", str(missing), "--target", str(tmp_path / "target")],
    )
    assert inspect_result.exit_code == 2
    assert import_result.exit_code == 2
    assert str(missing) not in inspect_result.output
    assert str(missing) not in import_result.output

    initialized = _initialized_workspace(tmp_path, "cli-export")
    output = tmp_path / "existing.zip"
    output.write_bytes(b"existing")
    export_result = runner.invoke(
        app,
        [
            "state-package",
            "export",
            str(output),
            "--workspace",
            str(initialized.root),
        ],
    )
    assert export_result.exit_code == 2
    assert str(output) not in export_result.output
    assert str(initialized.root) not in export_result.output
