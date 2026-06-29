from __future__ import annotations

import runpy
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "scripts" / "imp_057_local_portability_probe.py"


def test_synthetic_local_portability_migration_directly() -> None:
    namespace = runpy.run_path(str(PROBE))
    run = cast(
        Callable[..., tuple[dict[str, bool], dict[str, object]]],
        namespace["run"],
    )

    with tempfile.TemporaryDirectory(prefix="doll-imp057-test-") as directory:
        checks, evidence = run(
            Path(directory),
            mode="ci",
            model_name="doll-test-portability:latest",
            ollama_port=11434,
        )

    failed_checks = {name for name, passed in checks.items() if not passed}
    assert not failed_checks
    assert evidence["runtime_mode"] == "synthetic"
    assert evidence["source_object_counts"] == {
        "conversation": 1,
        "conversation_event": 2,
        "total": 3,
    }
    assert evidence["published_object_counts"] == evidence["source_object_counts"]
    assert evidence["allowed_loopback_socket_attempts"] == 0
    assert evidence["rejected_socket_attempts"] == 0
