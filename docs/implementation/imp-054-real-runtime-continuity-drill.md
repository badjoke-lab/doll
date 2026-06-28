# IMP-054 — Network-disabled real-runtime continuity drill

## Status

Automated acceptance harness and canonical-conversation State Package v2 support are implemented. The primary Intel Mac real-machine gate remains pending, so Phase 5 is not complete and no local-inference release claim is made.

This implementation may merge while the gate is pending. Issue #169 remains open until a separate completion PR stores and validates the accepted result from the exact merged `main` commit.

## Purpose

IMP-054 integrates the Phase 5 runtime, manifest, canonical conversation, streaming, switching, rollback, package, backup, and recovery boundaries into one repeatable drill.

The drill proves the orchestration in CI with an injected deterministic Ollama transport. It also defines the bounded command that will later run the same orchestration against a real preinstalled Ollama runtime and two preinstalled local models on the primary Intel Mac with networking disabled.

## Accepted scenario

The drill creates a disposable synthetic Doll workspace and performs the following sequence:

1. confirm the concrete `ollama.local` adapter is ready;
2. inventory two exact local models with fixed revisions;
3. create and verify one runtime manifest and two model manifests;
4. create one active primary binding and one explicitly configured fallback binding;
5. execute one canonical non-streaming turn through the primary model;
6. execute one canonical bounded streaming turn through the primary model;
7. switch explicitly to the chosen fallback through bounded preflight and post-activation probes;
8. execute one canonical turn through the fallback;
9. attempt an explicit switch back to the primary while forcing only the post-activation verification to fail;
10. verify exact rollback to the previous fallback binding;
11. execute one more canonical turn after rollback;
12. export Doll State Package v2, import it, create a state backup, restore it, remove runtime adapter objects, and inspect the source, imported, and restored workspaces in fresh processes with model adapters disabled.

The scenario also creates synthetic confirmed memory, project-continuity records, State Package v2 portability state, one canonical conversation, and managed conversation artifacts. Their identifiers and revisions are checked before and after switching and rollback.

## CI boundary

CI uses `DeterministicOllamaTransport`, which implements the accepted transport protocol entirely in memory. It returns:

- one bounded version response;
- exactly two local inventory entries with deterministic digests;
- one accepted uppercase `_SWITCH_OK` machine token for each smoke probe;
- bounded non-streaming and streaming conversation output.

No CI socket connection, runtime process, installed Ollama instance, model file, model download, cloud provider, credential, or external service is used.

The CI path is orchestration evidence only. It is not real-runtime evidence.

## Real-runtime boundary

Real-machine mode constructs the accepted `LoopbackOllamaTransport` with an explicit port and `local_only_confirmed=True`. The runner accepts no host argument. The transport can represent only fixed IPv4 loopback.

A process-local socket guard rejects every destination except `127.0.0.1` on the selected Ollama port. A second transport wrapper rejects every API path except:

- `/api/version`;
- `/api/tags`;
- `/api/generate`.

The user must disable networking outside the runner before invoking real-machine mode. The runner requires both `--offline-confirmed` and `--local-only-confirmed`, the exact checked-out commit, Darwin on x86_64 or amd64, and two distinct explicit names of already installed local Ollama models.

The runner does not install or start Ollama. It does not pull, delete, modify, or select models automatically. Each selected model must complete the fixed bounded probe and return one non-empty uppercase ASCII token ending in `_SWITCH_OK`. A harmless uppercase prefix variation is accepted because real models can normalize an unfamiliar fixed token; empty output, prose, punctuation, Markdown, malformed output, timeout, or runtime failure is rejected. The probe allows 60 seconds for CPU-only model loading and generation.

## Canonical state and authority

Non-streaming and streaming output use the accepted IMP-051 and IMP-053 canonical paths. Partial streaming deltas remain transient. Only terminally validated output becomes one assistant artifact and event.

Runtime output remains an immutable data-only instruction origin with untrusted authority. It cannot create or update memory, approve a procedure, confirm a checkpoint, complete project work, grant permission, retrieve a credential, invoke a capability, or execute a tool.

The forced rollback failure is injected outside the model after one genuine target preflight. It exists only to prove the existing IMP-052 exact rollback path. Probe output is not stored as a conversation, artifact, instruction-origin record, memory, project record, or capability request.

## Transfer and recovery

State Package v2 now registers the already-existing canonical `conversation` and `conversation_event` record types as optional package categories. Package verification validates that every event belongs to a packaged conversation, every parent exists in the same conversation, and the parent graph is acyclic. Package v1 is unchanged, and earlier v2 packages that omit both optional members remain readable.

The drill exports State Package v2 and verifies that it contains the expected canonical conversation and events, runtime manifest, two model manifests, and two model bindings. It imports that package into an empty target.

It also creates and restores a state backup. A separate process inspects the source, package-imported, and backup-restored workspaces with no runtime adapter constructed. That process verifies:

- schema version 3;
- preserved memory and project revisions;
- current project checkpoint state;
- twelve canonical conversation events representing four completed turns;
- data-only runtime-output origins;
- one preserved runtime manifest and two preserved model manifests;
- the fallback binding active after rollback;
- the rejected primary binding marked rolled back to that fallback;
- absence of persisted switch-probe output;
- matching bounded record counts across source, package import, and backup restore.

Runtime-private HTTP objects and stream iterators are not required for inspection or recovery.

## Evidence and privacy

The acceptance runner emits one bounded JSON object. Successful output contains only:

- exact commit and evidence level;
- operating-system, architecture, and Python version identifiers;
- normalized check names and booleans;
- adapter and runtime versions;
- counts;
- hashes of model revisions and the final active binding identifier;
- gate state and documented limitations.

It does not include native model names, prompts, model responses, conversation text, stream deltas, local paths, usernames, hostnames, credentials, secret values, or private fixture content. Failure output contains only the test ID, requested commit, completion time, stage, and exception class.

## Automated command

```bash
python scripts/run_imp_054_runtime_continuity.py \
  --commit-sha "$(git rev-parse HEAD)" \
  --evidence-level ci
```

Expected gate state before accepted primary-machine evidence:

```text
result = pass
primary_intel_mac_gate = pending
phase5_gate_complete = false
```

## Primary Intel Mac command

Run only from the exact merged `main` commit after networking has been disabled, Ollama is already running locally, and two suitable local models are already installed:

```bash
python scripts/run_imp_054_runtime_continuity.py \
  --commit-sha "$(git rev-parse HEAD)" \
  --evidence-level real-machine \
  --offline-confirmed \
  --local-only-confirmed \
  --primary-model "<installed-model-name>" \
  --fallback-model "<different-installed-model-name>"
```

Review the one-line JSON before storing it. Do not commit terminal history, native model names, prompts, responses, absolute paths, usernames, hostnames, private project text, fixture archives, or machine-specific diagnostics.

## Completion step

A separate completion PR must:

1. store the reviewed result under `docs/testing/results/`;
2. change the matrix real-machine gate from `pending` to `pass`;
3. bind the result to the exact merged implementation commit, Darwin architecture, completion time, and `offline-confirmed` mode;
4. set `phase5_gate_complete` to `true` only if every declared check passed;
5. update the roadmap, generated specification, and public project status;
6. rerun CI and validate the stored evidence;
7. close #169 only after those checks pass.

## State and compatibility effects

IMP-054 introduces no new authoritative Doll State record type and no migration. It registers two already-existing canonical record types as optional State Package v2 members. Schema version 3 and State Package format version 2 remain unchanged.

No user-owned state is rewritten merely because a different model is selected. Expected conversation and audit additions are append-oriented. Memory, project, portability, package, backup, and recovery state remain model-independent.

## Files

- `docs/testing/phase-5-local-runtime-continuity-matrix.json`
- `scripts/imp_054_runtime_probe.py`
- `scripts/imp_054_state_inspector.py`
- `scripts/run_imp_054_runtime_continuity.py`
- `src/doll/state_package.py`
- `src/doll/state_package_registry.py`
- `tests/test_runtime_continuity_acceptance.py`
- `tests/test_runtime_continuity_acceptance_static.py`
- `tests/test_state_package_conversation.py`
- `tests/test_state_package_registry.py`
- `tests/test_state_package_v2.py`

## Issue

Refs #169.
