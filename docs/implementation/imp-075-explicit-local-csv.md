# IMP-075 — Explicit local CSV inspection and transformation

## Status

Implemented with deterministic synthetic CI evidence after merge. This document does not claim complete Phase 6 or Lite v1.0.

## Objective

Provide the Lite v1.0-blocking CSV inspection and simple transformation function as one explicit, local-only, non-persistent workflow.

## User surface

The root CLI exposes:

```text
doll csv inspect SOURCE
doll csv transform SOURCE
```

Inspection supports an explicit delimiter profile, a bounded preview-row count, and deterministic JSON.

Transformation supports only:

- exact column selection;
- caller-ordered column reordering;
- exact `OLD=NEW` header renaming;
- deterministic JSON or CSV output to the current command output.

No transformed file is written. The selected source is not overwritten.

## Source and parser boundary

A selected source must:

- use the `.csv` extension;
- be one regular non-symlink file;
- remain within the two-megabyte source limit;
- remain unchanged across path and open-handle identity, size, and modification-time verification;
- decode as strict UTF-8 after deterministic optional UTF-8 BOM removal;
- use one explicit supported delimiter profile: comma, tab, semicolon, or pipe;
- contain one non-empty unique header row;
- remain within row, column, cell, aggregate-character, and preview limits;
- contain only rectangular data rows;
- contain no NUL, DEL, or prohibited control characters.

Parsing uses the Python standard-library CSV engine with strict syntax handling. No dialect sniffing, encoding detection, type inference, spreadsheet engine, or expression language is used.

## Inspection result

Content-free metadata includes only:

- schema version;
- delimiter profile;
- ordered headers;
- row and column counts;
- source and decoded-content byte counts;
- decoded character count;
- exact source and decoded-content SHA-256 values;
- whether a UTF-8 BOM was removed;
- blank-cell count;
- potential spreadsheet-formula cell count;
- fixed instruction-origin classification;
- explicit false flags for source persistence, output persistence, workspace mutation, state mutation, formula evaluation, model execution, and network access.

A bounded preview may include caller-selected source cell text. Native paths, filenames, usernames, hostnames, credentials, and secret values are not included in metadata or errors.

Potential formula cells are cells whose first non-space or non-tab character is `=`, `+`, `-`, or `@`. They are counted for visibility but are never evaluated, rewritten, neutralized, executed, or promoted to instructions.

## Transformation contract

When no column selection is supplied, all columns retain source order. When columns are supplied, they must be exact, existing, unique header names and the output follows caller order.

Header renames:

- use exact `OLD=NEW` syntax;
- apply only to selected columns;
- require non-blank bounded target headers;
- reject duplicate rename sources;
- reject duplicate final output headers.

Cell text is preserved exactly. The transformed CSV is serialized through the standard-library CSV writer using the selected delimiter, minimal quoting, UTF-8, and `\n` line endings. The result includes an exact output SHA-256 and byte and character counts.

Transformation does not sort, filter, join, group, aggregate, calculate, infer types, evaluate formulas, or execute expressions.

## Instruction and authority boundary

Every source header and cell remains:

```text
origin_class = external_content
actor_type = extractor
acquisition_method = extraction
authority_class = untrusted_data
```

CSV content cannot grant task authority, approval, permission, confirmation, capability authority, credential scope, memory, fact, project state, work completion, procedure approval, checkpoint confirmation, or model binding.

IMP-075 does not inject CSV content into a model context.

## State and side effects

The workflow performs no:

- workspace initialization or mutation;
- SQLite or authoritative-state mutation;
- artifact creation or publication;
- audit write;
- source overwrite or output-file creation;
- memory, project, decision, work-item, procedure, or checkpoint mutation;
- permission, confirmation, or capability operation;
- formula execution;
- model or runtime execution;
- process or shell execution;
- network or cloud request;
- credential or binding access;
- persistent indexing or transformed-result persistence.

## Acceptance coverage

Dedicated tests cover:

- Unicode and Japanese text;
- quoted delimiters and quoted line breaks;
- CRLF and UTF-8 BOM input;
- all explicit delimiter profiles;
- exact hashes and counts;
- blank and formula-like cell counts;
- bounded previews;
- column selection and reordering;
- exact header renaming;
- deterministic output and line endings;
- output reparsing to exact expected cells;
- source, workspace, and state preservation;
- malformed syntax, blank and duplicate headers, ragged rows, invalid UTF-8, binary-like content, size and structural limits, missing files, directories, symlinks, identity mismatch, and changed files;
- invalid delimiter, selection, and rename requests;
- path-free CLI failures and help without workspace initialization;
- Ubuntu, macOS, and Windows CI.

## Non-claims

IMP-075 does not establish:

- type inference;
- sorting, filtering, joins, grouping, aggregation, or arithmetic;
- formula execution or spreadsheet safety rewriting;
- arbitrary expressions or code;
- XLSX or other spreadsheet formats;
- source overwrite, artifact publication, or persistent transformed files;
- automatic discovery;
- semantic retrieval or model-selected context;
- writing-workflow attachment integration;
- PDF, OCR, or Web processing;
- model execution or tools;
- cloud services;
- complete Phase 6;
- Lite v1.0 completion;
- Lite performance acceptance;
- the release-candidate soak;
- stable general anti-lock-in.
