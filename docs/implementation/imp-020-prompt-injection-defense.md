# IMP-020 — Prompt Injection Defense

## Status

Implementation in progress.

## Scope

IMP-020 adds a model-independent prompt-injection defense layer above IMP-019 instruction-origin records.

The implementation will provide:

- bounded advisory detection with no matched text retained in findings;
- secret-safe, complete-or-fail context packaging;
- structural separation of authority channels and data-only channels;
- external instruction-authority checks that cannot be overridden by model output or classifier labels;
- hostile source, exfiltration, capability-request, malformed, archived, stale-policy, secret-bearing, and resource-limit fixtures.

It does not add a live model, prompt transmission, tool execution, capability registry, high-risk confirmation, network path, dependency, schema migration, or custom cryptography.
