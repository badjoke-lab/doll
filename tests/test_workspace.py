"""Tests for workspace initialization."""

from __future__ import annotations

import importlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from doll.cli import app
from doll.paths import canonicalize_path, default_workspace_root
from doll.workspace import (
    WORKSPACE_RECORD_FILE,
    ProfilePreference,
    WorkspaceInitError,
    create_workspace,
)


def test_create_workspace_writes_stable_record_and_minimal_directories(tmp_path: Path) -> None:
    target = tmp_path / "人形 workspace"

    result = create_workspace(
        target,
        instance_label="東京",
        profile=ProfilePreference.AUTO,
    )

    data = json.loads((target / WORKSPACE_RECORD_FILE).read_text(encoding="utf-8"))
    assert result.path == canonicalize_path(target)
    assert result.created_root is True
    assert data["workspace_id"] == result.record.workspace_id
    assert data["schema_version"] == "0.1"
    assert data["profile_preference"] == "auto"
    assert data["instance_label"] == "東京"
    assert data["state_revision"] == 0
    assert sorted(child.name for child in target.iterdir()) == [
        "cache",
        "files",
        "state",
        WORKSPACE_RECORD_FILE,
    ]
    if os.name == "posix":
        assert oct(target.stat().st_mode & 0o777) == "0o700"
        assert oct((target / WORKSPACE_RECORD_FILE).stat().st_mode & 0o777) == "0o600"


def test_rejects_repository_root(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()

    with pytest.raises(WorkspaceInitError, match="repository checkout"):
        create_workspace(tmp_path)

    assert not (tmp_path / WORKSPACE_RECORD_FILE).exists()


def test_rejects_nested_target_inside_repository(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'synthetic'\n", encoding="utf-8")
    target = tmp_path / "nested" / "workspace"

    with pytest.raises(WorkspaceInitError, match="repository checkout"):
        create_workspace(target)

    assert not target.exists()


def test_rejects_non_empty_target(tmp_path: Path) -> None:
    (tmp_path / "existing.txt").write_text("synthetic", encoding="utf-8")

    with pytest.raises(WorkspaceInitError, match="must be empty"):
        create_workspace(tmp_path)

    assert (tmp_path / "existing.txt").read_text(encoding="utf-8") == "synthetic"


def test_rejects_duplicate_workspace(tmp_path: Path) -> None:
    create_workspace(tmp_path)

    with pytest.raises(WorkspaceInitError, match=r"already exists|must be empty"):
        create_workspace(tmp_path)


def test_rejects_file_target(tmp_path: Path) -> None:
    target = tmp_path / "not-a-directory"
    target.write_text("synthetic", encoding="utf-8")

    with pytest.raises(WorkspaceInitError, match="not a directory"):
        create_workspace(target)

    assert target.read_text(encoding="utf-8") == "synthetic"


def test_atomic_replacement_failure_removes_new_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "new-workspace"

    def fail_replace(source: str | os.PathLike[str], destination: str | os.PathLike[str]) -> None:
        raise OSError(f"synthetic failure replacing {source} with {destination}")

    monkeypatch.setattr("doll.workspace.os.replace", fail_replace)

    with pytest.raises(WorkspaceInitError, match="failed to create"):
        create_workspace(target)

    assert not target.exists()


def test_pre_existing_empty_root_remains_after_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "empty-workspace"
    target.mkdir()

    def fail_replace(source: str | os.PathLike[str], destination: str | os.PathLike[str]) -> None:
        raise OSError(f"synthetic failure replacing {source} with {destination}")

    monkeypatch.setattr("doll.workspace.os.replace", fail_replace)

    with pytest.raises(WorkspaceInitError, match="failed to create"):
        create_workspace(target)

    assert target.exists()
    assert list(target.iterdir()) == []


def test_unreadable_pyproject_handling(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "workspace"

    def raise_for_pyproject(self: Path) -> bool:
        if self.name == "pyproject.toml":
            raise OSError("synthetic permission failure")
        return False

    monkeypatch.setattr(Path, "is_file", raise_for_pyproject)

    result = create_workspace(target)

    assert result.path == canonicalize_path(target)
    assert (target / WORKSPACE_RECORD_FILE).exists()


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


def test_default_workspace_root_fallbacks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    assert default_workspace_root().parts[-3:] == ("AppData", "Local", "doll")

    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    assert default_workspace_root().parts[-3:] == (".local", "share", "doll")


def test_cli_init_positional_path_and_options(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app,
        [
            "init",
            str(tmp_path),
            "--instance-label",
            "test",
            "--profile",
            "heavy",
        ],
    )

    assert result.exit_code == 0
    assert "initialized workspace" in result.stdout
    data = json.loads((tmp_path / WORKSPACE_RECORD_FILE).read_text(encoding="utf-8"))
    assert data["instance_label"] == "test"
    assert data["profile_preference"] == "heavy"


def test_cli_init_reports_validation_error(tmp_path: Path) -> None:
    (tmp_path / "existing.txt").write_text("synthetic", encoding="utf-8")

    result = CliRunner().invoke(app, ["init", str(tmp_path)])

    assert result.exit_code != 0
    assert "workspace target must be empty" in result.output


def test_import_help_version_and_create_app_have_no_workspace_side_effect(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["XDG_DATA_HOME"] = str(tmp_path / "data")
    commands = [
        [sys.executable, "-c", "import doll.cli; import doll.workspace; import doll.api"],
        [sys.executable, "-m", "doll", "--help"],
        [sys.executable, "-m", "doll", "version"],
        [sys.executable, "-c", "from doll.api import create_app; create_app()"],
    ]

    for command in commands:
        completed = subprocess.run(command, check=False, env=env, capture_output=True, text=True)
        assert completed.returncode == 0, completed.stderr

    assert not (tmp_path / "data").exists()


def test_module_import_has_no_workspace_side_effect(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))

    importlib.import_module("doll.workspace")

    assert not (tmp_path / "data").exists()
