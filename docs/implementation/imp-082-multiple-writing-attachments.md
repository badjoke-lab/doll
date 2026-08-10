# IMP-082 — Explicit multiple writing attachments

## Objective

Extend the accepted local writing workflow so one `revise`, `summarize`, or `translate` turn may consume a small explicit ordered set of already-supported local file attachments without weakening source-specific validation, task authority, local-only operation, or the accepted single-source API.

## Boundary

IMP-082 adds `LocalWritingAttachment` and an optional `source_attachments` argument to `LocalWritingWorkflowService.execute`. Existing `source_text`, text/Markdown, PDF, OCR-image, and CSV single-source arguments remain supported unchanged. A multi-attachment turn cannot combine `source_attachments` with any legacy primary-source argument or its source-specific options.

A non-empty multiple attachment set contains exactly 2 through 4 caller-selected items. Supported attachment kinds are:

- `document`, reusing IMP-074;
- `pdf`, reusing IMP-076 and its optional pypdf adapter;
- `ocr`, reusing IMP-077 and its optional OCR adapter;
- `csv`, reusing IMP-075 transformation.

Caller order is authoritative and deterministic. There is no file discovery, directory traversal, globbing, semantic retrieval, ranking, model-selected source selection, or automatic attachment expansion.

## Validation and preparation order

The workflow validates the writing mode, request, attachment specification shapes, source-form exclusivity, target language, and operation identity before any local file is opened. It then performs the existing conversation/binding/runtime preflight before reading the first attachment.

After preflight, every attachment is prepared through its unchanged source-specific boundary. All attachments must prepare successfully. The sum of the prepared writing material must not exceed the existing 16,000-character writing-source limit. Only after every source has prepared successfully and the aggregate limit passes are source-origin operation IDs checked for reuse. All source-origin IDs must be unused before the first new source InstructionOrigin is created.

This ordering intentionally prevents a later invalid attachment, aggregate overflow, or pre-existing later attachment origin from leaving a newly created partial source-origin prefix.

## Trust and authority

Each prepared attachment receives its own InstructionOrigin in caller order. Every origin remains:

- `origin_class = external_content`;
- `actor_type = extractor`;
- `authority_class = untrusted_data`;
- `data_only = true`;
- `acquisition_method = ocr` only for OCR material and `extraction` otherwise.

The current user request remains the sole task-authority instruction. Attachment text cannot grant permissions, confirmation, capability authority, binding changes, memory/project/decision mutations, completion authority, or tool authority. Prompt-injection handling remains the accepted local-conversation boundary.

## Result metadata

Multi-attachment results use `source_kind = multiple`, set the singular `source_instruction_id` to `None`, and expose ordered content-free aggregate metadata:

- source InstructionOrigin IDs;
- source kinds;
- prepared character counts;
- prepared-content SHA-256 values;
- aggregate source character count.

Legacy singular source-specific result metadata remains populated only for a single-source turn. No native path, filename, source body, prompt body, generated body, credential, or secret is added to the result.

## Limits and side effects

IMP-082 does not create persistent attachment records, SourceRecords, copied source files, output artifacts, persistent indexes, embeddings, or caches. It performs no network or cloud access, credential access, process or shell launch, capability execution, or binding mutation. Input files are read-only and are not rewritten on success or failure.

`draft` remains source-free. Draft reference attachments are outside this implementation.

## Acceptance

Dedicated synthetic acceptance covers mixed document/CSV order, two-through-four cardinality, legacy-source conflicts, draft rejection, malformed attachment kinds and paths, source-specific option misuse, target-before-read ordering, later-source failure before origin creation, aggregate limit failure, all-origin-ID preflight before first creation, hostile multi-source data isolation, runtime failure, path/content privacy, and exact source preservation.

Standard project CI remains the merge gate on Ubuntu, macOS, and Windows. Existing single-source and accepted IMP-064 real-machine evidence are not broadened by this implementation.

## Explicit non-claims

IMP-082 does not establish automatic source discovery, draft attachments, attachment persistence, semantic retrieval, model-selected attachments, XLSX/ODS support, formula execution, PDF OCR/scanned-PDF fallback, new OCR adapters, tools, network/cloud inference, complete Phase 6, Lite v1.0, release-candidate soak, target-specific application replacement, or stable general anti-lock-in.
