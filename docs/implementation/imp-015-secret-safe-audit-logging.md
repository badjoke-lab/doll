# IMP-015 — Secret-Safe Audit and Logging

## Status

Phase 3 implementation following IMP-014.

## Purpose

IMP-015 makes secret-safe handling a property of the audit and logging sinks rather than a convention that every caller must remember.

The implementation reuses the bounded IMP-014 detector and adds structured field classification, audit-specific validation, private-environment minimization, and a standard-library logging handler that sanitizes before writing to its stream.

It does not claim perfect secret or personal-data detection.

## Audit boundary

`AuditService.append` sanitizes or rejects every caller-supplied field before starting the database transaction.

Field behavior is deliberately different by semantic role:

- stable tokens and identifiers are rejected when sanitization would alter them;
- summaries are whitespace-normalized and deterministically redacted so useful non-secret context can remain;
- exception values are not stored, only a bounded class name;
- metadata keys must be non-empty strings;
- secret-like metadata keys are rejected;
- private-environment metadata keys such as usernames, hostnames, home directories, working directories, and environment-variable collections are rejected;
- string values under otherwise allowed metadata keys are redacted before JSON serialization;
- binary values, unknown objects, sets, tuples, non-finite numbers, cycles, excessive depth, excessive item count, and excessive encoded size are rejected.

Audit metadata limits are:

- recursion depth: 6;
- aggregate items: 256;
- per-string scan bound: 4,096 characters;
- encoded metadata: 8,192 UTF-8 bytes.

An over-scan metadata string is replaced by the IMP-014 fail-safe marker rather than returning an unscanned suffix.

No audit schema migration is required. Existing columns and append-only triggers remain unchanged.

## Read-time validation

Stored audit rows are not silently repaired or normalized.

On read, the same sanitizer is run in validation mode. If a stored summary or metadata value would change, the row is treated as corrupt. This prevents a legacy, tampered, or directly inserted unsafe value from being returned as though it had passed the current write boundary.

## Structured diagnostic strengthening

Structured diagnostics now additionally:

- redact values selected by secret-like field names even when the value itself has no detectable prefix;
- redact values selected by private-environment field names;
- avoid `str()` for unknown mapping keys;
- represent unknown mapping keys only by type name;
- detect cycles;
- omit non-finite numbers;
- preserve deterministic collision handling for redacted keys.

These changes close the split-label case where a mapping such as `{ "password": "value" }` could otherwise evade a detector that scans keys and values independently.

## Logging boundary

`SecretSafeLogHandler` writes one bounded JSON object per line.

It deliberately does not call `LogRecord.getMessage()` because normal interpolation may invoke attacker-controlled or secret-bearing `__str__` or `__repr__` methods.

The handler records only:

- UTC timestamp;
- level;
- logger name;
- sanitized message template or a safe object-type marker;
- sanitized format arguments as structured data;
- optional sanitized structured context;
- allowlisted correlation fields (`operation_id`, `event_id`, and `action`);
- exception class and redacted exception message;
- a marker indicating omitted stack information.

It does not persist:

- traceback text;
- source pathname;
- filename or module path;
- process or thread identifiers;
- preformatted `exc_text`;
- raw stack text;
- unknown-object representations;
- unbounded context.

The final JSON line is limited to 16,384 UTF-8 bytes. If the sanitized payload still exceeds that bound, the handler returns only a reduced event containing `[LOG_RECORD_SIZE_LIMIT]`.

If rendering itself fails, the handler writes a static `[LOG_RECORD_OMITTED]` event and does not invoke `logging.handleError`, whose default diagnostics could expose the original record.

`configure_secret_safe_logger` removes existing handlers from the named doll-owned logger, installs only the secret-safe handler, and disables propagation so the same record cannot also reach an unsanitized ancestor handler.

## Private-environment minimization

The boundary minimizes tested forms of:

- macOS, Linux, and Windows user-home paths;
- absolute local paths in audit text;
- labeled usernames;
- labeled hostnames and machine names;
- labeled home and working directories;
- structured environment-variable collections.

Portable identifiers and relative managed paths remain allowed.

## Failure behavior

Validation and sanitization happen before the audit transaction begins.

A rejected event therefore does not:

- insert an audit row;
- increment state revision;
- update workspace revision metadata.

Audit persistence failure behavior for later capabilities remains governed by the accepted security specification: an operation that requires mandatory audit persistence must not be reported as successful when safe audit persistence fails.

## Portability and project-continuity effects

IMP-015 adds no Phase 4A source adapter, canonical conversation record, Phase 4B project record, Resume Bundle, or package-v2 implementation.

It establishes a reusable sink boundary that those later features must use so imported conversations, project status, verification evidence, generated handoff material, and adapter diagnostics cannot bypass secret and private-environment controls.

Specification set 0.2 sequencing remains unchanged:

1. complete IMP-015 through IMP-023;
2. pass the Phase 3 safety gate;
3. implement Phase 4A canonical AI-environment portability;
4. implement Phase 4B project continuity;
5. begin accepted local model integration.

## Security, permission, network, package, backup, and migration effects

- Secret handling: strengthened at audit and logging sinks.
- Permission and authority: unchanged; sanitization grants no permission or authority.
- Network: no listener, request, telemetry, or outbound behavior is added.
- Filesystem: no scan or new workspace read is added; the logging handler writes only to an explicitly supplied stream.
- Package, export, backup, and restore: no format change.
- Database: no schema migration.
- Dependencies: standard library and existing doll modules only.
- Model execution: none.
- External secret store and credential broker: none.

## Acceptance

Permanent tests prove:

- tested secrets and personal values are absent from persisted audit rows;
- secret-bearing audit summaries and allowed metadata values are redacted before persistence;
- secret-like and private-environment metadata keys are rejected without echoing their raw content in validation errors;
- rejected audit writes do not advance state or workspace revisions;
- cyclic, excessive-depth, excessive-item, non-JSON, non-finite, and oversized metadata fails closed;
- unsafe directly inserted audit content is treated as corrupt on read;
- structured secret-field values are redacted without inspecting their value;
- diagnostic cycles and unknown keys do not invoke unsafe string conversion;
- log message templates, arguments, context, exceptions, and correlation fields are sanitized before stream output;
- traceback paths, preformatted exception text, stack text, and unknown-object representations are not written;
- existing unsafe logger handlers are removed and propagation is disabled;
- final log lines remain bounded;
- no model, cloud, network, filesystem scan, secret-store, credential-broker, Phase 4A, or Phase 4B dependency is introduced.
