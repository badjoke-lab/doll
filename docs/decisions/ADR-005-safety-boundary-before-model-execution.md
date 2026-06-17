# ADR-005: Complete the safety boundary before model execution

**Status:** Accepted when merged  
**Date:** 2026-06-17

## Context

Doll is a personal AI continuity system whose durable core is user-owned state rather than any one model or provider. The project already accepts default-deny permissions, workspace confinement, untrusted model output, untrusted external content, prompt-injection resistance, secret-safe logging, and a mandatory Capability Broker.

The original implementation roadmap nevertheless placed the first local model adapter and local conversation path before the complete safety boundary. That order would allow model execution before the contracts governing secrets, credentials, trust, instruction origin, capability risk, and mandatory confirmation were implemented and acceptance-tested.

Local execution does not make a model trustworthy. A local model may hallucinate, be compromised, follow hostile content, request excessive authority, expose sensitive context, or produce malformed tool requests. The same safety boundary must govern local and cloud models.

## Decision

Doll will complete and acceptance-test its safety boundary before introducing any model execution path.

The implementation order is:

1. establish local authoritative state;
2. prove export, backup, restore, and post-restore continuity without a model;
3. implement the safety boundary as a model-independent subsystem;
4. pass the safety acceptance gate;
5. only then connect a local model runtime;
6. add cloud and multiple-model paths only after the local path remains complete and safe.

Continuity and the safety boundary are co-equal architectural pillars:

- continuity preserves user-owned state across failure and replacement;
- the safety boundary prevents models, tools, runtimes, and external content from gaining undeclared authority over that state, the operating system, secrets, accounts, or external services.

## Required safety-boundary components

Before model execution is permitted, doll must have accepted contracts and tested implementation for:

- secret classification;
- secret detection and redaction;
- secret-safe audit and logging;
- an external secret-store contract;
- a credential broker that returns bounded results rather than exposing stored secret values;
- separation of confirmed facts, claims, evidence, and inferences;
- instruction-origin metadata and authority ordering;
- an untrusted-content boundary in which imported and retrieved content is data, not instruction;
- prompt-injection defenses that do not rely only on another model's classification;
- a versioned capability taxonomy and risk tiers;
- mandatory fresh confirmation for high-risk operations;
- a safety acceptance test that proves denial paths as well as allowed paths.

## Secret rule

Ordinary Doll State must not store secret values.

It may store a non-secret reference containing only the minimum metadata needed to request a credential through an external secret store. Secret values must not appear in normal records, audit events, logs, exports, backups, fixtures, generated diagnostics, or model context.

A later feature that needs a credential must request a narrowly scoped operation through the credential broker. The broker may use a secret internally, but the default result returned to the caller must be a bounded operation result, not the secret value itself.

## Trust and instruction rule

Doll must distinguish at least:

- confirmed fact: user-confirmed durable information;
- claim: an assertion that may be true or false;
- evidence: a source or observation supporting or contradicting a claim;
- inference: a derived conclusion with provenance and uncertainty.

No claim becomes a confirmed fact merely because a model, tool, document, website, or import states it confidently.

Every instruction-bearing input must retain its origin and authority class. Retrieved pages, documents, OCR output, media transcripts, tool results, and imported data are untrusted content. They may provide evidence or task data but cannot grant permission, change policy, approve an operation, or override higher-authority instructions.

## Capability and confirmation rule

Every side-effecting operation must use a versioned capability with a declared risk tier. Unknown capabilities fail closed.

High-risk operations require a fresh, user-controlled confirmation that identifies the exact capability, target, destination, material side effects, and credential class where applicable. High-risk confirmation cannot be supplied by model text, external content, a tool result, or a previously stored broad permission. Material changes invalidate the confirmation.

Some high-risk capabilities may remain unavailable even when confirmation exists. Confirmation is necessary where specified; it is not sufficient to bypass policy or release scope.

## Consequences

### Positive

- Model integration cannot silently become the security architecture.
- Local and cloud models share one authority boundary.
- Secrets and durable memory remain structurally separate.
- Prompt injection cannot directly grant authority.
- Claims and evidence remain inspectable outside one model's answer.
- High-risk actions remain attributable, bounded, and reviewable.
- The first continuity proof remains independent of model availability.

### Negative

- The first local conversation milestone moves later.
- More model-independent infrastructure must be implemented before visible AI behavior appears.
- Secret-store behavior differs across operating systems and requires a strict portability contract.
- Permission and confirmation flows add user friction.
- Trust and provenance records add schema and testing work.

These costs are accepted because adding model execution first would create an unsafe dependency that later refactoring might preserve accidentally.

## Rejected alternatives

### Connect a local model first and add controls later

Rejected because local models are untrusted inputs and early direct integration would establish unsafe interfaces before the authority boundary exists.

### Treat local models as more trusted than cloud models

Rejected because location does not establish correctness, integrity, provenance, or resistance to hostile content.

### Store credentials in ordinary Doll State with encryption added later

Rejected because it mixes memory portability with secret custody, increases backup and export exposure, and makes every state reader part of the secret-handling boundary.

### Rely on system prompts for instruction hierarchy

Rejected because prompts are not an authorization mechanism and may be ignored, confused, or overridden by hostile context.

### Use one broad confirmation for arbitrary commands

Rejected because arbitrary commands cannot be reliably summarized into a stable, bounded side-effect contract.

## Compatibility and migration

This decision changes implementation order but does not invalidate IMP-001 through IMP-010. Those implementations contain no model execution path and remain the Phase 1 and Phase 2 foundation.

IMP-011 remains the next code implementation after this documentation change. IMP-012 becomes the model-independent Continuity Acceptance Test. IMP-013 through IMP-023 implement and validate the safety boundary. Local model work begins at IMP-024 or later.

No state migration is introduced by this ADR. Future secret-reference, trust, evidence, instruction-origin, capability, and confirmation schemas require their own implementation issues and migrations.

## Validation

This decision is validated when:

1. the roadmap places the safety acceptance gate before every model adapter and model execution path;
2. ordinary Doll State contains secret references rather than secret values;
3. audit, logs, exports, backups, fixtures, and diagnostics are tested for secret exclusion or redaction;
4. the credential broker can perform a bounded operation without returning the stored secret to a model;
5. claims, evidence, inferences, and confirmed facts remain distinct through persistence and export;
6. untrusted content cannot grant permission or change instruction authority;
7. risk-tier enforcement denies unknown or under-confirmed capabilities;
8. high-risk confirmation is fresh, exact, user-controlled, and invalidated by material changes;
9. the safety acceptance suite passes before the first model execution PR is merged.
