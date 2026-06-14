# IMP-008 projects and decisions

IMP-008 adds durable ProjectRecord and DecisionRecord management to Doll State.

## ProjectRecord

A project stores:

- name;
- description;
- domain status;
- start and optional end timestamps;
- optional links to decisions, confirmed memories, and managed artifacts.

Initial domain statuses are `planned`, `active`, `on_hold`, `completed`, and
`cancelled`.

## DecisionRecord

A decision stores:

- the explicit decision;
- its reason;
- domain status;
- decision timestamp;
- alternatives and constraints;
- optional review timestamp;
- optional superseded decision;
- optional project, confirmed-memory, and artifact links.

Initial domain statuses are `accepted`, `superseded`, and `reversed`. A decision is
authoritative only when created or changed through the explicit user management path.

## Links

Links are UUID record IDs and are type checked when created or updated:

- memory IDs must resolve to valid confirmed memories;
- artifact IDs must resolve to managed artifact records;
- project IDs must resolve to ProjectRecord instances;
- decision and supersedes IDs must resolve to DecisionRecord instances.

Links are not automatically reciprocal. Updating or archiving one record does not
silently rewrite another authoritative record.

## Lifecycle and transactions

Projects and decisions support create, inspect, list, revision-safe update, archive,
and standalone deterministic JSON export.

Archived records are inspection-only. Create, update, and archive keep the record
mutation, audit insertion, and one state revision increment in one SQLite transaction.
Stale revisions and failed validation leave no partial authoritative mutation.

## Export

Normal export is read-only, deterministic, portable, and rejects secret records. It
does not advance state revision or add audit events.

Bulk Doll State package export/import remains IMP-009 work. IMP-008 supplies the
record-level persistence and portable serialization needed by that package.

## CLI

```text
doll project create|get|list|update|archive|export
doll decision create|get|list|update|archive|export
```

## Exclusions

This slice does not add task execution, automatic planning, automatic progress
inference, automatic decision extraction, model recall, semantic search, reciprocal
link rewriting, bulk state import/export, backup/restore, secret export, or hard delete.
