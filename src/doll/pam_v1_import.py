"""Offline PAM v1.0 memory-store staging through the generic import boundary."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from typing import cast

from doll.generic_import import GenericImportStageResult, GenericImportStager
from doll.portability import (
    AdapterResourceLimits,
    PortabilityContractError,
    SourceAdapterContract,
    SourceEnvironmentRecord,
)

PAM_V1_SCHEMA = "portable-ai-memory"
PAM_V1_SCHEMA_VERSION = "1.0"
PAM_V1_ADAPTER_ID = "pam-v1-memory-store"
PAM_V1_ADAPTER_VERSION = "1.0.0"
PAM_V1_ENVIRONMENT_CLASS = "pam-memory-store"
PAM_V1_SOURCE_TYPE = "memory"
PAM_V1_MAX_INPUT_BYTES = 16 * 1024 * 1024
PAM_V1_MAX_MEMORIES = 50_000
PAM_V1_MAX_NESTING_DEPTH = 48

_PAM_TYPES = frozenset(
    {
        "fact",
        "preference",
        "skill",
        "context",
        "relationship",
        "goal",
        "instruction",
        "identity",
        "environment",
        "project",
        "custom",
    }
)
_PAM_STATUSES = frozenset({"active", "superseded", "deprecated", "retracted", "archived"})
_PAM_RELATION_TYPES = frozenset(
    {"supports", "contradicts", "extends", "supersedes", "related_to", "derived_from"}
)
_EXTRACTION_METHODS = frozenset(
    {"llm_inference", "explicit_user_input", "api_export", "browser_extraction", "manual"}
)
_PLATFORM_PATTERN = re.compile(r"^[a-z0-9_-]{2,32}$")
_CONTENT_HASH_PATTERN = re.compile(r"^sha256:[a-f0-9]{64}$")
_TAG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_MEMORY_KNOWN_KEYS = frozenset(
    {
        "id",
        "type",
        "content",
        "content_hash",
        "temporal",
        "provenance",
        "custom_type",
        "status",
        "summary",
        "tags",
        "confidence",
        "access",
        "embedding_ref",
        "metadata",
    }
)


class PamV1ImportError(PortabilityContractError):
    """Raised when PAM v1.0 bytes cannot safely produce a staged result."""


@dataclass(frozen=True, slots=True)
class PamV1MemoryMapping:
    """Non-authoritative mapping evidence for one PAM memory object."""

    source_memory_id: str
    pam_type: str
    source_content_hash: str
    generic_source_hash: str
    relation_ids: tuple[str, ...]
    preserved_non_authoritative_fields: tuple[str, ...]
    mapping_notes: tuple[str, ...]
    review_required: bool = True
    authority_class: str = "external_data"

    def canonical_metadata(self) -> dict[str, object]:
        return {
            "source_memory_id": self.source_memory_id,
            "pam_type": self.pam_type,
            "source_content_hash": self.source_content_hash,
            "generic_source_hash": self.generic_source_hash,
            "relation_ids": list(self.relation_ids),
            "preserved_non_authoritative_fields": list(
                self.preserved_non_authoritative_fields
            ),
            "mapping_notes": list(self.mapping_notes),
            "review_required": self.review_required,
            "authority_class": self.authority_class,
        }


@dataclass(frozen=True, slots=True)
class PamV1ImportStageResult:
    """Exact PAM source evidence plus the generic non-authoritative staging result."""

    source_sha256: str
    source_size_bytes: int
    schema_version: str
    adapter_id: str
    adapter_version: str
    generic_projection_sha256: str
    generic_stage: GenericImportStageResult
    memory_mappings: tuple[PamV1MemoryMapping, ...]
    root_mapping_notes: tuple[str, ...]
    verified_content_hash_count: int

    def __post_init__(self) -> None:
        if not _SHA256_PATTERN.fullmatch(self.source_sha256):
            raise PamV1ImportError("PAM source SHA-256 is invalid")
        if not _SHA256_PATTERN.fullmatch(self.generic_projection_sha256):
            raise PamV1ImportError("generic projection SHA-256 is invalid")
        if self.source_size_bytes < 1:
            raise PamV1ImportError("PAM source size is invalid")
        if self.schema_version != PAM_V1_SCHEMA_VERSION:
            raise PamV1ImportError("PAM schema version is invalid")
        if self.adapter_id != PAM_V1_ADAPTER_ID:
            raise PamV1ImportError("PAM adapter id is invalid")
        if self.adapter_version != PAM_V1_ADAPTER_VERSION:
            raise PamV1ImportError("PAM adapter version is invalid")
        if self.verified_content_hash_count != len(self.memory_mappings):
            raise PamV1ImportError("PAM verified content-hash count is inconsistent")

    def canonical_summary(self) -> dict[str, object]:
        return {
            "source_sha256": self.source_sha256,
            "source_size_bytes": self.source_size_bytes,
            "schema_version": self.schema_version,
            "adapter_id": self.adapter_id,
            "adapter_version": self.adapter_version,
            "generic_projection_sha256": self.generic_projection_sha256,
            "generic_stage": self.generic_stage.canonical_summary(),
            "memory_mappings": [item.canonical_metadata() for item in self.memory_mappings],
            "root_mapping_notes": list(self.root_mapping_notes),
            "verified_content_hash_count": self.verified_content_hash_count,
            "authoritative_memory_created": False,
            "permission_authority_created": False,
        }


@dataclass(frozen=True, slots=True)
class PamV1ImportStager:
    """Validate PAM v1.0 bytes and project memories into GenericImportStager."""

    source_environment: SourceEnvironmentRecord
    max_input_bytes: int = PAM_V1_MAX_INPUT_BYTES
    max_memories: int = PAM_V1_MAX_MEMORIES
    max_nesting_depth: int = PAM_V1_MAX_NESTING_DEPTH

    def __post_init__(self) -> None:
        if self.source_environment.environment_class != PAM_V1_ENVIRONMENT_CLASS:
            raise PamV1ImportError("source environment is not a PAM memory store")
        if self.source_environment.export_format not in {None, "json"}:
            raise PamV1ImportError("PAM source environment export format must be JSON")
        if self.source_environment.export_version not in {None, PAM_V1_SCHEMA_VERSION}:
            raise PamV1ImportError("PAM source environment version is unsupported")
        for name, value, maximum in (
            ("input byte limit", self.max_input_bytes, PAM_V1_MAX_INPUT_BYTES),
            ("memory count limit", self.max_memories, PAM_V1_MAX_MEMORIES),
            ("nesting depth limit", self.max_nesting_depth, PAM_V1_MAX_NESTING_DEPTH),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
                raise PamV1ImportError(f"{name} is outside the supported range")

    @property
    def adapter(self) -> SourceAdapterContract:
        return SourceAdapterContract(
            adapter_id=PAM_V1_ADAPTER_ID,
            adapter_version=PAM_V1_ADAPTER_VERSION,
            source_environment_class=PAM_V1_ENVIRONMENT_CLASS,
            supported_source_versions=(PAM_V1_SCHEMA_VERSION,),
            supported_event_types=(PAM_V1_SOURCE_TYPE,),
            attachment_behavior="unsupported",
            branch_behavior="unsupported",
            resource_limits=AdapterResourceLimits(
                max_input_bytes=self.max_input_bytes,
                max_object_count=self.max_memories,
                max_attachment_bytes=1,
                max_nesting_depth=self.max_nesting_depth,
            ),
            network_behavior="none",
            loss_categories=(
                "pam-lifecycle-preserved",
                "pam-access-preserved",
                "pam-relation-preserved",
                "pam-conversation-index-preserved",
                "pam-integrity-preserved-unverified",
                "pam-signature-preserved-unverified",
                "pam-embedding-reference-preserved",
            ),
        )

    def stage(
        self,
        source_bytes: bytes,
        *,
        import_batch_id: str,
        started_at: str,
    ) -> PamV1ImportStageResult:
        """Return deterministic external-data candidates without writing Doll State."""

        if not isinstance(source_bytes, bytes):
            raise PamV1ImportError("PAM source must be bytes")
        if not source_bytes:
            raise PamV1ImportError("PAM source must not be empty")
        if len(source_bytes) > self.max_input_bytes:
            raise PamV1ImportError("PAM source exceeds the accepted byte limit")
        try:
            source_text = source_bytes.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise PamV1ImportError("PAM source is not valid UTF-8") from exc
        try:
            raw = json.loads(source_text)
        except (json.JSONDecodeError, RecursionError) as exc:
            raise PamV1ImportError("PAM source is not valid bounded JSON") from exc
        if _json_depth(raw) > self.max_nesting_depth:
            raise PamV1ImportError("PAM source nesting exceeds the accepted limit")
        document = _require_object(raw, "PAM root")
        memories = _validate_root(document, max_memories=self.max_memories)
        memory_ids = tuple(cast(str, item["id"]) for item in memories)
        relations_by_memory = _validate_relations(document.get("relations"), memory_ids)
        _validate_root_optional_blocks(document, len(memories))

        generic_objects: list[dict[str, object]] = []
        mapping_inputs: list[tuple[str, str, tuple[str, ...], tuple[str, ...], tuple[str, ...]]] = []
        for memory in memories:
            memory_id = cast(str, memory["id"])
            pam_type = cast(str, memory["type"])
            _validate_memory(memory)
            relations = relations_by_memory.get(memory_id, ())
            payload = _memory_payload(memory, relations)
            generic_objects.append(
                {
                    "source_object_id": memory_id,
                    "source_type": PAM_V1_SOURCE_TYPE,
                    "parent_source_object_ids": [],
                    "payload": payload,
                }
            )
            preserved_fields, notes = _memory_mapping_notes(memory, relations)
            mapping_inputs.append(
                (
                    memory_id,
                    pam_type,
                    tuple(item["id"] for item in relations),
                    preserved_fields,
                    notes,
                )
            )

        projection_bytes = _generic_projection_bytes(
            self.source_environment.environment_id,
            generic_objects,
        )
        generic_stage = GenericImportStager(self.adapter, self.source_environment).stage(
            projection_bytes,
            source_format="json",
            import_batch_id=import_batch_id,
            started_at=started_at,
        )
        staged_by_id = {item.source_object_id: item for item in generic_stage.staged_objects}
        if len(staged_by_id) != len(memories):
            raise PamV1ImportError("generic staging did not preserve all PAM memory candidates")

        mappings = tuple(
            PamV1MemoryMapping(
                source_memory_id=memory_id,
                pam_type=pam_type,
                source_content_hash=cast(
                    str,
                    next(item for item in memories if item["id"] == memory_id)["content_hash"],
                ),
                generic_source_hash=staged_by_id[memory_id].source_hash,
                relation_ids=relation_ids,
                preserved_non_authoritative_fields=preserved_fields,
                mapping_notes=notes,
            )
            for memory_id, pam_type, relation_ids, preserved_fields, notes in sorted(
                mapping_inputs,
                key=lambda item: item[0],
            )
        )
        return PamV1ImportStageResult(
            source_sha256=hashlib.sha256(source_bytes).hexdigest(),
            source_size_bytes=len(source_bytes),
            schema_version=PAM_V1_SCHEMA_VERSION,
            adapter_id=PAM_V1_ADAPTER_ID,
            adapter_version=PAM_V1_ADAPTER_VERSION,
            generic_projection_sha256=hashlib.sha256(projection_bytes).hexdigest(),
            generic_stage=generic_stage,
            memory_mappings=mappings,
            root_mapping_notes=_root_mapping_notes(document),
            verified_content_hash_count=len(memories),
        )


def pam_content_hash(content: str) -> str:
    """Compute PAM v1.0 content_hash exactly as the published normalization specifies."""

    if not isinstance(content, str):
        raise PamV1ImportError("PAM memory content must be text")
    normalized = content.strip().lower()
    normalized = unicodedata.normalize("NFC", normalized)
    normalized = " ".join(normalized.split())
    return "sha256:" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _validate_root(
    document: dict[str, object],
    *,
    max_memories: int,
) -> tuple[dict[str, object], ...]:
    if document.get("schema") != PAM_V1_SCHEMA:
        raise PamV1ImportError("PAM schema identifier is unsupported")
    if document.get("schema_version") != PAM_V1_SCHEMA_VERSION:
        raise PamV1ImportError("PAM schema version is unsupported")
    owner = _require_object(document.get("owner"), "PAM owner")
    _require_nonempty_text(owner.get("id"), "PAM owner id")
    raw_memories = document.get("memories")
    if not isinstance(raw_memories, list):
        raise PamV1ImportError("PAM memories must be an array")
    if len(raw_memories) > max_memories:
        raise PamV1ImportError("PAM memory count exceeds the accepted limit")
    memories = tuple(_require_object(item, "PAM memory") for item in raw_memories)
    ids = [_require_nonempty_text(item.get("id"), "PAM memory id") for item in memories]
    if len(ids) != len(set(ids)):
        raise PamV1ImportError("PAM memory ids contain duplicates")
    return memories


def _validate_memory(memory: dict[str, object]) -> None:
    memory_id = _require_nonempty_text(memory.get("id"), "PAM memory id")
    pam_type = _require_nonempty_text(memory.get("type"), f"PAM memory {memory_id} type")
    if pam_type not in _PAM_TYPES:
        raise PamV1ImportError(f"PAM memory {memory_id} type is unsupported")
    custom_type = memory.get("custom_type")
    if pam_type == "custom":
        _require_nonempty_text(custom_type, f"PAM memory {memory_id} custom_type")
    elif custom_type is not None:
        raise PamV1ImportError(f"PAM memory {memory_id} custom_type must be null")

    content = memory.get("content")
    if not isinstance(content, str):
        raise PamV1ImportError(f"PAM memory {memory_id} content must be text")
    content_hash = _require_nonempty_text(
        memory.get("content_hash"),
        f"PAM memory {memory_id} content_hash",
    )
    if not _CONTENT_HASH_PATTERN.fullmatch(content_hash):
        raise PamV1ImportError(f"PAM memory {memory_id} content_hash format is invalid")
    if pam_content_hash(content) != content_hash:
        raise PamV1ImportError(f"PAM memory {memory_id} content_hash does not match content")

    temporal = _require_object(memory.get("temporal"), f"PAM memory {memory_id} temporal")
    _validate_timestamp(temporal.get("created_at"), f"PAM memory {memory_id} created_at")
    for field in ("updated_at", "valid_from", "valid_until"):
        if temporal.get(field) is not None:
            _validate_timestamp(temporal[field], f"PAM memory {memory_id} {field}")
    if temporal.get("superseded_by") is not None:
        _require_nonempty_text(
            temporal["superseded_by"],
            f"PAM memory {memory_id} superseded_by",
        )

    provenance = _require_object(
        memory.get("provenance"),
        f"PAM memory {memory_id} provenance",
    )
    platform = _require_nonempty_text(
        provenance.get("platform"),
        f"PAM memory {memory_id} provenance platform",
    )
    if not _PLATFORM_PATTERN.fullmatch(platform):
        raise PamV1ImportError(f"PAM memory {memory_id} provenance platform is invalid")
    extraction_method = provenance.get("extraction_method")
    if extraction_method is not None and extraction_method not in _EXTRACTION_METHODS:
        raise PamV1ImportError(f"PAM memory {memory_id} extraction method is invalid")
    for field in ("extracted_at",):
        if provenance.get(field) is not None:
            _validate_timestamp(provenance[field], f"PAM memory {memory_id} {field}")
    for field in ("platform_user_id", "conversation_ref", "message_ref", "extractor"):
        value = provenance.get(field)
        if value is not None and not isinstance(value, str):
            raise PamV1ImportError(f"PAM memory {memory_id} provenance {field} is invalid")

    status = memory.get("status", "active")
    if status not in _PAM_STATUSES:
        raise PamV1ImportError(f"PAM memory {memory_id} status is invalid")
    summary = memory.get("summary")
    if summary is not None and not isinstance(summary, str):
        raise PamV1ImportError(f"PAM memory {memory_id} summary is invalid")
    tags = memory.get("tags", [])
    if not isinstance(tags, list) or any(
        not isinstance(item, str) or not _TAG_PATTERN.fullmatch(item) for item in tags
    ):
        raise PamV1ImportError(f"PAM memory {memory_id} tags are invalid")
    for field in ("confidence", "access", "metadata"):
        value = memory.get(field)
        if value is not None and not isinstance(value, dict):
            raise PamV1ImportError(f"PAM memory {memory_id} {field} must be an object")
    embedding_ref = memory.get("embedding_ref")
    if embedding_ref is not None and not isinstance(embedding_ref, str):
        raise PamV1ImportError(f"PAM memory {memory_id} embedding_ref is invalid")


def _validate_relations(
    raw_relations: object,
    memory_ids: tuple[str, ...],
) -> dict[str, tuple[dict[str, object], ...]]:
    if raw_relations is None:
        return {}
    if not isinstance(raw_relations, list):
        raise PamV1ImportError("PAM relations must be an array")
    known_ids = set(memory_ids)
    relation_ids: set[str] = set()
    related: dict[str, list[dict[str, object]]] = {}
    for raw in raw_relations:
        relation = _require_object(raw, "PAM relation")
        relation_id = _require_nonempty_text(relation.get("id"), "PAM relation id")
        if relation_id in relation_ids:
            raise PamV1ImportError("PAM relation ids contain duplicates")
        relation_ids.add(relation_id)
        source_id = _require_nonempty_text(relation.get("from"), "PAM relation from")
        target_id = _require_nonempty_text(relation.get("to"), "PAM relation to")
        if source_id not in known_ids or target_id not in known_ids:
            raise PamV1ImportError("PAM relation references an unknown memory id")
        relation_type = _require_nonempty_text(relation.get("type"), "PAM relation type")
        if relation_type not in _PAM_RELATION_TYPES:
            raise PamV1ImportError("PAM relation type is invalid")
        _validate_timestamp(relation.get("created_at"), "PAM relation created_at")
        confidence = relation.get("confidence")
        if confidence is not None and (
            isinstance(confidence, bool)
            or not isinstance(confidence, (int, float))
            or not 0 <= float(confidence) <= 1
        ):
            raise PamV1ImportError("PAM relation confidence is invalid")
        related.setdefault(source_id, []).append(relation)
        if target_id != source_id:
            related.setdefault(target_id, []).append(relation)
    return {
        memory_id: tuple(sorted(items, key=lambda item: cast(str, item["id"])))
        for memory_id, items in related.items()
    }


def _validate_root_optional_blocks(document: dict[str, object], memory_count: int) -> None:
    export_type = document.get("export_type", "full")
    if export_type not in {"full", "incremental"}:
        raise PamV1ImportError("PAM export_type is invalid")
    conversations = document.get("conversations_index")
    if conversations is not None and not isinstance(conversations, list):
        raise PamV1ImportError("PAM conversations_index must be an array")
    integrity = document.get("integrity")
    if integrity is not None:
        block = _require_object(integrity, "PAM integrity")
        checksum = _require_nonempty_text(block.get("checksum"), "PAM integrity checksum")
        if not _CONTENT_HASH_PATTERN.fullmatch(checksum):
            raise PamV1ImportError("PAM integrity checksum format is invalid")
        total = block.get("total_memories")
        if isinstance(total, bool) or not isinstance(total, int) or total != memory_count:
            raise PamV1ImportError("PAM integrity total_memories is inconsistent")
        canonicalization = block.get("canonicalization", "RFC8785")
        if canonicalization != "RFC8785":
            raise PamV1ImportError("PAM integrity canonicalization is unsupported")
    signature = document.get("signature")
    if signature is not None and not isinstance(signature, dict):
        raise PamV1ImportError("PAM signature must be an object or null")


def _memory_payload(
    memory: dict[str, object],
    relations: tuple[dict[str, object], ...],
) -> dict[str, object]:
    return {
        "pam_memory": memory,
        "pam_relations": list(relations),
        "pam_contract": PAM_V1_SCHEMA_VERSION,
        "authority_class": "external_data",
        "review_required": True,
    }


def _memory_mapping_notes(
    memory: dict[str, object],
    relations: tuple[dict[str, object], ...],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    preserved: set[str] = set()
    notes: set[str] = {"pam-content-hash-verified", "confirmed-memory-not-created"}
    status = memory.get("status", "active")
    temporal = cast(dict[str, object], memory["temporal"])
    if status != "active" or any(
        temporal.get(field) is not None for field in ("valid_from", "valid_until", "superseded_by")
    ):
        preserved.add("lifecycle")
        notes.add("pam-lifecycle-remains-source-metadata")
    if memory.get("access") is not None:
        preserved.add("access")
        notes.add("pam-access-does-not-create-doll-permission")
    if memory.get("confidence") is not None:
        preserved.add("confidence")
        notes.add("pam-confidence-does-not-control-doll-memory-truth")
    if memory.get("embedding_ref") is not None:
        preserved.add("embedding_ref")
        notes.add("pam-embedding-reference-is-non-authoritative")
    if relations:
        preserved.add("relations")
        notes.add("pam-relations-remain-source-metadata")
    if memory.get("type") == "instruction":
        preserved.add("instruction_type")
        notes.add("pam-instruction-does-not-create-doll-instruction-authority")
    unknown_fields = sorted(set(memory) - _MEMORY_KNOWN_KEYS)
    for field in unknown_fields:
        preserved.add(f"extension:{field}")
        notes.add("pam-extension-preserved-without-local-authority")
    return tuple(sorted(preserved)), tuple(sorted(notes))


def _root_mapping_notes(document: dict[str, object]) -> tuple[str, ...]:
    notes = {
        "pam-memory-interchange-not-doll-state-package",
        "pam-owner-metadata-does-not-create-local-account-authority",
        "pam-source-bytes-hashed-exactly",
    }
    if document.get("conversations_index"):
        notes.add("pam-conversation-index-preserved-at-source-not-imported-in-this-slice")
    if document.get("integrity") is not None:
        notes.add("pam-integrity-block-preserved-structurally-not-rfc8785-verified")
    if document.get("signature") is not None:
        notes.add("pam-signature-preserved-as-source-metadata-not-local-trust")
    if document.get("export_type", "full") == "incremental":
        notes.add("pam-incremental-export-staged-without-base-merge")
    return tuple(sorted(notes))


def _generic_projection_bytes(
    environment_id: str,
    objects: list[dict[str, object]],
) -> bytes:
    projection = {
        "format": "doll-generic-import",
        "format_version": PAM_V1_SCHEMA_VERSION,
        "source_environment_id": environment_id,
        "objects": objects,
    }
    return json.dumps(
        projection,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _require_object(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise PamV1ImportError(f"{label} must be an object with text keys")
    return cast(dict[str, object], value)


def _require_nonempty_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise PamV1ImportError(f"{label} must be non-empty text")
    return value


def _validate_timestamp(value: object, label: str) -> str:
    text = _require_nonempty_text(value, label)
    candidate = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise PamV1ImportError(f"{label} is not a valid ISO 8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise PamV1ImportError(f"{label} must include a timezone")
    return text


def _json_depth(value: object) -> int:
    if isinstance(value, dict):
        if not value:
            return 1
        return 1 + max(_json_depth(item) for item in value.values())
    if isinstance(value, list):
        if not value:
            return 1
        return 1 + max(_json_depth(item) for item in value)
    return 1
