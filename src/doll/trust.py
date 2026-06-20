"""Claim, evidence, inference, and explicit trust-assessment records."""

from __future__ import annotations

import math
import re
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, cast
from uuid import UUID, uuid4

from doll.audit import AuditActorType, _reject_local_path, _reject_secret_text
from doll.audit import _serialize_metadata as _serialize_audit_metadata
from doll.audit import _validate_token as _validate_audit_token
from doll.memory import MemoryCorruptError, _memory_from_record
from doll.state import (
    ReadOnlyStateError,
    RecordEnvelope,
    RecordProvenance,
    RecordSensitivity,
    RecordStatus,
    StaleRevisionError,
    StateCorruptError,
    StateError,
    _utc_now,
)
from doll.state_repository import (
    StateRepository,
    _validate_record_fields,
    _validate_secret_boundary,
)
from doll.state_repository import (
    _serialize_metadata as _serialize_record_metadata,
)

TruthRecordKind = Literal["claim", "evidence", "inference", "trust_assessment"]
TruthActorType = Literal[
    "user",
    "model",
    "runtime",
    "tool",
    "system",
    "importer",
    "migration",
]
TruthOriginType = Literal[
    "user_statement",
    "imported_content",
    "external_source",
    "tool_result",
    "runtime_output",
    "model_proposal",
    "system_observation",
    "migrated",
    "restored",
    "unknown",
]
TruthReviewState = Literal["unreviewed", "reviewed", "disputed", "rejected"]
EvidenceType = Literal["source", "observation", "record", "artifact"]
TrustLevel = Literal["unknown", "distrusted", "limited", "trusted"]
TrustSubjectType = Literal["claim", "evidence", "inference", "confirmed_fact", "source"]
TrustAssessorType = Literal["user", "system"]

_ALLOWED_RECORD_KINDS = frozenset({"claim", "evidence", "inference", "trust_assessment"})
_ALLOWED_ACTORS = frozenset({"user", "model", "runtime", "tool", "system", "importer", "migration"})
_ALLOWED_ORIGINS = frozenset(
    {
        "user_statement",
        "imported_content",
        "external_source",
        "tool_result",
        "runtime_output",
        "model_proposal",
        "system_observation",
        "migrated",
        "restored",
        "unknown",
    }
)
_ALLOWED_REVIEW_STATES = frozenset({"unreviewed", "reviewed", "disputed", "rejected"})
_ALLOWED_EVIDENCE_TYPES = frozenset({"source", "observation", "record", "artifact"})
_ALLOWED_TRUST_LEVELS = frozenset({"unknown", "distrusted", "limited", "trusted"})
_ALLOWED_TRUST_SUBJECTS = frozenset({"claim", "evidence", "inference", "confirmed_fact", "source"})
_ALLOWED_TRUST_ASSESSORS = frozenset({"user", "system"})
_ALLOWED_RECORD_PROVENANCE = frozenset(
    {"user-created", "imported", "model-proposed", "system-generated", "migrated", "restored"}
)
_SHA256_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_CONTROL_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

MAX_TITLE_LENGTH = 240
MAX_BODY_LENGTH = 8000
MAX_UNCERTAINTY_LENGTH = 2000
MAX_METHOD_LENGTH = 1000
MAX_REVIEW_NOTE_LENGTH = 2000
MAX_TRUST_REASON_LENGTH = 2000
MAX_IDENTIFIER_LENGTH = 300
MAX_REFERENCE_COUNT = 100
MAX_LIST_LIMIT = 200


class TruthModelError(StateError):
    """Base class for claim, evidence, inference, and trust failures."""


class TruthValidationError(TruthModelError):
    """Raised when a truth-model request is invalid."""


class ForbiddenTruthMutationError(TruthModelError):
    """Raised when an untrusted actor attempts a review or trust mutation."""


class TruthCorruptError(TruthModelError):
    """Raised when a stored truth-model record is malformed."""


@dataclass(frozen=True, slots=True)
class TruthSource:
    """Explicit, non-authoritative provenance for one truth-status record."""

    origin_type: TruthOriginType
    creator_actor_type: TruthActorType
    source_identifier: str | None = None
    observed_at: str | None = None
    source_content_hash: str | None = None
    transformation_method: str | None = None
    model_manifest_id: str | None = None
    runtime_adapter_id: str | None = None
    session_id: str | None = None
    origin_operation_id: str | None = None

    def __post_init__(self) -> None:
        source = _validate_source_values(
            origin_type=self.origin_type,
            creator_actor_type=self.creator_actor_type,
            source_identifier=self.source_identifier,
            observed_at=self.observed_at,
            source_content_hash=self.source_content_hash,
            transformation_method=self.transformation_method,
            model_manifest_id=self.model_manifest_id,
            runtime_adapter_id=self.runtime_adapter_id,
            session_id=self.session_id,
            origin_operation_id=self.origin_operation_id,
        )
        for name, value in source.items():
            object.__setattr__(self, name, value)


@dataclass(frozen=True, slots=True)
class ClaimInfo:
    record_id: str
    title: str
    statement: str
    confidence: float | None
    uncertainty: str | None
    review_state: TruthReviewState
    reviewed_at: str | None
    reviewer_actor_type: Literal["user"] | None
    review_note: str | None
    source: TruthSource
    revision: int
    status: RecordStatus
    record_provenance: RecordProvenance
    sensitivity: RecordSensitivity
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class EvidenceInfo:
    record_id: str
    title: str
    summary: str
    evidence_type: EvidenceType
    supports_claim_ids: tuple[str, ...]
    contradicts_claim_ids: tuple[str, ...]
    contextualizes_claim_ids: tuple[str, ...]
    confidence: float | None
    uncertainty: str | None
    review_state: TruthReviewState
    reviewed_at: str | None
    reviewer_actor_type: Literal["user"] | None
    review_note: str | None
    source: TruthSource
    revision: int
    status: RecordStatus
    record_provenance: RecordProvenance
    sensitivity: RecordSensitivity
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class InferenceInfo:
    record_id: str
    title: str
    conclusion: str
    method: str
    claim_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    confidence: float | None
    uncertainty: str | None
    review_state: TruthReviewState
    reviewed_at: str | None
    reviewer_actor_type: Literal["user"] | None
    review_note: str | None
    source: TruthSource
    revision: int
    status: RecordStatus
    record_provenance: RecordProvenance
    sensitivity: RecordSensitivity
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class TrustAssessmentInfo:
    record_id: str
    subject_type: TrustSubjectType
    subject_id: str
    level: TrustLevel
    reason: str
    assessor_type: TrustAssessorType
    policy_reference: str | None
    evidence_ids: tuple[str, ...]
    revision: int
    status: RecordStatus
    record_provenance: RecordProvenance
    sensitivity: RecordSensitivity
    created_at: str
    updated_at: str


TruthInfo = ClaimInfo | EvidenceInfo | InferenceInfo | TrustAssessmentInfo


@dataclass(slots=True)
class ClaimEvidenceTrustService:
    """Persist truth status and explicit trust without automatic fact promotion."""

    repository: StateRepository

    def create_claim(
        self,
        *,
        title: str,
        statement: str,
        source: TruthSource,
        confidence: float | None = None,
        uncertainty: str | None = None,
        review_state: TruthReviewState = "unreviewed",
        review_note: str | None = None,
        operation_id: str | None = None,
        sensitivity: RecordSensitivity = "personal",
    ) -> ClaimInfo:
        safe_title = _validate_text("claim title", title, MAX_TITLE_LENGTH)
        safe_statement = _validate_text("claim statement", statement, MAX_BODY_LENGTH)
        safe_source = _require_source(source)
        safe_confidence = _validate_optional_confidence(confidence)
        safe_uncertainty = _validate_optional_text(
            "claim uncertainty", uncertainty, MAX_UNCERTAINTY_LENGTH
        )
        review = _initial_review_values(
            safe_source.creator_actor_type,
            review_state,
            review_note,
        )
        metadata = {
            "truth_kind": "claim",
            "title": safe_title,
            "statement": safe_statement,
            "confidence": safe_confidence,
            "uncertainty": safe_uncertainty,
            **review,
            **_source_metadata(safe_source),
        }
        record_id = _create_truth_record(
            self.repository,
            record_type="claim",
            title=safe_title,
            metadata=metadata,
            provenance=_record_provenance(safe_source),
            sensitivity=sensitivity,
            operation_id=operation_id,
            audit_actor=safe_source.creator_actor_type,
            audit_metadata=_truth_audit_metadata(metadata),
        )
        return self.get_claim(record_id)

    def create_evidence(
        self,
        *,
        title: str,
        summary: str,
        evidence_type: EvidenceType,
        source: TruthSource,
        supports_claim_ids: Sequence[str] = (),
        contradicts_claim_ids: Sequence[str] = (),
        contextualizes_claim_ids: Sequence[str] = (),
        confidence: float | None = None,
        uncertainty: str | None = None,
        review_state: TruthReviewState = "unreviewed",
        review_note: str | None = None,
        operation_id: str | None = None,
        sensitivity: RecordSensitivity = "personal",
    ) -> EvidenceInfo:
        safe_title = _validate_text("evidence title", title, MAX_TITLE_LENGTH)
        safe_summary = _validate_text("evidence summary", summary, MAX_BODY_LENGTH)
        if not isinstance(evidence_type, str) or evidence_type not in _ALLOWED_EVIDENCE_TYPES:
            raise TruthValidationError("invalid evidence type")
        safe_source = _require_source(source)
        supports = _validate_reference_ids("supporting claim IDs", supports_claim_ids)
        contradicts = _validate_reference_ids("contradicting claim IDs", contradicts_claim_ids)
        contextualizes = _validate_reference_ids("contextual claim IDs", contextualizes_claim_ids)
        _require_disjoint_relations(supports, contradicts, contextualizes)
        if not (supports or contradicts or contextualizes):
            raise TruthValidationError("evidence must relate to at least one claim")
        _validate_record_references(
            self.repository, supports + contradicts + contextualizes, "claim"
        )
        safe_confidence = _validate_optional_confidence(confidence)
        safe_uncertainty = _validate_optional_text(
            "evidence uncertainty", uncertainty, MAX_UNCERTAINTY_LENGTH
        )
        review = _initial_review_values(
            safe_source.creator_actor_type,
            review_state,
            review_note,
        )
        metadata = {
            "truth_kind": "evidence",
            "title": safe_title,
            "summary": safe_summary,
            "evidence_type": evidence_type,
            "supports_claim_ids": list(supports),
            "contradicts_claim_ids": list(contradicts),
            "contextualizes_claim_ids": list(contextualizes),
            "confidence": safe_confidence,
            "uncertainty": safe_uncertainty,
            **review,
            **_source_metadata(safe_source),
        }
        record_id = _create_truth_record(
            self.repository,
            record_type="evidence",
            title=safe_title,
            metadata=metadata,
            provenance=_record_provenance(safe_source),
            sensitivity=sensitivity,
            operation_id=operation_id,
            audit_actor=safe_source.creator_actor_type,
            audit_metadata=_truth_audit_metadata(metadata),
        )
        return self.get_evidence(record_id)

    def create_inference(
        self,
        *,
        title: str,
        conclusion: str,
        method: str,
        source: TruthSource,
        claim_ids: Sequence[str] = (),
        evidence_ids: Sequence[str] = (),
        confidence: float | None = None,
        uncertainty: str | None = None,
        review_state: TruthReviewState = "unreviewed",
        review_note: str | None = None,
        operation_id: str | None = None,
        sensitivity: RecordSensitivity = "personal",
    ) -> InferenceInfo:
        safe_title = _validate_text("inference title", title, MAX_TITLE_LENGTH)
        safe_conclusion = _validate_text("inference conclusion", conclusion, MAX_BODY_LENGTH)
        safe_method = _validate_text("inference method", method, MAX_METHOD_LENGTH)
        safe_source = _require_source(source)
        claims = _validate_reference_ids("inference claim IDs", claim_ids)
        evidence = _validate_reference_ids("inference evidence IDs", evidence_ids)
        if not (claims or evidence):
            raise TruthValidationError("inference requires at least one claim or evidence source")
        _validate_record_references(self.repository, claims, "claim")
        _validate_record_references(self.repository, evidence, "evidence")
        safe_confidence = _validate_optional_confidence(confidence)
        safe_uncertainty = _validate_optional_text(
            "inference uncertainty", uncertainty, MAX_UNCERTAINTY_LENGTH
        )
        review = _initial_review_values(
            safe_source.creator_actor_type,
            review_state,
            review_note,
        )
        metadata = {
            "truth_kind": "inference",
            "title": safe_title,
            "conclusion": safe_conclusion,
            "method": safe_method,
            "claim_ids": list(claims),
            "evidence_ids": list(evidence),
            "confidence": safe_confidence,
            "uncertainty": safe_uncertainty,
            **review,
            **_source_metadata(safe_source),
        }
        record_id = _create_truth_record(
            self.repository,
            record_type="inference",
            title=safe_title,
            metadata=metadata,
            provenance=_record_provenance(safe_source),
            sensitivity=sensitivity,
            operation_id=operation_id,
            audit_actor=safe_source.creator_actor_type,
            audit_metadata=_truth_audit_metadata(metadata),
        )
        return self.get_inference(record_id)

    def assess_trust(
        self,
        *,
        subject_type: TrustSubjectType,
        subject_id: str,
        level: TrustLevel,
        reason: str,
        assessor_type: TrustAssessorType = "user",
        policy_reference: str | None = None,
        evidence_ids: Sequence[str] = (),
        operation_id: str | None = None,
        sensitivity: RecordSensitivity = "personal",
    ) -> TrustAssessmentInfo:
        safe_subject_type = _validate_trust_subject_type(subject_type)
        safe_subject_id = _validate_identifier("trust subject ID", subject_id)
        _validate_trust_subject(self.repository, safe_subject_type, safe_subject_id)
        safe_level = _validate_trust_level(level)
        safe_reason = _validate_text("trust reason", reason, MAX_TRUST_REASON_LENGTH)
        safe_assessor = _validate_trust_assessor(assessor_type)
        safe_policy = _validate_optional_identifier("policy reference", policy_reference)
        if safe_assessor == "system" and safe_policy is None:
            raise TruthValidationError("system trust assessment requires a policy reference")
        evidence = _validate_reference_ids("trust evidence IDs", evidence_ids)
        _validate_record_references(self.repository, evidence, "evidence")
        metadata: dict[str, object] = {
            "truth_kind": "trust_assessment",
            "subject_type": safe_subject_type,
            "subject_id": safe_subject_id,
            "level": safe_level,
            "reason": safe_reason,
            "assessor_type": safe_assessor,
            "policy_reference": safe_policy,
            "evidence_ids": list(evidence),
        }
        record_id = _create_truth_record(
            self.repository,
            record_type="trust_assessment",
            title=f"Trust assessment: {safe_subject_type}",
            metadata=metadata,
            provenance="user-created" if safe_assessor == "user" else "system-generated",
            sensitivity=sensitivity,
            operation_id=operation_id,
            audit_actor=cast(TruthActorType, safe_assessor),
            audit_metadata=_truth_audit_metadata(metadata),
        )
        return self.get_trust_assessment(record_id)

    def review(
        self,
        record_id: str,
        *,
        expected_revision: int,
        review_state: TruthReviewState,
        review_note: str | None = None,
        operation_id: str | None = None,
        actor_type: TruthActorType = "user",
    ) -> ClaimInfo | EvidenceInfo | InferenceInfo:
        if actor_type != "user":
            raise ForbiddenTruthMutationError("only the user may review truth-status records")
        record = self.repository.get_record(record_id)
        if record.record_type not in {"claim", "evidence", "inference"}:
            raise KeyError(record_id)
        _parse_truth_record(record)
        _require_active(record)
        metadata = dict(record.metadata)
        metadata.update(_review_values(review_state, review_note))
        _update_truth_record(
            self.repository,
            current=record,
            expected_revision=expected_revision,
            metadata=metadata,
            status="active",
            operation_id=operation_id,
            audit_actor="user",
            action=f"truth.{record.record_type}.review",
            audit_metadata=_truth_audit_metadata(metadata),
        )
        updated = self.repository.get_record(record_id)
        result = _parse_truth_record(updated)
        if isinstance(result, TrustAssessmentInfo):  # pragma: no cover - guarded above.
            raise TruthCorruptError("review returned the wrong truth record type")
        return result

    def archive(
        self,
        record_id: str,
        *,
        expected_revision: int,
        operation_id: str | None = None,
        actor_type: TruthActorType = "user",
    ) -> TruthInfo:
        if actor_type != "user":
            raise ForbiddenTruthMutationError("only the user may archive truth-model records")
        record = self.repository.get_record(record_id)
        if record.record_type not in _ALLOWED_RECORD_KINDS:
            raise KeyError(record_id)
        parsed = _parse_truth_record(record)
        _require_active(record)
        _update_truth_record(
            self.repository,
            current=record,
            expected_revision=expected_revision,
            metadata=record.metadata,
            status="archived",
            operation_id=operation_id,
            audit_actor="user",
            action=f"truth.{record.record_type}.archive",
            audit_metadata=_truth_audit_metadata(record.metadata),
        )
        return _parse_truth_record(self.repository.get_record(parsed.record_id))

    def get_claim(self, record_id: str) -> ClaimInfo:
        value = _parse_truth_record(_require_record_type(self.repository, record_id, "claim"))
        if not isinstance(value, ClaimInfo):  # pragma: no cover - type guard.
            raise TruthCorruptError("claim record returned the wrong type")
        return value

    def get_evidence(self, record_id: str) -> EvidenceInfo:
        value = _parse_truth_record(_require_record_type(self.repository, record_id, "evidence"))
        if not isinstance(value, EvidenceInfo):  # pragma: no cover - type guard.
            raise TruthCorruptError("evidence record returned the wrong type")
        return value

    def get_inference(self, record_id: str) -> InferenceInfo:
        value = _parse_truth_record(_require_record_type(self.repository, record_id, "inference"))
        if not isinstance(value, InferenceInfo):  # pragma: no cover - type guard.
            raise TruthCorruptError("inference record returned the wrong type")
        return value

    def get_trust_assessment(self, record_id: str) -> TrustAssessmentInfo:
        value = _parse_truth_record(
            _require_record_type(self.repository, record_id, "trust_assessment")
        )
        if not isinstance(value, TrustAssessmentInfo):  # pragma: no cover - type guard.
            raise TruthCorruptError("trust assessment returned the wrong type")
        return value

    def list(
        self,
        kind: TruthRecordKind,
        *,
        include_archived: bool = False,
        limit: int = 50,
    ) -> tuple[TruthInfo, ...]:
        if not isinstance(kind, str) or kind not in _ALLOWED_RECORD_KINDS:
            raise TruthValidationError("invalid truth record kind")
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= MAX_LIST_LIMIT
        ):
            raise TruthValidationError(f"truth list limit must be between 1 and {MAX_LIST_LIMIT}")
        status_clause = (
            "AND status IN ('active', 'archived')" if include_archived else "AND status = 'active'"
        )
        try:
            rows = self.repository.connection.execute(
                f"""
                SELECT id FROM records
                WHERE record_type = ? {status_clause}
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (kind, limit),
            ).fetchall()
        except sqlite3.DatabaseError as exc:
            raise StateCorruptError("truth-model records are unreadable") from exc
        return tuple(
            _parse_truth_record(self.repository.get_record(cast(str, row[0]))) for row in rows
        )


def _validate_source_values(
    *,
    origin_type: object,
    creator_actor_type: object,
    source_identifier: object,
    observed_at: object,
    source_content_hash: object,
    transformation_method: object,
    model_manifest_id: object,
    runtime_adapter_id: object,
    session_id: object,
    origin_operation_id: object,
) -> dict[str, object]:
    if not isinstance(origin_type, str) or origin_type not in _ALLOWED_ORIGINS:
        raise TruthValidationError("invalid truth origin type")
    if not isinstance(creator_actor_type, str) or creator_actor_type not in _ALLOWED_ACTORS:
        raise TruthValidationError("invalid truth creator actor type")
    safe_source_identifier = _validate_optional_identifier("source identifier", source_identifier)
    safe_observed_at = _validate_optional_utc("observation time", observed_at)
    safe_hash = _validate_optional_hash(source_content_hash)
    safe_transformation = _validate_optional_text(
        "transformation method", transformation_method, MAX_METHOD_LENGTH
    )
    safe_model = _validate_optional_identifier("model manifest ID", model_manifest_id)
    safe_runtime = _validate_optional_identifier("runtime adapter ID", runtime_adapter_id)
    safe_session = _validate_optional_identifier("session ID", session_id)
    safe_operation = _validate_optional_identifier("origin operation ID", origin_operation_id)

    if origin_type == "user_statement" and creator_actor_type != "user":
        raise TruthValidationError("user-statement origin requires a user creator")
    if origin_type == "imported_content":
        if creator_actor_type != "importer":
            raise TruthValidationError("imported-content origin requires an importer creator")
        if safe_source_identifier is None or safe_operation is None:
            raise TruthValidationError(
                "imported-content origin requires source and operation provenance"
            )
    if origin_type == "external_source" and safe_source_identifier is None:
        raise TruthValidationError("external-source origin requires a source identifier")
    if origin_type == "tool_result":
        if creator_actor_type != "tool":
            raise TruthValidationError("tool-result origin requires a tool creator")
        if safe_source_identifier is None or safe_operation is None:
            raise TruthValidationError(
                "tool-result origin requires source and operation provenance"
            )
    if origin_type == "runtime_output":
        if creator_actor_type != "runtime":
            raise TruthValidationError("runtime-output origin requires a runtime creator")
        if safe_runtime is None or safe_operation is None:
            raise TruthValidationError(
                "runtime-output origin requires runtime and operation provenance"
            )
    if origin_type == "model_proposal":
        if creator_actor_type != "model":
            raise TruthValidationError("model-proposal origin requires a model creator")
        required = (safe_model, safe_runtime, safe_session, safe_operation)
        if any(value is None for value in required):
            raise TruthValidationError(
                "model-proposal origin requires model, runtime, session, and operation provenance"
            )
    if origin_type == "system_observation" and creator_actor_type != "system":
        raise TruthValidationError("system-observation origin requires a system creator")
    if origin_type == "migrated" and creator_actor_type != "migration":
        raise TruthValidationError("migrated origin requires a migration creator")
    if origin_type == "restored" and creator_actor_type != "system":
        raise TruthValidationError("restored origin requires a system creator")

    required_origin_for_actor = {
        "model": "model_proposal",
        "runtime": "runtime_output",
        "tool": "tool_result",
        "importer": "imported_content",
        "migration": "migrated",
    }.get(creator_actor_type)
    if required_origin_for_actor is not None and origin_type != required_origin_for_actor:
        raise TruthValidationError(
            f"{creator_actor_type} creator requires {required_origin_for_actor} origin"
        )

    return {
        "origin_type": cast(TruthOriginType, origin_type),
        "creator_actor_type": cast(TruthActorType, creator_actor_type),
        "source_identifier": safe_source_identifier,
        "observed_at": safe_observed_at,
        "source_content_hash": safe_hash,
        "transformation_method": safe_transformation,
        "model_manifest_id": safe_model,
        "runtime_adapter_id": safe_runtime,
        "session_id": safe_session,
        "origin_operation_id": safe_operation,
    }


def _require_source(value: TruthSource) -> TruthSource:
    if type(value) is not TruthSource:
        raise TruthValidationError("truth record requires validated source provenance")
    return value


def _source_metadata(source: TruthSource) -> dict[str, object]:
    return {
        "origin_type": source.origin_type,
        "creator_actor_type": source.creator_actor_type,
        "source_identifier": source.source_identifier,
        "observed_at": source.observed_at,
        "source_content_hash": source.source_content_hash,
        "transformation_method": source.transformation_method,
        "model_manifest_id": source.model_manifest_id,
        "runtime_adapter_id": source.runtime_adapter_id,
        "session_id": source.session_id,
        "origin_operation_id": source.origin_operation_id,
    }


def _source_from_metadata(metadata: dict[str, object]) -> TruthSource:
    return TruthSource(
        origin_type=cast(TruthOriginType, _required_string(metadata, "origin_type")),
        creator_actor_type=cast(TruthActorType, _required_string(metadata, "creator_actor_type")),
        source_identifier=_optional_string(metadata, "source_identifier"),
        observed_at=_optional_string(metadata, "observed_at"),
        source_content_hash=_optional_string(metadata, "source_content_hash"),
        transformation_method=_optional_string(metadata, "transformation_method"),
        model_manifest_id=_optional_string(metadata, "model_manifest_id"),
        runtime_adapter_id=_optional_string(metadata, "runtime_adapter_id"),
        session_id=_optional_string(metadata, "session_id"),
        origin_operation_id=_optional_string(metadata, "origin_operation_id"),
    )


def _initial_review_values(
    actor_type: TruthActorType,
    review_state: TruthReviewState,
    review_note: str | None,
) -> dict[str, object]:
    safe_state = _validate_review_state(review_state)
    safe_note = _validate_optional_text("review note", review_note, MAX_REVIEW_NOTE_LENGTH)
    if actor_type != "user" and safe_state != "unreviewed":
        raise ForbiddenTruthMutationError("non-user truth records must be created as unreviewed")
    if safe_state == "unreviewed":
        if safe_note is not None:
            raise TruthValidationError("unreviewed record cannot have a review note")
        return {
            "review_state": "unreviewed",
            "reviewed_at": None,
            "reviewer_actor_type": None,
            "review_note": None,
        }
    return {
        "review_state": safe_state,
        "reviewed_at": _utc_now(),
        "reviewer_actor_type": "user",
        "review_note": safe_note,
    }


def _review_values(
    review_state: TruthReviewState,
    review_note: str | None,
) -> dict[str, object]:
    return _initial_review_values("user", review_state, review_note)


def _review_from_metadata(
    metadata: dict[str, object],
) -> tuple[TruthReviewState, str | None, Literal["user"] | None, str | None]:
    state = _validate_review_state(_required_string(metadata, "review_state"))
    reviewed_at = _validate_optional_utc("reviewed time", _optional_string(metadata, "reviewed_at"))
    reviewer = _optional_string(metadata, "reviewer_actor_type")
    note = _validate_optional_text(
        "review note", _optional_string(metadata, "review_note"), MAX_REVIEW_NOTE_LENGTH
    )
    if state == "unreviewed":
        if reviewed_at is not None or reviewer is not None or note is not None:
            raise TruthValidationError("unreviewed record contains review metadata")
        return state, None, None, None
    if reviewed_at is None or reviewer != "user":
        raise TruthValidationError("reviewed record lacks user review provenance")
    return state, reviewed_at, "user", note


def _create_truth_record(
    repository: StateRepository,
    *,
    record_type: TruthRecordKind,
    title: str,
    metadata: dict[str, object],
    provenance: RecordProvenance,
    sensitivity: RecordSensitivity,
    operation_id: str | None,
    audit_actor: TruthActorType,
    audit_metadata: dict[str, object],
) -> str:
    if repository.read_only:
        raise ReadOnlyStateError("state repository is open in read-only mode")
    _validate_record_fields(
        record_type=record_type,
        schema_version=1,
        status="active",
        provenance=provenance,
        sensitivity=sensitivity,
    )
    _validate_secret_boundary(
        record_type=record_type,
        sensitivity=sensitivity,
        metadata=metadata,
    )
    safe_operation_id = _validate_operation_id(operation_id)
    record_id = str(uuid4())
    now = _utc_now()
    metadata_json = _serialize_record_metadata(metadata)
    connection = repository.connection
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """
            INSERT INTO records (
                id, record_type, schema_version, created_at, updated_at, revision,
                status, provenance, sensitivity, title, metadata_json
            ) VALUES (?, ?, 1, ?, ?, 1, 'active', ?, ?, ?, ?)
            """,
            (
                record_id,
                record_type,
                now,
                now,
                provenance,
                sensitivity,
                title,
                metadata_json,
            ),
        )
        _insert_truth_audit(
            repository,
            operation_id=safe_operation_id,
            actor_type=audit_actor,
            action=f"truth.{record_type}.create",
            target_type=record_type,
            target_id=record_id,
            metadata=audit_metadata,
        )
        state_revision = repository._commit_state_revision()
        connection.execute("COMMIT")
    except sqlite3.DatabaseError as exc:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise StateCorruptError("truth-model record could not be created") from exc
    except BaseException:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise
    repository._sync_after_commit(state_revision)
    return record_id


def _update_truth_record(
    repository: StateRepository,
    *,
    current: RecordEnvelope,
    expected_revision: int,
    metadata: dict[str, object],
    status: RecordStatus,
    operation_id: str | None,
    audit_actor: TruthActorType,
    action: str,
    audit_metadata: dict[str, object],
) -> None:
    if repository.read_only:
        raise ReadOnlyStateError("state repository is open in read-only mode")
    if isinstance(expected_revision, bool) or not isinstance(expected_revision, int):
        raise TruthValidationError("expected revision must be an integer")
    safe_operation_id = _validate_operation_id(operation_id)
    _validate_secret_boundary(
        record_type=current.record_type,
        sensitivity=current.sensitivity,
        metadata=metadata,
    )
    metadata_json = _serialize_record_metadata(metadata)
    now = _utc_now()
    connection = repository.connection
    try:
        connection.execute("BEGIN IMMEDIATE")
        refreshed = repository.get_record(current.id)
        if refreshed.revision != expected_revision:
            raise StaleRevisionError(
                f"record revision is {refreshed.revision}, expected {expected_revision}"
            )
        if refreshed.status != "active":
            raise TruthValidationError("archived truth-model record cannot be changed")
        connection.execute(
            """
            UPDATE records
            SET updated_at = ?, revision = revision + 1, status = ?, metadata_json = ?
            WHERE id = ? AND revision = ? AND status = 'active'
            """,
            (now, status, metadata_json, current.id, expected_revision),
        )
        changed = connection.execute("SELECT changes()").fetchone()
        if changed is None or cast(int, changed[0]) != 1:
            raise StaleRevisionError("record revision changed during update")
        _insert_truth_audit(
            repository,
            operation_id=safe_operation_id,
            actor_type=audit_actor,
            action=action,
            target_type=cast(TruthRecordKind, current.record_type),
            target_id=current.id,
            metadata=audit_metadata,
        )
        state_revision = repository._commit_state_revision()
        connection.execute("COMMIT")
    except sqlite3.DatabaseError as exc:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise StateCorruptError("truth-model record could not be updated") from exc
    except BaseException:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise
    repository._sync_after_commit(state_revision)


def _insert_truth_audit(
    repository: StateRepository,
    *,
    operation_id: str,
    actor_type: TruthActorType,
    action: str,
    target_type: TruthRecordKind,
    target_id: str,
    metadata: dict[str, object],
) -> None:
    repository.connection.execute(
        """
        INSERT INTO audit_events (
            event_id, operation_id, occurred_at, actor_type, action,
            target_type, target_id, result, summary, metadata_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'success', ?, ?)
        """,
        (
            str(uuid4()),
            operation_id,
            _utc_now(),
            _audit_actor(actor_type),
            _validate_audit_token("action", action, 120),
            target_type,
            target_id,
            "Changed truth-status or trust record",
            _serialize_audit_metadata(metadata),
        ),
    )


def _truth_audit_metadata(metadata: dict[str, object]) -> dict[str, object]:
    kind = _required_string(metadata, "truth_kind")
    result: dict[str, object] = {"truth_kind": kind}
    if kind in {"claim", "evidence", "inference"}:
        result.update(
            {
                "origin_type": _required_string(metadata, "origin_type"),
                "review_state": _required_string(metadata, "review_state"),
                "confidence_present": metadata.get("confidence") is not None,
                "uncertainty_present": metadata.get("uncertainty") is not None,
                "source_identifier_present": metadata.get("source_identifier") is not None,
                "source_hash_present": metadata.get("source_content_hash") is not None,
            }
        )
    if kind == "evidence":
        result.update(
            {
                "supports_count": len(_metadata_list(metadata, "supports_claim_ids")),
                "contradicts_count": len(_metadata_list(metadata, "contradicts_claim_ids")),
                "context_count": len(_metadata_list(metadata, "contextualizes_claim_ids")),
            }
        )
    elif kind == "inference":
        result.update(
            {
                "claim_count": len(_metadata_list(metadata, "claim_ids")),
                "evidence_count": len(_metadata_list(metadata, "evidence_ids")),
            }
        )
    elif kind == "trust_assessment":
        result.update(
            {
                "subject_type": _required_string(metadata, "subject_type"),
                "level": _required_string(metadata, "level"),
                "assessor_type": _required_string(metadata, "assessor_type"),
                "evidence_count": len(_metadata_list(metadata, "evidence_ids")),
                "policy_reference_present": metadata.get("policy_reference") is not None,
            }
        )
    return result


def _parse_truth_record(record: RecordEnvelope) -> TruthInfo:
    try:
        _validate_truth_envelope(record)
        kind = _required_string(record.metadata, "truth_kind")
        if kind != record.record_type:
            raise TruthValidationError("truth kind and record type are inconsistent")
        if kind == "claim":
            return _claim_from_record_unchecked(record)
        if kind == "evidence":
            return _evidence_from_record_unchecked(record)
        if kind == "inference":
            return _inference_from_record_unchecked(record)
        if kind == "trust_assessment":
            return _trust_assessment_from_record_unchecked(record)
        raise TruthValidationError("unsupported truth record kind")
    except (KeyError, TypeError, ValueError, TruthValidationError) as exc:
        raise TruthCorruptError("truth-model record is malformed") from exc


def _claim_from_record(record: RecordEnvelope) -> ClaimInfo:
    value = _parse_truth_record(record)
    if not isinstance(value, ClaimInfo):
        raise TruthCorruptError("record is not a claim")
    return value


def _evidence_from_record(record: RecordEnvelope) -> EvidenceInfo:
    value = _parse_truth_record(record)
    if not isinstance(value, EvidenceInfo):
        raise TruthCorruptError("record is not evidence")
    return value


def _inference_from_record(record: RecordEnvelope) -> InferenceInfo:
    value = _parse_truth_record(record)
    if not isinstance(value, InferenceInfo):
        raise TruthCorruptError("record is not an inference")
    return value


def _trust_assessment_from_record(record: RecordEnvelope) -> TrustAssessmentInfo:
    value = _parse_truth_record(record)
    if not isinstance(value, TrustAssessmentInfo):
        raise TruthCorruptError("record is not a trust assessment")
    return value


def _claim_from_record_unchecked(record: RecordEnvelope) -> ClaimInfo:
    title = _record_title(record, "claim")
    statement = _validate_text(
        "claim statement", _required_string(record.metadata, "statement"), MAX_BODY_LENGTH
    )
    confidence = _validate_optional_confidence(record.metadata.get("confidence"))
    uncertainty = _validate_optional_text(
        "claim uncertainty",
        _optional_string(record.metadata, "uncertainty"),
        MAX_UNCERTAINTY_LENGTH,
    )
    review_state, reviewed_at, reviewer, review_note = _review_from_metadata(record.metadata)
    source = _source_from_metadata(record.metadata)
    _validate_record_source_provenance(record, source)
    return ClaimInfo(
        record_id=record.id,
        title=title,
        statement=statement,
        confidence=confidence,
        uncertainty=uncertainty,
        review_state=review_state,
        reviewed_at=reviewed_at,
        reviewer_actor_type=reviewer,
        review_note=review_note,
        source=source,
        revision=record.revision,
        status=record.status,
        record_provenance=record.provenance,
        sensitivity=record.sensitivity,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _evidence_from_record_unchecked(record: RecordEnvelope) -> EvidenceInfo:
    title = _record_title(record, "evidence")
    summary = _validate_text(
        "evidence summary", _required_string(record.metadata, "summary"), MAX_BODY_LENGTH
    )
    evidence_type = _required_string(record.metadata, "evidence_type")
    if evidence_type not in _ALLOWED_EVIDENCE_TYPES:
        raise TruthValidationError("invalid evidence type")
    supports = _metadata_reference_ids(record.metadata, "supports_claim_ids")
    contradicts = _metadata_reference_ids(record.metadata, "contradicts_claim_ids")
    contextualizes = _metadata_reference_ids(record.metadata, "contextualizes_claim_ids")
    _require_disjoint_relations(supports, contradicts, contextualizes)
    if not (supports or contradicts or contextualizes):
        raise TruthValidationError("evidence has no claim relation")
    confidence = _validate_optional_confidence(record.metadata.get("confidence"))
    uncertainty = _validate_optional_text(
        "evidence uncertainty",
        _optional_string(record.metadata, "uncertainty"),
        MAX_UNCERTAINTY_LENGTH,
    )
    review_state, reviewed_at, reviewer, review_note = _review_from_metadata(record.metadata)
    source = _source_from_metadata(record.metadata)
    _validate_record_source_provenance(record, source)
    return EvidenceInfo(
        record_id=record.id,
        title=title,
        summary=summary,
        evidence_type=cast(EvidenceType, evidence_type),
        supports_claim_ids=supports,
        contradicts_claim_ids=contradicts,
        contextualizes_claim_ids=contextualizes,
        confidence=confidence,
        uncertainty=uncertainty,
        review_state=review_state,
        reviewed_at=reviewed_at,
        reviewer_actor_type=reviewer,
        review_note=review_note,
        source=source,
        revision=record.revision,
        status=record.status,
        record_provenance=record.provenance,
        sensitivity=record.sensitivity,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _inference_from_record_unchecked(record: RecordEnvelope) -> InferenceInfo:
    title = _record_title(record, "inference")
    conclusion = _validate_text(
        "inference conclusion", _required_string(record.metadata, "conclusion"), MAX_BODY_LENGTH
    )
    method = _validate_text(
        "inference method", _required_string(record.metadata, "method"), MAX_METHOD_LENGTH
    )
    claim_ids = _metadata_reference_ids(record.metadata, "claim_ids")
    evidence_ids = _metadata_reference_ids(record.metadata, "evidence_ids")
    if not (claim_ids or evidence_ids):
        raise TruthValidationError("inference has no source links")
    confidence = _validate_optional_confidence(record.metadata.get("confidence"))
    uncertainty = _validate_optional_text(
        "inference uncertainty",
        _optional_string(record.metadata, "uncertainty"),
        MAX_UNCERTAINTY_LENGTH,
    )
    review_state, reviewed_at, reviewer, review_note = _review_from_metadata(record.metadata)
    source = _source_from_metadata(record.metadata)
    _validate_record_source_provenance(record, source)
    return InferenceInfo(
        record_id=record.id,
        title=title,
        conclusion=conclusion,
        method=method,
        claim_ids=claim_ids,
        evidence_ids=evidence_ids,
        confidence=confidence,
        uncertainty=uncertainty,
        review_state=review_state,
        reviewed_at=reviewed_at,
        reviewer_actor_type=reviewer,
        review_note=review_note,
        source=source,
        revision=record.revision,
        status=record.status,
        record_provenance=record.provenance,
        sensitivity=record.sensitivity,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _trust_assessment_from_record_unchecked(record: RecordEnvelope) -> TrustAssessmentInfo:
    expected_title = f"Trust assessment: {_required_string(record.metadata, 'subject_type')}"
    if record.title != expected_title:
        raise TruthValidationError("trust-assessment title is inconsistent")
    subject_type = _validate_trust_subject_type(
        cast(TrustSubjectType, _required_string(record.metadata, "subject_type"))
    )
    subject_id = _validate_identifier(
        "trust subject ID", _required_string(record.metadata, "subject_id")
    )
    level = _validate_trust_level(cast(TrustLevel, _required_string(record.metadata, "level")))
    reason = _validate_text(
        "trust reason", _required_string(record.metadata, "reason"), MAX_TRUST_REASON_LENGTH
    )
    assessor = _validate_trust_assessor(
        cast(TrustAssessorType, _required_string(record.metadata, "assessor_type"))
    )
    policy = _validate_optional_identifier(
        "policy reference", _optional_string(record.metadata, "policy_reference")
    )
    if assessor == "system" and policy is None:
        raise TruthValidationError("system trust assessment lacks a policy reference")
    evidence_ids = _metadata_reference_ids(record.metadata, "evidence_ids")
    expected_provenance: RecordProvenance = (
        "user-created" if assessor == "user" else "system-generated"
    )
    if record.provenance != expected_provenance:
        raise TruthValidationError("trust-assessment provenance is inconsistent")
    return TrustAssessmentInfo(
        record_id=record.id,
        subject_type=subject_type,
        subject_id=subject_id,
        level=level,
        reason=reason,
        assessor_type=assessor,
        policy_reference=policy,
        evidence_ids=evidence_ids,
        revision=record.revision,
        status=record.status,
        record_provenance=record.provenance,
        sensitivity=record.sensitivity,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _validate_truth_envelope(record: RecordEnvelope) -> None:
    if record.record_type not in _ALLOWED_RECORD_KINDS:
        raise TruthValidationError("unsupported truth record type")
    if record.schema_version != 1:
        raise TruthValidationError("truth record schema version is unsupported")
    if record.revision < 1:
        raise TruthValidationError("truth record revision must be positive")
    if record.status not in {"active", "archived"}:
        raise TruthValidationError("truth record lifecycle is unsupported")
    if record.provenance not in _ALLOWED_RECORD_PROVENANCE:
        raise TruthValidationError("truth record provenance is unsupported")
    if record.sensitivity not in {"public", "internal", "personal", "sensitive", "secret"}:
        raise TruthValidationError("truth record sensitivity is unsupported")


def _record_title(record: RecordEnvelope, kind: str) -> str:
    title = _validate_text(
        f"{kind} title", _required_string(record.metadata, "title"), MAX_TITLE_LENGTH
    )
    if record.title != title:
        raise TruthValidationError(f"{kind} title is inconsistent")
    return title


def _validate_record_source_provenance(record: RecordEnvelope, source: TruthSource) -> None:
    if record.provenance != _record_provenance(source):
        raise TruthValidationError("record provenance and source provenance are inconsistent")


def _record_provenance(source: TruthSource) -> RecordProvenance:
    if source.origin_type == "migrated":
        return "migrated"
    if source.origin_type == "restored":
        return "restored"
    if source.origin_type == "imported_content" or source.creator_actor_type == "importer":
        return "imported"
    if source.origin_type == "model_proposal" or source.creator_actor_type == "model":
        return "model-proposed"
    if source.creator_actor_type == "user":
        return "user-created"
    return "system-generated"


def _validate_trust_subject(
    repository: StateRepository,
    subject_type: TrustSubjectType,
    subject_id: str,
) -> None:
    if subject_type == "source":
        return
    expected = "memory" if subject_type == "confirmed_fact" else subject_type
    record = _require_record_type(repository, subject_id, expected)
    if subject_type == "confirmed_fact":
        try:
            _memory_from_record(record)
        except MemoryCorruptError as exc:
            raise TruthValidationError("confirmed-fact subject is malformed") from exc
    else:
        _parse_truth_record(record)


def _validate_record_references(
    repository: StateRepository,
    record_ids: Sequence[str],
    expected_type: str,
) -> None:
    for record_id in record_ids:
        record = _require_record_type(repository, record_id, expected_type)
        if expected_type in {"claim", "evidence", "inference", "trust_assessment"}:
            _parse_truth_record(record)


def _require_record_type(
    repository: StateRepository,
    record_id: str,
    expected_type: str,
) -> RecordEnvelope:
    safe_id = _validate_uuid("record ID", record_id)
    try:
        record = repository.get_record(safe_id)
    except KeyError as exc:
        raise TruthValidationError(f"referenced {expected_type} record does not exist") from exc
    if record.record_type != expected_type:
        raise TruthValidationError(f"referenced record is not {expected_type}")
    return record


def _require_active(record: RecordEnvelope) -> None:
    if record.status != "active":
        raise TruthValidationError("archived truth-model record cannot be changed")


def _require_disjoint_relations(*groups: Sequence[str]) -> None:
    seen: set[str] = set()
    for group in groups:
        overlap = seen.intersection(group)
        if overlap:
            raise TruthValidationError("one claim cannot have multiple evidence relations")
        seen.update(group)


def _validate_reference_ids(name: str, values: Sequence[str]) -> tuple[str, ...]:
    if isinstance(values, str | bytes):
        raise TruthValidationError(f"{name} must be a sequence")
    if len(values) > MAX_REFERENCE_COUNT:
        raise TruthValidationError(f"{name} exceeds {MAX_REFERENCE_COUNT} entries")
    result = tuple(_validate_uuid(name, value) for value in values)
    if len(set(result)) != len(result):
        raise TruthValidationError(f"{name} contains duplicate IDs")
    return result


def _metadata_reference_ids(metadata: dict[str, object], key: str) -> tuple[str, ...]:
    values = _metadata_list(metadata, key)
    if any(not isinstance(value, str) for value in values):
        raise TruthValidationError(f"{key} contains a non-string ID")
    return _validate_reference_ids(key, cast(list[str], values))


def _metadata_list(metadata: dict[str, object], key: str) -> list[object]:
    value = metadata.get(key)
    if not isinstance(value, list):
        raise TruthValidationError(f"{key} is not a list")
    return cast(list[object], value)


def _validate_review_state(value: object) -> TruthReviewState:
    if not isinstance(value, str) or value not in _ALLOWED_REVIEW_STATES:
        raise TruthValidationError("invalid review state")
    return cast(TruthReviewState, value)


def _validate_trust_subject_type(value: object) -> TrustSubjectType:
    if not isinstance(value, str) or value not in _ALLOWED_TRUST_SUBJECTS:
        raise TruthValidationError("invalid trust subject type")
    return cast(TrustSubjectType, value)


def _validate_trust_level(value: object) -> TrustLevel:
    if not isinstance(value, str) or value not in _ALLOWED_TRUST_LEVELS:
        raise TruthValidationError("invalid trust level")
    return cast(TrustLevel, value)


def _validate_trust_assessor(value: object) -> TrustAssessorType:
    if not isinstance(value, str) or value not in _ALLOWED_TRUST_ASSESSORS:
        raise ForbiddenTruthMutationError("only user or policy-bound system may assess trust")
    return cast(TrustAssessorType, value)


def _validate_optional_confidence(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TruthValidationError("confidence must be a number or null")
    confidence = float(value)
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise TruthValidationError("confidence must be between 0 and 1")
    return confidence


def _validate_optional_hash(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TruthValidationError("source content hash must be a string")
    normalized = value.strip().lower()
    if _SHA256_PATTERN.fullmatch(normalized) is None:
        raise TruthValidationError("source content hash must be a sha256 digest")
    return normalized


def _validate_optional_utc(name: str, value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TruthValidationError(f"{name} must be a string or null")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise TruthValidationError(f"{name} must be an ISO 8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise TruthValidationError(f"{name} must include a timezone")
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _validate_text(name: str, value: object, maximum: int) -> str:
    if not isinstance(value, str):
        raise TruthValidationError(f"{name} must be a string")
    normalized = " ".join(value.split())
    if not normalized:
        raise TruthValidationError(f"{name} must not be blank")
    if len(normalized) > maximum:
        raise TruthValidationError(f"{name} exceeds {maximum} characters")
    if _CONTROL_PATTERN.search(normalized):
        raise TruthValidationError(f"{name} contains control characters")
    try:
        _reject_secret_text(normalized)
        _reject_local_path(normalized)
    except Exception as exc:
        raise TruthValidationError(f"{name} contains unsafe data") from exc
    return normalized


def _validate_optional_text(name: str, value: object, maximum: int) -> str | None:
    if value is None:
        return None
    return _validate_text(name, value, maximum)


def _validate_identifier(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise TruthValidationError(f"{name} must be a string")
    normalized = " ".join(value.split())
    if not normalized:
        raise TruthValidationError(f"{name} must not be blank")
    if len(normalized) > MAX_IDENTIFIER_LENGTH:
        raise TruthValidationError(f"{name} exceeds {MAX_IDENTIFIER_LENGTH} characters")
    if _CONTROL_PATTERN.search(normalized):
        raise TruthValidationError(f"{name} contains control characters")
    try:
        _reject_secret_text(normalized)
        _reject_local_path(normalized)
    except Exception as exc:
        raise TruthValidationError(f"{name} contains unsafe data") from exc
    return normalized


def _validate_optional_identifier(name: str, value: object) -> str | None:
    if value is None:
        return None
    return _validate_identifier(name, value)


def _validate_uuid(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise TruthValidationError(f"{name} must be a UUID string")
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise TruthValidationError(f"{name} must be a UUID string") from exc
    normalized = str(parsed)
    if normalized != value.lower():
        raise TruthValidationError(f"{name} must use canonical UUID form")
    return normalized


def _validate_operation_id(value: str | None) -> str:
    return _validate_audit_token("operation ID", value or str(uuid4()), 200)


def _audit_actor(actor_type: TruthActorType) -> AuditActorType:
    if actor_type == "tool":
        return "capability"
    if actor_type == "importer":
        return "system"
    return cast(AuditActorType, actor_type)


def _required_string(metadata: dict[str, object], key: str) -> str:
    value = metadata.get(key)
    if not isinstance(value, str):
        raise TruthValidationError(f"{key} is missing or invalid")
    return value


def _optional_string(metadata: dict[str, object], key: str) -> str | None:
    value = metadata.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise TruthValidationError(f"{key} is invalid")
    return value


__all__ = [
    "ClaimEvidenceTrustService",
    "ClaimInfo",
    "EvidenceInfo",
    "EvidenceType",
    "ForbiddenTruthMutationError",
    "InferenceInfo",
    "TrustAssessmentInfo",
    "TrustAssessorType",
    "TrustLevel",
    "TrustSubjectType",
    "TruthActorType",
    "TruthCorruptError",
    "TruthInfo",
    "TruthModelError",
    "TruthOriginType",
    "TruthRecordKind",
    "TruthReviewState",
    "TruthSource",
    "TruthValidationError",
    "_claim_from_record",
    "_evidence_from_record",
    "_inference_from_record",
    "_trust_assessment_from_record",
]
