# IMP-048 — Local runtime adapter contract

## Status

Implementation of the first bounded Phase 5 slice.

This slice defines a runtime-independent contract and a failure-isolating local boundary. It does not connect Ollama or another real runtime and does not execute a model.

## Contract surface

`src/doll/runtime_adapter.py` provides:

- immutable runtime, health, model-inventory, generation, stream-event, and result records;
- a runtime-checkable `RuntimeAdapter` protocol;
- a deterministic immutable adapter registry;
- bounded cancellation and timeout context;
- a `LocalRuntimeBoundary` that validates adapter declarations and results before exposing them to callers;
- closed failure categories rather than provider-specific exception text;
- explicit offline and no-cloud-fallback declarations;
- deterministic declaration fingerprints and normalized model inventories;
- bounded materialization of ordered streaming transcripts.

The initial contract supports normalized `inventory`, `generate`, and `stream` operations. Runtime connection kinds are descriptive and limited to in-process, local-process, or local-socket adapters.

## Authority and trust boundary

The runtime adapter contract is not an authority boundary.

Adapters are not given a state repository, capability broker, permission service, secret store, credential broker, filesystem service, network client, instruction-origin service, or project-mutation service through this contract. Declared runtime and model capabilities are descriptive data, not permissions.

Model input and output remain transient, untrusted content. The contract does not treat model text as approval, confirmation, evidence, a durable memory, a completed work item, an approved procedure, a cleared blocker, a confirmed checkpoint, or permission to perform a side effect.

Later conversation and capability paths must continue through the accepted Phase 3 safety boundary and the Phase 4A/4B canonical state contracts.

## State and migration effects

This slice introduces no authoritative Doll State record, SQLite migration, state-package member, backup member, restore behavior, portability record, project-continuity record, or generated project-status mutation.

Runtime identifiers, adapter identifiers, model identifiers, operation identifiers, and runtime-private responses remain separate from canonical Doll record identities. No provider-native or runtime-private object becomes authoritative state.

Because there are no persistent schema changes, this contract can be removed without rewriting existing Doll State or invalidating Phase 2, Phase 4A, or Phase 4B evidence.

## Secret and credential effects

No credential is accepted or retrieved by the contract. No cloud account or provider key is required.

Prompt and output text are excluded from dataclass representations. Adapter exceptions are normalized to closed failure codes, so provider messages, private paths, hostnames, and secret values are not propagated by the boundary.

This representation protection is not a replacement for the accepted secret-classification, redaction, model-context, and output policies. Callers must apply those policies before supplying content to a future real runtime and before presenting or persisting output.

## Network and process effects

The implementation performs no network request, process launch, socket connection, model download, runtime installation, or cloud fallback.

Adapter declarations must explicitly state that they are local-only, have cloud fallback disabled, and do not silently download models. IMP-048 tests use synthetic in-memory adapters only and require no running service, preferred UI, model, provider, or network route.

No separate real-machine acceptance run is required for this contract-only slice. Real hardware and offline-runtime evidence begins with the first concrete local runtime adapter.

## Failure and resource boundary

The boundary returns deterministic outcomes for:

- unavailable or degraded runtimes;
- missing adapters and unsupported operations;
- malformed declarations, inventories, generation responses, and stream events;
- adapter exceptions;
- cancellation and timeout before or after an adapter operation;
- input, output, inventory, feature, and streaming-event resource limits.

Generation and streaming failures do not mutate authoritative state or execute side effects. Ordered stream events are validated and materialized into a bounded transcript. Live incremental delivery and real runtime transport are deliberately deferred to the first concrete adapter slice.

## Tests

The IMP-048 tests cover:

- declaration, identifier, version, operation, connection, and offline invariants;
- deterministic declaration fingerprints;
- health and inventory normalization;
- duplicate, malformed, and oversized inventory failures;
- generation success, malformed output, adapter failure, timeout, cancellation, and resource limits;
- ordered stream start, delta, completion, error, cancellation, timeout, malformed-event, event-count, and output-size behavior;
- registry immutability and adapter-identity checks;
- bounded privacy-safe failure results;
- absence of authority-bearing, networking, subprocess, secret-store, and state-repository imports;
- cross-platform CI without a runtime or model.

## Deliberate limitations and next slice

- No real runtime is contacted.
- No model is installed, discovered, selected, or executed.
- No canonical conversation path is implemented.
- Streaming is represented and validated as an ordered bounded transcript; a future concrete adapter may deliver events incrementally while preserving this contract.
- Model manifests, runtime manifests, model bindings, activation, fallback, and rollback remain separate later slices.
- The next bounded Phase 5 slice may implement the first real local runtime adapter, initially targeting Ollama, only through this contract and without silent download or cloud fallback.

## Issue

Closes #152.
