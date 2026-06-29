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
        '''            payload = {
                "models": [
                    {
                        "name": self.model_name,
                        "model": self.model_name,
                        "digest": "5" * 64,
                    }
                ]
            }
            return OllamaHttpResponse(
                200,
                json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            )
''',
        '''            inventory_payload: dict[str, object] = {
                "models": [
                    {
                        "name": self.model_name,
                        "model": self.model_name,
                        "digest": "5" * 64,
                    }
                ]
            }
            return OllamaHttpResponse(
                200,
                json.dumps(inventory_payload, separators=(",", ":")).encode("utf-8"),
            )
''',
    )
    replace_once(
        probe,
        '''            payload = {
                "model": self.model_name,
                "created_at": "2026-06-29T03:00:01Z",
                "message": {"role": "assistant", "content": SYNTHETIC_RESPONSE},
                "done": True,
                "done_reason": "stop",
            }
            return OllamaHttpResponse(
                200,
                json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            )
''',
        '''            chat_payload: dict[str, object] = {
                "model": self.model_name,
                "created_at": "2026-06-29T03:00:01Z",
                "message": {"role": "assistant", "content": SYNTHETIC_RESPONSE},
                "done": True,
                "done_reason": "stop",
            }
            return OllamaHttpResponse(
                200,
                json.dumps(chat_payload, separators=(",", ":")).encode("utf-8"),
            )
''',
    )
    replace_once(
        probe,
        "        socket.socket.connect = guarded_connect  # type: ignore[method-assign]\n",
        "        socket.socket.connect = guarded_connect  # type: ignore[assignment]\n",
    )
    replace_once(
        probe,
        "        socket.socket.connect_ex = guarded_connect_ex  # type: ignore[method-assign]\n",
        "        socket.socket.connect_ex = guarded_connect_ex  # type: ignore[assignment]\n",
    )
    replace_once(
        probe,
        "            socket.socket.connect = self._connect  # type: ignore[method-assign]\n",
        "            socket.socket.connect = self._connect  # type: ignore[assignment]\n",
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
        '''            preservation_state=cast(
                Literal["managed_snapshot", "hash_only"],
                metadata["preservation_state"],
            ),
''',
    )
    replace_once(
        portability,
        '''    for snapshot in snapshots.values():
        batch = batches.get(snapshot.import_batch_id)
        if batch is None or batch.source_root_hash != snapshot.source_root_hash:
''',
        '''    for snapshot in snapshots.values():
        snapshot_batch = batches.get(snapshot.import_batch_id)
        if (
            snapshot_batch is None
            or snapshot_batch.source_root_hash != snapshot.source_root_hash
        ):
''',
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
