# IMP-059 — Bounded ChatGPT conversations.json source adapter

## Status

Implementation foundation for PORT-014. Synthetic CI evidence may establish only `ci-pass`; project-owner private manual evidence remains required before PORT-014 or ChatGPT history migration support can pass.

## Purpose

IMP-059 adds one offline provider-specific source adapter after the accepted generic and local portability foundations:

```text
caller-extracted conversations.json
        ↓
content-free inventory of all conversations
        ↓
explicit selected conversation IDs
        ↓
observed-v1 graph mapping
        ↓
generic staging and loss report
        ↓
reviewed canonical publication as external data
        ↓
generic export and shutdown escape preservation
```

OpenAI documents that exports contain chat history and may include `conversations.json`; larger exports may use numbered conversation JSON files. The provider's internal graph schema is not treated as a stable public specification. The adapter therefore identifies its supported shape as `observed-v1` and fails or reports loss when the observed shape cannot be handled safely.

## Implementation boundary

The adapter accepts exact caller-provided `conversations.json` bytes only. It performs no:

- export request;
- ZIP parsing or extraction;
- account access;
- browser or desktop automation;
- email handling;
- network request;
- credential, cookie, token, or OAuth access;
- model or runtime execution;
- file discovery;
- background import.

A caller must explicitly provide the source-environment UUID, observation timestamp, import-batch UUID, and non-empty selected conversation IDs.

## Selection and privacy boundary

The adapter inventories all conversations using counts and hashes. It maps message content only for explicitly selected conversation IDs. Unselected conversation text is not copied into the generic staging payload or public acceptance result.

Public and CI evidence contains only bounded classifications, counts, hashes, adapter/version identifiers, platform class, check names, and explicit non-claims. No account identifier, conversation ID, title, prompt, response, model name, path, username, hostname, credential, secret, or private fixture content may be committed.

## Mapping boundary

Supported text-only user, assistant, system, and tool messages map into the existing generic portability object model. Supported source branches remain branches through parent source-object IDs.

Provider-specific values such as model, author, status, current node, and provider identifiers remain external-data source metadata. They cannot create or modify policy, permission, capability, credential, confirmed memory, trusted fact, project state, checkpoint, procedure approval, work completion, or model binding.

Unsupported roles, non-text content, malformed objects, unknown provider fields, attachment references, missing parents, cycles, and conflicting duplicates enter quarantine or mapping/loss reporting. They are not silently omitted from fidelity accounting.

## Publication boundary

IMP-059 reuses the accepted generic import publication path:

- preview is read-only;
- exact plan hash is required;
- unchanged re-import reuses existing canonical records;
- changed source objects create blocking review conflicts;
- exact supplied JSON bytes can be preserved as an optional managed original-source snapshot;
- publication is atomic and failure-safe;
- canonical conversations and events remain imported data;
- generic export and shutdown escape remain provider-independent recovery surfaces.

No schema version, State Package version, or authoritative record type is added.

## Synthetic acceptance

Synthetic CI proves:

1. deterministic source-adapter contract and inventory;
2. explicit selected-only content mapping;
3. branch preservation;
4. source provenance and exact source hash;
5. read-only preview;
6. reviewed publication;
7. exact original-source preservation;
8. unchanged-source idempotency;
9. changed-source conflict blocking;
10. imported-data authority separation;
11. generic inspectable export;
12. shutdown-escape recovery visibility;
13. quarantine and loss handling for malformed and unsupported provider objects;
14. absence of model, runtime, network, cloud credential, preferred UI, or private source dependency.

Machine-readable evidence is stored in `docs/testing/phase-6-chatgpt-history-matrix.json`.

## Private manual completion boundary

The implementation PR may merge with the private gate pending. A later completion step must:

1. obtain a fresh project-owner export through the official user-controlled export flow;
2. extract `conversations.json` outside the repository;
3. run the exact merged implementation commit locally without network or model execution;
4. select a bounded subset of conversations explicitly;
5. review inventory, quarantine, mapping, and loss output;
6. verify canonical publication, generic export, and shutdown-escape preservation;
7. inspect the bounded result for private-data leakage;
8. commit only the privacy-safe result and evidence binding.

Until that result is accepted, PORT-014 remains `ci-pass` and no ChatGPT history migration support claim is allowed.

## Commands

Synthetic CI-equivalent evidence:

```bash
python scripts/run_imp_059_chatgpt_export.py \
  --commit-sha "$(git rev-parse HEAD)"
```

The later private manual command is intentionally not implemented by this synthetic foundation. It must be added or reviewed as part of the privacy-preserving completion workflow rather than accepting arbitrary private paths in CI code.

## Explicit non-claims

IMP-059 does not establish:

- ZIP ingestion;
- numbered-file aggregation;
- automatic full-history import;
- account merge or account rehydration;
- sidebar restoration;
- custom-instruction, memory, GPT, settings, subscription, file, or workspace migration;
- attachment-byte recovery;
- target-specific ChatGPT export;
- provider round-trip fidelity;
- PORT-014 completion;
- the complete Phase 6 gate;
- stable general anti-lock-in.
