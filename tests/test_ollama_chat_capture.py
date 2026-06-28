from __future__ import annotations

import ast
import json
import time
from collections.abc import Iterable
from dataclasses import replace
from pathlib import Path
from typing import cast
from uuid import uuid4

import pytest

from doll.ollama_adapter import (
    MAX_OLLAMA_JSON_BYTES,
    OllamaAdapterConfig,
    OllamaEndpoint,
    OllamaHttpResponse,
    OllamaTransportFailure,
    ollama_model_id,
)
from doll.ollama_chat_capture import (
    OllamaChatCaptureError,
    OllamaChatCaptureFailure,
    OllamaChatCaptureRequest,
    OllamaChatCaptureService,
)
from doll.ollama_session_import import OllamaSessionSourceAdapter
from doll.runtime_adapter import RuntimeAdapterContext, RuntimeCancellationToken

NATIVE_MODEL = "synthetic:1b"
MODEL_ID = ollama_model_id(NATIVE_MODEL)
ENVIRONMENT_ID = "11111111-1111-4111-8111-111111111111"
CONVERSATION_ID = "conversation-a"
T0 = "2026-06-28T17:00:00Z"
T1 = "2026-06-28T17:00:01Z"
T2 = "2026-06-28T17:00:02Z"
T3 = "2026-06-28T17:00:03Z"
T4 = "2026-06-28T17:00:04Z"


def encode(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def model(name: str = NATIVE_MODEL, *, digest: str | None = None) -> dict[str, object]:
    return {
        "name": name,
        "model": name,
        "modified_at": T0,
        "size": 1,
        "digest": digest,
        "details": {"format": "gguf"},
    }


def tags(*entries: object) -> bytes:
    return encode({"models": list(entries)})


def chat_response(
    *,
    model_name: str = NATIVE_MODEL,
    content: object = "assistant reply",
    role: object = "assistant",
    created_at: object = T2,
    done: object = True,
    done_reason: object = "stop",
    message_extra: dict[str, object] | None = None,
    root_extra: dict[str, object] | None = None,
) -> bytes:
    message: dict[str, object] = {"role": role, "content": content}
    if message_extra:
        message.update(message_extra)
    document: dict[str, object] = {
        "model": model_name,
        "created_at": created_at,
        "message": message,
        "done": done,
        "done_reason": done_reason,
    }
    if root_extra:
        document.update(root_extra)
    return encode(document)


class FakeTransport:
    def __init__(self, endpoint: OllamaEndpoint | None = None) -> None:
        self.endpoint = endpoint or OllamaEndpoint()
        self.responses: list[object] = []
        self.requests: list[tuple[str, str, bytes | None, int]] = []

    def request_json(
        self,
        method: str,
        path: str,
        *,
        body: bytes | None,
        context: RuntimeAdapterContext | None,
        maximum_bytes: int,
    ) -> OllamaHttpResponse:
        del context
        self.requests.append((method, path, body, maximum_bytes))
        if not self.responses:
            raise AssertionError("unexpected request")
        value = self.responses.pop(0)
        if isinstance(value, BaseException):
            raise value
        return cast(OllamaHttpResponse, value)

    def stream_ndjson(
        self,
        path: str,
        *,
        body: bytes,
        context: RuntimeAdapterContext,
        maximum_bytes: int,
        maximum_line_bytes: int,
    ) -> Iterable[bytes]:
        del path, body, context, maximum_bytes, maximum_line_bytes
        raise AssertionError("chat capture must not stream")


def context(
    *,
    operation_id: str = "capture-1",
    timeout: float = 30.0,
    cancellation: RuntimeCancellationToken | None = None,
) -> RuntimeAdapterContext:
    return RuntimeAdapterContext(
        operation_id,
        time.monotonic() + timeout,
        cancellation or RuntimeCancellationToken(),
    )


def request(
    *,
    existing_bundle: bytes | None = None,
    environment_id: str = ENVIRONMENT_ID,
    conversation_id: str = CONVERSATION_ID,
    user_message_id: str = "message-1",
    assistant_message_id: str = "message-2",
    user_text: str = "user prompt",
    user_created_at: str = T1,
    exported_at: str = T3,
    model_id: str = MODEL_ID,
    max_output_chars: int = 1024,
) -> OllamaChatCaptureRequest:
    return OllamaChatCaptureRequest(
        model_id=model_id,
        source_environment_id=environment_id,
        conversation_id=conversation_id,
        user_message_id=user_message_id,
        assistant_message_id=assistant_message_id,
        user_text=user_text,
        user_created_at=user_created_at,
        exported_at=exported_at,
        existing_bundle=existing_bundle,
        title=None if existing_bundle else "Synthetic session",
        conversation_created_at=None if existing_bundle else T0,
        max_output_chars=max_output_chars,
    )


def service(fake: FakeTransport | None = None) -> tuple[OllamaChatCaptureService, FakeTransport]:
    transport = fake or FakeTransport()
    capture = OllamaChatCaptureService(
        OllamaAdapterConfig(local_only_confirmed=True),
        transport=transport,
    )
    return capture, transport


def ready(fake: FakeTransport, *, response: bytes | None = None) -> None:
    fake.responses.extend(
        [
            OllamaHttpResponse(200, tags(model(), model("remote:cloud"))),
            OllamaHttpResponse(200, encode({"version": "0.30.11"})),
            OllamaHttpResponse(200, response or chat_response()),
        ]
    )


def decoded_bundle(bundle: bytes) -> dict[str, object]:
    value = json.loads(bundle)
    assert isinstance(value, dict)
    return cast(dict[str, object], value)


def conversations(document: dict[str, object]) -> list[dict[str, object]]:
    value = document["conversations"]
    assert isinstance(value, list)
    return cast(list[dict[str, object]], value)


def messages(conversation: dict[str, object]) -> list[dict[str, object]]:
    value = conversation["messages"]
    assert isinstance(value, list)
    return cast(list[dict[str, object]], value)


def test_new_capture_uses_exact_local_requests_and_returns_valid_bundle() -> None:
    capture, fake = service()
    ready(fake)

    result = capture.capture(request(), context())

    assert result.operation_id == "capture-1"
    assert result.model_id == MODEL_ID
    assert result.runtime_version == "0.30.11"
    assert result.conversation_count == 1
    assert result.message_count == 2
    assert result.finish_reason == "stop"
    assert len(result.source_root_hash) == 64
    assert "user prompt" not in repr(result)
    assert "assistant reply" not in repr(result)
    assert NATIVE_MODEL not in repr(result)
    assert "user prompt" not in json.dumps(result.canonical_summary())

    assert [(method, path) for method, path, _, _ in fake.requests] == [
        ("GET", "/api/tags"),
        ("GET", "/api/version"),
        ("POST", "/api/chat"),
    ]
    assert all(limit == MAX_OLLAMA_JSON_BYTES for _, _, _, limit in fake.requests)
    body = fake.requests[-1][2]
    assert body is not None
    assert json.loads(body) == {
        "model": NATIVE_MODEL,
        "messages": [{"role": "user", "content": "user prompt"}],
        "stream": False,
    }

    document = decoded_bundle(result.bundle_bytes)
    assert document["source_environment_id"] == ENVIRONMENT_ID
    assert document["runtime_version"] == "0.30.11"
    conversation = conversations(document)[0]
    assert conversation["conversation_id"] == CONVERSATION_ID
    captured = messages(conversation)
    assert [item["role"] for item in captured] == ["user", "assistant"]
    assert captured[0]["parent_message_ids"] == []
    assert captured[1]["parent_message_ids"] == ["message-1"]
    assert captured[0]["model"] is None
    assert captured[1]["model"] == NATIVE_MODEL

    staged = OllamaSessionSourceAdapter().stage(
        result.bundle_bytes,
        import_batch_id=str(uuid4()),
        started_at=T4,
    )
    assert staged.inventory.conversation_count == 1
    assert staged.inventory.message_count == 2
    assert staged.inventory.runtime_version == "0.30.11"


def test_append_preserves_existing_and_unrelated_conversation() -> None:
    capture, fake = service()
    ready(fake)
    first = capture.capture(request(), context())
    first_document = decoded_bundle(first.bundle_bytes)
    unrelated = {
        "conversation_id": "conversation-other",
        "title": "Unrelated",
        "created_at": T0,
        "messages": [],
    }
    cast(list[object], first_document["conversations"]).append(unrelated)
    existing = encode(first_document)

    second_capture, second_fake = service()
    ready(second_fake, response=chat_response(content="second reply", created_at=T4))
    second = second_capture.capture(
        request(
            existing_bundle=existing,
            user_message_id="message-3",
            assistant_message_id="message-4",
            user_text="second prompt",
            user_created_at=T3,
            exported_at=T4,
        ),
        context(operation_id="capture-2"),
    )

    assert second.message_count == 4
    document = decoded_bundle(second.bundle_bytes)
    output_conversations = conversations(document)
    assert output_conversations[1] == unrelated
    captured = messages(output_conversations[0])
    assert [item["message_id"] for item in captured] == [
        "message-1",
        "message-2",
        "message-3",
        "message-4",
    ]
    assert captured[2]["parent_message_ids"] == ["message-2"]
    assert captured[3]["parent_message_ids"] == ["message-3"]
    body = second_fake.requests[-1][2]
    assert body is not None
    assert json.loads(body)["messages"] == [
        {"role": "user", "content": "user prompt"},
        {"role": "assistant", "content": "assistant reply"},
        {"role": "user", "content": "second prompt"},
    ]


def test_length_finish_reason_is_accepted() -> None:
    capture, fake = service()
    ready(fake, response=chat_response(done_reason="length"))
    assert capture.capture(request(), context()).finish_reason == "length"


def test_configuration_and_request_contracts_fail_closed() -> None:
    with pytest.raises(OllamaChatCaptureError, match="configuration"):
        OllamaChatCaptureService(cast(OllamaAdapterConfig, object()))
    with pytest.raises(OllamaChatCaptureError, match="not confirmed"):
        OllamaChatCaptureService(OllamaAdapterConfig())
    with pytest.raises(OllamaChatCaptureError, match="transport"):
        OllamaChatCaptureService(
            OllamaAdapterConfig(local_only_confirmed=True),
            transport=FakeTransport(OllamaEndpoint(12000)),
        )
    with pytest.raises(OllamaChatCaptureError, match="source adapter"):
        OllamaChatCaptureService(
            OllamaAdapterConfig(local_only_confirmed=True),
            transport=FakeTransport(),
            source_adapter=cast(OllamaSessionSourceAdapter, object()),
        )

    base = request()
    invalids: list[tuple[dict[str, object], str]] = [
        ({"model_id": "bad model"}, "model ID"),
        ({"source_environment_id": "bad"}, "environment ID"),
        ({"conversation_id": ""}, "conversation ID"),
        ({"user_message_id": "bad\nid"}, "user message ID"),
        ({"assistant_message_id": "message-1"}, "identifiers must differ"),
        ({"user_text": "   "}, "must not be blank"),
        ({"user_text": "x\x00y"}, "user text"),
        ({"user_created_at": "bad"}, "timestamp"),
        ({"exported_at": T0}, "precedes"),
        ({"conversation_created_at": T2}, "follows"),
        ({"max_output_chars": 0}, "maximum"),
        ({"max_output_chars": True}, "maximum"),
    ]
    for changes, message in invalids:
        with pytest.raises(OllamaChatCaptureError, match=message):
            replace(base, **cast(Any, changes))

    with pytest.raises(OllamaChatCaptureError, match="creation timestamp"):
        OllamaChatCaptureRequest(
            model_id=MODEL_ID,
            source_environment_id=ENVIRONMENT_ID,
            conversation_id=CONVERSATION_ID,
            user_message_id="u",
            assistant_message_id="a",
            user_text="text",
            user_created_at=T1,
            exported_at=T2,
        )
    with pytest.raises(OllamaChatCaptureError, match="non-empty bytes"):
        replace(base, existing_bundle=b"", title=None, conversation_created_at=None)
    with pytest.raises(OllamaChatCaptureError, match="cannot replace"):
        replace(base, existing_bundle=b"{}")

    capture, _ = service()
    with pytest.raises(OllamaChatCaptureError, match="request"):
        capture.capture(cast(OllamaChatCaptureRequest, object()), context())
    with pytest.raises(OllamaChatCaptureError, match="context"):
        capture.capture(base, cast(RuntimeAdapterContext, object()))


def test_existing_bundle_identity_and_history_rejections_precede_chat() -> None:
    capture, fake = service()
    ready(fake)
    first = capture.capture(request(), context()).bundle_bytes

    cases: list[tuple[bytes, dict[str, object], str]] = []
    wrong_environment = decoded_bundle(first)
    wrong_environment["source_environment_id"] = str(uuid4())
    cases.append((encode(wrong_environment), {}, "environment identity"))

    wrong_conversation = decoded_bundle(first)
    conversations(wrong_conversation)[0]["conversation_id"] = "other"
    cases.append((encode(wrong_conversation), {}, "exactly one selected"))

    duplicate_conversation = decoded_bundle(first)
    cast(list[object], duplicate_conversation["conversations"]).append(
        conversations(duplicate_conversation)[0].copy()
    )
    cases.append((encode(duplicate_conversation), {}, "exactly one selected"))

    duplicate_message = decoded_bundle(first)
    messages(conversations(duplicate_message)[0])[1]["message_id"] = "message-1"
    cases.append((encode(duplicate_message), {}, "duplicate message ID"))

    non_linear = decoded_bundle(first)
    messages(conversations(non_linear)[0])[1]["parent_message_ids"] = []
    cases.append((encode(non_linear), {}, "linear conversation"))

    unsupported_role = decoded_bundle(first)
    messages(conversations(unsupported_role)[0])[0]["role"] = "developer"
    cases.append((encode(unsupported_role), {}, "role is unsupported"))

    attachment = decoded_bundle(first)
    messages(conversations(attachment)[0])[0]["attachments"] = [
        {
            "attachment_id": "attachment-1",
            "name": "file",
            "media_type": None,
            "size_bytes": 0,
            "sha256": None,
        }
    ]
    cases.append((encode(attachment), {}, "unsupported for text capture"))

    tool = decoded_bundle(first)
    messages(conversations(tool)[0])[1]["tool_calls"] = [
        {"tool_call_id": "tool-1", "name": "x", "arguments": {}}
    ]
    cases.append((encode(tool), {}, "unsupported for text capture"))

    runtime_mismatch = decoded_bundle(first)
    runtime_mismatch["runtime_version"] = "older"
    cases.append((encode(runtime_mismatch), {}, "runtime version differs"))

    for bundle, changes, expected in cases:
        next_capture, next_fake = service()
        next_fake.responses.extend(
            [
                OllamaHttpResponse(200, tags(model())),
                OllamaHttpResponse(200, encode({"version": "0.30.11"})),
            ]
        )
        with pytest.raises(OllamaChatCaptureError, match=expected):
            next_capture.capture(
                request(
                    existing_bundle=bundle,
                    user_message_id="message-3",
                    assistant_message_id="message-4",
                    user_created_at=T3,
                    exported_at=T4,
                    **cast(Any, changes),
                ),
                context(),
            )
        assert all(path != "/api/chat" for _, path, _, _ in next_fake.requests)

    with pytest.raises(OllamaChatCaptureError, match="bundle validation"):
        service()[0].capture(
            request(
                existing_bundle=b"not-json",
                user_message_id="message-3",
                assistant_message_id="message-4",
            ),
            context(),
        )


def test_model_inventory_and_transport_failures_are_bounded() -> None:
    cases: list[tuple[object, str]] = [
        (OllamaHttpResponse(200, tags(model("only:cloud"))), "model_not_found"),
        (OllamaHttpResponse(200, tags(model("other:1b"))), "model_not_found"),
        (OllamaHttpResponse(500, b"private inventory detail"), "runtime_unavailable"),
        (OllamaTransportFailure("timeout"), "timeout"),
        (OllamaTransportFailure("cancelled"), "cancelled"),
        (OllamaTransportFailure("resource_limit"), "resource_limit"),
    ]
    for value, code in cases:
        capture, fake = service()
        fake.responses.append(value)
        with pytest.raises(OllamaChatCaptureFailure) as exc:
            capture.capture(request(), context())
        assert exc.value.code == code
        assert "private inventory detail" not in str(exc.value)
        assert "user prompt" not in str(exc.value)
        assert NATIVE_MODEL not in str(exc.value)

    token = RuntimeCancellationToken()
    token.cancel()
    capture, fake = service()
    fake.responses.append(OllamaHttpResponse(200, tags(model())))
    with pytest.raises(OllamaChatCaptureFailure) as exc:
        capture.capture(request(), context(cancellation=token))
    assert exc.value.code == "cancelled"


def test_version_failures_are_bounded_and_do_not_chat() -> None:
    cases: list[tuple[object, str]] = [
        (OllamaHttpResponse(503, b"private"), "runtime_unavailable"),
        (OllamaHttpResponse(200, b"not-json"), "invalid_response"),
        (OllamaHttpResponse(200, b'{"version":"1","version":"2"}'), "invalid_response"),
        (OllamaHttpResponse(200, encode({})), "invalid_response"),
        (OllamaHttpResponse(200, encode({"version": "bad version"})), "invalid_response"),
        (OllamaTransportFailure("failure"), "adapter_failure"),
    ]
    for value, code in cases:
        capture, fake = service()
        fake.responses.extend([OllamaHttpResponse(200, tags(model())), value])
        with pytest.raises(OllamaChatCaptureFailure) as exc:
            capture.capture(request(), context())
        assert exc.value.code == code
        assert all(path != "/api/chat" for _, path, _, _ in fake.requests)


def test_chat_status_and_transport_failures_are_bounded() -> None:
    cases: list[tuple[object, str]] = [
        (OllamaHttpResponse(404, b"private"), "model_not_found"),
        (OllamaHttpResponse(503, b"private"), "adapter_failure"),
        (OllamaTransportFailure("failure"), "adapter_failure"),
        (OllamaTransportFailure("timeout"), "timeout"),
        (OllamaTransportFailure("invalid_response"), "invalid_response"),
    ]
    for value, code in cases:
        capture, fake = service()
        fake.responses.extend(
            [
                OllamaHttpResponse(200, tags(model())),
                OllamaHttpResponse(200, encode({"version": "0.30.11"})),
                value,
            ]
        )
        with pytest.raises(OllamaChatCaptureFailure) as exc:
            capture.capture(request(), context())
        assert exc.value.code == code
        assert "private" not in str(exc.value)


def test_malformed_chat_responses_fail_closed() -> None:
    malformed: list[tuple[bytes, str]] = [
        (b"not-json", "invalid_response"),
        (b"[]", "invalid_response"),
        (b'{"model":"x","model":"y"}', "invalid_response"),
        (b'{"model":NaN}', "invalid_response"),
        (b"\xff", "invalid_response"),
        (encode({}), "invalid_response"),
        (chat_response(model_name="other:1b"), "invalid_response"),
        (chat_response(created_at=None), "invalid_response"),
        (chat_response(created_at="bad"), "invalid_response"),
        (chat_response(done=False), "invalid_response"),
        (chat_response(done_reason="other"), "invalid_response"),
        (encode({"model": NATIVE_MODEL, "created_at": T2, "done": True}), "invalid_response"),
        (chat_response(role="user"), "invalid_response"),
        (chat_response(content=None), "invalid_response"),
        (chat_response(content="   "), "invalid_response"),
        (chat_response(content="x\x00y"), "invalid_response"),
        (chat_response(message_extra={"unknown": True}), "invalid_response"),
        (chat_response(message_extra={"images": ["x"]}), "invalid_response"),
        (chat_response(message_extra={"tool_calls": [{}]}), "invalid_response"),
        (chat_response(message_extra={"thinking": "private"}), "invalid_response"),
    ]
    for response, code in malformed:
        capture, fake = service()
        ready(fake, response=response)
        with pytest.raises(OllamaChatCaptureFailure) as exc:
            capture.capture(request(), context())
        assert exc.value.code == code
        assert "private" not in str(exc.value)

    capture, fake = service()
    ready(fake, response=chat_response(content="abcd"))
    with pytest.raises(OllamaChatCaptureFailure) as exc:
        capture.capture(request(max_output_chars=3), context())
    assert exc.value.code == "resource_limit"


def test_bundle_serialization_and_final_validation_are_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import doll.ollama_chat_capture as module

    with pytest.raises(OllamaChatCaptureError, match="serializable"):
        module._encode_bundle({"bad": {1, 2}})

    capture, fake = service()
    ready(fake)
    monkeypatch.setattr(module, "_encode_bundle", lambda document: b"not-json")
    with pytest.raises(OllamaChatCaptureError, match="bundle validation"):
        capture.capture(request(), context())


def test_module_has_no_state_tool_credential_or_cloud_dependency() -> None:
    source = Path("src/doll/ollama_chat_capture.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported.update(
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    )
    for forbidden in (
        "socket",
        "subprocess",
        "requests",
        "urllib",
        "httpx",
        "doll.state",
        "doll.state_repository",
        "doll.capabilities",
        "doll.credential_broker",
    ):
        assert forbidden not in imported
    assert '"/api/chat"' in source
    assert "save_" not in source
    assert "create_record" not in source


def test_failure_representation_is_bounded() -> None:
    failure = OllamaChatCaptureFailure("timeout")
    assert failure.code == "timeout"
    assert str(failure) == "Ollama chat capture failure: timeout"
    assert "prompt" not in repr(failure)
