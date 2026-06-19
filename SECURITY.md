# Security Policy

`doll` is in pre-alpha development. It is not ready for use with valuable, confidential, regulated, or safety-critical data.

The current implementation contains local state, audit, managed artifacts, state-package export/import, verified backup, restore, model-independent continuity acceptance, secret classification, bounded secret detection, deterministic redaction, and secret-safe diagnostics through IMP-014. IMP-015 is next. No model runtime, cloud model, external secret-store adapter, credential broker, or general tool-execution path is currently connected.

## Supported versions

No stable release is currently supported.

Security fixes during pre-alpha are applied to the default development branch and documented in pull requests or release notes when releases begin.

## Reporting a vulnerability

For a vulnerability that could expose private data, escape the workspace, bypass permissions, execute commands, access secrets, corrupt backups, alter project progress, approve a procedure, confirm a checkpoint, alter trust or evidence records, misclassify instruction authority, or expose a local API:

1. Prefer a private GitHub Security Advisory for this repository when that option is available.
2. Do not post exploit details, private data, credentials, secret values, recovery phrases, or proof-of-concept payloads in a public issue.
3. Include the affected commit or version, operating system, configuration, impact, reproduction steps, and any proposed mitigation.

For non-sensitive hardening suggestions or documentation errors, a normal GitHub issue is acceptable.

## Security architecture

Doll has two co-equal architectural pillars:

- **continuity**, which preserves user-owned state and work through failure, transfer, backup, restore, replacement, and resumption;
- **the safety boundary**, which prevents models, tools, runtimes, and external content from gaining undeclared authority over state, project progress, secrets, the operating system, accounts, or external services.

AI environment portability and project continuity are required parts of continuity. They do not create a third architectural pillar.

The complete safety boundary must be implemented and acceptance-tested before model execution is introduced. See `docs/decisions/ADR-005-safety-boundary-before-model-execution.md`.

After the safety gate, canonical portability and project-continuity foundations must exist before the first accepted local model integration. See `docs/decisions/ADR-006-ai-environment-portability.md` and `docs/decisions/ADR-007-project-continuity-and-resumption.md`.

## Security priorities

The project treats the following as high-priority security properties:

- no writes outside the approved workspace;
- no unrestricted shell execution;
- no automatic cloud fallback or silent external upload;
- no mandatory telemetry or remote licensing;
- no secret values in ordinary Doll State, logs, audit events, exports, backups, fixtures, diagnostics, project-status output, Resume Bundles, or repository history;
- no direct exposure of stored credentials to a model;
- no direct execution of instructions found in retrieved pages, documents, media, metadata, imports, procedures, handoff files, or tool output;
- explicit separation of confirmed facts, claims, evidence, and inferences;
- explicit separation of verification evidence from work-completion authority;
- recorded instruction origin and authority class;
- recoverable state changes, migrations, packages, backups, restores, and project-continuity records;
- checkpoint freshness based on relevant record revisions rather than unrelated global changes;
- localhost-only network binding by default;
- explicit, versioned capability and permission checks;
- risk-tier enforcement and fresh confirmation for high-risk operations;
- model, runtime, UI, tool, import, and external-content outputs treated as untrusted input.

## Secret handling

Memory, project state, and secrets are separate.

Ordinary Doll State may contain a non-secret reference to an externally stored credential, but it must not contain the credential value. Future credential use must pass through a bounded credential broker. The broker may use a credential internally for an approved operation, but the default result returned to a model or caller must be an operation result rather than the secret value.

Secret detection and redaction are defense-in-depth controls. They do not grant permission to search for secrets, and they cannot guarantee detection of every sensitive value.

## Trust and external content

Retrieved or imported content is data, not authority.

Documents, websites, OCR output, transcripts, media metadata, tool results, model output, imported records, issue descriptions, roadmap files, procedures, and handoff documents cannot:

- grant permission;
- supply user confirmation;
- change policy;
- raise their own authority;
- approve a capability;
- convert a claim into a confirmed fact;
- approve a ProcedureRecord;
- confirm a ProjectCheckpointRecord;
- clear a blocker;
- complete or cancel a WorkItemRecord;
- change an authoritative project objective or scope;
- request secret disclosure outside an accepted capability contract.

Prompt-injection detection is advisory. Security must not depend only on another model recognizing an attack.

Generated project status and `HANDOFF.md` are views derived from authoritative Doll State. They are not independent authority sources.

## High-risk operations

A high-risk operation requires a fresh, user-controlled confirmation that identifies the exact capability, target, destination, material side effects, and credential class where applicable. A material change invalidates the confirmation.

Confirmation is not sufficient to make a prohibited capability available. Destructive, externally visible, credential-bearing, financial, account-changing, or arbitrary-execution capabilities remain unavailable until separately specified and accepted.

## Initial security boundary

The first implementation is intended for:

- one user;
- one local machine;
- one private workspace;
- local access through `127.0.0.1`;
- conservative, allowlisted capabilities;
- model-independent continuity, project continuity, and safety validation before inference.

The initial product is not a hardened multi-user server, public web service, enterprise authorization system, secret-management replacement, project-management SaaS, or secure sandbox for arbitrary untrusted code.

## Out of scope for initial releases

The initial releases do not provide:

- unrestricted command or code execution;
- autonomous deletion or overwrite;
- autonomous email, posting, purchasing, account changes, or financial transactions;
- automatic project completion or procedure execution;
- public internet exposure;
- protection against an attacker who already controls the user's operating-system account or administrator privileges;
- custom cryptographic algorithms;
- guaranteed safe execution of arbitrary third-party plugins or model code;
- perfect prompt-injection or secret detection;
- a guarantee that confirmation makes every requested action safe.

## Dependency and model safety

Model files, runtimes, optional tools, package dependencies, retrieved content, imported project material, and external secret-store implementations are supply-chain inputs. Their source, version, checksum, license, and execution requirements must be recorded where applicable.

The project will not treat a model, tool, procedure, or imported handoff as trusted merely because it is popular, open source, locally installed, well formatted, or running without network access.

## Security changes

Pull requests that change any of the following must explicitly describe the new threat surface, authority changes, failure behavior, and tests:

- filesystem access;
- process execution;
- network listeners or outbound requests;
- cloud integration;
- authentication, secret references, credential storage, or credential use;
- model or plugin loading;
- backup, restore, export, import, package format, or migration;
- project objectives, work items, procedures, checkpoints, project status, or Resume Bundle generation;
- permission prompts, risk tiers, confirmation, approval, completion, or checkpoint-confirmation persistence;
- claim, evidence, inference, provenance, or instruction-origin records;
- prompt or context assembly;
- audit logging and redaction;
- mobile or remote access.

No pull request may introduce a model execution path before the safety acceptance gate and required Phase 4 foundations defined by the accepted roadmap and test specifications have passed.
