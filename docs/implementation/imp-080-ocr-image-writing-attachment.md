# IMP-080 — Explicit OCR image writing attachment

Status: implemented with deterministic CI evidence on Ubuntu, macOS, and Windows.

Issue: #243

## Objective

Allow one explicitly selected local PNG or JPEG to replace inline, text/Markdown, or PDF primary source material for the existing bounded `revise`, `summarize`, and `translate` writing modes after local OCR, while preserving the accepted task-versus-material authority boundary.

## Accepted foundations

IMP-080 composes existing contracts rather than adding a second OCR stack:

- IMP-063/IMP-064 bounded local writing workflow and accepted primary Intel Mac evidence;
- IMP-068 explicit translation mode;
- IMP-077 bounded local raster-image OCR with optional invocation-only macOS Vision `ocrmac` adapter;
- IMP-078 exactly-one-primary-source attachment selection;
- IMP-079 attachment metadata and preflight composition pattern.

## Source selection

The writing workflow accepts `none`, `inline`, `document`, `pdf`, and `ocr` source kinds.

- `draft` accepts no primary source;
- `revise`, `summarize`, and `translate` require exactly one primary source form;
- the OCR source is one explicit `Path` pointing to a PNG, JPG, or JPEG;
- source-form validation occurs before target preflight, but the selected image is not opened and OCR is not invoked until the accepted conversation, capacity, active-binding, and runtime-declaration preflight succeeds.

## OCR and writing material

The selected image passes only through the unchanged IMP-077 `extract_local_image_ocr` boundary. That path provides:

- regular-file and symlink rejection;
- eight-megabyte source limit;
- PNG/JPEG extension, signature, and structural validation;
- path/open-handle identity, size, and modification-time verification;
- maximum 10,000-pixel width and height and 25,000,000 total pixels;
- maximum 1,000 recognized lines;
- maximum 20,000 characters per OCR line and 200,000 aggregate recognized characters;
- optional invocation-only macOS Vision `ocrmac` adapter loading;
- no process or shell execution, network/cloud access, persistence, model selection, or automatic download.

After successful OCR, recognized line strings are joined deterministically in adapter order with one newline character. The joined text must then satisfy the existing 16,000-character writing-source limit. Empty or whitespace-only recognized material fails closed. No writing-source InstructionOrigin is created until OCR and writing-source validation both succeed.

## Trust and instruction origin

Recognized OCR text remains only writing material. The source InstructionOrigin is classified as:

- origin class: `external_content`;
- actor type: `extractor`;
- acquisition method: `ocr`;
- authority class: `untrusted_data`;
- prompt channel: data-only `untrusted_content`.

The current user request remains the only task-authority instruction. Instructions recognized inside the image cannot change mode, target language, permissions, confirmations, capabilities, bindings, memory, project state, decisions, completion authority, or any other authoritative state.

## Result metadata

The content-free writing result identifies `source_kind = "ocr"` and exposes only bounded path-free OCR metadata:

- adapter ID and version;
- source byte count and SHA-256;
- image format;
- width, height, and pixel count;
- recognized line count;
- raw aggregate recognized-character count;
- existing writing-source character count after deterministic line joining.

Native path, filename, recognized text, prompt text, generated response text, credentials, and secrets are not added to the writing result.

## Failure preservation

Invalid source combinations, invalid path types, unavailable writing targets, unsupported or unsafe images, missing optional OCR adapter, invalid OCR output, blank recognized material, OCR limits, the 16,000-character writing-source limit, and runtime failure do not modify the source image.

Failures before runtime do not create a writing-source origin. Runtime failures retain the existing canonical local-writing persistence contract without granting recognized content additional authority.

## Acceptance

Dedicated deterministic acceptance covers:

- real IMP-077 PNG structural/source validation with an injected fake OCR adapter;
- recognized line order reaching `untrusted_content`;
- `acquisition_method = "ocr"` on the persisted source InstructionOrigin;
- path-free OCR metadata and source hash;
- exact source-form conflict and draft denial;
- invalid OCR source path type denial;
- proof that target preflight occurs before OCR invocation;
- missing optional adapter failure before source-origin creation;
- blank and over-16,000-character writing material failure before source-origin creation;
- hostile recognized instructions remaining data-only;
- runtime failure and exact source-image byte/size/mtime preservation;
- regression of existing inline, text/Markdown, and PDF writing sources through the full suite.

Standard CI is required on Ubuntu, macOS, and Windows. Existing hosted macOS IMP-077 Vision execution may remain referenced, but IMP-080 does not require or broaden primary Intel Mac real-machine evidence.

## Explicit non-claims

IMP-080 does not establish image understanding beyond OCR, OCR of PDFs, scanned-PDF fallback, a Windows/Linux real OCR adapter, multiple attachments, mixed primary sources, draft reference attachments, attachment persistence, SourceRecord creation, artifact publication, persistent indexing, automatic file discovery, semantic retrieval, embeddings, ranking, model-selected context, Web retrieval, process/shell/tool/capability execution, network/cloud access, CSV writing attachment integration, target-specific export, accessibility presentation, Lite performance acceptance, the release-candidate soak, complete Phase 6, Lite v1.0 completion, or stable general anti-lock-in.
