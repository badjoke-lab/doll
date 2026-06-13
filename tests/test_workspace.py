from __future__ import annotations

import json
from pathlib import Path

import pytest

from doll import workspace


def test_initialize_workspace(tmp_path: Path) -> None:
    target = tmp_path / "workspace-jp"
    result = workspace.initialize_workspace(
        target,
        instance_label="current Mac",
        profile_preference="lite",
    )

    assert result.root == target.resolve()
    assert result.record.instance_label == "current Mac"
    assert result.record.state_revision == 0

    record_path = target / workspace.WORKSPACE_RECORD_NAME
    record = json.loads(record_path.read_text(encoding="utf-8"))
    assert record["workspace_id"] == str(result.record.workspace_id)

    for name in workspace.WORKSPACE_DIRECTORIES:
        assert (target / name).is_dir()


def test_duplicate_workspace_is_rejected(tmp_path: Path) -> None:
    target = tmp_path / "workspace"
    workspace.initialize_workspace(target)
    original = (target / workspace.WORKSPACE_RECORD_NAME).read_bytes()

    with pytest.raises(workspace.WorkspaceExistsError):
        workspace.initialize_workspace(target)

    assert (target / workspace.WORKSPACE_RECORD_NAME).read_bytes() == original


def test_non_empty_target_is_rejected(tmp_path: Path) -> None:
    target = tmp_path / "occupied"
    target.mkdir()
    existing = target / "keep.txt"
    existing.write_text("keep", encoding="utf-8")

    with pytest.raises(workspace.WorkspaceNotEmptyError):
        workspace.initialize_workspace(target)

    assert existing.read_text(encoding="utf-8") == "keep"


def test_repository_target_is_rejected(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    target = repository / "data"
    (repository / ".git").mkdir(parents=True)
    (repository / "pyproject.toml").write_text(
        '[project]\nname = "doll-ai"\n',
        encoding="utf-8",
    )

    with pytest.raises(workspace.WorkspacePathError):
        workspace.initialize_workspace(target)

    assert not target.exists()


def test_repository_root_is_rejected(tmp_path: Path) -> None:
    repository = tmp_path / "doll"
    (repository / ".git").mkdir(parents=True)
    (repository / "pyproject.toml").write_text(
        '[project]\nname = "doll-ai"\n',
        encoding="utf-8",
    )

    with pytest.raises(workspace.WorkspacePathError):
        workspace.initialize_workspace(repository)

    assert sorted(child.name for child in repository.iterdir()) == [".git", "pyproject.toml"]


def test_file_target_is_rejected(tmp_path: Path) -> None:
    target = tmp_path / "workspace-file"
    target.write_text("not a directory", encoding="utf-8")

    with pytest.raises(workspace.WorkspacePathError):
        workspace.initialize_workspace(target)

    assert target.read_text(encoding="utf-8") == "not a directory"


def test_profile_preference_can_be_heavy_or_auto(tmp_path: Path) -> None:
    heavy = workspace.initialize_workspace(tmp_path / "heavy", profile_preference="heavy")
    auto = workspace.initialize_workspace(tmp_path / "auto", profile_preference="auto")

    assert heavy.record.profile_preference == "heavy"
    assert auto.record.profile_preference == "auto"


def test_blank_label_is_rejected(tmp_path: Path) -> None:
    target = tmp_path / "workspace"

    with pytest.raises(workspace.WorkspacePathError):
        workspace.initialize_workspace(target, instance_label="   ")

    assert not target.exists()
