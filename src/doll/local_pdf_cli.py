"""CLI surface for optional local PDF text extraction."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Never

import typer

from doll.local_pdf import LocalPdfError, extract_local_pdf_text

pdf_app = typer.Typer(
    help="Extract text from one explicitly selected local PDF through an optional adapter.",
    no_args_is_help=True,
)


@pdf_app.command("extract")
def extract_pdf_command(
    source: Annotated[Path, typer.Argument(help="Explicit local .pdf file.")],
    pages: Annotated[
        list[int] | None,
        typer.Option(
            "--page",
            min=1,
            help="One-based page number. Repeat for an exact ordered page selection.",
        ),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit deterministic machine-readable JSON."),
    ] = False,
    metadata_only: Annotated[
        bool,
        typer.Option("--metadata-only", help="Omit extracted page text from output."),
    ] = False,
) -> None:
    """Extract bounded PDF text without OCR, persistence, models, or network access."""

    try:
        result = extract_local_pdf_text(source, selected_pages=tuple(pages or ()))
    except (LocalPdfError, OSError) as exc:
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
        f"PDF extraction: pages={result.selected_page_count}/"
        f"{result.document_page_count} adapter={result.adapter_id} "
        f"version={result.adapter_version} persisted=false"
    )
    typer.echo(
        f"Origin: {result.origin.origin_class}/{result.origin.authority_class} "
        f"via {result.origin.actor_type}/{result.origin.acquisition_method}"
    )
    if result.empty_text_page_numbers:
        pages_text = ",".join(str(page) for page in result.empty_text_page_numbers)
        typer.echo(f"Pages with no extractable text: {pages_text}")
    if not metadata_only:
        for page in result.pages:
            typer.echo(f"--- page {page.page_number} ---")
            typer.echo(page.text, nl=not page.text.endswith(("\n", "\r")))


def _fail(exc: BaseException, *, json_output: bool) -> Never:
    if json_output:
        typer.echo(
            json.dumps(
                {
                    "error": "local_pdf_extraction_failed",
                    "error_class": type(exc).__name__,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    else:
        typer.echo(f"local PDF extraction failed: {type(exc).__name__}", err=True)
    raise typer.Exit(code=2) from exc


__all__ = ["extract_pdf_command", "pdf_app"]
