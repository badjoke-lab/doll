from __future__ import annotations

import ast
from pathlib import Path

MODULE = Path("src/doll/runtime_adapter.py")


def test_runtime_adapter_contract_exposes_no_authority_bearing_dependency() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.add(node.module)

    forbidden_modules = {
        "doll.capability_broker",
        "doll.credential_broker",
        "doll.secret_store",
        "doll.state_repository",
        "httpx",
        "requests",
        "socket",
        "subprocess",
        "urllib",
    }
    assert imports.isdisjoint(forbidden_modules)

    protocol = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "RuntimeAdapter"
    )
    source = ast.get_source_segment(MODULE.read_text(encoding="utf-8"), protocol)
    assert source is not None
    for forbidden_name in (
        "approve",
        "capability_broker",
        "credential",
        "permission",
        "project_complete",
        "secret",
        "state_repository",
    ):
        assert forbidden_name not in source.lower()
