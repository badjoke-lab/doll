# IMP-004 append-oriented audit service

IMP-004 adds a local audit history to the authoritative SQLite state repository.

The audit service records bounded operational facts without storing raw exception messages,
stack traces, credentials, secrets, or absolute local paths in normal CLI output.

## Schema migration

IMP-004 advances the state schema from version 1 to version 2.

Schema version 2 adds `audit_events` with:

```text
sequence
event_id
operation_id
occurred_at
actor_type
actor_id
action
target_type
target_id
result
summary
error_class
metadata_json
```

The migration is applied through the existing deterministic migration runner. Existing
schema version 1 workspaces migrate through `1 -> 2`; new workspaces run both initial
migrations in order.

The database creates triggers that reject `UPDATE` and `DELETE` operations on
`audit_events`. The public audit service exposes append, get, and list operations only.

## Actor and result categories

Actor categories:

- `user`;
- `system`;
- `model`;
- `runtime`;
- `capability`;
- `migration`.

A model actor record does not represent user approval.

Result categories:

- `success`;
- `denied`;
- `failed`;
- `cancelled`;
- `partial`.

## Operation IDs

Each audit event has a globally unique event ID. Related events may share one operation
ID so an operation can be inspected across multiple steps.

When the caller does not provide an operation ID, the service generates a UUID. IDs do
not encode host names, account names, file paths, or other personal information.

## Secret-safe persistence

The service persists only the exception class, such as `TimeoutError`. It never persists
the raw exception message or traceback.

Audit summaries are single-line, bounded strings. Summaries containing recognized secret
assignments, private-key material, JWT-like values, or common absolute local paths are
rejected.

Audit metadata:

- must be a JSON object;
- must use string keys;
- must use portable standard JSON values;
- rejects `NaN` and infinity;
- rejects recognized secret-like keys recursively;
- rejects recognized secret material in string values;
- is limited to 8192 encoded UTF-8 bytes.

Secret detection is defensive and best-effort. Callers must still avoid submitting
sensitive values.

## State revision behavior

Appending an audit event and advancing the database `state_revision` occur in one SQLite
transaction. After commit, `workspace.json` is synchronized atomically through the
existing IMP-003 revision mechanism.

A failed validation or failed SQL transaction does not append an event or advance the
revision.

## CLI

```text
doll audit list [PATH]
```

Optional filters:

```text
--operation-id
--action
--actor-type
--result
--limit
```

The command opens the repository with SQLite read-only mode. It does not run migrations,
advance revisions, update `workspace.json`, or modify filesystem timestamps.

CLI output includes:

- UTC time;
- result;
- actor type;
- action;
- operation ID;
- target type;
- safe error class;
- safe summary.

CLI output intentionally omits actor IDs, target IDs, metadata, workspace IDs, database
paths, exception messages, and tracebacks.

## Recovery behavior

A schema version 1 database is migrated only through a writable open. A read-only open
never migrates. Unsupported future schema versions fail closed through the existing state
repository checks.

A failed `1 -> 2` migration rolls back the audit table and trigger changes while leaving
the previously committed schema version 1 database usable. A later writable open may retry
the accepted migration.

## Scope boundary

IMP-004 does not yet provide:

- automatic audit integration for every command;
- permission approval records;
- audit export or retention policy;
- audit deletion or compaction;
- cryptographic signing;
- telemetry or external logging;
- cloud logging.

Those behaviors require later accepted implementation slices.
