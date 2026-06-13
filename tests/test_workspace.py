"""Tests for workspace initialization."""

from __future__ import annotations

import json
import platform
from pathlib import Path

import pytest
from typer.testing import CliRunner

from doll.cli import app
from doll.paths import default_workspace_root
from doll.workspace import WORKSPACE_RECORD_FILE, WorkspaceInitError, create_workspace


def test_create_workspace_writes_unicode_identity(tmp_path: Path) -> None:
    target = tmp_path / "人形 workspace"

    record = create_workspace(target, instance_label="東京")

    data = json.loads((target / WORKSPACE_RECORD_FILE).read_text(encoding="utf-8"))
    assert data["workspace_id"] == record.workspace_id
    assert data["schema_version"] == "0.1"
    assert data["instance_label"] == "東京"
    assert data["state_revision"] == 0


def test_rejects_repository_checkout(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()

    with pytest.raises(WorkspaceInitError, match="repository checkout"):
        create_workspace(tmp_path)

    assert not (tmp_path / WORKSPACE_RECORD_FILE).exists()


def test_rejects_non_empty_target(tmp_path: Path) -> None:
    (tmp_path / "existing.txt").write_text("synthetic", encoding="utf-8")

    with pytest.raises(WorkspaceInitError, match="must be empty"):
        create_workspace(tmp_path)

    assert (tmp_path / "existing.txt").read_text(encoding="utf-8") == "synthetic"


def test_rejects_duplicate_workspace(tmp_path: Path) -> None:
    create_workspace(tmp_path)

    with pytest.raises(WorkspaceInitError, match=r"already exists|must be empty"):
        create_workspace(tmp_path)


def test_cleanup_after_partial_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "new-workspace"

    def fail_replace(source: Path, destination: Path) -> None:
        raise OSError(f"synthetic failure replacing {source} with {destination}")

    monkeypatch.setattr("doll.workspace.os.replace", fail_replace)

    with pytest.raises(WorkspaceInitError, match="failed to create"):
        create_workspace(target)

    assert not target.exists()


@pytest.mark.parametrize(
    ("system", "env", "expected"),
    [
        ("Darwin", {}, ("Library", "Application Support", "doll")),
        ("Windows", {"LOCALAPPDATA": "C:/Users/A/AppData/Local"}, ("doll",)),
        ("Linux", {"XDG_DATA_HOME": "/tmp/xdg-data"}, ("doll",)),
    ],
)
def test_default_workspace_root_platforms(
    system: str, env: dict[str, str], expected: tuple[str, ...], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(platform, "system", lambda: system)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    root = default_workspace_root()

    assert root.parts[-len(expected) :] == expected


def test_cli_init_creates_workspace(tmp_path: Path) -> None:
    result = CliRunner().invoke(app, ["init", "--path", str(tmp_path), "--label", "test"])

    assert result.exit_code == 0
    assert "initialized workspace" in result.stdout
    assert (tmp_path / WORKSPACE_RECORD_FILE).exists()


def test_create_workspace_rejects_file_target(tmp_path: Path) -> None:
    target = tmp_path / "not-a-directory"
    target.write_text("synthetic", encoding="utf-8")

    with pytest.raises(WorkspaceInitError, match="not a directory"):
        create_workspace(target)

    assert target.read_text(encoding="utf-8") == "synthetic"


def test_default_workspace_root_fallbacks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    assert default_workspace_root().parts[-3:] == ("AppData", "Local", "doll")

    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    assert default_workspace_root().parts[-3:] == (".local", "share", "doll")


def test_cli_init_reports_validation_error(tmp_path: Path) -> None:
    (tmp_path / "existing.txt").write_text("synthetic", encoding="utf-8")

    result = CliRunner().invoke(app, ["init", "--path", str(tmp_path)])

    assert result.exit_code != 0
    assert "workspace target must be empty" in result.output


def test_cleanup_tolerates_missing_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "vanishing-workspace"

    def remove_then_fail(source: Path, destination: Path) -> None:
        source.unlink()
        target.rmdir()
        raise OSError("synthetic missing workspace")

    monkeypatch.setattr("doll.workspace.os.replace", remove_then_fail)

    with pytest.raises(WorkspaceInitError, match="failed to create"):
        create_workspace(target)

    assert not target.exists()
