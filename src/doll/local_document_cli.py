"""CLI surface for explicit local text and Markdown reading."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from doll.local_document import LocalDocumentError, read_local_document

document_app = typer.Typer(
    help="Read one explicitly selected local UTF-8 text or Markdown document.",
    no_args_is_help=True,
)


@document_app.command("read")
def read_document_command(
    source: Annotated[
        Path,
        typer.Argument(help="Explicit .txt, .md, or .markdown file."),
    ],
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit deterministic machine-readable JSON."),
    ] = False,
    metadata_only: Annotated[
        bool,
        typer.Option("--metadata-only", help="Omit document content from output."),
    ] = False,
) -> None:
    """Read one selected local document without persistence or model execution."""

    try:
        result = read_local_document(source)
    except (LocalDocumentError, OSError) as exc:
        if json_output:
            typer.echo(
                json.dumps(
                    {
                        "error": "local_document_read_failed",
                        "error_class": type(exc).__name__,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
        else:
            typer.echo(f"local document read failed: {type(exc).__name__}", err=True)
        raise typer.Exit(code=2) from exc

    if json_output:
        typer.echo(
            json.dumps(
                result.to_dict(include_content=not metadata_only),
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return

    metadata = result.metadata_dict()
    typer.echo(
        f"Document: {metadata['document_kind']} {metadata['media_type']} "
        f"bytes={metadata['source_byte_count']} chars={metadata['character_count']} "
        f"lines={metadata['line_count']}"
    )
    typer.echo(
        f"Origin: {result.origin.origin_class}/{result.origin.authority_class} "
        f"via {result.origin.actor_type}/{result.origin.acquisition_method}"
    )
    if not metadata_only:
        typer.echo("---")
        typer.echo(result.text, nl=not result.text.endswith(("\n", "\r")))


__all__ = ["document_app", "read_document_command"]
