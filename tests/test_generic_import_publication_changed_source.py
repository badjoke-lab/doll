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


def test_changed_source_object_does_not_replace_existing_state(tmp_path: Path) -> None:
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
