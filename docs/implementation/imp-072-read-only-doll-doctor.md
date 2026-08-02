# IMP-072 — Read-only doll doctor diagnostics

**Status:** Implemented with deterministic synthetic CI evidence

## Objective

Add the Lite v1.0-required `doll doctor` path as a deterministic, secret-safe, read-only diagnostic over one explicitly selected local workspace.

## Implemented boundary

The doctor service:

- validates workspace identity without initializing or mutating it;
- checks every required workspace directory for presence, directory type, symlink rejection, and confinement under the workspace root;
- opens the authoritative state repository with `read_only=True`;
- checks read-only status, workspace/database identity, current schema, and workspace/database revision agreement;
- runs SQLite `PRAGMA quick_check` without migration or repair;
- returns ordered immutable `pass`, `warn`, or `fail` checks with bounded summaries and fixed local-only guidance;
- provides stable human-readable and deterministic JSON CLI output;
- excludes native paths, workspace identifiers, database paths, usernames, hostnames, record content, model output, credentials, and secret values.

The command exits successfully only when no blocking check fails. A failed diagnostic exits with code 2 while leaving the selected workspace unchanged.

## Safety and continuity effects

IMP-072 performs no schema migration, workspace write, state write, repair, deletion, backup creation, restore, model execution, runtime start, process launch, shell command, tool, capability, network request, cloud fallback, login, credential access, model download, installation, or binding change.

When the workspace cannot be validated, the diagnostic report contains only a generic fixed failure summary and local recovery guidance. Provider exception text and native paths do not enter the report.

## Evidence

Dedicated acceptance covers:

- a healthy initialized workspace and state repository;
- deterministic content-free JSON output;
- stable human output and exit codes;
- no creation for an invalid workspace path;
- required-directory absence and symlink rejection;
- corrupt SQLite state without repair;
- revision mismatch without metadata rewrite;
- injected quick-check failure;
- workspace-path absence from public results and representations;
- exact file-content and modification-time preservation during a healthy run.

Standard CI covers Ubuntu, macOS, and Windows. This implementation is CI-only and does not broaden prior accepted real-machine evidence.

## Non-claims

IMP-072 does not establish automatic repair, provider-specific troubleshooting, local runtime or model health calls, performance benchmarking, installer diagnostics, accessibility presentation, the seven-day release-candidate soak, complete Phase 6, Lite v1.0 completion, or stable general anti-lock-in.
