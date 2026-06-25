from __future__ import annotations

from pathlib import Path


PATH = Path(__file__).resolve().parents[1] / "src/doll/state_package.py"


def replace_once(text: str, old: str, new: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one match, found {count}: {old!r}")
    return text.replace(old, new)


def main() -> None:
    text = PATH.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "    SUPPORTED_PACKAGE_FORMAT_VERSIONS,\n",
        "    SUPPORTED_PACKAGE_FORMAT_VERSIONS as _SUPPORTED_PACKAGE_FORMAT_VERSIONS,\n",
    )
    text = replace_once(
        text,
        "PACKAGE_FORMAT_VERSION = 2\n",
        "PACKAGE_FORMAT_VERSION = 2\n"
        "SUPPORTED_PACKAGE_FORMAT_VERSIONS = _SUPPORTED_PACKAGE_FORMAT_VERSIONS\n",
    )
    text = replace_once(
        text,
        "    actual_counts: dict[str, int] = {}\n"
        "    for category in registry.categories:\n",
        "    actual_counts: dict[str, int] = {}\n"
        "    payloads: list[object]\n"
        "    for category in registry.categories:\n",
    )
    PATH.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
