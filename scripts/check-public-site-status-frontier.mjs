import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const statusPath = path.join(root, "website/project-status.json");
const interpretationPath = path.join(
  root,
  "docs/testing/results/IMP-097-lite-client-performance-interpretation.json",
);
const runtimeEvidencePath = path.join(
  root,
  "docs/testing/results/IMP-099-primary-intel-mac-local-runtime-resource-measurement.json",
);
const baselineChecker = path.join(root, "scripts/check-public-site-status.mjs");

function fail(message) {
  console.error(`public-site-status frontier check failed: ${message}`);
  process.exit(1);
}

function expect(condition, message) {
  if (!condition) {
    fail(message);
  }
}

const originalStatusText = fs.readFileSync(statusPath, "utf8");
const status = JSON.parse(originalStatusText);
const interpretation = JSON.parse(fs.readFileSync(interpretationPath, "utf8"));
const runtimeEvidence = JSON.parse(fs.readFileSync(runtimeEvidencePath, "utf8"));
const message = status.model_runtime?.message || "";

expect(
  status.phase?.id === "6" &&
    status.phase?.state === "in_progress" &&
    status.phase?.next_implementation === 100,
  "Phase 6 must be in progress through IMP-099 with IMP-100 next",
);
expect(
  message.includes("Phase 6 is in progress through IMP-099"),
  "public message must advance through IMP-099",
);
expect(
  message.includes(
    "IMP-098 adds the bounded collection and validation path for one representative local Ollama runtime/model resource observation",
  ),
  "public message must describe the bounded IMP-098 collection path",
);
expect(
  message.includes(
    "IMP-099 accepts one privacy-reviewed real-machine IMP-098 result bound to commit 7e99fadbf0e9d6c4ed9c5f200de9be8b79ce1b6c",
  ),
  "public message must describe the accepted IMP-099 evidence",
);
for (const required of [
  "provider-reported model size 986061892 bytes",
  "maximum sampled runtime process-tree RSS 1252057088 bytes",
  "doll-process peak RSS 36093952 bytes",
  "6763389867 ns, 129910556 ns, and 147618618 ns",
  "repeatability/variance evidence",
  "full-install/model-storage measurement",
  "user-visible latency measurement",
  "the release soak gate",
]) {
  expect(message.includes(required), `public message must retain ${required}`);
}
expect(
  !message.includes(
    "PDF OCR/scanned-PDF fallback, accessibility presentation, representative local-runtime/model resource evidence",
  ),
  "accepted representative runtime/model evidence must not remain in the incomplete frontier",
);
expect(
  message.includes(
    "Minimum RAM, total-system/GPU/Metal memory, full-install/model-storage requirements, final user-visible latency, cold-start performance, cross-machine performance, supported/default model selection, full Lite performance thresholds, accessibility, release soak, Phase 6, and Lite v1.0 remain incomplete",
  ),
  "IMP-099 measurements must not become broader release requirements or completion claims",
);

expect(
  interpretation.schema_version === 1 &&
    interpretation.test_id ===
      "IMP-097-LITE-CLIENT-PERFORMANCE-INTERPRETATION" &&
    interpretation.result === "pass" &&
    interpretation.source_commit_sha ===
      "b57ebe6fb4a7620901b95b49f6743b71ae1026f7" &&
    interpretation.measurement_scope === "doll-lite-client-only",
  "IMP-097 interpretation result must remain bound to accepted IMP-096 evidence",
);
expect(
  interpretation.claims?.bounded_client_workload_observed_on_primary_intel_mac ===
    true &&
    interpretation.claims?.client_only_evidence_interpretation_complete === true &&
    interpretation.claims?.full_lite_performance_thresholds_defined === false &&
    interpretation.claims?.lite_performance_gate_complete === false &&
    interpretation.claims?.phase6_gate_complete === false &&
    interpretation.claims?.lite_v1_complete === false &&
    interpretation.claims?.accessibility_gate_complete === false &&
    interpretation.claims?.release_candidate_soak_complete === false,
  "IMP-097 machine-readable non-claims must remain conservative",
);

expect(
  runtimeEvidence.test_id === "IMP-098-LOCAL-RUNTIME-RESOURCE-MEASUREMENT" &&
    runtimeEvidence.result === "pass" &&
    runtimeEvidence.commit_sha ===
      "7e99fadbf0e9d6c4ed9c5f200de9be8b79ce1b6c" &&
    runtimeEvidence.evidence_level === "real-machine" &&
    runtimeEvidence.operating_system === "Darwin" &&
    runtimeEvidence.architecture === "x86_64" &&
    runtimeEvidence.measurement_scope === "doll-local-runtime-single-model" &&
    runtimeEvidence.repeat_count === 3 &&
    runtimeEvidence.real_machine_measurement_collected === true &&
    runtimeEvidence.real_machine_measurement_accepted === false &&
    runtimeEvidence.synthetic_observations === false,
  "IMP-099 accepted evidence must remain the exact bounded real-machine collection",
);
expect(
  Object.values(runtimeEvidence.checks || {}).length > 0 &&
    Object.values(runtimeEvidence.checks || {}).every((value) => value === true),
  "IMP-099 accepted evidence checks must all remain true",
);
expect(
  Object.values(runtimeEvidence.privacy || {}).length > 0 &&
    Object.values(runtimeEvidence.privacy || {}).every((value) => value === false),
  "IMP-099 accepted evidence privacy flags must all remain false",
);
expect(
  Object.values(runtimeEvidence.claims || {}).length > 0 &&
    Object.values(runtimeEvidence.claims || {}).every((value) => value === false),
  "IMP-099 accepted evidence broader claims must all remain false",
);
const observation = runtimeEvidence.observation || {};
expect(
  observation.runtime_version === "0.32.15" &&
    observation.model?.provider_reported_installed_size_bytes === 986061892 &&
    observation.maximum_sampled_runtime_process_tree_rss_bytes === 1252057088 &&
    observation.doll_process_rss?.peak_bytes === 36093952 &&
    JSON.stringify(observation.generation_duration?.values_ns) ===
      JSON.stringify([6763389867, 129910556, 147618618]),
  "IMP-099 accepted measurements must remain exact",
);

const imp097Paragraph =
  "IMP-097 adds a deterministic conservative interpretation layer over the accepted IMP-096 evidence. " +
  "It preserves the observed duration, peak process RSS, and workspace values as measurements rather than release requirements, " +
  "records successful execution only for the bounded primary Intel Mac client workload, and keeps minimum RAM, full-install disk, " +
  "user-visible latency, external-runtime/model/GPU/total-system resource requirements, cross-machine generalization, full Lite " +
  "performance thresholds, accessibility, release soak, Phase 6, and Lite v1.0 incomplete. The interpretation identifies " +
  "representative local-runtime/model resource measurement, repeatability/variance, full-install/model-storage measurement, " +
  "user-visible latency workload measurement, and release-candidate soak disk-growth evidence as still required before broader " +
  "performance claims. ";
const imp098Paragraph =
  "IMP-098 adds the bounded collection and validation path for one representative local Ollama runtime/model resource observation on the primary Intel Mac. " +
  "It uses an explicit already-installed non-cloud local model through the fixed loopback adapter, records provider-reported model bytes, four runtime process-tree RSS samples, doll-process RSS, and three generation durations without publishing native model names, prompts, responses, PIDs, command lines, paths, usernames, hostnames, credentials, or secrets; it does not install, pull, start, stop, or select a product default model and does not define Lite hardware thresholds. ";
const imp099Paragraph =
  "IMP-099 accepts one privacy-reviewed real-machine IMP-098 result bound to commit 7e99fadbf0e9d6c4ed9c5f200de9be8b79ce1b6c: Darwin x86_64 with CPython 3.14.6 and Ollama 0.32.15, provider-reported model size 986061892 bytes, maximum sampled runtime process-tree RSS 1252057088 bytes, doll-process peak RSS 36093952 bytes, and three generation durations of 6763389867 ns, 129910556 ns, and 147618618 ns. " +
  "The first generation is much slower than the repeats, so these values remain measurements rather than a user-visible latency threshold. Minimum RAM, total-system/GPU/Metal memory, full-install/model-storage requirements, final user-visible latency, cold-start performance, cross-machine performance, supported/default model selection, full Lite performance thresholds, accessibility, release soak, Phase 6, and Lite v1.0 remain incomplete. ";
const currentIncomplete =
  "PDF OCR/scanned-PDF fallback, accessibility presentation, repeatability/variance evidence, full-install/model-storage measurement, user-visible latency measurement, the release soak gate,";
const baselineIncomplete =
  "PDF OCR/scanned-PDF fallback, accessibility presentation, performance threshold interpretation, the release soak gate,";

const baselineStatus = structuredClone(status);
baselineStatus.phase.next_implementation = 97;
baselineStatus.model_runtime.message = message
  .replace("Phase 6 is in progress through IMP-099", "Phase 6 is in progress through IMP-096")
  .replace(imp097Paragraph, "")
  .replace(imp098Paragraph, "")
  .replace(imp099Paragraph, "")
  .replace(currentIncomplete, baselineIncomplete);

expect(
  baselineStatus.model_runtime.message !== message &&
    !baselineStatus.model_runtime.message.includes("IMP-097 adds") &&
    !baselineStatus.model_runtime.message.includes("IMP-098 adds") &&
    !baselineStatus.model_runtime.message.includes("IMP-099 accepts"),
  "IMP-099 compatibility projection must be deterministic",
);

try {
  fs.writeFileSync(
    statusPath,
    `${JSON.stringify(baselineStatus, null, 2)}\n`,
    "utf8",
  );
  const completed = spawnSync(process.execPath, [baselineChecker], {
    cwd: root,
    stdio: "inherit",
  });
  if (completed.error) {
    throw completed.error;
  }
  if (completed.status !== 0) {
    process.exitCode = completed.status ?? 1;
  }
} finally {
  fs.writeFileSync(statusPath, originalStatusText, "utf8");
}
