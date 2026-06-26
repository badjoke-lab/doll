"""Inspect a Resume Bundle using only the Python standard library."""

from __future__ import annotations

import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = "resume-bundle"
REQUIRED = {
    f"{ROOT}/manifest.json",
    f"{ROOT}/project.json",
    f"{ROOT}/checkpoint.json",
    f"{ROOT}/active-work-items.jsonl",
    f"{ROOT}/next-work-items.jsonl",
    f"{ROOT}/blocked-work-items.jsonl",
    f"{ROOT}/decisions.jsonl",
    f"{ROOT}/procedures.jsonl",
    f"{ROOT}/relevant-policies.jsonl",
    f"{ROOT}/validation-requirements.json",
    f"{ROOT}/artifact-references.jsonl",
    f"{ROOT}/source-references.jsonl",
    f"{ROOT}/HANDOFF.md",
    f"{ROOT}/checksums.json",
}
CHECKSUM_NAME = f"{ROOT}/checksums.json"
PRIVATE_PATH = re.compile(r"(?:/Users/|/home/|[A-Za-z]:\\\\Users\\\\)")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
MAX_MEMBER_BYTES = 8 * 1024 * 1024
MAX_TOTAL_BYTES = 32 * 1024 * 1024


def _reject_constant(value: str) -> None:
    raise ValueError(f"unsupported JSON constant: {value}")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _value(content: bytes, name: str) -> Any:
    try:
        return json.loads(
            content.decode("utf-8", errors="strict"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"{name} is invalid JSON") from exc


def _object(content: bytes, name: str) -> dict[str, Any]:
    value = _value(content, name)
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def _array(content: bytes, name: str) -> list[Any]:
    value = _value(content, name)
    if not isinstance(value, list):
        raise ValueError(f"{name} must be an array")
    return value


def _jsonl_count(content: bytes, name: str) -> int:
    lines = content.decode("utf-8", errors="strict").splitlines()
    for line in lines:
        if not line or not isinstance(_value(line.encode("utf-8"), name), dict):
            raise ValueError(f"{name} contains an invalid record")
    return len(lines)


def _read(path: Path) -> dict[str, bytes]:
    if not path.is_file() or path.is_symlink():
        raise ValueError("bundle path is invalid")
    members: dict[str, bytes] = {}
    total = 0
    with zipfile.ZipFile(path, "r") as archive:
        infos = archive.infolist()
        names = [item.filename for item in infos]
        if len(names) != len(set(names)) or set(names) != REQUIRED:
            raise ValueError("bundle inventory is invalid")
        for info in infos:
            member = PurePosixPath(info.filename)
            if member.is_absolute() or ".." in member.parts or info.is_dir():
                raise ValueError("bundle member path is unsafe")
            if info.flag_bits & 0x1 or info.file_size > MAX_MEMBER_BYTES:
                raise ValueError("bundle member metadata is invalid")
            content = archive.read(info)
            if len(content) != info.file_size:
                raise ValueError("bundle member size is invalid")
            total += len(content)
            if total > MAX_TOTAL_BYTES:
                raise ValueError("bundle is too large")
            members[info.filename] = content
    return members


def _checksums(members: dict[str, bytes]) -> bool:
    payload = _object(members[CHECKSUM_NAME], "checksums")
    if payload.get("algorithm") != "sha256":
        return False
    entries = payload.get("entries")
    if not isinstance(entries, list):
        return False
    expected = sorted(set(members) - {CHECKSUM_NAME})
    actual: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            return False
        name = entry.get("path")
        digest = entry.get("sha256")
        size = entry.get("size_bytes")
        if not isinstance(name, str) or name not in members or name == CHECKSUM_NAME:
            return False
        if not isinstance(digest, str) or not SHA256.fullmatch(digest):
            return False
        content = members[name]
        if digest != hashlib.sha256(content).hexdigest() or size != len(content):
            return False
        actual.append(name)
    return actual == expected


def inspect(path: Path) -> dict[str, bool]:
    members = _read(path)
    manifest = _object(members[f"{ROOT}/manifest.json"], "manifest")
    project = _object(members[f"{ROOT}/project.json"], "project")
    checkpoint = _value(members[f"{ROOT}/checkpoint.json"], "checkpoint")
    handoff = members[f"{ROOT}/HANDOFF.md"].decode("utf-8", errors="strict")
    combined = "\n".join(content.decode("utf-8", errors="strict") for content in members.values())
    selection = manifest.get("selection_options")
    included = manifest.get("included_record_counts")
    omitted = manifest.get("omitted_record_counts")
    reasons = manifest.get("omission_reasons")
    actual_counts = {
        "project": 1,
        "checkpoint": 1 if checkpoint is not None else 0,
        "active_work_items": _jsonl_count(
            members[f"{ROOT}/active-work-items.jsonl"], "active work"
        ),
        "next_work_items": _jsonl_count(members[f"{ROOT}/next-work-items.jsonl"], "next work"),
        "blocked_work_items": _jsonl_count(
            members[f"{ROOT}/blocked-work-items.jsonl"], "blocked work"
        ),
        "decisions": _jsonl_count(members[f"{ROOT}/decisions.jsonl"], "decisions"),
        "procedures": _jsonl_count(members[f"{ROOT}/procedures.jsonl"], "procedures"),
        "policies": _jsonl_count(members[f"{ROOT}/relevant-policies.jsonl"], "policies"),
        "validation_requirements": len(
            _array(
                members[f"{ROOT}/validation-requirements.json"],
                "validation requirements",
            )
        ),
        "artifact_references": _jsonl_count(
            members[f"{ROOT}/artifact-references.jsonl"], "artifact references"
        ),
        "source_references": _jsonl_count(
            members[f"{ROOT}/source-references.jsonl"], "source references"
        ),
    }
    omitted_valid = isinstance(omitted, dict) and all(
        isinstance(key, str)
        and isinstance(value, int)
        and not isinstance(value, bool)
        and value >= 0
        for key, value in omitted.items()
    )
    return {
        "fixed_inventory_valid": set(members) == REQUIRED,
        "checksums_valid": _checksums(members),
        "manifest_version_valid": manifest.get("bundle_format_version") == 1,
        "manifest_project_matches": manifest.get("project_id") == project.get("project_id"),
        "checkpoint_current": isinstance(checkpoint, dict)
        and checkpoint.get("freshness") == "current"
        and manifest.get("checkpoint_id") == checkpoint.get("checkpoint_id"),
        "selection_secret_safe": isinstance(selection, dict)
        and selection.get("include_secret_records") is False,
        "counts_explicit": isinstance(included, dict) and omitted_valid,
        "count_contract_valid": included == actual_counts,
        "secret_omission_reported": omitted_valid and omitted.get("work_items") == 1,
        "omissions_explicit": isinstance(reasons, list)
        and bool(reasons)
        and all(isinstance(value, str) and value for value in reasons),
        "handoff_non_authoritative": "generated and non-authoritative" in handoff,
        "no_private_absolute_paths": PRIVATE_PATH.search(combined) is None,
        "synthetic_secret_absent": "PRIVATE IMP-046 MARKER" not in combined,
    }


def main() -> int:
    try:
        checks = inspect(Path(sys.argv[1]))
        if not all(checks.values()):
            raise ValueError("bundle inspection failed")
        payload: dict[str, object] = {"result": "pass", "checks": checks}
    except BaseException as exc:
        payload = {"result": "fail", "error_class": type(exc).__name__}
        print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
        return 2
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
