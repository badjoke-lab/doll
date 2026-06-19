from __future__ import annotations

from pathlib import Path

from pytest import MonkeyPatch
from typer.testing import CliRunner

from doll.cli import app
from doll.workspace import WorkspaceError

runner = CliRunner()


def test_cli_redacts_secret_and_private_path_from_workspace_error(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    import doll.cli as cli_module

    secret = "synthetic-password-value"
    private_path = "/Users/example/private/workspace"

    def fail(*args: object, **kwargs: object) -> object:
        raise WorkspaceError(f"password={secret} path={private_path}")

    monkeypatch.setattr(cli_module, "initialize_workspace", fail)
    result = runner.invoke(app, ["init", str(tmp_path / "workspace")])

    assert result.exit_code == 2
    assert "workspace initialization failed:" in result.stderr
    assert secret not in result.stderr
    assert private_path not in result.stderr
    assert "[REDACTED:credential_assignment]" in result.stderr
    assert "[REDACTED:private_path]" in result.stderr
