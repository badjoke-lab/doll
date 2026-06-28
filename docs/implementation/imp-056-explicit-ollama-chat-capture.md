# IMP-056 — Explicit loopback Ollama chat session capture

## Status

Implemented with deterministic injected-transport CI evidence. Real primary Intel Mac capture, import, application-removal, and PORT-013 evidence remain pending.

## Purpose

IMP-056 adds the first explicit live source-capture path for Phase 6. A caller selects one already-installed local Ollama model by opaque model ID, supplies one approved text turn and exact session identities, and receives an updated `ollama-api-chat-session` version 1 bundle that the IMP-055 source adapter accepts.

The service captures only content passed directly to it and the bounded assistant response returned by the declared local runtime. It does not inspect Ollama logs, shell or terminal history, private application databases, arbitrary files, or unrelated sessions.

## Runtime boundary

The service requires `OllamaAdapterConfig(local_only_confirmed=True)` and reuses the accepted fixed IPv4 loopback endpoint and transport from IMP-049. The transport allowlist adds only:

```text
POST /api/chat
```

The complete non-streaming capture request sequence is:

1. `GET /api/tags` to resolve one opaque model ID through the existing local inventory;
2. `GET /api/version` to bind the returned source bundle to the observed local runtime version;
3. `POST /api/chat` with one exact text-only history and `stream = false`.

The caller cannot provide a host. Proxy, redirect, remote endpoint, credential, cloud fallback, automatic model selection, model download, process launch, and runtime installation paths are absent.

Cloud-marked inventory entries remain filtered by the existing Ollama adapter before model selection. A requested opaque model ID must resolve to exactly one available local inventory entry.

## Capture request

The typed request contains:

- one opaque model ID;
- one canonical source-environment UUID;
- one conversation source ID;
- one new user-message source ID;
- one new assistant-message source ID;
- one non-blank user text value hidden from object representation;
- exact user, conversation, and export timestamps;
- an optional existing IMP-055 bundle hidden from object representation;
- an optional title only when starting a new conversation;
- one bounded maximum assistant-output size.

New capture requires a conversation creation timestamp. Append capture cannot replace the existing title or creation time. New message identifiers must differ and must not collide with existing source identifiers.

## Existing history boundary

Before any chat request, an existing bundle is validated through IMP-055 and then restricted further for this first live slice:

- the source-environment identity must match exactly;
- exactly one selected conversation must exist;
- history must be one linear parent chain;
- message source IDs must be unique;
- roles must already be supported text roles;
- attachment metadata and tool calls are rejected rather than silently omitted;
- history length must remain within the capture limit;
- the retained runtime version, when present, must match the current runtime before capture continues.

Unrelated conversations in the same valid bundle are preserved while the selected conversation is appended.

## Chat request and response

The request body contains only:

```json
{
  "model": "resolved-native-local-model",
  "messages": [
    {
      "role": "user",
      "content": "caller-provided-text"
    }
  ],
  "stream": false
}
```

Prior supported text history is included when appending. Model names are resolved internally from the opaque inventory identity and are not accepted as free caller input.

The response must satisfy all of the following:

- bounded UTF-8 JSON object with no duplicate keys or non-standard constants;
- HTTP 200;
- exact returned native model identity;
- valid timezone-bearing response timestamp;
- `done = true`;
- completion reason `stop`, `length`, or omitted as the accepted stop equivalent;
- one assistant message object;
- non-blank, non-null-bearing text within the caller's output bound;
- no non-empty images, tool calls, or thinking payload;
- no undeclared message members.

Malformed, oversized, wrong-model, unfinished, non-assistant, multimodal, tool-bearing, timed-out, cancelled, missing-model, and transport-failed results fail closed with bounded failure codes. Prompt, response, native model name, host, path, user identity, credential, and private provider detail are absent from failure objects.

## Returned source bundle

On success, the service appends:

1. one user message whose parent is the previous terminal message or the conversation root;
2. one assistant message whose parent is the new user message.

The assistant message records the resolved native model only as source metadata. The root runtime version and export timestamp are updated. The complete canonical JSON bytes are then revalidated through IMP-055 before they leave the service.

The bounded result exposes only:

- operation ID;
- opaque model ID;
- normalized runtime version;
- exact source-root SHA-256;
- conversation count;
- message count;
- finish reason.

Returned bundle bytes are hidden from representation. They remain source data until the caller explicitly preserves or imports them through the existing portability review and publication path.

## State and authority

IMP-056 writes no Doll State. It creates no conversation, memory, policy, permission, credential, capability, model manifest, model binding, confirmation, procedure, checkpoint, blocker, or project-completion record.

Captured user text and model output remain external source data under IMP-055. The service invokes no tool or capability and cannot convert model output into authority.

No schema migration, State Package format change, or new authoritative record type is introduced.

## Synthetic evidence

Injected deterministic transport tests prove:

- exact tags, version, and chat request order;
- one valid new two-message session;
- deterministic append to four messages;
- preservation of unrelated conversations;
- exact chat request history and non-streaming flag;
- opaque local-model resolution and cloud-model exclusion;
- strict caller identity, timestamp, text, and output-bound validation;
- malformed bundle, wrong environment, wrong conversation, duplicate ID, non-linear history, unsupported role, attachment, tool-call, and runtime-version mismatch rejection before chat;
- inventory, version, status, transport, timeout, cancellation, malformed JSON, duplicate-key, invalid UTF-8, wrong-model, wrong-role, blank, oversized, unfinished, unsupported-reason, and unsupported response-member failures;
- final bundle revalidation through IMP-055;
- absence of State, credential, capability, subprocess, remote HTTP library, or direct tool dependencies.

CI uses no real socket, runtime process, installed model, private conversation, native installed-model inventory, cloud account, credential, model download, or tool execution.

## Deliberate limitations

- The service is an explicit API caller, not an HTTP compatibility proxy for arbitrary applications.
- It does not discover or capture conversations created elsewhere.
- It supports non-streaming text-only capture; attachments, images, tool calls, tool results with structured fidelity, thinking payloads, and multimodal content remain unsupported.
- It does not publish the returned bundle into Doll State automatically.
- It does not provide target-specific export back to Ollama or another application.
- It does not prove a tested round trip, application replacement, PORT-013, or the Phase 6 gate.

## Completion boundary

A separate exact-commit completion slice must run the merged implementation against real local Ollama on the primary Intel Mac, capture reviewed synthetic or approved private test content, import the returned bundle through IMP-055, retrieve the canonical imported context through another approved execution component, disable or remove the original capture path, and confirm that Doll State and generic export remain usable. Only accepted stored evidence from that later drill may advance PORT-013 or the Phase 6 portability claim.

## Issue

Refs #176.
