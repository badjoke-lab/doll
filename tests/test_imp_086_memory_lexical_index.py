from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from doll import state, workspace
from doll.backup import create_state_backup, verify_backup
from doll.memory import ConfirmedMemoryService
from doll.recall_index import (
    MEMORY_LEXICAL_INDEX_ALGORITHM_ID,
    MEMORY_LEXICAL_INDEX_ALGORITHM_VERSION,
    MEMORY_LEXICAL_INDEX_QUERY_MODE,
    MEMORY_LEXICAL_INDEX_SCHEMA_VERSION,
    RecallIndexCorruptError,
    RecallIndexStaleError,
    RecallIndexUnavailableError,
    RecallIndexUnsupportedError,
    RecallIndexValidationError,
    build_memory_lexical_index,
    discard_memory_lexical_index,
    inspect_memory_lexical_index,
    memory_lexical_index_path,
    query_memory_lexical_index,
)
from doll.recall_state import derive_memory_recall_state
from doll.state_package import export_state_package, verify_state_package


def initialized_workspace(tmp_path: Path) -> workspace.InitializedWorkspace:
    initialized = workspace.initialize_workspace(tmp_path / "workspace")
    with state.initialize_state_repository(initialized.root):
        pass
    return initialized


def test_imp_086_index_is_disposable_rebuildable_and_excludes_secret_archived_memory(
    tmp_path: Path,
) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        service = ConfirmedMemoryService(repository)
        subject_memory = service.create(
            subject="alpha beta release",
            content="neutral text",
            source_reference="release-source",
        )
        metadata_memory = service.create(
            subject="neutral metadata",
            content="plain content",
            source_reference="metadata-only-token",
        )
        secret_memory = service.create(
            subject="secret-only-token",
            content="private body",
            sensitivity="secret",
        )
        archived_memory = service.create(
            subject="archived-only-token",
            content="old body",
        )
        archived_memory = service.archive(
            archived_memory.record_id,
            expected_revision=archived_memory.revision,
        )
        state_revision_before = repository.status().state_revision
        record_count_before = repository.status().record_count
        authoritative_before = {
            memory.record_id: memory
            for memory in (subject_memory, metadata_memory, secret_memory, archived_memory)
        }

    with state.open_state_repository(
        initialized.root,
        read_only=True,
        immutable=True,
    ) as repository:
        inspection = build_memory_lexical_index(repository)
        assert inspection.schema_version == MEMORY_LEXICAL_INDEX_SCHEMA_VERSION == 1
        assert inspection.algorithm_id == MEMORY_LEXICAL_INDEX_ALGORITHM_ID
        assert inspection.algorithm_version == MEMORY_LEXICAL_INDEX_ALGORITHM_VERSION == "1"
        assert inspection.source_state_revision == state_revision_before
        assert inspection.indexed_memory_count == 2
        assert inspection.posting_count > 0
        assert inspection.scan_truncated is False

        report = query_memory_lexical_index(repository, "alpha beta")
        assert report.to_dict()["query_mode"] == MEMORY_LEXICAL_INDEX_QUERY_MODE
        assert [hit.memory_id for hit in report.hits] == [subject_memory.record_id]
        metadata_report = query_memory_lexical_index(repository, "metadata-only-token")
        assert [hit.memory_id for hit in metadata_report.hits] == [metadata_memory.record_id]
        assert query_memory_lexical_index(repository, "secret-only-token").result_count == 0
        assert query_memory_lexical_index(repository, "archived-only-token").result_count == 0
        first_report = report.to_dict()

        index_path = memory_lexical_index_path(repository)
        connection = sqlite3.connect(index_path)
        try:
            table_names = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
                )
            }
            assert table_names == {
                "index_metadata",
                "indexed_memories",
                "token_postings",
            }
            columns = {
                row[1]
                for row in connection.execute("PRAGMA table_info(token_postings)")
            }
            assert columns == {"token", "memory_id", "field_class"}
            stored_tokens = {
                row[0] for row in connection.execute("SELECT token FROM token_postings")
            }
            assert "alpha" in stored_tokens
            assert "beta" in stored_tokens
            assert "alpha beta release" not in stored_tokens
            assert "secret-only-token" not in stored_tokens
            assert "archived-only-token" not in stored_tokens
        finally:
            connection.close()

        assert repository.status().state_revision == state_revision_before
        assert repository.status().record_count == record_count_before
        assert discard_memory_lexical_index(repository) is True
        assert not index_path.exists()
        fallback = derive_memory_recall_state(repository, "alpha beta")
        assert [item.memory_id for item in fallback.states] == [subject_memory.record_id]
        assert repository.status().state_revision == state_revision_before

    with state.open_state_repository(
        initialized.root,
        read_only=True,
        immutable=True,
    ) as repository:
        with pytest.raises(RecallIndexUnavailableError, match="does not exist"):
            inspect_memory_lexical_index(repository)
        rebuilt = build_memory_lexical_index(repository)
        assert rebuilt.source_state_revision == state_revision_before
        assert query_memory_lexical_index(repository, "alpha beta").to_dict() == first_report
        service = ConfirmedMemoryService(repository)
        for record_id, before in authoritative_before.items():
            assert service.get(record_id) == before
        assert repository.status().state_revision == state_revision_before
        assert repository.status().record_count == record_count_before


def test_imp_086_stale_and_corrupt_index_do_not_block_memory_package_backup_or_scan_fallback(
    tmp_path: Path,
) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        service = ConfirmedMemoryService(repository)
        first = service.create(subject="alpha beta", content="first memory")
        first_before = service.get(first.record_id)

    with state.open_state_repository(
        initialized.root,
        read_only=True,
        immutable=True,
    ) as repository:
        build_memory_lexical_index(repository)

    with state.open_state_repository(initialized.root) as repository:
        service = ConfirmedMemoryService(repository)
        service.create(subject="gamma", content="new authoritative state")
        changed_state_revision = repository.status().state_revision

    with state.open_state_repository(
        initialized.root,
        read_only=True,
        immutable=True,
    ) as repository:
        with pytest.raises(RecallIndexStaleError, match="stale"):
            query_memory_lexical_index(repository, "alpha")
        fallback = derive_memory_recall_state(repository, "alpha")
        assert [item.memory_id for item in fallback.states] == [first.record_id]
        assert ConfirmedMemoryService(repository).get(first.record_id) == first_before
        rebuilt = build_memory_lexical_index(repository)
        assert rebuilt.source_state_revision == changed_state_revision
        index_path = memory_lexical_index_path(repository)

    index_path.write_bytes(b"not-a-sqlite-database")

    with state.open_state_repository(
        initialized.root,
        read_only=True,
        immutable=True,
    ) as repository:
        with pytest.raises(RecallIndexCorruptError):
            inspect_memory_lexical_index(repository)
        assert ConfirmedMemoryService(repository).get(first.record_id) == first_before
        fallback = derive_memory_recall_state(repository, "alpha")
        assert [item.memory_id for item in fallback.states] == [first.record_id]
        package_path = tmp_path / "state-package.zip"
        package = export_state_package(repository, package_path)
        verified = verify_state_package(package_path)
        assert verified.workspace_id == package.workspace_id
        assert verified.state_revision == changed_state_revision

    backup_path = tmp_path / "state-backup.zip"
    backup = create_state_backup(initialized.root, backup_path)
    verified_backup = verify_backup(backup_path)
    assert verified_backup.file_sha256 == backup.inspection.file_sha256
    assert ConfirmedMemoryService(
        state.open_state_repository(initialized.root, read_only=True).__enter__()
    )

    with state.open_state_repository(
        initialized.root,
        read_only=True,
        immutable=True,
    ) as repository:
        assert ConfirmedMemoryService(repository).get(first.record_id) == first_before
        post_backup_revision = repository.status().state_revision
        with pytest.raises(RecallIndexStaleError):
            inspect_memory_lexical_index(repository)
        rebuilt = build_memory_lexical_index(repository)
        assert rebuilt.source_state_revision == post_backup_revision
        assert query_memory_lexical_index(repository, "alpha").result_count == 1


def test_imp_086_unsupported_index_and_atomic_rebuild_failure_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        memory = ConfirmedMemoryService(repository).create(
            subject="alpha beta",
            content="stable memory",
        )
        state_revision_before = repository.status().state_revision

    with state.open_state_repository(
        initialized.root,
        read_only=True,
        immutable=True,
    ) as repository:
        build_memory_lexical_index(repository)
        original_report = query_memory_lexical_index(repository, "alpha").to_dict()
        index_path = memory_lexical_index_path(repository)

    connection = sqlite3.connect(index_path)
    try:
        connection.execute("UPDATE index_metadata SET schema_version = 99 WHERE singleton = 1")
        connection.commit()
    finally:
        connection.close()

    with state.open_state_repository(
        initialized.root,
        read_only=True,
        immutable=True,
    ) as repository:
        with pytest.raises(RecallIndexUnsupportedError, match="unsupported"):
            inspect_memory_lexical_index(repository)
        build_memory_lexical_index(repository)
        assert query_memory_lexical_index(repository, "alpha").to_dict() == original_report

        def fail_replace(source: Path, target: Path) -> None:
            raise OSError("synthetic publish failure")

        monkeypatch.setattr("doll.recall_index.os.replace", fail_replace)
        with pytest.raises(RecallIndexUnavailableError, match="could not be built"):
            build_memory_lexical_index(repository)
        assert query_memory_lexical_index(repository, "alpha").to_dict() == original_report
        assert ConfirmedMemoryService(repository).get(memory.record_id).revision == 1
        assert repository.status().state_revision == state_revision_before
        leftovers = [path.name for path in index_path.parent.iterdir()]
        assert leftovers == [index_path.name]


def test_imp_086_requests_fail_closed_outside_read_only_bounded_contract(
    tmp_path: Path,
) -> None:
    initialized = initialized_workspace(tmp_path)
    with state.open_state_repository(initialized.root) as repository:
        ConfirmedMemoryService(repository).create(subject="alpha", content="alpha")
        with pytest.raises(RecallIndexValidationError, match="read-only"):
            build_memory_lexical_index(repository)
        with pytest.raises(RecallIndexValidationError, match="read-only"):
            query_memory_lexical_index(repository, "alpha")
        with pytest.raises(RecallIndexValidationError, match="read-only"):
            discard_memory_lexical_index(repository)

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        build_memory_lexical_index(repository)
        with pytest.raises(RecallIndexValidationError, match="blank"):
            query_memory_lexical_index(repository, "   ")
        with pytest.raises(RecallIndexValidationError, match="control"):
            query_memory_lexical_index(repository, "alpha\nbeta")
        with pytest.raises(RecallIndexValidationError, match="too many"):
            query_memory_lexical_index(
                repository,
                "one two three four five six seven eight nine ten eleven twelve thirteen",
            )
        with pytest.raises(RecallIndexValidationError, match="between 1 and 100"):
            query_memory_lexical_index(repository, "alpha", limit=0)
