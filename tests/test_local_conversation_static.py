from __future__ import annotations

import ast
from pathlib import Path

MODULE = Path("src/doll/local_conversation.py")


def test_local_conversation_has_no_network_process_or_capability_dependency() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.add(node.module)
    forbidden = {
        "http.client",
        "requests",
        "urllib",
        "subprocess",
        "socket",
        "doll.capability",
        "doll.confirmation",
        "doll.credential_broker",
        "doll.secret_store",
    }
    assert not imports.intersection(forbidden)


def test_result_and_runtime_request_hide_conversation_content_from_repr() -> None:
    source = MODULE.read_text(encoding="utf-8")
    assert "class LocalConversationResult" in source
    assert (
        "user_text:"
        not in source.split("class LocalConversationResult", 1)[1].split(
            "class _CreatedTurnState", 1
        )[0]
    )
    assert (
        "assistant_text:"
        not in source.split("class LocalConversationResult", 1)[1].split(
            "class _CreatedTurnState", 1
        )[0]
    )
    assert "RuntimeGenerationRequest(" in source
    assert "LocalRuntimeBoundary" in source


def test_turn_path_is_workspace_relative_and_operation_opaque() -> None:
    source = MODULE.read_text(encoding="utf-8")
    assert 'return f"conversations/{conversation_id}/turns/{digest}"' in source
    assert "hashlib.sha256(operation_id.encode" in source
    assert "/Users/" not in source
    assert "/home/" not in source
    assert "C:\\\\Users\\\\" not in source
