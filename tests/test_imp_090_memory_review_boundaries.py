from __future__ import annotations

from pathlib import Path

import pytest

from doll import state, workspace
from doll.memory import ConfirmedMemoryService
from doll.memory_consolidation import (
    MemoryConsolidationValidationError,
    detect_memory_consolidation_candidates,
)
from doll.state_repository import StateRepository


def _init(root: Path) -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(root)
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def _snapshot(repository: StateRepository) -> dict[str, tuple[object, ...]]:
    service = ConfirmedMemoryService(repository)
    memories = service.list(include_archived=True, limit=200)
    return {
        memory.record_id: (
            memory.revision,
            memory.subject,
            memory.content,
            memory.status,
            memory.provenance,
            memory.sensitivity,
            memory.related_memory_ids,
            memory.contradicts_memory_ids,
        )
        for memory in memories
    }


def test_imp_090_review_preserves_memory_state_and_exclusions(
    tmp_path: Path,
) -> None:
    initialized = _init(tmp_path / "workspace")
    with state.open_state_repository(initialized.root) as repository:
        service = ConfirmedMemoryService(repository)
        visible_a = service.create(subject="Same note", content="Visible text")
        visible_b = service.create(subject="Same note", content="Visible text")
        private_a = service.create(
            subject="Same note",
            content="Visible text",
            sensitivity="secret",
        )
        old = service.create(subject="Same note", content="Visible text")
        service.archive(old.record_id, expected_revision=old.revision)
        before = _snapshot(repository)

    with state.open_state_repository(
        initialized.root,
        read_only=True,
        immutable=True,
    ) as repository:
        report = detect_memory_consolidation_candidates(repository)

    with state.open_state_repository(initialized.root) as repository:
        after = _snapshot(repository)

    assert before == after
    candidate_ids = {
        memory_id
        for candidate in report.candidates
        for memory_id in (candidate.left_memory_id, candidate.right_memory_id)
    }
    assert visible_a.record_id in candidate_ids
    assert visible_b.record_id in candidate_ids
    assert private_a.record_id not in candidate_ids
    assert old.record_id not in candidate_ids
    assert report.excluded_secret_memories == 1


def test_imp_090_requires_read_only_repository(tmp_path: Path) -> None:
    initialized = _init(tmp_path / "workspace")
    with state.open_state_repository(initialized.root) as repository:
        with pytest.raises(MemoryConsolidationValidationError):
            detect_memory_consolidation_candidates(repository)
