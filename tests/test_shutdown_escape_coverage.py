from __future__ import annotations

import hashlib
import io
import json
import stat
import sys
import zipfile
from pathlib import Path
from typing import Any

import pytest

from doll import shutdown_escape_inspector as inspector
from doll.shutdown_escape import (
    ShutdownEscapeIntegrityError,
    ShutdownEscapeValidationError,
    _boolean_mapping,
    _inspection_from_summary,
    _integer_mapping,
    _json_bytes,
    verify_shutdown_escape_bundle,
)


def _info(
    name: str,
    *,
    size: int = 0,
    compressed: int = 0,
    mode: int = stat.S_IFREG | 0o600,
) -> zipfile.ZipInfo:
    value = zipfile.ZipInfo(name)
    value.create_system = 3
    value.external_attr = mode << 16
    value.file_size = size
    value.compress_size = compressed
    return value


def _zip_bytes(entries: list[tuple[zipfile.ZipInfo | str, bytes]]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        for raw_name, content in entries:
            info = raw_name if isinstance(raw_name, zipfile.ZipInfo) else _info(raw_name)
            archive.writestr(info, content)
    return buffer.getvalue()


def _embedded_zip(
    *,
    root: str = "embedded",
    manifest: bytes = b"{}",
    algorithm: str = "sha256",
    entries: list[object] | None = None,
    extra: list[tuple[zipfile.ZipInfo | str, bytes]] | None = None,
) -> bytes:
    manifest_path = f"{root}/manifest.json"
    checksum_path = f"{root}/checksums.json"
    checksum_entries: list[object]
    if entries is None:
        checksum_entries = [
            {
                "path": manifest_path,
                "sha256": hashlib.sha256(manifest).hexdigest(),
                "size_bytes": len(manifest),
            }
        ]
    else:
        checksum_entries = entries
    checksums = json.dumps(
        {"algorithm": algorithm, "entries": checksum_entries},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    members: list[tuple[zipfile.ZipInfo | str, bytes]] = [
        (manifest_path, manifest),
        (checksum_path, checksums),
    ]
    if extra:
        members.extend(extra)
    return _zip_bytes(members)


@pytest.mark.parametrize(
    "value",
    ["", "bad\\path", "C:/bad", "/absolute", "../escape", "other/file"],
)
def test_outer_member_name_rejects_unsafe_paths(value: str) -> None:
    with pytest.raises(inspector.EscapeInspectionError):
        inspector._member_name(value)


@pytest.mark.parametrize("value", ["", "bad\\path", "C:/bad", "/absolute", "../escape"])
def test_inner_member_name_rejects_unsafe_paths(value: str) -> None:
    with pytest.raises(inspector.EscapeInspectionError):
        inspector._inner_member_name(value, "embedded")


def test_required_and_json_helpers_reject_invalid_values() -> None:
    with pytest.raises(inspector.EscapeInspectionError):
        inspector._required({}, "missing")
    for content in (b"\xff", b"{", b'{"value": NaN}', b"[]"):
        with pytest.raises(inspector.EscapeInspectionError):
            inspector._json_object(content, "document")
    with pytest.raises(ValueError):
        inspector._reject_constant("NaN")


@pytest.mark.parametrize(
    "document",
    [
        {},
        {"algorithm": "sha1", "entries": []},
        {"algorithm": "sha256", "entries": {}},
        {"algorithm": "sha256", "entries": [None]},
        {
            "algorithm": "sha256",
            "entries": [{"path": "x", "sha256": "0" * 64, "size_bytes": 0}],
        },
        {
            "algorithm": "sha256",
            "entries": [
                {
                    "path": f"{inspector.ROOT}/x",
                    "sha256": "bad",
                    "size_bytes": 0,
                }
            ],
        },
        {
            "algorithm": "sha256",
            "entries": [
                {
                    "path": f"{inspector.ROOT}/x",
                    "sha256": "0" * 64,
                    "size_bytes": True,
                }
            ],
        },
    ],
)
def test_checksum_entry_validation_rejects_bad_documents(document: dict[str, Any]) -> None:
    with pytest.raises(inspector.EscapeInspectionError):
        inspector._checksum_entries(document)


def test_checksum_entry_validation_rejects_unsorted_or_duplicate_paths() -> None:
    entry = {
        "path": f"{inspector.ROOT}/x",
        "sha256": "0" * 64,
        "size_bytes": 0,
    }
    with pytest.raises(inspector.EscapeInspectionError):
        inspector._checksum_entries(
            {"algorithm": "sha256", "entries": [entry, dict(entry)]}
        )


def test_validate_infos_rejects_archive_structure(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(inspector.EscapeInspectionError):
        inspector._validate_infos([])

    regular = _info(f"{inspector.ROOT}/a", size=0, compressed=0)
    monkeypatch.setattr(inspector, "MAX_MEMBERS", 0)
    with pytest.raises(inspector.EscapeInspectionError):
        inspector._validate_infos([regular])
    monkeypatch.setattr(inspector, "MAX_MEMBERS", 4096)

    with pytest.raises(inspector.EscapeInspectionError):
        inspector._validate_infos([regular, _info(f"{inspector.ROOT}/a")])
    with pytest.raises(inspector.EscapeInspectionError):
        inspector._validate_infos(
            [_info(f"{inspector.ROOT}/Case"), _info(f"{inspector.ROOT}/case")]
        )
    with pytest.raises(inspector.EscapeInspectionError):
        inspector._validate_infos([_info(f"{inspector.ROOT}/directory/")])
    with pytest.raises(inspector.EscapeInspectionError):
        inspector._validate_infos(
            [_info(f"{inspector.ROOT}/link", mode=stat.S_IFLNK | 0o777)]
        )

    monkeypatch.setattr(inspector, "MAX_MEMBER_BYTES", 0)
    with pytest.raises(inspector.EscapeInspectionError):
        inspector._validate_infos(
            [_info(f"{inspector.ROOT}/large", size=1, compressed=1)]
        )
    monkeypatch.setattr(inspector, "MAX_MEMBER_BYTES", 512 * 1024 * 1024)

    monkeypatch.setattr(inspector, "MAX_TOTAL_BYTES", 0)
    with pytest.raises(inspector.EscapeInspectionError):
        inspector._validate_infos(
            [_info(f"{inspector.ROOT}/total", size=1, compressed=1)]
        )
    monkeypatch.setattr(inspector, "MAX_TOTAL_BYTES", 1024 * 1024 * 1024)

    with pytest.raises(inspector.EscapeInspectionError):
        inspector._validate_infos(
            [_info(f"{inspector.ROOT}/zero", size=1, compressed=0)]
        )
    monkeypatch.setattr(inspector, "MAX_COMPRESSION_RATIO", 1)
    with pytest.raises(inspector.EscapeInspectionError):
        inspector._validate_infos(
            [_info(f"{inspector.ROOT}/ratio", size=2, compressed=1)]
        )


def test_embedded_zip_verifier_rejects_missing_and_unreadable() -> None:
    with pytest.raises(inspector.EscapeInspectionError):
        inspector._verify_json_checksum_zip(None, "embedded")
    with pytest.raises(inspector.EscapeInspectionError):
        inspector._verify_json_checksum_zip(b"not-a-zip", "embedded")


def test_embedded_zip_verifier_rejects_duplicate_casefold_and_non_regular() -> None:
    duplicate = _zip_bytes(
        [
            ("embedded/manifest.json", b"{}"),
            ("embedded/manifest.json", b"{}"),
        ]
    )
    with pytest.raises(inspector.EscapeInspectionError):
        inspector._verify_json_checksum_zip(duplicate, "embedded")

    casefold = _zip_bytes(
        [("embedded/A", b""), ("embedded/a", b"")]
    )
    with pytest.raises(inspector.EscapeInspectionError):
        inspector._verify_json_checksum_zip(casefold, "embedded")

    link = _info("embedded/link", mode=stat.S_IFLNK | 0o777)
    with pytest.raises(inspector.EscapeInspectionError):
        inspector._verify_json_checksum_zip(_zip_bytes([(link, b"x")]), "embedded")


def test_embedded_zip_verifier_rejects_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _zip_bytes([("embedded/file", b"x")])
    monkeypatch.setattr(inspector, "MAX_MEMBER_BYTES", 0)
    with pytest.raises(inspector.EscapeInspectionError):
        inspector._verify_json_checksum_zip(payload, "embedded")
    monkeypatch.setattr(inspector, "MAX_MEMBER_BYTES", 512 * 1024 * 1024)
    monkeypatch.setattr(inspector, "MAX_TOTAL_BYTES", 0)
    with pytest.raises(inspector.EscapeInspectionError):
        inspector._verify_json_checksum_zip(payload, "embedded")


def test_embedded_zip_verifier_rejects_inventory_and_checksums() -> None:
    with pytest.raises(inspector.EscapeInspectionError):
        inspector._verify_json_checksum_zip(
            _zip_bytes([("embedded/file", b"x")]), "embedded"
        )
    with pytest.raises(inspector.EscapeInspectionError):
        inspector._verify_json_checksum_zip(
            _embedded_zip(algorithm="sha1"), "embedded"
        )
    with pytest.raises(inspector.EscapeInspectionError):
        inspector._verify_json_checksum_zip(
            _embedded_zip(entries=[None]), "embedded"
        )
    with pytest.raises(inspector.EscapeInspectionError):
        inspector._verify_json_checksum_zip(
            _embedded_zip(
                entries=[{"path": 1, "sha256": "0" * 64, "size_bytes": 0}]
            ),
            "embedded",
        )
    with pytest.raises(inspector.EscapeInspectionError):
        inspector._verify_json_checksum_zip(
            _embedded_zip(
                entries=[
                    {
                        "path": "embedded/manifest.json",
                        "sha256": "bad",
                        "size_bytes": 2,
                    }
                ]
            ),
            "embedded",
        )
    with pytest.raises(inspector.EscapeInspectionError):
        inspector._verify_json_checksum_zip(
            _embedded_zip(
                entries=[
                    {
                        "path": "embedded/manifest.json",
                        "sha256": hashlib.sha256(b"{}").hexdigest(),
                        "size_bytes": True,
                    }
                ]
            ),
            "embedded",
        )
    with pytest.raises(inspector.EscapeInspectionError):
        inspector._verify_json_checksum_zip(
            _embedded_zip(
                entries=[
                    {
                        "path": "embedded/manifest.json",
                        "sha256": "0" * 64,
                        "size_bytes": 2,
                    }
                ]
            ),
            "embedded",
        )
    with pytest.raises(inspector.EscapeInspectionError):
        inspector._verify_json_checksum_zip(
            _embedded_zip(extra=[("embedded/extra", b"x")]), "embedded"
        )


def _generic_members() -> dict[str, bytes]:
    payloads = {
        "manifest.json": b'{"format":"doll-generic-export","format_version":"1"}',
        "records.json": b"[]",
        "records.jsonl": b"",
        "transcript.md": b"# transcript\n",
    }
    checksums = "".join(
        f"{hashlib.sha256(content).hexdigest()}  {name}\n"
        for name, content in sorted(payloads.items())
    ).encode()
    return {
        **{f"generic/{name}": content for name, content in payloads.items()},
        "generic/checksums.sha256": checksums,
    }


def test_generic_export_verifier_rejects_invalid_forms() -> None:
    with pytest.raises(inspector.EscapeInspectionError):
        inspector._verify_generic_export({}, "generic")

    members = _generic_members()
    broken = dict(members)
    broken["generic/checksums.sha256"] = b"bad"
    with pytest.raises(inspector.EscapeInspectionError):
        inspector._verify_generic_export(broken, "generic")

    broken = dict(members)
    broken["generic/checksums.sha256"] = (
        b"0" * 64 + b"  manifest.json\n" + b"0" * 64 + b"  manifest.json\n"
    )
    with pytest.raises(inspector.EscapeInspectionError):
        inspector._verify_generic_export(broken, "generic")

    broken = dict(members)
    broken["generic/checksums.sha256"] = b""
    with pytest.raises(inspector.EscapeInspectionError):
        inspector._verify_generic_export(broken, "generic")

    broken = dict(members)
    broken["generic/records.json"] = b"[1]"
    with pytest.raises(inspector.EscapeInspectionError):
        inspector._verify_generic_export(broken, "generic")

    broken = dict(members)
    manifest = b'{"format":"wrong","format_version":"1"}'
    broken["generic/manifest.json"] = manifest
    broken["generic/checksums.sha256"] = "".join(
        f"{hashlib.sha256(broken[f'generic/{name}']).hexdigest()}  {name}\n"
        for name in ("manifest.json", "records.json", "records.jsonl", "transcript.md")
    ).encode()
    with pytest.raises(inspector.EscapeInspectionError):
        inspector._verify_generic_export(broken, "generic")


def test_shutdown_helpers_reject_invalid_summary_and_json(tmp_path: Path) -> None:
    with pytest.raises(ShutdownEscapeValidationError):
        verify_shutdown_escape_bundle(tmp_path / "missing.zip")
    with pytest.raises(ShutdownEscapeIntegrityError):
        _inspection_from_summary({})
    with pytest.raises(ShutdownEscapeIntegrityError):
        _integer_mapping({"x": True}, "counts")
    with pytest.raises(ShutdownEscapeIntegrityError):
        _boolean_mapping({"x": 1}, "flags")
    with pytest.raises(ShutdownEscapeValidationError):
        _json_bytes(float("nan"))


def test_inspector_main_reports_pass_and_failure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["inspect_escape.py", "bundle.zip"])
    monkeypatch.setattr(
        inspector,
        "inspect_bundle",
        lambda _: {"format": inspector.FORMAT, "format_version": 1},
    )
    assert inspector.main() == 0
    assert json.loads(capsys.readouterr().out)["result"] == "pass"

    def fail(_: str) -> dict[str, object]:
        raise inspector.EscapeInspectionError("rejected")

    monkeypatch.setattr(inspector, "inspect_bundle", fail)
    assert inspector.main() == 1
    assert json.loads(capsys.readouterr().out) == {
        "error": "rejected",
        "result": "fail",
    }
