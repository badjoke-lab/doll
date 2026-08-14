"""Append-oriented semantic project experience for Doll continuity."""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, cast
from uuid import UUID

from doll.project_state import ProjectDecisionCorruptError, _project_from_record
from doll.state import (
    RecordEnvelope,
    RecordProvenance,
    RecordSensitivity,
    RecordStatus,
    StateCorruptError,
    StateError,
)
from doll.state_repository import StateRepository
from doll.trust import TruthCorruptError, _evidence_from_record
from doll.work_item import WorkItemCorruptError, _work_item_from_record

ProjectExperienceEventKind = Literal[
    "observation",
    "hypothesis",
    "attempt",
    "outcome",
    "resolution",
    "lesson",
]
ProjectExperienceOutcome = Literal["worked", "failed", "partial", "unknown"]
ProjectExperienceAssertionState = Literal[
    "user_recorded",
    "user_confirmed",
    "deterministic_system",
    "imported_external",
    "model_proposed",
]
ProjectExperienceActor = Literal["user", "system", "importer", "model"]

PROJECT_EXPERIENCE_SCHEMA_VERSION = 1
_ALLOWED_EVENT_KINDS = frozenset(
    {"observation", "hypothesis", "attempt", "outcome", "resolution", "lesson"}
)
_ALLOWED_OUTCOMES = frozenset({"worked", "failed", "partial", "unknown"})
_ALLOWED_ASSERTION_STATES = frozenset(
    {
        "user_recorded",
        "user_confirmed",
        "deterministic_system",
        "imported_external",
        "model_proposed",
    }
)
_ASSERTION_ACTORS: dict[str, str] = {
    "user_recorded": "user",
    "user_confirmed": "user",
    "deterministic_system": "system",
    "imported_external": "importer",
    "model_proposed": "model",
}
_ASSERTION_PROVENANCE: dict[str, RecordProvenance] = {
    "user_recorded": "user-created",
    "user_confirmed": "user-confirmed",
    "deterministic_system": "system-generated",
    "imported_external": "imported",
    "model_proposed": "model-proposed",
}
_POSIX_PATH_PATTERN = re.compile(r"(?<![:/\w])/(?:[^/\s]+/)*[^/\s]+")
_WINDOWS_PATH_PATTERN = re.compile(r"(?i)\b[A-Z]:[\\/]")

MAX_SUMMARY_LENGTH = 6000
MAX_LINKS = 100
MAX_LIST_LIMIT = 500


class ProjectExperienceError(StateError):
    """Base class for ProjectExperienceRecord failures."""


class ProjectExperienceValidationError(ProjectExperienceError):
    """Raised when requested project-experience values are invalid."""


class ProjectExperienceCorruptError(ProjectExperienceError):
    """Raised when persisted project experience is malformed."""


@dataclass(frozen=True, slots=True)
class ProjectExperienceInfo:
    experience_id: str
    project_id: str
    work_item_id: str | None
    event_kind: ProjectExperienceEventKind
    summary: str
    outcome: ProjectExperienceOutcome | None
    occurred_at: str
    assertion_state: ProjectExperienceAssertionState
    related_record_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    supersedes_id: str | None
    revision: int
    lifecycle_status: RecordStatus
    provenance: RecordProvenance
    sensitivity: RecordSensitivity
    created_at: str
    updated_at: str


@dataclass(slots=True)
class ProjectExperienceService:
    repository: StateRepository

    def record(
        self,
        *,
        project_id: str,
        event_kind: ProjectExperienceEventKind,
        summary: str,
        occurred_at: str,
        assertion_state: ProjectExperienceAssertionState,
        actor_type: ProjectExperienceActor,
        outcome: ProjectExperienceOutcome | None = None,
        work_item_id: str | None = None,
        related_record_ids: Sequence[str] = (),
        evidence_ids: Sequence[str] = (),
        source_ids: Sequence[str] = (),
        supersedes_id: str | None = None,
        sensitivity: RecordSensitivity = "personal",
    ) -> ProjectExperienceInfo:
        """Append one semantic experience event without mutating current project state."""

        safe_assertion = _assertion_state(assertion_state)
        _require_assertion_actor(safe_assertion, actor_type)
        metadata = _validated_values(
            self.repository,
            project_id=project_id,
            work_item_id=work_item_id,
            event_kind=event_kind,
            summary=summary,
            outcome=outcome,
            occurred_at=occurred_at,
            assertion_state=safe_assertion,
            related_record_ids=related_record_ids,
            evidence_ids=evidence_ids,
            source_ids=source_ids,
            supersedes_id=supersedes_id,
            sensitivity=sensitivity,
        )
        record = self.repository.create_record(
            record_type="project_experience",
            schema_version=PROJECT_EXPERIENCE_SCHEMA_VERSION,
            status="active",
            provenance=_ASSERTION_PROVENANCE[safe_assertion],
            sensitivity=sensitivity,
            title=_title_for_summary(cast(str, metadata["summary"])),
            metadata=metadata,
        )
        return _project_experience_from_record(record, self.repository)

    def correct(
        self,
        experience_id: str,
        *,
        summary: str,
        occurred_at: str,
        assertion_state: ProjectExperienceAssertionState,
        actor_type: ProjectExperienceActor,
        event_kind: ProjectExperienceEventKind | None = None,
        outcome: ProjectExperienceOutcome | None = None,
        related_record_ids: Sequence[str] = (),
        evidence_ids: Sequence[str] = (),
        source_ids: Sequence[str] = (),
        sensitivity: RecordSensitivity | None = None,
    ) -> ProjectExperienceInfo:
        """Append a linked replacement; the prior published event remains unchanged."""

        prior = self.get(experience_id)
        return self.record(
            project_id=prior.project_id,
            work_item_id=prior.work_item_id,
            event_kind=event_kind or prior.event_kind,
            summary=summary,
            outcome=prior.outcome if outcome is None else outcome,
            occurred_at=occurred_at,
            assertion_state=assertion_state,
            actor_type=actor_type,
            related_record_ids=related_record_ids,
            evidence_ids=evidence_ids,
            source_ids=source_ids,
            supersedes_id=prior.experience_id,
            sensitivity=sensitivity or prior.sensitivity,
        )

    def get(self, experience_id: str) -> ProjectExperienceInfo:
        try:
            record = self.repository.get_record(_uuid("experience ID", experience_id))
        except KeyError as exc:
            raise ProjectExperienceValidationError("project experience does not exist") from exc
        return _project_experience_from_record(record, self.repository)

    def list(
        self,
        *,
        project_id: str | None = None,
        include_archived: bool = False,
        limit: int = 100,
    ) -> tuple[ProjectExperienceInfo, ...]:
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= MAX_LIST_LIMIT
        ):
            raise ProjectExperienceValidationError("project-experience list limit is invalid")
        safe_project_id = _optional_uuid("project ID", project_id)
        try:
            rows = self.repository.connection.execute(
                "SELECT id FROM records WHERE record_type = 'project_experience' "
                "ORDER BY created_at, id"
            ).fetchall()
        except sqlite3.DatabaseError as exc:
            raise StateCorruptError("project experiences are unreadable") from exc
        result: list[ProjectExperienceInfo] = []
        for row in rows:
            item = self.get(cast(str, row[0]))
            if not include_archived and item.lifecycle_status != "active":
                continue
            if safe_project_id is not None and item.project_id != safe_project_id:
                continue
            result.append(item)
            if len(result) >= limit:
                break
        return tuple(result)

    def export_json(self, experience_id: str) -> str:
        item = self.get(experience_id)
        if item.sensitivity == "secret":
            raise ProjectExperienceValidationError(
                "secret project experiences are excluded from normal export"
            )
        record = self.repository.get_record(item.experience_id)
        payload = {
            "export_schema": "doll.project-experience.v1",
            "record": {
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
            },
        }
        return (
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                allow_nan=False,
                separators=(",", ":"),
            )
            + "\n"
        )


def _validated_values(
    repository: StateRepository,
    *,
    project_id: str,
    work_item_id: str | None,
    event_kind: str,
    summary: str,
    outcome: str | None,
    occurred_at: str,
    assertion_state: str,
    related_record_ids: Sequence[str],
    evidence_ids: Sequence[str],
    source_ids: Sequence[str],
    supersedes_id: str | None,
    sensitivity: RecordSensitivity,
) -> dict[str, object]:
    safe_project_id = _uuid("project experience project ID", project_id)
    safe_work_item_id = _optional_uuid("project experience work-item ID", work_item_id)
    safe_kind = _event_kind(event_kind)
    safe_summary = _text("project experience summary", summary, MAX_SUMMARY_LENGTH)
    safe_outcome = _outcome(outcome)
    safe_occurred_at = _utc("project experience occurred-at", occurred_at)
    safe_assertion = _assertion_state(assertion_state)
    safe_related = _ids("related record IDs", related_record_ids)
    safe_evidence = _ids("evidence IDs", evidence_ids)
    safe_sources = _ids("source IDs", source_ids)
    safe_supersedes = _optional_uuid("supersedes experience ID", supersedes_id)

    if safe_kind == "outcome" and safe_outcome is None:
        raise ProjectExperienceValidationError("outcome events require an outcome value")
    _validate_project(repository, safe_project_id, sensitivity)
    if safe_work_item_id is not None:
        _validate_work_item(repository, safe_work_item_id, safe_project_id, sensitivity)
    _validate_evidence(repository, safe_evidence, sensitivity)
    _validate_generic_links(repository, safe_related, "related record", sensitivity)
    _validate_generic_links(repository, safe_sources, "source", sensitivity)
    if safe_supersedes is not None:
        _validate_supersedes(repository, safe_supersedes, safe_project_id, sensitivity)

    return {
        "project_id": safe_project_id,
        "work_item_id": safe_work_item_id,
        "event_kind": safe_kind,
        "summary": safe_summary,
        "outcome": safe_outcome,
        "occurred_at": safe_occurred_at,
        "assertion_state": safe_assertion,
        "related_record_ids": list(safe_related),
        "evidence_ids": list(safe_evidence),
        "source_ids": list(safe_sources),
        "supersedes_id": safe_supersedes,
    }


def _project_experience_from_record(
    record: RecordEnvelope,
    repository: StateRepository | None = None,
) -> ProjectExperienceInfo:
    try:
        if (
            record.record_type != "project_experience"
            or record.schema_version != PROJECT_EXPERIENCE_SCHEMA_VERSION
        ):
            raise ProjectExperienceValidationError("project-experience envelope is unsupported")
        if record.status not in {"active", "archived"} or record.revision < 1:
            raise ProjectExperienceValidationError("project-experience lifecycle is unsupported")
        project_id = _uuid("project experience project ID", _required_string(record, "project_id"))
        work_item_id = _optional_uuid(
            "project experience work-item ID", _optional_string(record, "work_item_id")
        )
        event_kind = _event_kind(_required_string(record, "event_kind"))
        summary = _text(
            "project experience summary",
            _required_string(record, "summary"),
            MAX_SUMMARY_LENGTH,
        )
        outcome = _outcome(_optional_string(record, "outcome"))
        occurred_at = _utc(
            "project experience occurred-at", _required_string(record, "occurred_at")
        )
        assertion_state = _assertion_state(_required_string(record, "assertion_state"))
        expected_provenance = _ASSERTION_PROVENANCE[assertion_state]
        if record.provenance != expected_provenance:
            raise ProjectExperienceValidationError("project-experience provenance is inconsistent")
        related_record_ids = _metadata_ids(record, "related_record_ids")
        evidence_ids = _metadata_ids(record, "evidence_ids")
        source_ids = _metadata_ids(record, "source_ids")
        supersedes_id = _optional_uuid(
            "supersedes experience ID", _optional_string(record, "supersedes_id")
        )
        if event_kind == "outcome" and outcome is None:
            raise ProjectExperienceValidationError("outcome event is missing outcome value")
        if repository is not None:
            _validate_project(repository, project_id, record.sensitivity)
            if work_item_id is not None:
                _validate_work_item(repository, work_item_id, project_id, record.sensitivity)
            _validate_evidence(repository, evidence_ids, record.sensitivity)
            _validate_generic_links(
                repository, related_record_ids, "related record", record.sensitivity
            )
            _validate_generic_links(repository, source_ids, "source", record.sensitivity)
            if supersedes_id is not None:
                if supersedes_id == record.id:
                    raise ProjectExperienceValidationError(
                        "project experience cannot supersede itself"
                    )
                _validate_supersedes(repository, supersedes_id, project_id, record.sensitivity)
    except (
        KeyError,
        TypeError,
        ValueError,
        ProjectDecisionCorruptError,
        WorkItemCorruptError,
        TruthCorruptError,
        ProjectExperienceValidationError,
    ) as exc:
        raise ProjectExperienceCorruptError("project-experience record is malformed") from exc
    return ProjectExperienceInfo(
        experience_id=record.id,
        project_id=project_id,
        work_item_id=work_item_id,
        event_kind=event_kind,
        summary=summary,
        outcome=outcome,
        occurred_at=occurred_at,
        assertion_state=assertion_state,
        related_record_ids=related_record_ids,
        evidence_ids=evidence_ids,
        source_ids=source_ids,
        supersedes_id=supersedes_id,
        revision=record.revision,
        lifecycle_status=record.status,
        provenance=record.provenance,
        sensitivity=record.sensitivity,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _validate_project(
    repository: StateRepository,
    project_id: str,
    sensitivity: RecordSensitivity,
) -> None:
    try:
        record = repository.get_record(project_id)
    except KeyError as exc:
        raise ProjectExperienceValidationError("linked project does not exist") from exc
    if record.record_type != "project":
        raise ProjectExperienceValidationError("project link points to another record type")
    _reject_secret_link(record, sensitivity, "project")
    _project_from_record(record)


def _validate_work_item(
    repository: StateRepository,
    work_item_id: str,
    project_id: str,
    sensitivity: RecordSensitivity,
) -> None:
    try:
        record = repository.get_record(work_item_id)
    except KeyError as exc:
        raise ProjectExperienceValidationError("linked work item does not exist") from exc
    if record.record_type != "work_item":
        raise ProjectExperienceValidationError("work-item link points to another record type")
    _reject_secret_link(record, sensitivity, "work item")
    item = _work_item_from_record(record, repository)
    if item.project_id != project_id:
        raise ProjectExperienceValidationError("work item belongs to another project")


def _validate_evidence(
    repository: StateRepository,
    evidence_ids: tuple[str, ...],
    sensitivity: RecordSensitivity,
) -> None:
    for evidence_id in evidence_ids:
        try:
            record = repository.get_record(evidence_id)
        except KeyError as exc:
            raise ProjectExperienceValidationError("linked evidence does not exist") from exc
        if record.record_type != "evidence":
            raise ProjectExperienceValidationError("evidence link points to another record type")
        _reject_secret_link(record, sensitivity, "evidence")
        _evidence_from_record(record)


def _validate_generic_links(
    repository: StateRepository,
    record_ids: tuple[str, ...],
    label: str,
    sensitivity: RecordSensitivity,
) -> None:
    for record_id in record_ids:
        try:
            record = repository.get_record(record_id)
        except KeyError as exc:
            raise ProjectExperienceValidationError(f"{label} does not exist") from exc
        _reject_secret_link(record, sensitivity, label)


def _validate_supersedes(
    repository: StateRepository,
    supersedes_id: str,
    project_id: str,
    sensitivity: RecordSensitivity,
) -> None:
    try:
        record = repository.get_record(supersedes_id)
    except KeyError as exc:
        raise ProjectExperienceValidationError("superseded experience does not exist") from exc
    _reject_secret_link(record, sensitivity, "superseded experience")
    prior = _project_experience_from_record(record, None)
    if prior.project_id != project_id:
        raise ProjectExperienceValidationError("superseded experience belongs to another project")


def _reject_secret_link(
    record: RecordEnvelope,
    sensitivity: RecordSensitivity,
    label: str,
) -> None:
    if record.sensitivity == "secret" and sensitivity != "secret":
        raise ProjectExperienceValidationError(
            f"non-secret experience cannot reference secret {label}"
        )


def _required_string(record: RecordEnvelope, key: str) -> str:
    value = record.metadata[key]
    if not isinstance(value, str):
        raise ProjectExperienceValidationError(f"{key} must be text")
    return value


def _optional_string(record: RecordEnvelope, key: str) -> str | None:
    value = record.metadata.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ProjectExperienceValidationError(f"{key} must be text or null")
    return value


def _metadata_ids(record: RecordEnvelope, key: str) -> tuple[str, ...]:
    raw = record.metadata.get(key)
    if not isinstance(raw, list):
        raise ProjectExperienceValidationError(f"{key} must be an ID list")
    return _ids(key, raw)


def _ids(name: str, values: Sequence[str]) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise ProjectExperienceValidationError(f"{name} must be a sequence")
    if len(values) > MAX_LINKS:
        raise ProjectExperienceValidationError(f"{name} exceeds {MAX_LINKS} entries")
    result: list[str] = []
    for value in values:
        canonical = _uuid(name, value)
        if canonical in result:
            raise ProjectExperienceValidationError(f"{name} contains duplicates")
        result.append(canonical)
    return tuple(result)


def _uuid(name: str, value: str) -> str:
    if not isinstance(value, str):
        raise ProjectExperienceValidationError(f"{name} must be text")
    try:
        return str(UUID(value))
    except ValueError as exc:
        raise ProjectExperienceValidationError(f"{name} is invalid") from exc


def _optional_uuid(name: str, value: str | None) -> str | None:
    if value is None:
        return None
    return _uuid(name, value)


def _event_kind(value: str) -> ProjectExperienceEventKind:
    if value not in _ALLOWED_EVENT_KINDS:
        raise ProjectExperienceValidationError("project experience event kind is invalid")
    return cast(ProjectExperienceEventKind, value)


def _outcome(value: str | None) -> ProjectExperienceOutcome | None:
    if value is None:
        return None
    if value not in _ALLOWED_OUTCOMES:
        raise ProjectExperienceValidationError("project experience outcome is invalid")
    return cast(ProjectExperienceOutcome, value)


def _assertion_state(value: str) -> ProjectExperienceAssertionState:
    if value not in _ALLOWED_ASSERTION_STATES:
        raise ProjectExperienceValidationError("project experience assertion state is invalid")
    return cast(ProjectExperienceAssertionState, value)


def _require_assertion_actor(assertion_state: str, actor_type: str) -> None:
    if actor_type != _ASSERTION_ACTORS[assertion_state]:
        raise ProjectExperienceValidationError(
            "project experience assertion state does not match the producing actor"
        )


def _utc(name: str, value: str) -> str:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ProjectExperienceValidationError(f"{name} must be UTC and end in Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ProjectExperienceValidationError(f"{name} is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise ProjectExperienceValidationError(f"{name} must be UTC")
    return value


def _text(name: str, value: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise ProjectExperienceValidationError(f"{name} must be text")
    normalized = "\n".join(line.rstrip() for line in value.strip().splitlines())
    if not normalized or len(normalized) > maximum:
        raise ProjectExperienceValidationError(f"{name} is empty or too long")
    if any(ord(character) < 32 and character not in {"\n", "\t"} for character in normalized):
        raise ProjectExperienceValidationError(f"{name} contains control characters")
    if _POSIX_PATH_PATTERN.search(normalized) or _WINDOWS_PATH_PATTERN.search(normalized):
        raise ProjectExperienceValidationError(f"{name} must not contain private absolute paths")
    return normalized


def _title_for_summary(summary: str) -> str:
    first_line = summary.splitlines()[0]
    return first_line[:240]
