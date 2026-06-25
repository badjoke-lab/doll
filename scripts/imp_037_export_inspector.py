"""Inspect one generic export with the Python standard library only."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

_FILE_NAMES = {
    "checksums.sha256",
    "manifest.json",
    "records.json",
    "records.jsonl",
    "transcript.md",
}
_PAYLOAD_NAMES = {"manifest.json", "records.json", "records.jsonl", "transcript.md"}
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_MAX_FILE_BYTES = 64 * 1024 * 1024


def _digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _load_json_object(content: bytes, name: str) -> dict[str, Any]:
    value = json.loads(content.decode("utf-8", errors="strict"))
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def _read_files(root: Path) -> dict[str, bytes]:
    if not root.is_dir() or root.is_symlink():
        raise ValueError("export root is invalid")
    entries = tuple(root.iterdir())
    if {item.name for item in entries} != _FILE_NAMES:
        raise ValueError("export file set is invalid")
    result: dict[str, bytes] = {}
    for item in entries:
        if item.is_symlink() or not item.is_file():
            raise ValueError("export member is invalid")
        content = item.read_bytes()
        if not content or len(content) > _MAX_FILE_BYTES:
            raise ValueError("export member size is invalid")
        result[item.name] = content
    return result


def _parse_checksums(content: bytes) -> dict[str, str]:
    declarations: dict[str, str] = {}
    for line in content.decode("ascii", errors="strict").splitlines():
        digest, separator, name = line.partition("  ")
        if (
            not separator
            or not _SHA256.fullmatch(digest)
            or name not in _PAYLOAD_NAMES
            or name in declarations
        ):
            raise ValueError("checksum declaration is invalid")
        declarations[name] = digest
    if set(declarations) != _PAYLOAD_NAMES:
        raise ValueError("checksum declarations are incomplete")
    return declarations


def _jsonl_records(content: bytes, export_batch_id: str) -> list[dict[str, Any]]:
    lines = content.decode("utf-8", errors="strict").splitlines()
    if len(lines) < 2:
        raise ValueError("records JSONL is incomplete")
    manifest = json.loads(lines[0])
    if not isinstance(manifest, dict):
        raise ValueError("records JSONL manifest is invalid")
    if manifest != {
        "record_kind": "manifest",
        "format": "doll-generic-export",
        "format_version": "1",
        "export_batch_id": export_batch_id,
    }:
        raise ValueError("records JSONL manifest does not match export")
    records: list[dict[str, Any]] = []
    for line in lines[1:]:
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError("records JSONL member is invalid")
        records.append(value)
    return records


def _record_checks(records: list[dict[str, Any]]) -> dict[str, bool]:
    conversations = [item for item in records if item.get("record_kind") == "conversation"]
    events = [item for item in records if item.get("record_kind") == "conversation_event"]
    if len(conversations) != 1 or len(events) != 3:
        raise ValueError("exported record counts are invalid")
    conversation_metadata = conversations[0].get("metadata")
    if not isinstance(conversation_metadata, dict):
        raise ValueError("conversation metadata is invalid")
    event_metadata = [item.get("metadata") for item in events]
    if not all(isinstance(item, dict) for item in event_metadata):
        raise ValueError("event metadata is invalid")
    typed_events = [item for item in event_metadata if isinstance(item, dict)]
    identity_separate = all(
        item.get("source_environment_id") == "11111111-1111-4111-8111-111111111111"
        and item.get("provider_id") == "provider-a"
        and item.get("application_id") == "application-a"
        and item.get("interface_id") == "interface-a"
        and isinstance(item.get("source_object_id"), str)
        and item.get("origin_class") == "imported_data"
        for item in typed_events
    )
    runtime_preserved = all(
        isinstance(item.get("extensions"), dict)
        and item["extensions"].get("source_runtime_id") == "runtime-a"
        for item in typed_events
    )
    return {
        "canonical_conversation_present": len(conversations) == 1,
        "canonical_events_present": len(events) == 3,
        "source_identity_fields_separate": identity_separate,
        "source_runtime_identity_preserved": runtime_preserved,
        "conversation_source_identity_preserved": (
            conversation_metadata.get("source_environment_id")
            == "11111111-1111-4111-8111-111111111111"
            and conversation_metadata.get("source_conversation_id") == "conversation-1"
        ),
    }


def inspect_export(root: Path) -> dict[str, bool]:
    files = _read_files(root)
    checksums = _parse_checksums(files["checksums.sha256"])
    checksums_valid = all(checksums[name] == _digest(files[name]) for name in _PAYLOAD_NAMES)
    if not checksums_valid:
        raise ValueError("checksum mismatch")

    manifest = _load_json_object(files["manifest.json"], "manifest")
    export_batch_id = manifest.get("export_batch_id")
    if not isinstance(export_batch_id, str):
        raise ValueError("export batch identifier is invalid")
    records_document = _load_json_object(files["records.json"], "records JSON")
    records = records_document.get("records")
    if not isinstance(records, list) or not all(isinstance(item, dict) for item in records):
        raise ValueError("records JSON is invalid")
    typed_records = [item for item in records if isinstance(item, dict)]
    jsonl_records = _jsonl_records(files["records.jsonl"], export_batch_id)
    transcript = files["transcript.md"].decode("utf-8", errors="strict")

    expected_counts = {"conversation": 1, "conversation_event": 3, "total": 4}
    authority_note = manifest.get("authority_note")
    manifest_files = manifest.get("files")
    if not isinstance(manifest_files, list):
        raise ValueError("manifest file declarations are invalid")
    declared = {
        item.get("name"): item
        for item in manifest_files
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    declared_payloads_valid = set(declared) == {
        "records.json",
        "records.jsonl",
        "transcript.md",
    } and all(
        item.get("size_bytes") == len(files[name])
        and item.get("sha256") == _digest(files[name])
        for name, item in declared.items()
    )

    checks = {
        "exact_export_file_set": set(files) == _FILE_NAMES,
        "checksums_valid": checksums_valid,
        "manifest_format_valid": (
            manifest.get("format") == "doll-generic-export"
            and manifest.get("format_version") == "1"
        ),
        "manifest_counts_valid": manifest.get("object_counts") == expected_counts,
        "manifest_payload_declarations_valid": declared_payloads_valid,
        "json_and_jsonl_records_match": typed_records == jsonl_records,
        "transcript_is_non_authoritative": (
            transcript.startswith("# Doll Generic Conversation Export\n")
            and "Non-authoritative inspectable view" in transcript
            and "Content references are not executed." in transcript
        ),
        "authority_note_present": (
            isinstance(authority_note, str)
            and "does not grant policy" in authority_note
            and "instruction authority" in authority_note
        ),
        **_record_checks(typed_records),
    }
    if not all(checks.values()):
        raise ValueError("export inspection failed")
    return checks


def main() -> int:
    if len(sys.argv) != 2:
        return 2
    try:
        checks = inspect_export(Path(sys.argv[1]))
    except BaseException as exc:
        print(
            json.dumps(
                {
                    "result": "fail",
                    "error_stage": "export_inspection",
                    "error_class": type(exc).__name__,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 2
    print(
        json.dumps(
            {"result": "pass", "checks": checks},
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
