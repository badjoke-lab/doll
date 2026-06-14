# IMP-006 preferences, policies, and permissions

IMP-006 adds typed authoritative records for preferences, durable policies, and scoped
permissions. The implementation uses the existing common record table and audit schema;
it does not add a database migration.

## Preferences

A preference record stores:

- a stable ASCII key;
- one bounded JSON-compatible value;
- an optional description;
- common-envelope revision, status, provenance, sensitivity, and timestamps.

Preferences can be created, inspected, listed, revision-safely updated, and archived.
They are not hidden only inside prompts.

## Policies

A policy record stores:

- a stable key;
- an explicit rule;
- an enabled flag;
- common-envelope revision and lifecycle fields.

Policies are distinct from memories. This slice stores and manages durable rules but does
not yet implement global runtime policy evaluation.

## Permissions

A permission record stores:

- capability ID;
- structured JSON scope with a required `kind`;
- mode;
- expiration;
- approval source;
- last-changed time;
- safe last-used time;
- allow-once remaining-use state.

Initial modes are exactly:

- `denied`;
- `allow_once`;
- `ask`;
- `scoped`.

Unknown modes and allow-all equivalents are rejected. `scoped` requires a non-global scope
and at least one explicit constraint. Global scope is accepted only for denied, ask, or
allow-once records.

## Approval boundary

Permission creation, update, reactivation, and widening require a user-controlled
management actor and an approval source of `management-cli` or `management-ui`.

Model, runtime, capability, imported-content, document, website, and tool-output claims do
not grant approval. A future capability-broker path may consume an existing allow-once
record because consumption only narrows permission. It cannot create or broaden one.

## Default deny and expiration

Resolving a capability and scope with no active matching record returns denied.
Expired permissions also resolve to denied without deleting their history.

An allow-once record starts with one remaining use. Successful consumption atomically:

1. verifies the record and revision;
2. verifies it is active, unexpired, and unused;
3. changes its mode to denied;
4. records last-used and last-changed times;
5. appends an audit event;
6. advances state revision once.

A second consumption is denied and creates no side effect.

## Transactions and audit

Each create, update, archive, or allow-once consumption keeps record mutation, audit
insertion, and state-revision advancement in one SQLite transaction.

Audit metadata includes stable keys, capability IDs, modes, approval source, and scope kind.
It does not include preference values, policy rules, full scope data, secrets, or absolute
host paths.

## CLI

Management commands are grouped under:

```text
doll preference ...
doll policy ...
doll permission ...
```

List commands avoid raw preference values, policy text, and full permission scopes.
Explicit `get` commands display the selected record details. Normal errors identify the
error class without printing the absolute workspace path.

## Limits and exclusions

This slice does not add:

- Capability Broker execution;
- approval dialogs;
- arbitrary file, network, cloud, account, or process capabilities;
- project records;
- memory records;
- export/import;
- backup/restore;
- secret credential storage;
- hard deletion.
