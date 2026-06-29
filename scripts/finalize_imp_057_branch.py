"""Remove temporary IMP-057 diagnostics and normalize final boundaries."""

from __future__ import annotations

from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise RuntimeError(f"unexpected replacement count for {path}: {old[:80]}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> int:
    replace_once(
        Path("scripts/imp_057_local_portability_probe.py"),
        '        "source_adapter_id": adapter.contract.adapter_id if False else "ollama-api-session",\n',
        '        "source_adapter_id": "ollama-api-session",\n',
    )
    replace_once(
        Path("scripts/imp_057_state_inspector.py"),
        '                and conversation.source_conversation_id == "imp057-conversation"\n',
        '                and conversation.source_conversation_id == "conversation:imp057-conversation"\n',
    )
    runner = Path("scripts/run_imp_057_local_portability.py")
    replace_once(
        runner,
        'DIAGNOSTIC = ROOT / "scripts" / "diagnose_imp_057_probe.py"\n',
        "",
    )
    replace_once(
        runner,
        '''def _diagnostic_tail(environment: dict[str, str]) -> str:\n    result = subprocess.run(\n        [sys.executable, str(DIAGNOSTIC)],\n        cwd=ROOT,\n        env=environment,\n        capture_output=True,\n        text=True,\n        check=False,\n    )\n    lines = [line.strip() for line in result.stderr.splitlines() if line.strip()]\n    return " | ".join(lines[-8:]) or "diagnostic produced no stderr"\n\n\n''',
        "",
    )
    replace_once(
        runner,
        '''    if result.returncode or payload.get("result") != "pass":\n        if machine:\n            raise RuntimeError("local-portability migration probe failed")\n        raise RuntimeError(_diagnostic_tail(environment))\n''',
        '''    if result.returncode or payload.get("result") != "pass":\n        raise RuntimeError("local-portability migration probe failed")\n''',
    )
    replace_once(
        runner,
        '''        if stage == "migration_probe" and arguments.evidence_level == "ci":\n            payload["error_detail"] = str(exc)\n''',
        "",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
