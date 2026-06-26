"""Deterministic project-scoped Resume Bundle export and verification."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import zipfile
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import cast

from doll.artifact import _artifact_from_record
from doll.paths import canonicalize_path, find_doll_repository_ancestor
from doll.procedure import ProcedureService
from doll.project_state import DecisionService, ProjectService
from doll.project_status import (
    ProjectStatusInfo,
    ProjectStatusService,
    StatusWorkItem,
)
from doll.settings import PolicyService
from doll.state import RecordEnvelope, StateError
from doll.state_package import _write_deterministic_zip
from doll.state_repository import StateRepository
from doll.work_item import WorkItemService

BUNDLE_FORMAT_VERSION = 1
BUNDLE_ROOT = "resume-bundle"
CHECKSUM_ALGORITHM = "sha256"


class ResumeBundleError(StateError):
    """Base class for Resume Bundle failures."""


class ResumeBundleValidationError(ResumeBundleError):
    """Raised when bundle selection or content is invalid."""


class ResumeBundleExportError(ResumeBundleError):
    """Raised when bundle publication fails."""


class ResumeBundleIntegrityError(ResumeBundleError):
    """Raised when a bundle inventory or checksum is invalid."""


@dataclass(frozen=True, slots=True)
class ResumeBundleInspection:
    bundle_format_version: int
    project_id: str
    workspace_id: str
    state_revision: int
    checkpoint_id: str | None
    checkpoint_freshness: str | None
    included_record_counts: dict[str, int]
    omitted_record_counts: dict[str, int]
    member_count: int
    checksum_algorithm: str


@dataclass(slots=True)
class ResumeBundleService:
    repository: StateRepository

    def export(self, project_id: str, output_path: Path) -> ResumeBundleInspection:
        if not self.repository.read_only:
            raise ResumeBundleValidationError(
                "Resume Bundle export requires a read-only repository"
            )
        output = canonicalize_path(output_path)
        if output.exists():
            raise ResumeBundleExportError("Resume Bundle output already exists")
        if find_doll_repository_ancestor(output.parent) is not None:
            raise ResumeBundleValidationError("Resume Bundle output must be outside the workspace")
        output.parent.mkdir(parents=True, exist_ok=True)
        members = self._members(project_id)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{output.name}.",
            suffix=".tmp",
            dir=output.parent,
        )
        os.close(descriptor)
        temporary = Path(temporary_name)
        try:
            temporary.unlink()
            _write_deterministic_zip(temporary, members)
            inspection = verify_resume_bundle(temporary)
            os.replace(temporary, output)
            return inspection
        except ResumeBundleError:
            temporary.unlink(missing_ok=True)
            output.unlink(missing_ok=True)
            raise
        except BaseException as exc:
            temporary.unlink(missing_ok=True)
            output.unlink(missing_ok=True)
            raise ResumeBundleExportError("Resume Bundle export failed") from exc

    def _members(self, project_id: str) -> dict[str, bytes]:
        status = ProjectStatusService(self.repository).build(project_id)
        project = ProjectService(self.repository).get(status.project_id)
        work = WorkItemService(self.repository)
        decisions = DecisionService(self.repository)
        procedures = ProcedureService(self.repository)
        policies = PolicyService(self.repository)

        active = tuple(work.get(item.work_item_id) for item in status.active_work)
        ready = tuple(work.get(item.work_item_id) for item in status.next_ready_work)
        blocked = tuple(work.get(item.work_item_id) for item in status.blocked_work)
        decision_records = tuple(
            decisions.get(item.decision_id) for item in status.governing_decisions
        )
        procedure_records = tuple(
            procedures.get(item.procedure_id) for item in status.approved_procedures
        )
        policy_records = tuple(policies.get(item.policy_id) for item in status.governing_policies)

        artifact_ids = set(project.artifact_ids)
        source_ids = set(project.memory_ids)
        for work_item in (*active, *ready, *blocked):
            artifact_ids.update(work_item.artifact_ids)
            source_ids.update(work_item.source_ids)
        for decision in decision_records:
            artifact_ids.update(decision.artifact_ids)
            source_ids.update(decision.memory_ids)
        for procedure in procedure_records:
            source_ids.update(procedure.source_ids)

        artifact_references, artifact_omissions = self._artifact_references(artifact_ids)
        source_references, source_omissions = self._source_references(source_ids)
        checkpoint_payload = (
            asdict(status.latest_checkpoint) if status.latest_checkpoint is not None else None
        )
        included_counts = {
            "project": 1,
            "checkpoint": 1 if checkpoint_payload is not None else 0,
            "active_work_items": len(active),
            "next_work_items": len(ready),
            "blocked_work_items": len(blocked),
            "decisions": len(decision_records),
            "procedures": len(procedure_records),
            "policies": len(policy_records),
            "validation_requirements": len(status.pending_required_validation),
            "artifact_references": len(artifact_references),
            "source_references": len(source_references),
        }
        omitted_counts = {
            **{
                key: status.omitted_record_counts[key]
                for key in sorted(status.omitted_record_counts)
            },
            "artifact_references": artifact_omissions,
            "source_references": source_omissions,
        }
        workspace_id = str(self.repository.workspace.record.workspace_id)
        state_revision = self.repository.status().state_revision
        manifest = {
            "bundle_format_version": BUNDLE_FORMAT_VERSION,
            "project_id": status.project_id,
            "generated_from_workspace_id": workspace_id,
            "generated_from_state_revision": state_revision,
            "generated_at_or_reproducibility_mode": "reproducible",
            "selection_options": {
                "artifact_content": "references_only",
                "checkpoint": "latest_confirmed_or_superseded",
                "include_secret_records": False,
                "work_item_states": ["in_progress", "ready", "blocked"],
            },
            "included_record_counts": included_counts,
            "omitted_record_counts": omitted_counts,
            "omission_reasons": [
                "secret records are omitted from normal Resume Bundles",
                "artifact bytes require a separate approved export",
                "external source content is not fetched",
                "unrelated project records are excluded",
            ],
            "checkpoint_id": (
                status.latest_checkpoint.checkpoint_id
                if status.latest_checkpoint is not None
                else None
            ),
            "checkpoint_freshness": (
                status.latest_checkpoint.freshness if status.latest_checkpoint is not None else None
            ),
            "checksum_algorithm": CHECKSUM_ALGORITHM,
        }
        members = {
            f"{BUNDLE_ROOT}/manifest.json": _json_bytes(manifest),
            f"{BUNDLE_ROOT}/project.json": _json_bytes(asdict(project)),
            f"{BUNDLE_ROOT}/checkpoint.json": _json_bytes(checkpoint_payload),
            f"{BUNDLE_ROOT}/active-work-items.jsonl": _jsonl_bytes(asdict(item) for item in active),
            f"{BUNDLE_ROOT}/next-work-items.jsonl": _jsonl_bytes(asdict(item) for item in ready),
            f"{BUNDLE_ROOT}/blocked-work-items.jsonl": _jsonl_bytes(
                asdict(item) for item in blocked
            ),
            f"{BUNDLE_ROOT}/decisions.jsonl": _jsonl_bytes(
                asdict(item) for item in decision_records
            ),
            f"{BUNDLE_ROOT}/procedures.jsonl": _jsonl_bytes(
                asdict(item) for item in procedure_records
            ),
            f"{BUNDLE_ROOT}/relevant-policies.jsonl": _jsonl_bytes(
                asdict(item) for item in policy_records
            ),
            f"{BUNDLE_ROOT}/validation-requirements.json": _json_bytes(
                [asdict(item) for item in status.pending_required_validation]
            ),
            f"{BUNDLE_ROOT}/artifact-references.jsonl": _jsonl_bytes(artifact_references),
            f"{BUNDLE_ROOT}/source-references.jsonl": _jsonl_bytes(source_references),
            f"{BUNDLE_ROOT}/HANDOFF.md": _handoff(status).encode("utf-8"),
        }
        checksums = {
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
        members[f"{BUNDLE_ROOT}/checksums.json"] = _json_bytes(checksums)
        return members

    def _artifact_references(
        self,
        record_ids: set[str],
    ) -> tuple[tuple[dict[str, object], ...], int]:
        result: list[dict[str, object]] = []
        omitted = 0
        for record_id in sorted(record_ids):
            try:
                record = self.repository.get_record(record_id)
            except KeyError:
                result.append(_missing_reference(record_id, "artifact"))
                continue
            if record.record_type != "artifact":
                result.append(_unavailable_reference(record, "wrong_record_type"))
                continue
            if record.sensitivity == "secret":
                omitted += 1
                continue
            artifact = _artifact_from_record(record)
            managed = PurePosixPath(artifact.managed_path)
            if managed.is_absolute() or ".." in managed.parts:
                raise ResumeBundleValidationError("artifact reference path is unsafe")
            result.append(
                {
                    "record_id": artifact.artifact_id,
                    "record_type": "artifact",
                    "title": artifact.title,
                    "availability": "requires_separate_approved_export",
                    "content_included": False,
                    "managed_path": artifact.managed_path,
                    "content_hash": artifact.content_hash,
                    "size_bytes": artifact.size_bytes,
                    "format": artifact.format,
                    "media_type": artifact.media_type,
                }
            )
        return tuple(result), omitted

    def _source_references(
        self,
        record_ids: set[str],
    ) -> tuple[tuple[dict[str, object], ...], int]:
        result: list[dict[str, object]] = []
        omitted = 0
        for record_id in sorted(record_ids):
            try:
                record = self.repository.get_record(record_id)
            except KeyError:
                result.append(_missing_reference(record_id, "source"))
                continue
            if record.sensitivity == "secret":
                omitted += 1
                continue
            result.append(
                {
                    "record_id": record.id,
                    "record_type": record.record_type,
                    "title": record.title,
                    "availability": "reference_only",
                    "content_included": False,
                    "status": record.status,
                    "revision": record.revision,
                }
            )
        return tuple(result), omitted


def verify_resume_bundle(path: Path) -> ResumeBundleInspection:
    try:
        with zipfile.ZipFile(path, "r") as archive:
            names = archive.namelist()
            if len(names) != len(set(names)):
                raise ResumeBundleIntegrityError("Resume Bundle contains duplicate members")
            required = {
                f"{BUNDLE_ROOT}/manifest.json",
                f"{BUNDLE_ROOT}/project.json",
                f"{BUNDLE_ROOT}/checkpoint.json",
                f"{BUNDLE_ROOT}/active-work-items.jsonl",
                f"{BUNDLE_ROOT}/next-work-items.jsonl",
                f"{BUNDLE_ROOT}/blocked-work-items.jsonl",
                f"{BUNDLE_ROOT}/decisions.jsonl",
                f"{BUNDLE_ROOT}/procedures.jsonl",
                f"{BUNDLE_ROOT}/relevant-policies.jsonl",
                f"{BUNDLE_ROOT}/validation-requirements.json",
                f"{BUNDLE_ROOT}/artifact-references.jsonl",
                f"{BUNDLE_ROOT}/source-references.jsonl",
                f"{BUNDLE_ROOT}/HANDOFF.md",
                f"{BUNDLE_ROOT}/checksums.json",
            }
            if set(names) != required:
                raise ResumeBundleIntegrityError("Resume Bundle inventory is invalid")
            members: dict[str, bytes] = {}
            for name in names:
                member = PurePosixPath(name)
                if member.is_absolute() or ".." in member.parts:
                    raise ResumeBundleIntegrityError("Resume Bundle member path is unsafe")
                members[name] = archive.read(name)
    except (OSError, zipfile.BadZipFile) as exc:
        raise ResumeBundleIntegrityError("Resume Bundle is unreadable") from exc

    checksum_name = f"{BUNDLE_ROOT}/checksums.json"
    checksums = _json_object(members[checksum_name], "checksums")
    if checksums.get("algorithm") != CHECKSUM_ALGORITHM:
        raise ResumeBundleIntegrityError("Resume Bundle checksum algorithm is unsupported")
    entries = checksums.get("entries")
    if not isinstance(entries, list):
        raise ResumeBundleIntegrityError("Resume Bundle checksum entries are invalid")
    expected_paths = set(members) - {checksum_name}
    actual_paths: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ResumeBundleIntegrityError("Resume Bundle checksum entry is invalid")
        member_path = entry.get("path")
        digest = entry.get("sha256")
        size = entry.get("size_bytes")
        if not isinstance(member_path, str) or member_path in actual_paths:
            raise ResumeBundleIntegrityError("Resume Bundle checksum path is invalid")
        content = members.get(member_path)
        if content is None:
            raise ResumeBundleIntegrityError("Resume Bundle checksum member is missing")
        if digest != hashlib.sha256(content).hexdigest() or size != len(content):
            raise ResumeBundleIntegrityError("Resume Bundle checksum mismatch")
        actual_paths.add(member_path)
    if actual_paths != expected_paths:
        raise ResumeBundleIntegrityError("Resume Bundle checksum inventory is incomplete")

    manifest = _json_object(members[f"{BUNDLE_ROOT}/manifest.json"], "manifest")
    if manifest.get("bundle_format_version") != BUNDLE_FORMAT_VERSION:
        raise ResumeBundleIntegrityError("Resume Bundle format version is unsupported")
    if manifest.get("checksum_algorithm") != CHECKSUM_ALGORITHM:
        raise ResumeBundleIntegrityError("Resume Bundle manifest checksum is invalid")
    handoff = members[f"{BUNDLE_ROOT}/HANDOFF.md"].decode("utf-8")
    if "generated and non-authoritative" not in handoff:
        raise ResumeBundleIntegrityError("Resume Bundle HANDOFF notice is missing")
    return ResumeBundleInspection(
        bundle_format_version=BUNDLE_FORMAT_VERSION,
        project_id=_required_string(manifest, "project_id"),
        workspace_id=_required_string(manifest, "generated_from_workspace_id"),
        state_revision=_required_int(manifest, "generated_from_state_revision"),
        checkpoint_id=_optional_string(manifest.get("checkpoint_id")),
        checkpoint_freshness=_optional_string(manifest.get("checkpoint_freshness")),
        included_record_counts=_integer_mapping(manifest, "included_record_counts"),
        omitted_record_counts=_integer_mapping(manifest, "omitted_record_counts"),
        member_count=len(members),
        checksum_algorithm=CHECKSUM_ALGORITHM,
    )


def _handoff(status: ProjectStatusInfo) -> str:
    lines = [
        "# Project Resume Handoff",
        "",
        "> This file is generated and non-authoritative. Machine-readable files in this bundle are derived from Doll authoritative records.",
        "",
        f"## Objective\n\n{status.objective or '[not recorded]'}",
        f"## Current phase\n\n{status.current_phase or '[no confirmed checkpoint]'}",
        f"## Current goal\n\n{status.current_goal or '[no confirmed checkpoint]'}",
        "## Active work",
        *_handoff_work(status.active_work),
        "## Next work",
        *_handoff_work(status.next_ready_work),
        "## Blockers",
        *_handoff_work(status.blocked_work),
        "## Important decisions",
        *([f"- {item.decision}" for item in status.governing_decisions] or ["- none"]),
        "## Applicable procedures",
        *(
            [f"- {item.title} (version {item.version})" for item in status.approved_procedures]
            or ["- none"]
        ),
        "## Governing policies and prohibitions",
        *([f"- {item.key}: {item.rule}" for item in status.governing_policies] or ["- none"]),
        "## Pending validation",
        *(
            [
                f"- {item.title}: {', '.join(item.blocking_criterion_ids)}"
                for item in status.pending_required_validation
            ]
            or ["- none"]
        ),
        "## Checkpoint freshness",
        (
            f"- {status.latest_checkpoint.freshness or 'unknown'}"
            if status.latest_checkpoint is not None
            else "- no confirmed checkpoint"
        ),
        "## Machine-readable files",
        "- Start with manifest.json and verify checksums.json.",
        "- Project, checkpoint, work, decisions, procedures, policies, validation, artifact references, and source references are separate files.",
        "- Artifact and external source content is not included in bundle v1.",
        "",
    ]
    return "\n\n".join(lines)


def _handoff_work(items: tuple[StatusWorkItem, ...]) -> list[str]:
    if not items:
        return ["- none"]
    return [f"- {item.title}" for item in items]


def _record_summary(record: RecordEnvelope) -> dict[str, object]:
    return {
        "record_id": record.id,
        "record_type": record.record_type,
        "title": record.title,
        "status": record.status,
        "revision": record.revision,
    }


def _missing_reference(record_id: str, expected_type: str) -> dict[str, object]:
    return {
        "record_id": record_id,
        "record_type": expected_type,
        "availability": "unavailable",
        "content_included": False,
    }


def _unavailable_reference(record: RecordEnvelope, reason: str) -> dict[str, object]:
    return {
        **_record_summary(record),
        "availability": "unavailable",
        "content_included": False,
        "reason": reason,
    }


def _json_bytes(value: object) -> bytes:
    return (_canonical_json(value) + "\n").encode("utf-8")


def _jsonl_bytes(values: Iterable[object]) -> bytes:
    return b"".join(_json_bytes(value) for value in values)


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
        raise ResumeBundleValidationError("Resume Bundle data is not strict JSON") from exc


def _json_object(content: bytes, name: str) -> dict[str, object]:
    try:
        value = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ResumeBundleIntegrityError(f"Resume Bundle {name} is invalid JSON") from exc
    if not isinstance(value, dict):
        raise ResumeBundleIntegrityError(f"Resume Bundle {name} must be an object")
    return cast(dict[str, object], value)


def _required_string(mapping: dict[str, object], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise ResumeBundleIntegrityError(f"Resume Bundle manifest {key} is invalid")
    return value


def _required_int(mapping: dict[str, object], key: str) -> int:
    value = mapping.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ResumeBundleIntegrityError(f"Resume Bundle manifest {key} is invalid")
    return value


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ResumeBundleIntegrityError("Resume Bundle optional manifest value is invalid")
    return value


def _integer_mapping(mapping: dict[str, object], key: str) -> dict[str, int]:
    value = mapping.get(key)
    if not isinstance(value, dict):
        raise ResumeBundleIntegrityError(f"Resume Bundle manifest {key} is invalid")
    result: dict[str, int] = {}
    for raw_key, raw_value in value.items():
        if (
            not isinstance(raw_key, str)
            or not isinstance(raw_value, int)
            or isinstance(raw_value, bool)
            or raw_value < 0
        ):
            raise ResumeBundleIntegrityError(
                f"Resume Bundle manifest {key} contains invalid counts"
            )
        result[raw_key] = raw_value
    return dict(sorted(result.items()))
