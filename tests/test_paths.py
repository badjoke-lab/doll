"""Tests for platform-aware private-data paths."""

from __future__ import annotations

from pathlib import Path

from doll import paths


def test_canonicalize_path_expands_relative_path(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.chdir(tmp_path)  # type: ignore[attr-defined]

    result = paths.canonicalize_path(Path("日本語") / "workspace")

    assert result == (tmp_path / "日本語" / "workspace").resolve()


def test_default_workspace_path_uses_platformdirs(tmp_path: Path, monkeypatch: object) -> None:
    expected = tmp_path / "platform-data" / "doll"
    monkeypatch.setattr(paths, "user_data_path", lambda *args, **kwargs: expected)  # type: ignore[attr-defined]

    assert paths.default_workspace_path() == expected.resolve()


def test_find_doll_repository_ancestor(tmp_path: Path) -> None:
    repository = tmp_path / "doll"
    target = repository / "nested" / "workspace"
    (repository / ".git").mkdir(parents=True)
    (repository / "pyproject.toml").write_text(
        '[project]\nname = "doll-ai"\n',
        encoding="utf-8",
    )

    assert paths.find_doll_repository_ancestor(target) == repository.resolve()


def test_unrelated_git_repository_is_not_treated_as_doll(tmp_path: Path) -> None:
    repository = tmp_path / "other"
    target = repository / "workspace"
    (repository / ".git").mkdir(parents=True)
    (repository / "pyproject.toml").write_text(
        '[project]\nname = "other-project"\n',
        encoding="utf-8",
    )

    assert paths.find_doll_repository_ancestor(target) is None
