from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "publish_dev_article.py"


def _run_script(tmp_path: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.pop("DEVTO_API_KEY", None)
    return subprocess.run(
        [sys.executable, str(SCRIPT), *arguments],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_dev_publisher_accepts_selected_valid_article_before_api_key_check(
    tmp_path: Path,
) -> None:
    article = tmp_path / "docs" / "writing" / "dev" / "test.md"
    article.parent.mkdir(parents=True)
    article.write_text(
        "---\n"
        "title: Test article\n"
        "published: false\n"
        "description: Test description\n"
        "tags: ai, architecture\n"
        "series: doll\n"
        "canonical_url: https://example.com/test/\n"
        "---\n\n"
        "Body.\n",
        encoding="utf-8",
    )

    result = _run_script(
        tmp_path,
        "--article",
        "docs/writing/dev/test.md",
    )

    assert result.returncode == 2
    assert "DEVTO_API_KEY is missing" in result.stderr


def test_dev_publisher_rejects_article_outside_allowed_directory(tmp_path: Path) -> None:
    article = tmp_path / "outside.md"
    article.write_text("not trusted", encoding="utf-8")

    result = _run_script(tmp_path, "--article", "outside.md")

    assert result.returncode == 2
    assert "under docs/writing/dev" in result.stderr


def test_dev_publisher_help_exposes_article_selector(tmp_path: Path) -> None:
    result = _run_script(tmp_path, "--help")

    assert result.returncode == 0
    assert "--article" in result.stdout
