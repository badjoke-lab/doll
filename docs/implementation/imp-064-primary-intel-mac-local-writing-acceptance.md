# IMP-064 — Primary Intel Mac local writing acceptance

## Status

Acceptance infrastructure implemented with deterministic synthetic CI evidence.

Primary Intel Mac real-machine evidence remains pending until the merged implementation commit is executed with networking operator-confirmed disabled and a privacy-reviewed content-free result is accepted through a separate completion pull request.

## Objective

Provide a bounded exact-commit acceptance harness for the IMP-063 local writing workflow.

The harness proves that `draft`, `revise`, and `summarize` execute through one explicitly selected already-installed local Ollama model without allowing supplied writing material to become task authority, select the runtime, mutate authoritative state, retrieve credentials, or execute capabilities.

## Accepted basis

IMP-064 composes the accepted contracts established by:

- IMP-019 immutable instruction origins and authority decisions;
- IMP-020 prompt-defense and secret-safe context packaging;
- Phase 4A canonical conversation, provenance, and non-authority rules;
- IMP-048 through IMP-054 runtime adapters, manifests, bindings, canonical local turns, and primary Intel Mac acceptance conventions;
- IMP-063 bounded local writing workflow.

It does not create a new authoritative record type, schema version, State Package version, runtime adapter, model binding type, permission path, credential path, capability path, or cloud path.

## Acceptance architecture

The probe creates a temporary non-private workspace and one canonical target conversation.

It binds one deterministic synthetic adapter in CI mode or one explicitly selected already-installed Ollama model in real-machine mode. It then executes:

1. one `draft` turn with no source material;
2. one `revise` turn with deterministic source material;
3. one `summarize` turn whose deterministic source contains a hostile embedded instruction.

For revision and summarization, source material is represented as immutable `external_content`, created through the accepted `extractor` / `extraction` origin combination, classified as `untrusted_data`, and passed only through `untrusted_content`.

The current user request remains the only `task_instruction` authority.

The probe verifies:

- all three workflow modes complete through the canonical user/context/assistant graph;
- draft creates no source instruction origin;
- revise and summarize each create exactly one source instruction origin;
- source material is absent from `current_user_instruction` and present only in `untrusted_content`;
- the hostile source remains data-only and produces an advisory prompt-injection finding;
- no policy, permission, capability, credential, confirmed memory, trusted fact, project, work item, procedure, checkpoint, or model binding mutation is created by a workflow turn;
- runtime and model identifiers in evidence are represented only through bounded hashes;
- failure and non-claim flags remain explicit.

## CI mode

CI uses an injected deterministic Ollama-compatible transport.

It performs no socket operation, process launch, model download, runtime installation, provider access, credential retrieval, tool execution, capability execution, or cloud fallback.

Dedicated acceptance must run on Ubuntu, macOS, and Windows.

CI evidence alone does not establish real local-runtime execution.

## Real-machine mode

Real-machine mode requires:

- the exact checked-out implementation commit;
- Darwin on Intel (`x86_64` or `amd64`);
- networking operator-confirmed disabled;
- explicit local-only confirmation;
- one caller-selected already-installed local Ollama model;
- fixed IPv4 loopback only;
- no runtime or model installation or download;
- no process launch by the runner;
- no cloud provider or credential path.

A socket guard must reject every undeclared destination while permitting only the declared fixed-loopback Ollama endpoint.

## Evidence privacy

The result is content-free and may include only bounded platform facts, booleans, counts, hashes, event counts, runtime request counts, socket-attempt counts, and explicit non-claim flags.

It must not include:

- native model names;
- request text;
- source text;
- prompt text;
- model response text;
- conversation titles or source identifiers;
- absolute paths;
- usernames;
- hostnames;
- credentials;
- secret values;
- private fixture content.

The private-machine runbook writes the result outside the repository and requires manual privacy review before a separate completion pull request may accept evidence.

## Failure boundary

The harness fails closed when:

- the checked-out commit differs from the declared implementation commit;
- the platform is not the accepted primary Intel Mac class;
- offline or local-only confirmation is absent;
- the selected model is unavailable or classified as cloud-hosted;
- any undeclared socket destination is attempted;
- any workflow mode fails;
- canonical graph, source-channel, authority, count, hash, or privacy checks fail;
- the result would contain prohibited content.

## Non-claims

IMP-064 does not establish:

- personal writing quality;
- automatic or semantic retrieval;
- memory or project context selection;
- translation;
- attachments or multimodal input;
- streaming workflow output;
- tools or capability execution;
- cloud portability or fallback;
- target-specific export;
- complete Phase 6;
- stable general anti-lock-in.
