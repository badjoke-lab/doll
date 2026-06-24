from __future__ import annotations

from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import pytest

import doll.generic_import_publication as publication
from doll import state
from tests.import_publication_support import _environment, _initialized


def _mapping_kwargs() -> dict[str, object]:
    return {
        "mapping_id": str(uuid4()),
        "source_environment_id": str(uuid4()),
        "adapter_id": "adapter",
        "adapter_version": "1",
        "source_object_id": "source-1",
        "source_type": "conversation",
        "source_hash": "0" * 64,
        "payload_json": "{}",
        "canonical_record_id": str(uuid4()),
        "canonical_record_type": "conversation",
        "first_import_batch_id": str(uuid4()),
    }


def test_source_mapping_rejects_invalid_record_type() -> None:
    values = _mapping_kwargs()
    values["canonical_record_type"] = "other"
    with pytest.raises(publication.GenericImportPublicationError, match="record type"):
        publication.SourceObjectMappingRecord(**cast(Any, values))


def test_source_mapping_rejects_invalid_payload_and_hash() -> None:
    values = _mapping_kwargs()
    values["payload_json"] = "[]"
    with pytest.raises(publication.GenericImportPublicationError, match="object"):
        publication.SourceObjectMappingRecord(**cast(Any, values))
    values = _mapping_kwargs()
    values["source_hash"] = "bad"
    with pytest.raises(publication.GenericImportPublicationError, match="source hash"):
        publication.SourceObjectMappingRecord(**cast(Any, values))


def test_quarantine_rejects_invalid_index() -> None:
    with pytest.raises(publication.GenericImportPublicationError, match="input index"):
        publication.ImportQuarantineRecord(
            quarantine_id=str(uuid4()),
            import_batch_id=str(uuid4()),
            input_index=-1,
            source_object_id=None,
            source_hash="0" * 64,
            reason="invalid-object",
        )


def test_source_snapshot_requires_consistent_path_state() -> None:
    with pytest.raises(publication.GenericImportPublicationError, match="path is required"):
        publication.OriginalSourceSnapshotRecord(
            snapshot_record_id=str(uuid4()),
            import_batch_id=str(uuid4()),
            source_root_hash="0" * 64,
            source_format="json",
            preservation_state="managed_snapshot",
            managed_path=None,
            size_bytes=1,
        )
    with pytest.raises(publication.GenericImportPublicationError, match="hash-only"):
        publication.OriginalSourceSnapshotRecord(
            snapshot_record_id=str(uuid4()),
            import_batch_id=str(uuid4()),
            source_root_hash="0" * 64,
            source_format="json",
            preservation_state="hash_only",
            managed_path="source.json",
            size_bytes=1,
        )


def test_publisher_rejects_invalid_snapshot_limit(tmp_path: Path) -> None:
    initialized = _initialized(tmp_path)
    with state.initialize_state_repository(initialized.root) as repository:
        with pytest.raises(publication.GenericImportPublicationError, match="snapshot byte"):
            publication.GenericImportPublisher(
                repository,
                _environment(),
                max_snapshot_bytes=cast(Any, 0),
            )
