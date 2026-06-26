from __future__ import annotations

from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "src/doll/checkpoint.py"


def main() -> None:
    text = PATH.read_text(encoding="utf-8")
    old = "        fingerprint = cast(str | None, fingerprint_value)\n"
    new = "        fingerprint = fingerprint_value\n"
    if text.count(old) != 1:
        raise RuntimeError("checkpoint fingerprint cast anchor changed")
    PATH.write_text(text.replace(old, new), encoding="utf-8")


if __name__ == "__main__":
    main()
