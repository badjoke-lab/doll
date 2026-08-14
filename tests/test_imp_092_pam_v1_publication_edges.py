from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest

from doll import pam_v1_publication as publication
from doll import state, workspace
from doll.memory import ConfirmedMemoryService
from doll.pam_v1_import import (
    PAM_V1_ENVIRONMENT_CLASS,
    PamV1ImportStager,
    PamV1ImportStageResult,
    pam_content_hash,
)
from doll.portability import SourceEnvironmentRecord

STARTED = "2026-08-14T07:30:00Z"


def _init(root: Path) -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(root)
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def _stage() -> tuple[SourceEnvironmentRecord, PamV1ImportStageResult]:
    memory: dict[str, object] = {
        "id": "memory-a",
        "type": "fact",
        "content": "Portable local memory.",
        "content_hash": pam_content_hash("Portable local memory."),
        "temporal": {"created_at": "2026-08-01T00:00:00Z"},
        "provenance": {"platform": "chatgpt"},
    }
    source = json.dumps(
        {
            "schema": "portable-ai-memory",
            "schema_version": "1.0",
            "owner": {"id": "owner-1"},
            "memories": [memory],
        },
        separators=(",", ":"),
    ).encode("utf-8")
    environment = SourceEnvironmentRecord(
        environment_id=str(uuid4()),
        environment_class=PAM_V1_ENVIRONMENT_CLASS,
        provider_id="pam",
        application_id="pam-memory-store",
        export_format="json",
        export_version="1.0",
        observed_at=STARTED,
    )
    result = PamV1ImportStager(environment).stage(
        source,
        import_batch_id=str(uuid4()),
        started_at=STARTED,
    )
    return environment, result


def test_imp_092_preview_summary_and_hash_format_fail_closed(tmp_path: Path) -> None:
    initialized = _init(tmp_path / "workspace")
    _, stage_result = _stage()
    with state.open_state_repository(initialized.root) as repository:
        publisher = publication.PamV1MemoryPublisher(repository)
        preview = publisher.preview(stage_result, "memory-a", decision="approve")
        assert preview.canonical_summary()["plan_hash"] == preview.plan_hash
        with pytest.raises(publication.PamV1PublicationError, match="plan hash is invalid"):
            publisher.publish(
                preview,
                stage_result,
                approved_plan_hash="bad",
                actor_type="user",
            )


def test_imp_092_approval_fails_on_read_only_repository(tmp_path: Path) -> None:
    initialized = _init(tmp_path / "workspace")
    _, stage_result = _stage()
    with state.open_state_repository(initialized.root) as repository:
        preview = publication.PamV1MemoryPublisher(repository).preview(
            stage_result,
            "memory-a",
            decision="approve",
        )

    with state.open_state_repository(
        initialized.root,
        read_only=True,
        immutable=True,
    ) as repository:
        with pytest.raises(publication.PamV1PublicationError, match="requires writable"):
            publication.PamV1MemoryPublisher(repository).publish(
                preview,
                stage_result,
                approved_plan_hash=preview.plan_hash,
                actor_type="user",
            )


def test_imp_092_private_candidate_helpers_reject_invalid_inputs() -> None:
    _, stage_result = _stage()
    with pytest.raises(publication.PamV1PublicationError, match="stage result is invalid"):
        publication._candidate(None, "memory-a")  # type: ignore[arg-type]
    with pytest.raises(publication.PamV1PublicationError, match="must be non-empty"):
        publication._candidate(stage_result, "")
    with pytest.raises(publication.PamV1PublicationError, match="memory type is invalid"):
        publication._local_subject("")
    with pytest.raises(publication.PamV1PublicationError, match="exceeds"):
        publication._source_reference("e" * 100, "memory-a", "0" * 64)


def test_imp_092_duplicate_lineage_and_existing_mismatch_fail_closed(tmp_path: Path) -> None:
    initialized = _init(tmp_path / "workspace")
    environment, stage_result = _stage()
    with state.open_state_repository(initialized.root) as repository:
        publisher = publication.PamV1MemoryPublisher(repository)
        preview = publisher.preview(stage_result, "memory-a", decision="approve")
        prefix = publication._lineage_prefix(environment.environment_id, "memory-a")
        service = ConfirmedMemoryService(repository)
        first = service.create(
            subject=preview.mapping.local_subject,
            content=preview.mapping.local_content,
            source_type="approved_import",
            source_reference=prefix + "1" * 64,
            sensitivity="personal",
            actor_type="user",
        )
        second = service.create(
            subject=preview.mapping.local_subject,
            content=preview.mapping.local_content,
            source_type="approved_import",
            source_reference=prefix + "2" * 64,
            sensitivity="personal",
            actor_type="user",
        )
        assert first.record_id != second.record_id
        with pytest.raises(publication.PamV1PublicationError, match="multiple confirmed memories"):
            publication._existing_lineage_memory(
                repository,
                environment.environment_id,
                "memory-a",
            )

        mismatched = replace(
            first,
            source_reference=preview.mapping.source_reference,
            content="changed",
        )
        with pytest.raises(publication.PamV1PublicationError, match="no longer matches"):
            publication._validate_existing(mismatched, preview.mapping)
