# Ollama API chat session bundle — version 1

## Status

This document defines the source format accepted by IMP-055. It is a doll-defined client-retained session bundle for Ollama API use. It is not an Ollama-native export standard and does not claim full Ollama history fidelity.

## Media and encoding

- UTF-8 JSON;
- one root JSON object;
- duplicate object keys are invalid;
- `NaN`, `Infinity`, and other non-standard JSON constants are invalid;
- no archive, executable content, remote reference resolution, or implicit file discovery.

## Root object

The root contains exactly these members:

```json
{
  "format": "ollama-api-chat-session",
  "format_version": "1",
  "source_environment_id": "00000000-0000-0000-0000-000000000000",
  "runtime_version": "runtime-version-or-null",
  "exported_at": "2026-01-01T00:00:00Z",
  "conversations": []
}
```

Rules:

- `format` is exactly `ollama-api-chat-session`;
- `format_version` is exactly `1`;
- `source_environment_id` is a canonical UUID string identifying one stable source environment;
- `runtime_version` is text or `null` and remains source metadata;
- `exported_at` is an ISO 8601 timestamp with timezone;
- `conversations` is a list.

## Conversation object

Each conversation contains exactly:

```json
{
  "conversation_id": "conversation-source-id",
  "title": "Optional title",
  "created_at": "2026-01-01T00:00:00Z",
  "messages": []
}
```

Rules:

- `conversation_id` is required non-empty text without control characters;
- `title` is text or `null`;
- `created_at` is an ISO 8601 timestamp with timezone or `null`;
- `messages` is a list;
- source identifiers are preserved as source identity, not interpreted as permissions or authority.

## Message object

Each message contains exactly:

```json
{
  "message_id": "message-source-id",
  "role": "user",
  "content": "message text",
  "created_at": "2026-01-01T00:00:00Z",
  "parent_message_ids": [],
  "model": "source-model-metadata-or-null",
  "attachments": [],
  "tool_calls": []
}
```

Rules:

- `message_id` is required non-empty text without control characters;
- `role` is required text;
- `content` is text and may be empty;
- `created_at` is an ISO 8601 timestamp with timezone or `null`;
- `parent_message_ids` is a list of message source identifiers;
- an empty parent list attaches the message directly to its conversation;
- `model` is text or `null` and remains non-authoritative source metadata;
- `attachments` is a list of attachment metadata objects;
- `tool_calls` is a list of tool-call data objects.

Version 1 maps these roles:

| Source role | Generic source type |
|---|---|
| `user` | `user-message` |
| `assistant` | `assistant-message` |
| `system` | `system-message` |
| `tool` | `tool-result` |

Other roles enter the unsupported-source quarantine and loss path. They are not silently discarded and do not gain authority.

## Attachment metadata object

Each attachment contains exactly:

```json
{
  "attachment_id": "attachment-source-id",
  "name": "file-name.ext",
  "media_type": "application/octet-stream",
  "size_bytes": 123,
  "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
}
```

Rules:

- `attachment_id` and `name` are required non-empty text;
- `media_type` is text or `null`;
- `size_bytes` is a non-negative integer;
- `sha256` is a lowercase hexadecimal SHA-256 or `null`;
- attachment bytes are never embedded, followed, fetched, or read by this format;
- version 1 preserves metadata only and records explicit material loss.

## Tool-call object

Each tool call contains exactly:

```json
{
  "tool_call_id": "tool-call-source-id",
  "name": "tool-name",
  "arguments": {
    "key": "value"
  }
}
```

Rules:

- `tool_call_id` and `name` are required non-empty text;
- `arguments` is a JSON object;
- imported tool calls are data only and are never executed;
- tool-call declarations cannot create capabilities, permissions, risk tiers, credentials, confirmations, or side effects.

## Determinism and source hashes

The SHA-256 of the exact accepted source bytes is the import root hash. Normalized source-object hashes and canonical IDs are deterministic for the same source environment, adapter version, and accepted source object.

Reformatting otherwise equivalent JSON changes the root hash because it changes the original source bytes. Source-object mappings remain based on normalized object content and stable source identifiers.

## Limits

The adapter contract declares bounded limits for:

- total input bytes;
- normalized object count;
- attachment metadata bytes;
- JSON nesting depth.

Inputs outside the declared limits fail closed or enter the accepted quarantine path. The default implementation does not read attachment bytes and opens no socket or subprocess.

## Authority and privacy

All imported content is external data. Source system messages, model names, tool calls, attachment metadata, and conversation text cannot become confirmed memory, policy, permission, credentials, capabilities, confirmations, model bindings, checkpoints, or completed project work automatically.

Shareable evidence and inventory must not expose message content, titles, model names, attachment names, tool arguments, local paths, usernames, hostnames, credentials, or secrets.
