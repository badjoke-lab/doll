# IMP-054 — Network-disabled real-runtime continuity drill

## Status

Accepted. The primary Intel Mac offline gate passed on exact merged `main` commit `1a5b66b2417d6f3e1eafcd14d2769e9c15d7f96c` on 2026-06-28.

Accepted evidence:

- `docs/testing/results/IMP-054-primary-intel-mac-2026-06-28.json`

The stored JSON is preserved from the accepted run. Its `limitations` array contains the pre-storage gate wording emitted by that commit; the updated matrix is the authoritative post-acceptance state.

Phase 5 is complete for the local-runtime and model-integration boundary covered by LRUN-001 through LRUN-012.

## Verified boundary

The accepted drill verified:

- fixed IPv4 loopback Ollama health and exact local inventory;
- two distinct preinstalled local model revisions;
- canonical non-streaming and bounded streaming conversation;
- explicit switching to a configured fallback;
- forced post-activation failure and rollback to the exact previous binding;
- preservation of unrelated memory and project revisions;
- canonical conversation and runtime-output state;
- State Package v2 transfer of conversation, runtime, model, and binding records;
- state-backup restoration;
- fresh-process inspection of source, imported, and restored state without runtime adapters;
- rejection of non-loopback socket destinations and undeclared Ollama API paths;
- transient, non-authoritative switch-probe output;
- bounded evidence without private machine or model details.

The runtime output remains data-only. It cannot create policy, grant permission, confirm a checkpoint, complete project work, invoke a capability, or execute a tool.

## Accepted environment

- implementation commit: `1a5b66b2417d6f3e1eafcd14d2769e9c15d7f96c`;
- operating system: `Darwin`;
- architecture: `x86_64`;
- Python: `3.12.13`;
- runtime adapter: `ollama.local` version `1.0.0`;
- local runtime version: `0.30.11`;
- network mode: `offline-confirmed`;
- evidence level: `real-machine`;
- completed at: `2026-06-28T15:23:40.505485Z`.

Result:

```text
result = pass
primary_intel_mac_gate = pass
phase5_gate_complete = true
```

All declared checks passed. The accepted report records zero rejected socket attempts, four completed canonical turns, twelve canonical conversation events, State Package v2 transfer, backup restore, three fresh-process inspections, explicit fallback switching, and exact forced rollback.

The stored result contains no native model names, prompt or response text, absolute paths, usernames, hostnames, or private fixture content.

## CI validation

```bash
python scripts/run_imp_054_runtime_continuity.py \
  --commit-sha "$(git rev-parse HEAD)" \
  --evidence-level ci
```

CI validates the stored result against the matrix commit, platform, architecture, completion time, offline mode, passing checks, evidence shape, and privacy flags while continuing to run the deterministic synthetic runtime drill.

## State and compatibility effects

IMP-054 adds no authoritative record type and no migration. Schema version 3 and State Package format version 2 remain unchanged.

No user-owned state is rewritten merely because a different model is selected. Conversation and audit additions are append-oriented, and memory, project, portability, package, backup, and recovery state remain model-independent.

## Deliberate limitations

- The accepted evidence covers the primary Intel Mac and the exact runtime and model revisions represented in the stored result.
- Other runtimes, model families, operating systems, architectures, hardware profiles, and revisions require separate compatibility evidence.
- The drill does not install or start the runtime and does not download, delete, or modify models.
- The drill does not prove cloud portability, tool execution, autonomous project mutation, or private-workspace migration.
- Local runtime output cannot bypass the Phase 3 safety boundary or Phase 4A/4B canonical state contracts.

## Issue

Completion of #169.
