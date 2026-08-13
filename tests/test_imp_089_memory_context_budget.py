from __future__ import annotations

from pathlib import Path
from typing import cast

from doll import state, workspace
from doll.memory import ConfirmedMemoryInfo, ConfirmedMemoryService
from doll.memory_context_budget import (
    MEMORY_CONTEXT_BUDGET_POLICY_ID,
    MEMORY_CONTEXT_BUDGET_POLICY_VERSION,
    MEMORY_CONTEXT_BUDGET_SCOPE,
    preview_memory_context_budget,
)
from doll.recall_state import DEFAULT_RECALL_ALGORITHM_ID, RECALL_ALGORITHM_VERSION
from doll.state import RecordSensitivity
from doll.state_repository import StateRepository
from doll.writing_context import (
    MAX_SELECTED_CONTEXT_CHARS,
    MAX_SELECTED_MEMORIES,
    SelectedWritingContextService,
)

_AS_OF = "2026-08-13T12:00:00Z"


def _workspace(root: Path) -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(root)
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def _create_memory(
    repository: StateRepository,
    *,
    subject: str,
    content: str,
    sensitivity: RecordSensitivity = "personal",
    valid_from: str | None = None,
    valid_until: str | None = None,
) -> ConfirmedMemoryInfo:
    return ConfirmedMemoryService(repository).create(
        subject=subject,
        content=content,
        sensitivity=sensitivity,
        valid_from=valid_from,
        valid_until=valid_until,
    )


def _origin_count(repository: StateRepository) -> int:
    row = repository.connection.execute(
        "SELECT COUNT(*) FROM records WHERE record_type = 'instruction_origin'"
    ).fetchone()
    assert row is not None
    return cast(int, row[0])


def test_imp_089_preview_is_ranked_versioned_read_only_and_inspectable(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path / "workspace")
    with state.open_state_repository(initialized.root) as repository:
        subject_match = _create_memory(
            repository,
            subject="alpha release plan",
            content="Ship the local client after review.",
        )
        content_match = _create_memory(
            repository,
            subject="release notes",
            content="The alpha checklist stays local.",
        )
        before_revision = repository.status().state_revision

    with state.open_state_repository(
        initialized.root,
        read_only=True,
        immutable=True,
    ) as repository:
        before_origins = _origin_count(repository)
        report = preview_memory_context_budget(repository, "alpha", as_of=_AS_OF)
        after_revision = repository.status().state_revision
        after_origins = _origin_count(repository)

    assert report.selected_memory_ids == (subject_match.record_id, content_match.record_id)
    assert [selection.recall_rank for selection in report.selections] == [1, 2]
    assert report.selections[0].lexical_score > report.selections[1].lexical_score
    assert report.source_state_revision == before_revision == after_revision
    assert report.policy_id == MEMORY_CONTEXT_BUDGET_POLICY_ID
    assert report.policy_version == MEMORY_CONTEXT_BUDGET_POLICY_VERSION
    assert report.recall_algorithm_id == DEFAULT_RECALL_ALGORITHM_ID
    assert report.recall_algorithm_version == RECALL_ALGORITHM_VERSION
    assert report.scope == MEMORY_CONTEXT_BUDGET_SCOPE
    assert report.as_of == "2026-08-13T12:00:00.000000Z"
    assert report.maximum_items == MAX_SELECTED_MEMORIES
    assert report.maximum_characters == MAX_SELECTED_CONTEXT_CHARS
    assert report.candidate_count == 2
    assert report.selected_count == 2
    assert report.selected_character_count == sum(
        selection.estimated_context_characters for selection in report.selections
    )
    assert before_origins == after_origins == 0
    payload = report.to_dict()
    assert payload["automatic_context_injection"] is False
    assert payload["requires_explicit_context_materialization"] is True


def test_imp_089_character_budget_skips_large_candidate_and_selects_later_fit(
    tmp_path: Path,
) -> None:
    initialized = _workspace(tmp_path / "workspace")
    with state.open_state_repository(initialized.root) as repository:
        large = _create_memory(repository, subject="alpha oversized", content="x" * 5000)
        small = _create_memory(repository, subject="notes", content="alpha tiny")

    with state.open_state_repository(
        initialized.root,
        read_only=True,
        immutable=True,
    ) as repository:
        planner = SelectedWritingContextService(repository)
        large_chars = planner.plan(memory_ids=(large.record_id,)).character_count
        small_chars = planner.plan(memory_ids=(small.record_id,)).character_count
        report = preview_memory_context_budget(
            repository,
            "alpha",
            as_of=_AS_OF,
            maximum_characters=small_chars,
        )

    assert large_chars > small_chars
    assert report.selected_memory_ids == (small.record_id,)
    assert report.selected_character_count == small_chars
    exclusion = next(item for item in report.exclusions if item.memory_id == large.record_id)
    assert exclusion.reason == "character_budget"
    assert exclusion.estimated_context_characters == large_chars


def test_imp_089_item_limit_preserves_recall_order(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path / "workspace")
    with state.open_state_repository(initialized.root) as repository:
        first = _create_memory(repository, subject="alpha primary", content="one")
        second = _create_memory(repository, subject="notes", content="alpha secondary")

    with state.open_state_repository(
        initialized.root,
        read_only=True,
        immutable=True,
    ) as repository:
        report = preview_memory_context_budget(
            repository,
            "alpha",
            as_of=_AS_OF,
            maximum_items=1,
        )

    assert report.selected_memory_ids == (first.record_id,)
    exclusion = next(item for item in report.exclusions if item.memory_id == second.record_id)
    assert exclusion.reason == "item_limit"


def test_imp_089_validity_windows_use_explicit_utc_time(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path / "workspace")
    with state.open_state_repository(initialized.root) as repository:
        future = _create_memory(
            repository,
            subject="alpha future",
            content="future",
            valid_from="2026-08-14T00:00:00Z",
        )
        expired = _create_memory(
            repository,
            subject="alpha expired",
            content="expired",
            valid_until="2026-08-13T11:59:59Z",
        )
        boundary = _create_memory(
            repository,
            subject="alpha boundary",
            content="boundary",
            valid_until=_AS_OF,
        )

    with state.open_state_repository(
        initialized.root,
        read_only=True,
        immutable=True,
    ) as repository:
        report = preview_memory_context_budget(repository, "alpha", as_of=_AS_OF)

    assert boundary.record_id in report.selected_memory_ids
    reasons = {item.memory_id: item.reason for item in report.exclusions}
    assert reasons[future.record_id] == "not_yet_valid"
    assert reasons[expired.record_id] == "expired"


def test_imp_089_sensitivity_archive_and_secret_boundaries_remain_closed(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path / "workspace")
    with state.open_state_repository(initialized.root) as repository:
        public = _create_memory(
            repository,
            subject="alpha public",
            content="public",
            sensitivity="public",
        )
        sensitive = _create_memory(
            repository,
            subject="alpha sensitive",
            content="sensitive",
            sensitivity="sensitive",
        )
        secret = _create_memory(
            repository,
            subject="alpha secret",
            content="secret",
            sensitivity="secret",
        )
        archived = _create_memory(repository, subject="alpha archived", content="archived")
        ConfirmedMemoryService(repository).archive(
            archived.record_id,
            expected_revision=archived.revision,
        )

    with state.open_state_repository(
        initialized.root,
        read_only=True,
        immutable=True,
    ) as repository:
        report = preview_memory_context_budget(
            repository,
            "alpha",
            as_of=_AS_OF,
            maximum_sensitivity="personal",
        )

    assert public.record_id in report.selected_memory_ids
    assert sensitive.record_id not in report.selected_memory_ids
    assert secret.record_id not in report.selected_memory_ids
    assert archived.record_id not in report.selected_memory_ids
    reasons = {item.memory_id: item.reason for item in report.exclusions}
    assert reasons[sensitive.record_id] == "sensitivity_limit"
    assert secret.record_id not in reasons
    assert archived.record_id not in reasons


def test_imp_089_explicit_materialization_remains_a_separate_write(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path / "workspace")
    with state.open_state_repository(initialized.root) as repository:
        memory = _create_memory(repository, subject="alpha", content="explicit context")

    with state.open_state_repository(
        initialized.root,
        read_only=True,
        immutable=True,
    ) as repository:
        report = preview_memory_context_budget(repository, "alpha", as_of=_AS_OF)
        assert report.selected_memory_ids == (memory.record_id,)
        assert _origin_count(repository) == 0

    with state.open_state_repository(initialized.root) as repository:
        service = SelectedWritingContextService(repository)
        plan = service.plan(memory_ids=report.selected_memory_ids)
        result = service.materialize(
            conversation_id="imp-089-explicit-conversation",
            operation_id="imp-089-explicit-materialize",
            plan=plan,
        )
        assert result.memory_ids == report.selected_memory_ids
        assert len(result.instruction_ids) == 1
        assert _origin_count(repository) == 1
