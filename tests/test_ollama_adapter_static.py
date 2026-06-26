from __future__ import annotations

import ast
from pathlib import Path

MODULE = Path("src/doll/ollama_adapter.py")


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

    assert api_paths == {"/api/generate", "/api/tags", "/api/version"}
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
