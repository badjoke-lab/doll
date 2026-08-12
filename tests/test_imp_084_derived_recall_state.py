from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from doll import state, workspace
from doll.memory import ConfirmedMemoryService
from doll.recall_state import (
    DEFAULT_RECALL_ALGORITHM_ID,
    RECALL_ALGORITHM_VERSION,
    RecallAlgorithmId,
    RecallStateValidationError,
    derive_memory_recall_state,
)


def initialized_workspace(tmp_path: Path) -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(tmp_path / "workspace")
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def test_imp_084_recall_state_is_ephemeral_rebuildable_and_memory_safe(
    tmp_path: Path,
) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        service = ConfirmedMemoryService(repository)
        remembered = service.create(
            subject="release rule",
            content="alpha review remains required",
            source_reference="synthetic-alpha-source",
        )
        service.create(
            subject="secret alpha",
            content="alpha must never enter normal recall",
            sensitivity="secret",
        )
        authoritative_before = service.get(remembered.record_id)
        state_revision_before = repository.status().state_revision
        record_count_before = repository.status().record_count

    with state.open_state_repository(
        initialized.root,
        read_only=True,
        immutable=True,
    ) as repository:
        report = derive_memory_recall_state(repository, "alpha")
        assert report.algorithm_id == DEFAULT_RECALL_ALGORITHM_ID
        assert report.algorithm_version == RECALL_ALGORITHM_VERSION
        assert report.source_state_revision == state_revision_before
        assert report.result_count == 1
        recalled = report.states[0]
        assert recalled.memory_id == remembered.record_id
        assert recalled.memory_revision == authoritative_before.revision
        assert recalled.source_state_revision == state_revision_before
        assert recalled.rank == 1
        assert recalled.lexical_score >= 1
        assert repository.status().state_revision == state_revision_before
        assert repository.status().record_count == record_count_before
        recall_row = repository.connection.execute(
            "SELECT COUNT(*) FROM records WHERE record_type = 'recall_state'"
        ).fetchone()
        assert recall_row is not None
        assert recall_row[0] == 0
        first_derivation = report.to_dict()

    with state.open_state_repository(
        initialized.root,
        read_only=True,
        immutable=True,
    ) as repository:
        rebuilt = derive_memory_recall_state(repository, "alpha")
        assert rebuilt.to_dict() == first_derivation
        assert ConfirmedMemoryService(repository).get(remembered.record_id) == authoritative_before
        assert repository.status().state_revision == state_revision_before
        assert repository.status().record_count == record_count_before


def test_imp_084_algorithm_replacement_does_not_rewrite_memory(
    tmp_path: Path,
) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        service = ConfirmedMemoryService(repository)
        title_match = service.create(
            subject="alpha",
            content="neutral body",
        )
        field_match = service.create(
            subject="neutral",
            content="alpha body",
            source_reference="alpha-source",
            session_id="alpha-session",
        )
        title_before = service.get(title_match.record_id)
        field_before = service.get(field_match.record_id)
        state_revision_before = repository.status().state_revision

    with state.open_state_repository(
        initialized.root,
        read_only=True,
        immutable=True,
    ) as repository:
        search_order = derive_memory_recall_state(
            repository,
            "alpha",
            algorithm_id="local-search-order",
        )
        field_count_order = derive_memory_recall_state(
            repository,
            "alpha",
            algorithm_id="bounded-field-count-rerank",
        )

        assert search_order.states[0].memory_id == title_match.record_id
        assert field_count_order.states[0].memory_id == field_match.record_id
        assert search_order.algorithm_id != field_count_order.algorithm_id
        assert search_order.algorithm_version == field_count_order.algorithm_version == "1"
        assert ConfirmedMemoryService(repository).get(title_match.record_id) == title_before
        assert ConfirmedMemoryService(repository).get(field_match.record_id) == field_before
        assert repository.status().state_revision == state_revision_before

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        assert ConfirmedMemoryService(repository).get(title_match.record_id).revision == 1
        assert ConfirmedMemoryService(repository).get(field_match.record_id).revision == 1
        assert repository.status().state_revision == state_revision_before


def test_imp_084_recall_requires_read_only_state_and_known_algorithm(
    tmp_path: Path,
) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        ConfirmedMemoryService(repository).create(subject="alpha", content="alpha")
        with pytest.raises(RecallStateValidationError, match="read-only"):
            derive_memory_recall_state(repository, "alpha")

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        with pytest.raises(RecallStateValidationError, match="unsupported"):
            derive_memory_recall_state(
                repository,
                "alpha",
                algorithm_id=cast(RecallAlgorithmId, "unsupported"),
            )
