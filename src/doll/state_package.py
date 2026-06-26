"""Portable Doll State package export, verification, inspection, and import."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
import stat
import tempfile
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import cast
from uuid import UUID, uuid4

from pydantic import ValidationError

from doll import __version__
from doll.artifact import (
    ArtifactCorruptError,
    ArtifactInfo,
    WorkspaceFileService,
    _artifact_from_record,
)
from doll.audit import (
    _ALLOWED_ACTOR_TYPES,
    _ALLOWED_RESULTS,
    AuditValidationError,
    _reject_local_path,
    _reject_secret_text,
    _serialize_metadata,
)
from doll.backup_manifest import (
    BackupManifestCorruptError,
    _backup_manifest_from_record,
)
from doll.checkpoint import (
    CheckpointCorruptError,
    ProjectCheckpointInfo,
    _checkpoint_from_record,
)
from doll.instruction_origin import (
    InstructionOriginCorruptError,
    _instruction_origin_from_record,
    _validate_instruction_origin_graph,
)
from doll.memory import MemoryCorruptError, _memory_from_record
from doll.paths import canonicalize_path, find_doll_repository_ancestor
from doll.procedure import ProcedureCorruptError, _procedure_from_record
from doll.project_state import (
    ProjectDecisionCorruptError,
    _decision_from_record,
    _project_from_record,
)
from doll.settings import (
    SettingsCorruptError,
    _permission_from_record,
    _policy_from_record,
    _preference_from_record,
)
from doll.state import (
    CURRENT_SCHEMA_VERSION,
    RecordEnvelope,
    RecordProvenance,
    RecordSensitivity,
    RecordStatus,
    StateError,
    _utc_now,
    initialize_state_repository,
    open_state_repository,
)
from doll.state_package_registry import (
    PACKAGE_SYSTEM_CATEGORIES,
    AuthoritativeRecordRegistry,
    StatePackageRegistryError,
    get_authoritative_record_registry,
)
from doll.state_package_registry import (
    SUPPORTED_PACKAGE_FORMAT_VERSIONS as _SUPPORTED_PACKAGE_FORMAT_VERSIONS,
)
from doll.state_repository import StateRepository, _validate_record_fields
from doll.trust import (
    TruthCorruptError,
    _claim_from_record,
    _evidence_from_record,
    _inference_from_record,
    _trust_assessment_from_record,
)
from doll.work_item import WorkItemCorruptError, _work_item_from_record
from doll.workspace import (
    WORKSPACE_DIRECTORIES,
    WORKSPACE_SCHEMA_VERSION,
    WorkspaceRecord,
    _write_record_atomic,
    load_workspace,
)
from doll.workspace_files import (
    DEFAULT_MAX_ARTIFACT_BYTES,
    publish_new_workspace_file,
    validate_managed_path,
)

PACKAGE_FORMAT_VERSION = 2
SUPPORTED_PACKAGE_FORMAT_VERSIONS = _SUPPORTED_PACKAGE_FORMAT_VERSIONS
PACKAGE_ROOT = "doll-state-package"
CHECKSUM_ALGORITHM = "sha256"
ENCRYPTION_STATE = "none"

MAX_PACKAGE_MEMBERS = 2048
MAX_PACKAGE_MEMBER_BYTES = 32 * 1024 * 1024
MAX_PACKAGE_TOTAL_BYTES = 512 * 1024 * 1024
MAX_COMPRESSION_RATIO = 1000
MAX_JSONL_LINE_BYTES = 2 * 1024 * 1024

_FIXED_MEMBER_PATHS = (
    "manifest.json",
    "records/workspace.json",
    "records/audit-events.jsonl",
    "records/migration-history.jsonl",
    "README.txt",
)
_DRIVE_PATH = re.compile(r"^[A-Za-z]:")
_ALLOWED_LIFECYCLE = frozenset({"active", "archived"})


_PACKAGE_FORMAT_REQUIRED_FIELDS: dict[int, frozenset[str]] = {
    version: frozenset(
        {
            "package_format_version",
            "workspace_id",
            "exported_at",
            "source_product_version",
            "source_workspace_schema_version",
            "source_state_schema_version",
            "state_revision",
            "included_categories",
            "excluded_categories",
            "record_counts",
            "audit_event_count",
            "migration_history_count",
            "authoritative_file_count",
            "total_payload_size_bytes",
            "checksum_algorithm",
            "encryption_state",
            "omitted_secret_counts",
            "external_references",
            "compatibility_notes",
        }
    )
    for version in SUPPORTED_PACKAGE_FORMAT_VERSIONS
}


_PACKAGE_RECORD_VALIDATORS: dict[str, Callable[[RecordEnvelope], object]] = {
    "preference": _preference_from_record,
    "policy": _policy_from_record,
    "permission": _permission_from_record,
    "memory": _memory_from_record,
    "claim": _claim_from_record,
    "evidence": _evidence_from_record,
    "inference": _inference_from_record,
    "trust_assessment": _trust_assessment_from_record,
    "instruction_origin": _instruction_origin_from_record,
    "project": _project_from_record,
    "decision": _decision_from_record,
    "artifact": _artifact_from_record,
    "backup_manifest": _backup_manifest_from_record,
    "work_item": _work_item_from_record,
    "procedure": _procedure_from_record,
    "project_checkpoint": _checkpoint_from_record,
}


class StatePackageError(StateError):
    """Base class for Doll State package failures."""


class StatePackageValidationError(StatePackageError):
    """Raised when a package or export source is invalid."""


class StatePackageIntegrityError(StatePackageError):
    """Raised when package inventory, checksums, or files do not match."""


class StatePackageConflictError(StatePackageError):
    """Raised when import would modify a populated or conflicting target."""


class StatePackageUnsafePathError(StatePackageError):
    """Raised when a package member or target path is unsafe."""


class StatePackageLimitError(StatePackageError):
    """Raised when archive limits are exceeded."""


class StatePackageExportError(StatePackageError):
    """Raised when export cannot be completed and verified."""


class StatePackageImportError(StatePackageError):
    """Raised when staged import cannot be completed safely."""


def _package_record_registry(package_format_version: int) -> AuthoritativeRecordRegistry:
    try:
        return get_authoritative_record_registry(package_format_version)
    except StatePackageRegistryError as exc:
        raise StatePackageValidationError("package format version is unsupported") from exc


def _validate_registry_validators(registry: AuthoritativeRecordRegistry) -> None:
    for category in registry.categories:
        if category.validator_id not in _PACKAGE_RECORD_VALIDATORS:
            raise StatePackageValidationError(
                "registered authoritative record validator is unavailable"
            )


@dataclass(frozen=True, slots=True)
class PackageInspection:
    package_format_version: int
    workspace_id: str
    schema_version: int
    state_revision: int
    record_counts: dict[str, int]
    omitted_secret_counts: dict[str, int]
    authoritative_file_count: int
    member_count: int
    total_payload_size_bytes: int
    exported_at: str


@dataclass(frozen=True, slots=True)
class ImportConflict:
    kind: str
    identifier: str | None = None


@dataclass(frozen=True, slots=True)
class ImportPlan:
    inspection: PackageInspection
    target_empty: bool
    conflicts: tuple[ImportConflict, ...]


@dataclass(frozen=True, slots=True)
class ImportResult:
    workspace_id: str
    source_state_revision: int
    imported_state_revision: int
    imported_record_count: int
    imported_file_count: int


@dataclass(frozen=True, slots=True)
class _PackageData:
    inspection: PackageInspection
    workspace: WorkspaceRecord
    records: tuple[RecordEnvelope, ...]
    audit_events: tuple[dict[str, object], ...]
    migration_history: tuple[dict[str, object], ...]
    artifact_files: dict[str, bytes]
    manifest: dict[str, object]


def export_state_package(
    repository: StateRepository,
    output_path: Path,
    *,
    exported_at: str | None = None,
) -> PackageInspection:
    """Export currently implemented authoritative state to a verified ZIP package."""

    if not repository.read_only:
        raise StatePackageValidationError("state package export requires a read-only repository")
    source_status = repository.status()
    if repository.workspace.record.state_revision != source_status.state_revision:
        raise StatePackageValidationError("workspace and state revisions are inconsistent")

    output = canonicalize_path(output_path)
    if output.exists():
        raise StatePackageExportError("state package output already exists")
    if find_doll_repository_ancestor(output.parent) is not None:
        raise StatePackageUnsafePathError("state package output must be outside the repository")
    output.parent.mkdir(parents=True, exist_ok=True)

    timestamp = _validate_utc_timestamp(exported_at or _utc_now(), "export time")
    members = _build_export_members(repository, timestamp)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.",
        suffix=".tmp",
        dir=output.parent,
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    published = False
    try:
        temporary.unlink()
        _write_deterministic_zip(temporary, members)
        inspection = verify_state_package(temporary)
        _fsync_file(temporary)
        os.replace(temporary, output)
        published = True
        _fsync_directory(output.parent)
        return inspection
    except StatePackageError:
        if published:
            _rollback_export_publication(output)
        temporary.unlink(missing_ok=True)
        raise
    except BaseException as exc:
        if published:
            _rollback_export_publication(output)
        temporary.unlink(missing_ok=True)
        raise StatePackageExportError("state package export failed") from exc


def inspect_state_package(package_path: Path) -> PackageInspection:
    """Inspect and fully verify a package without extracting or executing content."""

    return _load_package(package_path).inspection


def verify_state_package(package_path: Path) -> PackageInspection:
    """Verify inventory, checksums, schemas, records, links, and artifact files."""

    return _load_package(package_path).inspection


def plan_state_package_import(package_path: Path, target: Path) -> ImportPlan:
    """Return an import plan and conflicts without mutating the target."""

    data = _load_package(package_path)
    target_path = canonicalize_path(target)
    conflicts = _target_conflicts(data, target_path)
    target_empty = not target_path.exists() or (
        target_path.is_dir() and not any(target_path.iterdir())
    )
    return ImportPlan(
        inspection=data.inspection,
        target_empty=target_empty,
        conflicts=conflicts,
    )


def import_state_package(package_path: Path, target: Path) -> ImportResult:
    """Import a verified package into an absent or empty target via staging."""

    data = _load_package(package_path)
    target_path = canonicalize_path(target)
    conflicts = _target_conflicts(data, target_path)
    if conflicts:
        raise StatePackageConflictError(f"state package import has {len(conflicts)} conflict(s)")
    if find_doll_repository_ancestor(target_path) is not None:
        raise StatePackageUnsafePathError("import target must be outside the repository")

    parent = target_path.parent
    parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".doll-import-", dir=parent))
    published_files = []
    try:
        bootstrap_record = data.workspace.model_copy(update={"state_revision": 0})
        _initialize_import_workspace(staging, bootstrap_record)
        with initialize_state_repository(staging) as repository:
            for record in data.records:
                if record.record_type != "artifact":
                    continue
                artifact = _artifact_from_record(record)
                content = data.artifact_files[artifact.managed_path]
                published = publish_new_workspace_file(
                    repository.workspace.root / "artifacts",
                    artifact.managed_path,
                    content,
                    max_bytes=DEFAULT_MAX_ARTIFACT_BYTES,
                )
                if (
                    published.content_hash != artifact.content_hash
                    or published.size_bytes != artifact.size_bytes
                ):
                    raise StatePackageIntegrityError(
                        "staged artifact does not match package metadata"
                    )
                published_files.append(published)
            imported_revision = _import_database_rows(repository, data)
            for published in published_files:
                published.close()
            published_files.clear()

        final_record = data.workspace.model_copy(
            update={
                "state_revision": imported_revision,
                "updated_at": datetime.now(UTC),
                "product_version_last_opened": __version__,
            }
        )
        _write_record_atomic(staging / "workspace.json", final_record)
        _validate_imported_workspace(staging, data, imported_revision)
        _publish_import_target(staging, target_path)
        return ImportResult(
            workspace_id=str(data.workspace.workspace_id),
            source_state_revision=data.inspection.state_revision,
            imported_state_revision=imported_revision,
            imported_record_count=len(data.records),
            imported_file_count=len(data.artifact_files),
        )
    except StatePackageError:
        for published in published_files:
            published.close()
        shutil.rmtree(staging, ignore_errors=True)
        raise
    except BaseException as exc:
        for published in published_files:
            published.close()
        shutil.rmtree(staging, ignore_errors=True)
        raise StatePackageImportError("state package import failed") from exc


def _build_export_members(
    repository: StateRepository,
    exported_at: str,
) -> dict[str, bytes]:
    registry = _package_record_registry(PACKAGE_FORMAT_VERSION)
    _validate_registry_validators(registry)
    records_by_type: dict[str, list[dict[str, object]]] = {
        category.record_type: [] for category in registry.categories
    }
    omitted_secret_counts: dict[str, int] = {
        category.record_type: 0 for category in registry.categories
    }
    artifact_files: dict[str, bytes] = {}

    try:
        rows = repository.connection.execute(
            "SELECT id, record_type FROM records ORDER BY id"
        ).fetchall()
    except sqlite3.DatabaseError as exc:
        raise StatePackageValidationError("authoritative records are unreadable") from exc

    for row in rows:
        record_id = cast(str, row["id"])
        record_type = cast(str, row["record_type"])
        category = registry.by_record_type.get(record_type)
        if category is None:
            raise StatePackageValidationError("unsupported authoritative record type")
        record = repository.get_record(record_id)
        if record.sensitivity == "secret":
            omitted_secret_counts[record_type] += 1
            continue
        _validate_export_record(record, category.validator_id)
        records_by_type[record_type].append(_record_payload(record))
        if record_type == "artifact":
            artifact = _artifact_from_record(record)
            verification = WorkspaceFileService(repository).verify(record.id)
            if verification.actual_hash != artifact.content_hash:
                raise StatePackageIntegrityError("artifact hash verification failed")
            content = _read_artifact_bytes(repository, artifact)
            member_path = f"files/authoritative/{artifact.managed_path}"
            if member_path in artifact_files:
                raise StatePackageValidationError("duplicate authoritative file path")
            artifact_files[member_path] = content

    workspace_payload = repository.workspace.record.model_dump(mode="json")
    audit_events = _export_audit_events(repository)
    migration_history = _export_migration_history(repository)

    members: dict[str, bytes] = {
        "records/workspace.json": _json_bytes(workspace_payload),
        "records/audit-events.jsonl": _jsonl_bytes(audit_events),
        "records/migration-history.jsonl": _jsonl_bytes(migration_history),
        "README.txt": _readme_bytes(),
    }
    for category in registry.categories:
        members[category.member_path] = _jsonl_bytes(records_by_type[category.record_type])
    members.update(artifact_files)

    payload_size = sum(len(value) for value in members.values())
    record_counts = {
        record_type: len(records_by_type[record_type])
        for record_type in sorted(registry.record_types)
    }
    manifest: dict[str, object] = {
        "package_format_version": PACKAGE_FORMAT_VERSION,
        "workspace_id": str(repository.workspace.record.workspace_id),
        "exported_at": exported_at,
        "source_product_version": repository.workspace.record.product_version_last_opened,
        "source_workspace_schema_version": repository.workspace.record.schema_version,
        "source_state_schema_version": repository.status().schema_version,
        "state_revision": repository.status().state_revision,
        "included_categories": sorted([*record_counts, *PACKAGE_SYSTEM_CATEGORIES]),
        "excluded_categories": [
            "caches",
            "reproducible_indexes",
            "model_assets",
            "runtime_assets",
            "temporary_files",
            "secrets",
        ],
        "record_counts": record_counts,
        "audit_event_count": len(audit_events),
        "migration_history_count": len(migration_history),
        "authoritative_file_count": len(artifact_files),
        "total_payload_size_bytes": payload_size,
        "checksum_algorithm": CHECKSUM_ALGORITHM,
        "encryption_state": ENCRYPTION_STATE,
        "omitted_secret_counts": omitted_secret_counts,
        "external_references": [],
        "compatibility_notes": [
            "Import supports package format versions 1 and 2 with a supported state schema.",
            "checksums.json is the inventory and is not self-hashed.",
        ],
    }
    members["manifest.json"] = _json_bytes(manifest)
    checksums = {
        "algorithm": CHECKSUM_ALGORITHM,
        "entries": [
            {
                "path": f"{PACKAGE_ROOT}/{path}",
                "sha256": hashlib.sha256(content).hexdigest(),
                "size_bytes": len(content),
            }
            for path, content in sorted(members.items())
        ],
    }
    members["checksums.json"] = _json_bytes(checksums)
    return {f"{PACKAGE_ROOT}/{path}": content for path, content in members.items()}


def _write_deterministic_zip(path: Path, members: dict[str, bytes]) -> None:
    try:
        with zipfile.ZipFile(
            path,
            mode="x",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
            allowZip64=False,
        ) as archive:
            for name, content in sorted(members.items()):
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = 3
                info.external_attr = (stat.S_IFREG | 0o600) << 16
                info.flag_bits |= 0x800
                archive.writestr(info, content, compress_type=zipfile.ZIP_DEFLATED)
    except (OSError, ValueError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise StatePackageExportError("state package ZIP could not be written") from exc


def _load_package(package_path: Path) -> _PackageData:
    expanded = package_path.expanduser()
    if expanded.is_symlink():
        raise StatePackageValidationError("state package is not a regular file")
    package = canonicalize_path(expanded)
    if not package.is_file():
        raise StatePackageValidationError("state package is not a regular file")
    try:
        with zipfile.ZipFile(package, "r") as archive:
            infos = archive.infolist()
            _validate_archive_inventory(infos)
            members = {info.filename: archive.read(info) for info in infos}
    except StatePackageError:
        raise
    except (
        OSError,
        RuntimeError,
        ValueError,
        zipfile.BadZipFile,
        zipfile.LargeZipFile,
    ) as exc:
        raise StatePackageValidationError("state package ZIP is unreadable") from exc

    checksums_path = f"{PACKAGE_ROOT}/checksums.json"
    checksums_value = _load_json_bytes(
        _required_member(members, checksums_path),
        "checksums",
    )
    checksum_entries = _validate_checksums(checksums_value)
    manifest_path = f"{PACKAGE_ROOT}/manifest.json"
    manifest = _load_json_bytes(_required_member(members, manifest_path), "manifest")
    if not isinstance(manifest, dict):
        raise StatePackageValidationError("manifest must be a JSON object")
    package_format_version = _validate_package_format_version(manifest)
    registry = _package_record_registry(package_format_version)
    _validate_registry_validators(registry)
    _validate_member_inventory_paths(set(checksum_entries), registry)
    expected_members = {checksums_path, *checksum_entries}
    if set(members) != expected_members:
        raise StatePackageIntegrityError("package member inventory does not match checksums")
    for name, expected in checksum_entries.items():
        content = members[name]
        if len(content) != expected["size_bytes"]:
            raise StatePackageIntegrityError(
                "package member size does not match checksum inventory"
            )
        if hashlib.sha256(content).hexdigest() != expected["sha256"]:
            raise StatePackageIntegrityError("package member checksum mismatch")

    workspace_path = f"{PACKAGE_ROOT}/records/workspace.json"
    workspace_payload = _load_json_bytes(
        _required_member(members, workspace_path),
        "workspace",
    )
    data = _validate_package_payloads(manifest, workspace_payload, members, registry)
    return data


def _validate_archive_inventory(infos: list[zipfile.ZipInfo]) -> None:
    if not infos or len(infos) > MAX_PACKAGE_MEMBERS:
        raise StatePackageLimitError("state package member count is unsupported")
    seen: set[str] = set()
    folded: set[str] = set()
    total = 0
    for info in infos:
        name = _validate_member_name(info.filename)
        if name in seen:
            raise StatePackageUnsafePathError("duplicate state package member")
        casefolded = name.casefold()
        if casefolded in folded:
            raise StatePackageUnsafePathError("case-folding package member collision")
        seen.add(name)
        folded.add(casefolded)

        mode = info.external_attr >> 16
        file_type = stat.S_IFMT(mode)
        if info.is_dir() or file_type == stat.S_IFLNK:
            raise StatePackageUnsafePathError("non-regular state package member")
        if file_type not in {0, stat.S_IFREG}:
            raise StatePackageUnsafePathError("unsupported state package entry type")
        if info.file_size < 0 or info.file_size > MAX_PACKAGE_MEMBER_BYTES:
            raise StatePackageLimitError("state package member is too large")
        total += info.file_size
        if total > MAX_PACKAGE_TOTAL_BYTES:
            raise StatePackageLimitError("state package total size is too large")
        if info.file_size > 0:
            if info.compress_size == 0:
                raise StatePackageLimitError("state package compression ratio is unsafe")
            if info.file_size / info.compress_size > MAX_COMPRESSION_RATIO:
                raise StatePackageLimitError("state package compression ratio is unsafe")


def _validate_member_name(value: str) -> str:
    if not value or "\\" in value or "\x00" in value:
        raise StatePackageUnsafePathError("state package member path is unsafe")
    if any(ord(character) < 32 for character in value):
        raise StatePackageUnsafePathError("state package member path has control characters")
    if value.startswith("/") or value.startswith("//") or _DRIVE_PATH.match(value):
        raise StatePackageUnsafePathError("state package member path is absolute")
    raw_parts = value.split("/")
    if any(part in {"", ".", ".."} for part in raw_parts):
        raise StatePackageUnsafePathError("state package member path is unsafe")
    path = PurePosixPath(value)
    if path.is_absolute():
        raise StatePackageUnsafePathError("state package member path is unsafe")
    if not path.parts or path.parts[0] != PACKAGE_ROOT:
        raise StatePackageUnsafePathError("state package root is invalid")
    return path.as_posix()


def _validate_checksums(value: object) -> dict[str, dict[str, object]]:
    if not isinstance(value, dict):
        raise StatePackageValidationError("checksums must be a JSON object")
    if value.get("algorithm") != CHECKSUM_ALGORITHM:
        raise StatePackageValidationError("checksum algorithm is unsupported")
    entries = value.get("entries")
    if not isinstance(entries, list):
        raise StatePackageValidationError("checksum entries must be a list")
    result: dict[str, dict[str, object]] = {}
    for raw in entries:
        if not isinstance(raw, dict):
            raise StatePackageValidationError("checksum entry must be an object")
        path = raw.get("path")
        digest = raw.get("sha256")
        size = raw.get("size_bytes")
        if not isinstance(path, str):
            raise StatePackageValidationError("checksum path is invalid")
        safe_path = _validate_member_name(path)
        if safe_path.endswith("/checksums.json"):
            raise StatePackageValidationError("checksums inventory must not self-reference")
        if safe_path in result:
            raise StatePackageValidationError("duplicate checksum entry")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise StatePackageValidationError("checksum digest is invalid")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise StatePackageValidationError("checksum byte size is invalid")
        result[safe_path] = {"sha256": digest, "size_bytes": size}
    return result


def _validate_member_inventory_paths(
    paths: set[str],
    registry: AuthoritativeRecordRegistry | None = None,
) -> None:
    selected = registry or _package_record_registry(PACKAGE_FORMAT_VERSION)
    fixed = {f"{PACKAGE_ROOT}/{path}" for path in _FIXED_MEMBER_PATHS}
    fixed.update(f"{PACKAGE_ROOT}/{path}" for path in selected.required_member_paths)
    if not fixed.issubset(paths):
        raise StatePackageIntegrityError("required package member is missing")
    optional = {f"{PACKAGE_ROOT}/{path}" for path in selected.optional_member_paths}
    artifact_prefix = f"{PACKAGE_ROOT}/files/authoritative/"
    for path in paths - fixed - optional:
        if not path.startswith(artifact_prefix) or path == artifact_prefix:
            raise StatePackageIntegrityError("package contains an unsupported member")


def _validate_package_format_version(manifest: dict[str, object]) -> int:
    version = _required_positive_int(manifest, "package_format_version")
    _package_record_registry(version)
    required_fields = _PACKAGE_FORMAT_REQUIRED_FIELDS.get(version)
    if required_fields is None:
        raise StatePackageValidationError("package format version is unsupported")
    if required_fields.difference(manifest):
        raise StatePackageValidationError(
            f"package format version {version} manifest is incomplete"
        )
    return version


def _required_unique_string_list(
    mapping: dict[str, object],
    key: str,
) -> tuple[str, ...]:
    value = mapping.get(key)
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise StatePackageValidationError(f"{key} must be a string list")
    result = tuple(value)
    if len(result) != len(set(result)):
        raise StatePackageValidationError(f"{key} contains duplicates")
    return result


def _validate_manifest_categories(
    manifest: dict[str, object],
    registry: AuthoritativeRecordRegistry,
) -> frozenset[str]:
    included = frozenset(_required_unique_string_list(manifest, "included_categories"))
    allowed = registry.record_types | PACKAGE_SYSTEM_CATEGORIES
    if not included.issubset(allowed):
        raise StatePackageValidationError(
            "manifest includes a category outside the package registry"
        )
    required = PACKAGE_SYSTEM_CATEGORIES | frozenset(
        category.record_type for category in registry.categories if category.required_member
    )
    if not required.issubset(included):
        raise StatePackageValidationError("manifest omits a required package category")
    excluded = frozenset(_required_unique_string_list(manifest, "excluded_categories"))
    if included.intersection(excluded):
        raise StatePackageValidationError("manifest included and excluded categories overlap")
    return included


def _validate_package_payloads(
    manifest_value: object,
    workspace_value: object,
    members: dict[str, bytes],
    registry: AuthoritativeRecordRegistry | None = None,
) -> _PackageData:
    if not isinstance(manifest_value, dict):
        raise StatePackageValidationError("manifest must be a JSON object")
    manifest = cast(dict[str, object], manifest_value)
    package_format_version = _validate_package_format_version(manifest)
    selected_registry = _package_record_registry(package_format_version)
    if registry is not None and registry.package_format_version != package_format_version:
        raise StatePackageIntegrityError("package registry version does not match manifest")
    registry = selected_registry
    _validate_registry_validators(registry)
    included_categories = _validate_manifest_categories(manifest, registry)
    if manifest.get("checksum_algorithm") != CHECKSUM_ALGORITHM:
        raise StatePackageValidationError("manifest checksum algorithm is unsupported")
    if manifest.get("encryption_state") != ENCRYPTION_STATE:
        raise StatePackageValidationError("encrypted state packages are unsupported")

    workspace_id = _required_uuid_string(manifest, "workspace_id")
    exported_at = _validate_utc_timestamp(
        _required_string(manifest, "exported_at"),
        "manifest export time",
    )
    schema_version = _required_nonnegative_int(manifest, "source_state_schema_version")
    if schema_version > CURRENT_SCHEMA_VERSION:
        raise StatePackageValidationError("package state schema is newer than supported")
    if schema_version != CURRENT_SCHEMA_VERSION:
        raise StatePackageValidationError("package state schema is not current")
    workspace_schema_version = _required_nonnegative_int(
        manifest,
        "source_workspace_schema_version",
    )
    if workspace_schema_version > WORKSPACE_SCHEMA_VERSION:
        raise StatePackageValidationError("workspace schema is newer than supported")
    source_product_version = _required_string(manifest, "source_product_version")
    state_revision = _required_nonnegative_int(manifest, "state_revision")

    if not isinstance(workspace_value, dict):
        raise StatePackageValidationError("workspace payload must be a JSON object")
    try:
        workspace_record = WorkspaceRecord.model_validate(workspace_value)
    except ValidationError as exc:
        raise StatePackageValidationError("workspace payload is invalid") from exc
    if workspace_record.schema_version > WORKSPACE_SCHEMA_VERSION:
        raise StatePackageValidationError("workspace schema is newer than supported")
    if workspace_record.schema_version != workspace_schema_version:
        raise StatePackageIntegrityError("workspace schema does not match manifest")
    if workspace_record.product_version_last_opened != source_product_version:
        raise StatePackageIntegrityError("workspace product version does not match manifest")
    _validate_workspace_record(workspace_record)
    if str(workspace_record.workspace_id) != workspace_id:
        raise StatePackageIntegrityError("workspace identity does not match manifest")
    if workspace_record.state_revision != state_revision:
        raise StatePackageIntegrityError("workspace revision does not match manifest")

    record_counts_value = manifest.get("record_counts")
    if not isinstance(record_counts_value, dict):
        raise StatePackageValidationError("manifest record counts are invalid")
    omitted_value = manifest.get("omitted_secret_counts")
    if not isinstance(omitted_value, dict):
        raise StatePackageValidationError("manifest omitted-secret counts are invalid")

    records: list[RecordEnvelope] = []
    records_by_id: dict[str, RecordEnvelope] = {}
    actual_counts: dict[str, int] = {}
    payloads: list[object]
    for category in registry.categories:
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
    if actual_counts != expected_counts:
        raise StatePackageIntegrityError("record counts do not match manifest")

    omitted_counts = {
        category.record_type: _mapping_record_count(
            omitted_value,
            category.record_type,
            required=category.required_member,
        )
        for category in registry.categories
    }
    _validate_active_setting_identities(records)
    _validate_cross_record_links(records_by_id)

    audit_payloads = _load_jsonl_bytes(
        _required_member(members, f"{PACKAGE_ROOT}/records/audit-events.jsonl"),
        "audit events",
    )
    audit_events = _validate_audit_events(audit_payloads)
    if len(audit_events) != _required_nonnegative_int(manifest, "audit_event_count"):
        raise StatePackageIntegrityError("audit event count does not match manifest")

    migration_payloads = _load_jsonl_bytes(
        _required_member(members, f"{PACKAGE_ROOT}/records/migration-history.jsonl"),
        "migration history",
    )
    migration_history = _validate_migration_history(migration_payloads)
    if len(migration_history) != _required_nonnegative_int(
        manifest,
        "migration_history_count",
    ):
        raise StatePackageIntegrityError("migration count does not match manifest")

    artifacts = {
        record.id: _artifact_from_record(record)
        for record in records
        if record.record_type == "artifact"
    }
    artifact_files = _validate_artifact_members(artifacts, members)
    file_count = _required_nonnegative_int(manifest, "authoritative_file_count")
    if len(artifact_files) != file_count:
        raise StatePackageIntegrityError("authoritative file count does not match manifest")

    payload_size = _required_nonnegative_int(manifest, "total_payload_size_bytes")
    actual_payload_size = sum(
        len(content)
        for name, content in members.items()
        if not name.endswith("/manifest.json") and not name.endswith("/checksums.json")
    )
    if payload_size != actual_payload_size:
        raise StatePackageIntegrityError("payload size does not match manifest")

    inspection = PackageInspection(
        package_format_version=package_format_version,
        workspace_id=workspace_id,
        schema_version=schema_version,
        state_revision=state_revision,
        record_counts=actual_counts,
        omitted_secret_counts=omitted_counts,
        authoritative_file_count=len(artifact_files),
        member_count=len(members),
        total_payload_size_bytes=payload_size,
        exported_at=exported_at,
    )
    return _PackageData(
        inspection=inspection,
        workspace=workspace_record,
        records=tuple(sorted(records, key=lambda item: item.id)),
        audit_events=audit_events,
        migration_history=migration_history,
        artifact_files=artifact_files,
        manifest=manifest,
    )


def _validate_workspace_record(record: WorkspaceRecord) -> None:
    if (
        record.created_at.tzinfo is None
        or record.created_at.utcoffset() != UTC.utcoffset(record.created_at)
        or record.updated_at.tzinfo is None
        or record.updated_at.utcoffset() != UTC.utcoffset(record.updated_at)
    ):
        raise StatePackageValidationError("workspace timestamps must be UTC")
    if record.updated_at < record.created_at:
        raise StatePackageValidationError("workspace update time precedes creation")
    try:
        for value in (
            record.instance_label,
            record.product_version_created,
            record.product_version_last_opened,
        ):
            _reject_secret_text(value)
            _reject_local_path(value)
    except AuditValidationError as exc:
        raise StatePackageValidationError("workspace metadata is not portable") from exc


def _envelope_from_payload(
    payload: object,
    expected_type: str,
    validator_id: str | None = None,
) -> RecordEnvelope:
    if not isinstance(payload, dict):
        raise StatePackageValidationError("record payload must be a JSON object")
    value = cast(dict[str, object], payload)
    record_id = _required_uuid_string(value, "id")
    record_type = _required_string(value, "record_type")
    if record_type != expected_type:
        raise StatePackageValidationError("record is stored in the wrong category")
    schema_version = _required_positive_int(value, "schema_version")
    created_at = _validate_utc_timestamp(_required_string(value, "created_at"), "created time")
    updated_at = _validate_utc_timestamp(_required_string(value, "updated_at"), "updated time")
    if _parse_utc(updated_at) < _parse_utc(created_at):
        raise StatePackageValidationError("record updated time precedes creation")
    revision = _required_positive_int(value, "revision")
    status = _required_string(value, "status")
    provenance = _required_string(value, "provenance")
    sensitivity = _required_string(value, "sensitivity")
    title = value.get("title")
    if title is not None and not isinstance(title, str):
        raise StatePackageValidationError("record title is invalid")
    metadata = value.get("metadata")
    if not isinstance(metadata, dict):
        raise StatePackageValidationError("record metadata must be an object")
    if status not in _ALLOWED_LIFECYCLE:
        raise StatePackageValidationError("record lifecycle status is unsupported")
    if sensitivity == "secret":
        raise StatePackageValidationError("unencrypted package contains a secret record")
    _validate_record_fields(
        record_type=record_type,
        schema_version=schema_version,
        status=status,
        provenance=provenance,
        sensitivity=sensitivity,
    )
    record = RecordEnvelope(
        id=record_id,
        record_type=record_type,
        schema_version=schema_version,
        created_at=created_at,
        updated_at=updated_at,
        revision=revision,
        status=cast(RecordStatus, status),
        provenance=cast(RecordProvenance, provenance),
        sensitivity=cast(RecordSensitivity, sensitivity),
        title=title,
        metadata=cast(dict[str, object], metadata),
    )
    validator = _PACKAGE_RECORD_VALIDATORS.get(validator_id or record_type)
    if validator is None:
        raise StatePackageValidationError("typed record validator is unavailable")
    try:
        validator(record)
    except (
        ArtifactCorruptError,
        BackupManifestCorruptError,
        CheckpointCorruptError,
        InstructionOriginCorruptError,
        MemoryCorruptError,
        ProcedureCorruptError,
        ProjectDecisionCorruptError,
        SettingsCorruptError,
        TruthCorruptError,
        WorkItemCorruptError,
    ) as exc:
        raise StatePackageValidationError("typed record payload is invalid") from exc
    return record


def _validate_cross_record_links(records: dict[str, RecordEnvelope]) -> None:
    try:
        _validate_instruction_origin_graph(records)
    except InstructionOriginCorruptError as exc:
        raise StatePackageValidationError("instruction-origin graph is invalid") from exc
    for record in records.values():
        metadata = record.metadata
        if record.record_type == "memory":
            for key in ("related_memory_ids", "contradicts_memory_ids"):
                for linked_id in _metadata_id_list(metadata, key):
                    _require_link_type(records, linked_id, "memory")
        elif record.record_type == "evidence":
            for key in (
                "supports_claim_ids",
                "contradicts_claim_ids",
                "contextualizes_claim_ids",
            ):
                for linked_id in _metadata_id_list(metadata, key):
                    _require_link_type(records, linked_id, "claim")
        elif record.record_type == "inference":
            for linked_id in _metadata_id_list(metadata, "claim_ids"):
                _require_link_type(records, linked_id, "claim")
            for linked_id in _metadata_id_list(metadata, "evidence_ids"):
                _require_link_type(records, linked_id, "evidence")
        elif record.record_type == "trust_assessment":
            for linked_id in _metadata_id_list(metadata, "evidence_ids"):
                _require_link_type(records, linked_id, "evidence")
            subject_type = _metadata_string(metadata, "subject_type")
            subject_id = _metadata_string(metadata, "subject_id")
            expected_subject_type = {
                "claim": "claim",
                "evidence": "evidence",
                "inference": "inference",
                "confirmed_fact": "memory",
            }.get(subject_type)
            if expected_subject_type is not None:
                _require_link_type(records, subject_id, expected_subject_type)
        elif record.record_type == "instruction_origin":
            derived_id = _metadata_optional_id(metadata, "derived_from_instruction_id")
            if derived_id is not None:
                if derived_id == record.id:
                    raise StatePackageValidationError(
                        "instruction origin cannot derive from itself"
                    )
                _require_link_type(records, derived_id, "instruction_origin")
            if _metadata_string(metadata, "origin_class") == "durable_user_policy":
                policy_id = _metadata_optional_id(metadata, "authority_reference_id")
                if policy_id is None:
                    raise StatePackageValidationError(
                        "durable user policy requires a policy reference"
                    )
                _require_link_type(records, policy_id, "policy")
        elif record.record_type == "project":
            for linked_id in _metadata_id_list(metadata, "decision_ids"):
                _require_link_type(records, linked_id, "decision")
            for linked_id in _metadata_id_list(metadata, "memory_ids"):
                _require_link_type(records, linked_id, "memory")
            for linked_id in _metadata_id_list(metadata, "artifact_ids"):
                _require_link_type(records, linked_id, "artifact")
            if record.schema_version == 2:
                for linked_id in _metadata_id_list(
                    metadata,
                    "governing_policy_ids",
                ):
                    _require_link_type(records, linked_id, "policy")
        elif record.record_type == "decision":
            project_id = _metadata_optional_id(metadata, "project_id")
            if project_id is not None:
                _require_link_type(records, project_id, "project")
            supersedes_id = _metadata_optional_id(metadata, "supersedes_id")
            if supersedes_id is not None:
                if supersedes_id == record.id:
                    raise StatePackageValidationError("decision cannot supersede itself")
                _require_link_type(records, supersedes_id, "decision")
            for linked_id in _metadata_id_list(metadata, "memory_ids"):
                _require_link_type(records, linked_id, "memory")
            for linked_id in _metadata_id_list(metadata, "artifact_ids"):
                _require_link_type(records, linked_id, "artifact")
        elif record.record_type == "work_item":
            _require_link_type(records, _metadata_string(metadata, "project_id"), "project")
            for key in ("depends_on_ids", "blocked_by_ids"):
                for linked_id in _metadata_id_list(metadata, key):
                    _require_link_type(records, linked_id, "work_item")
            for linked_id in _metadata_id_list(metadata, "source_decision_ids"):
                _require_link_type(records, linked_id, "decision")
            for linked_id in _metadata_id_list(metadata, "verification_evidence_ids"):
                _require_link_type(records, linked_id, "evidence")
            for linked_id in _metadata_id_list(metadata, "artifact_ids"):
                _require_link_type(records, linked_id, "artifact")
            for linked_id in _metadata_id_list(metadata, "source_ids"):
                linked = records.get(linked_id)
                if linked is None or linked.status != "active":
                    raise StatePackageValidationError(
                        "work-item source link is missing or inactive"
                    )
        elif record.record_type == "procedure":
            _require_link_type(
                records,
                _metadata_string(metadata, "project_id"),
                "project",
            )
            for linked_id in _metadata_id_list(
                metadata,
                "verification_evidence_ids",
            ):
                _require_link_type(records, linked_id, "evidence")
            for linked_id in _metadata_id_list(metadata, "source_ids"):
                linked = records.get(linked_id)
                if linked is None or linked.status != "active":
                    raise StatePackageValidationError(
                        "procedure source link is missing or inactive"
                    )
            for key in ("supersedes_id", "superseded_by_id"):
                optional_link_id = _metadata_optional_id(metadata, key)
                if optional_link_id is not None:
                    _require_link_type(records, optional_link_id, "procedure")
    _validate_work_item_package_graph(records)
    _validate_procedure_package_graph(records)
    _validate_checkpoint_package_graph(records)


def _validate_work_item_package_graph(records: dict[str, RecordEnvelope]) -> None:
    items = {
        record.id: _work_item_from_record(record)
        for record in records.values()
        if record.record_type == "work_item"
    }
    graph: dict[str, tuple[str, ...]] = {}
    for item in items.values():
        project = records.get(item.project_id)
        if project is None or project.record_type != "project" or project.status != "active":
            raise StatePackageValidationError("work item requires an active project")
        for linked_id in (*item.depends_on_ids, *item.blocked_by_ids):
            linked = items.get(linked_id)
            linked_record = records.get(linked_id)
            if (
                linked is None
                or linked_record is None
                or linked_record.status != "active"
                or linked.project_id != item.project_id
            ):
                raise StatePackageValidationError(
                    "work-item relation is invalid or crosses project scope"
                )
        for blocker_id in item.blocked_by_ids:
            if items[blocker_id].work_status in {"completed", "cancelled"}:
                raise StatePackageValidationError("terminal work cannot be a current blocker")
        graph[item.work_item_id] = item.depends_on_ids
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            raise StatePackageValidationError("work-item dependency graph contains a cycle")
        if node in visited:
            return
        visiting.add(node)
        for dependency in graph.get(node, ()):
            visit(dependency)
        visiting.remove(node)
        visited.add(node)

    for node in graph:
        visit(node)


def _validate_procedure_package_graph(
    records: dict[str, RecordEnvelope],
) -> None:
    procedures = {
        record.id: _procedure_from_record(record)
        for record in records.values()
        if record.record_type == "procedure"
    }
    for procedure in procedures.values():
        project = records.get(procedure.project_id)
        if project is None or project.record_type != "project" or project.status != "active":
            raise StatePackageValidationError("procedure requires an active project")
        if procedure.supersedes_id is not None:
            predecessor = procedures.get(procedure.supersedes_id)
            if (
                predecessor is None
                or predecessor.project_id != procedure.project_id
                or predecessor.version >= procedure.version
                or predecessor.procedure_status not in {"approved", "superseded"}
                or (
                    predecessor.procedure_status == "superseded"
                    and predecessor.superseded_by_id != procedure.procedure_id
                )
            ):
                raise StatePackageValidationError("procedure predecessor relation is invalid")
        if procedure.superseded_by_id is not None:
            replacement = procedures.get(procedure.superseded_by_id)
            if (
                replacement is None
                or replacement.project_id != procedure.project_id
                or replacement.version <= procedure.version
                or replacement.supersedes_id != procedure.procedure_id
            ):
                raise StatePackageValidationError("procedure replacement relation is invalid")


def _validate_checkpoint_package_graph(
    records: dict[str, RecordEnvelope],
) -> None:
    checkpoints = {
        record.id: _checkpoint_from_record(record)
        for record in records.values()
        if record.record_type == "project_checkpoint"
    }
    for checkpoint in checkpoints.values():
        basis_current = True
        for record_id, expected_revision in checkpoint.basis_record_revisions:
            linked = records.get(record_id)
            if linked is None or linked.revision != expected_revision:
                basis_current = False
                break
        if checkpoint.confirmation_state != "proposed" and not basis_current:
            continue
        _validate_current_checkpoint_package_links(records, checkpoint)


def _validate_current_checkpoint_package_links(
    records: dict[str, RecordEnvelope],
    checkpoint: ProjectCheckpointInfo,
) -> None:
    project = records.get(checkpoint.project_id)
    if project is None or project.record_type != "project" or project.status != "active":
        raise StatePackageValidationError("checkpoint requires an active project")
    expected_groups = (
        (checkpoint.active_work_item_ids, {"in_progress"}, None),
        (checkpoint.next_work_item_ids, {"ready"}, None),
        (checkpoint.blocked_work_item_ids, {"blocked"}, None),
        (checkpoint.completed_milestone_ids, {"completed"}, "milestone"),
    )
    for record_ids, statuses, expected_kind in expected_groups:
        for record_id in record_ids:
            record = records.get(record_id)
            if record is None or record.record_type != "work_item" or record.status != "active":
                raise StatePackageValidationError("checkpoint work-item link is invalid")
            item = _work_item_from_record(record)
            if item.project_id != checkpoint.project_id or item.work_status not in statuses:
                raise StatePackageValidationError("checkpoint work-item role is invalid")
            if expected_kind is not None and item.kind != expected_kind:
                raise StatePackageValidationError("checkpoint milestone link is invalid")
    for record_id in (
        *checkpoint.required_validation_ids,
        *checkpoint.basis_record_ids,
    ):
        record = records.get(record_id)
        if record is None or record.status != "active":
            raise StatePackageValidationError("checkpoint basis link is invalid")


def _validate_active_setting_identities(records: list[RecordEnvelope]) -> None:
    identities: set[tuple[str, str]] = set()
    for record in records:
        if record.status != "active":
            continue
        if record.record_type == "preference":
            identity = ("preference", _metadata_string(record.metadata, "preference_key"))
        elif record.record_type == "policy":
            identity = ("policy", _metadata_string(record.metadata, "policy_key"))
        elif record.record_type == "permission":
            identity = ("permission", _metadata_string(record.metadata, "permission_identity"))
        else:
            continue
        if identity in identities:
            raise StatePackageValidationError("duplicate active setting identity")
        identities.add(identity)


def _validate_artifact_members(
    artifacts: dict[str, ArtifactInfo],
    members: dict[str, bytes],
) -> dict[str, bytes]:
    expected_paths: dict[str, ArtifactInfo] = {}
    for artifact in artifacts.values():
        path = validate_managed_path(artifact.managed_path).as_posix()
        if path in expected_paths:
            raise StatePackageValidationError("duplicate artifact managed path")
        expected_paths[path] = artifact
    actual_members = {
        name.removeprefix(f"{PACKAGE_ROOT}/files/authoritative/"): content
        for name, content in members.items()
        if name.startswith(f"{PACKAGE_ROOT}/files/authoritative/")
    }
    if set(actual_members) != set(expected_paths):
        raise StatePackageIntegrityError("artifact file inventory does not match records")
    for path, artifact in expected_paths.items():
        content = actual_members[path]
        if len(content) != artifact.size_bytes:
            raise StatePackageIntegrityError("artifact file size does not match record")
        digest = f"sha256:{hashlib.sha256(content).hexdigest()}"
        if digest != artifact.content_hash:
            raise StatePackageIntegrityError("artifact file hash does not match record")
    return actual_members


def _validate_audit_events(payloads: list[object]) -> tuple[dict[str, object], ...]:
    result: list[dict[str, object]] = []
    sequences: set[int] = set()
    event_ids: set[str] = set()
    previous = 0
    for payload in payloads:
        if not isinstance(payload, dict):
            raise StatePackageValidationError("audit event must be an object")
        event = cast(dict[str, object], payload)
        sequence = _required_positive_int(event, "sequence")
        if sequence in sequences or sequence <= previous:
            raise StatePackageValidationError("audit event sequence is invalid")
        previous = sequence
        sequences.add(sequence)
        event_id = _required_uuid_string(event, "event_id")
        if event_id in event_ids:
            raise StatePackageValidationError("duplicate audit event ID")
        event_ids.add(event_id)
        _required_string(event, "operation_id")
        _validate_utc_timestamp(_required_string(event, "occurred_at"), "audit time")
        actor_type = _required_string(event, "actor_type")
        if actor_type not in _ALLOWED_ACTOR_TYPES:
            raise StatePackageValidationError("audit actor type is invalid")
        action = _required_string(event, "action")
        if not action:
            raise StatePackageValidationError("audit action is invalid")
        audit_result = _required_string(event, "result")
        if audit_result not in _ALLOWED_RESULTS:
            raise StatePackageValidationError("audit result is invalid")
        metadata = event.get("metadata")
        if not isinstance(metadata, dict):
            raise StatePackageValidationError("audit metadata must be an object")
        for key in ("actor_id", "target_type", "target_id", "summary", "error_class"):
            value = event.get(key)
            if value is not None and not isinstance(value, str):
                raise StatePackageValidationError("audit optional field is invalid")
        try:
            for value in event.values():
                if isinstance(value, str):
                    _reject_secret_text(value)
                    _reject_local_path(value)
            _serialize_metadata(cast(dict[str, object], metadata))
            _reject_local_paths_in_json(metadata)
        except AuditValidationError as exc:
            raise StatePackageValidationError("audit event is not portable") from exc
        result.append(event)
    return tuple(result)


def _reject_local_paths_in_json(value: object) -> None:
    if isinstance(value, dict):
        for nested in value.values():
            _reject_local_paths_in_json(nested)
        return
    if isinstance(value, list):
        for nested in value:
            _reject_local_paths_in_json(nested)
        return
    if isinstance(value, str):
        _reject_local_path(value)


def _validate_migration_history(payloads: list[object]) -> tuple[dict[str, object], ...]:
    result: list[dict[str, object]] = []
    run_ids: set[str] = set()
    for payload in payloads:
        if not isinstance(payload, dict):
            raise StatePackageValidationError("migration record must be an object")
        migration = cast(dict[str, object], payload)
        run_id = _required_uuid_string(migration, "migration_run_id")
        if run_id in run_ids:
            raise StatePackageValidationError("duplicate migration run ID")
        run_ids.add(run_id)
        _required_string(migration, "migration_id")
        _required_nonnegative_int(migration, "from_schema_version")
        _required_nonnegative_int(migration, "to_schema_version")
        _validate_utc_timestamp(_required_string(migration, "started_at"), "migration start")
        completed = migration.get("completed_at")
        if completed is not None:
            if not isinstance(completed, str):
                raise StatePackageValidationError("migration completion time is invalid")
            _validate_utc_timestamp(completed, "migration completion")
        status = _required_string(migration, "status")
        if status not in {"running", "completed", "failed"}:
            raise StatePackageValidationError("migration status is invalid")
        error_class = migration.get("error_class")
        if error_class is not None and not isinstance(error_class, str):
            raise StatePackageValidationError("migration error class is invalid")
        result.append(migration)
    return tuple(result)


def _target_conflicts(data: _PackageData, target: Path) -> tuple[ImportConflict, ...]:
    if not target.exists():
        return ()
    if not target.is_dir():
        return (ImportConflict("target_not_directory"),)
    if not any(target.iterdir()):
        return ()
    conflicts: list[ImportConflict] = []
    try:
        workspace = load_workspace(target)
    except BaseException:
        return (ImportConflict("target_not_empty"),)
    if str(workspace.record.workspace_id) != data.inspection.workspace_id:
        return (ImportConflict("workspace_id_conflict"),)
    try:
        with open_state_repository(target, read_only=True) as repository:
            local_rows = repository.connection.execute(
                "SELECT id FROM records ORDER BY id"
            ).fetchall()
            local = {
                cast(str, row["id"]): repository.get_record(cast(str, row["id"]))
                for row in local_rows
            }
    except BaseException:
        return (ImportConflict("target_state_unreadable"),)
    for incoming in data.records:
        existing = local.get(incoming.id)
        if existing is None:
            continue
        if existing.revision > incoming.revision:
            conflicts.append(ImportConflict("newer_target_revision", incoming.id))
        elif existing.revision == incoming.revision:
            if _record_payload(existing) != _record_payload(incoming):
                conflicts.append(ImportConflict("same_revision_different_content", incoming.id))
            else:
                conflicts.append(ImportConflict("existing_record", incoming.id))
        else:
            conflicts.append(ImportConflict("older_target_record", incoming.id))
    for record in data.records:
        if record.record_type != "artifact":
            continue
        artifact = _artifact_from_record(record)
        if (target / "artifacts" / artifact.managed_path).exists():
            conflicts.append(ImportConflict("artifact_path_collision", record.id))
    if not conflicts:
        conflicts.append(ImportConflict("target_not_empty"))
    return tuple(conflicts)


def _initialize_import_workspace(root: Path, record: WorkspaceRecord) -> None:
    if any(root.iterdir()):
        raise StatePackageImportError("import staging directory is not empty")
    if os.name != "nt":
        root.chmod(0o700)
    for directory_name in WORKSPACE_DIRECTORIES:
        (root / directory_name).mkdir(exist_ok=False)
    _write_record_atomic(root / "workspace.json", record)


def _import_database_rows(repository: StateRepository, data: _PackageData) -> int:
    connection = repository.connection
    imported_revision = data.inspection.state_revision + 1
    now = _utc_now()
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("DELETE FROM migration_history")
        for migration in data.migration_history:
            connection.execute(
                """
                INSERT INTO migration_history (
                    migration_run_id, migration_id, from_schema_version,
                    to_schema_version, started_at, completed_at, status, error_class
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    migration["migration_run_id"],
                    migration["migration_id"],
                    migration["from_schema_version"],
                    migration["to_schema_version"],
                    migration["started_at"],
                    migration.get("completed_at"),
                    migration["status"],
                    migration.get("error_class"),
                ),
            )
        for record in data.records:
            connection.execute(
                """
                INSERT INTO records (
                    id, record_type, schema_version, created_at, updated_at,
                    revision, status, provenance, sensitivity, title, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    record.record_type,
                    record.schema_version,
                    record.created_at,
                    record.updated_at,
                    record.revision,
                    record.status,
                    record.provenance,
                    record.sensitivity,
                    record.title,
                    _canonical_json(record.metadata),
                ),
            )
        for event in data.audit_events:
            connection.execute(
                """
                INSERT INTO audit_events (
                    sequence, event_id, operation_id, occurred_at, actor_type,
                    actor_id, action, target_type, target_id, result,
                    summary, error_class, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event["sequence"],
                    event["event_id"],
                    event["operation_id"],
                    event["occurred_at"],
                    event["actor_type"],
                    event.get("actor_id"),
                    event["action"],
                    event.get("target_type"),
                    event.get("target_id"),
                    event["result"],
                    event.get("summary"),
                    event.get("error_class"),
                    _canonical_json(cast(dict[str, object], event["metadata"])),
                ),
            )
        next_sequence = (
            max((cast(int, event["sequence"]) for event in data.audit_events), default=0) + 1
        )
        connection.execute(
            """
            INSERT INTO audit_events (
                sequence, event_id, operation_id, occurred_at, actor_type,
                action, target_type, target_id, result, summary, metadata_json
            ) VALUES (?, ?, ?, ?, 'system', 'state-package.import',
                      'workspace', ?, 'success', ?, ?)
            """,
            (
                next_sequence,
                str(uuid4()),
                str(uuid4()),
                now,
                data.inspection.workspace_id,
                "Imported verified Doll State package",
                _canonical_json(
                    {
                        "package_format_version": data.inspection.package_format_version,
                        "source_state_revision": data.inspection.state_revision,
                        "record_count": len(data.records),
                        "authoritative_file_count": len(data.artifact_files),
                    }
                ),
            ),
        )
        connection.execute(
            """
            UPDATE schema_metadata
            SET workspace_id = ?, schema_version = ?, state_revision = ?,
                created_at = ?, updated_at = ?
            WHERE singleton = 1
            """,
            (
                data.inspection.workspace_id,
                data.inspection.schema_version,
                imported_revision,
                data.workspace.created_at.isoformat().replace("+00:00", "Z"),
                now,
            ),
        )
        connection.execute("COMMIT")
    except sqlite3.DatabaseError as exc:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise StatePackageImportError("package rows could not be imported") from exc
    except BaseException:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise
    return imported_revision


def _validate_imported_workspace(
    staging: Path,
    data: _PackageData,
    imported_revision: int,
) -> None:
    try:
        with open_state_repository(staging, read_only=True) as repository:
            status = repository.status()
            if status.workspace_id != data.inspection.workspace_id:
                raise StatePackageIntegrityError("imported workspace identity changed")
            if status.state_revision != imported_revision:
                raise StatePackageIntegrityError("imported state revision is invalid")
            if status.record_count != len(data.records):
                raise StatePackageIntegrityError("imported record count is invalid")
            for record in data.records:
                imported = repository.get_record(record.id)
                if _record_payload(imported) != _record_payload(record):
                    raise StatePackageIntegrityError("imported record differs from package")
                if record.record_type == "artifact":
                    WorkspaceFileService(repository).verify(record.id)
    except StatePackageError:
        raise
    except BaseException as exc:
        raise StatePackageImportError("imported workspace validation failed") from exc


def _publish_import_target(staging: Path, target: Path) -> None:
    backup: Path | None = None
    published = False
    try:
        if target.exists():
            if not target.is_dir() or any(target.iterdir()):
                raise StatePackageConflictError("import target changed before publication")
            backup = target.with_name(f".{target.name}.empty-{uuid4().hex}")
            os.replace(target, backup)
        os.replace(staging, target)
        published = True
        _fsync_directory(target.parent)
        if backup is not None:
            backup.rmdir()
            backup = None
    except StatePackageError:
        _rollback_import_publication(target, backup, published)
        raise
    except BaseException as exc:
        _rollback_import_publication(target, backup, published)
        raise StatePackageImportError("import target could not be published") from exc


def _rollback_import_publication(
    target: Path,
    backup: Path | None,
    published: bool,
) -> None:
    try:
        if published and target.exists():
            shutil.rmtree(target)
        if backup is not None and backup.exists():
            os.replace(backup, target)
    except BaseException as exc:
        raise StatePackageImportError("import publication rollback failed") from exc


def _validate_export_record(
    record: RecordEnvelope,
    validator_id: str | None = None,
) -> None:
    if record.status not in _ALLOWED_LIFECYCLE:
        raise StatePackageValidationError("unsupported record lifecycle for export")
    _envelope_from_payload(
        _record_payload(record),
        record.record_type,
        validator_id or record.record_type,
    )


def _read_artifact_bytes(
    repository: StateRepository,
    artifact: ArtifactInfo,
) -> bytes:
    safe_path = validate_managed_path(artifact.managed_path)
    path = repository.workspace.root / "artifacts" / safe_path
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise StatePackageIntegrityError("managed artifact could not be read") from exc
    if len(content) > DEFAULT_MAX_ARTIFACT_BYTES:
        raise StatePackageLimitError("managed artifact exceeds export size limit")
    if len(content) != artifact.size_bytes:
        raise StatePackageIntegrityError("managed artifact size changed during export")
    digest = f"sha256:{hashlib.sha256(content).hexdigest()}"
    if digest != artifact.content_hash:
        raise StatePackageIntegrityError("managed artifact hash changed during export")
    return content


def _export_audit_events(repository: StateRepository) -> list[dict[str, object]]:
    try:
        rows = repository.connection.execute(
            """
            SELECT sequence, event_id, operation_id, occurred_at, actor_type,
                   actor_id, action, target_type, target_id, result,
                   summary, error_class, metadata_json
            FROM audit_events
            ORDER BY sequence
            """
        ).fetchall()
    except sqlite3.DatabaseError as exc:
        raise StatePackageValidationError("audit history is unreadable") from exc
    result = []
    for row in rows:
        metadata = _load_json_text(cast(str, row["metadata_json"]), "audit metadata")
        if not isinstance(metadata, dict):
            raise StatePackageValidationError("audit metadata must be an object")
        result.append(
            {
                "sequence": cast(int, row["sequence"]),
                "event_id": cast(str, row["event_id"]),
                "operation_id": cast(str, row["operation_id"]),
                "occurred_at": cast(str, row["occurred_at"]),
                "actor_type": cast(str, row["actor_type"]),
                "actor_id": cast(str | None, row["actor_id"]),
                "action": cast(str, row["action"]),
                "target_type": cast(str | None, row["target_type"]),
                "target_id": cast(str | None, row["target_id"]),
                "result": cast(str, row["result"]),
                "summary": cast(str | None, row["summary"]),
                "error_class": cast(str | None, row["error_class"]),
                "metadata": metadata,
            }
        )
    _validate_audit_events(cast(list[object], result))
    return result


def _export_migration_history(repository: StateRepository) -> list[dict[str, object]]:
    try:
        rows = repository.connection.execute(
            """
            SELECT migration_run_id, migration_id, from_schema_version,
                   to_schema_version, started_at, completed_at, status, error_class
            FROM migration_history
            ORDER BY started_at, migration_run_id
            """
        ).fetchall()
    except sqlite3.DatabaseError as exc:
        raise StatePackageValidationError("migration history is unreadable") from exc
    result: list[dict[str, object]] = [
        {
            "migration_run_id": cast(str, row["migration_run_id"]),
            "migration_id": cast(str, row["migration_id"]),
            "from_schema_version": cast(int, row["from_schema_version"]),
            "to_schema_version": cast(int, row["to_schema_version"]),
            "started_at": cast(str, row["started_at"]),
            "completed_at": cast(str | None, row["completed_at"]),
            "status": cast(str, row["status"]),
            "error_class": cast(str | None, row["error_class"]),
        }
        for row in rows
    ]
    _validate_migration_history(cast(list[object], result))
    return result


def _record_payload(record: RecordEnvelope) -> dict[str, object]:
    return {
        "id": record.id,
        "record_type": record.record_type,
        "schema_version": record.schema_version,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
        "revision": record.revision,
        "status": record.status,
        "provenance": record.provenance,
        "sensitivity": record.sensitivity,
        "title": record.title,
        "metadata": record.metadata,
    }


def _json_bytes(value: object) -> bytes:
    return (_canonical_json(value) + "\n").encode("utf-8")


def _jsonl_bytes(values: list[dict[str, object]]) -> bytes:
    return "".join(_canonical_json(value) + "\n" for value in values).encode("utf-8")


def _canonical_json(value: object) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise StatePackageValidationError("package value is not strict JSON") from exc


def _load_json_text(value: str, name: str) -> object:
    try:
        return json.loads(value, parse_constant=_reject_nonstandard_json)
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise StatePackageValidationError(f"{name} is not valid strict JSON") from exc


def _load_json_bytes(value: bytes, name: str) -> object:
    try:
        text = value.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise StatePackageValidationError(f"{name} is not UTF-8") from exc
    return _load_json_text(text, name)


def _load_jsonl_bytes(value: bytes, name: str) -> list[object]:
    try:
        text = value.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise StatePackageValidationError(f"{name} is not UTF-8") from exc
    if text and not text.endswith("\n"):
        raise StatePackageValidationError(f"{name} must end with LF")
    result = []
    for line in text.splitlines():
        if not line:
            raise StatePackageValidationError(f"{name} contains a blank JSONL line")
        if len(line.encode("utf-8")) > MAX_JSONL_LINE_BYTES:
            raise StatePackageLimitError(f"{name} contains an oversized JSONL line")
        result.append(_load_json_text(line, name))
    return result


def _reject_nonstandard_json(value: str) -> object:
    raise ValueError(f"non-standard JSON constant: {value}")


def _required_member(members: dict[str, bytes], name: str) -> bytes:
    try:
        return members[name]
    except KeyError as exc:
        raise StatePackageIntegrityError("required package member is missing") from exc


def _required_string(mapping: dict[str, object], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise StatePackageValidationError(f"{key} is missing or invalid")
    return value


def _required_uuid_string(mapping: dict[str, object], key: str) -> str:
    value = _required_string(mapping, key)
    try:
        return str(UUID(value))
    except ValueError as exc:
        raise StatePackageValidationError(f"{key} is not a valid UUID") from exc


def _required_nonnegative_int(mapping: dict[str, object], key: str) -> int:
    value = mapping.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise StatePackageValidationError(f"{key} is not a non-negative integer")
    return value


def _required_positive_int(mapping: dict[str, object], key: str) -> int:
    value = _required_nonnegative_int(mapping, key)
    if value < 1:
        raise StatePackageValidationError(f"{key} is not positive")
    return value


def _mapping_nonnegative_int(mapping: dict[object, object], key: str) -> int:
    value = mapping.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise StatePackageValidationError(f"{key} count is invalid")
    return value


def _mapping_record_count(
    mapping: dict[object, object],
    key: str,
    *,
    required: bool = True,
) -> int:
    if not required and key not in mapping:
        return 0
    return _mapping_nonnegative_int(mapping, key)


def _validate_utc_timestamp(value: str, name: str) -> str:
    if not value.endswith("Z"):
        raise StatePackageValidationError(f"{name} must be UTC")
    try:
        parsed = _parse_utc(value)
    except ValueError as exc:
        raise StatePackageValidationError(f"{name} is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise StatePackageValidationError(f"{name} must be UTC")
    return value


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value[:-1] + "+00:00")


def _metadata_id_list(metadata: dict[str, object], key: str) -> tuple[str, ...]:
    value = metadata.get(key)
    if not isinstance(value, list):
        raise StatePackageValidationError(f"{key} must be a list")
    result = []
    for raw in value:
        if not isinstance(raw, str):
            raise StatePackageValidationError(f"{key} must contain IDs")
        try:
            record_id = str(UUID(raw))
        except ValueError as exc:
            raise StatePackageValidationError(f"{key} contains an invalid ID") from exc
        if record_id in result:
            raise StatePackageValidationError(f"{key} contains duplicate IDs")
        result.append(record_id)
    return tuple(result)


def _metadata_optional_id(metadata: dict[str, object], key: str) -> str | None:
    value = metadata.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise StatePackageValidationError(f"{key} is invalid")
    try:
        return str(UUID(value))
    except ValueError as exc:
        raise StatePackageValidationError(f"{key} is invalid") from exc


def _metadata_string(metadata: dict[str, object], key: str) -> str:
    value = metadata.get(key)
    if not isinstance(value, str) or not value:
        raise StatePackageValidationError(f"{key} is invalid")
    return value


def _require_link_type(
    records: dict[str, RecordEnvelope],
    record_id: str,
    expected_type: str,
) -> None:
    record = records.get(record_id)
    if record is None or record.record_type != expected_type:
        raise StatePackageValidationError("typed record link is missing or has wrong type")


def _readme_bytes() -> bytes:
    return (
        "Doll State Package\n"
        f"Format version: {PACKAGE_FORMAT_VERSION}\n"
        "This archive contains data only. Do not execute package content.\n"
        "Verify checksums.json before import.\n"
        "Secret records are omitted from unencrypted packages.\n"
    ).encode()


def _rollback_export_publication(output: Path) -> None:
    try:
        output.unlink(missing_ok=True)
    except OSError as exc:
        raise StatePackageExportError("state package publication rollback failed") from exc


def _fsync_file(path: Path) -> None:
    if os.name == "nt":
        return
    try:
        with path.open("rb") as handle:
            os.fsync(handle.fileno())
    except OSError as exc:
        raise StatePackageExportError("state package could not be synchronized") from exc


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    try:
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError as exc:
        raise StatePackageError("directory publication could not be synchronized") from exc
