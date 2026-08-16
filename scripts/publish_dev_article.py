"""Create or publish the WEB-013 DEV syndication article via the official Forem API."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

API_URL = "https://dev.to/api/articles"
ARTICLE_PATH = Path("docs/writing/dev/portable-memory-not-ai-continuity.md")
TITLE = "Portable Memory Is Not AI Continuity: PAM, PLUR, PROJECTMEM, and doll"
CANONICAL_URL = "https://doll.badjoke-lab.com/notes/portable-memory-not-ai-continuity/"
DESCRIPTION = (
    "PAM, PLUR, PROJECTMEM, and doll address different layers of persistent AI "
    "memory and continuity. Why interchange, recall, project experience, and authority "
    "should stay separate."
)
TAGS = ["ai", "opensource", "architecture", "localfirst"]
SERIES = "doll"
_FRONT_MATTER = re.compile(r"\A---\n.*?\n---\n+", re.DOTALL)


class DevPublishError(RuntimeError):
    """Raised when a DEV publication request cannot be completed safely."""


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--publish",
        action="store_true",
        help="publish immediately instead of creating a DEV draft",
    )
    return parser.parse_args()


def _body_markdown() -> str:
    text = ARTICLE_PATH.read_text(encoding="utf-8")
    body = _FRONT_MATTER.sub("", text, count=1).strip()
    if not body:
        raise DevPublishError("DEV article body is empty")
    return body


def _api_key() -> str:
    value = os.environ.get("DEVTO_API_KEY", "").strip()
    if not value:
        raise DevPublishError(
            "DEVTO_API_KEY is missing; create a DEV API key and provide it as a secret"
        )
    return value


def create_article(*, publish: bool) -> dict[str, object]:
    payload = {
        "article": {
            "title": TITLE,
            "published": publish,
            "body_markdown": _body_markdown(),
            "tags": TAGS,
            "series": SERIES,
            "canonical_url": CANONICAL_URL,
            "description": DESCRIPTION,
        }
    }
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "api-key": _api_key(),
            "content-type": "application/json",
            "user-agent": "badjoke-lab-doll-web-013",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise DevPublishError(f"DEV API HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise DevPublishError(f"DEV API request failed: {exc}") from exc
    if not isinstance(data, dict):
        raise DevPublishError("DEV API returned a non-object response")
    return data


def main() -> int:
    arguments = _arguments()
    try:
        result = create_article(publish=arguments.publish)
    except (DevPublishError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    summary = {
        "id": result.get("id"),
        "published": result.get("published"),
        "url": result.get("url"),
        "canonical_url": CANONICAL_URL,
    }
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
