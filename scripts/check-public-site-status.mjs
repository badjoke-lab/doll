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

expect(status.schema_version === 2, "project-status.json must use schema_version 2");
expect(
  Boolean(status.maturity) && typeof status.maturity === "string",
  "project-status.json requires a maturity string",
);
expect(
  Array.isArray(status.completed_phases) && status.completed_phases.includes("4B"),
  "project-status.json must record completed phases through Phase 4B",
);
expect(
  status.phase?.id === "5" &&
    status.phase?.name === "Local runtime and model integration" &&
    status.phase?.state === "in_progress" &&
    status.phase?.started_by_implementation === 48 &&
    status.phase?.next_implementation === 54,
  "project-status.json must mark Phase 5 in progress from IMP-048 with IMP-054 next",
);
expect(
  status.model_runtime &&
    typeof status.model_runtime.connected === "boolean" &&
    typeof status.model_runtime.message === "string",
  "project-status.json requires model_runtime.connected and model_runtime.message",
);
expect(
  /^\d{4}-\d{2}-\d{2}$/.test(status.last_reviewed || ""),
  "project-status.json last_reviewed must be YYYY-MM-DD",
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
  roadmap.includes("IMP-048 establishes the runtime-independent local adapter contract"),
  "roadmap must record the IMP-048 runtime adapter contract",
);
expect(
  roadmap.includes("IMP-049 implements the first concrete Ollama adapter"),
  "roadmap must record the IMP-049 Ollama adapter",
);
expect(
  roadmap.includes("IMP-050 adds authoritative RuntimeManifestRecord v1"),
  "roadmap must record the IMP-050 authoritative manifest foundation",
);
expect(
  roadmap.includes("IMP-051 adds the first canonical non-streaming local conversation path"),
  "roadmap must record the IMP-051 canonical local conversation path",
);
expect(
  roadmap.includes("IMP-052 adds explicit scope-local switching to a chosen binding"),
  "roadmap must record the IMP-052 explicit model-switch boundary",
);
expect(
  roadmap.includes("IMP-053 connects the bounded local stream transcript"),
  "roadmap must record the IMP-053 bounded streaming boundary",
);
expect(
  roadmap.includes("IMP-054 adds an exact-commit Phase 5 acceptance runner"),
  "roadmap must record the IMP-054 local-runtime continuity harness",
);
expect(
  roadmap.includes("The required order after automated IMP-054 evidence is:"),
  "roadmap must advance immediate work to the IMP-054 real-machine gate",
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
