from __future__ import annotations

from pathlib import Path

from doll import state, workspace
from doll.memory import ConfirmedMemoryService
from doll.recall_state import (
    DEFAULT_RECALL_ALGORITHM_ID,
    RECALL_ALGORITHM_VERSION,
    derive_memory_recall_state,
)


def initialized_workspace(tmp_path: Path) -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(tmp_path / "workspace")
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def test_imp_085_weighted_memory_fields_rank_subject_content_and_metadata(
    tmp_path: Path,
) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        service = ConfirmedMemoryService(repository)
        subject_memory = service.create(
            subject="alpha beta",
            content="neutral body",
        )
        content_memory = service.create(
            subject="neutral subject",
            content="alpha beta",
        )
        metadata_memory = service.create(
            subject="another neutral subject",
            content="another neutral body",
            source_reference="alpha beta source",
        )
        service.create(
            subject="secret alpha beta",
            content="secret alpha beta body",
            sensitivity="secret",
        )
        state_revision_before = repository.status().state_revision
        record_count_before = repository.status().record_count
        authoritative_before = {
            memory.record_id: memory
            for memory in (subject_memory, content_memory, metadata_memory)
        }

    with state.open_state_repository(
        initialized.root,
        read_only=True,
        immutable=True,
    ) as repository:
        report = derive_memory_recall_state(repository, "alpha beta")
        assert report.algorithm_id == DEFAULT_RECALL_ALGORITHM_ID == "weighted-memory-fields"
        assert report.algorithm_version == RECALL_ALGORITHM_VERSION == "1"
        assert [item.memory_id for item in report.states] == [
            subject_memory.record_id,
            content_memory.record_id,
            metadata_memory.record_id,
        ]
        assert [item.lexical_score for item in report.states] == [24, 12, 2]
        assert max(item.lexical_score for item in report.states) <= 156
        assert repository.status().state_revision == state_revision_before
        assert repository.status().record_count == record_count_before
        first_report = report.to_dict()

    with state.open_state_repository(
        initialized.root,
        read_only=True,
        immutable=True,
    ) as repository:
        rebuilt = derive_memory_recall_state(repository, "alpha beta")
        assert rebuilt.to_dict() == first_report
        memory_service = ConfirmedMemoryService(repository)
        for record_id, memory_before in authoritative_before.items():
            assert memory_service.get(record_id) == memory_before
        assert repository.status().state_revision == state_revision_before
        assert repository.status().record_count == record_count_before


def test_imp_085_exact_phrase_bonus_breaks_same_field_weight_tie(
    tmp_path: Path,
) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        service = ConfirmedMemoryService(repository)
        phrase = service.create(
            subject="alpha beta release rule",
            content="neutral body",
        )
        separated = service.create(
            subject="alpha release beta rule",
            content="neutral body",
        )
        state_revision_before = repository.status().state_revision

    with state.open_state_repository(
        initialized.root,
        read_only=True,
        immutable=True,
    ) as repository:
        report = derive_memory_recall_state(repository, "alpha beta")
        scores = {item.memory_id: item.lexical_score for item in report.states}
        assert scores[phrase.record_id] == 24
        assert scores[separated.record_id] == 16
        assert report.states[0].memory_id == phrase.record_id
        assert repository.status().state_revision == state_revision_before


def test_imp_085_weighted_policy_can_replace_and_rollback_without_memory_writes(
    tmp_path: Path,
) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        service = ConfirmedMemoryService(repository)
        content_memory = service.create(
            subject="neutral content memory",
            content="alpha beta",
        )
        metadata_memory = service.create(
            subject="neutral metadata memory",
            content="neutral body",
            source_reference="alpha-source",
            session_id="beta-session",
        )
        content_before = service.get(content_memory.record_id)
        metadata_before = service.get(metadata_memory.record_id)
        state_revision_before = repository.status().state_revision

    with state.open_state_repository(
        initialized.root,
        read_only=True,
        immutable=True,
    ) as repository:
        legacy = derive_memory_recall_state(
            repository,
            "alpha beta",
            algorithm_id="local-search-order",
        )
        weighted = derive_memory_recall_state(
            repository,
            "alpha beta",
            algorithm_id="weighted-memory-fields",
        )
        rollback = derive_memory_recall_state(
            repository,
            "alpha beta",
            algorithm_id="local-search-order",
        )

        assert legacy.to_dict() == rollback.to_dict()
        assert legacy.states[0].memory_id == metadata_memory.record_id
        assert weighted.states[0].memory_id == content_memory.record_id
        assert weighted.states[0].lexical_score == 12
        assert weighted.states[1].lexical_score == 2
        memory_service = ConfirmedMemoryService(repository)
        assert memory_service.get(content_memory.record_id) == content_before
        assert memory_service.get(metadata_memory.record_id) == metadata_before
        assert repository.status().state_revision == state_revision_before
