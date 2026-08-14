from __future__ import annotations

import json
from dataclasses import replace
from uuid import uuid4

import pytest

from doll import pam_v1_import as pam
from doll.portability import SourceEnvironmentRecord

STARTED = "2026-08-14T06:30:00Z"


def _environment(**overrides: object) -> SourceEnvironmentRecord:
    values: dict[str, object] = {
        "environment_id": str(uuid4()),
        "environment_class": pam.PAM_V1_ENVIRONMENT_CLASS,
        "provider_id": "pam",
        "application_id": "pam-memory-store",
        "export_format": "json",
        "export_version": "1.0",
        "observed_at": STARTED,
    }
    values.update(overrides)
    return SourceEnvironmentRecord(**values)  # type: ignore[arg-type]


def _memory(**overrides: object) -> dict[str, object]:
    content = str(overrides.pop("content", "Local memory text."))
    values: dict[str, object] = {
        "id": "memory-a",
        "type": "fact",
        "content": content,
        "content_hash": pam.pam_content_hash(content),
        "temporal": {"created_at": "2026-08-01T00:00:00Z"},
        "provenance": {"platform": "chatgpt"},
    }
    values.update(overrides)
    return values


def _document(memories: object | None = None, **overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "schema": pam.PAM_V1_SCHEMA,
        "schema_version": pam.PAM_V1_SCHEMA_VERSION,
        "owner": {"id": "owner-1"},
        "memories": [_memory()] if memories is None else memories,
    }
    values.update(overrides)
    return values


def _bytes(document: object) -> bytes:
    return json.dumps(document, separators=(",", ":")).encode("utf-8")


def _stage(source: bytes, **limits: int):
    return pam.PamV1ImportStager(_environment(), **limits).stage(
        source,
        import_batch_id=str(uuid4()),
        started_at=STARTED,
    )


@pytest.mark.parametrize(
    ("environment_overrides", "message"),
    [
        ({"export_format": "yaml"}, "export format"),
        ({"export_version": "2.0"}, "version is unsupported"),
    ],
)
def test_imp_091_rejects_unsupported_source_environment(
    environment_overrides: dict[str, object], message: str
) -> None:
    with pytest.raises(pam.PamV1ImportError, match=message):
        pam.PamV1ImportStager(_environment(**environment_overrides))


@pytest.mark.parametrize(
    ("limit_name", "value"),
    [
        ("max_input_bytes", False),
        ("max_input_bytes", 0),
        ("max_memories", pam.PAM_V1_MAX_MEMORIES + 1),
        ("max_nesting_depth", pam.PAM_V1_MAX_NESTING_DEPTH + 1),
    ],
)
def test_imp_091_rejects_invalid_adapter_limits(limit_name: str, value: object) -> None:
    with pytest.raises(pam.PamV1ImportError, match="outside the supported range"):
        pam.PamV1ImportStager(_environment(), **{limit_name: value})  # type: ignore[arg-type]


def test_imp_091_rejects_invalid_source_bytes_and_bounds() -> None:
    stager = pam.PamV1ImportStager(_environment())
    with pytest.raises(pam.PamV1ImportError, match="must be bytes"):
        stager.stage("not-bytes", import_batch_id=str(uuid4()), started_at=STARTED)  # type: ignore[arg-type]
    with pytest.raises(pam.PamV1ImportError, match="must not be empty"):
        stager.stage(b"", import_batch_id=str(uuid4()), started_at=STARTED)
    with pytest.raises(pam.PamV1ImportError, match="valid UTF-8"):
        stager.stage(b"\xff", import_batch_id=str(uuid4()), started_at=STARTED)
    with pytest.raises(pam.PamV1ImportError, match="valid bounded JSON"):
        stager.stage(b"{", import_batch_id=str(uuid4()), started_at=STARTED)

    tiny = pam.PamV1ImportStager(_environment(), max_input_bytes=1)
    with pytest.raises(pam.PamV1ImportError, match="byte limit"):
        tiny.stage(b"{}", import_batch_id=str(uuid4()), started_at=STARTED)

    shallow = pam.PamV1ImportStager(_environment(), max_nesting_depth=2)
    with pytest.raises(pam.PamV1ImportError, match="nesting"):
        shallow.stage(_bytes(_document()), import_batch_id=str(uuid4()), started_at=STARTED)


@pytest.mark.parametrize(
    ("document", "message"),
    [
        (_document(schema="other"), "schema identifier"),
        (_document(owner=[]), "PAM owner must be an object"),
        (_document(owner={"id": ""}), "owner id"),
        (_document(memories={}), "memories must be an array"),
        (_document(memories=["bad"]), "PAM memory must be an object"),
        (
            _document(memories=[_memory(), _memory()]),
            "memory ids contain duplicates",
        ),
    ],
)
def test_imp_091_rejects_invalid_root_contract(document: dict[str, object], message: str) -> None:
    with pytest.raises(pam.PamV1ImportError, match=message):
        _stage(_bytes(document))


def test_imp_091_rejects_memory_count_limit() -> None:
    source = _bytes(_document(memories=[_memory(id="a"), _memory(id="b")]))
    with pytest.raises(pam.PamV1ImportError, match="memory count"):
        _stage(source, max_memories=1)


@pytest.mark.parametrize(
    ("memory", "message"),
    [
        (_memory(type="unknown"), "type is unsupported"),
        (_memory(type="custom"), "custom_type"),
        (_memory(custom_type="unexpected"), "custom_type must be null"),
        (_memory(content=123), "content must be text"),
        (_memory(content_hash="bad"), "content_hash format"),
        (_memory(temporal=[]), "temporal must be an object"),
        (_memory(temporal={"created_at": "2026-08-01"}), "include a timezone"),
        (_memory(provenance={"platform": "BAD PLATFORM"}), "platform is invalid"),
        (
            _memory(provenance={"platform": "chatgpt", "extraction_method": "other"}),
            "extraction method",
        ),
        (
            _memory(provenance={"platform": "chatgpt", "platform_user_id": 4}),
            "platform_user_id is invalid",
        ),
        (_memory(status="unknown"), "status is invalid"),
        (_memory(summary=4), "summary is invalid"),
        (_memory(tags=["Bad Tag"]), "tags are invalid"),
        (_memory(confidence=[]), "confidence must be an object"),
        (_memory(access=[]), "access must be an object"),
        (_memory(metadata=[]), "metadata must be an object"),
        (_memory(embedding_ref=4), "embedding_ref is invalid"),
    ],
)
def test_imp_091_rejects_invalid_memory_fields(memory: dict[str, object], message: str) -> None:
    with pytest.raises(pam.PamV1ImportError, match=message):
        pam._validate_memory(memory)


def test_imp_091_accepts_custom_and_optional_temporal_provenance_fields() -> None:
    memory = _memory(
        type="custom",
        custom_type="local-note",
        temporal={
            "created_at": "2026-08-01T00:00:00Z",
            "updated_at": "2026-08-02T00:00:00+00:00",
            "valid_until": "2026-09-01T00:00:00Z",
            "superseded_by": "memory-b",
        },
        provenance={
            "platform": "chatgpt",
            "extraction_method": "manual",
            "extracted_at": "2026-08-02T00:00:00Z",
            "platform_user_id": "user-a",
            "conversation_ref": "conversation-a",
            "message_ref": "message-a",
            "extractor": "manual-tool",
        },
        tags=["local_note"],
    )
    pam._validate_memory(memory)


@pytest.mark.parametrize(
    ("relations", "message"),
    [
        ({}, "relations must be an array"),
        (
            [
                {
                    "id": "r1",
                    "from": "memory-a",
                    "to": "memory-a",
                    "type": "unknown",
                    "created_at": "2026-08-01T00:00:00Z",
                }
            ],
            "relation type",
        ),
        (
            [
                {
                    "id": "r1",
                    "from": "memory-a",
                    "to": "memory-a",
                    "type": "supports",
                    "created_at": "2026-08-01T00:00:00Z",
                    "confidence": True,
                }
            ],
            "relation confidence",
        ),
    ],
)
def test_imp_091_rejects_invalid_relation_contract(relations: object, message: str) -> None:
    with pytest.raises(pam.PamV1ImportError, match=message):
        pam._validate_relations(relations, ("memory-a",))


def test_imp_091_rejects_duplicate_relation_ids_and_accepts_self_relation() -> None:
    relation = {
        "id": "r1",
        "from": "memory-a",
        "to": "memory-a",
        "type": "related_to",
        "created_at": "2026-08-01T00:00:00Z",
        "confidence": 0.5,
    }
    result = pam._validate_relations([relation], ("memory-a",))
    assert len(result["memory-a"]) == 1
    with pytest.raises(pam.PamV1ImportError, match="relation ids contain duplicates"):
        pam._validate_relations([relation, relation], ("memory-a",))


@pytest.mark.parametrize(
    ("document", "message"),
    [
        (_document(export_type="other"), "export_type"),
        (_document(conversations_index={}), "conversations_index"),
        (_document(integrity=[]), "PAM integrity must be an object"),
        (
            _document(integrity={"checksum": "bad", "total_memories": 1}),
            "checksum format",
        ),
        (
            _document(
                integrity={
                    "checksum": "sha256:" + "0" * 64,
                    "total_memories": 2,
                }
            ),
            "total_memories",
        ),
        (
            _document(
                integrity={
                    "checksum": "sha256:" + "0" * 64,
                    "total_memories": 1,
                    "canonicalization": "other",
                }
            ),
            "canonicalization",
        ),
        (_document(signature=[]), "signature must be an object"),
    ],
)
def test_imp_091_rejects_invalid_optional_root_blocks(
    document: dict[str, object], message: str
) -> None:
    with pytest.raises(pam.PamV1ImportError, match=message):
        pam._validate_root_optional_blocks(document, 1)


def test_imp_091_preserves_incremental_and_extension_notes() -> None:
    memory = _memory(custom_extension={"value": 1})
    result = _stage(_bytes(_document(memories=[memory], export_type="incremental")))
    mapping = result.memory_mappings[0]
    assert "extension:custom_extension" in mapping.preserved_non_authoritative_fields
    assert "pam-extension-preserved-without-local-authority" in mapping.mapping_notes
    assert "pam-incremental-export-staged-without-base-merge" in result.root_mapping_notes


def test_imp_091_result_contract_rejects_internal_inconsistency() -> None:
    valid = _stage(_bytes(_document()))
    invalid_cases = [
        {"source_sha256": "bad"},
        {"generic_projection_sha256": "bad"},
        {"source_size_bytes": 0},
        {"schema_version": "2.0"},
        {"adapter_id": "other"},
        {"adapter_version": "2.0.0"},
        {"verified_content_hash_count": 0},
    ]
    for changes in invalid_cases:
        with pytest.raises(pam.PamV1ImportError):
            replace(valid, **changes)


def test_imp_091_helper_validation_is_fail_closed() -> None:
    with pytest.raises(pam.PamV1ImportError, match="content must be text"):
        pam.pam_content_hash(1)  # type: ignore[arg-type]
    with pytest.raises(pam.PamV1ImportError, match="object with text keys"):
        pam._require_object({1: "value"}, "object")
    with pytest.raises(pam.PamV1ImportError, match="non-empty text"):
        pam._require_nonempty_text("", "text")
    with pytest.raises(pam.PamV1ImportError, match="valid ISO 8601"):
        pam._validate_timestamp("not-a-time", "time")
    with pytest.raises(pam.PamV1ImportError, match="include a timezone"):
        pam._validate_timestamp("2026-08-14T06:00:00", "time")
    assert pam._json_depth({}) == 1
    assert pam._json_depth([]) == 1
    assert pam._json_depth("scalar") == 1
