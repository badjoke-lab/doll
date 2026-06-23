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

const statusPath = "website/project-status.json";
const status = JSON.parse(read(statusPath));

expect(status.schema_version === 2, "project-status.json must use schema_version 2");
expect(Boolean(status.maturity) && typeof status.maturity === "string", "project-status.json requires a maturity string");
expect(
  Array.isArray(status.completed_phases) && status.completed_phases.includes("3"),
  "project-status.json must record completed phases through Phase 3",
);
expect(
  status.phase?.id === "4A" &&
    status.phase?.name === "AI environment portability foundation" &&
    status.phase?.state === "in progress" &&
    status.phase?.started_by_implementation === 30,
  "project-status.json must mark Phase 4A in progress from IMP-030",
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
const middleware = read("website/functions/_middleware.js");
const activityApi = read("website/functions/api/project-status.js");
const manifest = JSON.parse(read("website/site.webmanifest"));
const llms = read("website/llms.txt");
const ai = read("website/ai.txt");

for (const required of [
  "data-project-maturity",
  "data-project-phase",
  "data-project-runtime",
  'id="project-current"',
  'id="project-last-completed"',
  'id="project-next"',
  'id="development-current"',
  'id="development-last-completed"',
  'id="development-next"',
  'id="development-log"',
  'data-roadmap-phase="3"',
  'data-roadmap-phase="4A"',
  "data-roadmap-state",
  'src="./status.js"',
]) {
  expect(index.includes(required), `website/index.html is missing ${required}`);
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
  roadmap.includes("new implementation identifiers increase monotonically from IMP-030 onward"),
  "roadmap must define monotonic implementation numbering",
);
expect(
  roadmap.includes("unused legacy reservations IMP-024 through IMP-029 are retired permanently"),
  "roadmap must retire IMP-024 through IMP-029",
);
expect(
  roadmap.includes("IMP-032 is the next planned implementation identifier"),
  "roadmap must identify IMP-032 as next",
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
    number: 72,
    title: "WEB-007: Publish an article",
    html_url: "https://example.invalid/pr/72",
    updated_at: "2026-06-24T00:00:00Z",
    merged_at: "2026-06-24T00:00:00Z",
  },
  {
    number: 85,
    title: "IMP-031: persist canonical conversation state",
    html_url: "https://example.invalid/pr/85",
    updated_at: "2026-06-23T11:33:03Z",
    merged_at: "2026-06-23T11:33:03Z",
  },
  {
    number: 83,
    title: "IMP-030: add canonical conversation schema contracts",
    html_url: "https://example.invalid/pr/83",
    updated_at: "2026-06-23T10:52:48Z",
    merged_at: "2026-06-23T10:52:48Z",
  },
  {
    number: 81,
    title: "Complete IMP-023 and Phase 3 safety gate",
    html_url: "https://example.invalid/pr/81",
    updated_at: "2026-06-22T15:45:49Z",
    merged_at: "2026-06-22T15:45:49Z",
  },
  {
    number: 80,
    title: "IMP-023: add Phase 3 acceptance evidence",
    html_url: "https://example.invalid/pr/80",
    updated_at: "2026-06-22T14:55:12Z",
    merged_at: "2026-06-22T14:55:12Z",
  },
];

const idleActivity = buildProjectActivity({ closedPulls });
expect(idleActivity.schema_version === 2, "activity schema must be version 2");
expect(idleActivity.latest_merged_implementation === 31, "latest merged implementation must be IMP-031");
expect(idleActivity.current === null, "idle fixture must have no current implementation");
expect(idleActivity.last_completed?.implementation === 31, "last completed must be IMP-031");
expect(
  idleActivity.next?.kind === "planned" && idleActivity.next?.implementation === 32,
  "idle fixture must plan IMP-032",
);
expect(
  JSON.stringify(idleActivity.recent.map((entry) => entry.title)) ===
    JSON.stringify([
      "IMP-031: persist canonical conversation state",
      "IMP-030: add canonical conversation schema contracts",
      "Complete IMP-023 and Phase 3 safety gate",
    ]),
  "recent development must show IMP-031, IMP-030, and Phase 3 gate completion",
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
      number: 90,
      title: "IMP-032: add adapter contracts",
      html_url: "https://example.invalid/pr/90",
      updated_at: "2026-06-24T01:00:00Z",
    },
  ],
  openIssues: [
    {
      number: 24,
      title: "IMP-024: stale retired reservation",
      html_url: "https://example.invalid/issue/24",
      updated_at: "2026-06-24T02:00:00Z",
      created_at: "2026-06-24T02:00:00Z",
    },
    {
      number: 91,
      title: "IMP-033: next portability slice",
      html_url: "https://example.invalid/issue/91",
      updated_at: "2026-06-24T03:00:00Z",
      created_at: "2026-06-24T03:00:00Z",
    },
  ],
});
expect(activeActivity.current?.implementation === 32, "active fixture current must be IMP-032");
expect(activeActivity.next?.implementation === 33, "active fixture next must be IMP-033");

if (!process.exitCode) {
  console.log("public-site-status check passed");
}
