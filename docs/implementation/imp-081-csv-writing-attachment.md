# IMP-081 — Explicit CSV writing attachment

Status: implementation and CI acceptance in progress.

Issue: #245

## Objective

Allow one explicitly selected local CSV to replace inline, text/Markdown, PDF, or OCR-image primary source material for the existing bounded `revise`, `summarize`, and `translate` writing modes while preserving the accepted task-versus-material authority boundary.

## Accepted foundations

IMP-081 composes existing contracts rather than introducing a spreadsheet engine:

- IMP-063/IMP-064 bounded local writing workflow and accepted primary Intel Mac evidence;
- IMP-068 explicit translation mode;
- IMP-075 bounded local CSV inspection and non-persistent column transformation;
- IMP-078 exactly-one-primary-source attachment selection;
- IMP-079/IMP-080 attachment metadata and target-preflight composition patterns.

## Source selection and transform options

The writing workflow accepts `none`, `inline`, `document`, `pdf`, `ocr`, and `csv` source kinds.

- `draft` accepts no primary source or CSV transform options;
- `revise`, `summarize`, and `translate` require exactly one primary source form;
- the CSV source is one explicit `Path` to `.csv`;
- callers may choose one IMP-075 delimiter profile (`comma`, `tab`, `semicolon`, or `pipe`), an ordered subset of exact source headers, and exact header renames;
- CSV transform options without a CSV source fail rather than being ignored;
- pure option type validation occurs before target preflight, while the file is not opened until conversation, capacity, binding, and runtime-declaration preflight succeeds.

## CSV validation and writing material

The selected CSV passes only through the unchanged IMP-075 `transform_local_csv` boundary. That path provides:

- regular-file and symlink rejection;
- two-megabyte source limit;
- strict UTF-8 with deterministic BOM removal;
- path/open-handle identity, size, and modification-time verification;
- explicit delimiter profiles only;
- non-blank unique headers and rectangular rows;
- at most 10,000 rows and 200 columns;
- bounded cell and aggregate character counts;
- formula-like-cell visibility without formula execution;
- only exact column selection/reordering and exact header renaming;
- deterministic UTF-8 CSV output with `\n` line endings;
- no source overwrite or output-file creation.

The deterministic transform output is then validated as the writing source and must satisfy the existing 16,000-character writing-source limit before a writing-source InstructionOrigin is created. The model never receives unvalidated source bytes.

## Trust and instruction origin

All transformed CSV text remains writing material only. The source InstructionOrigin retains:

- origin class: `external_content`;
- actor type: `extractor`;
- acquisition method: `extraction`;
- authority class: `untrusted_data`;
- prompt channel: data-only `untrusted_content`.

Formula-like cells are inert text. Cells or headers containing instructions cannot change writing mode, target language, permissions, confirmations, capabilities, bindings, memory, project state, decisions, completion authority, or any other authoritative state.

## Result metadata

The content-free writing result identifies `source_kind = "csv"` and exposes only bounded path-free metadata:

- delimiter profile;
- source byte count, source SHA-256, content SHA-256, and BOM-removal state;
- source row and column counts;
- transformed output column count;
- blank-cell and potential-formula-cell counts;
- transformed output byte count, character count, and SHA-256;
- existing writing-source character count after normal writing-source validation.

Headers, selected column names, renamed header text, cell values, native path, filename, prompt text, generated response text, credentials, and secrets are not added to the writing result.

## Failure preservation

Invalid source combinations, transform options without a CSV source, invalid option types, unsupported delimiter profiles, malformed or unsafe CSV input, missing or invalid selected columns, invalid renames, source limits, transformed writing material over 16,000 characters, target/runtime preflight failures, and runtime failures do not modify the selected CSV.

Failures before runtime do not create a writing-source InstructionOrigin. Runtime failures retain the existing canonical local-writing persistence contract without granting CSV content additional authority.

## Acceptance

Dedicated deterministic acceptance covers:

- real IMP-075 UTF-8/BOM/semicolon parsing and transformation through the writing workflow;
- caller-ordered column selection and exact header rename reaching `untrusted_content`;
- formula-like cells remaining inert visible text;
- path-free source and transform metadata and hashes;
- persisted `external_content` / `extractor` / `extraction` / `untrusted_data` provenance;
- source-form conflict, draft, transform-options-without-source, path-type, selected-column-type, and rename-type denial;
- proof that target preflight occurs before CSV transformation;
- transform failure before source-origin creation;
- missing column and over-16,000-character writing material failure before source-origin creation;
- hostile CSV instructions remaining data-only;
- runtime failure and exact source-file byte/size/mtime preservation;
- regression of existing inline, text/Markdown, PDF, and OCR-image writing sources through the full suite.

Standard CI is required on Ubuntu, macOS, and Windows. IMP-081 does not require or broaden primary Intel Mac real-machine evidence.

## Explicit non-claims

IMP-081 does not establish type inference, sorting, filtering, joins, grouping, aggregation, arithmetic, formula evaluation, arbitrary expressions, spreadsheet formats other than CSV, multiple attachments, mixed primary sources, draft reference attachments, attachment persistence, SourceRecord creation, artifact publication, persistent indexing, automatic file discovery, semantic retrieval, embeddings, ranking, model-selected context, Web retrieval, process/shell/tool/capability execution, network/cloud access, target-specific export, accessibility presentation, Lite performance acceptance, the release-candidate soak, complete Phase 6, Lite v1.0 completion, or stable general anti-lock-in.
