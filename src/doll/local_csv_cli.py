"""CLI surface for explicit local CSV inspection and transformation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from doll.local_csv import (
    LocalCsvError,
    inspect_local_csv,
    parse_header_renames,
    transform_local_csv,
)

csv_app = typer.Typer(
    help="Inspect or transform one explicitly selected local UTF-8 CSV file.",
    no_args_is_help=True,
)


@csv_app.command("inspect")
def inspect_csv_command(
    source: Annotated[Path, typer.Argument(help="Explicit local .csv file.")],
    delimiter: Annotated[
        str,
        typer.Option(
            "--delimiter",
            help="Delimiter profile: comma, tab, semicolon, or pipe.",
        ),
    ] = "comma",
    preview_rows: Annotated[
        int,
        typer.Option("--preview-rows", min=0, max=100, help="Rows included in preview."),
    ] = 10,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit deterministic machine-readable JSON."),
    ] = False,
) -> None:
    """Inspect one selected local CSV without persistence or model execution."""

    try:
        result = inspect_local_csv(
            source,
            delimiter_profile=delimiter,
            preview_rows=preview_rows,
        )
    except (LocalCsvError, OSError) as exc:
        _fail(exc, json_output=json_output)

    if json_output:
        typer.echo(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True))
        return
    metadata = result.table.metadata_dict()
    typer.echo(
        f"CSV: rows={metadata['row_count']} columns={metadata['column_count']} "
        f"delimiter={metadata['delimiter_profile']}"
    )
    typer.echo("Headers: " + " | ".join(result.table.headers))
    typer.echo(
        f"Blank cells: {metadata['blank_cell_count']}  "
        f"Potential formulas: {metadata['potential_formula_cell_count']}"
    )
    typer.echo(
        f"Origin: {result.table.origin.origin_class}/{result.table.origin.authority_class} "
        f"via {result.table.origin.actor_type}/{result.table.origin.acquisition_method}"
    )
    for row in result.preview_rows:
        typer.echo(" | ".join(row))


@csv_app.command("transform")
def transform_csv_command(
    source: Annotated[Path, typer.Argument(help="Explicit local .csv file.")],
    delimiter: Annotated[
        str,
        typer.Option(
            "--delimiter",
            help="Delimiter profile: comma, tab, semicolon, or pipe.",
        ),
    ] = "comma",
    columns: Annotated[
        list[str] | None,
        typer.Option(
            "--column",
            help="Select one exact column. Repeat to select and reorder multiple columns.",
        ),
    ] = None,
    renames: Annotated[
        list[str] | None,
        typer.Option(
            "--rename",
            help="Rename one selected header using exact OLD=NEW. Repeat as needed.",
        ),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit deterministic machine-readable JSON."),
    ] = False,
    metadata_only: Annotated[
        bool,
        typer.Option("--metadata-only", help="Omit transformed CSV content from output."),
    ] = False,
) -> None:
    """Select, reorder, and rename CSV columns without writing an output file."""

    try:
        result = transform_local_csv(
            source,
            delimiter_profile=delimiter,
            selected_columns=tuple(columns or ()),
            header_renames=parse_header_renames(tuple(renames or ())),
        )
    except (LocalCsvError, OSError) as exc:
        _fail(exc, json_output=json_output)

    if json_output:
        typer.echo(
            json.dumps(
                result.to_dict(include_output=not metadata_only),
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return
    typer.echo(
        f"CSV transformation: rows={result.source.row_count} "
        f"columns={len(result.output_headers)} persisted=false"
    )
    typer.echo("Output headers: " + " | ".join(result.output_headers))
    if not metadata_only:
        typer.echo("---")
        typer.echo(result.output_csv, nl=False)


def _fail(exc: BaseException, *, json_output: bool) -> None:
    if json_output:
        typer.echo(
            json.dumps(
                {
                    "error": "local_csv_failed",
                    "error_class": type(exc).__name__,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    else:
        typer.echo(f"local CSV failed: {type(exc).__name__}", err=True)
    raise typer.Exit(code=2) from exc


__all__ = ["csv_app", "inspect_csv_command", "transform_csv_command"]
