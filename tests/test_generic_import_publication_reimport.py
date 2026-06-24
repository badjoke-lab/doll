from __future__ import annotations

from pathlib import Path

import doll.generic_import_publication as publication
from doll import state
from tests.import_publication_support import (
    COMPLETED,
    _environment,
    _initialized,
    _portable_objects,
    _scalar,
    _source,
    _stage,
)


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
