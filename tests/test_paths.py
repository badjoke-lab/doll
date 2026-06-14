"""Tests for platform-aware private-data paths."""

from __future__ import annotations

from pathlib import Path

from pytest import MonkeyPatch

from doll import paths


def test_canonicalize_path_expands_relative_path(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    result = paths.canonicalize_path(Path("日本語") / "workspace")

    assert result == (tmp_path / "日本語" / "workspace").resolve()


def test_default_workspace_path_uses_platformdirs(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    expected = tmp_path / "platform-data" / "doll"
    monkeypatch.setattr(paths, "user_data_path", lambda *args, **kwargs: expected)

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


def test_unreadable_pyproject_repository_is_rejected(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    repository = tmp_path / "doll"
    target = repository / "workspace"
    pyproject = repository / "pyproject.toml"
    (repository / ".git").mkdir(parents=True)
    pyproject.write_text('[project]\nname = "doll-ai"\n', encoding="utf-8")

    original_read_text = Path.read_text

    def unreadable(self: Path, encoding: str | None = None, errors: str | None = None) -> str:
        if self == pyproject:
            raise OSError("permission denied")
        return original_read_text(self, encoding=encoding, errors=errors)

    monkeypatch.setattr(Path, "read_text", unreadable)

    assert paths.find_doll_repository_ancestor(target) == repository.resolve()
