# Security Policy

`doll` is in pre-alpha specification development. It is not ready for use with valuable, confidential, regulated, or safety-critical data.

## Supported versions

No stable release is currently supported.

Security fixes during pre-alpha are applied to the default development branch and documented in pull requests or release notes when releases begin.

## Reporting a vulnerability

For a vulnerability that could expose private data, escape the workspace, bypass permissions, execute commands, access secrets, corrupt backups, or expose a local API:

1. Prefer a private GitHub Security Advisory for this repository when that option is available.
2. Do not post exploit details, private data, credentials, or proof-of-concept payloads in a public issue.
3. Include the affected commit or version, operating system, configuration, impact, reproduction steps, and any proposed mitigation.

For non-sensitive hardening suggestions or documentation errors, a normal GitHub issue is acceptable.

## Security priorities

The project treats the following as high-priority security properties:

- no writes outside the approved workspace;
- no unrestricted shell execution;
- no automatic cloud fallback or silent external upload;
- no mandatory telemetry or remote licensing;
- no secrets in logs, exports, fixtures, or repository history;
- no direct execution of instructions found in retrieved web pages or documents;
- recoverable state changes, migrations, backups, and restores;
- localhost-only network binding by default;
- explicit, versioned capability and permission checks;
- model, runtime, UI, and tool outputs treated as untrusted input.

## Initial security boundary

The first implementation is intended for:

- one user;
- one local machine;
- one private workspace;
- local access through `127.0.0.1`;
- conservative, allowlisted capabilities.

The initial product is not a hardened multi-user server, public web service, enterprise authorization system, or secure sandbox for arbitrary untrusted code.

## Out of scope for initial releases

The initial releases do not provide:

- unrestricted command or code execution;
- autonomous deletion or overwrite;
- autonomous email, posting, purchasing, or financial transactions;
- public internet exposure;
- protection against an attacker who already controls the user's operating-system account or administrator privileges;
- custom cryptographic algorithms;
- guaranteed safe execution of arbitrary third-party plugins or model code.

## Dependency and model safety

Model files, runtimes, optional tools, and package dependencies are supply-chain inputs. Their source, version, checksum, license, and execution requirements must be recorded where applicable.

The project will not treat a model or tool as trusted merely because it is popular or locally installed.

## Security changes

Pull requests that change any of the following must explicitly describe the new threat surface and tests:

- filesystem access;
- process execution;
- network listeners or outbound requests;
- cloud integration;
- authentication or credential storage;
- model or plugin loading;
- backup, restore, export, import, or migration;
- permission prompts or approval persistence;
- audit logging;
- mobile or remote access.
