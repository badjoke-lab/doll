from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise RuntimeError(f"expected one style-fix match in {path}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def main() -> None:
    replace_once(
        ROOT / "src/doll/local_csv.py",
        "def _parse_csv(text: str, delimiter: str) -> "
        "tuple[tuple[str, ...], tuple[tuple[str, ...], ...], int]:\n",
        "def _parse_csv(\n"
        "    text: str,\n"
        "    delimiter: str,\n"
        ") -> tuple[tuple[str, ...], tuple[tuple[str, ...], ...], int]:\n",
    )


if __name__ == "__main__":
    main()
