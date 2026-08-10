from pathlib import Path

path = Path("scripts/check-public-site-status.mjs")
text = path.read_text(encoding="utf-8")

old_roadmap = '''  roadmap.includes("### IMP-077 — Optional local image OCR adapter") &&
    roadmap.includes("### IMP-078 — Explicit text and Markdown writing attachments") &&
    roadmap.includes("### IMP-079 — Explicit PDF writing attachment") &&
    roadmap.includes("### IMP-080 — Explicit OCR image writing attachment") &&
    roadmap.includes("the next bounded implementation receives IMP-081 only when a new implementation issue is opened"),
  "roadmap must record IMP-080 and identify IMP-081 as the next unallocated implementation identifier",'''
new_roadmap = '''  roadmap.includes("### IMP-077 — Optional local image OCR adapter") &&
    roadmap.includes("### IMP-078 — Explicit text and Markdown writing attachments") &&
    roadmap.includes("### IMP-079 — Explicit PDF writing attachment") &&
    roadmap.includes("### IMP-080 — Explicit OCR image writing attachment") &&
    roadmap.includes("### IMP-081 — Explicit CSV writing attachment") &&
    roadmap.includes("the next bounded implementation receives IMP-082 only when a new implementation issue is opened"),
  "roadmap must record IMP-081 and identify IMP-082 as the next unallocated implementation identifier",'''
if text.count(old_roadmap) != 1:
    raise SystemExit("roadmap checker marker missing")
text = text.replace(old_roadmap, new_roadmap, 1)

marker = '''expect(
  localWritingPrimary.test_id === "IMP-064-LOCAL-WRITING-PRIMARY" &&'''
if text.count(marker) != 1:
    raise SystemExit("local-writing primary checker marker missing")

csv_check = '''expect(
  dailyUse.csv_writing_attachment_extension?.implementation === "IMP-081" &&
    dailyUse.csv_writing_attachment_extension?.status === "ci-pass" &&
    JSON.stringify(dailyUse.csv_writing_attachment_extension?.passed_evidence_levels) === JSON.stringify(["ci"]) &&
    JSON.stringify(dailyUse.csv_writing_attachment_extension?.required_evidence_levels) === JSON.stringify(["ci"]) &&
    dailyUse.csv_writing_attachment_extension?.selection_mode === "explicit-single-file" &&
    JSON.stringify(dailyUse.csv_writing_attachment_extension?.allowed_extensions) === JSON.stringify([".csv"]) &&
    JSON.stringify(dailyUse.csv_writing_attachment_extension?.supported_modes) === JSON.stringify(["revise", "summarize", "translate"]) &&
    dailyUse.csv_writing_attachment_extension?.draft_primary_source_allowed === false &&
    dailyUse.csv_writing_attachment_extension?.exactly_one_primary_source === true &&
    JSON.stringify(dailyUse.csv_writing_attachment_extension?.primary_source_forms) === JSON.stringify(["inline", "document", "pdf", "ocr", "csv"]) &&
    dailyUse.csv_writing_attachment_extension?.reader_implementation === "IMP-075" &&
    JSON.stringify(dailyUse.csv_writing_attachment_extension?.delimiter_profiles) === JSON.stringify(["comma", "tab", "semicolon", "pipe"]) &&
    dailyUse.csv_writing_attachment_extension?.caller_ordered_column_selection === true &&
    dailyUse.csv_writing_attachment_extension?.column_reordering === true &&
    dailyUse.csv_writing_attachment_extension?.header_renaming === true &&
    dailyUse.csv_writing_attachment_extension?.formula_evaluation === false &&
    dailyUse.csv_writing_attachment_extension?.formula_like_cells_preserved_as_text === true &&
    dailyUse.csv_writing_attachment_extension?.maximum_writing_source_characters === 16000 &&
    dailyUse.csv_writing_attachment_extension?.strict_utf8 === true &&
    dailyUse.csv_writing_attachment_extension?.utf8_bom_handling === "remove-and-report" &&
    dailyUse.csv_writing_attachment_extension?.symlinks_allowed === false &&
    dailyUse.csv_writing_attachment_extension?.automatic_file_discovery === false &&
    dailyUse.csv_writing_attachment_extension?.persistent_document_record === false &&
    dailyUse.csv_writing_attachment_extension?.source_record_created === false &&
    dailyUse.csv_writing_attachment_extension?.artifact_created === false &&
    dailyUse.csv_writing_attachment_extension?.persistent_index === false &&
    dailyUse.csv_writing_attachment_extension?.semantic_retrieval === false &&
    dailyUse.csv_writing_attachment_extension?.model_selected_context === false &&
    dailyUse.csv_writing_attachment_extension?.network_access === false &&
    dailyUse.csv_writing_attachment_extension?.cloud_access === false &&
    dailyUse.csv_writing_attachment_extension?.process_launch === false &&
    dailyUse.csv_writing_attachment_extension?.shell_execution === false &&
    dailyUse.csv_writing_attachment_extension?.capability_execution === false &&
    dailyUse.csv_writing_attachment_extension?.origin_class === "external_content" &&
    dailyUse.csv_writing_attachment_extension?.actor_type === "extractor" &&
    dailyUse.csv_writing_attachment_extension?.acquisition_method === "extraction" &&
    dailyUse.csv_writing_attachment_extension?.authority_class === "untrusted_data" &&
    dailyUse.csv_writing_attachment_extension?.phase6_gate_complete === false &&
    dailyUse.csv_writing_attachment_extension?.lite_v1_complete === false &&
    dailyUse.csv_writing_attachment_extension?.stable_anti_lock_in_claim === false &&
    dailyUse.csv_writing_attachment_extension?.implementation_doc === "docs/implementation/imp-081-csv-writing-attachment.md",
  "IMP-081 CSV writing attachment must remain explicit, transformed-only, untrusted, local-only, and CI-only",
);

'''
text = text.replace(marker, csv_check + marker, 1)
path.write_text(text, encoding="utf-8")
