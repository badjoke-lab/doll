from __future__ import annotations

import ast
from pathlib import Path


def test_model_switch_has_no_cloud_tool_capability_or_process_dependency() -> None:
    path = Path("src/doll/model_switch.py")
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported.update(
        (node.module or "").split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    )
    assert imported.isdisjoint(
        {"http", "requests", "socket", "subprocess", "credential_broker", "capabilities"}
    )
    assert "automatic failover" not in source.lower()
    assert "LocalRuntimeBoundary" in source
    assert ".generate(" in source
    assert ".stream(" not in source
    assert ".inventory(" not in source
