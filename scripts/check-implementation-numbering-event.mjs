import fs from "node:fs";

const IMPLEMENTATION_TITLE = /^IMP-(\d+)\s*:/i;
const RETIRED = new Set([24, 25, 26, 27, 28, 29]);
const BASELINE = 31;
const PAGE_SIZE = 100;
const MAX_PAGES = 10;

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

async function fetchPages(path) {
  const items = [];
  for (let page = 1; page <= MAX_PAGES; page += 1) {
    const separator = path.includes("?") ? "&" : "?";
    const response = await fetch(
      `https://api.github.com/repos/${repository}/${path}${separator}per_page=${PAGE_SIZE}&page=${page}`,
      { headers },
    );
    if (!response.ok) {
      fail(`GitHub API returned ${response.status} for ${path}`);
    }
    const pageItems = await response.json();
    if (!Array.isArray(pageItems)) {
      fail(`GitHub API returned an invalid collection for ${path}`);
    }
    items.push(...pageItems);
    if (pageItems.length < PAGE_SIZE) {
      return items;
    }
  }
  fail(`GitHub API pagination exceeded ${MAX_PAGES} pages for ${path}`);
}

const [pulls, issues] = await Promise.all([
  fetchPages("pulls?state=closed&sort=updated&direction=desc"),
  fetchPages("issues?state=closed&sort=updated&direction=desc"),
]);

const mergedNumbers = pulls
  .filter((pull) => Boolean(pull.merged_at))
  .map((pull) => implementationNumber(pull.title))
  .filter((number) => number !== null);

const completedIssueNumbers = issues
  .filter(
    (issue) =>
      !issue.pull_request &&
      Boolean(issue.closed_at) &&
      issue.state_reason !== "not_planned",
  )
  .map((issue) => implementationNumber(issue.title))
  .filter((number) => number !== null);

const latestCompleted = Math.max(
  BASELINE,
  ...mergedNumbers,
  ...completedIssueNumbers,
);
const expected = latestCompleted + 1;
if (requested !== expected) {
  fail(
    `next implementation must be IMP-${String(expected).padStart(3, "0")} after completed IMP-${String(latestCompleted).padStart(3, "0")}; received IMP-${String(requested).padStart(3, "0")}`,
  );
}

console.log(`implementation-numbering check passed: IMP-${String(requested).padStart(3, "0")}`);
