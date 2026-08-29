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
const repeatabilityEvidencePath = path.join(
  root,
  "docs/testing/results/IMP-101-primary-intel-mac-local-runtime-repeatability-variance.json",
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
const repeatabilityEvidence = JSON.parse(
  fs.readFileSync(repeatabilityEvidencePath, "utf8"),
);
const message = status.model_runtime?.message || "";

expect(
  status.phase?.id === "6" &&
    status.phase?.state === "in_progress" &&
    status.phase?.next_implementation === 102,
  "Phase 6 must be in progress through IMP-101 with IMP-102 next",
);
expect(
  message.includes("Phase 6 is in progress through IMP-101"),
  "public message must advance through IMP-101",
);
expect(
  message.includes(
    "IMP-100 adds a deterministic privacy-safe repeatability/variance layer over IMP-098",
  ),
  "public message must describe the bounded IMP-100 repeatability layer",
);
expect(
  message.includes(
    "IMP-101 accepts one privacy-reviewed three-session real-machine aggregate bound to commit a861e4bfd85214c6337bb188c3318e90846f5ebf",
  ),
  "public message must describe the accepted IMP-101 evidence",
);
for (const required of [
  "Ollama 0.33.1",
  "provider-reported model size 986061892 bytes",
  "runtime process-tree RSS maxima 1202470912, 1203814400, and 1137139712 bytes",
  "66674688-byte spread",
  "doll peak RSS 34045952, 35110912, and 34877440 bytes",
  "1064960-byte spread",
  "generation-position-1 durations 10589242907, 268770737, and 855706395 ns",
  "10320472170-ns spread",
  "full-install/model-storage measurement",
  "user-visible latency measurement",
  "the release soak gate",
]) {
  expect(message.includes(required), `public message must retain ${required}`);
}
expect(
  !message.includes(
    "PDF OCR/scanned-PDF fallback, accessibility presentation, repeatability/variance evidence",
  ),
  "accepted repeatability/variance evidence must not remain in the incomplete frontier",
);
expect(
  message.includes(
    "The large timing spread remains evidence only, not a product latency or cold-start requirement",
  ),
  "IMP-101 timing variance must remain a measurement rather than a threshold",
);
expect(
  message.includes(
    "no broader Lite performance, accessibility, release-soak, Phase 6, or Lite v1.0 gate is completed",
  ),
  "IMP-101 evidence must not become a broader release completion claim",
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
const runtimeObservation = runtimeEvidence.observation || {};
expect(
  runtimeObservation.runtime_version === "0.32.15" &&
    runtimeObservation.model?.provider_reported_installed_size_bytes === 986061892 &&
    runtimeObservation.maximum_sampled_runtime_process_tree_rss_bytes ===
      1252057088 &&
    runtimeObservation.doll_process_rss?.peak_bytes === 36093952 &&
    JSON.stringify(runtimeObservation.generation_duration?.values_ns) ===
      JSON.stringify([6763389867, 129910556, 147618618]),
  "IMP-099 accepted measurements must remain exact",
);

expect(
  repeatabilityEvidence.test_id ===
    "IMP-100-LOCAL-RUNTIME-REPEATABILITY-VARIANCE" &&
    repeatabilityEvidence.result === "pass" &&
    repeatabilityEvidence.commit_sha ===
      "a861e4bfd85214c6337bb188c3318e90846f5ebf" &&
    repeatabilityEvidence.evidence_level === "real-machine" &&
    repeatabilityEvidence.operating_system === "Darwin" &&
    repeatabilityEvidence.architecture === "x86_64" &&
    repeatabilityEvidence.measurement_scope ===
      "doll-local-runtime-single-model-repeatability" &&
    repeatabilityEvidence.session_count === 3 &&
    repeatabilityEvidence.real_machine_repeatability_collected === true &&
    repeatabilityEvidence.real_machine_repeatability_accepted === false &&
    repeatabilityEvidence.separate_measurement_session_invocations_confirmed ===
      true &&
    repeatabilityEvidence.source_manual_privacy_review_confirmed === true &&
    repeatabilityEvidence.cold_start_repeatability_measured === false,
  "IMP-101 accepted aggregate must remain the exact bounded real-machine repeatability collection",
);
expect(
  Object.values(repeatabilityEvidence.checks || {}).length > 0 &&
    Object.values(repeatabilityEvidence.checks || {}).every(
      (value) => value === true,
    ),
  "IMP-101 accepted aggregate checks must all remain true",
);
expect(
  Object.values(repeatabilityEvidence.privacy || {}).length > 0 &&
    Object.values(repeatabilityEvidence.privacy || {}).every(
      (value) => value === false,
    ),
  "IMP-101 accepted aggregate privacy flags must all remain false",
);
expect(
  Object.values(repeatabilityEvidence.claims || {}).length > 0 &&
    Object.values(repeatabilityEvidence.claims || {}).every(
      (value) => value === false,
    ),
  "IMP-101 accepted aggregate broader claims must all remain false",
);
const identity = repeatabilityEvidence.identity || {};
const sessions = repeatabilityEvidence.sessions || [];
const variance = repeatabilityEvidence.variance || {};
expect(
  identity.python_version === "3.14.6" &&
    identity.runtime_version === "0.33.1" &&
    identity.provider_reported_installed_size_bytes === 986061892 &&
    JSON.stringify(
      sessions.map(
        (session) => session.maximum_sampled_runtime_process_tree_rss_bytes,
      ),
    ) === JSON.stringify([1202470912, 1203814400, 1137139712]) &&
    JSON.stringify(
      sessions.map((session) => session.doll_process_peak_rss_bytes),
    ) === JSON.stringify([34045952, 35110912, 34877440]) &&
    JSON.stringify(
      sessions.map((session) => session.generation_duration_values_ns?.[0]),
    ) === JSON.stringify([10589242907, 268770737, 855706395]) &&
    variance.maximum_sampled_runtime_process_tree_rss_bytes?.spread ===
      66674688 &&
    variance.doll_process_peak_rss_bytes?.spread === 1064960 &&
    variance.generation_duration_by_position_ns?.[0]?.spread === 10320472170,
  "IMP-101 accepted repeatability measurements must remain exact",
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
const imp100Paragraph =
  "IMP-100 adds a deterministic privacy-safe repeatability/variance layer over IMP-098, requiring exactly three separately invoked real-machine reports sharing the same exact doll commit, Intel Mac platform, Python/runtime version, opaque model identity/revision, provider-reported model bytes, and offline/local-only conditions. " +
  "It validates every source through IMP-098, requires byte-distinct reports plus explicit independent-session and privacy-review confirmation, emits only source SHA-256 fingerprints and bounded RSS/duration summaries, and keeps minimum RAM, total-system/GPU/Metal memory, full-install/model-storage, user-visible latency, cold-start, cross-machine support, default-model selection, release variance thresholds, accessibility, release soak, Phase 6, and Lite v1.0 as non-claims. ";
const imp101Paragraph =
  "IMP-101 accepts one privacy-reviewed three-session real-machine aggregate bound to commit a861e4bfd85214c6337bb188c3318e90846f5ebf: Darwin x86_64 with CPython 3.14.6 and Ollama 0.33.1, provider-reported model size 986061892 bytes, runtime process-tree RSS maxima 1202470912, 1203814400, and 1137139712 bytes with a 66674688-byte spread, doll peak RSS 34045952, 35110912, and 34877440 bytes with a 1064960-byte spread, and generation-position-1 durations 10589242907, 268770737, and 855706395 ns with a 10320472170-ns spread. " +
  "The source reports remain uncommitted and the accepted aggregate binds them by SHA-256. The large timing spread remains evidence only, not a product latency or cold-start requirement, and no broader Lite performance, accessibility, release-soak, Phase 6, or Lite v1.0 gate is completed. ";
const currentIncomplete =
  "PDF OCR/scanned-PDF fallback, accessibility presentation, full-install/model-storage measurement, user-visible latency measurement, the release soak gate,";
const baselineIncomplete =
  "PDF OCR/scanned-PDF fallback, accessibility presentation, performance threshold interpretation, the release soak gate,";

const baselineStatus = structuredClone(status);
baselineStatus.phase.next_implementation = 97;
baselineStatus.model_runtime.message = message
  .replace("Phase 6 is in progress through IMP-101", "Phase 6 is in progress through IMP-096")
  .replace(imp097Paragraph, "")
  .replace(imp098Paragraph, "")
  .replace(imp099Paragraph, "")
  .replace(imp100Paragraph, "")
  .replace(imp101Paragraph, "")
  .replace(currentIncomplete, baselineIncomplete);

expect(
  baselineStatus.model_runtime.message !== message &&
    !baselineStatus.model_runtime.message.includes("IMP-097 adds") &&
    !baselineStatus.model_runtime.message.includes("IMP-098 adds") &&
    !baselineStatus.model_runtime.message.includes("IMP-099 accepts") &&
    !baselineStatus.model_runtime.message.includes("IMP-100 adds") &&
    !baselineStatus.model_runtime.message.includes("IMP-101 accepts"),
  "IMP-101 compatibility projection must be deterministic",
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
