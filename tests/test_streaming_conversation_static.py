from __future__ import annotations

import ast
from pathlib import Path

MODULE = Path("src/doll/streaming_conversation.py")


def test_streaming_conversation_has_no_network_process_or_capability_dependency() -> None:
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


def test_streaming_result_hides_text_and_uses_existing_canonical_persistence() -> None:
    source = MODULE.read_text(encoding="utf-8")
    result_block = source.split("class LocalStreamingConversationResult", 1)[1].split(
        "class LocalStreamingConversationService", 1
    )[0]
    assert "display_events:" in result_block
    assert "field(repr=False)" in result_block
    assert "assistant_text:" not in result_block
    assert "user_text:" not in result_block
    assert "self.runtime_boundary.stream(" in source
    assert "self._persist_turn(" in source
    assert "stream_transcript" not in source
    assert "stream_delta" not in source


def test_streaming_path_does_not_persist_partial_output_or_private_locations() -> None:
    source = MODULE.read_text(encoding="utf-8")
    assert "WorkspaceFileService" not in source
    assert "save_conversation_event" not in source
    assert "runtime_private_locator" in source
    assert "/Users/" not in source
    assert "/home/" not in source
    assert "C:\\\\Users\\\\" not in source
    assert "cloud" not in source.lower()
