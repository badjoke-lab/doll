from __future__ import annotations

import ast
import json
from pathlib import Path

MATRIX = Path("docs/testing/phase-5-local-runtime-continuity-matrix.json")
RUNNER = Path("scripts/run_imp_054_runtime_continuity.py")
PROBE = Path("scripts/imp_054_runtime_probe.py")
INSPECTOR = Path("scripts/imp_054_state_inspector.py")


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.add(node.module)
    return imports


def test_phase_5_matrix_maps_lrun_001_through_lrun_012_with_gate_complete() -> None:
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    entries = matrix["runtime_tests"]
    result_path = Path(matrix["accepted_real_machine_result"])
    result_text = result_path.read_text(encoding="utf-8")
    result = json.loads(result_text)

    assert matrix["schema_version"] == 1
    assert matrix["phase"] == "5"
    assert matrix["acceptance_test_id"] == "IMP-054-LOCAL-RUNTIME-CONTINUITY"
    assert matrix["phase5_gate_complete"] is True
    assert result_path == Path(
        "docs/testing/results/IMP-054-primary-intel-mac-2026-06-28.json"
    )
    assert [item["id"] for item in entries] == [f"LRUN-{number:03d}" for number in range(1, 13)]
    assert all(item["status"] == "pass" for item in entries)
    assert all(item["pytest_files"] for item in entries)
    assert all(item["evidence_levels"] == ["ci", "real-machine"] for item in entries)

    gate = matrix["real_machine_gate"]
    assert gate == {
        "required": True,
        "status": "pass",
        "platform": "Darwin",
        "architectures": ["x86_64", "amd64"],
        "minimum_local_models": 2,
        "commit_sha": "1a5b66b2417d6f3e1eafcd14d2769e9c15d7f96c",
        "completed_at": "2026-06-28T15:23:40.505485Z",
        "network_mode": "offline-confirmed",
    }
    assert result["test_id"] == matrix["acceptance_test_id"]
    assert result["result"] == "pass"
    assert result["evidence_level"] == "real-machine"
    assert result["operating_system"] == "Darwin"
    assert result["architecture"] == "x86_64"
    assert result["python_version"] == "3.12.13"
    assert result["network_mode"] == "offline-confirmed"
    assert result["commit_sha"] == gate["commit_sha"]
    assert result["completed_at"] == gate["completed_at"]
    assert result["primary_intel_mac_gate"] == "pass"
    assert result["phase5_gate_complete"] is True
    assert result["real_runtime_used"] is True
    assert result["runtime_test_count"] == 12
    assert result["runtime_test_ids"] == [f"LRUN-{number:03d}" for number in range(1, 13)]
    assert result["external_network_request_used"] is False
    assert result["cloud_credentials_used"] is False
    assert result["model_download_used"] is False
    assert result["runtime_installation_used"] is False
    assert all(result["checks"].values())
    assert all(value is False for value in result["privacy"].values())
    assert result["evidence"]["runtime_mode"] == "real-local"
    assert result["evidence"]["runtime_adapter_id"] == "ollama.local"
    assert result["evidence"]["runtime_version"] == "0.30.11"
    assert result["evidence"]["model_count"] == 2
    assert result["evidence"]["rejected_socket_attempts"] == 0

    for forbidden in (
        "qwen2.5",
        "/Users/",
        "/home/",
        "primary-model",
        "fallback-model",
    ):
        assert forbidden not in result_text


def test_real_runtime_probe_uses_only_loopback_ollama_and_no_install_path() -> None:
    source = PROBE.read_text(encoding="utf-8")
    assert "LoopbackOllamaTransport" in source
    assert "OLLAMA_LOOPBACK_HOST" in source
    assert 'frozenset({"/api/version", "/api/tags", "/api/generate"})' in source
    assert "SocketDestinationGuard" in source
    assert "http.client.HTTPConnection" not in source
    assert "requests" not in _imports(PROBE)
    assert "urllib" not in _imports(PROBE)
    assert "httpx" not in _imports(PROBE)
    assert "doll.credential_broker" not in _imports(PROBE)
    assert "doll.capability" not in _imports(PROBE)
    for forbidden in (
        "ollama pull",
        "ollama run",
        "ollama rm",
        "brew install",
        "subprocess.Popen",
        "shell=True",
    ):
        assert forbidden not in source


def test_runner_requires_exact_commit_and_explicit_real_machine_confirmation() -> None:
    source = RUNNER.read_text(encoding="utf-8")
    assert '["git", "rev-parse", "HEAD"]' in source
    assert "arguments.commit_sha != _head()" in source
    assert 'platform.system() != "Darwin"' in source
    assert 'platform.machine().lower() not in {"x86_64", "amd64"}' in source
    assert "not arguments.offline_confirmed" in source
    assert "not arguments.local_only_confirmed" in source
    assert "arguments.primary_model == arguments.fallback_model" in source
    assert '"model_download_used": False' in source
    assert '"runtime_installation_used": False' in source
    assert '"external_network_request_used": False' in source


def test_fresh_state_inspector_has_no_runtime_adapter_or_network_dependency() -> None:
    imports = _imports(INSPECTOR)
    assert "doll.ollama_adapter" not in imports
    assert "doll.runtime_adapter" not in imports
    assert "socket" not in imports
    assert "subprocess" not in imports
    assert "requests" not in imports
    assert "urllib" not in imports
    assert "httpx" not in imports
    source = INSPECTOR.read_text(encoding="utf-8")
    assert 'b"DOLL_SWITCH_OK"' in source
    assert "read_only=True" in source
    assert "runtime_outputs_data_only" in source
