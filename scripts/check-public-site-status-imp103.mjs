import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const statusPath = path.join(root, "website/project-status.json");
const evidencePath = path.join(
  root,
  "docs/testing/results/IMP-103-primary-intel-mac-lite-install-storage-measurement.json",
);
const previousChecker = path.join(
  root,
  "scripts/check-public-site-status-frontier.mjs",
);

function fail(message) {
  console.error(`public-site-status IMP-103 check failed: ${message}`);
  process.exit(1);
}

function expect(condition, message) {
  if (!condition) {
    fail(message);
  }
}

const originalStatusText = fs.readFileSync(statusPath, "utf8");
const status = JSON.parse(originalStatusText);
const evidence = JSON.parse(fs.readFileSync(evidencePath, "utf8"));
const message = status.model_runtime?.message || "";

expect(
  status.phase?.id === "6" &&
    status.phase?.state === "in_progress" &&
    status.phase?.next_implementation === 104,
  "Phase 6 must be in progress through IMP-103 with IMP-104 next",
);
expect(
  message.includes("Phase 6 is in progress through IMP-103"),
  "public message must advance through IMP-103",
);
expect(
  message.includes(
    "IMP-102 adds a bounded Lite installation/model-storage measurement path",
  ),
  "public message must describe the bounded IMP-102 measurement path",
);
expect(
  message.includes(
    "IMP-103 accepts one privacy-reviewed primary Intel Mac installation/model-storage result bound to commit a323aa0958387dcd746fa9ef9fa95eb519da1e54",
  ),
  "public message must describe the accepted IMP-103 evidence",
);
for (const required of [
  "Darwin x86_64",
  "CPython 3.14.6",
  "uv 0.11.21",
  "Ollama 0.33.2",
  "64426153 logical bytes",
  "69378048 allocated bytes",
  "provider-reported selected-model size 986061892 bytes",
  "runtime installation itself was not measured",
  "user-visible latency measurement",
  "the release soak gate",
]) {
  expect(message.includes(required), `public message must retain ${required}`);
}
expect(
  !message.includes(
    "PDF OCR/scanned-PDF fallback, accessibility presentation, full-install/model-storage measurement",
  ),
  "accepted installation/model-storage evidence must not remain in the incomplete frontier",
);
expect(
  message.includes(
    "These remain bounded observations rather than final disk, RAM, complete-stack, or performance requirements",
  ),
  "IMP-103 measurements must remain observations rather than release requirements",
);

expect(
  evidence.test_id === "IMP-102-LITE-INSTALL-MODEL-STORAGE-MEASUREMENT" &&
    evidence.result === "pass" &&
    evidence.commit_sha === "a323aa0958387dcd746fa9ef9fa95eb519da1e54" &&
    evidence.evidence_level === "real-machine" &&
    evidence.operating_system === "Darwin" &&
    evidence.architecture === "x86_64" &&
    evidence.measurement_scope ===
      "doll-lite-python-install-selected-model-storage" &&
    evidence.real_machine_measurement_collected === true &&
    evidence.real_machine_measurement_accepted === false &&
    evidence.synthetic_observations === false,
  "IMP-103 accepted evidence must remain the exact bounded real-machine collection",
);
expect(
  Object.values(evidence.checks || {}).length > 0 &&
    Object.values(evidence.checks || {}).every((value) => value === true),
  "IMP-103 accepted evidence checks must all remain true",
);
expect(
  Object.values(evidence.privacy || {}).length > 0 &&
    Object.values(evidence.privacy || {}).every((value) => value === false),
  "IMP-103 accepted evidence privacy flags must all remain false",
);
expect(
  Object.values(evidence.claims || {}).length > 0 &&
    Object.values(evidence.claims || {}).every((value) => value === false),
  "IMP-103 accepted evidence broader claims must all remain false",
);
const installation = evidence.observation?.lite_python_installation || {};
const tree = installation.tree || {};
const model = evidence.observation?.model || {};
expect(
  evidence.python_version === "3.14.6" &&
    evidence.observation?.uv_version === "uv 0.11.21" &&
    evidence.observation?.runtime_version === "0.33.2" &&
    installation.profile === "lite-python-no-dev-all-extras" &&
    JSON.stringify(installation.optional_extras) === JSON.stringify(["ocr", "pdf"]) &&
    installation.dependency_source_mode === "locked-offline-local-cache" &&
    installation.editable_install_used === false &&
    installation.dev_dependencies_included === false &&
    tree.logical_bytes === 64426153 &&
    tree.allocated_bytes === 69378048 &&
    tree.symlink_target_bytes_included === false &&
    model.provider_reported_installed_size_bytes === 986061892 &&
    evidence.observation?.runtime_installation?.measured === false,
  "IMP-103 accepted installation/model-storage measurements must remain exact",
);

const imp102Paragraph =
  "IMP-102 adds a bounded Lite installation/model-storage measurement path for the primary Intel Mac. " +
  "It creates a fresh locked offline non-editable no-dev environment with all supported Lite extras, verifies the dependency boundary, measures logical and allocated installation bytes, and inspects one explicitly selected already-installed local model through the fixed loopback runtime path. It does not pull models, install or start the runtime, use cloud credentials, make external network requests, infer a product default model, or define release disk/RAM/performance thresholds. ";
const imp103Paragraph =
  "IMP-103 accepts one privacy-reviewed primary Intel Mac installation/model-storage result bound to commit a323aa0958387dcd746fa9ef9fa95eb519da1e54: Darwin x86_64 with CPython 3.14.6, uv 0.11.21, and Ollama 0.33.2; the fresh locked no-dev/all-extras Lite Python environment measured 64426153 logical bytes and 69378048 allocated bytes, and the provider-reported selected-model size was 986061892 bytes. The optional runtime installation root was intentionally omitted, so the runtime installation itself was not measured and this is not a complete local-stack disk footprint. These remain bounded observations rather than final disk, RAM, complete-stack, or performance requirements, and user-visible latency, accessibility, release soak, full Lite performance, Phase 6, and Lite v1.0 remain incomplete. ";
const currentIncomplete =
  "PDF OCR/scanned-PDF fallback, accessibility presentation, user-visible latency measurement, the release soak gate,";
const previousIncomplete =
  "PDF OCR/scanned-PDF fallback, accessibility presentation, full-install/model-storage measurement, user-visible latency measurement, the release soak gate,";

const previousStatus = structuredClone(status);
previousStatus.phase.next_implementation = 102;
previousStatus.model_runtime.message = message
  .replace("Phase 6 is in progress through IMP-103", "Phase 6 is in progress through IMP-101")
  .replace(imp102Paragraph, "")
  .replace(imp103Paragraph, "")
  .replace(currentIncomplete, previousIncomplete);
previousStatus.last_reviewed = "2026-08-29";

expect(
  previousStatus.model_runtime.message !== message &&
    !previousStatus.model_runtime.message.includes("IMP-102 adds") &&
    !previousStatus.model_runtime.message.includes("IMP-103 accepts"),
  "IMP-103 compatibility projection must be deterministic",
);

try {
  fs.writeFileSync(
    statusPath,
    `${JSON.stringify(previousStatus, null, 2)}\n`,
    "utf8",
  );
  const completed = spawnSync(process.execPath, [previousChecker], {
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
