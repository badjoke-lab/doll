"""Acceptance coverage for IMP-075 explicit local CSV workflows."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path

import pytest
from pytest import MonkeyPatch
from typer.testing import CliRunner

from doll import local_csv as local_csv_module
from doll.cli import app
from doll.local_csv import (
    LOCAL_CSV_ACQUISITION_METHOD,
    LOCAL_CSV_ACTOR_TYPE,
    LOCAL_CSV_AUTHORITY_CLASS,
    LOCAL_CSV_ORIGIN_CLASS,
    LOCAL_CSV_REPORT_SCHEMA_VERSION,
    LocalCsvReadError,
    LocalCsvValidationError,
    inspect_local_csv,
    parse_header_renames,
    read_local_csv,
    transform_local_csv,
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


def _parse_output(value: str, *, delimiter: str = ",") -> list[list[str]]:
    return list(csv.reader(io.StringIO(value, newline=""), delimiter=delimiter, strict=True))


def test_inspects_utf8_csv_with_quotes_newlines_bom_and_fixed_origin(tmp_path: Path) -> None:
    source = tmp_path / "data.csv"
    content = '名前,説明,値\r\n"東京","a,b",10\r\n"大阪","複数\n行",=1+1\r\n'
    raw = b"\xef\xbb\xbf" + content.encode()
    source.write_bytes(raw)

    result = inspect_local_csv(source, preview_rows=2)
    table = result.table

    assert table.headers == ("名前", "説明", "値")
    assert table.rows == (("東京", "a,b", "10"), ("大阪", "複数\n行", "=1+1"))
    assert result.preview_rows == table.rows
    assert table.row_count == 2
    assert table.column_count == 3
    assert table.source_byte_count == len(raw)
    assert table.content_byte_count == len(content.encode())
    assert table.character_count == len(content)
    assert table.source_sha256 == hashlib.sha256(raw).hexdigest()
    assert table.content_sha256 == hashlib.sha256(content.encode()).hexdigest()
    assert table.utf8_bom_removed is True
    assert table.blank_cell_count == 0
    assert table.potential_formula_cell_count == 1
    assert table.origin.origin_class == LOCAL_CSV_ORIGIN_CLASS
    assert table.origin.actor_type == LOCAL_CSV_ACTOR_TYPE
    assert table.origin.acquisition_method == LOCAL_CSV_ACQUISITION_METHOD
    assert table.origin.authority_class == LOCAL_CSV_AUTHORITY_CLASS
    payload = result.to_dict()
    assert payload["schema_version"] == LOCAL_CSV_REPORT_SCHEMA_VERSION
    assert payload["formula_evaluation_used"] is False
    assert payload["source_persisted"] is False


def test_supports_explicit_delimiter_profiles(tmp_path: Path) -> None:
    source = tmp_path / "data.csv"
    source.write_bytes("a\tb\n1\t2\n".encode())

    table = read_local_csv(source, delimiter_profile="TAB")

    assert table.delimiter_profile == "tab"
    assert table.headers == ("a", "b")
    assert table.rows == (("1", "2"),)


@pytest.mark.parametrize("profile", ["semicolon", "pipe"])
def test_semicolon_and_pipe_profiles(tmp_path: Path, profile: str) -> None:
    delimiter = ";" if profile == "semicolon" else "|"
    source = tmp_path / "data.csv"
    source.write_bytes(f"a{delimiter}b\n1{delimiter}2\n".encode())

    result = inspect_local_csv(source, delimiter_profile=profile)

    assert result.table.rows == (("1", "2"),)


def test_transform_selects_reorders_and_renames_without_rewriting_cells(tmp_path: Path) -> None:
    source = tmp_path / "data.csv"
    source.write_bytes('name,age,note\nAlice,20,"a,b"\nBob,30,=SUM(A1)\n'.encode())

    result = transform_local_csv(
        source,
        selected_columns=("note", "name"),
        header_renames={"note": "memo", "name": "person"},
    )

    assert result.selected_source_headers == ("note", "name")
    assert result.output_headers == ("memo", "person")
    assert _parse_output(result.output_csv) == [
        ["memo", "person"],
        ["a,b", "Alice"],
        ["=SUM(A1)", "Bob"],
    ]
    assert result.output_csv.endswith("\n")
    assert "\r\n" not in result.output_csv
    assert result.output_sha256 == hashlib.sha256(result.output_csv.encode()).hexdigest()
    assert result.to_dict()["formula_evaluation_used"] is False
    assert result.to_dict()["source_overwritten"] is False


def test_transform_defaults_to_all_columns_and_metadata_can_omit_output(tmp_path: Path) -> None:
    source = tmp_path / "data.csv"
    source.write_bytes(b"a,b\n1,2\n")

    result = transform_local_csv(source)
    metadata = result.to_dict(include_output=False)

    assert result.selected_source_headers == ("a", "b")
    assert _parse_output(result.output_csv) == [["a", "b"], ["1", "2"]]
    assert "output_csv" not in metadata


def test_formula_like_cells_are_counted_but_preserved(tmp_path: Path) -> None:
    source = tmp_path / "formula.csv"
    source.write_bytes(b"value\n=1+1\n +2\n-3\n@x\nplain\n")

    table = read_local_csv(source)
    transformed = transform_local_csv(source)

    assert table.potential_formula_cell_count == 4
    assert [row[0] for row in table.rows] == ["=1+1", " +2", "-3", "@x", "plain"]
    assert [row[0] for row in _parse_output(transformed.output_csv)[1:]] == [
        "=1+1",
        " +2",
        "-3",
        "@x",
        "plain",
    ]


def test_read_and_transform_do_not_modify_source_workspace_or_state(tmp_path: Path) -> None:
    initialized = initialize_workspace(tmp_path / "workspace")
    with initialize_state_repository(initialized.root):
        pass
    source = tmp_path / "data.csv"
    source.write_bytes(b"a,b\n1,2\n")
    source_before = source.read_bytes()
    workspace_before = _workspace_snapshot(initialized.root)
    siblings_before = sorted(path.name for path in tmp_path.iterdir())

    inspect_local_csv(source)
    transform_local_csv(source, selected_columns=("b",))

    assert source.read_bytes() == source_before
    assert _workspace_snapshot(initialized.root) == workspace_before
    assert sorted(path.name for path in tmp_path.iterdir()) == siblings_before


@pytest.mark.parametrize(
    ("name", "content", "message"),
    [
        ("data.txt", b"a,b\n1,2\n", "extension"),
        ("data.csv", b"", "header row"),
        ("data.csv", b",b\n1,2\n", "blank"),
        ("data.csv", b"a,a\n1,2\n", "unique"),
        ("data.csv", b"a,b\n1\n", "non-rectangular"),
        ("data.csv", b'a,b\n"broken,2\n', "syntax"),
        ("data.csv", b"\xff\xfe", "UTF-8"),
        ("data.csv", b"a\x00,b\n1,2\n", "NUL"),
        ("data.csv", b"a,b\n1,\x012\n", "control"),
        ("data.csv", b"a,b\n1,\x7f2\n", "control"),
    ],
)
def test_rejects_malformed_or_binary_like_csv(
    tmp_path: Path,
    name: str,
    content: bytes,
    message: str,
) -> None:
    source = tmp_path / name
    source.write_bytes(content)

    with pytest.raises(LocalCsvValidationError, match=message):
        read_local_csv(source)


def test_rejects_missing_directory_symlink_oversize_and_changed_inputs(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    with pytest.raises(LocalCsvReadError, match="unavailable"):
        read_local_csv(tmp_path / "missing.csv")

    directory = tmp_path / "folder.csv"
    directory.mkdir()
    with pytest.raises(LocalCsvValidationError, match="regular file"):
        read_local_csv(directory)

    target = tmp_path / "target.csv"
    target.write_bytes(b"a\n1\n")
    link = tmp_path / "link.csv"
    try:
        link.symlink_to(target)
    except OSError:
        pass
    else:
        with pytest.raises(LocalCsvValidationError, match="symlinks"):
            read_local_csv(link)

    oversized = tmp_path / "large.csv"
    oversized.write_bytes(b"a\n" + b"x" * 17)
    monkeypatch.setattr(local_csv_module, "_MAX_SOURCE_BYTES", 16)
    with pytest.raises(LocalCsvValidationError, match="maximum byte size"):
        read_local_csv(oversized)

    monkeypatch.setattr(local_csv_module, "_MAX_SOURCE_BYTES", 2_097_152)
    changed = tmp_path / "changed.csv"
    changed.write_bytes(b"a\n1\n")
    monkeypatch.setattr(local_csv_module, "_stable_read", lambda *args: False)
    with pytest.raises(LocalCsvReadError, match="changed while"):
        read_local_csv(changed)


def test_enforces_rows_columns_cells_aggregate_and_preview_limits(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    source = tmp_path / "data.csv"
    source.write_bytes(b"a,b\n1,2\n")

    monkeypatch.setattr(local_csv_module, "_MAX_COLUMNS", 1)
    with pytest.raises(LocalCsvValidationError, match="column limit"):
        read_local_csv(source)
    monkeypatch.setattr(local_csv_module, "_MAX_COLUMNS", 200)

    monkeypatch.setattr(local_csv_module, "_MAX_ROWS", 0)
    with pytest.raises(LocalCsvValidationError, match="row limit"):
        read_local_csv(source)
    monkeypatch.setattr(local_csv_module, "_MAX_ROWS", 10_000)

    monkeypatch.setattr(local_csv_module, "_MAX_CELL_CHARACTERS", 0)
    with pytest.raises(LocalCsvValidationError, match="header exceeds"):
        read_local_csv(source)
    monkeypatch.setattr(local_csv_module, "_MAX_CELL_CHARACTERS", 16_384)

    monkeypatch.setattr(local_csv_module, "_MAX_AGGREGATE_CHARACTERS", 2)
    with pytest.raises(LocalCsvValidationError, match="aggregate"):
        read_local_csv(source)
    monkeypatch.setattr(local_csv_module, "_MAX_AGGREGATE_CHARACTERS", 4_000_000)

    for preview in (-1, 101, True):
        with pytest.raises(LocalCsvValidationError, match="preview"):
            inspect_local_csv(source, preview_rows=preview)


def test_rejects_invalid_delimiters_selections_and_renames(tmp_path: Path) -> None:
    source = tmp_path / "data.csv"
    source.write_bytes(b"a,b,c\n1,2,3\n")

    with pytest.raises(LocalCsvValidationError, match="delimiter"):
        read_local_csv(source, delimiter_profile="auto")
    with pytest.raises(LocalCsvValidationError, match="unique"):
        transform_local_csv(source, selected_columns=("a", "a"))
    with pytest.raises(LocalCsvValidationError, match="does not exist"):
        transform_local_csv(source, selected_columns=("missing",))
    with pytest.raises(LocalCsvValidationError, match="not selected"):
        transform_local_csv(
            source,
            selected_columns=("a",),
            header_renames={"b": "renamed"},
        )
    with pytest.raises(LocalCsvValidationError, match="must not be blank"):
        transform_local_csv(source, header_renames={"a": " "})
    with pytest.raises(LocalCsvValidationError, match="must be unique"):
        transform_local_csv(source, header_renames={"a": "b"})

    assert parse_header_renames(("a=x", "b=y=z")) == {"a": "x", "b": "y=z"}
    for values in (("broken",), ("=x",), ("a=",), ("a=x", "a=y")):
        with pytest.raises(LocalCsvValidationError):
            parse_header_renames(values)


def test_cli_inspect_transform_json_metadata_and_path_safe_failures(tmp_path: Path) -> None:
    source = tmp_path / "data.csv"
    source.write_bytes("名前,値\n東京,1\n大阪,2\n".encode())

    inspect_human = runner.invoke(app, ["csv", "inspect", str(source)])
    inspect_json = runner.invoke(app, ["csv", "inspect", str(source), "--json"])
    transform_human = runner.invoke(
        app,
        ["csv", "transform", str(source), "--column", "値", "--rename", "値=amount"],
    )
    transform_json = runner.invoke(
        app,
        [
            "csv",
            "transform",
            str(source),
            "--column",
            "値",
            "--rename",
            "値=amount",
            "--json",
        ],
    )
    metadata = runner.invoke(
        app,
        ["csv", "transform", str(source), "--json", "--metadata-only"],
    )
    missing = tmp_path / "private-missing.csv"
    failure = runner.invoke(app, ["csv", "inspect", str(missing), "--json"])

    assert inspect_human.exit_code == 0
    assert "CSV: rows=2 columns=2" in inspect_human.stdout
    assert "external_content/untrusted_data" in inspect_human.stdout
    assert json.loads(inspect_json.stdout)["row_count"] == 2
    assert transform_human.exit_code == 0
    assert "persisted=false" in transform_human.stdout
    assert "amount" in transform_human.stdout
    transformed = json.loads(transform_json.stdout)
    assert _parse_output(transformed["output_csv"]) == [
        ["amount"],
        ["1"],
        ["2"],
    ]
    assert "output_csv" not in json.loads(metadata.stdout)
    assert failure.exit_code == 2
    assert json.loads(failure.stdout)["error"] == "local_csv_failed"
    assert str(missing) not in failure.stdout
    assert str(tmp_path) not in failure.stdout


def test_csv_help_does_not_initialize_workspace(monkeypatch: MonkeyPatch) -> None:
    import doll.cli as cli_module

    monkeypatch.setattr(
        cli_module,
        "initialize_workspace",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unexpected init")),
    )

    result = runner.invoke(app, ["csv", "--help"])

    assert result.exit_code == 0
    assert "UTF-8 CSV" in result.stdout
