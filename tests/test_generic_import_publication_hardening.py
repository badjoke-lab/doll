from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import pytest

import doll.generic_import_publication as publication
from doll import state
from doll.portability import PortabilityState
from tests.import_publication_support import (
    COMPLETED,
    _environment,
    _initialized,
    _object,
    _portable_objects,
    _source,
    _stage,
)


def _publish(
    repository: state.StateRepository,
    environment: Any,
    source_bytes: bytes,
    *,
    preserve_source: bool = False,
) -> tuple[
    publication.GenericImportPublisher,
    Any,
    publication.GenericImportPublicationResult,
]:
    staged = _stage(environment, source_bytes)
    publisher = publication.GenericImportPublisher(repository, environment)
    preview = publisher.preview(staged, source_bytes, preserve_source=preserve_source)
    result = publisher.publish(
        preview,
        source_bytes,
        approved_plan_hash=preview.plan_hash,
        completed_at=COMPLETED,
    )
    return publisher, staged, result


def _set_metadata(
    repository: state.StateRepository,
    record_id: str,
    metadata: dict[str, object],
) -> None:
    metadata_json = json.dumps(
        metadata,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    repository.connection.execute(
        "UPDATE records SET metadata_json = ? WHERE id = ?",
        (metadata_json, record_id),
    )


def test_publication_record_contracts_fail_closed() -> None:
    base_mapping = dict(
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
    for changes in (
        {"canonical_record_type": "other"},
        {"authority_class": "trusted"},
        {"payload_json": "[]"},
        {"payload_json": "{"},
        {"source_hash": "bad"},
        {"adapter_id": ""},
    ):
        values = dict(base_mapping)
        values.update(changes)
        with pytest.raises(publication.GenericImportPublicationError):
            publication.SourceObjectMappingRecord(**cast(Any, values))

    quarantine = dict(
        quarantine_id=str(uuid4()),
        import_batch_id=str(uuid4()),
        input_index=0,
        source_object_id=None,
        source_hash="0" * 64,
        reason="invalid-object",
    )
    for changes in (
        {"input_index": True},
        {"input_index": -1},
        {"source_object_id": ""},
        {"source_hash": "bad"},
        {"reason": ""},
        {"authority_class": "trusted"},
    ):
        values = dict(quarantine)
        values.update(changes)
        with pytest.raises(publication.GenericImportPublicationError):
            publication.ImportQuarantineRecord(**cast(Any, values))

    snapshot = dict(
        snapshot_record_id=str(uuid4()),
        import_batch_id=str(uuid4()),
        source_root_hash="0" * 64,
        source_format="json",
        preservation_state="hash_only",
        managed_path=None,
        size_bytes=1,
    )
    for changes in (
        {"source_format": "archive"},
        {"preservation_state": "other"},
        {"size_bytes": True},
        {"size_bytes": 0},
        {"preservation_state": "managed_snapshot", "managed_path": None},
        {"managed_path": "source.json"},
        {"authority_class": "trusted"},
    ):
        values = dict(snapshot)
        values.update(changes)
        with pytest.raises(publication.GenericImportPublicationError):
            publication.OriginalSourceSnapshotRecord(**cast(Any, values))


def test_internal_validation_helpers_reject_noncanonical_values() -> None:
    assert publication._count({"value": 1}, "value") == 1
    assert publication._string_tuple(["a", "b"], "values") == ("a", "b")
    assert publication._load_json_object('{"a":1}', "fixture") == {"a": 1}
    assert publication._event_contract("user-message") == ("user_message", "user")
    assert publication._event_contract("other") == ("imported_unknown_event", "unknown")
    assert publication._hash_json({"a": 1}) == hashlib.sha256(b'{"a":1}').hexdigest()

    with pytest.raises(state.StateCorruptError, match="count"):
        publication._count({"value": True}, "value")
    with pytest.raises(state.StateCorruptError, match="invalid"):
        publication._string_tuple([1], "values")
    with pytest.raises(publication.GenericImportPublicationError, match="invalid JSON"):
        publication._load_json_object("{", "fixture")
    with pytest.raises(publication.GenericImportPublicationError, match="must be an object"):
        publication._load_json_object("[]", "fixture")
    with pytest.raises(publication.GenericImportPublicationError, match="invalid JSON"):
        publication._load_json_object('{"value":NaN}', "fixture")
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
    with pytest.raises(publication.GenericImportPublicationError, match="text"):
        publication._validate_text("text", "x" * 5, maximum=4)


def test_preview_rejects_invalid_stage_and_payload_metadata(tmp_path: Path) -> None:
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

        duplicate = replace(staged, staged_objects=(staged.staged_objects[0],) * 2)
        with pytest.raises(publication.GenericImportPublicationError, match="duplicates"):
            publisher.preview(duplicate, source_bytes, preserve_source=False)

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

        small_publisher = publication.GenericImportPublisher(
            repository,
            environment,
            max_snapshot_bytes=10,
        )
        with pytest.raises(publication.GenericImportPublicationError, match="byte limit"):
            small_publisher.preview(staged, source_bytes, preserve_source=False)

        cases = [
            [_object("conversation", "conversation", {"title": 1})],
            [
                _object("root", "conversation", {}),
                _object("child", "conversation", {}, parents=["root"]),
            ],
            [
                _object("root", "conversation", {}),
                _object("event", "user-message", {"occurred_at": 1}, parents=["root"]),
            ],
            [
                _object("root", "conversation", {}),
                _object("event", "user-message", {"sequence_hint": True}, parents=["root"]),
            ],
        ]
        for objects in cases:
            invalid_bytes = _source(environment, objects)
            invalid_stage = _stage(environment, invalid_bytes)
            with pytest.raises(publication.GenericImportPublicationError):
                publisher.preview(invalid_stage, invalid_bytes, preserve_source=False)


def test_preview_detects_environment_and_canonical_state_conflicts(
    tmp_path: Path,
) -> None:
    initialized = _initialized(tmp_path)
    environment = _environment()
    source_bytes = _source(environment, _portable_objects())
    staged = _stage(environment, source_bytes)

    with state.initialize_state_repository(initialized.root) as repository:
        PortabilityState(repository).save_source_environment(environment)
        changed_environment = replace(environment, provider_id="provider-b")
        changed_bytes = _source(changed_environment, _portable_objects())
        changed_stage = _stage(changed_environment, changed_bytes)
        with pytest.raises(publication.GenericImportPublicationError, match="does not match"):
            publication.GenericImportPublisher(repository, changed_environment).preview(
                changed_stage,
                changed_bytes,
                preserve_source=False,
            )

    initialized = _initialized(tmp_path / "canonical")
    with state.initialize_state_repository(initialized.root) as repository:
        conversation = staged.staged_objects[0]
        canonical_id = publication._canonical_record_id(
            environment.environment_id,
            conversation,
        )
        repository.create_record(
            record_id=canonical_id,
            record_type="conversation",
            provenance="imported",
            sensitivity="personal",
            title="Existing",
            metadata={
                "source_environment_id": environment.environment_id,
                "source_conversation_id": conversation.source_object_id,
            },
        )
        preview = publication.GenericImportPublisher(repository, environment).preview(
            staged,
            source_bytes,
            preserve_source=False,
        )
        assert preview.conflicts[0].reason == (
            "canonical-record-id-already-exists-without-source-mapping"
        )


def test_stale_preview_and_corrupt_existing_mapping_fail_closed(tmp_path: Path) -> None:
    initialized = _initialized(tmp_path)
    environment = _environment()
    source_bytes = _source(environment, _portable_objects())

    with state.initialize_state_repository(initialized.root) as repository:
        publisher = publication.GenericImportPublisher(repository, environment)
        first_stage = _stage(environment, source_bytes)
        stale_preview = publisher.preview(first_stage, source_bytes, preserve_source=False)
        second_stage = _stage(environment, source_bytes)
        second_preview = publisher.preview(second_stage, source_bytes, preserve_source=False)
        publisher.publish(
            second_preview,
            source_bytes,
            approved_plan_hash=second_preview.plan_hash,
            completed_at=COMPLETED,
        )
        with pytest.raises(publication.GenericImportPublicationError, match="stale"):
            publisher.publish(
                stale_preview,
                source_bytes,
                approved_plan_hash=stale_preview.plan_hash,
                completed_at="2026-06-24T09:00:02Z",
            )

        mapping_row = repository.connection.execute(
            "SELECT metadata_json FROM records "
            "WHERE record_type = 'portability_source_mapping' "
            "AND json_extract(metadata_json, '$.canonical_record_type') = 'conversation'"
        ).fetchone()
        assert mapping_row is not None
        mapping_metadata = json.loads(cast(str, mapping_row[0]))
        canonical_id = cast(str, mapping_metadata["canonical_record_id"])
        repository.connection.execute(
            "UPDATE records SET record_type = 'other' WHERE id = ?",
            (canonical_id,),
        )
        third_stage = _stage(environment, source_bytes)
        with pytest.raises(state.StateCorruptError, match="wrong canonical"):
            publisher.preview(third_stage, source_bytes, preserve_source=False)

        repository.connection.execute(
            "UPDATE records SET record_type = 'conversation', provenance = 'user-created' "
            "WHERE id = ?",
            (canonical_id,),
        )
        with pytest.raises(state.StateCorruptError, match="non-imported"):
            publisher.preview(third_stage, source_bytes, preserve_source=False)


def test_reader_rejects_corrupt_reports_envelopes_and_snapshot(tmp_path: Path) -> None:
    initialized = _initialized(tmp_path)
    environment = _environment()
    source_bytes = _source(
        environment,
        [
            _object("conversation-1", "conversation", {"title": "Partial"}),
            _object("unsupported-1", "unknown-object", {"value": 1}),
        ],
    )

    with state.initialize_state_repository(initialized.root) as repository:
        _, staged, result = _publish(
            repository,
            environment,
            source_bytes,
            preserve_source=True,
        )
        reader = publication.GenericImportPublicationState(repository)

        report_id = staged.mapping_report.mapping_report_id
        report_envelope = repository.get_record(report_id)
        bad_counts = dict(report_envelope.metadata)
        bad_counts["mapping_counts"] = "bad"
        _set_metadata(repository, report_id, bad_counts)
        with pytest.raises(state.StateCorruptError, match="counts"):
            reader.get_mapping_report(report_id)

        bad_fidelity = dict(report_envelope.metadata)
        bad_fidelity["full_fidelity_possible"] = not staged.mapping_report.full_fidelity_possible
        _set_metadata(repository, report_id, bad_fidelity)
        with pytest.raises(state.StateCorruptError, match="fidelity"):
            reader.get_mapping_report(report_id)
        _set_metadata(repository, report_id, report_envelope.metadata)

        loss_id = staged.loss_records[0].loss_record_id
        loss_envelope = repository.get_record(loss_id)
        bad_material = dict(loss_envelope.metadata)
        bad_material["is_material"] = not staged.loss_records[0].is_material
        _set_metadata(repository, loss_id, bad_material)
        with pytest.raises(state.StateCorruptError, match="materiality"):
            reader.get_loss(loss_id)
        _set_metadata(repository, loss_id, loss_envelope.metadata)

        batch_id = staged.import_batch.import_batch_id
        batch_envelope = repository.get_record(batch_id)
        bad_shape = dict(batch_envelope.metadata)
        bad_shape.pop("status")
        _set_metadata(repository, batch_id, bad_shape)
        with pytest.raises(state.StateCorruptError, match="shape"):
            reader.get_import_batch(batch_id)
        _set_metadata(repository, batch_id, batch_envelope.metadata)

        repository.connection.execute(
            "UPDATE records SET record_type = 'other' WHERE id = ?",
            (batch_id,),
        )
        with pytest.raises(state.StateCorruptError, match="not a supported"):
            reader.get_import_batch(batch_id)
        repository.connection.execute(
            "UPDATE records SET record_type = 'portability_import_batch' WHERE id = ?",
            (batch_id,),
        )

        managed_path = result.source_snapshot.managed_path
        assert managed_path is not None
        (initialized.root / "artifacts" / managed_path).write_bytes(b"tampered")
        with pytest.raises(state.StateCorruptError, match="source"):
            reader.get_original_source(result.source_snapshot.snapshot_record_id)


def test_all_quarantined_import_is_persisted_as_rejected(tmp_path: Path) -> None:
    initialized = _initialized(tmp_path)
    environment = _environment()
    source_bytes = _source(
        environment,
        [_object("unsupported-1", "unknown-object", {"value": 1})],
    )

    with state.initialize_state_repository(initialized.root) as repository:
        _, staged, result = _publish(repository, environment, source_bytes)
        assert result.import_batch.status == "rejected"
        assert result.import_batch.published_object_count == 0
        assert staged.import_batch.quarantined_object_count == 1
        assert repository.list_conversations() == ()
