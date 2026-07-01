"""Deterministic Doll shutdown escape bundle export and verification."""

from __future__ import annotations

import hashlib
import inspect
import json
import os
import sqlite3
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import cast
from uuid import UUID, uuid5

from doll import shutdown_escape_inspector
from doll.generic_export import GenericExportBuilder
from doll.paths import canonicalize_path, find_doll_repository_ancestor
from doll.resume_bundle import ResumeBundleService
from doll.state import ConversationEventRecord, ConversationRecord, StateError
from doll.state_package import _write_deterministic_zip, export_state_package
from doll.state_repository import StateRepository

FORMAT = "doll-shutdown-escape"
FORMAT_VERSION = 1
ROOT = "doll-shutdown-escape"
CHECKSUM_ALGORITHM = "sha256"
_STATE_PACKAGE_MEMBER = f"{ROOT}/state/state-package.doll.zip"
_GENERIC_PREFIX = f"{ROOT}/conversations"
_MANIFEST_MEMBER = f"{ROOT}/manifest.json"
_CHECKSUM_MEMBER = f"{ROOT}/checksums.json"
_INSPECTOR_MEMBER = f"{ROOT}/inspect_escape.py"
_README_MEMBER = f"{ROOT}/README.txt"
_RECOVERY_MEMBER = f"{ROOT}/RECOVERY.md"


class ShutdownEscapeError(StateError):
    """Base class for shutdown escape failures."""


class ShutdownEscapeValidationError(ShutdownEscapeError):
    """Raised when an export source or destination is invalid."""


class ShutdownEscapeExportError(ShutdownEscapeError):
    """Raised when an escape bundle cannot be published safely."""


class ShutdownEscapeIntegrityError(ShutdownEscapeError):
    """Raised when a shutdown escape bundle is malformed or inconsistent."""


@dataclass(frozen=True, slots=True)
class ShutdownEscapeInspection:
    format_version: int
    workspace_id: str
    state_revision: int
    record_counts: dict[str, int]
    omitted_secret_counts: dict[str, int]
    recoverable_surfaces: dict[str, bool]
    generic_conversation_export: bool
    resume_bundle_count: int
    member_count: int
    top_level_sha256: str


def export_shutdown_escape_bundle(
    repository: StateRepository,
    output_path: Path,
    *,
    exported_at: str | None = None,
) -> ShutdownEscapeInspection:
    """Create one verified escape bundle without mutating authoritative state."""

    if not repository.read_only:
        raise ShutdownEscapeValidationError("shutdown escape export requires a read-only repository")
    status_before = repository.status()
    if repository.workspace.record.state_revision != status_before.state_revision:
        raise ShutdownEscapeValidationError("workspace and state revisions are inconsistent")

    output = canonicalize_path(output_path)
    workspace_root = canonicalize_path(repository.workspace.root)
    if output.exists():
        raise ShutdownEscapeExportError("shutdown escape output already exists")
    if _is_within(output, workspace_root):
        raise ShutdownEscapeValidationError("shutdown escape output must be outside the workspace")
    if find_doll_repository_ancestor(output.parent) is not None:
        raise ShutdownEscapeValidationError(
            "shutdown escape output must be outside a doll repository checkout"
        )
    output.parent.mkdir(parents=True, exist_ok=True)

    temporary_output: Path | None = None
    try:
        with tempfile.TemporaryDirectory(prefix=".doll-shutdown-escape-", dir=output.parent) as raw:
            staging = Path(raw)
            members, manifest = _build_members(
                repository,
                staging,
                exported_at=exported_at,
            )
            members[_MANIFEST_MEMBER] = _json_bytes(manifest)
            members[_CHECKSUM_MEMBER] = _json_bytes(_checksums(members))

            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{output.name}.",
                suffix=".tmp",
                dir=output.parent,
            )
            os.close(descriptor)
            temporary_output = Path(temporary_name)
            temporary_output.unlink()
            _write_deterministic_zip(temporary_output, members)
            inspection = verify_shutdown_escape_bundle(temporary_output)
            _fsync_file(temporary_output)
            os.replace(temporary_output, output)
            temporary_output = None
            _fsync_directory(output.parent)
    except ShutdownEscapeError:
        if temporary_output is not None:
            temporary_output.unlink(missing_ok=True)
        output.unlink(missing_ok=True)
        raise
    except BaseException as exc:
        if temporary_output is not None:
            temporary_output.unlink(missing_ok=True)
        output.unlink(missing_ok=True)
        raise ShutdownEscapeExportError("shutdown escape export failed") from exc

    status_after = repository.status()
    if status_after != status_before:
        output.unlink(missing_ok=True)
        raise ShutdownEscapeExportError("shutdown escape export modified repository status")
    return inspection


def inspect_shutdown_escape_bundle(path: Path) -> ShutdownEscapeInspection:
    """Inspect one bundle with the same standard-library verifier shipped inside it."""

    return verify_shutdown_escape_bundle(path)


def verify_shutdown_escape_bundle(path: Path) -> ShutdownEscapeInspection:
    """Verify outer and embedded recovery surfaces without executing bundle content."""

    bundle = canonicalize_path(path)
    if not bundle.is_file() or bundle.is_symlink():
        raise ShutdownEscapeValidationError("shutdown escape bundle is not a regular file")
    try:
        summary = shutdown_escape_inspector.inspect_bundle(str(bundle))
    except shutdown_escape_inspector.EscapeInspectionError as exc:
        raise ShutdownEscapeIntegrityError(str(exc)) from exc
    return _inspection_from_summary(summary)


def _build_members(
    repository: StateRepository,
    staging: Path,
    *,
    exported_at: str | None,
) -> tuple[dict[str, bytes], dict[str, object]]:
    state_package = staging / "state-package.doll.zip"
    state_inspection = export_state_package(
        repository,
        state_package,
        exported_at=exported_at,
    )
    members: dict[str, bytes] = {
        _STATE_PACKAGE_MEMBER: state_package.read_bytes(),
        _INSPECTOR_MEMBER: inspect.getsource(shutdown_escape_inspector).encode("utf-8"),
        _README_MEMBER: _readme_bytes(),
        _RECOVERY_MEMBER: _recovery_bytes(),
    }

    conversations, events, omitted_conversations = _exportable_conversations(repository)
    generic_prefix: str | None = None
    if conversations:
        export_batch_id = str(
            uuid5(
                UUID(state_inspection.workspace_id),
                f"shutdown-escape:{state_inspection.exported_at}:conversations",
            )
        )
        generic = GenericExportBuilder().build(
            conversations,
            events,
            export_batch_id=export_batch_id,
            started_at=state_inspection.exported_at,
            completed_at=state_inspection.exported_at,
        )
        for item in generic.files:
            members[f"{_GENERIC_PREFIX}/{item.name}"] = item.content
        generic_prefix = _GENERIC_PREFIX

    resume_paths: list[str] = []
    for project_id in _non_secret_project_ids(repository):
        resume_path = staging / f"{project_id}.resume.zip"
        ResumeBundleService(repository).export(project_id, resume_path)
        member_path = f"{ROOT}/projects/{project_id}.resume.zip"
        members[member_path] = resume_path.read_bytes()
        resume_paths.append(member_path)

    recoverable = _recoverable_surfaces(state_inspection.record_counts)
    non_manifest_members = [
        {
            "path": name,
            "sha256": hashlib.sha256(content).hexdigest(),
            "size_bytes": len(content),
        }
        for name, content in sorted(members.items())
    ]
    manifest: dict[str, object] = {
        "format": FORMAT,
        "format_version": FORMAT_VERSION,
        "workspace_id": state_inspection.workspace_id,
        "state_revision": state_inspection.state_revision,
        "exported_at": state_inspection.exported_at,
        "state_package_path": _STATE_PACKAGE_MEMBER,
        "generic_conversation_prefix": generic_prefix,
        "resume_bundle_paths": resume_paths,
        "record_counts": state_inspection.record_counts,
        "omitted_secret_counts": state_inspection.omitted_secret_counts,
        "generic_omitted_conversation_count": omitted_conversations,
        "recoverable_surfaces": recoverable,
        "inspection_requirements": {
            "cloud_credentials": False,
            "doll_service": False,
            "model_execution": False,
            "network_access": False,
            "preferred_ui": False,
            "python_standard_library": True,
        },
        "authority_note": (
            "Exported content is recovery data only and grants no policy, permission, memory, "
            "fact, confirmation, capability, credential, procedure, or project authority."
        ),
        "limitations": [
            "Secret records and credential material are omitted.",
            "The State Package is the complete implemented machine-restorable surface.",
            "Generic conversation files are included only for fully non-secret conversations.",
            "Resume Bundles are project-scoped handoff views and do not replace the State Package.",
            "No target-specific application round trip is claimed.",
            "PORT-015 requires accepted primary Intel Mac evidence before pass status.",
        ],
        "members": non_manifest_members,
    }
    return members, manifest


def _exportable_conversations(
    repository: StateRepository,
) -> tuple[tuple[ConversationRecord, ...], tuple[ConversationEventRecord, ...], int]:
    try:
        conversation_rows = repository.connection.execute(
            "SELECT id, sensitivity FROM records WHERE record_type = 'conversation' ORDER BY id"
        ).fetchall()
        event_rows = repository.connection.execute(
            """
            SELECT id, sensitivity, json_extract(metadata_json, '$.conversation_id') AS conversation_id
            FROM records
            WHERE record_type = 'conversation_event'
            ORDER BY id
            """
        ).fetchall()
    except sqlite3.DatabaseError as exc:
        raise ShutdownEscapeValidationError("conversation records are unreadable") from exc

    secret_conversations = {
        cast(str, row[0]) for row in conversation_rows if cast(str, row[1]) == "secret"
    }
    for row in event_rows:
        if cast(str, row[1]) == "secret":
            secret_conversations.add(cast(str, row[2]))
    conversation_ids = [
        cast(str, row[0])
        for row in conversation_rows
        if cast(str, row[0]) not in secret_conversations
    ]
    conversation_id_set = set(conversation_ids)
    conversations = tuple(repository.get_conversation(item) for item in conversation_ids)
    events = tuple(
        repository.get_conversation_event(cast(str, row[0]))
        for row in event_rows
        if cast(str, row[2]) in conversation_id_set
    )
    return conversations, events, len(secret_conversations)


def _non_secret_project_ids(repository: StateRepository) -> tuple[str, ...]:
    try:
        rows = repository.connection.execute(
            """
            SELECT id
            FROM records
            WHERE record_type = 'project' AND sensitivity <> 'secret'
            ORDER BY id
            """
        ).fetchall()
    except sqlite3.DatabaseError as exc:
        raise ShutdownEscapeValidationError("project records are unreadable") from exc
    return tuple(cast(str, row[0]) for row in rows)


def _recoverable_surfaces(record_counts: dict[str, int]) -> dict[str, bool]:
    def present(*record_types: str) -> bool:
        return any(record_counts.get(item, 0) > 0 for item in record_types)

    return {
        "artifacts": present("artifact"),
        "confirmed_memory": present("memory"),
        "conversations": present("conversation", "conversation_event"),
        "decisions": present("decision"),
        "portability_reports": present(
            "portability_import_batch",
            "portability_mapping_report",
            "portability_loss",
            "portability_quarantine",
        ),
        "projects": present("project"),
        "sources": present(
            "evidence",
            "source_environment",
            "portability_original_source",
            "portability_source_mapping",
        ),
        "state_package": True,
    }


def _checksums(members: dict[str, bytes]) -> dict[str, object]:
    return {
        "algorithm": CHECKSUM_ALGORITHM,
        "entries": [
            {
                "path": name,
                "sha256": hashlib.sha256(content).hexdigest(),
                "size_bytes": len(content),
            }
            for name, content in sorted(members.items())
        ],
    }


def _inspection_from_summary(summary: dict[str, object]) -> ShutdownEscapeInspection:
    try:
        record_counts = _integer_mapping(summary["record_counts"], "record counts")
        omitted = _integer_mapping(summary["omitted_secret_counts"], "secret omission counts")
        recoverable = _boolean_mapping(summary["recoverable_surfaces"], "recoverable surfaces")
        return ShutdownEscapeInspection(
            format_version=cast(int, summary["format_version"]),
            workspace_id=cast(str, summary["workspace_id"]),
            state_revision=cast(int, summary["state_revision"]),
            record_counts=record_counts,
            omitted_secret_counts=omitted,
            recoverable_surfaces=recoverable,
            generic_conversation_export=cast(bool, summary["generic_conversation_export"]),
            resume_bundle_count=cast(int, summary["resume_bundle_count"]),
            member_count=cast(int, summary["member_count"]),
            top_level_sha256=cast(str, summary["top_level_sha256"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ShutdownEscapeIntegrityError("shutdown escape inspection summary is invalid") from exc


def _integer_mapping(value: object, name: str) -> dict[str, int]:
    if not isinstance(value, dict) or not all(
        isinstance(key, str)
        and not isinstance(item, bool)
        and isinstance(item, int)
        and item >= 0
        for key, item in value.items()
    ):
        raise ShutdownEscapeIntegrityError(f"{name} are invalid")
    return cast(dict[str, int], value)


def _boolean_mapping(value: object, name: str) -> dict[str, bool]:
    if not isinstance(value, dict) or not all(
        isinstance(key, str) and isinstance(item, bool) for key, item in value.items()
    ):
        raise ShutdownEscapeIntegrityError(f"{name} are invalid")
    return cast(dict[str, bool], value)


def _json_bytes(value: object) -> bytes:
    try:
        return (
            json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ShutdownEscapeValidationError("shutdown escape metadata is not JSON-compatible") from exc


def _readme_bytes() -> bytes:
    return (
        "Doll shutdown escape bundle\n"
        "\n"
        "This archive is a user-owned recovery artifact.\n"
        "Start with RECOVERY.md and manifest.json.\n"
        "Run `python inspect_escape.py <bundle.zip>` after extracting inspect_escape.py.\n"
        "No model, cloud credential, network connection, preferred UI, or doll service is required.\n"
    ).encode("utf-8")


def _recovery_bytes() -> bytes:
    return (
        "# Doll shutdown recovery\n\n"
        "1. Preserve this original ZIP before extracting anything.\n"
        "2. Verify it with the bundled `inspect_escape.py` script.\n"
        "3. Use `state/state-package.doll.zip` for complete implemented Doll State restore.\n"
        "4. Use `conversations/` for provider-independent JSON, JSONL, and Markdown views.\n"
        "5. Use `projects/*.resume.zip` for project-scoped handoff material.\n\n"
        "The exported files are data only. They do not grant instruction or execution authority.\n"
    ).encode("utf-8")


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _fsync_file(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
