from __future__ import annotations

import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPDATERS = (
    "imp_043_update_registry.py",
    "imp_043_update_fixtures.py",
    "imp_043_update_checkpoint_tests.py",
    "imp_043_update_package_core.py",
    "imp_043_update_package_graph.py",
    "imp_043_update_status.py",
)


def main() -> None:
    for name in UPDATERS:
        runpy.run_path(str(ROOT / "scripts" / name), run_name="__main__")
    runpy.run_path(str(ROOT / "scripts" / "build_final_spec.py"), run_name="__main__")


if __name__ == "__main__":
    main()
