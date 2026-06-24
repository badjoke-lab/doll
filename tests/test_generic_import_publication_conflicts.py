from __future__ import annotations

from pathlib import Path

import pytest

import doll.generic_import_publication as publication
from doll import state
from tests.import_publication_support import (
    COMPLETED,
    _environment,
    _initialized,
    _portable_objects,
    _source,
    _stage,
)


def test_modified_source_yields_conflict_without_state_change(tmp_path: Path) -> None:
    initialized = _initialized(tmp_path)
    environment = _environment()
    source_bytes = _source(environment, _portable_objects())

    with state.initialize_state_repository(initialized.root) as repository:
        publisher = publication.GenericImportPublisher(repository, environment)
        staged = _stage(environment, source_bytes)
        preview = publisher.preview(staged, source_bytes, preserve_source=False)
        publisher.publish(
            preview,
            source_bytes,
            approved_plan_hash=preview.plan_hash,
            completed_at=COMPLETED,
        )
        revision = repository.status().state_revision
        record_count = repository.status().record_count

        modified_bytes = _source(environment, _portable_objects(assistant_text="modified"))
        modified_stage = _stage(environment, modified_bytes)
        modified_preview = publisher.preview(
            modified_stage,
            modified_bytes,
            preserve_source=False,
        )
        assert [item.source_object_id for item in modified_preview.conflicts] == ["message-2"]
        assert modified_preview.conflicts[0].reason == "changed-source-object"
        with pytest.raises(publication.GenericImportPublicationError, match="conflicts"):
            publisher.publish(
                modified_preview,
                modified_bytes,
                approved_plan_hash=modified_preview.plan_hash,
                completed_at="2026-06-24T09:00:02Z",
            )
        assert repository.status().state_revision == revision
        assert repository.status().record_count == record_count
