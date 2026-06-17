# Security Policy

`doll` is in pre-alpha development. It is not ready for use with valuable, confidential, regulated, or safety-critical data.

The current implementation contains local state, audit, managed artifact, export/import, and verified backup foundations through IMP-010. Restore is next. No model runtime, cloud model, credential broker, or general tool-execution path is currently connected.

## Supported versions

No stable release is currently supported.

Security fixes during pre-alpha are applied to the default development branch and documented in pull requests or release notes when releases begin.

## Reporting a vulnerability

For a vulnerability that could expose private data, escape the workspace, bypass permissions, execute commands, access secrets, corrupt backups, alter trust or evidence records, misclassify instruction authority, or expose a local API:

1. Prefer a private GitHub Security Advisory for this repository when that option is available.
2. Do not post exploit details, private data, credentials, secret values, recovery phrases, or proof-of-concept payloads in a public issue.
3. Include the affected commit or version, operating system, configuration, impact, reproduction steps, and any proposed mitigation.

For non-sensitive hardening suggestions or documentation errors, a normal GitHub issue is acceptable.

## Security architecture

Doll has two co-equal architectural pillars:

- **continuity**, which preserves user-owned state through failure, transfer, backup, restore, and replacement;
- **the safety boundary**, which prevents models, tools, runtimes, and external content from gaining undeclared authority over state, secrets, the operating system, accounts, or external services.

The complete safety boundary must be implemented and acceptance-tested before model execution is introduced. See `docs/decisions/ADR-005-safety-boundary-before-model-execution.md`.

## Security priorities

The project treats the following as high-priority security properties:

- no writes outside the approved workspace;
- no unrestricted shell execution;
- no automatic cloud fallback or silent external upload;
- no mandatory telemetry or remote licensing;
- no secret values in ordinary Doll State, logs, audit events, exports, backups, fixtures, diagnostics, or repository history;
- no direct exposure of stored credentials to a model;
- no direct execution of instructions found in retrieved pages, documents, media, metadata, imports, or tool output;
- explicit separation of confirmed facts, claims, evidence, and inferences;
- recorded instruction origin and authority class;
- recoverable state changes, migrations, backups, and restores;
- localhost-only network binding by default;
- explicit, versioned capability and permission checks;
- risk-tier enforcement and fresh confirmation for high-risk operations;
- model, runtime, UI, tool, and external-content outputs treated as untrusted input.

## Secret handling

Memory and secrets are separate.

Ordinary Doll State may contain a non-secret reference to an externally stored credential, but it must not contain the credential value. Future credential use must pass through a bounded credential broker. The broker may use a credential internally for an approved operation, but the default result returned to a model or caller must be an operation result rather than the secret value.

Secret detection and redaction are defense-in-depth controls. They do not grant permission to search for secrets, and they cannot guarantee detection of every sensitive value.

## Trust and external content

Retrieved or imported content is data, not authority.

Documents, websites, OCR output, transcripts, media metadata, tool results, model output, and imported records cannot:

- grant permission;
- supply user confirmation;
- change policy;
- raise their own authority;
- approve a capability;
- convert a claim into a confirmed fact;
- request secret disclosure outside an accepted capability contract.

Prompt-injection detection is advisory. Security must not depend only on another model recognizing an attack.

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
- model-independent continuity and safety validation before inference.

The initial product is not a hardened multi-user server, public web service, enterprise authorization system, secret-management replacement, or secure sandbox for arbitrary untrusted code.

## Out of scope for initial releases

The initial releases do not provide:

- unrestricted command or code execution;
- autonomous deletion or overwrite;
- autonomous email, posting, purchasing, account changes, or financial transactions;
- public internet exposure;
- protection against an attacker who already controls the user's operating-system account or administrator privileges;
- custom cryptographic algorithms;
- guaranteed safe execution of arbitrary third-party plugins or model code;
- perfect prompt-injection or secret detection;
- a guarantee that confirmation makes every requested action safe.

## Dependency and model safety

Model files, runtimes, optional tools, package dependencies, retrieved content, and external secret-store implementations are supply-chain inputs. Their source, version, checksum, license, and execution requirements must be recorded where applicable.

The project will not treat a model or tool as trusted merely because it is popular, open source, locally installed, or running without network access.

## Security changes

Pull requests that change any of the following must explicitly describe the new threat surface, authority changes, failure behavior, and tests:

- filesystem access;
- process execution;
- network listeners or outbound requests;
- cloud integration;
- authentication, secret references, credential storage, or credential use;
- model or plugin loading;
- backup, restore, export, import, or migration;
- permission prompts, risk tiers, confirmation, or approval persistence;
- claim, evidence, inference, provenance, or instruction-origin records;
- prompt or context assembly;
- audit logging and redaction;
- mobile or remote access.

No pull request may introduce a model execution path before the safety acceptance gate defined by the accepted roadmap and test specification has passed.
