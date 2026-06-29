"""Apply the two Ruff line-wrap fixes in the portability package tests."""

from __future__ import annotations

from pathlib import Path

TARGET = Path("tests/test_state_package_portability.py")


def replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise RuntimeError("unexpected portability test format patch context")
    return text.replace(old, new, 1)


def main() -> int:
    text = TARGET.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '        _envelope(environment.environment_id, "source_environment", environment.canonical_metadata()),\n',
        '''        _envelope(
            environment.environment_id,
            "source_environment",
            environment.canonical_metadata(),
        ),
''',
    )
    text = replace_once(
        text,
        '        _envelope(environment.environment_id, "source_environment", environment.canonical_metadata())\n',
        '''        _envelope(
            environment.environment_id,
            "source_environment",
            environment.canonical_metadata(),
        )
''',
    )
    TARGET.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
