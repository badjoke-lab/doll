"""Create or publish a DEV syndication article via the official Forem API."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

API_URL = "https://dev.to/api/articles"
DEFAULT_ARTICLE_PATH = Path("docs/writing/dev/portable-memory-not-ai-continuity.md")
DEV_ARTICLE_ROOT = Path("docs/writing/dev")


class DevPublishError(RuntimeError):
    """Raised when a DEV publication request cannot be completed safely."""


@dataclass(frozen=True)
class Article:
    """Validated metadata and body for one DEV syndication article."""

    title: str
    description: str
    tags: list[str]
    series: str | None
    canonical_url: str
    body_markdown: str


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--article",
        type=Path,
        default=DEFAULT_ARTICLE_PATH,
        help="Markdown article under docs/writing/dev",
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help="publish immediately instead of creating a DEV draft",
    )
    return parser.parse_args()


def _safe_article_path(path: Path) -> Path:
    root = DEV_ARTICLE_ROOT.resolve()
    resolved = path.resolve()
    if resolved.suffix.lower() != ".md" or root not in resolved.parents:
        raise DevPublishError("DEV article must be a Markdown file under docs/writing/dev")
    return resolved


def _front_matter_and_body(path: Path) -> tuple[dict[str, str], str]:
    text = _safe_article_path(path).read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise DevPublishError("DEV article front matter is missing")
    remainder = text[4:]
    marker = "\n---\n"
    if marker not in remainder:
        raise DevPublishError("DEV article front matter is not terminated")
    front_matter_text, body = remainder.split(marker, 1)

    metadata: dict[str, str] = {}
    for line in front_matter_text.splitlines():
        if not line.strip():
            continue
        key, separator, value = line.partition(":")
        if not separator:
            raise DevPublishError(f"invalid DEV front matter line: {line}")
        metadata[key.strip()] = value.strip()

    body = body.strip()
    if not body:
        raise DevPublishError("DEV article body is empty")
    return metadata, body


def load_article(path: Path) -> Article:
    """Load and validate one article without performing network access."""

    metadata, body = _front_matter_and_body(path)
    required = ("title", "description", "tags", "canonical_url")
    missing = [key for key in required if not metadata.get(key)]
    if missing:
        raise DevPublishError(
            "DEV article front matter is missing required fields: " + ", ".join(missing)
        )

    tags = [tag.strip() for tag in metadata["tags"].split(",") if tag.strip()]
    if not tags:
        raise DevPublishError("DEV article must define at least one tag")
    if len(tags) > 4:
        raise DevPublishError("DEV supports at most four article tags")

    return Article(
        title=metadata["title"],
        description=metadata["description"],
        tags=tags,
        series=metadata.get("series") or None,
        canonical_url=metadata["canonical_url"],
        body_markdown=body,
    )


def _api_key() -> str:
    value = os.environ.get("DEVTO_API_KEY", "").strip()
    if not value:
        raise DevPublishError(
            "DEVTO_API_KEY is missing; create a DEV API key and provide it as a secret"
        )
    return value


def _request_json(request: urllib.request.Request) -> object:
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise DevPublishError(f"DEV API HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise DevPublishError(f"DEV API request failed: {exc}") from exc


def find_existing_article(
    api_key: str, *, title: str, canonical_url: str
) -> dict[str, object] | None:
    query = urllib.parse.urlencode({"page": 1, "per_page": 100})
    request = urllib.request.Request(
        f"{API_URL}/me/all?{query}",
        method="GET",
        headers={
            "api-key": api_key,
            "user-agent": "badjoke-lab-doll-dev-publisher",
        },
    )
    data = _request_json(request)
    if not isinstance(data, list):
        raise DevPublishError("DEV API article listing returned a non-list response")
    for item in data:
        if not isinstance(item, dict):
            continue
        if item.get("canonical_url") == canonical_url or item.get("title") == title:
            return item
    return None


def create_article(*, article_path: Path, publish: bool) -> dict[str, object]:
    article = load_article(article_path)
    api_key = _api_key()
    existing = find_existing_article(
        api_key,
        title=article.title,
        canonical_url=article.canonical_url,
    )
    if existing is not None:
        return existing

    payload = {
        "article": {
            "title": article.title,
            "published": publish,
            "body_markdown": article.body_markdown,
            "tags": article.tags,
            "series": article.series,
            "canonical_url": article.canonical_url,
            "description": article.description,
        }
    }
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "api-key": api_key,
            "content-type": "application/json",
            "user-agent": "badjoke-lab-doll-dev-publisher",
        },
    )
    data = _request_json(request)
    if not isinstance(data, dict):
        raise DevPublishError("DEV API returned a non-object response")
    return data


def main() -> int:
    arguments = _arguments()
    try:
        result = create_article(
            article_path=arguments.article,
            publish=arguments.publish,
        )
    except (DevPublishError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    summary = {
        "id": result.get("id"),
        "published": result.get("published"),
        "url": result.get("url"),
        "canonical_url": result.get("canonical_url"),
    }
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
