from __future__ import annotations

import json
from typing import Any, cast
from uuid import uuid4

import pytest

from doll.generic_import import GenericImportStager, GenericImportStagingError
from doll.portability import (
    AdapterResourceLimits,
    SourceAdapterContract,
    SourceEnvironmentRecord,
)

STARTED = "2026-06-24T03:00:00Z"


def _adapter(
    *,
    environment_class: str = "generic-file-export",
    versions: tuple[str, ...] = ("1",),
    event_types: tuple[str, ...] = ("user-message", "assistant-message"),
    branch_behavior: str = "preserve",
    attachment_behavior: str = "preserve_reference",
    network_behavior: str = "none",
    max_input_bytes: int = 10_000,
    max_object_count: int = 20,
    max_attachment_bytes: int = 1000,
    max_nesting_depth: int = 12,
) -> SourceAdapterContract:
    return SourceAdapterContract(
        adapter_id="generic-import",
        adapter_version="1",
        source_environment_class=environment_class,
        supported_source_versions=versions,
        supported_event_types=event_types,
        attachment_behavior=attachment_behavior,  # type: ignore[arg-type]
        branch_behavior=branch_behavior,  # type: ignore[arg-type]
        resource_limits=AdapterResourceLimits(
            max_input_bytes=max_input_bytes,
            max_object_count=max_object_count,
            max_attachment_bytes=max_attachment_bytes,
            max_nesting_depth=max_nesting_depth,
        ),
        network_behavior=network_behavior,  # type: ignore[arg-type]
    )


def _environment(
    environment_id: str,
    *,
    environment_class: str = "generic-file-export",
    export_format: str | None = None,
    export_version: str | None = "1",
) -> SourceEnvironmentRecord:
    return SourceEnvironmentRecord(
        environment_id=environment_id,
        environment_class=environment_class,
        export_format=export_format,
        export_version=export_version,
    )


def _object(
    source_object_id: str,
    source_type: str = "user-message",
    *,
    parents: list[str] | None = None,
    payload: object | None = None,
) -> dict[str, object]:
    return {
        "source_object_id": source_object_id,
        "source_type": source_type,
        "parent_source_object_ids": parents or [],
        "payload": {"text": "x"} if payload is None else payload,
    }


def _json_source(
    environment_id: str,
    objects: list[object],
    *,
    version: str = "1",
    format_name: str = "doll-generic-import",
) -> bytes:
    return json.dumps(
        {
            "format": format_name,
            "format_version": version,
            "source_environment_id": environment_id,
            "objects": objects,
        },
        separators=(",", ":"),
    ).encode()


def _stage(
    source_bytes: bytes,
    *,
    environment_id: str,
    adapter: SourceAdapterContract | None = None,
    environment: SourceEnvironmentRecord | None = None,
    source_format: str = "json",
):
    stager = GenericImportStager(
        adapter or _adapter(),
        environment or _environment(environment_id),
    )
    return stager.stage(
        source_bytes,
        source_format=cast(Any, source_format),
        import_batch_id=str(uuid4()),
        started_at=STARTED,
    )


def test_stager_rejects_networked_or_mismatched_adapter_context() -> None:
    environment_id = str(uuid4())
    with pytest.raises(GenericImportStagingError, match="network behavior none"):
        GenericImportStager(
            _adapter(network_behavior="declared_read_only"),
            _environment(environment_id),
        )
    with pytest.raises(GenericImportStagingError, match="class does not match"):
        GenericImportStager(
            _adapter(),
            _environment(environment_id, environment_class="other-export"),
        )


def test_stager_rejects_invalid_bytes_format_and_size() -> None:
    environment_id = str(uuid4())
    valid = _json_source(environment_id, [])
    with pytest.raises(GenericImportStagingError, match="source format is invalid"):
        _stage(valid, environment_id=environment_id, source_format="yaml")
    with pytest.raises(GenericImportStagingError, match="must be bytes"):
        GenericImportStager(_adapter(), _environment(environment_id)).stage(
            cast(Any, "not-bytes"),
            source_format="json",
            import_batch_id=str(uuid4()),
            started_at=STARTED,
        )
    with pytest.raises(GenericImportStagingError, match="must not be empty"):
        _stage(b"", environment_id=environment_id)
    with pytest.raises(GenericImportStagingError, match="valid UTF-8"):
        _stage(b"\xff", environment_id=environment_id)
    with pytest.raises(GenericImportStagingError, match="byte limit"):
        _stage(
            valid,
            environment_id=environment_id,
            adapter=_adapter(max_input_bytes=1),
        )


def test_json_envelope_rejects_invalid_structure_and_duplicate_keys() -> None:
    environment_id = str(uuid4())
    with pytest.raises(GenericImportStagingError, match="source envelope is invalid"):
        _stage(b"{", environment_id=environment_id)
    with pytest.raises(GenericImportStagingError, match="must be an object"):
        _stage(b"[]", environment_id=environment_id)
    with pytest.raises(GenericImportStagingError, match="fields are invalid"):
        _stage(
            json.dumps(
                {
                    "format": "doll-generic-import",
                    "format_version": "1",
                    "source_environment_id": environment_id,
                    "objects": [],
                    "unexpected": True,
                }
            ).encode(),
            environment_id=environment_id,
        )
    with pytest.raises(GenericImportStagingError, match="objects must be a list"):
        _stage(
            json.dumps(
                {
                    "format": "doll-generic-import",
                    "format_version": "1",
                    "source_environment_id": environment_id,
                    "objects": {},
                }
            ).encode(),
            environment_id=environment_id,
        )
    duplicate_key = (
        '{"format":"doll-generic-import","format":"other",'
        f'"format_version":"1","source_environment_id":"{environment_id}",'
        '"objects":[]}'
    ).encode()
    with pytest.raises(GenericImportStagingError, match="source envelope is invalid"):
        _stage(duplicate_key, environment_id=environment_id)


def test_manifest_rejects_name_version_and_environment_mismatch() -> None:
    environment_id = str(uuid4())
    with pytest.raises(GenericImportStagingError, match="format name"):
        _stage(
            _json_source(environment_id, [], format_name="other"),
            environment_id=environment_id,
        )
    with pytest.raises(GenericImportStagingError, match="unsupported"):
        _stage(
            _json_source(environment_id, [], version="2"),
            environment_id=environment_id,
        )
    with pytest.raises(GenericImportStagingError, match="identifier does not match"):
        _stage(
            _json_source(str(uuid4()), []),
            environment_id=environment_id,
        )
    with pytest.raises(GenericImportStagingError, match="version does not match"):
        _stage(
            _json_source(environment_id, []),
            environment_id=environment_id,
            environment=_environment(environment_id, export_version="2"),
        )
    with pytest.raises(GenericImportStagingError, match="format does not match"):
        _stage(
            _json_source(environment_id, []),
            environment_id=environment_id,
            environment=_environment(environment_id, export_format="jsonl"),
        )


def test_object_and_nesting_limits_fail_before_result() -> None:
    environment_id = str(uuid4())
    with pytest.raises(GenericImportStagingError, match="object count"):
        _stage(
            _json_source(environment_id, [_object("a"), _object("b")]),
            environment_id=environment_id,
            adapter=_adapter(max_object_count=1),
        )
    nested: object = {"value": 1}
    for _ in range(8):
        nested = {"nested": nested}
    with pytest.raises(GenericImportStagingError, match="nesting"):
        _stage(
            _json_source(environment_id, [_object("a", payload=nested)]),
            environment_id=environment_id,
            adapter=_adapter(max_nesting_depth=4),
        )


def test_malformed_and_unsupported_objects_are_quarantined() -> None:
    environment_id = str(uuid4())
    result = _stage(
        _json_source(
            environment_id,
            [
                "not-an-object",
                _object("bad-payload", payload=[]),
                _object("unsupported", source_type="future-event"),
            ],
        ),
        environment_id=environment_id,
    )

    assert result.import_batch.staged_object_count == 3
    assert result.import_batch.quarantined_object_count == 3
    assert result.mapping_report.malformed_or_quarantined_count == 2
    assert result.mapping_report.unsupported_but_preserved_count == 1
    assert result.mapping_report.material_loss_count == 3
    assert {item.reason for item in result.quarantined_objects} == {
        "source-object-not-an-object",
        "payload-not-an-object",
        "unsupported-source-type",
    }


def test_conflicting_duplicate_quarantines_every_occurrence() -> None:
    environment_id = str(uuid4())
    result = _stage(
        _json_source(
            environment_id,
            [
                _object("same-id", payload={"value": 1}),
                _object("same-id", payload={"value": 2}),
            ],
        ),
        environment_id=environment_id,
    )

    assert result.staged_objects == ()
    assert len(result.quarantined_objects) == 2
    assert result.mapping_report.malformed_or_quarantined_count == 2
    assert result.mapping_report.material_loss_count == 2
    assert {item.reason for item in result.quarantined_objects} == {"conflicting-duplicate"}


def test_missing_parent_cascades_and_cycles_are_quarantined() -> None:
    environment_id = str(uuid4())
    missing = _stage(
        _json_source(
            environment_id,
            [
                _object("child", parents=["missing"]),
                _object("grandchild", parents=["child"]),
            ],
        ),
        environment_id=environment_id,
    )
    assert missing.staged_objects == ()
    assert missing.mapping_report.missing_dependency_count == 2

    cycle = _stage(
        _json_source(
            environment_id,
            [
                _object("a", parents=["b"]),
                _object("b", parents=["a"]),
            ],
        ),
        environment_id=environment_id,
    )
    assert cycle.staged_objects == ()
    assert cycle.mapping_report.malformed_or_quarantined_count == 2
    assert {item.reason for item in cycle.quarantined_objects} == {"cyclic-parent-relationship"}


def test_unsupported_branch_behavior_quarantines_parented_object() -> None:
    environment_id = str(uuid4())
    result = _stage(
        _json_source(
            environment_id,
            [
                _object("root", source_type="conversation"),
                _object("child", parents=["root"]),
            ],
        ),
        environment_id=environment_id,
        adapter=_adapter(branch_behavior="unsupported"),
    )

    assert [item.source_object_id for item in result.staged_objects] == ["root"]
    assert result.mapping_report.unsupported_but_preserved_count == 1
    assert result.quarantined_objects[0].reason == "unsupported-branch-relationship"


def test_duplicate_transformed_objects_share_transformation_status() -> None:
    environment_id = str(uuid4())
    root = _object("root", source_type="conversation")
    child = _object("child", parents=["root"])
    result = _stage(
        _json_source(environment_id, [root, child, child]),
        environment_id=environment_id,
        adapter=_adapter(branch_behavior="linearize_with_loss"),
    )

    assert result.duplicate_object_count == 1
    assert result.mapping_report.total_object_count == 3
    assert result.mapping_report.mapped_without_known_loss_count == 1
    assert result.mapping_report.mapped_with_transformation_count == 2
    assert result.mapping_report.material_loss_count == 2


def test_attachment_payload_limit_is_enforced() -> None:
    environment_id = str(uuid4())
    result = _stage(
        _json_source(
            environment_id,
            [_object("attachment", source_type="attachment", payload={"data": "x" * 50})],
        ),
        environment_id=environment_id,
        adapter=_adapter(max_attachment_bytes=10),
    )

    assert result.staged_objects == ()
    assert result.mapping_report.malformed_or_quarantined_count == 1
    assert result.quarantined_objects[0].reason == "attachment-byte-limit"


def test_jsonl_malformed_object_line_is_quarantined() -> None:
    environment_id = str(uuid4())
    manifest = json.dumps(
        {
            "record_kind": "manifest",
            "format": "doll-generic-import",
            "format_version": "1",
            "source_environment_id": environment_id,
        }
    )
    valid = json.dumps({"record_kind": "object", **_object("valid")})
    source = f"{manifest}\n{{bad json\n{valid}\n".encode()

    result = _stage(
        source,
        environment_id=environment_id,
        source_format="jsonl",
    )

    assert [item.source_object_id for item in result.staged_objects] == ["valid"]
    assert result.mapping_report.malformed_or_quarantined_count == 1
    assert result.quarantined_objects[0].reason == "malformed-jsonl-object"


def test_jsonl_manifest_is_strict() -> None:
    environment_id = str(uuid4())
    with pytest.raises(GenericImportStagingError, match="must not be empty"):
        _stage(b"", environment_id=environment_id, source_format="jsonl")
    with pytest.raises(GenericImportStagingError, match="first record"):
        _stage(
            json.dumps(
                {
                    "record_kind": "object",
                    "format": "doll-generic-import",
                    "format_version": "1",
                    "source_environment_id": environment_id,
                }
            ).encode(),
            environment_id=environment_id,
            source_format="jsonl",
        )
