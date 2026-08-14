"""Deterministic offline PAM v1.0 export for explicit confirmed-memory selections."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass

from doll.memory import (
    MAX_MEMORY_LIMIT,
    ConfirmedMemoryInfo,
    ConfirmedMemoryService,
    MemoryExportError,
)
from doll.pam_v1_import import PAM_V1_SCHEMA, PAM_V1_SCHEMA_VERSION, pam_content_hash
from doll.state import StateError
from doll.state_repository import StateRepository

PAM_V1_EXPORT_ADAPTER_ID = "pam-v1-confirmed-memory-export"
PAM_V1_EXPORT_ADAPTER_VERSION = "1.0.0"
PAM_V1_EXPORT_CUSTOM_TYPE = "doll_confirmed_memory"
PAM_V1_EXPORT_PLATFORM = "doll"
PAM_V1_EXPORT_ARTIFACT_KIND = "pam_memory_interchange"
PAM_V1_EXPORT_MAX_OWNER_ID_LENGTH = 200


class PamV1ExportError(MemoryExportError):
    """Raised when selected Doll memories cannot be exported safely as PAM v1.0."""


@dataclass(frozen=True, slots=True)
class PamV1ExportMemoryMapping:
    """Out-of-band mapping and loss evidence for one exported Doll memory."""

    doll_memory_id: str
    pam_memory_id: str
    pam_type: str
    pam_custom_type: str
    pam_content_hash: str
    represented_doll_fields: tuple[str, ...]
    omitted_doll_fields: tuple[str, ...]
    mapping_notes: tuple[str, ...]

    def canonical_summary(self) -> dict[str, object]:
        return {
            "doll_memory_id": self.doll_memory_id,
            "pam_memory_id": self.pam_memory_id,
            "pam_type": self.pam_type,
            "pam_custom_type": self.pam_custom_type,
            "pam_content_hash": self.pam_content_hash,
            "represented_doll_fields": list(self.represented_doll_fields),
            "omitted_doll_fields": list(self.omitted_doll_fields),
            "mapping_notes": list(self.mapping_notes),
        }


@dataclass(frozen=True, slots=True)
class PamV1ExportResult:
    """Deterministic PAM memory-store bytes plus explicit non-continuity metadata."""

    target_version: str
    adapter_id: str
    adapter_version: str
    owner_id: str
    source_state_revision: int
    memory_store_bytes: bytes
    memory_store_sha256: str
    memory_mappings: tuple[PamV1ExportMemoryMapping, ...]
    root_mapping_notes: tuple[str, ...]
    artifact_kind: str = PAM_V1_EXPORT_ARTIFACT_KIND
    complete_doll_continuity_export: bool = False

    def canonical_summary(self) -> dict[str, object]:
        return {
            "target_version": self.target_version,
            "adapter_id": self.adapter_id,
            "adapter_version": self.adapter_version,
            "owner_id": self.owner_id,
            "source_state_revision": self.source_state_revision,
            "memory_store_sha256": self.memory_store_sha256,
            "memory_store_size_bytes": len(self.memory_store_bytes),
            "memory_count": len(self.memory_mappings),
            "memory_mappings": [item.canonical_summary() for item in self.memory_mappings],
            "root_mapping_notes": list(self.root_mapping_notes),
            "artifact_kind": self.artifact_kind,
            "complete_doll_continuity_export": self.complete_doll_continuity_export,
        }


@dataclass(frozen=True, slots=True)
class PamV1MemoryExporter:
    """Export an explicit confirmed-memory selection without mutating Doll State."""

    repository: StateRepository

    def export_memory_store(
        self,
        *,
        owner_id: str,
        memory_ids: Sequence[str],
        target_version: str = PAM_V1_SCHEMA_VERSION,
    ) -> PamV1ExportResult:
        safe_owner_id = _validate_owner_id(owner_id)
        if target_version != PAM_V1_SCHEMA_VERSION:
            raise PamV1ExportError("PAM export target version is unsupported")
        selected_ids = _validate_memory_ids(memory_ids)
        source_state_revision = self.repository.status().state_revision
        service = ConfirmedMemoryService(self.repository)

        memories: list[ConfirmedMemoryInfo] = []
        for memory_id in selected_ids:
            try:
                memory = service.get(memory_id)
            except StateError as exc:
                raise PamV1ExportError("selected confirmed memory is unavailable") from exc
            _validate_exportable_memory(memory)
            memories.append(memory)

        if self.repository.status().state_revision != source_state_revision:
            raise PamV1ExportError("Doll State changed while PAM export was being prepared")

        pam_memories: list[dict[str, object]] = []
        mappings: list[PamV1ExportMemoryMapping] = []
        for memory in sorted(memories, key=lambda item: item.record_id):
            content_hash = pam_content_hash(memory.content)
            pam_memories.append(
                {
                    "id": memory.record_id,
                    "type": "custom",
                    "custom_type": PAM_V1_EXPORT_CUSTOM_TYPE,
                    "content": memory.content,
                    "content_hash": content_hash,
                    "temporal": {"created_at": memory.created_at},
                    "provenance": {"platform": PAM_V1_EXPORT_PLATFORM},
                }
            )
            mappings.append(_mapping_for(memory, content_hash))

        document: dict[str, object] = {
            "schema": PAM_V1_SCHEMA,
            "schema_version": PAM_V1_SCHEMA_VERSION,
            "owner": {"id": safe_owner_id},
            "memories": pam_memories,
        }
        output = (
            json.dumps(
                document,
                ensure_ascii=False,
                sort_keys=True,
                allow_nan=False,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")
        if self.repository.status().state_revision != source_state_revision:
            raise PamV1ExportError("Doll State changed while PAM export was being serialized")

        return PamV1ExportResult(
            target_version=PAM_V1_SCHEMA_VERSION,
            adapter_id=PAM_V1_EXPORT_ADAPTER_ID,
            adapter_version=PAM_V1_EXPORT_ADAPTER_VERSION,
            owner_id=safe_owner_id,
            source_state_revision=source_state_revision,
            memory_store_bytes=output,
            memory_store_sha256=hashlib.sha256(output).hexdigest(),
            memory_mappings=tuple(mappings),
            root_mapping_notes=(
                "caller-supplied-pam-owner-id",
                "explicit-confirmed-memory-selection-only",
                "pam-embeddings-omitted",
                "pam-integrity-and-signature-blocks-omitted",
                "pam-memory-interchange-not-doll-state-package",
            ),
        )


def _validate_owner_id(owner_id: str) -> str:
    if not isinstance(owner_id, str):
        raise PamV1ExportError("PAM owner id must be text")
    if not owner_id or owner_id != owner_id.strip():
        raise PamV1ExportError("PAM owner id must be non-empty canonical text")
    if len(owner_id) > PAM_V1_EXPORT_MAX_OWNER_ID_LENGTH:
        raise PamV1ExportError("PAM owner id exceeds the supported length")
    if any(ord(character) < 32 or ord(character) == 127 for character in owner_id):
        raise PamV1ExportError("PAM owner id contains control characters")
    return owner_id


def _validate_memory_ids(memory_ids: Sequence[str]) -> tuple[str, ...]:
    if isinstance(memory_ids, (str, bytes)) or not isinstance(memory_ids, Sequence):
        raise PamV1ExportError("PAM export memory ids must be an explicit sequence")
    if not memory_ids:
        raise PamV1ExportError("PAM export requires at least one confirmed memory id")
    if len(memory_ids) > MAX_MEMORY_LIMIT:
        raise PamV1ExportError("PAM export memory selection exceeds the supported limit")
    normalized: list[str] = []
    for memory_id in memory_ids:
        if not isinstance(memory_id, str) or not memory_id or memory_id != memory_id.strip():
            raise PamV1ExportError("PAM export memory ids must be non-empty canonical text")
        normalized.append(memory_id)
    if len(normalized) != len(set(normalized)):
        raise PamV1ExportError("PAM export memory ids contain duplicates")
    return tuple(normalized)


def _validate_exportable_memory(memory: ConfirmedMemoryInfo) -> None:
    if memory.status != "active":
        raise PamV1ExportError("archived confirmed memories are excluded from PAM export")
    if memory.sensitivity == "secret":
        raise PamV1ExportError("secret confirmed memories are excluded from PAM export")


def _mapping_for(
    memory: ConfirmedMemoryInfo,
    content_hash: str,
) -> PamV1ExportMemoryMapping:
    omitted = {
        "confirmation_state",
        "confidence",
        "provenance",
        "revision",
        "sensitivity",
        "source_type",
        "status",
        "subject",
        "updated_at",
    }
    optional_values = {
        "valid_from": memory.valid_from,
        "valid_until": memory.valid_until,
        "related_memory_ids": memory.related_memory_ids,
        "contradicts_memory_ids": memory.contradicts_memory_ids,
        "source_reference": memory.source_reference,
        "model_manifest_id": memory.model_manifest_id,
        "runtime_adapter_id": memory.runtime_adapter_id,
        "session_id": memory.session_id,
        "origin_operation_id": memory.origin_operation_id,
    }
    omitted.update(field for field, value in optional_values.items() if value)
    return PamV1ExportMemoryMapping(
        doll_memory_id=memory.record_id,
        pam_memory_id=memory.record_id,
        pam_type="custom",
        pam_custom_type=PAM_V1_EXPORT_CUSTOM_TYPE,
        pam_content_hash=content_hash,
        represented_doll_fields=("content", "created_at", "record_id"),
        omitted_doll_fields=tuple(sorted(omitted)),
        mapping_notes=(
            "doll-record-id-preserved-without-content-hash-identity",
            "pam-custom-type-does-not-reclassify-doll-memory-semantics",
            "doll-authority-and-lifecycle-semantics-reported-out-of-band",
        ),
    )
