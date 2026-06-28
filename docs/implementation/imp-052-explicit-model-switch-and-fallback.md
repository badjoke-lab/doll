# IMP-052 — Explicit model switching and fallback rollback

## Status

Complete in code with synthetic runtime adapters. No real runtime, real model, user-side offline test, runtime installation, model download, cloud request, credential retrieval, tool execution, or capability execution is part of this implementation.

## Purpose

IMP-052 adds a model-independent `ModelSwitchService` above the accepted runtime adapter, manifest, binding, and canonical state contracts. It allows a caller to inspect valid targets for one exact scope and explicitly switch to one chosen binding. It also exposes explicitly configured fallback candidates without creating autonomous failover.

The model and runtime remain replaceable execution components. They do not own Doll State, select their own replacement, approve a fallback, or acquire authority over conversations, memory, projects, permissions, confirmations, capabilities, backups, or portability.

## Target and fallback discovery

`list_switch_targets` starts from the one active binding for the requested scope and returns only other scope-local bindings in candidate, previous, fallback, or disabled state whose exact runtime and model manifest revisions still validate and whose registered adapter declaration still matches the authoritative local-only runtime manifest.

`list_fallback_candidates` further restricts the result to bindings explicitly marked fallback, eligible, and previously smoke-tested as passed. Candidates are ordered deterministically by ascending user-configured fallback priority and binding ID. Listing a fallback does not activate it. The caller must still provide that exact binding ID to `switch_to_fallback`.

Invalid, stale, archived, quarantined, deprecated, unavailable, cross-scope, active, unregistered, declaration-mismatched, or non-adapter-facing targets are rejected or omitted. Runtime inventory is not consulted and cannot choose a model.

## Explicit switch protocol

A switch request contains one exact scope, one exact target binding ID, and one operation ID. The service:

1. requires a writable repository and validates the current active binding;
2. validates the selected target and exact runtime/model manifests;
3. validates the registered adapter declaration and local-only contract;
4. reserves the operation through a bounded audit event and rejects reuse;
5. runs a bounded pre-activation machine-readability probe;
6. records the target smoke result;
7. activates only a target whose preflight passed;
8. resolves the newly active binding and runs a post-activation probe;
9. returns success only after that verification passes;
10. restores the exact previous binding when post-activation validation fails.

There is no automatic discovery, automatic selection, third-binding substitution, automatic failover, cloud fallback, model download, runtime installation, or process management.

## Smoke-probe boundary

Both probes call only `LocalRuntimeBoundary.generate`. The transient request uses a fixed explicit instruction, a 64-character output ceiling, a 60-second timeout for CPU-only local model loading and generation, and a fresh cancellation token. It contains no user conversation, imported content, memory, project data, procedure, checkpoint, credential, secret, private path, provider body, or host information.

A completed response must be one non-empty uppercase ASCII token ending in `_SWITCH_OK`, with no prose, quotation, punctuation, Markdown, or multiline content. The prefix may vary because real local models can harmlessly normalize an unfamiliar fixed token while still proving bounded machine-readable generation. Timeout, cancellation, resource limit, adapter failure, empty output, explanation text, malformed output, or any response outside that bounded token grammar becomes a normalized failure code.

Probe output is never stored as an artifact, conversation event, instruction-origin record, memory, project record, or audit value. Results expose stable identifiers, a hash of the scope key, normalized outcomes, and normalized failure codes only.

## Preflight failure

A failed preflight marks the selected target smoke status failed, records a bounded completion audit event, and leaves the existing active binding unchanged. No activation transaction is attempted.

## Activation and exact rollback

After a passed preflight, the service uses the existing `activate_binding` transaction. That transaction moves the former active binding to previous state and installs the selected target as the only active binding for the scope.

The service then revalidates the active record, manifests, adapter declaration, and post-activation probe. Any bounded post-activation validation or probe failure invokes the existing `rollback_binding` transaction against the activated target. The exact preserved previous binding is restored as active; the rejected target becomes rolled back and its smoke status becomes failed. Failure to restore the exact prior binding is surfaced as `ModelSwitchRollbackError` rather than silently choosing another binding.

## State, package, backup, and continuity effects

IMP-052 introduces no authoritative record type and no schema migration. It uses existing model-binding state, revisions, audit records, and transaction semantics. Schema version 3 and State Package v2 remain unchanged. Existing package, backup, restore, and fresh-process behavior therefore continue to carry binding state without a new format category.

The implementation rewrites only the selected target, the current/previous binding involved in activation or rollback, state revision metadata, and bounded audit events. It does not mutate unrelated manifests, conversations, artifacts, instruction origins, memory, decisions, projects, work items, procedures, checkpoints, permissions, confirmations, portability records, backups, or capability state.

## Privacy and authority

The returned result does not expose the raw scope key, probe input, probe output, provider detail, exception text, host data, credential, secret, or private path. Binding activation and rollback audit metadata now use a scope-key hash rather than the raw scope key.

The probe is health evidence only. Its output is not a user instruction, policy, confirmation, permission, memory, fact, decision, completion claim, checkpoint, project mutation, capability request, or tool result.

## Validation boundary

Tests use deterministic injected adapters and clocks. They cover target and fallback ordering, explicit successful switching, explicit fallback switching, preflight failure without active-binding change, bounded runtime failure, post-activation probe failure, post-activation adapter-declaration mismatch, exact rollback, unrelated-state preservation, cross-scope and current-target rejection, adapter mismatch before execution, duplicate operation rejection, read-only state, bounded result and audit privacy, accepted fixed and harmless-prefix-variant smoke tokens, rejected empty/explanatory/malformed output, and static absence of cloud, tool, capability, inventory, streaming, and process dependencies.

CI performs no real network request, runtime process launch, runtime installation, model download, cloud request, or credential retrieval. No user-side local/offline action is required for IMP-052.

## Deliberate limitations and next boundary

IMP-052 does not add streaming conversation output, automatic failover, a real Ollama switch, a real model replacement, runtime installation, model download, cloud providers, credentials, tools, capabilities, permission flows, memory publication, or project mutation.

The next bounded work is streaming integration while preserving the non-streaming canonical event and managed-artifact result as authoritative. The network-disabled real-runtime continuity drill remains required before any local-inference release claim.

## Issue

Closes #163.
