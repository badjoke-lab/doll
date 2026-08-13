from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest

from doll import state, workspace
from doll.memory import ConfirmedMemoryService
from doll.memory_context_budget import (
    MemoryContextBudgetValidationError,
    preview_memory_context_budget,
)
from doll.writing_context import MAX_SELECTED_CONTEXT_CHARS, MAX_SELECTED_MEMORIES

_AS_OF = "2026-08-13T12:00:00Z"


def _workspace(root: Path) -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(root)
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def test_imp_089_disabled_memory_returns_empty(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path / "workspace")
    with state.open_state_repository(initialized.root) as repository:
        ConfirmedMemoryService(repository).create(subject="alpha", content="remember")
        revision = repository.status().state_revision

    with state.open_state_repository(
        initialized.root,
        read_only=True,
        immutable=True,
    ) as repository:
        report = preview_memory_context_budget(
            repository,
            "",
            as_of=_AS_OF,
            memory_enabled=False,
        )

    assert report.memory_enabled is False
    assert report.source_state_revision == revision
    assert report.scanned_records == 0
    assert report.candidate_count == 0
    assert report.selected_count == 0
    assert report.selected_character_count == 0


@pytest.mark.parametrize(
    "as_of",
    ["", "2026-08-13T12:00:00", "2026-08-13T21:00:00+09:00", "not-a-time", "x" * 65],
)
def test_imp_089_rejects_invalid_as_of(tmp_path: Path, as_of: str) -> None:
    initialized = _workspace(tmp_path / "workspace")
    with state.open_state_repository(
        initialized.root,
        read_only=True,
        immutable=True,
    ) as repository:
        with pytest.raises(MemoryContextBudgetValidationError):
            preview_memory_context_budget(repository, "alpha", as_of=as_of)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("memory_enabled", cast(Any, "yes")),
        ("maximum_sensitivity", cast(Any, "secret")),
        ("maximum_sensitivity", cast(Any, "unknown")),
        ("maximum_items", cast(Any, True)),
        ("maximum_items", 0),
        ("maximum_items", MAX_SELECTED_MEMORIES + 1),
        ("maximum_characters", cast(Any, True)),
        ("maximum_characters", 0),
        ("maximum_characters", MAX_SELECTED_CONTEXT_CHARS + 1),
    ],
)
def test_imp_089_rejects_invalid_budget_controls(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    initialized = _workspace(tmp_path / "workspace")
    kwargs: dict[str, object] = {field: value}
    with state.open_state_repository(
        initialized.root,
        read_only=True,
        immutable=True,
    ) as repository:
        with pytest.raises(MemoryContextBudgetValidationError):
            preview_memory_context_budget(
                repository,
                "alpha",
                as_of=_AS_OF,
                **cast(Any, kwargs),
            )


def test_imp_089_requires_read_only_repository(tmp_path: Path) -> None:
    initialized = _workspace(tmp_path / "workspace")
    with state.open_state_repository(initialized.root) as repository:
        with pytest.raises(MemoryContextBudgetValidationError):
            preview_memory_context_budget(repository, "alpha", as_of=_AS_OF)
