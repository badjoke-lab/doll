"""Standalone standard-library inspector for Doll shutdown escape bundles."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import stat
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

FORMAT = "doll-shutdown-escape"
FORMAT_VERSION = 1
ROOT = "doll-shutdown-escape"
CHECKSUMS = f"{ROOT}/checksums.json"
MANIFEST = f"{ROOT}/manifest.json"
MAX_MEMBERS = 4096
MAX_MEMBER_BYTES = 512 * 1024 * 1024
MAX_TOTAL_BYTES = 1024 * 1024 * 1024
MAX_COMPRESSION_RATIO = 1000
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_DRIVE_PATH = re.compile(r"^[A-Za-z]:")


class EscapeInspectionError(ValueError):
    """Raised when an escape bundle is malformed or inconsistent."""


def inspect_bundle(path: str) -> dict[str, object]:
    """Verify one bundle and return a content-free recovery summary."""

    try:
        with zipfile.ZipFile(path, "r") as archive:
            infos = archive.infolist()
            _validate_infos(infos)
            members = {info.filename: archive.read(info) for info in infos}
    except EscapeInspectionError:
        raise
    except (OSError, RuntimeError, ValueError, zipfile.BadZipFile) as exc:
        raise EscapeInspectionError("shutdown escape bundle is unreadable") from exc

    checksum_document = _json_object(_required(members, CHECKSUMS), "checksums")
    entries = _checksum_entries(checksum_document)
    expected = set(entries) | {CHECKSUMS}
    if set(members) != expected:
        raise EscapeInspectionError("shutdown escape inventory does not match checksums")
    for name, expected_entry in entries.items():
        content = members[name]
        if len(content) != expected_entry["size_bytes"]:
            raise EscapeInspectionError("shutdown escape member size mismatch")
        if hashlib.sha256(content).hexdigest() != expected_entry["sha256"]:
            raise EscapeInspectionError("shutdown escape member checksum mismatch")

    manifest = _json_object(_required(members, MANIFEST), "manifest")
    if manifest.get("format") != FORMAT or manifest.get("format_version") != FORMAT_VERSION:
        raise EscapeInspectionError("shutdown escape manifest version is unsupported")
    declared = manifest.get("members")
    expected_declared = [
        {
            "path": name,
            "sha256": hashlib.sha256(members[name]).hexdigest(),
            "size_bytes": len(members[name]),
        }
        for name in sorted(set(members) - {CHECKSUMS, MANIFEST})
    ]
    if declared != expected_declared:
        raise EscapeInspectionError("shutdown escape manifest member inventory is invalid")

    state_path = manifest.get("state_package_path")
    if not isinstance(state_path, str):
        raise EscapeInspectionError("shutdown escape state package path is invalid")
    state_summary = _verify_json_checksum_zip(members.get(state_path), "state package")
    state_manifest = state_summary["manifest"]
    record_counts = state_manifest.get("record_counts")
    omitted_secret_counts = state_manifest.get("omitted_secret_counts")
    if not isinstance(record_counts, dict) or not isinstance(omitted_secret_counts, dict):
        raise EscapeInspectionError("state package recovery counts are invalid")
    if manifest.get("record_counts") != record_counts:
        raise EscapeInspectionError("shutdown escape record counts disagree with State Package")
    if manifest.get("omitted_secret_counts") != omitted_secret_counts:
        raise EscapeInspectionError("shutdown escape secret omission counts disagree")

    generic_path = manifest.get("generic_conversation_prefix")
    if generic_path is not None:
        if not isinstance(generic_path, str):
            raise EscapeInspectionError("generic conversation prefix is invalid")
        _verify_generic_export(members, generic_path)

    resume_paths = manifest.get("resume_bundle_paths")
    if not isinstance(resume_paths, list) or not all(isinstance(item, str) for item in resume_paths):
        raise EscapeInspectionError("resume bundle path list is invalid")
    for resume_path in resume_paths:
        _verify_json_checksum_zip(members.get(resume_path), "Resume Bundle")

    recoverable = manifest.get("recoverable_surfaces")
    if not isinstance(recoverable, dict) or not all(
        isinstance(key, str) and isinstance(value, bool) for key, value in recoverable.items()
    ):
        raise EscapeInspectionError("recoverable surface declaration is invalid")

    return {
        "format": FORMAT,
        "format_version": FORMAT_VERSION,
        "workspace_id": manifest.get("workspace_id"),
        "state_revision": manifest.get("state_revision"),
        "record_counts": record_counts,
        "omitted_secret_counts": omitted_secret_counts,
        "recoverable_surfaces": recoverable,
        "generic_conversation_export": generic_path is not None,
        "resume_bundle_count": len(resume_paths),
        "member_count": len(members),
        "top_level_sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
    }


def _validate_infos(infos: list[zipfile.ZipInfo]) -> None:
    if not infos or len(infos) > MAX_MEMBERS:
        raise EscapeInspectionError("shutdown escape member count is unsupported")
    seen: set[str] = set()
    folded: set[str] = set()
    total = 0
    for info in infos:
        name = _member_name(info.filename)
        if name in seen:
            raise EscapeInspectionError("shutdown escape contains duplicate members")
        folded_name = name.casefold()
        if folded_name in folded:
            raise EscapeInspectionError("shutdown escape contains case-folding collisions")
        seen.add(name)
        folded.add(folded_name)
        mode = info.external_attr >> 16
        file_type = stat.S_IFMT(mode)
        if info.is_dir() or file_type == stat.S_IFLNK or file_type not in {0, stat.S_IFREG}:
            raise EscapeInspectionError("shutdown escape contains a non-regular member")
        if info.file_size < 0 or info.file_size > MAX_MEMBER_BYTES:
            raise EscapeInspectionError("shutdown escape member size is unsupported")
        total += info.file_size
        if total > MAX_TOTAL_BYTES:
            raise EscapeInspectionError("shutdown escape total size is unsupported")
        if info.compress_size == 0:
            if info.file_size > 0:
                raise EscapeInspectionError("shutdown escape compression ratio is invalid")
        elif info.file_size / info.compress_size > MAX_COMPRESSION_RATIO:
            raise EscapeInspectionError("shutdown escape compression ratio is unsupported")


def _member_name(value: str) -> str:
    if not value or "\\" in value or _DRIVE_PATH.match(value):
        raise EscapeInspectionError("shutdown escape member path is unsafe")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise EscapeInspectionError("shutdown escape member path is unsafe")
    if path.parts[0] != ROOT:
        raise EscapeInspectionError("shutdown escape member root is invalid")
    return path.as_posix()


def _required(members: dict[str, bytes], name: str) -> bytes:
    try:
        return members[name]
    except KeyError as exc:
        raise EscapeInspectionError(f"required member is missing: {name}") from exc


def _json_object(content: bytes, name: str) -> dict[str, Any]:
    try:
        value = json.loads(content.decode("utf-8"), parse_constant=_reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise EscapeInspectionError(f"{name} is not valid JSON") from exc
    if not isinstance(value, dict):
        raise EscapeInspectionError(f"{name} must be a JSON object")
    return value


def _reject_constant(value: str) -> object:
    raise ValueError(f"unsupported JSON constant: {value}")


def _checksum_entries(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if document.get("algorithm") != "sha256":
        raise EscapeInspectionError("checksum algorithm is unsupported")
    raw_entries = document.get("entries")
    if not isinstance(raw_entries, list):
        raise EscapeInspectionError("checksum entries are invalid")
    result: dict[str, dict[str, Any]] = {}
    previous = ""
    for raw in raw_entries:
        if not isinstance(raw, dict) or set(raw) != {"path", "sha256", "size_bytes"}:
            raise EscapeInspectionError("checksum entry shape is invalid")
        path = raw.get("path")
        digest = raw.get("sha256")
        size = raw.get("size_bytes")
        if not isinstance(path, str) or _member_name(path) != path or path <= previous:
            raise EscapeInspectionError("checksum entry order or path is invalid")
        if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
            raise EscapeInspectionError("checksum digest is invalid")
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise EscapeInspectionError("checksum size is invalid")
        result[path] = {"sha256": digest, "size_bytes": size}
        previous = path
    return result


def _inner_member_name(value: str, name: str) -> str:
    if not value or "\\" in value or _DRIVE_PATH.match(value):
        raise EscapeInspectionError(f"{name} member path is unsafe")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise EscapeInspectionError(f"{name} member path is unsafe")
    return path.as_posix()


def _verify_json_checksum_zip(content: bytes | None, name: str) -> dict[str, Any]:
    if content is None:
        raise EscapeInspectionError(f"{name} member is missing")
    try:
        with zipfile.ZipFile(io.BytesIO(content), "r") as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if len(names) != len(set(names)):
                raise EscapeInspectionError(f"{name} contains duplicate members")
            folded = {item.casefold() for item in names}
            if len(folded) != len(names):
                raise EscapeInspectionError(f"{name} contains case-folding collisions")
            total = 0
            for info in infos:
                _inner_member_name(info.filename, name)
                mode = info.external_attr >> 16
                file_type = stat.S_IFMT(mode)
                if info.is_dir() or file_type == stat.S_IFLNK or file_type not in {0, stat.S_IFREG}:
                    raise EscapeInspectionError(f"{name} contains a non-regular member")
                if info.file_size < 0 or info.file_size > MAX_MEMBER_BYTES:
                    raise EscapeInspectionError(f"{name} member size is unsupported")
                total += info.file_size
                if total > MAX_TOTAL_BYTES:
                    raise EscapeInspectionError(f"{name} total size is unsupported")
            members = {info.filename: archive.read(info) for info in infos}
    except EscapeInspectionError:
        raise
    except (RuntimeError, ValueError, zipfile.BadZipFile) as exc:
        raise EscapeInspectionError(f"{name} is unreadable") from exc
    checksum_names = [item for item in members if item.endswith("/checksums.json")]
    manifest_names = [item for item in members if item.endswith("/manifest.json")]
    if len(checksum_names) != 1 or len(manifest_names) != 1:
        raise EscapeInspectionError(f"{name} inventory is incomplete")
    checksums = _json_object(members[checksum_names[0]], f"{name} checksums")
    raw_entries = checksums.get("entries")
    if checksums.get("algorithm") != "sha256" or not isinstance(raw_entries, list):
        raise EscapeInspectionError(f"{name} checksum inventory is invalid")
    expected_paths: set[str] = set()
    for raw in raw_entries:
        if not isinstance(raw, dict):
            raise EscapeInspectionError(f"{name} checksum entry is invalid")
        path = raw.get("path")
        digest = raw.get("sha256")
        size = raw.get("size_bytes")
        if not isinstance(path, str) or path in expected_paths:
            raise EscapeInspectionError(f"{name} checksum path is invalid")
        if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
            raise EscapeInspectionError(f"{name} checksum digest is invalid")
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise EscapeInspectionError(f"{name} checksum size is invalid")
        payload = members.get(path)
        if payload is None or len(payload) != size or hashlib.sha256(payload).hexdigest() != digest:
            raise EscapeInspectionError(f"{name} checksum verification failed")
        expected_paths.add(path)
    if set(members) != expected_paths | {checksum_names[0]}:
        raise EscapeInspectionError(f"{name} member inventory does not match checksums")
    return {"manifest": _json_object(members[manifest_names[0]], f"{name} manifest")}


def _verify_generic_export(members: dict[str, bytes], prefix: str) -> None:
    required = {
        "manifest.json",
        "records.json",
        "records.jsonl",
        "transcript.md",
        "checksums.sha256",
    }
    files = {name: members.get(f"{prefix}/{name}") for name in required}
    if any(content is None for content in files.values()):
        raise EscapeInspectionError("generic conversation export inventory is incomplete")
    checksums = files["checksums.sha256"]
    assert checksums is not None
    declared: dict[str, str] = {}
    try:
        for line in checksums.decode("utf-8").splitlines():
            digest, name = line.split("  ", 1)
            if _SHA256.fullmatch(digest) is None or name in declared:
                raise ValueError
            declared[name] = digest
    except (UnicodeDecodeError, ValueError) as exc:
        raise EscapeInspectionError("generic conversation checksums are invalid") from exc
    payload_names = {"manifest.json", "records.json", "records.jsonl", "transcript.md"}
    if set(declared) != payload_names:
        raise EscapeInspectionError("generic conversation checksum inventory is invalid")
    for name in payload_names:
        content = files[name]
        assert content is not None
        if hashlib.sha256(content).hexdigest() != declared[name]:
            raise EscapeInspectionError("generic conversation checksum mismatch")
    manifest = _json_object(files["manifest.json"] or b"", "generic conversation manifest")
    if manifest.get("format") != "doll-generic-export" or manifest.get("format_version") != "1":
        raise EscapeInspectionError("generic conversation format is unsupported")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", help="Path to one Doll shutdown escape ZIP")
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        result = inspect_bundle(args.bundle)
    except EscapeInspectionError as exc:
        print(json.dumps({"result": "fail", "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps({"result": "pass", **result}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
