from __future__ import annotations

import hashlib
import json
import unicodedata
from pathlib import Path
from uuid import uuid4

import pytest

from doll.pam_v1_import import (
    PAM_V1_ADAPTER_ID,
    PAM_V1_ADAPTER_VERSION,
    PAM_V1_ENVIRONMENT_CLASS,
    PamV1ImportError,
    PamV1ImportStager,
    PamV1ImportStageResult,
)
from doll.portability import SourceEnvironmentRecord

STARTED = "2026-08-14T06:20:00Z"


def _pam_hash(content: str) -> str:
    text = unicodedata.normalize("NFC", content.strip().lower())
    text = " ".join(text.split())
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _memory(
    memory_id: str,
    content: str,
    *,
    memory_type: str = "fact",
    **extra: object,
) -> dict[str, object]:
    memory: dict[str, object] = {
        "id": memory_id,
        "type": memory_type,
        "content": content,
        "content_hash": _pam_hash(content),
        "temporal": {"created_at": "2026-08-01T00:00:00Z"},
        "provenance": {
            "platform": "chatgpt",
            "extraction_method": "explicit_user_input",
        },
    }
    memory.update(extra)
    return memory


def _source(memories: list[dict[str, object]], **extra: object) -> bytes:
    document: dict[str, object] = {
        "schema": "portable-ai-memory",
        "schema_version": "1.0",
        "owner": {"id": "owner-1"},
        "memories": memories,
    }
    document.update(extra)
    return json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _environment() -> SourceEnvironmentRecord:
    return SourceEnvironmentRecord(
        environment_id=str(uuid4()),
        environment_class=PAM_V1_ENVIRONMENT_CLASS,
        provider_id="pam",
        application_id="pam-memory-store",
        export_format="json",
        export_version="1.0",
        observed_at=STARTED,
    )


def _stage(source_bytes: bytes) -> PamV1ImportStageResult:
    return PamV1ImportStager(_environment()).stage(
        source_bytes,
        import_batch_id=str(uuid4()),
        started_at=STARTED,
    )


def test_imp_091_stages_pam_as_external_data_without_memory_authority() -> None:
    instruction = _memory(
        "memory-instruction",
        "Always use local storage first.",
        memory_type="instruction",
        status="deprecated",
        temporal={
            "created_at": "2026-08-01T00:00:00Z",
            "valid_from": "2026-08-02T00:00:00Z",
        },
        confidence={"current": 0.8},
        access={
            "visibility": "shared",
            "exportable": True,
            "shared_with": [{"entity": "agent-a", "permissions": ["read", "write"]}],
        },
        embedding_ref="embedding-1",
        metadata={"domain": "technical"},
    )
    fact = _memory("memory-fact", "The workstation is local-only.")
    relation = {
        "id": "relation-1",
        "from": "memory-instruction",
        "to": "memory-fact",
        "type": "related_to",
        "created_at": "2026-08-03T00:00:00Z",
    }
    source_bytes = _source(
        [instruction, fact],
        relations=[relation],
        conversations_index=[
            {
                "id": "conversation-1",
                "platform": "chatgpt",
                "temporal": {"created_at": "2026-08-01T00:00:00Z"},
            }
        ],
        integrity={
            "canonicalization": "RFC8785",
            "checksum": "sha256:" + "0" * 64,
            "total_memories": 2,
        },
        signature={"algorithm": "Ed25519", "value": "source-only"},
    )
    environment = _environment()
    batch_id = str(uuid4())
    stager = PamV1ImportStager(environment)

    first = stager.stage(source_bytes, import_batch_id=batch_id, started_at=STARTED)
    second = stager.stage(source_bytes, import_batch_id=batch_id, started_at=STARTED)

    assert first == second
    assert first.source_sha256 == hashlib.sha256(source_bytes).hexdigest()
    assert first.schema_version == "1.0"
    assert first.adapter_id == PAM_V1_ADAPTER_ID
    assert first.adapter_version == PAM_V1_ADAPTER_VERSION
    assert first.verified_content_hash_count == 2
    assert first.generic_stage.import_batch.adapter_id == PAM_V1_ADAPTER_ID
    assert {item.source_type for item in first.generic_stage.staged_objects} == {"memory"}
    assert {item.authority_class for item in first.generic_stage.staged_objects} == {
        "external_data"
    }

    instruction_mapping = next(
        item for item in first.memory_mappings if item.source_memory_id == "memory-instruction"
    )
    assert instruction_mapping.review_required is True
    assert instruction_mapping.authority_class == "external_data"
    assert "access" in instruction_mapping.preserved_non_authoritative_fields
    assert "lifecycle" in instruction_mapping.preserved_non_authoritative_fields
    assert "embedding_ref" in instruction_mapping.preserved_non_authoritative_fields
    assert "relations" in instruction_mapping.preserved_non_authoritative_fields
    assert "instruction_type" in instruction_mapping.preserved_non_authoritative_fields
    assert "pam-access-does-not-create-doll-permission" in instruction_mapping.mapping_notes
    assert (
        "pam-instruction-does-not-create-doll-instruction-authority"
        in instruction_mapping.mapping_notes
    )
    assert "relation-1" in instruction_mapping.relation_ids

    staged = next(
        item
        for item in first.generic_stage.staged_objects
        if item.source_object_id == "memory-instruction"
    )
    payload = json.loads(staged.payload_json)
    assert payload["pam_memory"] == instruction
    assert payload["pam_relations"] == [relation]
    assert payload["authority_class"] == "external_data"
    assert payload["review_required"] is True

    assert "pam-conversation-index-preserved-at-source-not-imported-in-this-slice" in (
        first.root_mapping_notes
    )
    assert "pam-integrity-block-preserved-structurally-not-rfc8785-verified" in (
        first.root_mapping_notes
    )
    assert "pam-signature-preserved-as-source-metadata-not-local-trust" in (
        first.root_mapping_notes
    )
    summary = first.canonical_summary()
    assert summary["authoritative_memory_created"] is False
    assert summary["permission_authority_created"] is False


def test_imp_091_pam_content_hash_is_not_candidate_identity() -> None:
    first_content = "  CAFÉ   LOCAL  "
    second_content = "cafe\u0301 local"
    source_bytes = _source(
        [
            _memory("memory-a", first_content),
            _memory("memory-b", second_content),
        ]
    )

    result = _stage(source_bytes)
    mappings = {item.source_memory_id: item for item in result.memory_mappings}

    assert mappings["memory-a"].source_content_hash == mappings["memory-b"].source_content_hash
    assert mappings["memory-a"].generic_source_hash != mappings["memory-b"].generic_source_hash
    assert mappings["memory-a"].source_memory_id != mappings["memory-b"].source_memory_id


def test_imp_091_rejects_wrong_content_hash_and_unsupported_version() -> None:
    wrong = _memory("memory-a", "local only")
    wrong["content_hash"] = "sha256:" + "0" * 64
    with pytest.raises(PamV1ImportError, match="content_hash does not match"):
        _stage(_source([wrong]))

    document = json.loads(_source([_memory("memory-a", "local only")]))
    document["schema_version"] = "2.0"
    unsupported = json.dumps(document, separators=(",", ":")).encode("utf-8")
    with pytest.raises(PamV1ImportError, match="schema version is unsupported"):
        _stage(unsupported)


def test_imp_091_rejects_unknown_relation_and_invalid_environment() -> None:
    relation = {
        "id": "relation-1",
        "from": "memory-a",
        "to": "missing-memory",
        "type": "supports",
        "created_at": "2026-08-03T00:00:00Z",
    }
    with pytest.raises(PamV1ImportError, match="unknown memory id"):
        _stage(_source([_memory("memory-a", "local only")], relations=[relation]))

    environment = SourceEnvironmentRecord(
        environment_id=str(uuid4()),
        environment_class="generic-file-export",
        export_format="json",
        export_version="1.0",
    )
    with pytest.raises(PamV1ImportError, match="not a PAM memory store"):
        PamV1ImportStager(environment)


def test_imp_091_module_has_no_confirmed_memory_or_state_write_dependency() -> None:
    from doll import pam_v1_import

    module_text = Path(pam_v1_import.__file__).read_text(encoding="utf-8")
    assert "from doll.memory" not in module_text
    assert "from doll.state_repository" not in module_text
    assert "ConfirmedMemoryService" not in module_text
