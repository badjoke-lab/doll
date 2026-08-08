"""CLI surface for optional local raster-image OCR."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Never

import typer

from doll.local_ocr import LocalOcrError, extract_local_image_ocr

ocr_app = typer.Typer(
    help="Extract text from one explicitly selected local raster image through an optional OCR adapter.",
    no_args_is_help=True,
)


@ocr_app.command("extract")
def extract_ocr_command(
    source: Annotated[
        Path,
        typer.Argument(help="Explicit local .png, .jpg, or .jpeg image file."),
    ],
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit deterministic machine-readable JSON."),
    ] = False,
    metadata_only: Annotated[
        bool,
        typer.Option("--metadata-only", help="Omit recognized text from output."),
    ] = False,
) -> None:
    """Recognize bounded image text without persistence, subprocesses, or network access."""

    try:
        result = extract_local_image_ocr(source)
    except (LocalOcrError, OSError) as exc:
        _fail(exc, json_output=json_output)

    if json_output:
        typer.echo(
            json.dumps(
                result.to_dict(include_text=not metadata_only),
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return

    typer.echo(
        f"OCR extraction: lines={result.line_count} size={result.width}x{result.height} "
        f"format={result.image_format} adapter={result.adapter_id} "
        f"version={result.adapter_version} persisted=false"
    )
    typer.echo(
        f"Origin: {result.origin.origin_class}/{result.origin.authority_class} "
        f"via {result.origin.actor_type}/{result.origin.acquisition_method}"
    )
    if result.empty_text:
        typer.echo("No text recognized.")
    if not metadata_only:
        for line in result.lines:
            typer.echo(line.text)


def _fail(exc: BaseException, *, json_output: bool) -> Never:
    if json_output:
        typer.echo(
            json.dumps(
                {
                    "error": "local_ocr_extraction_failed",
                    "error_class": type(exc).__name__,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    else:
        typer.echo(f"local OCR extraction failed: {type(exc).__name__}", err=True)
    raise typer.Exit(code=2) from exc


__all__ = ["extract_ocr_command", "ocr_app"]
