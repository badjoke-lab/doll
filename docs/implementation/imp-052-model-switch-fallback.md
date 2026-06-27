# IMP-052 — Explicit model switching and local fallback execution

## Status

Implementation in progress.

IMP-052 adds explicit user-controlled candidate switching after a bounded local smoke test, deterministic previous-binding retention and rollback, and one opt-in local fallback attempt for canonical conversation turns.

The implementation must preserve exact manifest and adapter validation, optimistic revisions, canonical artifacts and events, non-authoritative model output, bounded failures, and scope-local rollback.

No cloud fallback, automatic model download, runtime installation, streaming, tool execution, permission mutation, automatic memory, project mutation, or real-machine inference claim is included.

## Issue

Closes #161.
