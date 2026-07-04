# ChatGPT conversations.json observed-v1 source format

## Status

Observed provider-specific import boundary for IMP-059. This document does not claim that the internal ChatGPT export schema is a stable OpenAI public API or published format specification.

## Officially documented container

OpenAI documents that a ChatGPT data export contains chat history and may include `conversations.json`. Larger exports may contain numbered conversation JSON files instead.

Official references:

- <https://help.openai.com/en/articles/7260999-how-do-i-export-my-chat-history-and-data>
- <https://help.openai.com/en/articles/9106926>

IMP-059 accepts only one caller-extracted `conversations.json` file. It does not parse the surrounding ZIP and does not aggregate numbered files.

## Adapter identity

```text
source format:             chatgpt-conversations-json
source format version:     observed-v1
source environment class:  cloud-ai-history-export
source adapter id:         chatgpt-conversations
source adapter version:    1.0.0
network behavior:           none
branch behavior:            preserve
attachment behavior:        metadata_only
```

## Input boundary

The caller supplies:

- exact `conversations.json` bytes;
- a source-environment UUID controlled by the caller;
- a non-empty explicit set of conversation IDs to stage;
- an import-batch UUID;
- a staging timestamp;
- an observation timestamp.

The adapter inventories every conversation without exposing content in its summary. Only explicitly selected conversations produce staged content objects.

## Observed conversation graph

The adapter recognizes a root JSON array containing conversation objects. A selected conversation may contain:

- `id` or `conversation_id` as source identity;
- `title`, `create_time`, and `current_node` as source metadata;
- `mapping` as an object keyed by node ID;
- nodes with `message`, `parent`, and `children` members;
- messages with `author`, `content`, timestamps, status, metadata, recipient, and channel members;
- text content represented by `content_type = text` and a list of string `parts`.

This shape is treated as observed adapter behavior only. Unknown provider fields are not silently trusted or discarded; they become explicit unsupported source objects and loss records.

## Supported mapping

The following selected text-only roles map to the accepted generic portability model:

| Source role | Generic source type |
|---|---|
| `user` | `user-message` |
| `assistant` | `assistant-message` |
| `system` | `system-message` |
| `tool` | `tool-result` |

Conversation objects map to `conversation`. Supported message parent relationships are preserved through source node identities. Provider model names, author names, status values, and provider identifiers remain external-data payload metadata and never become Doll authority.

## Unsupported and loss behavior

The adapter routes the following through existing quarantine and mapping/loss reporting:

- non-text content;
- unsupported roles;
- malformed messages or mapping nodes;
- missing parent nodes;
- cyclic parent graphs;
- conflicting duplicate source identifiers;
- attachment or asset references without bytes;
- unknown provider fields;
- unsupported provider objects.

Material loss prevents a full-fidelity claim.

## Parser safety

The adapter rejects:

- empty input;
- input exceeding the declared byte limit;
- invalid UTF-8;
- duplicate JSON object keys;
- non-finite JSON constants;
- a non-list root;
- excessive nesting;
- excessive conversation or staged-object counts;
- invalid, conflicting, or overlong identifiers;
- invalid timestamps;
- empty, duplicate, or missing selected conversation IDs;
- message text exceeding the declared limit.

No source content is executed. The adapter imports no network, HTTP, subprocess, browser, credential, or runtime module.

## Publication and preservation

After staging, the accepted generic publication path provides:

- state-aware preview with no write;
- exact-plan approval;
- unchanged-source idempotency;
- changed-source conflict blocking;
- optional exact-byte original-source preservation;
- atomic publication and failure cleanup;
- external-data authority classification;
- generic inspectable export;
- State Package, backup, restore, and shutdown-escape preservation through existing canonical records.

## Explicit non-claims

This format does not establish:

- ZIP ingestion;
- numbered-file aggregation;
- full ChatGPT account migration;
- sidebar recreation;
- custom-instruction, memory, GPT, settings, subscription, file, or workspace migration;
- attachment-byte recovery;
- target-specific export back to ChatGPT;
- round-trip fidelity;
- PORT-014 completion;
- the complete Phase 6 gate;
- stable general anti-lock-in.
