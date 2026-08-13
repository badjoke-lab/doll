from __future__ import annotations

from pathlib import Path

from doll import state, workspace
from doll.memory import ConfirmedMemoryService
from doll.memory_consolidation import (
    NEAR_DUPLICATE_THRESHOLD_BASIS_POINTS,
    detect_memory_consolidation_candidates,
)


def _init(root: Path) -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(root)
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def test_imp_090_detects_declared_candidate_classes(tmp_path: Path) -> None:
    initialized = _init(tmp_path / "workspace")
    with state.open_state_repository(initialized.root) as repository:
        service = ConfirmedMemoryService(repository)
        exact_a = service.create(subject="Backup Schedule", content="Run the LOCAL backup nightly.")
        exact_b = service.create(subject=" backup   schedule ", content="run the local backup nightly.")
        near_a = service.create(
            subject="Shutdown verification A",
            content="Keep the local backup before every shutdown and verify it.",
        )
        near_b = service.create(
            subject="Shutdown verification B",
            content="Keep the local backup before every shutdown, then verify it.",
        )
        extension_a = service.create(
            subject="Recovery note",
            content="Restore from the latest verified backup.",
        )
        extension_b = service.create(
            subject="Recovery note",
            content="Restore from the latest verified backup. Then inspect project state.",
        )
        conflict_a = service.create(
            subject="Runtime choice",
            content="Use runtime A for the migration drill.",
        )
        conflict_b = service.create(
            subject="Runtime replacement",
            content="Use runtime B for the migration drill.",
            contradicts_memory_ids=(conflict_a.record_id,),
        )
        unrelated = service.create(
            subject="Garden reminder",
            content="Water the basil planter on Sunday morning.",
        )
        source_revision = repository.status().state_revision

    with state.open_state_repository(
        initialized.root,
        read_only=True,
        immutable=True,
    ) as repository:
        first = detect_memory_consolidation_candidates(repository)
        second = detect_memory_consolidation_candidates(repository)

    assert first == second
    assert first.source_state_revision == source_revision
    pairs = {
        (candidate.kind, frozenset((candidate.left_memory_id, candidate.right_memory_id))): candidate
        for candidate in first.candidates
    }
    assert ("exact_duplicate", frozenset((exact_a.record_id, exact_b.record_id))) in pairs
    near = pairs[("near_duplicate", frozenset((near_a.record_id, near_b.record_id)))]
    assert near.lexical_overlap_basis_points is not None
    assert near.lexical_overlap_basis_points >= NEAR_DUPLICATE_THRESHOLD_BASIS_POINTS
    assert (
        "compatible_extension",
        frozenset((extension_a.record_id, extension_b.record_id)),
    ) in pairs
    assert (
        "explicit_contradiction",
        frozenset((conflict_a.record_id, conflict_b.record_id)),
    ) in pairs
    assert all(
        unrelated.record_id not in {candidate.left_memory_id, candidate.right_memory_id}
        for candidate in first.candidates
    )
    assert all(candidate.to_dict()["review_required"] is True for candidate in first.candidates)
    assert first.to_dict()["automatic_memory_mutation"] is False
