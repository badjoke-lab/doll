from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
from pytest import MonkeyPatch
from typer.testing import CliRunner

from doll import local_search as local_search_module
from doll import local_search_cli as local_search_cli_module
from doll.cli import app
from doll.local_search import (
    LocalSearchHit,
    LocalSearchMatch,
    LocalSearchReport,
    LocalSearchValidationError,
    search_local_state,
    search_workspace,
)
from doll.state import StateCorruptError, StateRepository, initialize_state_repository
from doll.workspace import initialize_workspace

runner = CliRunner()


def _workspace(tmp_path: Path) -> Path:
    initialized = initialize_workspace(tmp_path / "workspace")
    with initialize_state_repository(initialized.root):
        pass
    return initialized.root


def test_search_wraps_sqlite_query_failure() -> None:
    class BrokenConnection:
        def execute(self, statement: str, parameters: list[object]) -> object:
            del statement, parameters
            raise sqlite3.DatabaseError("synthetic failure")

    repository = cast(
        StateRepository,
        SimpleNamespace(read_only=True, connection=BrokenConnection()),
    )

    with pytest.raises(StateCorruptError, match="could not be searched"):
        search_local_state(repository, "needle")


def test_search_handles_untitled_blank_and_unmatched_fields(tmp_path: Path) -> None:
    root = _workspace(tmp_path)
    with local_search_module.open_state_repository(root) as repository:
        repository.create_record(
            record_id="00000000-0000-0000-0000-000000000201",
            record_type="note",
            title=None,
            metadata={
                "blank": "   ",
                "list": ["needle", 7, {"other": "not this term"}],
            },
        )

    report = search_workspace(root, "needle")
    missing = search_workspace(root, "needle absent")
    human = runner.invoke(app, ["search", "needle", "--workspace", str(root)])

    assert report.result_count == 1
    assert report.hits[0].title is None
    assert report.hits[0].matches[0].field_path == "metadata.list[0]"
    assert missing.result_count == 0
    assert human.exit_code == 0
    assert "(untitled)" in human.stdout


def test_query_and_record_type_validation_edges(tmp_path: Path) -> None:
    root = _workspace(tmp_path)

    with pytest.raises(LocalSearchValidationError, match="must be text"):
        search_workspace(root, cast(str, object()))
    for record_type in ("", "has space", "x" * 129):
        with pytest.raises(LocalSearchValidationError, match="record type"):
            search_workspace(root, "needle", record_type=record_type)


def test_corrupt_metadata_fails_closed(tmp_path: Path) -> None:
    root = _workspace(tmp_path)
    with local_search_module.open_state_repository(root) as repository:
        created = repository.create_record(
            record_id="00000000-0000-0000-0000-000000000202",
            record_type="note",
            title="needle",
            metadata={"body": "valid"},
        )
        repository.connection.execute(
            "UPDATE records SET metadata_json = ? WHERE id = ?",
            ("not-json", created.id),
        )

    with pytest.raises(StateCorruptError, match="metadata is unreadable"):
        search_workspace(root, "needle")

    with local_search_module.open_state_repository(root) as repository:
        repository.connection.execute(
            "UPDATE records SET metadata_json = ? WHERE id = ?",
            ("[]", created.id),
        )

    with pytest.raises(StateCorruptError, match="not an object"):
        search_workspace(root, "needle")


def test_private_text_helpers_cover_bounded_failure_edges(monkeypatch: MonkeyPatch) -> None:
    fields = tuple(
        local_search_module._iter_text_fields(
            cast(dict[str, object], {1: "ignored"}),
            "metadata",
        )
    )
    assert fields == ()
    assert local_search_module._make_snippet("plain", ()) == "plain"
    assert local_search_module._safe_field_component("\x00") == "?"
    assert local_search_module._safe_field_component("x" * 60).endswith("…")
    assert len(local_search_module._bound_field_path("x" * 200)) == 160

    monkeypatch.setattr(Path, "is_file", lambda self: True)

    def fail_stat(self: Path) -> object:
        del self
        raise OSError("synthetic stat failure")

    monkeypatch.setattr(Path, "stat", fail_stat)
    assert local_search_module._has_pending_sqlite_journal(Path("database.sqlite3")) is True

    with pytest.raises(ValueError, match="non-standard JSON"):
        local_search_module._reject_nonstandard_json("NaN")


def test_snippet_marks_truncated_suffix(tmp_path: Path) -> None:
    root = _workspace(tmp_path)
    with local_search_module.open_state_repository(root) as repository:
        repository.create_record(
            record_id="00000000-0000-0000-0000-000000000203",
            record_type="note",
            title="suffix needle " + "x" * 260,
            metadata={},
        )

    report = search_workspace(root, "needle")

    assert report.hits[0].matches[0].snippet.endswith("…")


def test_human_cli_covers_errors_empty_results_and_truncation(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = _workspace(tmp_path)
    missing = tmp_path / "missing-private-workspace"

    error = runner.invoke(app, ["search", "needle", "--workspace", str(missing)])
    empty = runner.invoke(app, ["search", "needle", "--workspace", str(root)])

    assert error.exit_code == 2
    assert "local search failed:" in error.stderr
    assert str(missing) not in error.stderr
    assert empty.exit_code == 0
    assert "No local records matched." in empty.stdout

    local_search_cli_module._render_human(
        LocalSearchReport(
            record_type_filter=None,
            scanned_records=10_000,
            scan_truncated=True,
            hits=(),
        )
    )
    empty_truncated = capsys.readouterr().out
    assert "bounded record limit" in empty_truncated

    local_search_cli_module._render_human(
        LocalSearchReport(
            record_type_filter=None,
            scanned_records=10_000,
            scan_truncated=True,
            hits=(
                LocalSearchHit(
                    record_id="00000000-0000-0000-0000-000000000204",
                    record_type="note",
                    sensitivity="personal",
                    title="result",
                    matches=(LocalSearchMatch(field_path="title", snippet="result"),),
                ),
            ),
        )
    )
    hit_truncated = capsys.readouterr().out
    assert "Local search results: 1" in hit_truncated
    assert "bounded record limit" in hit_truncated
