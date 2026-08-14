from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest

from doll import state, workspace
from doll.memory import ConfirmedMemoryService
from doll.pam_v1_import import (
    PAM_V1_ENVIRONMENT_CLASS,
    PamV1ImportStager,
    pam_content_hash,
)
from doll.pam_v1_publication import (
    ForbiddenPamV1PublicationError,
    PamV1MemoryPublisher,
    PamV1PublicationError,
)
from doll.portability import SourceEnvironmentRecord

STARTED = "2026-08-14T07:20:00Z"


def _init(root: Path) -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(root)
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def _environment(environment_id: str | None = None) -> SourceEnvironmentRecord:
    return SourceEnvironmentRecord(
        environment_id=environment_id or str(uuid4()),
        environment_class=PAM_V1_ENVIRONMENT_CLASS,
        provider_id="pam",
        application_id="pam-memory-store",
        export_format="json",
        export_version="1.0",
        observed_at=STARTED,
    )


def _memory(
    memory_id: str,
    content: str,
    *,
    memory_type: str = "fact",
    **extra: object,
) -> dict[str, object]:
    item: dict[str, object] = {
        "id": memory_id,
        "type": memory_type,
        "content": content,
        "content_hash": pam_content_hash(content),
        "temporal": {"created_at": "2026-08-01T00:00:00Z"},
        "provenance": {
            "platform": "chatgpt",
            "extraction_method": "explicit_user_input",
        },
    }
    item.update(extra)
    return item


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


def _stage(
    source_bytes: bytes,
    source_environment: SourceEnvironmentRecord,
):
    return PamV1ImportStager(source_environment).stage(
        source_bytes,
        import_batch_id=str(uuid4()),
        started_at=STARTED,
    )


def test_imp_092_preview_is_read_only_and_keeps_pam_authority_out(tmp_path: Path) -> None:
    initialized = _init(tmp_path / "workspace")
    source_environment = _environment()
    memory = _memory(
        "memory-instruction",
        "  Keep local state first.  ",
        memory_type="instruction",
        status="deprecated",
        temporal={
            "created_at": "2026-08-01T00:00:00Z",
            "valid_from": "2026-08-02T00:00:00Z",
            "valid_until": "2026-09-01T00:00:00Z",
        },
        confidence={"current": 0.72},
        access={
            "visibility": "shared",
            "exportable": True,
            "shared_with": [{"entity": "agent-a", "permissions": ["write"]}],
        },
        embedding_ref="embedding-a",
    )
    related = _memory("memory-related", "A related source memory.")
    source_bytes = _source(
        [memory, related],
        relations=[
            {
                "id": "relation-1",
                "from": "memory-instruction",
                "to": "memory-related",
                "type": "related_to",
                "created_at": "2026-08-03T00:00:00Z",
            }
        ],
    )
    stage_result = _stage(source_bytes, source_environment)

    with state.open_state_repository(initialized.root) as repository:
        before = repository.status().state_revision
        preview = PamV1MemoryPublisher(repository).preview(
            stage_result,
            "memory-instruction",
            decision="approve",
        )
        after = repository.status().state_revision

    assert before == after
    assert preview.action == "create"
    assert preview.decision == "approve"
    assert preview.existing_memory_id is None
    assert preview.mapping.local_source_type == "approved_import"
    assert preview.mapping.local_sensitivity == "personal"
    assert preview.mapping.content_transformed is True
    assert preview.mapping.local_content == "Keep local state first."
    assert preview.mapping.local_subject == "Imported PAM instruction memory"
    assert preview.mapping.source_reference.startswith(
        f"pam-v1:{source_environment.environment_id}:"
    )
    assert preview.mapping.source_reference.endswith(stage_result.source_sha256)
    assert "pam-access-not-applied-to-doll-permission" in preview.mapping.mapping_notes
    assert "pam-lifecycle-not-applied-to-doll-memory" in preview.mapping.mapping_notes
    assert "pam-confidence-not-applied-to-doll-memory" in preview.mapping.mapping_notes
    assert "pam-relations-not-applied-to-doll-memory-links" in preview.mapping.mapping_notes
    assert "pam-embedding-reference-not-applied-to-doll-recall" in preview.mapping.mapping_notes
    assert (
        "pam-instruction-type-does-not-create-doll-instruction-authority"
        in preview.mapping.mapping_notes
    )
    summary = preview.mapping.canonical_summary()
    assert summary["pam_validity_applied"] is False
    assert summary["pam_confidence_applied"] is False
    assert summary["pam_access_applied"] is False
    assert summary["pam_relations_applied"] is False
    assert summary["pam_instruction_authority_applied"] is False
    assert summary["pam_embedding_applied"] is False


def test_imp_092_user_approval_persists_and_repeated_import_reuses(tmp_path: Path) -> None:
    initialized = _init(tmp_path / "workspace")
    source_environment = _environment()
    source_bytes = _source([_memory("memory-a", "The workstation remains local-first.")])
    stage_result = _stage(source_bytes, source_environment)

    with state.open_state_repository(initialized.root) as repository:
        publisher = PamV1MemoryPublisher(repository)
        preview = publisher.preview(stage_result, "memory-a", decision="approve")
        result = publisher.publish(
            preview,
            stage_result,
            approved_plan_hash=preview.plan_hash,
            actor_type="user",
            operation_id="imp-092-test-approve",
        )
        assert result.action == "create"
        assert result.memory_id is not None
        created_id = result.memory_id
        created_revision = result.state_revision
        memory = ConfirmedMemoryService(repository).get(created_id)
        assert memory.source_type == "approved_import"
        assert memory.provenance == "imported"
        assert memory.subject == "Imported PAM fact memory"
        assert memory.content == "The workstation remains local-first."
        assert memory.valid_from is None
        assert memory.valid_until is None
        assert memory.confidence == 1.0
        assert memory.related_memory_ids == ()
        assert memory.contradicts_memory_ids == ()
        assert memory.sensitivity == "personal"

    with state.open_state_repository(initialized.root) as repository:
        publisher = PamV1MemoryPublisher(repository)
        preview = publisher.preview(stage_result, "memory-a", decision="approve")
        assert preview.action == "reuse"
        assert preview.existing_memory_id == created_id
        before_reuse = repository.status().state_revision
        reused = publisher.publish(
            preview,
            stage_result,
            approved_plan_hash=preview.plan_hash,
            actor_type="user",
            operation_id="imp-092-test-reuse",
        )
        assert reused.action == "reuse"
        assert reused.memory_id == created_id
        assert reused.state_revision == before_reuse == created_revision
        assert ConfirmedMemoryService(repository).get(created_id).record_id == created_id


def test_imp_092_reject_is_explicit_and_writes_nothing(tmp_path: Path) -> None:
    initialized = _init(tmp_path / "workspace")
    source_environment = _environment()
    stage_result = _stage(
        _source([_memory("memory-a", "Do not publish this candidate.")]),
        source_environment,
    )

    with state.open_state_repository(initialized.root) as repository:
        publisher = PamV1MemoryPublisher(repository)
        before = repository.status().state_revision
        preview = publisher.preview(stage_result, "memory-a", decision="reject")
        result = publisher.publish(
            preview,
            stage_result,
            approved_plan_hash=preview.plan_hash,
            actor_type="user",
        )
        assert preview.action == "reject"
        assert result.action == "reject"
        assert result.memory_id is None
        assert result.state_revision == before
        assert repository.status().state_revision == before
        assert ConfirmedMemoryService(repository).list() == ()


def test_imp_092_non_user_wrong_hash_and_stale_preview_fail_closed(tmp_path: Path) -> None:
    initialized = _init(tmp_path / "workspace")
    source_environment = _environment()
    stage_result = _stage(
        _source([_memory("memory-a", "Approved only after exact review.")]),
        source_environment,
    )

    with state.open_state_repository(initialized.root) as repository:
        publisher = PamV1MemoryPublisher(repository)
        preview = publisher.preview(stage_result, "memory-a", decision="approve")
        with pytest.raises(ForbiddenPamV1PublicationError):
            publisher.publish(
                preview,
                stage_result,
                approved_plan_hash=preview.plan_hash,
                actor_type="model",
            )
        with pytest.raises(PamV1PublicationError, match="does not match"):
            publisher.publish(
                preview,
                stage_result,
                approved_plan_hash="0" * 64,
                actor_type="user",
            )

        ConfirmedMemoryService(repository).create(
            subject="Unrelated memory",
            content="This changes the state revision.",
            operation_id="imp-092-unrelated",
        )
        with pytest.raises(PamV1PublicationError, match="stale"):
            publisher.publish(
                preview,
                stage_result,
                approved_plan_hash=preview.plan_hash,
                actor_type="user",
            )
        assert all(
            item.source_type != "approved_import"
            for item in ConfirmedMemoryService(repository).list()
        )


def test_imp_092_same_pam_identity_from_changed_source_fails_closed(tmp_path: Path) -> None:
    initialized = _init(tmp_path / "workspace")
    source_environment = _environment()
    original = _stage(
        _source([_memory("memory-a", "Original source content.")]),
        source_environment,
    )

    with state.open_state_repository(initialized.root) as repository:
        publisher = PamV1MemoryPublisher(repository)
        preview = publisher.preview(original, "memory-a", decision="approve")
        created = publisher.publish(
            preview,
            original,
            approved_plan_hash=preview.plan_hash,
            actor_type="user",
        )
        assert created.memory_id is not None

    changed = _stage(
        _source([_memory("memory-a", "Changed source content.")]),
        source_environment,
    )
    assert changed.source_sha256 != original.source_sha256

    with state.open_state_repository(initialized.root) as repository:
        with pytest.raises(PamV1PublicationError, match="different source package"):
            PamV1MemoryPublisher(repository).preview(
                changed,
                "memory-a",
                decision="approve",
            )


def test_imp_092_reject_of_changed_source_still_does_not_mutate_existing(tmp_path: Path) -> None:
    initialized = _init(tmp_path / "workspace")
    source_environment = _environment()
    original = _stage(
        _source([_memory("memory-a", "Original source content.")]),
        source_environment,
    )
    with state.open_state_repository(initialized.root) as repository:
        publisher = PamV1MemoryPublisher(repository)
        preview = publisher.preview(original, "memory-a", decision="approve")
        created = publisher.publish(
            preview,
            original,
            approved_plan_hash=preview.plan_hash,
            actor_type="user",
        )
        memory_id = created.memory_id
        assert memory_id is not None

    changed = _stage(
        _source([_memory("memory-a", "Changed source content.")]),
        source_environment,
    )
    with state.open_state_repository(initialized.root) as repository:
        before = repository.status().state_revision
        preview = PamV1MemoryPublisher(repository).preview(
            changed,
            "memory-a",
            decision="reject",
        )
        assert preview.action == "reject"
        result = PamV1MemoryPublisher(repository).publish(
            preview,
            changed,
            approved_plan_hash=preview.plan_hash,
            actor_type="user",
        )
        assert result.memory_id is None
        assert repository.status().state_revision == before
        assert ConfirmedMemoryService(repository).get(memory_id).content == "Original source content."


def test_imp_092_unrepresentable_or_missing_candidate_fails_in_preview(tmp_path: Path) -> None:
    initialized = _init(tmp_path / "workspace")
    source_environment = _environment()
    stage_result = _stage(
        _source([_memory("memory-a", "Use /absolute/private/path for this task.")]),
        source_environment,
    )
    with state.open_state_repository(initialized.root) as repository:
        publisher = PamV1MemoryPublisher(repository)
        with pytest.raises(PamV1PublicationError, match="cannot be represented"):
            publisher.preview(stage_result, "memory-a", decision="approve")
        with pytest.raises(PamV1PublicationError, match="missing or ambiguous"):
            publisher.preview(stage_result, "missing-memory", decision="approve")
        with pytest.raises(PamV1PublicationError, match="decision"):
            publisher.preview(stage_result, "memory-a", decision="later")  # type: ignore[arg-type]
