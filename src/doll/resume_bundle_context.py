"""Explicit verified Resume Bundle context for bounded local writing."""

from __future__ import annotations

import hashlib
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from doll.instruction_origin import InstructionOriginService, InstructionSource
from doll.resume_bundle import (
    BUNDLE_ROOT,
    ResumeBundleError,
    ResumeBundleInspection,
    verify_resume_bundle,
)
from doll.secret_detection import MAX_CONFIGURED_SCAN_CHARS, scan_secrets
from doll.state import RecordSensitivity, StateError
from doll.state_repository import StateRepository
from doll.writing_context import MAX_SELECTED_CONTEXT_CHARS

_MAX_BUNDLE_FILE_BYTES = 32 * 1024 * 1024
_SNAPSHOT_SENSITIVITY: RecordSensitivity = "sensitive"
_CORE_MEMBERS = {
    "project": f"{BUNDLE_ROOT}/project.json",
    "checkpoint": f"{BUNDLE_ROOT}/checkpoint.json",
    "active_work_items": f"{BUNDLE_ROOT}/active-work-items.jsonl",
    "next_work_items": f"{BUNDLE_ROOT}/next-work-items.jsonl",
    "blocked_work_items": f"{BUNDLE_ROOT}/blocked-work-items.jsonl",
    "decisions": f"{BUNDLE_ROOT}/decisions.jsonl",
    "procedures": f"{BUNDLE_ROOT}/procedures.jsonl",
    "policies": f"{BUNDLE_ROOT}/relevant-policies.jsonl",
    "validation_requirements": f"{BUNDLE_ROOT}/validation-requirements.json",
}


class ResumeBundleWritingContextError(StateError):
    """Base class for explicit Resume Bundle writing-context failures."""


class ResumeBundleWritingContextValidationError(ResumeBundleWritingContextError):
    """Raised before runtime execution when selected bundle context is invalid."""


@dataclass(frozen=True, slots=True)
class ResumeBundleWritingContextPlan:
    """One validated immutable Resume Bundle snapshot ready for materialization."""

    content: str | None
    project_id: str | None
    state_revision: int | None
    bundle_sha256: str | None
    member_group_count: int
    character_count: int
    required_sensitivity: RecordSensitivity

    @property
    def selected(self) -> bool:
        return self.content is not None


@dataclass(frozen=True, slots=True)
class ResumeBundleWritingContextResult:
    """Content-free identifiers for materialized Resume Bundle context."""

    instruction_ids: tuple[str, ...]
    project_id: str | None
    state_revision: int | None
    bundle_sha256: str | None
    member_group_count: int
    character_count: int
    required_sensitivity: RecordSensitivity


@dataclass(frozen=True, slots=True)
class _FileIdentity:
    size_bytes: int
    modified_ns: int
    device: int
    inode: int
    sha256: str


@dataclass(slots=True)
class ResumeBundleWritingContextService:
    """Verify one caller-selected Resume Bundle and materialize data-only context."""

    repository: StateRepository

    def plan(self, bundle_path: Path | None) -> ResumeBundleWritingContextPlan:
        """Validate and snapshot one explicit bundle before creating any origin."""

        if bundle_path is None:
            return _empty_plan()
        if not isinstance(bundle_path, Path):
            raise ResumeBundleWritingContextValidationError(
                "Resume Bundle context path must be a pathlib Path"
            )

        before = _file_identity(bundle_path)
        try:
            inspection = verify_resume_bundle(bundle_path)
            content = _snapshot_content(bundle_path, inspection)
        except ResumeBundleError as exc:
            raise ResumeBundleWritingContextValidationError(
                "selected Resume Bundle is invalid"
            ) from exc
        except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
            raise ResumeBundleWritingContextValidationError(
                "selected Resume Bundle is unreadable"
            ) from exc
        after = _file_identity(bundle_path)
        if before != after:
            raise ResumeBundleWritingContextValidationError(
                "selected Resume Bundle changed during validation"
            )

        character_count = len(content)
        if character_count > MAX_SELECTED_CONTEXT_CHARS:
            raise ResumeBundleWritingContextValidationError(
                "selected Resume Bundle context exceeds the configured character limit"
            )
        scan = scan_secrets(content, max_scan_chars=MAX_CONFIGURED_SCAN_CHARS)
        if scan.detected or scan.input_truncated or scan.finding_limit_reached:
            raise ResumeBundleWritingContextValidationError(
                "selected Resume Bundle context failed secret-safe checks"
            )
        return ResumeBundleWritingContextPlan(
            content=content,
            project_id=inspection.project_id,
            state_revision=inspection.state_revision,
            bundle_sha256=before.sha256,
            member_group_count=len(_CORE_MEMBERS),
            character_count=character_count,
            required_sensitivity=_SNAPSHOT_SENSITIVITY,
        )

    def require_unused(
        self,
        *,
        operation_id: str,
        plan: ResumeBundleWritingContextPlan,
    ) -> None:
        """Fail before materialization when deterministic preparation exists."""

        if not plan.selected:
            return
        source_operation_id = _context_operation_id(operation_id, plan)
        row = self.repository.connection.execute(
            "SELECT 1 FROM records WHERE record_type = 'instruction_origin' "
            "AND json_extract(metadata_json, '$.parent_operation_id') = ? LIMIT 1",
            (source_operation_id,),
        ).fetchone()
        if row is not None:
            raise ResumeBundleWritingContextValidationError(
                "selected Resume Bundle context preparation already exists"
            )

    def materialize(
        self,
        *,
        conversation_id: str,
        operation_id: str,
        plan: ResumeBundleWritingContextPlan,
    ) -> ResumeBundleWritingContextResult:
        """Create one immutable external-content origin for a validated bundle."""

        if not plan.selected:
            return _empty_result()
        if (
            plan.content is None
            or plan.project_id is None
            or plan.state_revision is None
            or plan.bundle_sha256 is None
        ):
            raise ResumeBundleWritingContextValidationError(
                "selected Resume Bundle context plan is incomplete"
            )
        source_operation_id = _context_operation_id(operation_id, plan)
        origin = InstructionOriginService(self.repository).create(
            title="Selected Resume Bundle context",
            content=plan.content,
            source=InstructionSource(
                origin_class="external_content",
                actor_type="extractor",
                acquisition_method="extraction",
                source_identifier=(
                    f"resume_bundle:{plan.project_id}:state_revision:{plan.state_revision}:"
                    f"{plan.bundle_sha256}"
                ),
                parent_operation_id=source_operation_id,
                session_id=conversation_id,
                content_hash=_sha256_text(plan.content),
            ),
            operation_id=source_operation_id,
            sensitivity=plan.required_sensitivity,
        )
        return ResumeBundleWritingContextResult(
            instruction_ids=(origin.record_id,),
            project_id=plan.project_id,
            state_revision=plan.state_revision,
            bundle_sha256=plan.bundle_sha256,
            member_group_count=plan.member_group_count,
            character_count=plan.character_count,
            required_sensitivity=plan.required_sensitivity,
        )


def _empty_plan() -> ResumeBundleWritingContextPlan:
    return ResumeBundleWritingContextPlan(
        content=None,
        project_id=None,
        state_revision=None,
        bundle_sha256=None,
        member_group_count=0,
        character_count=0,
        required_sensitivity="public",
    )


def _empty_result() -> ResumeBundleWritingContextResult:
    return ResumeBundleWritingContextResult(
        instruction_ids=(),
        project_id=None,
        state_revision=None,
        bundle_sha256=None,
        member_group_count=0,
        character_count=0,
        required_sensitivity="public",
    )


def _file_identity(path: Path) -> _FileIdentity:
    try:
        if path.is_symlink() or not path.is_file():
            raise ResumeBundleWritingContextValidationError(
                "selected Resume Bundle must be a regular non-symlink file"
            )
        stat = path.stat()
        if stat.st_size > _MAX_BUNDLE_FILE_BYTES:
            raise ResumeBundleWritingContextValidationError(
                "selected Resume Bundle file exceeds the configured size limit"
            )
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
    except ResumeBundleWritingContextValidationError:
        raise
    except OSError as exc:
        raise ResumeBundleWritingContextValidationError(
            "selected Resume Bundle file is unavailable"
        ) from exc
    return _FileIdentity(
        size_bytes=stat.st_size,
        modified_ns=stat.st_mtime_ns,
        device=stat.st_dev,
        inode=stat.st_ino,
        sha256=f"sha256:{digest.hexdigest()}",
    )


def _snapshot_content(path: Path, inspection: ResumeBundleInspection) -> str:
    with zipfile.ZipFile(path, "r") as archive:
        project = _json_object(archive.read(_CORE_MEMBERS["project"]), "project")
        checkpoint = _optional_json_object(
            archive.read(_CORE_MEMBERS["checkpoint"]),
            "checkpoint",
        )
        active = _jsonl_objects(
            archive.read(_CORE_MEMBERS["active_work_items"]),
            "active work items",
        )
        next_items = _jsonl_objects(
            archive.read(_CORE_MEMBERS["next_work_items"]),
            "next work items",
        )
        blocked = _jsonl_objects(
            archive.read(_CORE_MEMBERS["blocked_work_items"]),
            "blocked work items",
        )
        decisions = _jsonl_objects(
            archive.read(_CORE_MEMBERS["decisions"]),
            "decisions",
        )
        procedures = _jsonl_objects(
            archive.read(_CORE_MEMBERS["procedures"]),
            "procedures",
        )
        policies = _jsonl_objects(
            archive.read(_CORE_MEMBERS["policies"]),
            "policies",
        )
        validation = _json_array_of_objects(
            archive.read(_CORE_MEMBERS["validation_requirements"]),
            "validation requirements",
        )
    payload: dict[str, object] = {
        "context_kind": "resume_bundle",
        "bundle_format_version": inspection.bundle_format_version,
        "bundle_sha256": _file_identity(path).sha256,
        "project_id": inspection.project_id,
        "generated_from_workspace_id": inspection.workspace_id,
        "generated_from_state_revision": inspection.state_revision,
        "checkpoint_id": inspection.checkpoint_id,
        "checkpoint_freshness": inspection.checkpoint_freshness,
        "included_record_counts": inspection.included_record_counts,
        "omitted_record_counts": inspection.omitted_record_counts,
        "project": project,
        "checkpoint": checkpoint,
        "active_work_items": active,
        "next_work_items": next_items,
        "blocked_work_items": blocked,
        "decisions": decisions,
        "procedures": procedures,
        "policies": policies,
        "validation_requirements": validation,
    }
    return _canonical_json(payload)


def _json_value(content: bytes, name: str) -> object:
    try:
        return json.loads(
            content,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ResumeBundleWritingContextValidationError(
            f"selected Resume Bundle {name} is invalid JSON"
        ) from exc


def _json_object(content: bytes, name: str) -> dict[str, object]:
    value = _json_value(content, name)
    if not isinstance(value, dict):
        raise ResumeBundleWritingContextValidationError(
            f"selected Resume Bundle {name} must be an object"
        )
    return cast(dict[str, object], value)


def _optional_json_object(content: bytes, name: str) -> dict[str, object] | None:
    value = _json_value(content, name)
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ResumeBundleWritingContextValidationError(
            f"selected Resume Bundle {name} must be an object or null"
        )
    return cast(dict[str, object], value)


def _jsonl_objects(content: bytes, name: str) -> list[dict[str, object]]:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ResumeBundleWritingContextValidationError(
            f"selected Resume Bundle {name} is not valid UTF-8"
        ) from exc
    result: list[dict[str, object]] = []
    for line in text.splitlines():
        if not line:
            raise ResumeBundleWritingContextValidationError(
                f"selected Resume Bundle {name} contains an empty JSONL row"
            )
        value = _json_value(line.encode("utf-8"), name)
        if not isinstance(value, dict):
            raise ResumeBundleWritingContextValidationError(
                f"selected Resume Bundle {name} row must be an object"
            )
        result.append(cast(dict[str, object], value))
    return result


def _json_array_of_objects(content: bytes, name: str) -> list[dict[str, object]]:
    value = _json_value(content, name)
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ResumeBundleWritingContextValidationError(
            f"selected Resume Bundle {name} must be an array of objects"
        )
    return cast(list[dict[str, object]], value)


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> object:
    raise ValueError(f"unsupported JSON constant: {value}")


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
        raise ResumeBundleWritingContextValidationError(
            "selected Resume Bundle context is not strict JSON"
        ) from exc


def _context_operation_id(
    operation_id: str,
    plan: ResumeBundleWritingContextPlan,
) -> str:
    if plan.project_id is None or plan.state_revision is None or plan.bundle_sha256 is None:
        raise ResumeBundleWritingContextValidationError(
            "selected Resume Bundle context plan is incomplete"
        )
    digest = hashlib.sha256(
        (f"{operation_id}\0{plan.project_id}\0{plan.state_revision}\0{plan.bundle_sha256}").encode()
    ).hexdigest()[:32]
    return f"imp067.context.resume_bundle.{digest}"


def _sha256_text(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"
