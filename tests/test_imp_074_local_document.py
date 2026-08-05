"""Acceptance coverage for IMP-074 explicit local text and Markdown reading."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from pytest import MonkeyPatch
from typer.testing import CliRunner

from doll import local_document as local_document_module
from doll.cli import app
from doll.local_document import (
    LOCAL_DOCUMENT_ACQUISITION_METHOD,
    LOCAL_DOCUMENT_ACTOR_TYPE,
    LOCAL_DOCUMENT_AUTHORITY_CLASS,
    LOCAL_DOCUMENT_ORIGIN_CLASS,
    LOCAL_DOCUMENT_REPORT_SCHEMA_VERSION,
    LocalDocumentReadError,
    LocalDocumentValidationError,
    read_local_document,
)
from doll.state import initialize_state_repository
from doll.workspace import initialize_workspace

runner = CliRunner()


def _workspace_snapshot(root: Path) -> dict[str, tuple[int, bytes]]:
    return {
        path.relative_to(root).as_posix(): (path.stat().st_mtime_ns, path.read_bytes())
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_reads_exact_utf8_text_and_markdown_with_fixed_untrusted_origin(
    tmp_path: Path,
) -> None:
    text_path = tmp_path / "notes.txt"
    markdown_path = tmp_path / "計画.MD"
    text_bytes = "一行目\r\nSecond line\n".encode()
    markdown_bytes = "# 見出し\n\n本文 **強調**".encode()
    text_path.write_bytes(text_bytes)
    markdown_path.write_bytes(markdown_bytes)

    text_result = read_local_document(text_path)
    markdown_result = read_local_document(markdown_path)

    assert text_result.text == "一行目\r\nSecond line\n"
    assert text_result.document_kind == "text"
    assert text_result.media_type == "text/plain"
    assert text_result.extension == ".txt"
    assert text_result.source_byte_count == len(text_bytes)
    assert text_result.content_byte_count == len(text_bytes)
    assert text_result.character_count == len(text_result.text)
    assert text_result.line_count == 2
    assert text_result.source_sha256 == hashlib.sha256(text_bytes).hexdigest()
    assert text_result.content_sha256 == hashlib.sha256(text_bytes).hexdigest()
    assert text_result.utf8_bom_removed is False
    assert markdown_result.text == markdown_bytes.decode()
    assert markdown_result.document_kind == "markdown"
    assert markdown_result.media_type == "text/markdown"
    assert markdown_result.extension == ".md"
    assert markdown_result.origin.origin_class == LOCAL_DOCUMENT_ORIGIN_CLASS
    assert markdown_result.origin.actor_type == LOCAL_DOCUMENT_ACTOR_TYPE
    assert markdown_result.origin.acquisition_method == LOCAL_DOCUMENT_ACQUISITION_METHOD
    assert markdown_result.origin.authority_class == LOCAL_DOCUMENT_AUTHORITY_CLASS


def test_utf8_bom_is_removed_deterministically_and_hashes_remain_explicit(
    tmp_path: Path,
) -> None:
    source = tmp_path / "bom.markdown"
    raw = b"\xef\xbb\xbf" + "# 日本語\n".encode()
    source.write_bytes(raw)

    result = read_local_document(source)

    assert result.text == "# 日本語\n"
    assert result.utf8_bom_removed is True
    assert result.source_sha256 == hashlib.sha256(raw).hexdigest()
    assert result.content_sha256 == hashlib.sha256(result.text.encode()).hexdigest()
    assert result.source_byte_count == len(raw)
    assert result.content_byte_count == len(result.text.encode())


def test_metadata_is_path_free_content_optional_and_declares_no_side_effects(
    tmp_path: Path,
) -> None:
    source = tmp_path / "private-name.txt"
    source.write_text("safe text", encoding="utf-8")

    result = read_local_document(source)
    metadata = result.metadata_dict()
    without_content = result.to_dict(include_content=False)
    with_content = result.to_dict()

    assert metadata["schema_version"] == LOCAL_DOCUMENT_REPORT_SCHEMA_VERSION
    assert metadata["source_persisted"] is False
    assert metadata["workspace_mutated"] is False
    assert metadata["state_mutated"] is False
    assert metadata["model_execution_used"] is False
    assert metadata["network_access_used"] is False
    assert "content" not in without_content
    assert with_content["content"] == "safe text"
    serialized = json.dumps(metadata, ensure_ascii=False, sort_keys=True)
    assert str(source) not in serialized
    assert str(tmp_path) not in serialized


def test_read_does_not_modify_initialized_workspace_or_state(tmp_path: Path) -> None:
    initialized = initialize_workspace(tmp_path / "workspace")
    with initialize_state_repository(initialized.root):
        pass
    source = tmp_path / "outside.md"
    source.write_bytes(b"# External\n")
    before = _workspace_snapshot(initialized.root)

    result = read_local_document(source)

    assert result.text == "# External\n"
    assert _workspace_snapshot(initialized.root) == before


@pytest.mark.parametrize(
    ("name", "content"),
    [
        ("unsupported.html", b"text"),
        ("invalid.txt", b"\xff\xfe"),
        ("nul.md", b"a\x00b"),
        ("control.txt", b"a\x01b"),
        ("delete.txt", b"a\x7fb"),
    ],
)
def test_rejects_unsupported_or_binary_like_inputs(
    tmp_path: Path,
    name: str,
    content: bytes,
) -> None:
    source = tmp_path / name
    source.write_bytes(content)

    with pytest.raises(LocalDocumentValidationError):
        read_local_document(source)


def test_rejects_missing_directory_symlink_oversize_and_changed_inputs(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    with pytest.raises(LocalDocumentReadError, match="unavailable"):
        read_local_document(tmp_path / "missing.txt")

    directory = tmp_path / "folder.md"
    directory.mkdir()
    with pytest.raises(LocalDocumentValidationError, match="regular file"):
        read_local_document(directory)

    target = tmp_path / "target.txt"
    target.write_text("target", encoding="utf-8")
    link = tmp_path / "link.txt"
    try:
        link.symlink_to(target)
    except OSError:
        pass
    else:
        with pytest.raises(LocalDocumentValidationError, match="symlinks"):
            read_local_document(link)

    oversized = tmp_path / "large.txt"
    oversized.write_bytes(b"x" * 17)
    monkeypatch.setattr(local_document_module, "_MAX_SOURCE_BYTES", 16)
    with pytest.raises(LocalDocumentValidationError, match="maximum byte size"):
        read_local_document(oversized)

    monkeypatch.setattr(local_document_module, "_MAX_SOURCE_BYTES", 1_048_576)
    changed = tmp_path / "changed.txt"
    changed.write_text("changed", encoding="utf-8")
    monkeypatch.setattr(local_document_module, "_stable_read", lambda *args: False)
    with pytest.raises(LocalDocumentReadError, match="changed while"):
        read_local_document(changed)


def test_rejects_character_limit_and_handle_identity_failures(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    source = tmp_path / "chars.txt"
    source.write_text("abcd", encoding="utf-8")
    monkeypatch.setattr(local_document_module, "_MAX_TEXT_CHARACTERS", 3)
    with pytest.raises(LocalDocumentValidationError, match="character limit"):
        read_local_document(source)

    monkeypatch.setattr(local_document_module, "_MAX_TEXT_CHARACTERS", 1_000_000)
    monkeypatch.setattr(local_document_module, "_same_identity", lambda *args: False)
    with pytest.raises(LocalDocumentReadError, match="changed before"):
        read_local_document(source)


def test_cli_human_json_metadata_only_and_path_safe_failures(tmp_path: Path) -> None:
    source = tmp_path / "document.md"
    source.write_bytes("# Heading\n本文".encode())

    human = runner.invoke(app, ["document", "read", str(source)])
    machine = runner.invoke(app, ["document", "read", str(source), "--json"])
    metadata = runner.invoke(
        app,
        ["document", "read", str(source), "--json", "--metadata-only"],
    )
    missing = tmp_path / "private-missing.txt"
    failure = runner.invoke(app, ["document", "read", str(missing), "--json"])

    assert human.exit_code == 0
    assert "Document: markdown text/markdown" in human.stdout
    assert "external_content/untrusted_data" in human.stdout
    assert "# Heading" in human.stdout
    payload = json.loads(machine.stdout)
    assert payload["content"] == "# Heading\n本文"
    assert payload["origin"]["authority_class"] == "untrusted_data"
    metadata_payload = json.loads(metadata.stdout)
    assert "content" not in metadata_payload
    assert failure.exit_code == 2
    failure_payload = json.loads(failure.stdout)
    assert failure_payload["error"] == "local_document_read_failed"
    assert str(missing) not in failure.stdout
    assert str(tmp_path) not in failure.stdout


def test_document_help_does_not_initialize_workspace(monkeypatch: MonkeyPatch) -> None:
    import doll.cli as cli_module

    monkeypatch.setattr(
        cli_module,
        "initialize_workspace",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unexpected init")),
    )

    result = runner.invoke(app, ["document", "--help"])

    assert result.exit_code == 0
    assert "UTF-8 text or Markdown" in result.stdout
