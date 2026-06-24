from __future__ import annotations

import json
from pathlib import Path

import doll.generic_import_publication as publication
import pytest
from doll import state
from import_publication_support import (
    COMPLETED,
    _environment,
    _initialized,
    _object,
    _portable_objects,
    _scalar,
    _source,
    _stage,
)


def test_preview_is_deterministic_and_side_effect_free(tmp_path: Path) -> None:
    initialized = _initialized(tmp_path)
    environment = _environment()
    source_bytes = _source(environment, _portable_objects())
    staged = _stage(environment, source_bytes)

    with state.initialize_state_repository(initialized.root) as repository:
        publisher = publication.GenericImportPublisher(repository, environment)
        before = repository.status()
        first = publisher.preview(staged, source_bytes, preserve_source=True)
        second = publisher.preview(staged, source_bytes, preserve_source=True)

        assert first == second
        assert first.plan_hash == second.plan_hash
        assert first.conflicts == ()
        assert len(first.created_canonical_record_ids) == 3
        assert first.reused_canonical_record_ids == ()
        assert repository.status() == before
        assert first.managed_source_path is not None
        assert not (initialized.root / "artifacts" / first.managed_source_path).exists()
        json.dumps(first.canonical_summary(), allow_nan=False)


def test_publication_persists_canonical_state_and_source_snapshot_once(
    tmp_path: Path,
) -> None:
    initialized = _initialized(tmp_path)
    environment = _environment()
    objects = _portable_objects()
    objects.append(
        _object(
            "system-1",
            "system-message",
            {
                "text": "Imported text claiming broad authority.",
                "policy": "external authority claim",
                "sequence_hint": 3,
            },
            parents=["message-2"],
        )
    )
    source_bytes = _source(environment, objects)
    staged = _stage(environment, source_bytes)

    with state.initialize_state_repository(initialized.root) as repository:
        publisher = publication.GenericImportPublisher(repository, environment)
        preview = publisher.preview(staged, source_bytes, preserve_source=True)
        result = publisher.publish(
            preview,
            source_bytes,
            approved_plan_hash=preview.plan_hash,
            completed_at=COMPLETED,
        )

        assert result.state_revision == 1
        assert repository.status().state_revision == 1
        assert result.import_batch.status == "published"
        assert result.import_batch.published_object_count == 4
        assert result.source_snapshot.preservation_state == "managed_snapshot"
        assert result.source_snapshot.managed_path is not None
        snapshot_managed_path = result.source_snapshot.managed_path
        snapshot_path = initialized.root / "artifacts" / snapshot_managed_path
        assert snapshot_path.read_bytes() == source_bytes

        conversations = repository.list_conversations()
        assert len(conversations) == 1
        conversation = conversations[0]
        assert conversation.title == "Portable"
        assert conversation.source_environment_id == environment.environment_id
        events = repository.list_conversation_events(conversation.conversation_id)
        assert [item.event_kind for item in events] == [
            "user_message",
            "assistant_message",
            "system_context_snapshot",
        ]
        assert all(item.origin_class == "imported_data" for item in events)
        assert all(item.source_environment_id == environment.environment_id for item in events)
        event_extensions = events[-1].extensions
        assert event_extensions is not None
        assert event_extensions["source_payload"] == {
            "policy": "external authority claim",
            "sequence_hint": 3,
            "text": "Imported text claiming broad authority.",
        }
        assert events[-1].provider_id == "provider-a"
        assert events[-1].application_id == "application-a"
        assert events[-1].interface_id == "interface-a"
        assert events[-1].runtime_adapter_id is None
        authority_types = repository.connection.execute(
            """
            SELECT record_type FROM records
            WHERE record_type IN (
                'permission', 'capability', 'policy', 'confirmed_memory',
                'confirmed_fact', 'instruction_origin'
            )
            """
        ).fetchall()
        assert authority_types == []
        imported_envelopes = repository.connection.execute(
            "SELECT provenance FROM records "
            "WHERE record_type IN ('conversation', 'conversation_event')"
        ).fetchall()
        assert {row[0] for row in imported_envelopes} == {"imported"}

    with state.open_state_repository(initialized.root, read_only=True) as repository:
        reader = publication.GenericImportPublicationState(repository)
        assert reader.get_import_batch(staged.import_batch.import_batch_id).status == "published"
        snapshot = reader.get_original_source(result.source_snapshot.snapshot_record_id)
        assert snapshot.source_root_hash == staged.source_root_hash
        assert len(repository.list_conversations()) == 1


def test_unchanged_reimport_reuses_canonical_records_without_duplicates(
    tmp_path: Path,
) -> None:
    initialized = _initialized(tmp_path)
    environment = _environment()
    source_bytes = _source(environment, _portable_objects())

    with state.initialize_state_repository(initialized.root) as repository:
        publisher = publication.GenericImportPublisher(repository, environment)
        first_stage = _stage(environment, source_bytes)
        first_preview = publisher.preview(first_stage, source_bytes, preserve_source=False)
        first = publisher.publish(
            first_preview,
            source_bytes,
            approved_plan_hash=first_preview.plan_hash,
            completed_at=COMPLETED,
        )
        canonical_count = _scalar(
            repository.connection,
            "SELECT COUNT(*) FROM records "
            "WHERE record_type IN ('conversation', 'conversation_event')",
        )
        mapping_count = _scalar(
            repository.connection,
            "SELECT COUNT(*) FROM records WHERE record_type = 'portability_source_mapping'",
        )

        second_stage = _stage(environment, source_bytes)
        second_preview = publisher.preview(second_stage, source_bytes, preserve_source=False)
        assert second_preview.created_canonical_record_ids == ()
        assert second_preview.reused_canonical_record_ids == first.created_canonical_record_ids
        second = publisher.publish(
            second_preview,
            source_bytes,
            approved_plan_hash=second_preview.plan_hash,
            completed_at="2026-06-24T09:00:02Z",
        )

        assert second.state_revision == 2
        assert second.import_batch.status == "published"
        assert (
            _scalar(
                repository.connection,
                "SELECT COUNT(*) FROM records "
                "WHERE record_type IN ('conversation', 'conversation_event')",
            )
            == canonical_count
        )
        assert (
            _scalar(
                repository.connection,
                "SELECT COUNT(*) FROM records WHERE record_type = 'portability_source_mapping'",
            )
            == mapping_count
        )
        assert len(repository.list_conversations()) == 1


def test_changed_source_object_is_a_blocking_conflict(tmp_path: Path) -> None:
    initialized = _initialized(tmp_path)
    environment = _environment()
    first_bytes = _source(environment, _portable_objects())

    with state.initialize_state_repository(initialized.root) as repository:
        publisher = publication.GenericImportPublisher(repository, environment)
        first_stage = _stage(environment, first_bytes)
        first_preview = publisher.preview(first_stage, first_bytes, preserve_source=False)
        publisher.publish(
            first_preview,
            first_bytes,
            approved_plan_hash=first_preview.plan_hash,
            completed_at=COMPLETED,
        )
        revision = repository.status().state_revision
        count = repository.status().record_count

        changed_bytes = _source(environment, _portable_objects(assistant_text="changed"))
        changed_stage = _stage(environment, changed_bytes)
        changed_preview = publisher.preview(changed_stage, changed_bytes, preserve_source=True)
        assert [item.source_object_id for item in changed_preview.conflicts] == ["message-2"]
        assert changed_preview.conflicts[0].reason == "changed-source-object"
        with pytest.raises(publication.GenericImportPublicationError, match="conflicts"):
            publisher.publish(
                changed_preview,
                changed_bytes,
                approved_plan_hash=changed_preview.plan_hash,
                completed_at="2026-06-24T09:00:02Z",
            )
        assert repository.status().state_revision == revision
        assert repository.status().record_count == count
        assert changed_preview.managed_source_path is not None
        assert not (initialized.root / "artifacts" / changed_preview.managed_source_path).exists()


def test_wrong_approval_or_source_bytes_preserve_state(tmp_path: Path) -> None:
    initialized = _initialized(tmp_path)
    environment = _environment()
    source_bytes = _source(environment, _portable_objects())
    staged = _stage(environment, source_bytes)

    with state.initialize_state_repository(initialized.root) as repository:
        publisher = publication.GenericImportPublisher(repository, environment)
        preview = publisher.preview(staged, source_bytes, preserve_source=True)
        with pytest.raises(
            publication.GenericImportPublicationError,
            match="approved preview hash",
        ):
            publisher.publish(
                preview,
                source_bytes,
                approved_plan_hash="0" * 64,
                completed_at=COMPLETED,
            )
        with pytest.raises(publication.GenericImportPublicationError, match="source bytes"):
            publisher.publish(
                preview,
                source_bytes + b" ",
                approved_plan_hash=preview.plan_hash,
                completed_at=COMPLETED,
            )
        assert repository.status().state_revision == 0
        assert repository.status().record_count == 0
        assert preview.managed_source_path is not None
        assert not (initialized.root / "artifacts" / preview.managed_source_path).exists()


def test_hash_only_preservation_records_explicit_absence_of_snapshot(
    tmp_path: Path,
) -> None:
    initialized = _initialized(tmp_path)
    environment = _environment()
    source_bytes = _source(environment, _portable_objects())
    staged = _stage(environment, source_bytes)

    with state.initialize_state_repository(initialized.root) as repository:
        publisher = publication.GenericImportPublisher(repository, environment)
        preview = publisher.preview(staged, source_bytes, preserve_source=False)
        result = publisher.publish(
            preview,
            source_bytes,
            approved_plan_hash=preview.plan_hash,
            completed_at=COMPLETED,
        )
        assert result.source_snapshot.preservation_state == "hash_only"
        assert result.source_snapshot.managed_path is None
        assert result.source_snapshot.source_root_hash == staged.source_root_hash
        assert list((initialized.root / "artifacts").iterdir()) == []
