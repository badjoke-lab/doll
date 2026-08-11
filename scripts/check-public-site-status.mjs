import fs from "node:fs";
import path from "node:path";

import {
  RETIRED_IMPLEMENTATION_IDS,
  buildProjectActivity,
} from "../website/project-status-core.mjs";

const root = process.cwd();

function read(relativePath) {
  return fs.readFileSync(path.join(root, relativePath), "utf8");
}

function fail(message) {
  console.error(`public-site-status check failed: ${message}`);
  process.exitCode = 1;
}

function expect(condition, message) {
  if (!condition) {
    fail(message);
  }
}

const status = JSON.parse(read("website/project-status.json"));
const localPortability = JSON.parse(
  read("docs/testing/phase-6-local-portability-matrix.json"),
);
const dailyUse = JSON.parse(
  read("docs/testing/phase-6-daily-use-matrix.json"),
);
const shutdownEscape = JSON.parse(
  read("docs/testing/phase-6-shutdown-escape-matrix.json"),
);
const chatgptHistory = JSON.parse(
  read("docs/testing/phase-6-chatgpt-history-matrix.json"),
);
const chatgptPrivate = JSON.parse(
  read("docs/testing/results/IMP-060-project-owner-chatgpt-2026-07-10.json"),
);
const importedReplayPrimary = JSON.parse(
  read("docs/testing/results/IMP-062-primary-intel-mac-2026-07-12.json"),
);
const localWritingPrimary = JSON.parse(
  read("docs/testing/results/IMP-064-primary-intel-mac-2026-07-15.json"),
);

expect(status.schema_version === 2, "project-status.json must use schema_version 2");
expect(
  Boolean(status.maturity) && typeof status.maturity === "string",
  "project-status.json requires a maturity string",
);
expect(
  Array.isArray(status.completed_phases) && status.completed_phases.includes("5"),
  "project-status.json must record completed phases through Phase 5",
);
expect(
  status.phase?.id === "6" &&
    status.phase?.name === "Local AI portability and daily-use integration" &&
    status.phase?.state === "in_progress" &&
    status.phase?.started_by_implementation === 55 &&
    status.phase?.next_implementation === 84,
  "project-status.json must mark Phase 6 in progress through IMP-083 with IMP-084 next",
);
expect(
  status.model_runtime &&
    typeof status.model_runtime.connected === "boolean" &&
    typeof status.model_runtime.message === "string",
  "project-status.json requires model_runtime.connected and model_runtime.message",
);
expect(
  status.model_runtime.message.includes("through IMP-083") &&
    status.model_runtime.message.includes("bounded Lite client resource measurement mechanics") &&
    status.model_runtime.message.includes("does not define RAM, disk, or latency requirements") &&
    status.model_runtime.message.includes("optional local PDF text extraction") &&
    status.model_runtime.message.includes("optional local image OCR") &&
    status.model_runtime.message.includes("text/Markdown writing attachment integration") &&
    status.model_runtime.message.includes("PDF writing attachment integration") &&
    status.model_runtime.message.includes("OCR image writing attachment integration") &&
    status.model_runtime.message.includes("CSV writing attachment integration") &&
    status.model_runtime.message.includes("multiple-attachment writing integration") &&
    status.model_runtime.message.includes("macOS Vision") &&
    status.model_runtime.message.includes("invocation-only in-process pypdf adapter") &&
    status.model_runtime.message.includes("reported without OCR") &&
    status.model_runtime.message.includes("no source overwrite, output file, persistence") &&
    status.model_runtime.message.includes("passes at both CI and real-machine evidence levels"),
  "project-status.json must describe IMP-083 without inventing resource thresholds or real-machine evidence",
);
expect(
  /^\d{4}-\d{2}-\d{2}$/.test(status.last_reviewed || ""),
  "project-status.json last_reviewed must be YYYY-MM-DD",
);
expect(
  localPortability.context_replay_extension?.implementation === "IMP-061" &&
    localPortability.context_replay_extension?.acceptance_implementation ===
      "IMP-062" &&
    localPortability.context_replay_extension?.portability_test_id ===
      "PORT-013" &&
    localPortability.context_replay_extension?.status === "pass" &&
    localPortability.context_replay_extension?.passed_evidence_levels?.length ===
      2 &&
    localPortability.context_replay_extension?.passed_evidence_levels?.includes(
      "ci",
    ) &&
    localPortability.context_replay_extension?.passed_evidence_levels?.includes(
      "real-machine",
    ) &&
    localPortability.context_replay_extension?.required_evidence_levels?.includes(
      "real-machine",
    ) &&
    localPortability.context_replay_extension?.accepted_real_machine_result ===
      "docs/testing/results/IMP-062-primary-intel-mac-2026-07-12.json" &&
    localPortability.context_replay_extension?.real_machine_gate?.required ===
      true &&
    localPortability.context_replay_extension?.real_machine_gate?.status ===
      "pass" &&
    localPortability.context_replay_extension?.real_machine_gate?.commit_sha ===
      "65f3b5e9ac8c9961c7ec2a152dfdfbb637386e93" &&
    localPortability.context_replay_extension?.real_machine_gate?.completed_at ===
      "2026-07-12T14:48:39.025820Z" &&
    localPortability.context_replay_extension?.real_machine_gate_status ===
      "pass" &&
    localPortability.context_replay_extension?.implementation_doc ===
      "docs/implementation/imp-062-imported-context-replay-real-machine-acceptance.md" &&
    localPortability.context_replay_extension?.runbook ===
      "docs/testing/imp-062-primary-intel-mac-runbook.md" &&
    localPortability.context_replay_extension?.phase6_gate_complete === false &&
    localPortability.context_replay_extension?.stable_anti_lock_in_claim === false,
  "IMP-061/IMP-062 context replay extension must bind accepted real-machine evidence",
);

expect(
  dailyUse.schema_version === 1 &&
    dailyUse.phase === "6" &&
    dailyUse.local_writing_workflow?.implementation === "IMP-063" &&
    dailyUse.local_writing_workflow?.acceptance_implementation === "IMP-064" &&
    dailyUse.local_writing_workflow?.status === "pass" &&
    JSON.stringify(dailyUse.local_writing_workflow?.passed_evidence_levels) ===
      JSON.stringify(["ci", "real-machine"]) &&
    JSON.stringify(dailyUse.local_writing_workflow?.required_evidence_levels) ===
      JSON.stringify(["ci", "real-machine"]) &&
    dailyUse.local_writing_workflow?.accepted_real_machine_result ===
      "docs/testing/results/IMP-064-primary-intel-mac-2026-07-15.json" &&
    dailyUse.local_writing_workflow?.real_machine_gate?.required === true &&
    dailyUse.local_writing_workflow?.real_machine_gate?.status === "pass" &&
    dailyUse.local_writing_workflow?.real_machine_gate?.commit_sha ===
      "d40ba32e87f6d211b05e9da1e1f51974ec6fc369" &&
    dailyUse.local_writing_workflow?.real_machine_gate?.completed_at ===
      "2026-07-14T16:17:03.751999Z" &&
    dailyUse.local_writing_workflow?.real_machine_gate_status === "pass" &&
    dailyUse.local_writing_workflow?.implementation_doc ===
      "docs/implementation/imp-064-primary-intel-mac-local-writing-acceptance.md" &&
    dailyUse.local_writing_workflow?.runbook ===
      "docs/testing/imp-064-primary-intel-mac-runbook.md" &&
    dailyUse.local_writing_workflow?.phase6_gate_complete === false &&
    dailyUse.local_writing_workflow?.stable_anti_lock_in_claim === false,
  "IMP-063/IMP-064 writing workflow must bind accepted real-machine evidence",
);

expect(
  dailyUse.explicit_context_extension?.implementation === "IMP-066" &&
    dailyUse.explicit_context_extension?.status === "ci-pass" &&
    JSON.stringify(dailyUse.explicit_context_extension?.passed_evidence_levels) ===
      JSON.stringify(["ci"]) &&
    JSON.stringify(dailyUse.explicit_context_extension?.required_evidence_levels) ===
      JSON.stringify(["ci"]) &&
    dailyUse.explicit_context_extension?.selection_mode === "explicit-only" &&
    dailyUse.explicit_context_extension?.automatic_retrieval === false &&
    dailyUse.explicit_context_extension?.semantic_retrieval === false &&
    dailyUse.explicit_context_extension?.model_selected_context === false &&
    dailyUse.explicit_context_extension?.secret_records_allowed === false &&
    JSON.stringify(dailyUse.explicit_context_extension?.selected_record_types) ===
      JSON.stringify(["confirmed_memory", "project", "decision"]) &&
    dailyUse.explicit_context_extension?.context_origin_class ===
      "external_content" &&
    dailyUse.explicit_context_extension?.context_actor_type === "retriever" &&
    dailyUse.explicit_context_extension?.context_acquisition_method ===
      "retrieval" &&
    dailyUse.explicit_context_extension?.context_authority_class ===
      "untrusted_data" &&
    dailyUse.explicit_context_extension?.phase6_gate_complete === false &&
    dailyUse.explicit_context_extension?.stable_anti_lock_in_claim === false &&
    dailyUse.explicit_context_extension?.implementation_doc ===
      "docs/implementation/imp-066-explicit-decision-context.md",
  "IMP-066 explicit decision context must remain bounded and CI-only",
);

expect(
  dailyUse.resume_bundle_context_extension?.implementation === "IMP-067" &&
    dailyUse.resume_bundle_context_extension?.status === "ci-pass" &&
    JSON.stringify(
      dailyUse.resume_bundle_context_extension?.passed_evidence_levels,
    ) === JSON.stringify(["ci"]) &&
    dailyUse.resume_bundle_context_extension?.selection_mode ===
      "explicit-only" &&
    dailyUse.resume_bundle_context_extension?.maximum_selected_bundles === 1 &&
    dailyUse.resume_bundle_context_extension?.automatic_file_search === false &&
    dailyUse.resume_bundle_context_extension?.semantic_retrieval === false &&
    dailyUse.resume_bundle_context_extension?.model_selected_context === false &&
    dailyUse.resume_bundle_context_extension?.canonical_state_import === false &&
    dailyUse.resume_bundle_context_extension?.secret_content_allowed === false &&
    dailyUse.resume_bundle_context_extension?.context_actor_type ===
      "extractor" &&
    dailyUse.resume_bundle_context_extension?.context_acquisition_method ===
      "extraction" &&
    dailyUse.resume_bundle_context_extension?.context_authority_class ===
      "untrusted_data" &&
    dailyUse.resume_bundle_context_extension?.phase6_gate_complete === false &&
    dailyUse.resume_bundle_context_extension?.stable_anti_lock_in_claim ===
      false &&
    dailyUse.resume_bundle_context_extension?.implementation_doc ===
      "docs/implementation/imp-067-resume-bundle-writing-context.md",
  "IMP-067 Resume Bundle context must remain explicit, bounded, and CI-only",
);

expect(
  dailyUse.translation_extension?.implementation === "IMP-068" &&
    dailyUse.translation_extension?.status === "ci-pass" &&
    JSON.stringify(dailyUse.translation_extension?.passed_evidence_levels) ===
      JSON.stringify(["ci"]) &&
    JSON.stringify(dailyUse.translation_extension?.required_evidence_levels) ===
      JSON.stringify(["ci"]) &&
    dailyUse.translation_extension?.mode === "translate" &&
    dailyUse.translation_extension?.source_required === true &&
    dailyUse.translation_extension?.target_language_required === true &&
    dailyUse.translation_extension?.automatic_language_detection === false &&
    dailyUse.translation_extension?.source_origin_class === "external_content" &&
    dailyUse.translation_extension?.source_actor_type === "extractor" &&
    dailyUse.translation_extension?.source_acquisition_method === "extraction" &&
    dailyUse.translation_extension?.source_authority_class === "untrusted_data" &&
    dailyUse.translation_extension?.selected_context_compatible === true &&
    dailyUse.translation_extension?.phase6_gate_complete === false &&
    dailyUse.translation_extension?.lite_v1_complete === false &&
    dailyUse.translation_extension?.stable_anti_lock_in_claim === false &&
    dailyUse.translation_extension?.implementation_doc ===
      "docs/implementation/imp-068-explicit-local-translation.md",
  "IMP-068 translation must remain explicit, data-only, bounded, and CI-only",
);

expect(
  dailyUse.work_item_proposal_extension?.implementation === "IMP-069" &&
    dailyUse.work_item_proposal_extension?.status === "ci-pass" &&
    JSON.stringify(dailyUse.work_item_proposal_extension?.passed_evidence_levels) ===
      JSON.stringify(["ci"]) &&
    JSON.stringify(dailyUse.work_item_proposal_extension?.required_evidence_levels) ===
      JSON.stringify(["ci"]) &&
    dailyUse.work_item_proposal_extension?.project_selection_mode === "explicit-only" &&
    dailyUse.work_item_proposal_extension?.maximum_proposals_per_turn === 1 &&
    dailyUse.work_item_proposal_extension?.model_provenance === "model-proposed" &&
    dailyUse.work_item_proposal_extension?.forced_work_status === "proposed" &&
    dailyUse.work_item_proposal_extension?.forced_verification_state === "not_verified" &&
    dailyUse.work_item_proposal_extension?.automatic_acceptance === false &&
    dailyUse.work_item_proposal_extension?.automatic_start === false &&
    dailyUse.work_item_proposal_extension?.automatic_completion === false &&
    dailyUse.work_item_proposal_extension?.capability_execution === false &&
    dailyUse.work_item_proposal_extension?.tool_execution === false &&
    dailyUse.work_item_proposal_extension?.semantic_retrieval === false &&
    JSON.stringify(dailyUse.work_item_proposal_extension?.selected_context_types) ===
      JSON.stringify(["project", "confirmed_memory", "decision"]) &&
    dailyUse.work_item_proposal_extension?.context_origin_class === "external_content" &&
    dailyUse.work_item_proposal_extension?.context_authority_class === "untrusted_data" &&
    dailyUse.work_item_proposal_extension?.phase6_gate_complete === false &&
    dailyUse.work_item_proposal_extension?.lite_v1_complete === false &&
    dailyUse.work_item_proposal_extension?.stable_anti_lock_in_claim === false &&
    dailyUse.work_item_proposal_extension?.implementation_doc ===
      "docs/implementation/imp-069-local-work-item-proposal.md",
  "IMP-069 work-item proposals must remain explicit, proposed-only, and CI-only",
);

expect(
  dailyUse.portability_review_extension?.implementation === "IMP-070" &&
    dailyUse.portability_review_extension?.status === "ci-pass" &&
    JSON.stringify(dailyUse.portability_review_extension?.passed_evidence_levels) ===
      JSON.stringify(["ci"]) &&
    JSON.stringify(dailyUse.portability_review_extension?.required_evidence_levels) ===
      JSON.stringify(["ci"]) &&
    dailyUse.portability_review_extension?.selection_mode === "explicit-only" &&
    JSON.stringify(dailyUse.portability_review_extension?.selected_record_types) ===
      JSON.stringify([
        "portability_import_batch",
        "portability_mapping_report",
        "portability_loss",
      ]) &&
    dailyUse.portability_review_extension?.exact_link_resolution === true &&
    dailyUse.portability_review_extension?.original_source_read === false &&
    dailyUse.portability_review_extension?.source_payload_read === false &&
    dailyUse.portability_review_extension?.automatic_retrieval === false &&
    dailyUse.portability_review_extension?.semantic_retrieval === false &&
    dailyUse.portability_review_extension?.model_selected_context === false &&
    dailyUse.portability_review_extension?.context_origin_class ===
      "external_content" &&
    dailyUse.portability_review_extension?.context_actor_type === "retriever" &&
    dailyUse.portability_review_extension?.context_acquisition_method ===
      "retrieval" &&
    dailyUse.portability_review_extension?.context_authority_class ===
      "untrusted_data" &&
    dailyUse.portability_review_extension?.record_mutation === false &&
    dailyUse.portability_review_extension?.tool_execution === false &&
    dailyUse.portability_review_extension?.capability_execution === false &&
    dailyUse.portability_review_extension?.phase6_gate_complete === false &&
    dailyUse.portability_review_extension?.lite_v1_complete === false &&
    dailyUse.portability_review_extension?.stable_anti_lock_in_claim === false &&
    dailyUse.portability_review_extension?.implementation_doc ===
      "docs/implementation/imp-070-explicit-local-portability-review.md",
  "IMP-070 portability review must remain explicit, linked-only, data-only, and CI-only",
);

expect(
  dailyUse.failure_guidance_extension?.implementation === "IMP-071" &&
    dailyUse.failure_guidance_extension?.status === "ci-pass" &&
    JSON.stringify(dailyUse.failure_guidance_extension?.passed_evidence_levels) ===
      JSON.stringify(["ci"]) &&
    JSON.stringify(dailyUse.failure_guidance_extension?.required_evidence_levels) ===
      JSON.stringify(["ci"]) &&
    dailyUse.failure_guidance_extension?.failure_code_count === 9 &&
    dailyUse.failure_guidance_extension?.guidance_version === 1 &&
    dailyUse.failure_guidance_extension?.canonical_error_event_persistence === true &&
    dailyUse.failure_guidance_extension?.completed_turn_guidance === false &&
    dailyUse.failure_guidance_extension?.state_preserved === true &&
    dailyUse.failure_guidance_extension?.automatic_action_taken === false &&
    dailyUse.failure_guidance_extension?.cloud_fallback_used === false &&
    dailyUse.failure_guidance_extension?.automatic_model_download === false &&
    dailyUse.failure_guidance_extension?.automatic_model_installation === false &&
    dailyUse.failure_guidance_extension?.automatic_binding_change === false &&
    dailyUse.failure_guidance_extension?.process_launch === false &&
    dailyUse.failure_guidance_extension?.shell_execution === false &&
    dailyUse.failure_guidance_extension?.tool_execution === false &&
    dailyUse.failure_guidance_extension?.capability_execution === false &&
    dailyUse.failure_guidance_extension?.destructive_state_mutation === false &&
    dailyUse.failure_guidance_extension?.phase6_gate_complete === false &&
    dailyUse.failure_guidance_extension?.lite_v1_complete === false &&
    dailyUse.failure_guidance_extension?.stable_anti_lock_in_claim === false &&
    dailyUse.failure_guidance_extension?.implementation_doc ===
      "docs/implementation/imp-071-structured-local-failure-guidance.md",
  "IMP-071 failure guidance must remain deterministic, local-only, and CI-only",
);

expect(
  dailyUse.doctor_extension?.implementation === "IMP-072" &&
    dailyUse.doctor_extension?.status === "ci-pass" &&
    JSON.stringify(dailyUse.doctor_extension?.passed_evidence_levels) ===
      JSON.stringify(["ci"]) &&
    JSON.stringify(dailyUse.doctor_extension?.required_evidence_levels) ===
      JSON.stringify(["ci"]) &&
    dailyUse.doctor_extension?.report_schema_version === 1 &&
    dailyUse.doctor_extension?.read_only === true &&
    dailyUse.doctor_extension?.workspace_mutation === false &&
    dailyUse.doctor_extension?.state_mutation === false &&
    dailyUse.doctor_extension?.schema_migration === false &&
    dailyUse.doctor_extension?.automatic_repair === false &&
    dailyUse.doctor_extension?.model_execution === false &&
    dailyUse.doctor_extension?.runtime_start === false &&
    dailyUse.doctor_extension?.process_launch === false &&
    dailyUse.doctor_extension?.shell_execution === false &&
    dailyUse.doctor_extension?.tool_execution === false &&
    dailyUse.doctor_extension?.capability_execution === false &&
    dailyUse.doctor_extension?.network_access === false &&
    dailyUse.doctor_extension?.cloud_fallback === false &&
    dailyUse.doctor_extension?.native_path_disclosure === false &&
    dailyUse.doctor_extension?.phase6_gate_complete === false &&
    dailyUse.doctor_extension?.lite_v1_complete === false &&
    dailyUse.doctor_extension?.stable_anti_lock_in_claim === false &&
    dailyUse.doctor_extension?.implementation_doc ===
      "docs/implementation/imp-072-read-only-doll-doctor.md",
  "IMP-072 doctor must remain deterministic, read-only, local-only, and CI-only",
);

expect(
  dailyUse.local_full_text_search_extension?.implementation === "IMP-073" &&
    dailyUse.local_full_text_search_extension?.status === "ci-pass" &&
    JSON.stringify(
      dailyUse.local_full_text_search_extension?.passed_evidence_levels,
    ) === JSON.stringify(["ci"]) &&
    JSON.stringify(
      dailyUse.local_full_text_search_extension?.required_evidence_levels,
    ) === JSON.stringify(["ci"]) &&
    dailyUse.local_full_text_search_extension?.report_schema_version === 1 &&
    dailyUse.local_full_text_search_extension?.search_mode ===
      "unicode-nfkc-casefold-substring-and" &&
    dailyUse.local_full_text_search_extension?.query_mode === "explicit-only" &&
    JSON.stringify(
      dailyUse.local_full_text_search_extension?.record_status_scope,
    ) === JSON.stringify(["active"]) &&
    dailyUse.local_full_text_search_extension?.secret_records_allowed === false &&
    dailyUse.local_full_text_search_extension?.maximum_scanned_records === 10000 &&
    dailyUse.local_full_text_search_extension?.maximum_results === 100 &&
    dailyUse.local_full_text_search_extension?.persistent_index === false &&
    dailyUse.local_full_text_search_extension?.schema_migration === false &&
    dailyUse.local_full_text_search_extension?.state_mutation === false &&
    dailyUse.local_full_text_search_extension?.workspace_mutation === false &&
    dailyUse.local_full_text_search_extension?.automatic_retrieval === false &&
    dailyUse.local_full_text_search_extension?.semantic_retrieval === false &&
    dailyUse.local_full_text_search_extension?.model_selected_context === false &&
    dailyUse.local_full_text_search_extension?.context_injection === false &&
    dailyUse.local_full_text_search_extension?.model_execution === false &&
    dailyUse.local_full_text_search_extension?.process_launch === false &&
    dailyUse.local_full_text_search_extension?.shell_execution === false &&
    dailyUse.local_full_text_search_extension?.tool_execution === false &&
    dailyUse.local_full_text_search_extension?.capability_execution === false &&
    dailyUse.local_full_text_search_extension?.network_access === false &&
    dailyUse.local_full_text_search_extension?.cloud_fallback === false &&
    dailyUse.local_full_text_search_extension?.phase6_gate_complete === false &&
    dailyUse.local_full_text_search_extension?.lite_v1_complete === false &&
    dailyUse.local_full_text_search_extension?.stable_anti_lock_in_claim === false &&
    dailyUse.local_full_text_search_extension?.implementation_doc ===
      "docs/implementation/imp-073-explicit-local-full-text-search.md",
  "IMP-073 local full-text search must remain explicit, read-only, local-only, and CI-only",
);

expect(
  dailyUse.local_text_markdown_extension?.implementation === "IMP-074" &&
    dailyUse.local_text_markdown_extension?.status === "ci-pass" &&
    JSON.stringify(
      dailyUse.local_text_markdown_extension?.passed_evidence_levels,
    ) === JSON.stringify(["ci"]) &&
    JSON.stringify(
      dailyUse.local_text_markdown_extension?.required_evidence_levels,
    ) === JSON.stringify(["ci"]) &&
    dailyUse.local_text_markdown_extension?.report_schema_version === 1 &&
    dailyUse.local_text_markdown_extension?.selection_mode ===
      "explicit-single-file" &&
    JSON.stringify(dailyUse.local_text_markdown_extension?.allowed_extensions) ===
      JSON.stringify([".txt", ".md", ".markdown"]) &&
    dailyUse.local_text_markdown_extension?.strict_utf8 === true &&
    dailyUse.local_text_markdown_extension?.utf8_bom_handling ===
      "remove-and-report" &&
    dailyUse.local_text_markdown_extension?.maximum_source_bytes === 1048576 &&
    dailyUse.local_text_markdown_extension?.maximum_text_characters === 1000000 &&
    dailyUse.local_text_markdown_extension?.symlinks_allowed === false &&
    dailyUse.local_text_markdown_extension?.source_persisted === false &&
    dailyUse.local_text_markdown_extension?.artifact_created === false &&
    dailyUse.local_text_markdown_extension?.index_created === false &&
    dailyUse.local_text_markdown_extension?.workspace_mutation === false &&
    dailyUse.local_text_markdown_extension?.state_mutation === false &&
    dailyUse.local_text_markdown_extension?.audit_mutation === false &&
    dailyUse.local_text_markdown_extension?.context_injection === false &&
    dailyUse.local_text_markdown_extension?.model_execution === false &&
    dailyUse.local_text_markdown_extension?.runtime_start === false &&
    dailyUse.local_text_markdown_extension?.process_launch === false &&
    dailyUse.local_text_markdown_extension?.shell_execution === false &&
    dailyUse.local_text_markdown_extension?.tool_execution === false &&
    dailyUse.local_text_markdown_extension?.capability_execution === false &&
    dailyUse.local_text_markdown_extension?.network_access === false &&
    dailyUse.local_text_markdown_extension?.cloud_fallback === false &&
    dailyUse.local_text_markdown_extension?.origin_class === "external_content" &&
    dailyUse.local_text_markdown_extension?.actor_type === "extractor" &&
    dailyUse.local_text_markdown_extension?.acquisition_method === "extraction" &&
    dailyUse.local_text_markdown_extension?.authority_class === "untrusted_data" &&
    dailyUse.local_text_markdown_extension?.phase6_gate_complete === false &&
    dailyUse.local_text_markdown_extension?.lite_v1_complete === false &&
    dailyUse.local_text_markdown_extension?.stable_anti_lock_in_claim === false &&
    dailyUse.local_text_markdown_extension?.implementation_doc ===
      "docs/implementation/imp-074-explicit-local-text-markdown-read.md",
  "IMP-074 local text and Markdown reading must remain explicit, untrusted, local-only, and CI-only",
);

expect(
  dailyUse.local_csv_extension?.implementation === "IMP-075" &&
    dailyUse.local_csv_extension?.status === "ci-pass" &&
    JSON.stringify(dailyUse.local_csv_extension?.passed_evidence_levels) ===
      JSON.stringify(["ci"]) &&
    JSON.stringify(dailyUse.local_csv_extension?.required_evidence_levels) ===
      JSON.stringify(["ci"]) &&
    dailyUse.local_csv_extension?.report_schema_version === 1 &&
    dailyUse.local_csv_extension?.selection_mode === "explicit-single-file" &&
    JSON.stringify(dailyUse.local_csv_extension?.allowed_extensions) ===
      JSON.stringify([".csv"]) &&
    JSON.stringify(dailyUse.local_csv_extension?.delimiter_profiles) ===
      JSON.stringify(["comma", "tab", "semicolon", "pipe"]) &&
    dailyUse.local_csv_extension?.strict_utf8 === true &&
    dailyUse.local_csv_extension?.utf8_bom_handling === "remove-and-report" &&
    dailyUse.local_csv_extension?.maximum_source_bytes === 2097152 &&
    dailyUse.local_csv_extension?.maximum_rows === 10000 &&
    dailyUse.local_csv_extension?.maximum_columns === 200 &&
    dailyUse.local_csv_extension?.maximum_cell_characters === 16384 &&
    dailyUse.local_csv_extension?.maximum_aggregate_characters === 4000000 &&
    dailyUse.local_csv_extension?.maximum_preview_rows === 100 &&
    dailyUse.local_csv_extension?.symlinks_allowed === false &&
    JSON.stringify(dailyUse.local_csv_extension?.transformation_operations) ===
      JSON.stringify(["column_selection", "column_reordering", "header_renaming"]) &&
    dailyUse.local_csv_extension?.type_inference === false &&
    dailyUse.local_csv_extension?.formula_evaluation === false &&
    dailyUse.local_csv_extension?.source_overwrite === false &&
    dailyUse.local_csv_extension?.source_persisted === false &&
    dailyUse.local_csv_extension?.output_persisted === false &&
    dailyUse.local_csv_extension?.artifact_created === false &&
    dailyUse.local_csv_extension?.index_created === false &&
    dailyUse.local_csv_extension?.workspace_mutation === false &&
    dailyUse.local_csv_extension?.state_mutation === false &&
    dailyUse.local_csv_extension?.audit_mutation === false &&
    dailyUse.local_csv_extension?.context_injection === false &&
    dailyUse.local_csv_extension?.model_execution === false &&
    dailyUse.local_csv_extension?.runtime_start === false &&
    dailyUse.local_csv_extension?.process_launch === false &&
    dailyUse.local_csv_extension?.shell_execution === false &&
    dailyUse.local_csv_extension?.tool_execution === false &&
    dailyUse.local_csv_extension?.capability_execution === false &&
    dailyUse.local_csv_extension?.network_access === false &&
    dailyUse.local_csv_extension?.cloud_fallback === false &&
    dailyUse.local_csv_extension?.origin_class === "external_content" &&
    dailyUse.local_csv_extension?.actor_type === "extractor" &&
    dailyUse.local_csv_extension?.acquisition_method === "extraction" &&
    dailyUse.local_csv_extension?.authority_class === "untrusted_data" &&
    dailyUse.local_csv_extension?.phase6_gate_complete === false &&
    dailyUse.local_csv_extension?.lite_v1_complete === false &&
    dailyUse.local_csv_extension?.stable_anti_lock_in_claim === false &&
    dailyUse.local_csv_extension?.implementation_doc ===
      "docs/implementation/imp-075-explicit-local-csv.md",
  "IMP-075 local CSV must remain explicit, non-persistent, non-evaluating, and CI-only",
);

expect(
  dailyUse.local_pdf_extension?.implementation === "IMP-076" &&
    dailyUse.local_pdf_extension?.status === "ci-pass" &&
    JSON.stringify(dailyUse.local_pdf_extension?.passed_evidence_levels) ===
      JSON.stringify(["ci"]) &&
    JSON.stringify(dailyUse.local_pdf_extension?.required_evidence_levels) ===
      JSON.stringify(["ci"]) &&
    dailyUse.local_pdf_extension?.report_schema_version === 1 &&
    dailyUse.local_pdf_extension?.selection_mode === "explicit-single-file" &&
    JSON.stringify(dailyUse.local_pdf_extension?.allowed_extensions) ===
      JSON.stringify([".pdf"]) &&
    dailyUse.local_pdf_extension?.adapter_optional === true &&
    dailyUse.local_pdf_extension?.adapter_id === "pypdf" &&
    dailyUse.local_pdf_extension?.adapter_version_range === ">=6.14.2,<7" &&
    dailyUse.local_pdf_extension?.adapter_loading === "invocation-only" &&
    dailyUse.local_pdf_extension?.strict_parsing === true &&
    dailyUse.local_pdf_extension?.maximum_source_bytes === 8388608 &&
    dailyUse.local_pdf_extension?.maximum_document_pages === 200 &&
    dailyUse.local_pdf_extension?.maximum_selected_pages === 100 &&
    dailyUse.local_pdf_extension?.maximum_page_characters === 100000 &&
    dailyUse.local_pdf_extension?.maximum_aggregate_characters === 1000000 &&
    dailyUse.local_pdf_extension?.page_numbering === "one-based" &&
    dailyUse.local_pdf_extension?.caller_order_preserved === true &&
    dailyUse.local_pdf_extension?.symlinks_allowed === false &&
    dailyUse.local_pdf_extension?.encrypted_pdf_allowed === false &&
    dailyUse.local_pdf_extension?.password_entry === false &&
    dailyUse.local_pdf_extension?.ocr_used === false &&
    dailyUse.local_pdf_extension?.image_extraction_used === false &&
    dailyUse.local_pdf_extension?.source_overwrite === false &&
    dailyUse.local_pdf_extension?.source_persisted === false &&
    dailyUse.local_pdf_extension?.output_persisted === false &&
    dailyUse.local_pdf_extension?.artifact_created === false &&
    dailyUse.local_pdf_extension?.index_created === false &&
    dailyUse.local_pdf_extension?.workspace_mutation === false &&
    dailyUse.local_pdf_extension?.state_mutation === false &&
    dailyUse.local_pdf_extension?.audit_mutation === false &&
    dailyUse.local_pdf_extension?.context_injection === false &&
    dailyUse.local_pdf_extension?.model_execution === false &&
    dailyUse.local_pdf_extension?.runtime_start === false &&
    dailyUse.local_pdf_extension?.process_launch === false &&
    dailyUse.local_pdf_extension?.shell_execution === false &&
    dailyUse.local_pdf_extension?.tool_execution === false &&
    dailyUse.local_pdf_extension?.capability_execution === false &&
    dailyUse.local_pdf_extension?.network_access === false &&
    dailyUse.local_pdf_extension?.cloud_fallback === false &&
    dailyUse.local_pdf_extension?.origin_class === "external_content" &&
    dailyUse.local_pdf_extension?.actor_type === "extractor" &&
    dailyUse.local_pdf_extension?.acquisition_method === "extraction" &&
    dailyUse.local_pdf_extension?.authority_class === "untrusted_data" &&
    dailyUse.local_pdf_extension?.phase6_gate_complete === false &&
    dailyUse.local_pdf_extension?.lite_v1_complete === false &&
    dailyUse.local_pdf_extension?.stable_anti_lock_in_claim === false &&
    dailyUse.local_pdf_extension?.implementation_doc ===
      "docs/implementation/imp-076-optional-local-pdf-text-extraction.md",
  "IMP-076 local PDF extraction must remain optional, untrusted, local-only, and CI-only",
);


expect(
  dailyUse.local_ocr_extension?.implementation === "IMP-077" &&
    dailyUse.local_ocr_extension?.status === "ci-pass" &&
    dailyUse.local_ocr_extension?.adapter_optional === true &&
    dailyUse.local_ocr_extension?.adapter_id === "ocrmac-vision" &&
    dailyUse.local_ocr_extension?.adapter_platform === "darwin" &&
    dailyUse.local_ocr_extension?.real_adapter_hosted_ci === true &&
    dailyUse.local_ocr_extension?.primary_intel_mac_real_machine_evidence === false &&
    dailyUse.local_ocr_extension?.process_launch === false &&
    dailyUse.local_ocr_extension?.network_access === false &&
    dailyUse.local_ocr_extension?.cloud_access === false &&
    dailyUse.local_ocr_extension?.automatic_download === false &&
    dailyUse.local_ocr_extension?.authority_class === "untrusted_data" &&
    dailyUse.local_ocr_extension?.phase6_gate_complete === false &&
    dailyUse.local_ocr_extension?.lite_v1_complete === false &&
    dailyUse.local_ocr_extension?.stable_anti_lock_in_claim === false,
  "IMP-077 local image OCR must remain optional, bounded, untrusted, local-only, and CI-only",
);


expect(
  dailyUse.text_markdown_writing_attachment_extension?.implementation === "IMP-078" &&
    dailyUse.text_markdown_writing_attachment_extension?.status === "ci-pass" &&
    JSON.stringify(dailyUse.text_markdown_writing_attachment_extension?.passed_evidence_levels) === JSON.stringify(["ci"]) &&
    JSON.stringify(dailyUse.text_markdown_writing_attachment_extension?.required_evidence_levels) === JSON.stringify(["ci"]) &&
    dailyUse.text_markdown_writing_attachment_extension?.selection_mode === "explicit-single-file" &&
    JSON.stringify(dailyUse.text_markdown_writing_attachment_extension?.allowed_extensions) === JSON.stringify([".txt", ".md", ".markdown"]) &&
    JSON.stringify(dailyUse.text_markdown_writing_attachment_extension?.supported_modes) === JSON.stringify(["revise", "summarize", "translate"]) &&
    dailyUse.text_markdown_writing_attachment_extension?.draft_primary_source_allowed === false &&
    dailyUse.text_markdown_writing_attachment_extension?.exactly_one_primary_source === true &&
    JSON.stringify(dailyUse.text_markdown_writing_attachment_extension?.primary_source_forms) === JSON.stringify(["inline", "document"]) &&
    dailyUse.text_markdown_writing_attachment_extension?.reader_implementation === "IMP-074" &&
    dailyUse.text_markdown_writing_attachment_extension?.maximum_document_source_bytes === 1048576 &&
    dailyUse.text_markdown_writing_attachment_extension?.maximum_writing_source_characters === 16000 &&
    dailyUse.text_markdown_writing_attachment_extension?.strict_utf8 === true &&
    dailyUse.text_markdown_writing_attachment_extension?.utf8_bom_handling === "remove-and-report" &&
    dailyUse.text_markdown_writing_attachment_extension?.symlinks_allowed === false &&
    dailyUse.text_markdown_writing_attachment_extension?.automatic_file_discovery === false &&
    dailyUse.text_markdown_writing_attachment_extension?.directory_traversal === false &&
    dailyUse.text_markdown_writing_attachment_extension?.globbing === false &&
    dailyUse.text_markdown_writing_attachment_extension?.persistent_document_record === false &&
    dailyUse.text_markdown_writing_attachment_extension?.source_record_created === false &&
    dailyUse.text_markdown_writing_attachment_extension?.artifact_created === false &&
    dailyUse.text_markdown_writing_attachment_extension?.persistent_index === false &&
    dailyUse.text_markdown_writing_attachment_extension?.semantic_retrieval === false &&
    dailyUse.text_markdown_writing_attachment_extension?.model_selected_context === false &&
    dailyUse.text_markdown_writing_attachment_extension?.network_access === false &&
    dailyUse.text_markdown_writing_attachment_extension?.cloud_access === false &&
    dailyUse.text_markdown_writing_attachment_extension?.process_launch === false &&
    dailyUse.text_markdown_writing_attachment_extension?.shell_execution === false &&
    dailyUse.text_markdown_writing_attachment_extension?.capability_execution === false &&
    dailyUse.text_markdown_writing_attachment_extension?.origin_class === "external_content" &&
    dailyUse.text_markdown_writing_attachment_extension?.actor_type === "extractor" &&
    dailyUse.text_markdown_writing_attachment_extension?.acquisition_method === "extraction" &&
    dailyUse.text_markdown_writing_attachment_extension?.authority_class === "untrusted_data" &&
    dailyUse.text_markdown_writing_attachment_extension?.phase6_gate_complete === false &&
    dailyUse.text_markdown_writing_attachment_extension?.lite_v1_complete === false &&
    dailyUse.text_markdown_writing_attachment_extension?.stable_anti_lock_in_claim === false &&
    dailyUse.text_markdown_writing_attachment_extension?.implementation_doc === "docs/implementation/imp-078-text-markdown-writing-attachments.md",
  "IMP-078 text/Markdown writing attachments must remain explicit, untrusted, local-only, and CI-only",
);


expect(
  dailyUse.pdf_writing_attachment_extension?.implementation === "IMP-079" &&
    dailyUse.pdf_writing_attachment_extension?.status === "ci-pass" &&
    JSON.stringify(dailyUse.pdf_writing_attachment_extension?.passed_evidence_levels) === JSON.stringify(["ci"]) &&
    JSON.stringify(dailyUse.pdf_writing_attachment_extension?.required_evidence_levels) === JSON.stringify(["ci"]) &&
    dailyUse.pdf_writing_attachment_extension?.selection_mode === "explicit-single-file" &&
    JSON.stringify(dailyUse.pdf_writing_attachment_extension?.allowed_extensions) === JSON.stringify([".pdf"]) &&
    JSON.stringify(dailyUse.pdf_writing_attachment_extension?.supported_modes) === JSON.stringify(["revise", "summarize", "translate"]) &&
    dailyUse.pdf_writing_attachment_extension?.draft_primary_source_allowed === false &&
    dailyUse.pdf_writing_attachment_extension?.exactly_one_primary_source === true &&
    JSON.stringify(dailyUse.pdf_writing_attachment_extension?.primary_source_forms) === JSON.stringify(["inline", "document", "pdf"]) &&
    dailyUse.pdf_writing_attachment_extension?.reader_implementation === "IMP-076" &&
    dailyUse.pdf_writing_attachment_extension?.adapter_optional === true &&
    dailyUse.pdf_writing_attachment_extension?.adapter_id === "pypdf" &&
    dailyUse.pdf_writing_attachment_extension?.adapter_loading === "invocation-only" &&
    dailyUse.pdf_writing_attachment_extension?.page_numbering === "one-based" &&
    dailyUse.pdf_writing_attachment_extension?.caller_order_preserved === true &&
    dailyUse.pdf_writing_attachment_extension?.page_join_separator === "\\n\\n" &&
    dailyUse.pdf_writing_attachment_extension?.maximum_pdf_source_bytes === 8388608 &&
    dailyUse.pdf_writing_attachment_extension?.maximum_document_pages === 200 &&
    dailyUse.pdf_writing_attachment_extension?.maximum_selected_pages === 100 &&
    dailyUse.pdf_writing_attachment_extension?.maximum_pdf_page_characters === 100000 &&
    dailyUse.pdf_writing_attachment_extension?.maximum_pdf_aggregate_characters === 1000000 &&
    dailyUse.pdf_writing_attachment_extension?.maximum_writing_source_characters === 16000 &&
    dailyUse.pdf_writing_attachment_extension?.encrypted_pdf_allowed === false &&
    dailyUse.pdf_writing_attachment_extension?.ocr_used === false &&
    dailyUse.pdf_writing_attachment_extension?.symlinks_allowed === false &&
    dailyUse.pdf_writing_attachment_extension?.automatic_file_discovery === false &&
    dailyUse.pdf_writing_attachment_extension?.persistent_document_record === false &&
    dailyUse.pdf_writing_attachment_extension?.source_record_created === false &&
    dailyUse.pdf_writing_attachment_extension?.artifact_created === false &&
    dailyUse.pdf_writing_attachment_extension?.persistent_index === false &&
    dailyUse.pdf_writing_attachment_extension?.semantic_retrieval === false &&
    dailyUse.pdf_writing_attachment_extension?.model_selected_context === false &&
    dailyUse.pdf_writing_attachment_extension?.network_access === false &&
    dailyUse.pdf_writing_attachment_extension?.cloud_access === false &&
    dailyUse.pdf_writing_attachment_extension?.process_launch === false &&
    dailyUse.pdf_writing_attachment_extension?.shell_execution === false &&
    dailyUse.pdf_writing_attachment_extension?.capability_execution === false &&
    dailyUse.pdf_writing_attachment_extension?.origin_class === "external_content" &&
    dailyUse.pdf_writing_attachment_extension?.actor_type === "extractor" &&
    dailyUse.pdf_writing_attachment_extension?.acquisition_method === "extraction" &&
    dailyUse.pdf_writing_attachment_extension?.authority_class === "untrusted_data" &&
    dailyUse.pdf_writing_attachment_extension?.phase6_gate_complete === false &&
    dailyUse.pdf_writing_attachment_extension?.lite_v1_complete === false &&
    dailyUse.pdf_writing_attachment_extension?.stable_anti_lock_in_claim === false &&
    dailyUse.pdf_writing_attachment_extension?.implementation_doc === "docs/implementation/imp-079-pdf-writing-attachment.md",
  "IMP-079 PDF writing attachment must remain explicit, bounded, untrusted, local-only, and CI-only",
);


expect(
  dailyUse.ocr_image_writing_attachment_extension?.implementation === "IMP-080" &&
    dailyUse.ocr_image_writing_attachment_extension?.status === "ci-pass" &&
    JSON.stringify(dailyUse.ocr_image_writing_attachment_extension?.passed_evidence_levels) === JSON.stringify(["ci"]) &&
    JSON.stringify(dailyUse.ocr_image_writing_attachment_extension?.required_evidence_levels) === JSON.stringify(["ci"]) &&
    dailyUse.ocr_image_writing_attachment_extension?.selection_mode === "explicit-single-file" &&
    JSON.stringify(dailyUse.ocr_image_writing_attachment_extension?.allowed_extensions) === JSON.stringify([".png", ".jpg", ".jpeg"]) &&
    JSON.stringify(dailyUse.ocr_image_writing_attachment_extension?.supported_modes) === JSON.stringify(["revise", "summarize", "translate"]) &&
    dailyUse.ocr_image_writing_attachment_extension?.draft_primary_source_allowed === false &&
    dailyUse.ocr_image_writing_attachment_extension?.exactly_one_primary_source === true &&
    JSON.stringify(dailyUse.ocr_image_writing_attachment_extension?.primary_source_forms) === JSON.stringify(["inline", "document", "pdf", "ocr"]) &&
    dailyUse.ocr_image_writing_attachment_extension?.reader_implementation === "IMP-077" &&
    dailyUse.ocr_image_writing_attachment_extension?.adapter_optional === true &&
    dailyUse.ocr_image_writing_attachment_extension?.adapter_id === "ocrmac-vision" &&
    dailyUse.ocr_image_writing_attachment_extension?.adapter_loading === "invocation-only" &&
    dailyUse.ocr_image_writing_attachment_extension?.adapter_platform === "darwin" &&
    dailyUse.ocr_image_writing_attachment_extension?.real_adapter_hosted_ci === true &&
    dailyUse.ocr_image_writing_attachment_extension?.primary_intel_mac_real_machine_evidence === false &&
    dailyUse.ocr_image_writing_attachment_extension?.line_order_preserved === true &&
    dailyUse.ocr_image_writing_attachment_extension?.line_join_separator === "\\n" &&
    dailyUse.ocr_image_writing_attachment_extension?.maximum_source_bytes === 8388608 &&
    dailyUse.ocr_image_writing_attachment_extension?.maximum_image_width === 10000 &&
    dailyUse.ocr_image_writing_attachment_extension?.maximum_image_height === 10000 &&
    dailyUse.ocr_image_writing_attachment_extension?.maximum_image_pixels === 25000000 &&
    dailyUse.ocr_image_writing_attachment_extension?.maximum_recognized_lines === 1000 &&
    dailyUse.ocr_image_writing_attachment_extension?.maximum_line_characters === 20000 &&
    dailyUse.ocr_image_writing_attachment_extension?.maximum_ocr_aggregate_characters === 200000 &&
    dailyUse.ocr_image_writing_attachment_extension?.maximum_writing_source_characters === 16000 &&
    dailyUse.ocr_image_writing_attachment_extension?.symlinks_allowed === false &&
    dailyUse.ocr_image_writing_attachment_extension?.automatic_file_discovery === false &&
    dailyUse.ocr_image_writing_attachment_extension?.persistent_document_record === false &&
    dailyUse.ocr_image_writing_attachment_extension?.source_record_created === false &&
    dailyUse.ocr_image_writing_attachment_extension?.artifact_created === false &&
    dailyUse.ocr_image_writing_attachment_extension?.persistent_index === false &&
    dailyUse.ocr_image_writing_attachment_extension?.semantic_retrieval === false &&
    dailyUse.ocr_image_writing_attachment_extension?.model_selected_context === false &&
    dailyUse.ocr_image_writing_attachment_extension?.network_access === false &&
    dailyUse.ocr_image_writing_attachment_extension?.cloud_access === false &&
    dailyUse.ocr_image_writing_attachment_extension?.process_launch === false &&
    dailyUse.ocr_image_writing_attachment_extension?.shell_execution === false &&
    dailyUse.ocr_image_writing_attachment_extension?.capability_execution === false &&
    dailyUse.ocr_image_writing_attachment_extension?.origin_class === "external_content" &&
    dailyUse.ocr_image_writing_attachment_extension?.actor_type === "extractor" &&
    dailyUse.ocr_image_writing_attachment_extension?.acquisition_method === "ocr" &&
    dailyUse.ocr_image_writing_attachment_extension?.authority_class === "untrusted_data" &&
    dailyUse.ocr_image_writing_attachment_extension?.phase6_gate_complete === false &&
    dailyUse.ocr_image_writing_attachment_extension?.lite_v1_complete === false &&
    dailyUse.ocr_image_writing_attachment_extension?.stable_anti_lock_in_claim === false &&
    dailyUse.ocr_image_writing_attachment_extension?.implementation_doc === "docs/implementation/imp-080-ocr-image-writing-attachment.md",
  "IMP-080 OCR image writing attachment must remain explicit, bounded, untrusted, local-only, and CI-only",
);

expect(
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

expect(
  dailyUse.multiple_writing_attachment_extension?.implementation === "IMP-082" &&
    dailyUse.multiple_writing_attachment_extension?.status === "ci-pass" &&
    JSON.stringify(dailyUse.multiple_writing_attachment_extension?.passed_evidence_levels) === JSON.stringify(["ci"]) &&
    JSON.stringify(dailyUse.multiple_writing_attachment_extension?.required_evidence_levels) === JSON.stringify(["ci"]) &&
    dailyUse.multiple_writing_attachment_extension?.selection_mode === "explicit-ordered-multiple-files" &&
    dailyUse.multiple_writing_attachment_extension?.minimum_attachments === 2 &&
    dailyUse.multiple_writing_attachment_extension?.maximum_attachments === 4 &&
    JSON.stringify(dailyUse.multiple_writing_attachment_extension?.supported_attachment_kinds) === JSON.stringify(["document", "pdf", "ocr", "csv"]) &&
    JSON.stringify(dailyUse.multiple_writing_attachment_extension?.supported_modes) === JSON.stringify(["revise", "summarize", "translate"]) &&
    dailyUse.multiple_writing_attachment_extension?.draft_attachments_allowed === false &&
    dailyUse.multiple_writing_attachment_extension?.caller_order_preserved === true &&
    dailyUse.multiple_writing_attachment_extension?.legacy_primary_source_mixing_allowed === false &&
    dailyUse.multiple_writing_attachment_extension?.maximum_aggregate_writing_source_characters === 16000 &&
    dailyUse.multiple_writing_attachment_extension?.target_preflight_before_attachment_read === true &&
    dailyUse.multiple_writing_attachment_extension?.all_attachments_prepared_before_origin_creation === true &&
    dailyUse.multiple_writing_attachment_extension?.all_source_operation_ids_preflighted_before_origin_creation === true &&
    dailyUse.multiple_writing_attachment_extension?.one_instruction_origin_per_attachment === true &&
    dailyUse.multiple_writing_attachment_extension?.source_specific_boundaries?.document === "IMP-074" &&
    dailyUse.multiple_writing_attachment_extension?.source_specific_boundaries?.csv === "IMP-075" &&
    dailyUse.multiple_writing_attachment_extension?.source_specific_boundaries?.pdf === "IMP-076" &&
    dailyUse.multiple_writing_attachment_extension?.source_specific_boundaries?.ocr === "IMP-077" &&
    dailyUse.multiple_writing_attachment_extension?.origin_class === "external_content" &&
    dailyUse.multiple_writing_attachment_extension?.actor_type === "extractor" &&
    dailyUse.multiple_writing_attachment_extension?.authority_class === "untrusted_data" &&
    dailyUse.multiple_writing_attachment_extension?.data_only === true &&
    dailyUse.multiple_writing_attachment_extension?.per_source_acquisition_method_preserved === true &&
    dailyUse.multiple_writing_attachment_extension?.automatic_file_discovery === false &&
    dailyUse.multiple_writing_attachment_extension?.directory_traversal === false &&
    dailyUse.multiple_writing_attachment_extension?.globbing === false &&
    dailyUse.multiple_writing_attachment_extension?.attachment_persistence === false &&
    dailyUse.multiple_writing_attachment_extension?.source_record_created === false &&
    dailyUse.multiple_writing_attachment_extension?.artifact_created === false &&
    dailyUse.multiple_writing_attachment_extension?.persistent_index === false &&
    dailyUse.multiple_writing_attachment_extension?.semantic_retrieval === false &&
    dailyUse.multiple_writing_attachment_extension?.model_selected_context === false &&
    dailyUse.multiple_writing_attachment_extension?.network_access === false &&
    dailyUse.multiple_writing_attachment_extension?.cloud_access === false &&
    dailyUse.multiple_writing_attachment_extension?.process_launch === false &&
    dailyUse.multiple_writing_attachment_extension?.shell_execution === false &&
    dailyUse.multiple_writing_attachment_extension?.capability_execution === false &&
    dailyUse.multiple_writing_attachment_extension?.primary_intel_mac_real_machine_evidence === false &&
    dailyUse.multiple_writing_attachment_extension?.phase6_gate_complete === false &&
    dailyUse.multiple_writing_attachment_extension?.lite_v1_complete === false &&
    dailyUse.multiple_writing_attachment_extension?.stable_anti_lock_in_claim === false &&
    dailyUse.multiple_writing_attachment_extension?.implementation_doc === "docs/implementation/imp-082-multiple-writing-attachments.md",
  "IMP-082 multiple writing attachments must remain explicit, ordered, atomic-before-origin, untrusted, local-only, and CI-only",
);

expect(
  dailyUse.lite_client_resource_measurement?.implementation === "IMP-083" &&
    dailyUse.lite_client_resource_measurement?.status === "ci-pass" &&
    JSON.stringify(dailyUse.lite_client_resource_measurement?.passed_evidence_levels) === JSON.stringify(["ci"]) &&
    JSON.stringify(dailyUse.lite_client_resource_measurement?.required_evidence_levels) === JSON.stringify(["ci"]) &&
    dailyUse.lite_client_resource_measurement?.measurement_scope === "doll-lite-client-only" &&
    dailyUse.lite_client_resource_measurement?.measurement_schema_version === 1 &&
    JSON.stringify(dailyUse.lite_client_resource_measurement?.workload_steps) === JSON.stringify(["workspace_initialize", "state_initialize", "workspace_load", "state_read_only_open", "doctor_read_only"]) &&
    dailyUse.lite_client_resource_measurement?.monotonic_duration_measurement === true &&
    dailyUse.lite_client_resource_measurement?.workspace_disk_measurement === true &&
    dailyUse.lite_client_resource_measurement?.workspace_entry_limit === 20000 &&
    dailyUse.lite_client_resource_measurement?.workspace_depth_limit === 32 &&
    dailyUse.lite_client_resource_measurement?.workspace_root_symlink_allowed === false &&
    dailyUse.lite_client_resource_measurement?.workspace_inner_symlinks_allowed === false &&
    dailyUse.lite_client_resource_measurement?.exact_commit_required === true &&
    dailyUse.lite_client_resource_measurement?.tracked_index_must_match_head === true &&
    dailyUse.lite_client_resource_measurement?.tracked_worktree_must_match_index === true &&
    dailyUse.lite_client_resource_measurement?.untracked_evidence_output_allowed === true &&
    dailyUse.lite_client_resource_measurement?.measured_workload_network_access === false &&
    dailyUse.lite_client_resource_measurement?.measured_workload_process_launch === false &&
    dailyUse.lite_client_resource_measurement?.external_runtime_memory_measured === false &&
    dailyUse.lite_client_resource_measurement?.model_memory_measured === false &&
    dailyUse.lite_client_resource_measurement?.performance_thresholds_defined === false &&
    dailyUse.lite_client_resource_measurement?.primary_intel_mac_real_machine_evidence === false &&
    dailyUse.lite_client_resource_measurement?.phase6_gate_complete === false &&
    dailyUse.lite_client_resource_measurement?.lite_v1_complete === false &&
    dailyUse.lite_client_resource_measurement?.stable_anti_lock_in_claim === false &&
    dailyUse.lite_client_resource_measurement?.implementation_doc === "docs/implementation/imp-083-lite-client-resource-measurement.md" &&
    dailyUse.lite_client_resource_measurement?.runbook === "docs/testing/imp-083-primary-intel-mac-runbook.md",
  "IMP-083 Lite client resource measurement must remain client-only, bounded, exact-checkout guarded, CI-only, threshold-free, and non-claiming",
);

expect(
  localWritingPrimary.test_id === "IMP-064-LOCAL-WRITING-PRIMARY" &&
    localWritingPrimary.result === "pass" &&
    localWritingPrimary.evidence_level === "real-machine" &&
    localWritingPrimary.commit_sha ===
      "d40ba32e87f6d211b05e9da1e1f51974ec6fc369" &&
    localWritingPrimary.operating_system === "Darwin" &&
    localWritingPrimary.architecture === "x86_64" &&
    localWritingPrimary.network_mode === "offline-confirmed" &&
    localWritingPrimary.real_runtime_used === true &&
    localWritingPrimary.external_network_request_used === false &&
    localWritingPrimary.cloud_credentials_used === false &&
    localWritingPrimary.model_download_used === false &&
    localWritingPrimary.runtime_installation_used === false &&
    localWritingPrimary.process_launch_used === false &&
    localWritingPrimary.tool_execution_used === false &&
    localWritingPrimary.capability_execution_used === false &&
    localWritingPrimary.writing_workflow_real_machine_gate === "pass" &&
    localWritingPrimary.local_writing_workflow_complete === true &&
    localWritingPrimary.phase6_gate_complete === false &&
    localWritingPrimary.stable_anti_lock_in_claim === false &&
    localWritingPrimary.evidence?.workflow_mode_count === 3 &&
    localWritingPrimary.evidence?.completed_workflow_count === 3 &&
    localWritingPrimary.evidence?.target_event_count === 9 &&
    localWritingPrimary.evidence?.runtime_request_count === 11 &&
    localWritingPrimary.evidence?.allowed_loopback_socket_attempts === 11 &&
    localWritingPrimary.evidence?.rejected_socket_attempts === 0 &&
    localWritingPrimary.evidence?.authority_record_count === 0 &&
    Object.values(localWritingPrimary.checks || {}).every(
      (value) => value === true,
    ) &&
    Object.values(localWritingPrimary.privacy || {}).every(
      (value) => value === false,
    ),
  "accepted IMP-064 primary evidence must remain bounded, offline, and privacy-safe",
);

expect(
  importedReplayPrimary.test_id ===
    "IMP-062-IMPORTED-CONTEXT-REPLAY-PRIMARY" &&
    importedReplayPrimary.result === "pass" &&
    importedReplayPrimary.evidence_level === "real-machine" &&
    importedReplayPrimary.commit_sha ===
      "65f3b5e9ac8c9961c7ec2a152dfdfbb637386e93" &&
    importedReplayPrimary.operating_system === "Darwin" &&
    importedReplayPrimary.architecture === "x86_64" &&
    importedReplayPrimary.network_mode === "offline-confirmed" &&
    importedReplayPrimary.real_runtime_used === true &&
    importedReplayPrimary.external_network_request_used === false &&
    importedReplayPrimary.cloud_credentials_used === false &&
    importedReplayPrimary.model_download_used === false &&
    importedReplayPrimary.runtime_installation_used === false &&
    importedReplayPrimary.process_launch_used === false &&
    importedReplayPrimary.tool_execution_used === false &&
    importedReplayPrimary.capability_execution_used === false &&
    importedReplayPrimary.context_replay_extension_complete === true &&
    importedReplayPrimary.phase6_gate_complete === false &&
    importedReplayPrimary.stable_anti_lock_in_claim === false &&
    Object.values(importedReplayPrimary.checks || {}).every(
      (value) => value === true,
    ) &&
    Object.values(importedReplayPrimary.privacy || {}).every(
      (value) => value === false,
    ),
  "accepted IMP-062 primary evidence must remain bounded, offline, and privacy-safe",
);

expect(
  shutdownEscape.implementation === "IMP-058" &&
    shutdownEscape.shutdown_escape_gate_complete === true &&
    shutdownEscape.accepted_real_machine_result ===
      "docs/testing/results/IMP-058-primary-intel-mac-2026-07-03.json" &&
    shutdownEscape.portability_tests?.length === 1 &&
    shutdownEscape.portability_tests[0]?.id === "PORT-015" &&
    shutdownEscape.portability_tests[0]?.status === "pass" &&
    shutdownEscape.portability_tests[0]?.passed_evidence_levels?.includes("ci") &&
    shutdownEscape.portability_tests[0]?.passed_evidence_levels?.includes("real-machine") &&
    shutdownEscape.real_machine_gate?.status === "pass" &&
    shutdownEscape.real_machine_gate?.commit_sha ===
      "bd06897c46b6fcb6dd3789195e8bdd0bfa54941b",
  "IMP-058 shutdown escape matrix must bind accepted primary-machine evidence",
);
expect(
  chatgptHistory.implementation === "IMP-060" &&
    chatgptHistory.port014_foundation_complete === true &&
    chatgptHistory.chatgpt_history_gate_complete === true &&
    chatgptHistory.accepted_private_manual_result ===
      "docs/testing/results/IMP-060-project-owner-chatgpt-2026-07-10.json" &&
    chatgptHistory.portability_tests?.length === 1 &&
    chatgptHistory.portability_tests[0]?.id === "PORT-014" &&
    chatgptHistory.portability_tests[0]?.status === "pass" &&
    chatgptHistory.portability_tests[0]?.passed_evidence_levels?.includes("ci") &&
    chatgptHistory.portability_tests[0]?.passed_evidence_levels?.includes(
      "private-manual",
    ) &&
    chatgptHistory.private_manual_gate?.status === "pass" &&
    chatgptHistory.private_manual_gate?.commit_sha ===
      "7e93adcd059af8aebab880bd42bcddc96c50778f",
  "IMP-060 ChatGPT history matrix must bind accepted PORT-014 private evidence",
);

expect(
  chatgptPrivate.test_id ===
    "IMP-060-CHATGPT-NUMBERED-PRIVATE-MANUAL" &&
    chatgptPrivate.result === "pass" &&
    chatgptPrivate.mode === "complete" &&
    chatgptPrivate.evidence_level === "private-manual" &&
    chatgptPrivate.commit_sha ===
      "7e93adcd059af8aebab880bd42bcddc96c50778f" &&
    chatgptPrivate.external_network_request_used === false &&
    chatgptPrivate.cloud_credentials_used === false &&
    chatgptPrivate.model_execution_used === false &&
    chatgptPrivate.phase6_gate_complete === false &&
    chatgptPrivate.stable_anti_lock_in_claim === false &&
    Object.values(chatgptPrivate.checks || {}).every(
      (value) => value === true,
    ) &&
    Object.values(chatgptPrivate.privacy || {}).every(
      (value) => value === false,
    ),
  "accepted IMP-060 private evidence must remain bounded, offline, and privacy-safe",
);

const readme = read("README.md");
const roadmap = read("docs/spec/09-development-roadmap.md");
const index = read("website/index.html");
const statusClient = read("website/status.js");
const activityCore = read("website/project-status-core.mjs");
const middleware = read("website/functions/_middleware.js");
const activityApi = read("website/functions/api/project-status.js");
const manifest = JSON.parse(read("website/site.webmanifest"));
const llms = read("website/llms.txt");
const ai = read("website/ai.txt");

for (const required of [
  "data-project-maturity",
  "data-project-phase",
  "data-project-runtime",
  'id="project-primary-label"',
  'id="project-primary"',
  'id="development-primary-label"',
  'id="development-primary"',
  'id="development-up-next-section"',
  'id="development-up-next"',
  'id="development-log"',
  'data-roadmap-phase="3"',
  'data-roadmap-phase="4A"',
  'data-roadmap-phase="4B"',
  'data-roadmap-phase="5"',
  'data-roadmap-phase="6"',
  "data-roadmap-state",
  'src="./status.js"',
]) {
  expect(index.includes(required), `website/index.html is missing ${required}`);
}

for (const forbidden of [
  'id="project-last-completed"',
  'id="project-next"',
  'id="development-last-completed"',
  'id="development-next"',
]) {
  expect(!index.includes(forbidden), `website/index.html still contains ${forbidden}`);
}

for (const publicDocument of [index, readme]) {
  expect(
    !/IMP-\d+\s+is\s+next/i.test(publicDocument),
    "public documentation contains a hard-coded next implementation phrase",
  );
}

for (const statusUrl of [
  "https://doll.badjoke-lab.com/project-status.json",
  "https://doll.badjoke-lab.com/api/project-status",
]) {
  expect(readme.includes(statusUrl), `README.md must reference ${statusUrl}`);
}

expect(!index.includes("devlog.js"), "website/index.html still references devlog.js");
expect(
  activityApi.includes('from "../../project-status-core.mjs"'),
  "activity API must use the tested project-status core",
);
expect(
  activityApi.includes("__doll-public-project-status-v4"),
  "activity API cache key must reflect the current response semantics",
);
expect(
  statusClient.includes('active ? "Current" : "Latest completed"'),
  "status client must switch between Current and Latest completed",
);
expect(
  statusClient.includes("section.hidden = !next"),
  "status client must hide Up next when no real issue exists",
);
expect(
  !activityCore.includes("not opened yet") && !activityCore.includes("plannedEntry"),
  "activity core must not synthesize unopened implementations",
);
expect(
  roadmap.includes("new implementation identifiers increase monotonically from IMP-030 onward"),
  "roadmap must define monotonic implementation numbering",
);
expect(
  roadmap.includes("unused legacy reservations IMP-024 through IMP-029 are retired permanently"),
  "roadmap must retire IMP-024 through IMP-029",
);
expect(
  roadmap.includes("Phase 4A gate status: passed on 2026-06-25."),
  "roadmap must record the accepted Phase 4A gate",
);
expect(
  roadmap.includes("Phase 4B gate status: passed on 2026-06-26."),
  "roadmap must record the accepted Phase 4B gate",
);
expect(
  roadmap.includes("### IMP-048 — Runtime adapter contract"),
  "roadmap must record the IMP-048 runtime adapter contract",
);
expect(
  roadmap.includes("### IMP-049 — First local Ollama runtime adapter"),
  "roadmap must record the IMP-049 Ollama adapter",
);
expect(
  roadmap.includes("### IMP-050 — Model manifests and explicit bindings"),
  "roadmap must record the IMP-050 authoritative manifest foundation",
);
expect(
  roadmap.includes("### IMP-051 — Canonical local conversation execution"),
  "roadmap must record the IMP-051 canonical local conversation path",
);
expect(
  roadmap.includes("### IMP-052 — Explicit model switching and fallback rollback"),
  "roadmap must record the IMP-052 explicit model-switch boundary",
);
expect(
  roadmap.includes("### IMP-053 — Bounded local streaming conversation path"),
  "roadmap must record the IMP-053 bounded streaming boundary",
);
expect(
  roadmap.includes("### IMP-054 — Network-disabled real-runtime continuity drill"),
  "roadmap must record the IMP-054 local-runtime continuity harness",
);
expect(
  roadmap.includes("Phase 5 gate status: passed on 2026-06-28."),
  "roadmap must record the accepted Phase 5 gate",
);
expect(
  roadmap.includes("### IMP-055 — Offline Ollama API session source adapter"),
  "roadmap must record the IMP-055 Ollama session source adapter",
);
expect(
  roadmap.includes("### IMP-056 — Explicit loopback Ollama chat session capture"),
  "roadmap must record the IMP-056 explicit local capture path",
);
expect(
  roadmap.includes("### IMP-057 — Local-portability migration harness"),
  "roadmap must record the IMP-057 local-portability harness",
);
expect(
  roadmap.includes("### IMP-058 — Deterministic Doll shutdown escape bundle"),
  "roadmap must record the IMP-058 shutdown escape bundle",
);
expect(
  roadmap.includes("### IMP-059 — Bounded ChatGPT conversations.json source adapter"),
  "roadmap must record the IMP-059 ChatGPT conversations.json source adapter",
);
expect(
  roadmap.includes("### IMP-060 — Bounded ChatGPT numbered conversation-file aggregation"),
  "roadmap must record the IMP-060 numbered conversation aggregation boundary",
);
expect(
  roadmap.includes("### IMP-061 — Bounded imported conversation context replay"),
  "roadmap must record the IMP-061 imported context replay boundary",
);
expect(
  roadmap.includes("### IMP-062 — Primary Intel Mac imported-context replay acceptance"),
  "roadmap must record the IMP-062 real-machine acceptance boundary",
);
expect(
  roadmap.includes("### IMP-063 — Bounded local writing workflow"),
  "roadmap must record the IMP-063 local writing workflow boundary",
);
expect(
  roadmap.includes("### IMP-064 — Primary Intel Mac local-writing acceptance"),
  "roadmap must record the IMP-064 local writing acceptance boundary",
);
expect(
  roadmap.includes("### IMP-065 — Explicit memory and project context selection"),
  "roadmap must record the IMP-065 explicit writing context boundary",
);
expect(
  roadmap.includes("### IMP-066 — Explicit decision context selection"),
  "roadmap must record the IMP-066 explicit decision context boundary",
);
expect(
  roadmap.includes("### IMP-067 — Explicit Resume Bundle writing context"),
  "roadmap must record the IMP-067 Resume Bundle writing context boundary",
);
expect(
  roadmap.includes("### IMP-069 — Local work-item proposal workflow"),
  "roadmap must record the IMP-069 work-item proposal boundary",
);
expect(
  roadmap.includes("### IMP-070 — Explicit local portability review workflow"),
  "roadmap must record the IMP-070 portability review boundary",
);
expect(
  roadmap.includes("### IMP-071 — Structured local runtime failure guidance"),
  "roadmap must record the IMP-071 failure-guidance boundary",
);
expect(
  roadmap.includes("### IMP-072 — Read-only doll doctor diagnostics"),
  "roadmap must record the IMP-072 doctor boundary",
);
expect(
  roadmap.includes("### IMP-073 — Explicit local full-text state search"),
  "roadmap must record the IMP-073 local-search boundary",
);
expect(
  roadmap.includes("### IMP-074 — Explicit local text and Markdown reading"),
  "roadmap must record the IMP-074 local-document boundary",
);
expect(
  roadmap.includes("### IMP-075 — Explicit local CSV inspection and transformation"),
  "roadmap must record the IMP-075 local-CSV boundary",
);
expect(
  roadmap.includes("### IMP-076 — Optional local PDF text extraction adapter"),
  "roadmap must record the IMP-076 local-PDF boundary",
);
expect(
  roadmap.includes("### IMP-077 — Optional local image OCR adapter") &&
    roadmap.includes("### IMP-078 — Explicit text and Markdown writing attachments") &&
    roadmap.includes("### IMP-079 — Explicit PDF writing attachment") &&
    roadmap.includes("### IMP-080 — Explicit OCR image writing attachment") &&
    roadmap.includes("### IMP-081 — Explicit CSV writing attachment") &&
    roadmap.includes("### IMP-082 — Explicit multiple writing attachments") &&
    roadmap.includes("### IMP-083 — Lite client resource measurement harness") &&
    roadmap.includes("IMP-083 is assigned to Issue #249") &&
    roadmap.includes("the next bounded implementation receives IMP-084 only when a new implementation issue is opened"),
  "roadmap must bind IMP-083 to Issue #249 and identify IMP-084 as the next unallocated implementation identifier",
);
expect(
  roadmap.includes("docs/testing/results/IMP-057-primary-intel-mac-2026-06-29.json"),
  "roadmap must bind the accepted IMP-057 primary Intel Mac evidence",
);
expect(
  roadmap.includes("docs/testing/results/IMP-058-primary-intel-mac-2026-07-03.json"),
  "roadmap must bind the accepted IMP-058 primary Intel Mac evidence",
);
expect(
  roadmap.includes(
    "After IMP-067 explicit Resume Bundle writing context, the immediate order is:",
  ),
  "roadmap must record IMP-067 and remaining Phase 6 work",
);
expect(
  !roadmap.includes("### IMP-024 —") && !roadmap.includes("### IMP-029 —"),
  "roadmap must not keep retired Phase 5 reservations as active headings",
);
expect(
  readme.includes("IMP-024 through IMP-029 are retired"),
  "README must explain retired implementation identifiers",
);

expect(!middleware.includes("doll-logo.svg"), "middleware still advertises the SVG favicon");
expect(
  middleware.includes('rel="icon" type="image/png"'),
  "middleware does not advertise a PNG favicon",
);
expect(
  Array.isArray(manifest.icons) && manifest.icons.length > 0,
  "site.webmanifest requires at least one icon",
);
if (Array.isArray(manifest.icons)) {
  expect(
    manifest.icons.every((icon) => icon.type === "image/png"),
    "site.webmanifest must contain PNG icons only",
  );
}

for (const machineFile of [llms, ai]) {
  expect(
    machineFile.includes("https://doll.badjoke-lab.com/project-status.json"),
    "machine-readable discovery files must reference project-status.json",
  );
  expect(
    machineFile.includes("https://doll.badjoke-lab.com/api/project-status"),
    "machine-readable discovery files must reference the live activity API",
  );
}

const closedPulls = [
  {
    number: 121,
    title: "Complete Phase 4A portability gate",
    html_url: "https://example.invalid/pr/121",
    updated_at: "2026-06-25T15:00:00Z",
    merged_at: "2026-06-25T15:00:00Z",
  },
  {
    number: 120,
    title: "IMP-037: add Phase 4A portability acceptance evidence",
    html_url: "https://example.invalid/pr/120",
    updated_at: "2026-06-25T14:00:00Z",
    merged_at: "2026-06-25T14:00:00Z",
  },
  {
    number: 118,
    title: "IMP-036: add reviewed generic import publication",
    html_url: "https://example.invalid/pr/118",
    updated_at: "2026-06-24T15:00:00Z",
    merged_at: "2026-06-24T15:00:00Z",
  },
  {
    number: 116,
    title: "IMP-035: add deterministic generic export",
    html_url: "https://example.invalid/pr/116",
    updated_at: "2026-06-24T14:00:00Z",
    merged_at: "2026-06-24T14:00:00Z",
  },
  {
    number: 72,
    title: "WEB-007: Publish an article",
    html_url: "https://example.invalid/pr/72",
    updated_at: "2026-06-24T00:00:00Z",
    merged_at: "2026-06-24T00:00:00Z",
  },
];

const idleActivity = buildProjectActivity({ closedPulls });
expect(idleActivity.schema_version === 2, "activity schema must be version 2");
expect(idleActivity.latest_merged_implementation === 37, "latest merged implementation must be IMP-037");
expect(idleActivity.current === null, "idle fixture must have no current implementation");
expect(idleActivity.last_completed?.implementation === 37, "last completed must be IMP-037");
expect(idleActivity.next === null, "idle fixture must not publish a synthetic next implementation");
expect(
  idleActivity.numbering_policy.next_planned_implementation === 38,
  "idle fixture must retain IMP-038 as machine-readable planning metadata",
);
expect(
  JSON.stringify(idleActivity.recent.map((entry) => entry.title)) ===
    JSON.stringify([
      "Complete Phase 4A portability gate",
      "IMP-037: add Phase 4A portability acceptance evidence",
      "IMP-036: add reviewed generic import publication",
    ]),
  "recent development must show Phase 4A completion, IMP-037, and IMP-036",
);
expect(
  JSON.stringify(idleActivity.numbering_policy.retired_implementations) ===
    JSON.stringify(RETIRED_IMPLEMENTATION_IDS),
  "activity numbering policy must expose retired identifiers",
);

const activeActivity = buildProjectActivity({
  closedPulls,
  openPulls: [
    {
      number: 125,
      title: "IMP-038: add package v2 foundation",
      html_url: "https://example.invalid/pr/125",
      updated_at: "2026-06-26T01:00:00Z",
    },
  ],
  openIssues: [
    {
      number: 24,
      title: "IMP-024: stale retired reservation",
      html_url: "https://example.invalid/issue/24",
      updated_at: "2026-06-26T02:00:00Z",
      created_at: "2026-06-26T02:00:00Z",
    },
    {
      number: 126,
      title: "IMP-039: next project-continuity slice",
      html_url: "https://example.invalid/issue/126",
      updated_at: "2026-06-26T03:00:00Z",
      created_at: "2026-06-26T03:00:00Z",
    },
  ],
});
expect(activeActivity.current?.implementation === 38, "active fixture current must be IMP-038");
expect(activeActivity.next?.implementation === 39, "active fixture up next must be the real IMP-039 issue");

const issueOnlyActivity = buildProjectActivity({
  closedPulls,
  openIssues: [
    {
      number: 125,
      title: "IMP-038: add package v2 foundation",
      html_url: "https://example.invalid/issue/125",
      updated_at: "2026-06-26T01:00:00Z",
      created_at: "2026-06-26T01:00:00Z",
    },
  ],
});
expect(issueOnlyActivity.current?.implementation === 38, "a real open issue may be Current");
expect(issueOnlyActivity.next === null, "one open issue must not create a synthetic Up next");

if (!process.exitCode) {
  console.log("public-site-status check passed");
}
