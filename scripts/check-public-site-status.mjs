import fs from "node:fs";
import path from "node:path";

const root = process.cwd();

function read(relativePath) {
  return fs.readFileSync(path.join(root, relativePath), "utf8");
}

function fail(message) {
  console.error(`public-site-status check failed: ${message}`);
  process.exitCode = 1;
}

const statusPath = "website/project-status.json";
const status = JSON.parse(read(statusPath));

if (status.schema_version !== 1) {
  fail("project-status.json must use schema_version 1");
}

if (!status.maturity || typeof status.maturity !== "string") {
  fail("project-status.json requires a maturity string");
}

if (!status.phase || !status.phase.id || !status.phase.name || !status.phase.state) {
  fail("project-status.json requires phase.id, phase.name, and phase.state");
}

if (
  !status.model_runtime ||
  typeof status.model_runtime.connected !== "boolean" ||
  typeof status.model_runtime.message !== "string"
) {
  fail("project-status.json requires model_runtime.connected and model_runtime.message");
}

if (!/^\d{4}-\d{2}-\d{2}$/.test(status.last_reviewed || "")) {
  fail("project-status.json last_reviewed must be YYYY-MM-DD");
}

const index = read("website/index.html");
const middleware = read("website/functions/_middleware.js");
const manifest = JSON.parse(read("website/site.webmanifest"));
const llms = read("website/llms.txt");
const ai = read("website/ai.txt");

for (const required of [
  "data-project-maturity",
  "data-project-phase",
  "data-project-runtime",
  'id="project-current"',
  'id="project-next"',
  'id="development-current"',
  'id="development-next"',
  'id="development-log"',
  'src="./status.js"',
]) {
  if (!index.includes(required)) {
    fail(`website/index.html is missing ${required}`);
  }
}

if (/IMP-\d+\s+is\s+next/i.test(index)) {
  fail("website/index.html contains a hard-coded next implementation");
}

if (index.includes("devlog.js")) {
  fail("website/index.html still references devlog.js");
}

if (middleware.includes("doll-logo.svg")) {
  fail("middleware still advertises the SVG favicon");
}

if (!middleware.includes('rel="icon" type="image/png"')) {
  fail("middleware does not advertise a PNG favicon");
}

if (!Array.isArray(manifest.icons) || manifest.icons.length === 0) {
  fail("site.webmanifest requires at least one icon");
} else if (manifest.icons.some((icon) => icon.type !== "image/png")) {
  fail("site.webmanifest must contain PNG icons only");
}

for (const machineFile of [llms, ai]) {
  if (!machineFile.includes("https://doll.badjoke-lab.com/project-status.json")) {
    fail("machine-readable discovery files must reference project-status.json");
  }

  if (!machineFile.includes("https://doll.badjoke-lab.com/api/project-status")) {
    fail("machine-readable discovery files must reference the live activity API");
  }
}

if (!process.exitCode) {
  console.log("public-site-status check passed");
}
