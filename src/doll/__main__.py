"""Allow `python -m doll` to run the management CLI."""

from __future__ import annotations

from doll.cli import main

if __name__ == "__main__":  # pragma: no cover - executed in a subprocess test.
    main()
