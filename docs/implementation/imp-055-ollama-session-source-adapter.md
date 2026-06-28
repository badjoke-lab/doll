# IMP-055 — Offline Ollama API session source adapter

## Status

Implemented for synthetic CI evidence. This slice starts Phase 6 but does not complete the Phase 6 local-portability claim or PORT-013.

## Purpose

IMP-055 adds the first source-specific local-AI portability adapter after the Phase 5 runtime gate. It accepts a documented caller-retained Ollama API chat-session bundle, parses it entirely offline, inventories it without exposing message content, and normalizes supported source objects through the accepted Phase 4A generic staging and reviewed-publication boundary.

Ollama's chat API receives message history from its caller. This implementation therefore supports an explicit client-retained session bundle. It does not claim that the Ollama runtime itself provides a complete native conversation-history export.

## Source identity

The adapter keeps these concepts separate:

- source environment class: `local-ai-runtime-session`;
- provider: unknown unless a later source format can establish one;
- application: `ollama`;
- interface: `ollama.api`;
- runtime: `ollama.local`;
- source format: `ollama-api-chat-session`;
- source format version: `1`;
- source adapter: `ollama-api-session` version `1.0.0`.

Imported model names remain source metadata inside imported external data. They do not create ModelManifestRecords, ModelBindingRecords, active bindings, compatibility claims, trusted identity, or model authority.

## Input boundary

The adapter accepts caller-provided UTF-8 JSON bytes only. It performs no file discovery, application-database inspection, shell-history inspection, log inspection, socket operation, subprocess launch, runtime startup, model lookup, model download, cloud request, or credential access.

The root object contains exactly:

- `format`;
- `format_version`;
- `source_environment_id`;
- `runtime_version`;
- `exported_at`;
- `conversations`.

Each conversation contains exactly:

- `conversation_id`;
- `title`;
- `created_at`;
- `messages`.

Each message contains exactly:

- `message_id`;
- `role`;
- `content`;
- `created_at`;
- `parent_message_ids`;
- `model`;
- `attachments`;
- `tool_calls`.

Attachment entries are metadata-only and contain an identifier, name, optional media type, declared size, and optional SHA-256. Tool-call entries contain an identifier, name, and JSON object of arguments.

Duplicate JSON object keys, non-finite constants, invalid UTF-8, wrong root shapes, unsupported versions, invalid timestamps, invalid identifiers, invalid attachment hashes or sizes, malformed tool-call arguments, excessive input, and excessive normalized object counts fail closed before publication.

## Normalization

The source adapter transforms accepted source objects into the existing `doll-generic-import` object model in memory:

- source conversations become `conversation` objects;
- user messages become `user-message` objects;
- assistant messages become `assistant-message` objects;
- system messages become `system-message` objects;
- tool-role messages become `tool-result` objects;
- tool calls become `tool-request` objects;
- attachment declarations become `attachment` objects with metadata only;
- unknown roles become unsupported source objects and are preserved through the existing quarantine and loss path;
- parent message identifiers remain explicit parent relationships.

Source object identifiers are namespaced by conversation and message where necessary. The same accepted input and adapter version produce deterministic normalized identifiers, source-object hashes, mapping reports, and canonical record identifiers.

The adapter restores the SHA-256 of the original source bytes as the import root hash after in-memory normalization. The existing publisher therefore verifies and optionally retains the exact original bundle rather than the intermediate generic representation.

## Inventory and privacy

The source-specific inventory reports only:

- source root hash;
- format version;
- optional runtime version;
- conversation count;
- message count;
- attachment count;
- tool-call count;
- normalized source-object count.

It does not contain message content, titles, model names, attachment names, tool arguments, paths, usernames, hostnames, credentials, or secrets.

## Reused Phase 4A boundary

IMP-055 deliberately reuses rather than duplicates the existing portability implementation:

- `SourceAdapterContract` and `SourceEnvironmentRecord`;
- deterministic generic staging;
- duplicate classification;
- missing-parent and cycle quarantine;
- explicit mapping and loss reports;
- reviewed publication preview;
- exact approved-plan hash;
- stable source-object mappings;
- unchanged-source idempotency;
- changed-source conflict detection;
- original-source hash or managed snapshot preservation;
- atomic canonical publication;
- rollback and cleanup on publication failure.

No new authoritative record type is introduced. Doll State schema version 3 and State Package format version 2 remain unchanged.

## Authority boundary

Every normalized object remains imported external data. Imported prompts, system messages, tool calls, model names, profile text, and attachment metadata cannot directly create or change:

- system or durable user policy;
- confirmed memory or facts;
- PermissionRecords;
- credentials or credential scope;
- capability definitions or risk tiers;
- confirmations or approvals;
- model manifests or bindings;
- procedures, checkpoints, blockers, or project completion.

The adapter does not execute tool calls or imported content. Publication creates only the accepted imported conversation, event, provenance, mapping, quarantine, loss, batch, source-environment, and original-source records.

## Synthetic evidence

Tests cover:

- deterministic inventory and normalization;
- one conversation with user and assistant messages;
- explicit parent relationships;
- one tool-call relationship;
- one metadata-only attachment and its explicit material loss;
- exact original-source hash preservation;
- managed source snapshot publication;
- unchanged re-import reuse without duplicate canonical records;
- changed-source review conflict without overwrite;
- identical and conflicting duplicates;
- missing parents and parent cycles;
- unsupported roles;
- duplicate JSON keys and non-finite constants;
- invalid UTF-8 and malformed shapes;
- byte and object limits;
- invalid timestamps, identifiers, attachment metadata, and tool calls;
- absence of network, subprocess, Ollama runtime-adapter, or live-runtime dependencies.

All fixtures are synthetic. No private conversation, application database, model inventory, native installed-model name, or user archive is committed.

## Deliberate limitations

- This is a documented client-retained session format, not proof of a native Ollama history export.
- It does not capture a live session or read an existing application's private storage.
- It does not import model files, Modelfiles, runtime configuration, credentials, or active model bindings.
- Attachment bytes are not accepted; attachment metadata produces explicit loss.
- It is a one-way source adapter and provides no target-specific export back to Ollama.
- It does not establish tested round-trip compatibility.
- It does not complete PORT-013, the private real-machine migration drill, the Phase 6 gate, or a stable local-environment portability claim.

## Follow-up

A later implementation must provide an explicit live capture or supported local-application export path, run the private primary-machine migration drill, retrieve imported context through a different approved execution component, disable or remove the original application, and prove that canonical Doll State and generic export remain usable. That later evidence, not IMP-055 alone, is required for PORT-013.

## Issue

Refs #174.
