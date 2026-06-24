from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import doll.generic_import_publication as publication
import pytest
from doll import state
from import_publication_support import (
    COMPLETED,
    _environment,
    _initialized,
    _object,
    _portable_objects,
    _source,
    _stage,
)


def test_preview_rejects_invalid_context_and_payload_shapes(tmp_path: Path) -> None:
    initialized = _initialized(tmp_path)
    environment = _environment()
    source_bytes = _source(environment, _portable_objects())
    staged = _stage(environment, source_bytes)

    with state.initialize_state_repository(initialized.root) as repository:
        publisher = publication.GenericImportPublisher(repository, environment)
        with pytest.raises(publication.GenericImportPublicationError, match="stage result"):
            publisher.preview(cast(Any, object()), source_bytes, preserve_source=False)
        with pytest.raises(publication.GenericImportPublicationError, match="non-empty bytes"):
            publisher.preview(staged, cast(Any, "text"), preserve_source=False)
        with pytest.raises(publication.GenericImportPublicationError, match="non-empty bytes"):
            publisher.preview(staged, b"", preserve_source=False)
        with pytest.raises(publication.GenericImportPublicationError, match="boolean"):
            publisher.preview(staged, source_bytes, preserve_source=cast(Any, 1))

        other_environment = _environment()
        other_publisher = publication.GenericImportPublisher(repository, other_environment)
        with pytest.raises(publication.GenericImportPublicationError, match="source environment"):
            other_publisher.preview(staged, source_bytes, preserve_source=False)

        bad_batch = replace(
            staged.import_batch,
            status="published",
            completed_at=COMPLETED,
            published_object_count=staged.import_batch.staged_object_count,
        )
        with pytest.raises(publication.GenericImportPublicationError, match="not staged"):
            publisher.preview(
                replace(staged, import_batch=bad_batch),
                source_bytes,
                preserve_source=False,
            )

        wrong_report = replace(staged.mapping_report, batch_id=str(uuid4()))
        with pytest.raises(publication.GenericImportPublicationError, match="mapping report"):
            publisher.preview(
                replace(staged, mapping_report=wrong_report),
                source_bytes,
                preserve_source=False,
            )

        export_report = replace(staged.mapping_report, direction="export")
        with pytest.raises(publication.GenericImportPublicationError, match="direction"):
            publisher.preview(
                replace(staged, mapping_report=export_report),
                source_bytes,
                preserve_source=False,
            )


def test_preview_rejects_invalid_conversation_and_event_metadata(tmp_path: Path) -> None:
    initialized = _initialized(tmp_path)
    environment = _environment()
    cases = [
        [_object("conversation", "conversation", {"title": 1})],
        [
            _object("root", "conversation", {}),
            _object("child", "conversation", {}, parents=["root"]),
        ],
        [
            _object("root", "conversation", {}),
            _object(
                "event",
                "user-message",
                {"occurred_at": 1},
                parents=["root"],
            ),
        ],
        [
            _object("root", "conversation", {}),
            _object(
                "event",
                "user-message",
                {"sequence_hint": True},
                parents=["root"],
            ),
        ],
    ]

    with state.initialize_state_repository(initialized.root) as repository:
        publisher = publication.GenericImportPublisher(repository, environment)
        for objects in cases:
            source_bytes = _source(environment, objects)
            staged = _stage(environment, source_bytes)
            with pytest.raises(publication.GenericImportPublicationError):
                publisher.preview(staged, source_bytes, preserve_source=False)


def test_mapping_conflict_reasons_are_explicit() -> None:
    environment = _environment()
    source_bytes = _source(environment, _portable_objects())
    staged = _stage(environment, source_bytes)
    source = staged.staged_objects[0]
    mapping = publication.SourceObjectMappingRecord(
        mapping_id=str(uuid4()),
        source_environment_id=environment.environment_id,
        adapter_id=staged.import_batch.adapter_id,
        adapter_version=staged.import_batch.adapter_version,
        source_object_id=source.source_object_id,
        source_type=source.source_type,
        source_hash=source.source_hash,
        payload_json=source.payload_json,
        canonical_record_id=str(uuid4()),
        canonical_record_type="conversation",
        first_import_batch_id=staged.import_batch.import_batch_id,
    )
    canonical_id = mapping.canonical_record_id

    assert (
        publication._mapping_conflict_reason(
            replace(mapping, source_environment_id=str(uuid4())),
            staged,
            source,
            canonical_id,
            "conversation",
        )
        == "source-environment-mismatch"
    )
    assert (
        publication._mapping_conflict_reason(
            replace(mapping, adapter_id="other"),
            staged,
            source,
            canonical_id,
            "conversation",
        )
        == "source-adapter-mismatch"
    )
    assert (
        publication._mapping_conflict_reason(
            replace(mapping, adapter_version="2"),
            staged,
            source,
            canonical_id,
            "conversation",
        )
        == "source-adapter-version-mismatch"
    )
    assert (
        publication._mapping_conflict_reason(
            replace(mapping, source_object_id="other"),
            staged,
            source,
            canonical_id,
            "conversation",
        )
        == "source-identity-mismatch"
    )
    assert (
        publication._mapping_conflict_reason(
            replace(mapping, source_hash="1" * 64),
            staged,
            source,
            canonical_id,
            "conversation",
        )
        == "changed-source-object"
    )
    assert (
        publication._mapping_conflict_reason(
            replace(mapping, payload_json='{"changed":true}'),
            staged,
            source,
            canonical_id,
            "conversation",
        )
        == "changed-source-payload"
    )
    assert (
        publication._mapping_conflict_reason(
            mapping,
            staged,
            source,
            str(uuid4()),
            "conversation",
        )
        == "canonical-mapping-mismatch"
    )
    assert (
        publication._mapping_conflict_reason(
            mapping,
            staged,
            source,
            canonical_id,
            "conversation",
        )
        is None
    )


def test_internal_validation_helpers_fail_closed() -> None:
    assert publication._event_contract("user-message") == ("user_message", "user")
    assert publication._event_contract("other") == ("imported_unknown_event", "unknown")
    assert publication._count({"value": 1}, "value") == 1
    assert publication._string_tuple(["a", "b"], "values") == ("a", "b")
    assert publication._load_json_object('{"a":1}', "fixture") == {"a": 1}
    assert len(publication._hash_json({"a": 1})) == 64

    with pytest.raises(state.StateCorruptError, match="count"):
        publication._count({"value": True}, "value")
    with pytest.raises(state.StateCorruptError, match="invalid"):
        publication._string_tuple([1], "values")
    with pytest.raises(publication.GenericImportPublicationError, match="invalid JSON"):
        publication._load_json_object("{", "fixture")
    with pytest.raises(publication.GenericImportPublicationError, match="must be an object"):
        publication._load_json_object("[]", "fixture")
    with pytest.raises(publication.GenericImportPublicationError, match="canonical JSON"):
        publication._hash_json({"value": object()})
    with pytest.raises(publication.GenericImportPublicationError, match="must be text"):
        publication._canonical_uuid("identifier", 1)
    with pytest.raises(publication.GenericImportPublicationError, match="is invalid"):
        publication._canonical_uuid("identifier", "bad")
    with pytest.raises(publication.GenericImportPublicationError, match="canonical UUID"):
        publication._canonical_uuid("identifier", str(uuid4()).upper())
    with pytest.raises(publication.GenericImportPublicationError, match="hash"):
        publication._validate_sha256("hash", "bad")
    with pytest.raises(publication.GenericImportPublicationError, match="text"):
        publication._validate_text("text", "")
