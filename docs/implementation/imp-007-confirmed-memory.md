# IMP-007 confirmed memory

IMP-007 adds the first authoritative long-term memory slice. Only explicitly confirmed
MemoryRecord instances are durable memory in this implementation.

## Record shape

Each confirmed memory uses the common record envelope and stores:

- `memory_class=confirmed`;
- content and subject;
- source type;
- `confirmation_state=confirmed`;
- optional validity interval;
- confidence from 0 to 1;
- related-memory IDs;
- contradicting-memory IDs;
- optional source, model, runtime, session, and origin-operation references.

The common provenance field is derived from source type. Explicit user statements and
accepted suggestions use `user-confirmed`; approved imports use `imported`; migrated and
restored memories preserve their corresponding provenance.

## Authority boundary

Create, update, and archive operations require the explicit user-controlled management
path. Model, runtime, capability, and system actors cannot directly create or edit a
confirmed memory.

Accepted model suggestions require model, runtime, session, and origin-operation
references. The accepted suggestion still becomes authoritative only through the user
management path.

There is no automatic conversation-to-memory conversion, automatic recall, prompt
injection, suggested-memory workflow, semantic search, or contradiction resolution in
this slice.

## Lifecycle

Confirmed memories support:

- create;
- inspect;
- list;
- revision-safe update;
- archive;
- standalone deterministic JSON export.

Archived memories are inspection-only. They cannot be updated or repeatedly archived.
Stale revisions cannot overwrite a newer record.

Related and contradicting references must point to existing confirmed memory records.
One ID cannot appear in both sets, and a memory cannot reference itself.

## Export

`doll memory export` writes one deterministic UTF-8 JSON object to standard output. A user
may redirect it to a chosen file. The export command performs no authoritative mutation,
does not advance state revision, and does not append an audit event.

Normal export rejects records with `sensitivity=secret`. Exported data contains portable
record values only and does not contain absolute local paths.

## Transactions and audit

Create, update, and archive keep the record mutation, audit insertion, and one state
revision increment in a single SQLite transaction. Database failures roll back and are
reported as state-corruption errors.

Audit metadata records source type, sensitivity, reference counts, and whether a validity
window exists. It does not contain memory content, subject text, secrets, or local paths.

## CLI

Management commands are available under:

```text
doll memory create
doll memory update
doll memory get
doll memory list
doll memory archive
doll memory export
```

## Exclusions

This slice does not add session memory, suggested memory, automatic extraction, model
recall, embeddings, FTS, contradiction adjudication, project relationships, bulk Doll
State export/import, backup/restore, secret export, or hard deletion.

## Envelope validation

Typed memory inspection validates the common envelope as well as memory metadata.
The first confirmed-memory schema accepts schema version 1, positive revisions,
active or archived status, supported sensitivity values, supported confirmed-memory
provenance, valid UTC timestamps, and an update time that is not earlier than creation.

Memory listing with `--include-archived` includes only active and archived confirmed
memories. Invalid, deleted, and superseded rows are not presented as ordinary confirmed
memory entries.
