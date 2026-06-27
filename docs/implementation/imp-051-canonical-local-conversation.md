# IMP-051 — Canonical local conversation execution

## Status

Implementation in progress.

IMP-051 connects one explicitly active local runtime/model binding to the provider-independent conversation contracts through the accepted local runtime and Phase 3 safety boundaries.

The slice is limited to one non-streaming turn. It does not introduce automatic model selection, automatic fallback, tools, capabilities, cloud providers, runtime installation, model download, or a real-machine inference claim.

## Required turn boundary

A valid turn must:

1. resolve one explicit active binding by scope;
2. revalidate exact runtime and model manifest identities and revisions;
3. match the registered adapter declaration to the authoritative runtime manifest;
4. create and authorize the current user instruction outside the model;
5. package additional context through prompt-injection and secret controls;
6. render one bounded deterministic transient runtime input;
7. call only `LocalRuntimeBoundary.generate`;
8. persist canonical user, context-snapshot, and assistant or error events with managed content references;
9. classify runtime output as data-only and non-authoritative;
10. leave no authoritative assistant event after failed, malformed, cancelled, timed-out, or oversized output.

## State expectation

The existing schema version 3, managed artifacts, instruction-origin records, conversations, conversation events, audit history, backup/restore, and State Package v2 should be sufficient. A new migration or package version is not expected unless implementation evidence proves otherwise.

## Issue

Closes #158.
