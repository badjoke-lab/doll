"""Explicit user-reviewed publication for staged PAM v1.0 memory candidates."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Literal, cast

from doll.memory import (
    ConfirmedMemoryInfo,
    ConfirmedMemoryService,
    MemoryMutationActor,
    MemoryValidationError,
    _validated_memory_values,
)
from doll.pam_v1_import import (
    PAM_V1_ADAPTER_ID,
    PAM_V1_ADAPTER_VERSION,
    PamV1ImportStageResult,
    PamV1MemoryMapping,
)
from doll.state import RecordSensitivity
from doll.state_repository import StateRepository

PamV1PublicationDecision = Literal["approve", "reject"]
PamV1PublicationAction = Literal["create", "reuse", "reject"]

PAM_V1_PUBLICATION_POLICY_ID = "pam-v1-reviewed-memory-publication"
PAM_V1_PUBLICATION_POLICY_VERSION = "1.0.0"
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class PamV1PublicationError(RuntimeError):
    """Raised when a PAM candidate cannot be reviewed or published safely."""


class ForbiddenPamV1PublicationError(PamV1PublicationError):
    """Raised when a non-user actor attempts to approve or reject a PAM candidate."""


@dataclass(frozen=True, slots=True)
class PamV1PublicationMapping:
    """Explicit mapping and non-mapping report for one PAM memory candidate."""

    source_memory_id: str
    pam_type: str
    source_content_hash: str
    source_reference: str
    local_subject: str
    local_content: str
    local_source_type: Literal["approved_import"]
    local_sensitivity: RecordSensitivity
    content_transformed: bool
    preserved_non_authoritative_fields: tuple[str, ...]
    mapping_notes: tuple[str, ...]

    def canonical_summary(self) -> dict[str, object]:
        return {
            "source_memory_id": self.source_memory_id,
            "pam_type": self.pam_type,
            "source_content_hash": self.source_content_hash,
            "source_reference": self.source_reference,
            "local_subject": self.local_subject,
            "local_content": self.local_content,
            "local_source_type": self.local_source_type,
            "local_sensitivity": self.local_sensitivity,
            "content_transformed": self.content_transformed,
            "preserved_non_authoritative_fields": list(self.preserved_non_authoritative_fields),
            "mapping_notes": list(self.mapping_notes),
            "pam_validity_applied": False,
            "pam_confidence_applied": False,
            "pam_access_applied": False,
            "pam_relations_applied": False,
            "pam_instruction_authority_applied": False,
            "pam_embedding_applied": False,
        }


@dataclass(frozen=True, slots=True)
class PamV1PublicationPreview:
    """Immutable read-only plan for one explicit candidate decision."""

    source_sha256: str
    source_environment_id: str
    source_memory_id: str
    source_state_revision: int
    decision: PamV1PublicationDecision
    action: PamV1PublicationAction
    existing_memory_id: str | None
    mapping: PamV1PublicationMapping
    policy_id: str
    policy_version: str
    plan_hash: str

    def canonical_summary(self, *, include_plan_hash: bool = True) -> dict[str, object]:
        payload: dict[str, object] = {
            "source_sha256": self.source_sha256,
            "source_environment_id": self.source_environment_id,
            "source_memory_id": self.source_memory_id,
            "source_state_revision": self.source_state_revision,
            "decision": self.decision,
            "action": self.action,
            "existing_memory_id": self.existing_memory_id,
            "mapping": self.mapping.canonical_summary(),
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "automatic_approval": False,
            "review_required": True,
        }
        if include_plan_hash:
            payload["plan_hash"] = self.plan_hash
        return payload


@dataclass(frozen=True, slots=True)
class PamV1PublicationResult:
    """Result of publishing or rejecting one exact reviewed candidate plan."""

    decision: PamV1PublicationDecision
    action: PamV1PublicationAction
    source_memory_id: str
    memory_id: str | None
    memory_revision: int | None
    memory_status: str | None
    state_revision: int


@dataclass(slots=True)
class PamV1MemoryPublisher:
    """Preview and publish exactly one staged PAM memory under explicit user control."""

    repository: StateRepository

    def preview(
        self,
        stage_result: PamV1ImportStageResult,
        source_memory_id: str,
        *,
        decision: PamV1PublicationDecision,
    ) -> PamV1PublicationPreview:
        if decision not in {"approve", "reject"}:
            raise PamV1PublicationError("PAM publication decision must be approve or reject")
        source_mapping, pam_memory = _candidate(stage_result, source_memory_id)
        source_environment_id = stage_result.generic_stage.import_batch.source_environment_id
        source_reference = _source_reference(
            source_environment_id,
            source_memory_id,
            stage_result.source_sha256,
        )
        local_subject = _local_subject(source_mapping.pam_type)
        source_content = pam_memory.get("content")
        if not isinstance(source_content, str):
            raise PamV1PublicationError("staged PAM memory content is invalid")
        try:
            validated = _validated_memory_values(
                self.repository,
                subject=local_subject,
                content=source_content,
                source_type="approved_import",
                valid_from=None,
                valid_until=None,
                confidence=1.0,
                related_memory_ids=(),
                contradicts_memory_ids=(),
                source_reference=source_reference,
                model_manifest_id=None,
                runtime_adapter_id=None,
                session_id=None,
                origin_operation_id=None,
                self_id=None,
            )
        except MemoryValidationError as exc:
            raise PamV1PublicationError(
                "PAM candidate cannot be represented as confirmed Doll memory"
            ) from exc
        local_content = cast(str, validated["content"])
        mapping_notes = _mapping_notes(
            source_mapping,
            pam_memory,
            content_transformed=local_content != source_content,
        )
        publication_mapping = PamV1PublicationMapping(
            source_memory_id=source_memory_id,
            pam_type=source_mapping.pam_type,
            source_content_hash=source_mapping.source_content_hash,
            source_reference=source_reference,
            local_subject=cast(str, validated["subject"]),
            local_content=local_content,
            local_source_type="approved_import",
            local_sensitivity="personal",
            content_transformed=local_content != source_content,
            preserved_non_authoritative_fields=source_mapping.preserved_non_authoritative_fields,
            mapping_notes=mapping_notes,
        )
        existing = _existing_lineage_memory(
            self.repository,
            source_environment_id,
            source_memory_id,
        )
        if decision == "reject":
            action: PamV1PublicationAction = "reject"
            existing_id = existing.record_id if existing is not None else None
        elif existing is None:
            action = "create"
            existing_id = None
        else:
            _validate_existing(existing, publication_mapping)
            action = "reuse"
            existing_id = existing.record_id

        source_revision = self.repository.status().state_revision
        provisional = PamV1PublicationPreview(
            source_sha256=stage_result.source_sha256,
            source_environment_id=source_environment_id,
            source_memory_id=source_memory_id,
            source_state_revision=source_revision,
            decision=decision,
            action=action,
            existing_memory_id=existing_id,
            mapping=publication_mapping,
            policy_id=PAM_V1_PUBLICATION_POLICY_ID,
            policy_version=PAM_V1_PUBLICATION_POLICY_VERSION,
            plan_hash="0" * 64,
        )
        plan_hash = _hash_json(provisional.canonical_summary(include_plan_hash=False))
        return PamV1PublicationPreview(
            source_sha256=provisional.source_sha256,
            source_environment_id=provisional.source_environment_id,
            source_memory_id=provisional.source_memory_id,
            source_state_revision=provisional.source_state_revision,
            decision=provisional.decision,
            action=provisional.action,
            existing_memory_id=provisional.existing_memory_id,
            mapping=provisional.mapping,
            policy_id=provisional.policy_id,
            policy_version=provisional.policy_version,
            plan_hash=plan_hash,
        )

    def publish(
        self,
        preview: PamV1PublicationPreview,
        stage_result: PamV1ImportStageResult,
        *,
        approved_plan_hash: str,
        actor_type: MemoryMutationActor,
        operation_id: str | None = None,
    ) -> PamV1PublicationResult:
        if actor_type != "user":
            raise ForbiddenPamV1PublicationError(
                "PAM candidate publication requires an explicit user-controlled actor"
            )
        if not _SHA256_PATTERN.fullmatch(approved_plan_hash):
            raise PamV1PublicationError("approved PAM publication plan hash is invalid")
        if approved_plan_hash != preview.plan_hash:
            raise PamV1PublicationError("approved PAM publication plan hash does not match")
        current = self.preview(
            stage_result,
            preview.source_memory_id,
            decision=preview.decision,
        )
        if current != preview:
            raise PamV1PublicationError("PAM publication preview is stale")

        if preview.decision == "reject":
            return PamV1PublicationResult(
                decision="reject",
                action="reject",
                source_memory_id=preview.source_memory_id,
                memory_id=None,
                memory_revision=None,
                memory_status=None,
                state_revision=self.repository.status().state_revision,
            )
        if preview.action == "reuse":
            if preview.existing_memory_id is None:  # pragma: no cover - dataclass plan invariant.
                raise PamV1PublicationError("reused PAM memory identifier is missing")
            existing = ConfirmedMemoryService(self.repository).get(preview.existing_memory_id)
            _validate_existing(existing, preview.mapping)
            return _result("reuse", preview.source_memory_id, existing, self.repository)
        if preview.action != "create":
            raise PamV1PublicationError("approved PAM publication action is invalid")
        if self.repository.read_only:
            raise PamV1PublicationError("PAM approval requires writable Doll State")

        memory = ConfirmedMemoryService(self.repository).create(
            subject=preview.mapping.local_subject,
            content=preview.mapping.local_content,
            source_type="approved_import",
            valid_from=None,
            valid_until=None,
            confidence=1.0,
            related_memory_ids=(),
            contradicts_memory_ids=(),
            source_reference=preview.mapping.source_reference,
            model_manifest_id=None,
            runtime_adapter_id=None,
            session_id=None,
            origin_operation_id=None,
            operation_id=operation_id,
            sensitivity="personal",
            actor_type="user",
        )
        return _result("create", preview.source_memory_id, memory, self.repository)


def _candidate(
    stage_result: PamV1ImportStageResult,
    source_memory_id: str,
) -> tuple[PamV1MemoryMapping, dict[str, object]]:
    if not isinstance(stage_result, PamV1ImportStageResult):
        raise PamV1PublicationError("PAM stage result is invalid")
    if not isinstance(source_memory_id, str) or not source_memory_id:
        raise PamV1PublicationError("PAM source memory id must be non-empty text")
    if stage_result.adapter_id != PAM_V1_ADAPTER_ID:
        raise PamV1PublicationError("PAM stage adapter id is unsupported")
    if stage_result.adapter_version != PAM_V1_ADAPTER_VERSION:
        raise PamV1PublicationError("PAM stage adapter version is unsupported")
    if not _SHA256_PATTERN.fullmatch(stage_result.source_sha256):
        raise PamV1PublicationError("PAM stage source hash is invalid")

    staged_matches = tuple(
        item
        for item in stage_result.generic_stage.staged_objects
        if item.source_object_id == source_memory_id
    )
    mapping_matches = tuple(
        item for item in stage_result.memory_mappings if item.source_memory_id == source_memory_id
    )
    if len(staged_matches) != 1 or len(mapping_matches) != 1:
        raise PamV1PublicationError("PAM source memory candidate is missing or ambiguous")
    staged = staged_matches[0]
    source_mapping = mapping_matches[0]
    if staged.source_type != "memory" or staged.authority_class != "external_data":
        raise PamV1PublicationError("PAM staged candidate authority boundary is invalid")
    if staged.source_hash != source_mapping.generic_source_hash:
        raise PamV1PublicationError("PAM staged candidate hash mapping is inconsistent")
    try:
        payload = json.loads(staged.payload_json)
    except json.JSONDecodeError as exc:  # pragma: no cover - GenericImportStager invariant.
        raise PamV1PublicationError("PAM staged candidate payload is invalid") from exc
    if not isinstance(payload, dict):
        raise PamV1PublicationError("PAM staged candidate payload is not an object")
    if (
        payload.get("authority_class") != "external_data"
        or payload.get("review_required") is not True
    ):
        raise PamV1PublicationError("PAM staged candidate review boundary is invalid")
    pam_memory = payload.get("pam_memory")
    if not isinstance(pam_memory, dict):
        raise PamV1PublicationError("PAM staged memory payload is missing")
    if pam_memory.get("id") != source_memory_id:
        raise PamV1PublicationError("PAM staged memory identity is inconsistent")
    if pam_memory.get("content_hash") != source_mapping.source_content_hash:
        raise PamV1PublicationError("PAM staged content hash is inconsistent")
    return source_mapping, cast(dict[str, object], pam_memory)


def _local_subject(pam_type: str) -> str:
    if not isinstance(pam_type, str) or not pam_type:
        raise PamV1PublicationError("PAM memory type is invalid")
    return f"Imported PAM {pam_type} memory"


def _source_reference(
    source_environment_id: str,
    source_memory_id: str,
    source_sha256: str,
) -> str:
    identity_hash = hashlib.sha256(source_memory_id.encode("utf-8")).hexdigest()
    reference = f"pam-v1:{source_environment_id}:{identity_hash}:{source_sha256}"
    if len(reference) > 200:
        raise PamV1PublicationError("PAM source reference exceeds the memory identifier limit")
    return reference


def _lineage_prefix(source_environment_id: str, source_memory_id: str) -> str:
    identity_hash = hashlib.sha256(source_memory_id.encode("utf-8")).hexdigest()
    return f"pam-v1:{source_environment_id}:{identity_hash}:"


def _existing_lineage_memory(
    repository: StateRepository,
    source_environment_id: str,
    source_memory_id: str,
) -> ConfirmedMemoryInfo | None:
    prefix = _lineage_prefix(source_environment_id, source_memory_id)
    try:
        rows = repository.connection.execute(
            """
            SELECT id
            FROM records
            WHERE record_type = 'memory' AND instr(metadata_json, ?) > 0
            ORDER BY id
            LIMIT 3
            """,
            (prefix,),
        ).fetchall()
    except Exception as exc:  # pragma: no cover - repository corruption handled below.
        raise PamV1PublicationError("PAM source lineage lookup failed") from exc
    service = ConfirmedMemoryService(repository)
    matches = tuple(
        memory
        for memory in (service.get(cast(str, row[0])) for row in rows)
        if memory.source_reference is not None and memory.source_reference.startswith(prefix)
    )
    if len(matches) > 1:
        raise PamV1PublicationError("multiple confirmed memories share one PAM source identity")
    return matches[0] if matches else None


def _validate_existing(
    memory: ConfirmedMemoryInfo,
    mapping: PamV1PublicationMapping,
) -> None:
    if memory.source_reference != mapping.source_reference:
        raise PamV1PublicationError(
            "PAM source identity already exists from a different source package"
        )
    if (
        memory.subject != mapping.local_subject
        or memory.content != mapping.local_content
        or memory.source_type != "approved_import"
        or memory.valid_from is not None
        or memory.valid_until is not None
        or memory.confidence != 1.0
        or memory.related_memory_ids
        or memory.contradicts_memory_ids
        or memory.sensitivity != mapping.local_sensitivity
        or memory.provenance != "imported"
    ):
        raise PamV1PublicationError(
            "existing PAM-approved memory no longer matches the reviewed mapping"
        )


def _mapping_notes(
    source_mapping: PamV1MemoryMapping,
    pam_memory: dict[str, object],
    *,
    content_transformed: bool,
) -> tuple[str, ...]:
    notes = set(source_mapping.mapping_notes)
    notes.update(
        {
            "pam-content-requires-explicit-user-approval",
            "pam-lifecycle-not-applied-to-doll-memory",
            "pam-confidence-not-applied-to-doll-memory",
            "pam-access-not-applied-to-doll-permission",
            "pam-relations-not-applied-to-doll-memory-links",
            "pam-embedding-reference-not-applied-to-doll-recall",
            "pam-source-reference-binds-source-package-and-source-identity",
        }
    )
    if pam_memory.get("type") == "instruction":
        notes.add("pam-instruction-type-does-not-create-doll-instruction-authority")
    if content_transformed:
        notes.add("doll-confirmed-memory-text-normalization-applied")
    return tuple(sorted(notes))


def _result(
    action: Literal["create", "reuse"],
    source_memory_id: str,
    memory: ConfirmedMemoryInfo,
    repository: StateRepository,
) -> PamV1PublicationResult:
    return PamV1PublicationResult(
        decision="approve",
        action=action,
        source_memory_id=source_memory_id,
        memory_id=memory.record_id,
        memory_revision=memory.revision,
        memory_status=memory.status,
        state_revision=repository.status().state_revision,
    )


def _hash_json(payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
