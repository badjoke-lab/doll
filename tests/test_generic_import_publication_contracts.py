from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import pytest

import doll.generic_import_publication as publication
from doll import state
from tests.import_publication_support import (
    _environment,
    _initialized,
)


def _mapping() -> publication.SourceObjectMappingRecord:
    return publication.SourceObjectMappingRecord(
        mapping_id=str(uuid4()),
        source_environment_id=str(uuid4()),
        adapter_id="adapter",
        adapter_version="1",
        source_object_id="source-1",
        source_type="conversation",
        source_hash="0" * 64,
        payload_json="{}",
        canonical_record_id=str(uuid4()),
        canonical_record_type="conversation",
        first_import_batch_id=str(uuid4()),
    )


def _quarantine() -> publication.ImportQuarantineRecord:
    return publication.ImportQuarantineRecord(
        quarantine_id=str(uuid4()),
        import_batch_id=str(uuid4()),
        input_index=0,
        source_object_id=None,
        source_hash="0" * 64,
        reason="invalid-object",
    )


def _snapshot() -> publication.OriginalSourceSnapshotRecord:
    return publication.OriginalSourceSnapshotRecord(
        snapshot_record_id=str(uuid4()),
        import_batch_id=str(uuid4()),
        source_root_hash="0" * 64,
        source_format="json",
        preservation_state="hash_only",
        managed_path=None,
        size_bytes=1,
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"canonical_record_type": "other"},
        {"authority_class": "trusted"},
        {"payload_json": "[]"},
        {"payload_json": "{"},
        {"source_hash": "bad"},
    ],
)
def test_source_mapping_contract_rejects_invalid_values(changes: dict[str, object]) -> None:
    with pytest.raises(publication.GenericImportPublicationError):
        replace(_mapping(), **cast(Any, changes))


@pytest.mark.parametrize(
    "changes",
    [
        {"input_index": True},
        {"input_index": -1},
        {"source_object_id": ""},
        {"source_hash": "bad"},
        {"reason": ""},
        {"authority_class": "trusted"},
    ],
)
def test_quarantine_contract_rejects_invalid_values(changes: dict[str, object]) -> None:
    with pytest.raises(publication.GenericImportPublicationError):
        replace(_quarantine(), **cast(Any, changes))


@pytest.mark.parametrize(
    "changes",
    [
        {"source_format": "archive"},
        {"preservation_state": "other"},
        {"size_bytes": True},
        {"size_bytes": 0},
        {"preservation_state": "managed_snapshot", "managed_path": None},
        {"managed_path": "unexpected.json"},
        {"authority_class": "trusted"},
    ],
)
def test_source_snapshot_contract_rejects_invalid_values(changes: dict[str, object]) -> None:
    with pytest.raises(publication.GenericImportPublicationError):
        replace(_snapshot(), **cast(Any, changes))


@pytest.mark.parametrize("limit", [0, True, -1])
def test_publisher_rejects_invalid_snapshot_limits(tmp_path: Path, limit: object) -> None:
    initialized = _initialized(tmp_path)
    with state.initialize_state_repository(initialized.root) as repository:
        with pytest.raises(publication.GenericImportPublicationError, match="snapshot byte"):
            publication.GenericImportPublisher(
                repository,
                _environment(),
                max_snapshot_bytes=cast(Any, limit),
            )
