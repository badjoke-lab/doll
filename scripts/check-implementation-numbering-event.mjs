import fs from "node:fs";

const IMPLEMENTATION_TITLE = /^IMP-(\d+)\s*:/i;
const RETIRED = new Set([24, 25, 26, 27, 28, 29]);
const BASELINE = 31;

function implementationNumber(title) {
  const match = IMPLEMENTATION_TITLE.exec(title || "");
  return match ? Number.parseInt(match[1], 10) : null;
}

function fail(message) {
  console.error(`implementation-numbering check failed: ${message}`);
  process.exit(1);
}

const eventPath = process.env.GITHUB_EVENT_PATH;
const repository = process.env.GITHUB_REPOSITORY;
const token = process.env.GITHUB_TOKEN;

if (!eventPath || !repository) {
  fail("GitHub event context is unavailable");
}

const event = JSON.parse(fs.readFileSync(eventPath, "utf8"));
const subject = event.pull_request || event.issue;
const requested = implementationNumber(subject?.title);

if (requested === null) {
  console.log("implementation-numbering check skipped: title is not an IMP item");
  process.exit(0);
}

if (RETIRED.has(requested)) {
  fail(`IMP-${String(requested).padStart(3, "0")} is retired and must not be reused`);
}

const headers = {
  Accept: "application/vnd.github+json",
  "User-Agent": "doll-implementation-numbering-check",
  "X-GitHub-Api-Version": "2022-11-28",
};
if (token) {
  headers.Authorization = `Bearer ${token}`;
}

const response = await fetch(
  `https://api.github.com/repos/${repository}/pulls?state=closed&per_page=100&sort=updated&direction=desc`,
  { headers },
);
if (!response.ok) {
  fail(`GitHub API returned ${response.status}`);
}

const pulls = await response.json();
const latestMerged = pulls.reduce((latest, pull) => {
  if (!pull.merged_at) {
    return latest;
  }
  const number = implementationNumber(pull.title);
  return number === null ? latest : Math.max(latest, number);
}, BASELINE);

const expected = latestMerged + 1;
if (requested !== expected) {
  fail(
    `next implementation must be IMP-${String(expected).padStart(3, "0")} after merged IMP-${String(latestMerged).padStart(3, "0")}; received IMP-${String(requested).padStart(3, "0")}`,
  );
}

console.log(`implementation-numbering check passed: IMP-${String(requested).padStart(3, "0")}`);
