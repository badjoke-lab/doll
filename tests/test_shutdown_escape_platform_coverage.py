from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from doll import shutdown_escape
from doll.shutdown_escape import (
    ShutdownEscapeExportError,
    ShutdownEscapeValidationError,
    _exportable_conversations,
    _fsync_directory,
    _non_secret_project_ids,
    export_shutdown_escape_bundle,
)


def _fake_repository(
    workspace_root: Path,
    statuses: list[object],
) -> SimpleNamespace:
    iterator = iter(statuses)
    return SimpleNamespace(
        read_only=True,
        workspace=SimpleNamespace(
            root=workspace_root,
            record=SimpleNamespace(state_revision=statuses[0].state_revision),
        ),
        status=lambda: next(iterator),
    )


def test_export_rejects_workspace_revision_mismatch(tmp_path: Path) -> None:
    status = SimpleNamespace(state_revision=2)
    repository = SimpleNamespace(
        read_only=True,
        workspace=SimpleNamespace(
            root=tmp_path / "workspace",
            record=SimpleNamespace(state_revision=1),
        ),
        status=lambda: status,
    )

    with pytest.raises(ShutdownEscapeValidationError, match="revisions are inconsistent"):
        export_shutdown_escape_bundle(repository, tmp_path / "escape.zip")


def test_export_rejects_destination_inside_repository_checkout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    status = SimpleNamespace(state_revision=1)
    repository = _fake_repository(tmp_path / "workspace", [status])
    monkeypatch.setattr(
        shutdown_escape,
        "find_doll_repository_ancestor",
        lambda _: tmp_path,
    )

    with pytest.raises(ShutdownEscapeValidationError, match="repository checkout"):
        export_shutdown_escape_bundle(repository, tmp_path / "outside" / "escape.zip")


def test_export_wraps_unexpected_build_failure_and_removes_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    status = SimpleNamespace(state_revision=1)
    repository = _fake_repository(tmp_path / "workspace", [status])
    output = tmp_path / "escape.zip"
    monkeypatch.setattr(shutdown_escape, "find_doll_repository_ancestor", lambda _: None)

    def fail_build(*_: object, **__: object) -> tuple[dict[str, bytes], dict[str, object]]:
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(shutdown_escape, "_build_members", fail_build)

    with pytest.raises(ShutdownEscapeExportError, match="export failed"):
        export_shutdown_escape_bundle(repository, output)
    assert not output.exists()


def test_export_cleans_temporary_file_after_bounded_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    status = SimpleNamespace(state_revision=1)
    repository = _fake_repository(tmp_path / "workspace", [status])
    output = tmp_path / "escape.zip"
    monkeypatch.setattr(shutdown_escape, "find_doll_repository_ancestor", lambda _: None)
    monkeypatch.setattr(shutdown_escape, "_build_members", lambda *_args, **_kwargs: ({}, {}))

    def fail_write(path: Path, _members: dict[str, bytes]) -> None:
        path.write_bytes(b"partial")
        raise ShutdownEscapeValidationError("synthetic bounded failure")

    monkeypatch.setattr(shutdown_escape, "_write_deterministic_zip", fail_write)

    with pytest.raises(ShutdownEscapeValidationError, match="bounded failure"):
        export_shutdown_escape_bundle(repository, output)
    assert not output.exists()
    assert not tuple(tmp_path.glob(".escape.zip.*.tmp"))


def test_export_rejects_repository_status_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = SimpleNamespace(state_revision=1, marker="before")
    after = SimpleNamespace(state_revision=1, marker="after")
    repository = _fake_repository(tmp_path / "workspace", [before, after])
    output = tmp_path / "escape.zip"
    monkeypatch.setattr(shutdown_escape, "find_doll_repository_ancestor", lambda _: None)
    monkeypatch.setattr(shutdown_escape, "_build_members", lambda *_args, **_kwargs: ({}, {}))
    monkeypatch.setattr(
        shutdown_escape,
        "_write_deterministic_zip",
        lambda path, _members: path.write_bytes(b"synthetic archive"),
    )
    monkeypatch.setattr(shutdown_escape, "verify_shutdown_escape_bundle", lambda _path: object())
    monkeypatch.setattr(shutdown_escape, "_fsync_file", lambda _path: None)
    monkeypatch.setattr(shutdown_escape, "_fsync_directory", lambda _path: None)

    with pytest.raises(ShutdownEscapeExportError, match="modified repository status"):
        export_shutdown_escape_bundle(repository, output)
    assert not output.exists()


class _FailingConnection:
    def execute(self, _query: str) -> Any:
        raise sqlite3.DatabaseError("synthetic database failure")


def test_record_discovery_wraps_database_failures() -> None:
    repository = SimpleNamespace(connection=_FailingConnection())

    with pytest.raises(ShutdownEscapeValidationError, match="conversation records"):
        _exportable_conversations(repository)
    with pytest.raises(ShutdownEscapeValidationError, match="project records"):
        _non_secret_project_ids(repository)


def test_secret_event_excludes_its_entire_conversation() -> None:
    results = iter(
        [
            [("conversation-id", "private")],
            [("event-id", "secret", "conversation-id")],
        ]
    )

    class Connection:
        def execute(self, _query: str) -> SimpleNamespace:
            rows = next(results)
            return SimpleNamespace(fetchall=lambda: rows)

    repository = SimpleNamespace(connection=Connection())
    conversations, events, omitted = _exportable_conversations(repository)

    assert conversations == ()
    assert events == ()
    assert omitted == 1


def test_directory_fsync_executes_posix_branch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, object]] = []
    fake_os = SimpleNamespace(
        name="posix",
        O_RDONLY=0,
        open=lambda path, flags: calls.append(("open", (path, flags))) or 17,
        fsync=lambda descriptor: calls.append(("fsync", descriptor)),
        close=lambda descriptor: calls.append(("close", descriptor)),
    )
    monkeypatch.setattr(shutdown_escape, "os", fake_os)

    _fsync_directory(tmp_path)

    assert calls == [
        ("open", (tmp_path, 0)),
        ("fsync", 17),
        ("close", 17),
    ]
