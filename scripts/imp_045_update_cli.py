from pathlib import Path

path = Path(__file__).resolve().parents[1] / "src/doll/project_cli.py"
text = path.read_text(encoding="utf-8")
old_import = "from doll.project_status import ProjectStatusError, ProjectStatusService\n"
new_import = (
    "from doll.project_status import ProjectStatusError, ProjectStatusService\n"
    "from doll.resume_bundle import ResumeBundleError, ResumeBundleService\n"
)
if old_import not in text:
    raise RuntimeError("project CLI import anchor missing")
text = text.replace(old_import, new_import, 1)
old_apps = '''decision_app = typer.Typer(
    help="Manage explicit user-confirmed decision records.",
    no_args_is_help=True,
)
'''
new_apps = old_apps + '''resume_app = typer.Typer(
    help="Export deterministic project Resume Bundles.",
    no_args_is_help=True,
)
project_app.add_typer(resume_app, name="resume")
'''
if old_apps not in text:
    raise RuntimeError("project CLI app anchor missing")
text = text.replace(old_apps, new_apps, 1)
anchor = '\n\n@project_app.command("archive")\n'
command = '''

@resume_app.command("export")
def project_resume_export(
    project_id: Annotated[str, typer.Argument()],
    output: Annotated[Path, typer.Option("--output")],
    workspace: Annotated[Path | None, typer.Option("--workspace")] = None,
) -> None:
    """Export a deterministic project-scoped Resume Bundle."""

    try:
        with open_state_repository(workspace, read_only=True) as repository:
            inspection = ResumeBundleService(repository).export(project_id, output)
    except (WorkspaceError, StateError, ProjectDecisionError, ResumeBundleError, KeyError) as exc:
        _fail("project resume export failed", exc)

    typer.echo(
        f"Resume Bundle exported: {output} project={inspection.project_id} "
        f"state_revision={inspection.state_revision} members={inspection.member_count}"
    )
'''
if anchor not in text:
    raise RuntimeError("project CLI command anchor missing")
text = text.replace(anchor, command + anchor, 1)
path.write_text(text, encoding="utf-8")
