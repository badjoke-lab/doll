from __future__ import annotations

import hashlib
import json
from pathlib import Path
from uuid import uuid4

import pytest

from doll import state, workspace
from doll.memory import ConfirmedMemoryService
from doll.pam_v1_export import (
    PAM_V1_EXPORT_ADAPTER_ID,
    PAM_V1_EXPORT_ADAPTER_VERSION,
    PAM_V1_EXPORT_ARTIFACT_KIND,
    PAM_V1_EXPORT_CUSTOM_TYPE,
    PamV1ExportError,
    PamV1MemoryExporter,
)
from doll.pam_v1_import import (
    PAM_V1_ENVIRONMENT_CLASS,
    PamV1ImportStager,
    pam_content_hash,
)
from doll.portability import SourceEnvironmentRecord

STARTED = "2026-08-15T00:30:00Z"


def _init(root: Path) -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(root)
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def _source_environment() -> SourceEnvironmentRecord:
    return SourceEnvironmentRecord(
        environment_id=str(uuid4()),
        environment_class=PAM_V1_ENVIRONMENT_CLASS,
        provider_id="doll",
        application_id="pam-memory-store",
        export_format="json",
        export_version="1.0",
        observed_at=STARTED,
    )


def test_imp_093_exports_deterministic_valid_pam_without_state_mutation(tmp_path: Path) -> None:
    initialized = _init(tmp_path / "workspace")
    with state.open_state_repository(initialized.root) as repository:
        service = ConfirmedMemoryService(repository)
        first = service.create(
            subject="First memory",
            content="Portable local memory one.",
            actor_type="user",
        )
        second = service.create(
            subject="Second memory",
            content="Portable local memory two.",
            actor_type="user",
        )
        before_revision = repository.status().state_revision
        exporter = PamV1MemoryExporter(repository)
        result = exporter.export_memory_store(
            owner_id="owner-1",
            memory_ids=(second.record_id, first.record_id),
        )
        repeated = exporter.export_memory_store(
            owner_id="owner-1",
            memory_ids=(first.record_id, second.record_id),
        )
        assert repository.status().state_revision == before_revision

    assert result.memory_store_bytes == repeated.memory_store_bytes
    assert result.memory_store_sha256 == hashlib.sha256(result.memory_store_bytes).hexdigest()
    assert result.adapter_id == PAM_V1_EXPORT_ADAPTER_ID
    assert result.adapter_version == PAM_V1_EXPORT_ADAPTER_VERSION
    assert result.target_version == "1.0"
    assert result.artifact_kind == PAM_V1_EXPORT_ARTIFACT_KIND
    assert result.complete_doll_continuity_export is False

    document = json.loads(result.memory_store_bytes)
    assert document["schema"] == "portable-ai-memory"
    assert document["schema_version"] == "1.0"
    assert document["owner"] == {"id": "owner-1"}
    assert [item["id"] for item in document["memories"]] == sorted(
        (first.record_id, second.record_id)
    )
    for item in document["memories"]:
        assert item["type"] == "custom"
        assert item["custom_type"] == PAM_V1_EXPORT_CUSTOM_TYPE
        assert item["content_hash"] == pam_content_hash(item["content"])
        assert item["provenance"] == {"platform": "doll"}
        assert "embedding_ref" not in item
        assert "access" not in item

    staged = PamV1ImportStager(_source_environment()).stage(
        result.memory_store_bytes,
        import_batch_id=str(uuid4()),
        started_at=STARTED,
    )
    assert staged.schema_version == "1.0"
    assert staged.verified_content_hash_count == 2


def test_imp_093_keeps_pam_hash_separate_from_doll_identity_and_reports_loss(
    tmp_path: Path,
) -> None:
    initialized = _init(tmp_path / "workspace")
    with state.open_state_repository(initialized.root) as repository:
        service = ConfirmedMemoryService(repository)
        first = service.create(
            subject="Identity A",
            content="Alpha Beta",
            source_type="user_statement",
            confidence=0.8,
            actor_type="user",
        )
        second = service.create(
            subject="Identity B",
            content="alpha   beta",
            source_type="user_statement",
            confidence=0.9,
            actor_type="user",
        )
        result = PamV1MemoryExporter(repository).export_memory_store(
            owner_id="owner-identity-test",
            memory_ids=(first.record_id, second.record_id),
        )

    document = json.loads(result.memory_store_bytes)
    exported = {item["id"]: item for item in document["memories"]}
    assert first.record_id != second.record_id
    assert exported[first.record_id]["content_hash"] == exported[second.record_id]["content_hash"]
    assert exported[first.record_id]["id"] == first.record_id
    assert exported[second.record_id]["id"] == second.record_id

    mappings = {item.doll_memory_id: item for item in result.memory_mappings}
    assert mappings[first.record_id].pam_memory_id == first.record_id
    assert "subject" in mappings[first.record_id].omitted_doll_fields
    assert "confidence" in mappings[first.record_id].omitted_doll_fields
    assert "source_type" in mappings[first.record_id].omitted_doll_fields
    assert mappings[first.record_id].represented_doll_fields == (
        "content",
        "created_at",
        "record_id",
    )
    assert "pam-memory-interchange-not-doll-state-package" in result.root_mapping_notes


def test_imp_093_secret_and_archived_memories_fail_closed(tmp_path: Path) -> None:
    initialized = _init(tmp_path / "workspace")
    with state.open_state_repository(initialized.root) as repository:
        service = ConfirmedMemoryService(repository)
        secret = service.create(
            subject="Synthetic private memory",
            content="Synthetic private content.",
            sensitivity="secret",
            actor_type="user",
        )
        archived = service.create(
            subject="Archived memory",
            content="Archived synthetic content.",
            actor_type="user",
        )
        archived = service.archive(
            archived.record_id,
            expected_revision=archived.revision,
            actor_type="user",
        )
        exporter = PamV1MemoryExporter(repository)
        before_revision = repository.status().state_revision

        with pytest.raises(PamV1ExportError, match="secret confirmed memories"):
            exporter.export_memory_store(
                owner_id="owner-1",
                memory_ids=(secret.record_id,),
            )
        with pytest.raises(PamV1ExportError, match="archived confirmed memories"):
            exporter.export_memory_store(
                owner_id="owner-1",
                memory_ids=(archived.record_id,),
            )
        assert repository.status().state_revision == before_revision


def test_imp_093_requires_explicit_bounded_owner_selection_and_version(tmp_path: Path) -> None:
    initialized = _init(tmp_path / "workspace")
    with state.open_state_repository(initialized.root) as repository:
        memory = ConfirmedMemoryService(repository).create(
            subject="Bounded export",
            content="Bounded export content.",
            actor_type="user",
        )
        exporter = PamV1MemoryExporter(repository)
        with pytest.raises(PamV1ExportError, match="owner id"):
            exporter.export_memory_store(owner_id="", memory_ids=(memory.record_id,))
        with pytest.raises(PamV1ExportError, match="at least one"):
            exporter.export_memory_store(owner_id="owner-1", memory_ids=())
        with pytest.raises(PamV1ExportError, match="duplicates"):
            exporter.export_memory_store(
                owner_id="owner-1",
                memory_ids=(memory.record_id, memory.record_id),
            )
        with pytest.raises(PamV1ExportError, match="target version"):
            exporter.export_memory_store(
                owner_id="owner-1",
                memory_ids=(memory.record_id,),
                target_version="2.0",
            )
        with pytest.raises(PamV1ExportError, match="unavailable"):
            exporter.export_memory_store(
                owner_id="owner-1",
                memory_ids=(str(uuid4()),),
            )


def test_imp_093_export_works_from_fresh_read_only_process_boundary(tmp_path: Path) -> None:
    initialized = _init(tmp_path / "workspace")
    with state.open_state_repository(initialized.root) as repository:
        memory = ConfirmedMemoryService(repository).create(
            subject="Read-only export",
            content="Fresh process compatible content.",
            actor_type="user",
        )
        expected_revision = repository.status().state_revision

    with state.open_state_repository(
        initialized.root,
        read_only=True,
        immutable=True,
    ) as repository:
        result = PamV1MemoryExporter(repository).export_memory_store(
            owner_id="owner-read-only",
            memory_ids=(memory.record_id,),
        )
        assert repository.status().state_revision == expected_revision

    summary = result.canonical_summary()
    assert summary["source_state_revision"] == expected_revision
    assert summary["memory_count"] == 1
    assert summary["complete_doll_continuity_export"] is False
