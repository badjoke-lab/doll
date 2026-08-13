from __future__ import annotations

from pathlib import Path

import pytest

from doll import state, workspace
from doll.memory import ConfirmedMemoryService
from doll.recall_index import (
    RecallIndexUnavailableError,
    RecallIndexValidationError,
    build_memory_lexical_index,
    discard_memory_lexical_index,
    memory_lexical_index_path,
)


def initialized_workspace(tmp_path: Path) -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(tmp_path / "workspace")
    with state.initialize_state_repository(initialized.root):
        pass
    with state.open_state_repository(initialized.root) as repository:
        ConfirmedMemoryService(repository).create(subject="alpha", content="stable memory")
    return initialized


def test_imp_086_build_rejects_directory_at_final_index_path(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        index_path = memory_lexical_index_path(repository)
        index_path.parent.mkdir(mode=0o700)
        index_path.mkdir()
        with pytest.raises(
            RecallIndexValidationError,
            match="existing lexical index path is unsafe",
        ):
            build_memory_lexical_index(repository)


def test_imp_086_discard_wraps_index_unlink_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        build_memory_lexical_index(repository)
        index_path = memory_lexical_index_path(repository)
        original_unlink = Path.unlink

        def fail_target_unlink(path: Path, *, missing_ok: bool = False) -> None:
            if path == index_path:
                raise OSError("synthetic index unlink failure")
            original_unlink(path, missing_ok=missing_ok)

        monkeypatch.setattr(Path, "unlink", fail_target_unlink)
        with pytest.raises(RecallIndexUnavailableError, match="could not be removed"):
            discard_memory_lexical_index(repository)


def test_imp_086_build_rejects_unsafe_workspace_temporary_root(tmp_path: Path) -> None:
    initialized = initialized_workspace(tmp_path)
    temporary_root = initialized.root / "temporary"
    temporary_root.rmdir()
    temporary_root.write_text("not-a-directory", encoding="utf-8")

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        with pytest.raises(RecallIndexValidationError, match="temporary directory is unsafe"):
            build_memory_lexical_index(repository)


def test_imp_086_build_wraps_index_directory_creation_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initialized = initialized_workspace(tmp_path)
    index_directory = initialized.root / "temporary" / "recall-index"
    original_mkdir = Path.mkdir

    def fail_index_directory_mkdir(
        path: Path,
        mode: int = 0o777,
        parents: bool = False,
        exist_ok: bool = False,
    ) -> None:
        if path == index_directory:
            raise OSError("synthetic index-directory creation failure")
        original_mkdir(path, mode=mode, parents=parents, exist_ok=exist_ok)

    monkeypatch.setattr(Path, "mkdir", fail_index_directory_mkdir)
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        with pytest.raises(RecallIndexUnavailableError, match="directory could not be created"):
            build_memory_lexical_index(repository)
