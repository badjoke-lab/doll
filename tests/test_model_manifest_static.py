from __future__ import annotations

import ast
from pathlib import Path

from doll.state_package_registry import get_authoritative_record_registry


def test_model_manifest_module_has_no_runtime_or_network_authority() -> None:
    source = Path("src/doll/model_manifest.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imports.update(
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    )
    assert imports.isdisjoint(
        {"http", "urllib", "requests", "socket", "subprocess", "ollama", "cloud"}
    )
    for forbidden in (
        "urlopen",
        "api_key",
        "authorization",
        "credential_broker",
        "capability_broker",
        "secret_store",
        "runtime_adapter",
    ):
        assert forbidden not in source.lower()


def test_package_v2_registers_manifest_and_binding_categories_as_optional() -> None:
    registry = get_authoritative_record_registry(2)
    assert registry.by_record_type["runtime_manifest"].required_member is False
    assert registry.by_record_type["model_manifest"].required_member is False
    assert registry.by_record_type["model_binding"].required_member is False
