# IMP-049 — First local Ollama runtime adapter

## Status

Implemented, hardened, and validated against the IMP-048 runtime contract. This slice adds a concrete adapter but does not claim that Ollama or a model is installed or usable on the project owner's machine.

## API surface

`src/doll/ollama_adapter.py` uses only:

- `GET /api/version` for local health;
- `GET /api/tags` for local inventory;
- `POST /api/generate` with `stream: false` for generation;
- `POST /api/generate` with `stream: true` for NDJSON streaming.

No model-management or hosted-service endpoint is exposed. Method and path combinations are validated as an exact allowlist.

## Local-only boundary

The production endpoint fixes the host to IPv4 loopback `127.0.0.1`. Only a validated port is configurable, with `11434` as the default. The transport uses a direct Python HTTP connection and provides no arbitrary URL, remote-host, redirect-following, proxy, or process-launch path.

The adapter is fail-closed until `local_only_confirmed` is explicitly enabled. This is an operator assertion, not proof obtained from the Ollama API. A later real-machine drill must independently verify the local-only server configuration.

## Model handling

Models with a terminal `cloud` tag are excluded. Generation is allowed only for a model found in the current filtered inventory.

Native model names are mapped to deterministic opaque identifiers:

```text
ollama.model.<sha256-of-native-name>
```

The native name remains a non-authoritative display value. Neither identity becomes an authoritative Doll State record in this slice.

## Safety and authority

The adapter receives no Doll state, permission, capability, project-mutation, or durable-memory authority. Prompt and generated text remain transient, untrusted content. Model output cannot approve procedures, confirm checkpoints, clear blockers, complete work, grant permissions, or execute side effects.

Later conversation and tool paths must continue through the Phase 3 safety boundary and the Phase 4A/4B canonical state contracts.

## State effects

IMP-049 adds no database migration, package member, backup member, portability record, project-continuity record, runtime manifest, or persistent model binding. The adapter can be removed without rewriting existing Doll State.

## Failure and resource behavior

The adapter returns bounded failures for unavailable runtime, unconfirmed local-only mode, missing model, malformed data, duplicate JSON keys, invalid constants, model mismatch, request and response limits, stream limits, cancellation, deadline expiry, and transport failure. HTTP 404 during generation or streaming is normalized as `model_not_found`.

Provider response bodies and transport exception details are not propagated through normalized results. Failed operations do not mutate authoritative state.

## Tests

Tests use an injected fake transport and perform no network request or process launch. They cover health, inventory normalization, opaque IDs, cloud-model exclusion, generation, ordered streaming, malformed responses, cancellation, timeout, resource limits, method and path restrictions, loopback restrictions, use through `LocalRuntimeBoundary`, and absence of authority-bearing dependencies.

Final cross-platform evidence at PR head `6302defe4d876ea84a8787253025de91d53f67aa`:

- Linux: 1028 passed, 95.33% coverage;
- macOS: 1028 passed, 95.33% coverage;
- Windows: 1027 passed, 1 skipped, 95.30% coverage;
- dependency lock, lint, formatting, strict typing, generated specification, implementation numbering, and public status checks passed.

## Real-machine evidence gap

This slice does not establish that:

- Ollama is installed or running on the primary Intel Mac;
- a specific model is installed;
- real inference, streaming, cancellation, latency, or memory behavior has passed;
- network-disabled operation has passed with a real runtime.

Those claims remain deferred to a separately scheduled Phase 5 real-machine drill.

## Next slice

The next bounded Phase 5 slice is the model-manifest and explicit-binding foundation, receiving IMP-050 when opened.

## Issue

Closes #154.
