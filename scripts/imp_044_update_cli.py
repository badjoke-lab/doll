from __future__ import annotations

from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "src/doll/project_cli.py"


def replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise RuntimeError(f"project CLI anchor mismatch: {old[:100]!r}")
    return text.replace(old, new, 1)


def main() -> None:
    text = PATH.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "from doll.state import RecordSensitivity, StateError, open_state_repository\n",
        "from doll.project_status import ProjectStatusError, ProjectStatusService\n"
        "from doll.state import RecordSensitivity, StateError, open_state_repository\n",
    )
    anchor = '''

@project_app.command("archive")
def project_archive(
'''
    command = '''

@project_app.command("status")
def project_status_command(
    project_id: Annotated[str, typer.Argument()],
    workspace: Annotated[Path | None, typer.Option("--workspace")] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit deterministic machine-readable JSON."),
    ] = False,
) -> None:
    """Derive deterministic live project status through a read-only connection."""

    try:
        with open_state_repository(workspace, read_only=True) as repository:
            service = ProjectStatusService(repository)
            output = (
                service.export_json(project_id)
                if json_output
                else service.render_text(project_id)
            )
    except (WorkspaceError, StateError, ProjectDecisionError, ProjectStatusError, KeyError) as exc:
        _fail("project status failed", exc)

    typer.echo(output, nl=False)
'''
    text = replace_once(text, anchor, command + anchor)
    PATH.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
