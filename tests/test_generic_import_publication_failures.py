from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

import doll.generic_import_publication as publication
from doll import state
from doll.workspace_files import ManagedFileExistsError, publish_new_workspace_file
from tests.import_publication_support import (
    COMPLETED,
    _environment,
    _initialized,
    _object,
    _portable_objects,
    _source,
    _stage,
    _text_scalar,
)


def test_transaction_failure_removes_new_snapshot_and_rolls_back_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    initialized = _initialized(tmp_path)
    environment = _environment()
    source_bytes = _source(environment, _portable_objects())
    staged = _stage(environment, source_bytes)

    with state.initialize_state_repository(initialized.root) as repository:
        publisher = publication.GenericImportPublisher(repository, environment)
        preview = publisher.preview(staged, source_bytes, preserve_source=True)
        original = publication._insert_planned_record
        calls = 0

        def fail_after_first(
            connection: sqlite3.Connection,
            record: publication._PlannedRecord,
            created_at: str,
        ) -> None:
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("test failure")
            original(connection, record, created_at)

        monkeypatch.setattr(publication, "_insert_planned_record", fail_after_first)
        with pytest.raises(RuntimeError, match="test failure"):
            publisher.publish(
                preview,
                source_bytes,
                approved_plan_hash=preview.plan_hash,
                completed_at=COMPLETED,
            )
        assert repository.status().state_revision == 0
        assert repository.status().record_count == 0
        managed_source_path = preview.managed_source_path
        assert managed_source_path is not None
        assert not (initialized.root / "artifacts" / managed_source_path).exists()


def test_existing_snapshot_target_prevents_database_publication(tmp_path: Path) -> None:
    initialized = _initialized(tmp_path)
    environment = _environment()
    source_bytes = _source(environment, _portable_objects())
    staged = _stage(environment, source_bytes)

    with state.initialize_state_repository(initialized.root) as repository:
        publisher = publication.GenericImportPublisher(repository, environment)
        preview = publisher.preview(staged, source_bytes, preserve_source=True)
        managed_source_path = preview.managed_source_path
        assert managed_source_path is not None
        existing = publish_new_workspace_file(
            initialized.root / "artifacts",
            managed_source_path,
            b"existing",
        )
        existing.close()
        with pytest.raises(ManagedFileExistsError):
            publisher.publish(
                preview,
                source_bytes,
                approved_plan_hash=preview.plan_hash,
                completed_at=COMPLETED,
            )
        assert repository.status().state_revision == 0
        assert repository.status().record_count == 0
        assert (initialized.root / "artifacts" / managed_source_path).read_bytes() == b"existing"


def test_semantic_graph_without_exactly_one_conversation_fails_preview(
    tmp_path: Path,
) -> None:
    initialized = _initialized(tmp_path)
    environment = _environment()

    with state.initialize_state_repository(initialized.root) as repository:
        publisher = publication.GenericImportPublisher(repository, environment)
        no_root_bytes = _source(
            environment,
            [_object("message", "user-message", {"text": "orphan"})],
        )
        with pytest.raises(publication.GenericImportPublicationError, match="exactly one"):
            publisher.preview(
                _stage(environment, no_root_bytes),
                no_root_bytes,
                preserve_source=False,
            )

        two_root_bytes = _source(
            environment,
            [
                _object("conversation-a", "conversation", {}),
                _object("conversation-b", "conversation", {}),
                _object(
                    "message",
                    "user-message",
                    {"text": "ambiguous"},
                    parents=["conversation-a", "conversation-b"],
                ),
            ],
        )
        with pytest.raises(publication.GenericImportPublicationError, match="exactly one"):
            publisher.preview(
                _stage(environment, two_root_bytes),
                two_root_bytes,
                preserve_source=False,
            )
        assert repository.status().state_revision == 0


def test_partial_publication_persists_quarantine_loss_and_reports(tmp_path: Path) -> None:
    initialized = _initialized(tmp_path)
    environment = _environment()
    source_bytes = _source(
        environment,
        [
            _object("conversation-1", "conversation", {"title": "Partial"}),
            _object("unsupported-1", "unknown-object", {"value": 1}),
        ],
    )
    staged = _stage(environment, source_bytes)
    assert staged.import_batch.quarantined_object_count == 1

    with state.initialize_state_repository(initialized.root) as repository:
        publisher = publication.GenericImportPublisher(repository, environment)
        preview = publisher.preview(staged, source_bytes, preserve_source=False)
        result = publisher.publish(
            preview,
            source_bytes,
            approved_plan_hash=preview.plan_hash,
            completed_at=COMPLETED,
        )
        assert result.import_batch.status == "partially_published"
        assert result.import_batch.published_object_count == 1
        reader = publication.GenericImportPublicationState(repository)
        report = reader.get_mapping_report(staged.mapping_report.mapping_report_id)
        assert report.unsupported_but_preserved_count == 1
        assert reader.get_loss(staged.loss_records[0].loss_record_id).is_material is True
        quarantine_id = _text_scalar(
            repository.connection,
            "SELECT id FROM records WHERE record_type = 'portability_quarantine'",
        )
        quarantine = reader.get_quarantine(quarantine_id)
        assert quarantine.reason == "unsupported-source-type"
        assert len(repository.list_conversations()) == 1


def test_read_only_repository_cannot_publish(tmp_path: Path) -> None:
    initialized = _initialized(tmp_path)
    environment = _environment()
    source_bytes = _source(environment, _portable_objects())
    staged = _stage(environment, source_bytes)
    with state.initialize_state_repository(initialized.root):
        pass

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        publisher = publication.GenericImportPublisher(repository, environment)
        preview = publisher.preview(staged, source_bytes, preserve_source=False)
        with pytest.raises(state.ReadOnlyStateError):
            publisher.publish(
                preview,
                source_bytes,
                approved_plan_hash=preview.plan_hash,
                completed_at=COMPLETED,
            )
        assert repository.status().state_revision == 0
