# IMP-003 SQLite state repository

IMP-003 adds the first authoritative metadata database to an initialized doll workspace.

## Commands

```text
doll init [PATH]
doll state init [PATH]
doll state status [PATH]
```

`doll init` still creates only the workspace identity and directory layout. It does not
create a database. `doll state init` is the explicit operation that creates and migrates
`state/doll-state.sqlite3`.

`doll state status` opens the database through SQLite read-only mode and reports:

- schema version;
- workspace state revision;
- common-envelope record count;
- read-only mode.

## Initial schema

The database starts with schema version 1.

Bootstrap tables:

- `schema_metadata` binds the database to one workspace ID and stores schema and state
  revisions;
- `migration_history` records completed and failed migration attempts.

Schema version 1 adds `records`, the physical foundation for the common authoritative
record envelope:

```text
id
record_type
schema_version
created_at
updated_at
revision
status
provenance
sensitivity
title
metadata_json
```

IMP-003 does not add memory, preference, project, audit, or model-specific records.

## Migration behavior

- migrations are ordered deterministic transitions;
- each migration runs inside `BEGIN IMMEDIATE`;
- schema metadata and the completed migration record commit in the same transaction;
- a failed migration rolls back its schema changes;
- the failure is recorded afterward without marking the migration complete;
- a later writable open may retry a still-pending migration;
- unsupported future schema versions are rejected before write-oriented PRAGMAs are
  applied.

## Revision behavior

Each committed common-envelope create or update:

1. commits the record mutation and database state-revision increment together;
2. updates `workspace.json` atomically to the committed database revision.

If the database revision is ahead because the process stopped between those two steps,
the next writable open repairs `workspace.json`. A workspace revision ahead of the
database is rejected rather than silently moved backward.

## Read-only recovery

Read-only opening uses SQLite URI `mode=ro` and `PRAGMA query_only=ON`.

It does not:

- run migrations;
- change journal mode;
- update `workspace.json`;
- create files;
- advance revisions.

A future schema, missing metadata, or workspace-ID mismatch fails closed.

## Storage and permissions

The database path is:

```text
<workspace>/state/doll-state.sqlite3
```

On POSIX systems the database file is set to mode `0600`. The workspace root and
`workspace.json` permissions remain governed by IMP-002.

No network operation occurs, and IMP-003 stores only schema metadata and synthetic
common-envelope records used by tests.
