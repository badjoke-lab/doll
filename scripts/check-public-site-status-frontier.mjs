import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const statusPath = path.join(root, "website/project-status.json");
const interpretationPath = path.join(
  root,
  "docs/testing/results/IMP-097-lite-client-performance-interpretation.json",
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
const message = status.model_runtime?.message || "";

expect(
  status.phase?.id === "6" &&
    status.phase?.state === "in_progress" &&
    status.phase?.next_implementation === 98,
  "Phase 6 must be in progress through IMP-097 with IMP-098 next",
);
expect(
  message.includes("Phase 6 is in progress through IMP-097"),
  "public message must advance through IMP-097",
);
expect(
  message.includes(
    "IMP-097 adds a deterministic conservative interpretation layer over the accepted IMP-096 evidence",
  ),
  "public message must describe the bounded IMP-097 interpretation",
);
expect(
  message.includes("measurements rather than release requirements") &&
    message.includes(
      "full Lite performance thresholds, accessibility, release soak, Phase 6, and Lite v1.0 incomplete",
    ),
  "IMP-097 observations must not become release requirements or completion claims",
);
for (const required of [
  "representative local-runtime/model resource measurement",
  "repeatability/variance",
  "full-install/model-storage measurement",
  "user-visible latency workload measurement",
  "release-candidate soak disk-growth evidence",
]) {
  expect(message.includes(required), `public message must retain ${required}`);
}
expect(
  !message.includes("performance threshold interpretation, the release soak gate"),
  "stale generic performance-interpretation blocker must be replaced",
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

const imp097Paragraph =
  "IMP-097 adds a deterministic conservative interpretation layer over the accepted IMP-096 evidence. " +
  "It preserves the observed duration, peak process RSS, and workspace values as measurements rather than release requirements, " +
  "records successful execution only for the bounded primary Intel Mac client workload, and keeps minimum RAM, full-install disk, " +
  "user-visible latency, external-runtime/model/GPU/total-system resource requirements, cross-machine generalization, full Lite " +
  "performance thresholds, accessibility, release soak, Phase 6, and Lite v1.0 incomplete. The interpretation identifies " +
  "representative local-runtime/model resource measurement, repeatability/variance, full-install/model-storage measurement, " +
  "user-visible latency workload measurement, and release-candidate soak disk-growth evidence as still required before broader " +
  "performance claims. ";
const currentIncomplete =
  "PDF OCR/scanned-PDF fallback, accessibility presentation, representative local-runtime/model resource evidence, " +
  "repeatability/variance evidence, full-install/model-storage measurement, user-visible latency measurement, the release soak gate,";
const baselineIncomplete =
  "PDF OCR/scanned-PDF fallback, accessibility presentation, performance threshold interpretation, the release soak gate,";

const baselineStatus = structuredClone(status);
baselineStatus.phase.next_implementation = 97;
baselineStatus.model_runtime.message = message
  .replace("Phase 6 is in progress through IMP-097", "Phase 6 is in progress through IMP-096")
  .replace(imp097Paragraph, "")
  .replace(currentIncomplete, baselineIncomplete);

expect(
  baselineStatus.model_runtime.message !== message &&
    !baselineStatus.model_runtime.message.includes("IMP-097 adds"),
  "IMP-097 compatibility projection must be deterministic",
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
