from __future__ import annotations

import ast
import base64
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

MODULE = Path("src/doll/ollama_adapter.py")
STATE_PACKAGE_MODULE = Path("src/doll/state_package.py")
IMP057_MATRIX = Path("docs/testing/phase-6-local-portability-matrix.json")
IMP057_PROBE = Path("scripts/imp_057_local_portability_probe.py")
IMP057_INSPECTOR = Path("scripts/imp_057_state_inspector.py")
IMP057_RUNNER = Path("scripts/run_imp_057_local_portability.py")


def parsed() -> tuple[str, ast.Module]:
    source = MODULE.read_text(encoding="utf-8")
    return source, ast.parse(source, filename=str(MODULE))


def test_ollama_adapter_imports_no_authority_cloud_or_process_dependency() -> None:
    _, tree = parsed()
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.add(node.module)

    forbidden = {
        "doll.capability_broker",
        "doll.credential_broker",
        "doll.permissions",
        "doll.secret_store",
        "doll.state_repository",
        "httpx",
        "os",
        "requests",
        "subprocess",
        "urllib",
    }
    assert imports.isdisjoint(forbidden)


def test_ollama_adapter_contains_only_the_fixed_loopback_api_surface() -> None:
    source, tree = parsed()
    string_values = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    api_paths = {value for value in string_values if value.startswith("/api/")}

    assert api_paths == {"/api/chat", "/api/generate", "/api/tags", "/api/version"}
    assert 'OLLAMA_LOOPBACK_HOST = "127.0.0.1"' in source
    assert "ollama.com" not in source
    assert "localhost" not in source
    assert "Authorization" not in source
    assert "http://" not in source
    assert "https://" not in source
    assert "/api/pull" not in source
    assert "/api/push" not in source
    assert "/api/create" not in source
    assert "/api/delete" not in source


def test_http_connection_target_is_the_fixed_loopback_constant() -> None:
    _, tree = parsed()
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "HTTPConnection"
    ]

    assert len(calls) == 2
    for call in calls:
        assert len(call.args) >= 2
        assert isinstance(call.args[0], ast.Name)
        assert call.args[0].id == "OLLAMA_LOOPBACK_HOST"
        assert isinstance(call.args[1], ast.Attribute)
        assert call.args[1].attr == "port"


def test_adapter_surface_has_no_state_or_side_effect_method() -> None:
    source, tree = parsed()
    adapter = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "OllamaRuntimeAdapter"
    )
    method_names = {node.name for node in adapter.body if isinstance(node, ast.FunctionDef)}

    assert {"declaration", "health", "inventory", "generate", "stream"}.issubset(method_names)
    for forbidden in (
        "approve",
        "authorize",
        "capability",
        "checkpoint",
        "credential",
        "download",
        "memory",
        "permission",
        "project_complete",
        "pull",
        "push",
        "secret",
        "state_repository",
    ):
        assert f"def {forbidden}" not in source


def _module_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.add(node.module)
    return imports


def test_imp_057_matrix_and_alternate_component_boundary() -> None:
    matrix = json.loads(IMP057_MATRIX.read_text(encoding="utf-8"))
    assert matrix["schema_version"] == 1
    assert matrix["phase"] == "6"
    assert matrix["implementation"] == "IMP-057"
    assert matrix["local_portability_gate_complete"] is False
    assert matrix["accepted_real_machine_result"] is None
    assert [item["id"] for item in matrix["portability_tests"]] == [
        "PORT-001",
        "PORT-003",
        "PORT-013",
    ]
    assert matrix["real_machine_gate"]["status"] == "pending"
    assert matrix["real_machine_gate"]["minimum_local_models"] == 1

    imports = _module_imports(IMP057_INSPECTOR)
    assert imports.isdisjoint(
        {
            "doll.ollama_adapter",
            "doll.ollama_chat_capture",
            "doll.ollama_session_import",
            "doll.local_conversation",
            "doll.streaming_conversation",
        }
    )
    probe = IMP057_PROBE.read_text(encoding="utf-8")
    assert '_ALLOWED_PATHS = frozenset({"/api/tags", "/api/version", "/api/chat"})' in probe
    assert "GenericImportPublisher" in probe
    assert "GenericExportBuilder" in probe
    assert "export_state_package" in probe
    assert "create_state_backup" in probe
    assert "restore_state_backup" in probe


def test_imp_057_ci_migration_runner() -> None:
    root = Path(__file__).resolve().parents[1]
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join((str(root / "src"), str(root)))
    result = subprocess.run(
        [sys.executable, str(IMP057_RUNNER), "--commit-sha", head],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    payload = cast(dict[str, Any], json.loads(result.stdout))

    assert result.returncode == 0, result.stdout
    assert payload["test_id"] == "IMP-057-LOCAL-PORTABILITY-MIGRATION"
    assert payload["result"] == "pass"
    assert payload["evidence_level"] == "ci"
    assert payload["primary_intel_mac_gate"] == "pending"
    assert payload["local_portability_gate_complete"] is False
    assert payload["phase6_gate_complete"] is False
    assert payload["real_runtime_used"] is False
    assert payload["portability_test_ids"] == ["PORT-001", "PORT-003", "PORT-013"]
    assert all(payload["checks"].values())
    evidence = payload["evidence"]
    assert evidence["runtime_mode"] == "synthetic"
    assert evidence["source_adapter_id"] == "ollama-api-session"
    assert evidence["capture_component_id"] == "ollama-chat-capture"
    assert evidence["alternate_component_id"] == "doll-generic-export"
    assert evidence["source_object_counts"]["total"] == 3
    assert evidence["published_object_counts"] == evidence["source_object_counts"]
    assert evidence["duplicate_counts"]["unchanged_reimport_canonical_duplicates"] == 0
    assert evidence["quarantine_counts"]["captured_source"] == 0
    assert evidence["loss_counts_by_severity"]["material"] == 0
    assert evidence["ollama_request_count"] == 3
    assert evidence["allowed_loopback_socket_attempts"] == 0
    assert evidence["rejected_socket_attempts"] == 0


def test_imp_057_lint_diagnostics() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            str(IMP057_PROBE),
            str(IMP057_INSPECTOR),
            str(IMP057_RUNNER),
            str(Path(__file__)),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_state_package_source_dump_for_patch() -> None:
    encoded = base64.b64encode(STATE_PACKAGE_MODULE.read_bytes()).decode("ascii")
    print("STATE_PACKAGE_BASE64_BEGIN")
    for offset in range(0, len(encoded), 4096):
        print(encoded[offset : offset + 4096])
    print("STATE_PACKAGE_BASE64_END")
    raise AssertionError("temporary source transfer")
