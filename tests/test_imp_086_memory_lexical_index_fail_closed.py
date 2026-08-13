from __future__ import annotations

import shutil
import sqlite3
from dataclasses import replace
from pathlib import Path
from typing import cast
from uuid import uuid4

import pytest

from doll import state, workspace
from doll.memory import ConfirmedMemoryService
from doll.recall_index import (
    RecallIndexCorruptError,
    RecallIndexStaleError,
    RecallIndexUnavailableError,
    RecallIndexValidationError,
    build_memory_lexical_index,
    discard_memory_lexical_index,
    inspect_memory_lexical_index,
    memory_lexical_index_path,
    query_memory_lexical_index,
)
from doll.state_repository import StateRepository


def initialized_workspace(tmp_path: Path, name: str) -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(tmp_path / name)
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def create_indexed_memory(initialized: workspace.InitializedWorkspace) -> str:
    with state.open_state_repository(initialized.root) as repository:
        memory = ConfirmedMemoryService(repository).create(
            subject="alpha beta",
            content="stable body",
        )
    with state.open_state_repository(
        initialized.root,
        read_only=True,
        immutable=True,
    ) as repository:
        build_memory_lexical_index(repository)
    return memory.record_id


def mutate_index(index_path: Path, statement: str, parameters: tuple[object, ...] = ()) -> None:
    connection = sqlite3.connect(index_path)
    try:
        connection.execute(statement, parameters)
        connection.commit()
    finally:
        connection.close()


def test_imp_086_index_rejects_wrong_workspace_and_reports_inspection_metadata(
    tmp_path: Path,
) -> None:
    first = initialized_workspace(tmp_path, "first")
    second = initialized_workspace(tmp_path, "second")
    create_indexed_memory(first)
    with state.open_state_repository(second.root) as repository:
        ConfirmedMemoryService(repository).create(subject="alpha beta", content="other body")

    with state.open_state_repository(
        first.root,
        read_only=True,
        immutable=True,
    ) as repository:
        inspection = inspect_memory_lexical_index(repository)
        inspection_dict = inspection.to_dict()
        assert inspection_dict["workspace_id"] == repository.status().workspace_id
        source_index = memory_lexical_index_path(repository)

    with state.open_state_repository(
        second.root,
        read_only=True,
        immutable=True,
    ) as repository:
        destination = memory_lexical_index_path(repository)
        destination.parent.mkdir(mode=0o700)
        shutil.copy2(source_index, destination)
        with pytest.raises(RecallIndexValidationError, match="another workspace"):
            inspect_memory_lexical_index(repository)
        with pytest.raises(RecallIndexValidationError, match="another workspace"):
            query_memory_lexical_index(repository, "alpha")


def test_imp_086_index_metadata_and_memory_bindings_fail_closed_when_tampered(
    tmp_path: Path,
) -> None:
    initialized = initialized_workspace(tmp_path, "workspace")
    memory_id = create_indexed_memory(initialized)

    with state.open_state_repository(
        initialized.root,
        read_only=True,
        immutable=True,
    ) as repository:
        index_path = memory_lexical_index_path(repository)

    mutate_index(
        index_path,
        "UPDATE index_metadata SET workspace_id = 'not-a-uuid' WHERE singleton = 1",
    )
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        with pytest.raises(RecallIndexCorruptError, match="workspace ID"):
            inspect_memory_lexical_index(repository)
        build_memory_lexical_index(repository)

    mutate_index(
        index_path,
        "UPDATE index_metadata SET source_state_revision = -1 WHERE singleton = 1",
    )
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        with pytest.raises(RecallIndexCorruptError, match="out of bounds"):
            inspect_memory_lexical_index(repository)
        build_memory_lexical_index(repository)

    mutate_index(
        index_path,
        "UPDATE index_metadata SET posting_count = posting_count + 1 WHERE singleton = 1",
    )
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        with pytest.raises(RecallIndexCorruptError, match="counts"):
            inspect_memory_lexical_index(repository)
        build_memory_lexical_index(repository)

    mutate_index(index_path, "DELETE FROM index_metadata WHERE singleton = 1")
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        with pytest.raises(RecallIndexCorruptError, match="metadata is missing"):
            inspect_memory_lexical_index(repository)
        build_memory_lexical_index(repository)

    mutate_index(
        index_path,
        "UPDATE indexed_memories SET memory_revision = memory_revision + 1 WHERE memory_id = ?",
        (memory_id,),
    )
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        with pytest.raises(RecallIndexCorruptError, match="binding disagrees"):
            query_memory_lexical_index(repository, "alpha")
        build_memory_lexical_index(repository)

    missing_id = str(uuid4())
    connection = sqlite3.connect(index_path)
    try:
        connection.execute(
            "UPDATE indexed_memories SET memory_id = ? WHERE memory_id = ?",
            (missing_id, memory_id),
        )
        connection.execute(
            "UPDATE token_postings SET memory_id = ? WHERE memory_id = ?",
            (missing_id, memory_id),
        )
        connection.commit()
    finally:
        connection.close()
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        with pytest.raises(RecallIndexCorruptError, match="invalid authoritative memory"):
            query_memory_lexical_index(repository, "alpha")
        build_memory_lexical_index(repository)
        assert discard_memory_lexical_index(repository) is True
        assert discard_memory_lexical_index(repository) is False


def test_imp_086_filesystem_and_publication_failures_leave_authoritative_state_usable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initialized = initialized_workspace(tmp_path, "workspace")
    with state.open_state_repository(initialized.root) as repository:
        memory = ConfirmedMemoryService(repository).create(subject="alpha", content="body")
        state_revision_before = repository.status().state_revision

    unsafe_parent = initialized.root / "temporary" / "recall-index"
    unsafe_parent.write_text("not-a-directory", encoding="utf-8")
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        with pytest.raises(RecallIndexValidationError, match="directory is unsafe"):
            build_memory_lexical_index(repository)
    unsafe_parent.unlink()

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        build_memory_lexical_index(repository)
        index_path = memory_lexical_index_path(repository)
        index_path.unlink()
        index_path.mkdir()
        with pytest.raises(RecallIndexValidationError, match="path is unsafe"):
            inspect_memory_lexical_index(repository)
        with pytest.raises(RecallIndexValidationError, match="path is unsafe"):
            discard_memory_lexical_index(repository)
        index_path.rmdir()
        build_memory_lexical_index(repository)

        original_status = StateRepository.status
        calls = 0

        def advance_on_final_status(self: StateRepository) -> state.StateStatus:
            nonlocal calls
            calls += 1
            current = original_status(self)
            if self is repository and calls >= 3:
                return replace(current, state_revision=current.state_revision + 1)
            return current

        with monkeypatch.context() as patcher:
            patcher.setattr(StateRepository, "status", advance_on_final_status)
            with pytest.raises(RecallIndexStaleError, match="changed during"):
                build_memory_lexical_index(repository)

        with monkeypatch.context() as patcher:
            patcher.setattr(
                "doll.recall_index.os.fsync",
                lambda descriptor: (_ for _ in ()).throw(OSError("synthetic fsync failure")),
            )
            with pytest.raises(RecallIndexUnavailableError, match="synchronized"):
                build_memory_lexical_index(repository)

        with monkeypatch.context() as patcher:
            patcher.setattr(
                "doll.recall_index.sqlite3.connect",
                lambda *args, **kwargs: (_ for _ in ()).throw(
                    sqlite3.DatabaseError("synthetic open failure")
                ),
            )
            with pytest.raises(RecallIndexUnavailableError, match="could not be opened"):
                inspect_memory_lexical_index(repository)

        assert ConfirmedMemoryService(repository).get(memory.record_id).revision == 1
        assert repository.status().state_revision == state_revision_before


def test_imp_086_repository_identity_and_additional_query_bounds_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initialized = initialized_workspace(tmp_path, "workspace")
    create_indexed_memory(initialized)

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        original_status = StateRepository.status

        def mismatched_status(self: StateRepository) -> state.StateStatus:
            current = original_status(self)
            if self is repository:
                return replace(current, state_revision=current.state_revision + 1)
            return current

        with monkeypatch.context() as patcher:
            patcher.setattr(StateRepository, "status", mismatched_status)
            with pytest.raises(RecallIndexValidationError, match="inconsistent"):
                inspect_memory_lexical_index(repository)

        with pytest.raises(RecallIndexValidationError, match="must be text"):
            query_memory_lexical_index(repository, cast(str, 7))
        with pytest.raises(RecallIndexValidationError, match="maximum length"):
            query_memory_lexical_index(repository, "a" * 241)
        with pytest.raises(RecallIndexValidationError, match="between 1 and 100"):
            query_memory_lexical_index(repository, "alpha", limit=cast(int, True))
        with pytest.raises(RecallIndexValidationError, match="between 1 and 100"):
            query_memory_lexical_index(repository, "alpha", limit=101)
