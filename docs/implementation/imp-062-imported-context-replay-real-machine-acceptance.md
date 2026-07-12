# IMP-062 — Primary Intel Mac imported-context replay acceptance

## Status

Implemented with deterministic synthetic CI evidence.

Primary Intel Mac real-machine evidence remains pending until the merged implementation commit is executed with networking operator-confirmed disabled and a privacy-reviewed result is accepted through a separate completion pull request.

Issue: #200

## Objective

Provide a bounded exact-commit acceptance harness for the IMP-061 imported conversation context replay path.

The harness proves that explicitly selected imported canonical text can be passed as data-only untrusted context to a distinct approved local Ollama runtime path without allowing imported content to select the runtime, gain task authority, create privileged records, or bypass the existing prompt-defense and canonical conversation boundaries.

## Accepted basis

IMP-062 composes the accepted contracts established by:

- IMP-019 instruction origins and authority decisions;
- Phase 3 prompt-injection and secret handling;
- Phase 4A generic staging, preview, publication, provenance, mappings, loss, idempotency, and conflict handling;
- IMP-055 and IMP-059 source adapters;
- Phase 5 runtime adapters, model manifests, explicit bindings, and canonical local conversation execution;
- IMP-061 bounded imported-context replay.

It does not create a new authoritative record type, runtime adapter, source adapter, schema version, State Package version, permission path, capability path, or model authority path.

## Acceptance architecture

The probe creates a deterministic non-private synthetic ChatGPT-format source inside a temporary workspace.

The source is staged and published through the accepted ChatGPT and generic publication path. Two imported canonical text events are selected explicitly.

The target is a separate conversation with an explicit active Ollama runtime and model binding. The selected imported events are materialized as immutable `imported_data` instruction origins and enter the rendered model prompt only through `untrusted_content`.

The probe verifies:

- source and target application/runtime paths are distinct;
- selected source mappings resolve to the exact canonical imported events;
- imported origins remain data-only and `untrusted_data`;
- imported content cannot authorize `task_instruction`;
- prompt-injection findings remain advisory and visible;
- one canonical user, context-snapshot, and assistant turn is persisted;
- runtime output remains model-proposed and creates no authority record;
- only declared fixed-loopback Ollama paths are used;
- no non-loopback socket destination is accepted.

## Execution modes

### Synthetic CI mode

CI uses an injected deterministic Ollama transport.

It performs no socket operation and runs on Ubuntu, macOS, and Windows while exercising the same import, replay, prompt, binding, persistence, evidence, and privacy shape used by real-machine mode.

### Real-machine mode

Real-machine mode requires:

- Darwin;
- Intel architecture reported as `x86_64` or `amd64`;
- the exact checked-out commit;
- a clean implementation checkout;
- explicit operator confirmation that networking is disabled;
- explicit local-only confirmation;
- one caller-selected already-installed Ollama model;
- fixed IPv4 loopback to the declared Ollama port.

It does not install or start Ollama, download or remove a model, read native application history, access a provider account, retrieve credentials, invoke tools, or enable cloud fallback.

## Evidence boundary

The public result contains only:

- platform and exact-commit facts;
- booleans;
- counts;
- hashes;
- runtime request and socket-attempt counts;
- bounded non-claim flags.

It excludes:

- native model names;
- source-native identifiers;
- source text;
- user prompt text;
- model response text;
- private paths;
- usernames;
- hostnames;
- credentials;
- secret values.

The raw real-machine result must first be written outside the repository and reviewed manually. A later separate completion pull request may store only a privacy-safe result accepted against the exact merged implementation commit.

## Non-claims

IMP-062 does not establish:

- automatic or semantic retrieval;
- embeddings or vector search;
- model-selected context;
- native ChatGPT or Ollama history discovery;
- attachment-byte or multimodal replay;
- tool or capability execution;
- target-specific export;
- provider round-trip fidelity;
- runtime or model installation;
- cloud portability or automatic cloud fallback;
- complete application replacement;
- the complete Phase 6 gate;
- stable general anti-lock-in.
