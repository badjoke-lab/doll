"""Apply reviewed type-only fixes for the IMP-057 harness."""

from __future__ import annotations

from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise RuntimeError(f"unexpected replacement count for {path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> int:
    probe = Path("scripts/imp_057_local_portability_probe.py")
    replace_once(
        probe,
        '''            payload = {\n                "models": [\n''',
        '''            inventory_payload: dict[str, object] = {\n                "models": [\n''',
    )
    replace_once(
        probe,
        '                json.dumps(payload, separators=(",", ":")).encode("utf-8"),\n',
        '                json.dumps(inventory_payload, separators=(",", ":")).encode("utf-8"),\n',
    )
    replace_once(
        probe,
        '''            payload = {\n                "model": self.model_name,\n''',
        '''            chat_payload: dict[str, object] = {\n                "model": self.model_name,\n''',
    )
    replace_once(
        probe,
        '                json.dumps(payload, separators=(",", ":")).encode("utf-8"),\n',
        '                json.dumps(chat_payload, separators=(",", ":")).encode("utf-8"),\n',
    )
    text = probe.read_text(encoding="utf-8")
    expected = text.count("# type: ignore[method-assign]")
    if expected != 4:
        raise RuntimeError("unexpected socket assignment ignore count")
    probe.write_text(
        text.replace("# type: ignore[method-assign]", "# type: ignore[assignment]"),
        encoding="utf-8",
    )

    runner = Path("scripts/run_imp_057_local_portability.py")
    replace_once(
        runner,
        '    machine = arguments.evidence_level == "real-machine"\n',
        '    machine = cast(str, arguments.evidence_level) == "real-machine"\n',
    )

    portability = Path("src/doll/state_package_portability.py")
    replace_once(
        portability,
        "from typing import cast\n",
        "from typing import Literal, cast\n",
    )
    replace_once(
        portability,
        '            preservation_state=cast(str, metadata["preservation_state"]),\n',
        '''            preservation_state=cast(\n                Literal["managed_snapshot", "hash_only"],\n                metadata["preservation_state"],\n            ),\n''',
    )
    replace_once(
        portability,
        '''    for snapshot in snapshots.values():\n        batch = batches.get(snapshot.import_batch_id)\n        if batch is None or batch.source_root_hash != snapshot.source_root_hash:\n''',
        '''    for snapshot in snapshots.values():\n        snapshot_batch = batches.get(snapshot.import_batch_id)\n        if (\n            snapshot_batch is None\n            or snapshot_batch.source_root_hash != snapshot.source_root_hash\n        ):\n''',
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
