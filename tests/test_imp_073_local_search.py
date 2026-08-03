from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from doll.cli import app
from doll.local_search import (
    LOCAL_SEARCH_MODE,
    LOCAL_SEARCH_REPORT_SCHEMA_VERSION,
    LocalSearchUnavailableError,
    LocalSearchValidationError,
    search_local_state,
    search_workspace,
)
from doll.state import STATE_DATABASE_NAME, initialize_state_repository, open_state_repository
from doll.workspace import initialize_workspace

runner = CliRunner()


def _workspace(tmp_path: Path) -> Path:
    initialized = initialize_workspace(tmp_path / "workspace")
    with initialize_state_repository(initialized.root):
        pass
    return initialized.root


def _snapshot(root: Path) -> dict[str, tuple[int, bytes]]:
    return {
        path.relative_to(root).as_posix(): (path.stat().st_mtime_ns, path.read_bytes())
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _create_record(
    root: Path,
    *,
    record_id: str,
    record_type: str,
    title: str,
    metadata: dict[str, object],
    status: str = "active",
    sensitivity: str = "personal",
) -> None:
    with open_state_repository(root) as repository:
        repository.create_record(
            record_id=record_id,
            record_type=record_type,
            status=status,  # type: ignore[arg-type]
            sensitivity=sensitivity,  # type: ignore[arg-type]
            title=title,
            metadata=metadata,
        )


def test_explicit_search_matches_title_nested_metadata_japanese_and_unicode(
    tmp_path: Path,
) -> None:
    root = _workspace(tmp_path)
    _create_record(
        root,
        record_id="00000000-0000-0000-0000-000000000101",
        record_type="project_note",
        title="Straße ＡＩ 計画",
        metadata={
            "summary": "ローカル全文検索の試験です",
            "nested": {"note": "Alpha Beta"},
        },
    )

    unicode_report = search_workspace(root, "STRASSE ai")
    japanese_report = search_workspace(root, "全文検索 試験")
    cross_field_report = search_workspace(root, "計画 beta")

    assert unicode_report.result_count == 1
    assert japanese_report.result_count == 1
    assert cross_field_report.result_count == 1
    assert unicode_report.hits[0].record_type == "project_note"
    assert unicode_report.hits[0].matches[0].field_path == "title"
    assert any(
        match.field_path == "metadata.nested.note"
        for match in cross_field_report.hits[0].matches
    )


def test_search_excludes_inactive_and_secret_records_and_filters_record_type(
    tmp_path: Path,
) -> None:
    root = _workspace(tmp_path)
    _create_record(
        root,
        record_id="00000000-0000-0000-0000-000000000102",
        record_type="project_note",
        title="visible needle",
        metadata={"body": "active record"},
    )
    _create_record(
        root,
        record_id="00000000-0000-0000-0000-000000000103",
        record_type="archived_note",
        title="archived needle",
        metadata={"body": "inactive record"},
        status="archived",
    )
    _create_record(
        root,
        record_id="00000000-0000-0000-0000-000000000104",
        record_type="secret_reference",
        title="secret needle",
        sensitivity="secret",
        metadata={
            "reference_id": "ref-hidden",
            "credential_class": "api_key",
            "store_adapter_class": "test_adapter",
            "label": "needle",
            "status": "active",
            "allowed_operation_scope": [],
            "allowed_destination_scope": [],
        },
    )
    _create_record(
        root,
        record_id="00000000-0000-0000-0000-000000000105",
        record_type="decision_note",
        title="decision needle",
        metadata={"body": "active decision"},
    )

    all_hits = search_workspace(root, "needle")
    filtered = search_workspace(root, "needle", record_type="project_note")

    assert {hit.record_type for hit in all_hits.hits} == {
        "project_note",
        "decision_note",
    }
    assert [hit.record_type for hit in filtered.hits] == ["project_note"]
    assert all(hit.sensitivity != "secret" for hit in all_hits.hits)


def test_search_is_deterministic_bounded_and_ranks_title_matches_first(
    tmp_path: Path,
) -> None:
    root = _workspace(tmp_path)
    _create_record(
        root,
        record_id="00000000-0000-0000-0000-000000000106",
        record_type="note",
        title="needle in title",
        metadata={"body": "x" * 260 + " needle tail"},
    )
    _create_record(
        root,
        record_id="00000000-0000-0000-0000-000000000107",
        record_type="note",
        title="metadata only",
        metadata={"body": "needle in metadata"},
    )

    first = search_workspace(root, "needle", limit=1)
    second = search_workspace(root, "needle", limit=1)

    assert first == second
    assert first.result_count == 1
    assert first.hits[0].record_id.endswith("0106")
    assert len(first.hits[0].matches) <= 3
    assert all(len(match.snippet) <= 162 for match in first.hits[0].matches)
    assert all(len(match.field_path) <= 160 for match in first.hits[0].matches)
    payload = first.to_dict()
    assert payload["schema_version"] == LOCAL_SEARCH_REPORT_SCHEMA_VERSION
    assert payload["search_mode"] == LOCAL_SEARCH_MODE


def test_search_workspace_preserves_every_workspace_file_exactly(tmp_path: Path) -> None:
    root = _workspace(tmp_path)
    _create_record(
        root,
        record_id="00000000-0000-0000-0000-000000000108",
        record_type="note",
        title="immutable needle",
        metadata={"body": "read only"},
    )
    before = _snapshot(root)

    report = search_workspace(root, "needle")

    assert report.result_count == 1
    assert _snapshot(root) == before


def test_search_rejects_writable_repository(tmp_path: Path) -> None:
    root = _workspace(tmp_path)

    with open_state_repository(root) as repository:
        with pytest.raises(LocalSearchValidationError, match="read-only"):
            search_local_state(repository, "needle")


@pytest.mark.parametrize(
    "query",
    [
        "",
        "   ",
        "line\nbreak",
        "x" * 241,
        "one two three four five six seven eight nine ten eleven twelve thirteen",
    ],
)
def test_search_rejects_invalid_queries(tmp_path: Path, query: str) -> None:
    root = _workspace(tmp_path)

    with pytest.raises(LocalSearchValidationError):
        search_workspace(root, query)


@pytest.mark.parametrize("limit", [0, 101, True])
def test_search_rejects_invalid_limits(tmp_path: Path, limit: int) -> None:
    root = _workspace(tmp_path)

    with pytest.raises(LocalSearchValidationError):
        search_workspace(root, "needle", limit=limit)


def test_pending_sqlite_journal_fails_closed_without_deletion(tmp_path: Path) -> None:
    root = _workspace(tmp_path)
    journal = root / "state" / f"{STATE_DATABASE_NAME}-wal"
    journal.write_bytes(b"pending")

    with pytest.raises(LocalSearchUnavailableError, match="active SQLite journal"):
        search_workspace(root, "needle")

    assert journal.read_bytes() == b"pending"


def test_cli_human_and_json_output_are_stable_and_path_free(tmp_path: Path) -> None:
    root = _workspace(tmp_path)
    _create_record(
        root,
        record_id="00000000-0000-0000-0000-000000000109",
        record_type="note",
        title="CLI needle",
        metadata={"body": "Japanese 日本語"},
    )

    human = runner.invoke(app, ["search", "needle", "--workspace", str(root)])
    machine = runner.invoke(
        app,
        ["search", "needle", "--workspace", str(root), "--json"],
    )

    assert human.exit_code == 0
    assert "Local search results: 1" in human.stdout
    assert "[note] CLI needle" in human.stdout
    assert machine.exit_code == 0
    payload = json.loads(machine.stdout)
    assert payload["result_count"] == 1
    assert payload["search_mode"] == LOCAL_SEARCH_MODE
    assert str(root) not in machine.stdout
    assert str(tmp_path) not in machine.stdout


def test_invalid_workspace_cli_does_not_create_or_disclose_target(tmp_path: Path) -> None:
    target = tmp_path / "private-missing-workspace"

    result = runner.invoke(
        app,
        ["search", "needle", "--workspace", str(target), "--json"],
    )

    assert result.exit_code == 2
    payload = json.loads(result.stdout)
    assert payload["error"] == "local_search_failed"
    assert str(target) not in result.stdout
    assert not target.exists()
