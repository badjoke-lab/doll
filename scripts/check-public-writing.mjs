import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
let failed = false;

function read(relativePath) {
  return fs.readFileSync(path.join(root, relativePath), "utf8");
}

function fail(message) {
  console.error(`public-writing check failed: ${message}`);
  failed = true;
}

function count(text, fragment) {
  return text.split(fragment).length - 1;
}

function validDate(value) {
  return /^\d{4}-\d{2}-\d{2}$/.test(value || "");
}

const catalogPath = "website/functions/writing-catalog.js";
const catalogSource = read(catalogPath);
const catalogUrl = `data:text/javascript;base64,${Buffer.from(catalogSource).toString("base64")}`;
const catalog = await import(catalogUrl);
const { OFFICIAL_NOTES, EXTERNAL_PUBLICATIONS, ALL_WRITING } = catalog;

if (!Array.isArray(OFFICIAL_NOTES) || OFFICIAL_NOTES.length === 0) {
  fail("writing catalog requires at least one official note");
}

if (!Array.isArray(EXTERNAL_PUBLICATIONS)) {
  fail("writing catalog requires an external-publications array");
}

if (!Array.isArray(ALL_WRITING) || ALL_WRITING.length !== OFFICIAL_NOTES.length + EXTERNAL_PUBLICATIONS.length) {
  fail("ALL_WRITING must contain every official and external publication exactly once");
}

const ids = new Set();
const paths = new Set();

for (const entry of ALL_WRITING) {
  if (!entry.id || typeof entry.id !== "string") {
    fail("every writing entry requires a string id");
    continue;
  }

  if (ids.has(entry.id)) {
    fail(`duplicate writing id: ${entry.id}`);
  }
  ids.add(entry.id);

  if (!entry.title || !entry.summary || !validDate(entry.published)) {
    fail(`${entry.id} requires title, summary, and YYYY-MM-DD published date`);
  }
}

for (const note of OFFICIAL_NOTES) {
  if (note.kind !== "official") {
    fail(`${note.id} must use kind official`);
  }

  if (!note.path?.startsWith("/notes/") || !note.path.endsWith("/")) {
    fail(`${note.id} must use a canonical /notes/.../ path`);
  }

  if (paths.has(note.path)) {
    fail(`duplicate official note path: ${note.path}`);
  }
  paths.add(note.path);

  if (!note.description) {
    fail(`${note.id} requires a metadata description`);
  }

  if (note.updated && (!validDate(note.updated) || note.updated < note.published)) {
    fail(`${note.id} updated date must be YYYY-MM-DD and not earlier than published`);
  }

  if (!Array.isArray(note.related) || !Array.isArray(note.externalVersions)) {
    fail(`${note.id} requires related and externalVersions arrays`);
  }

  const noteFile = `website${note.path}index.html`;
  if (!fs.existsSync(path.join(root, noteFile))) {
    fail(`${note.id} is missing ${noteFile}`);
  } else if (!read(noteFile).includes(`<h1>${note.title}</h1>`)) {
    fail(`${noteFile} must contain the catalog title`);
  }

  for (const relatedId of note.related || []) {
    if (relatedId === note.id || !ALL_WRITING.some((entry) => entry.id === relatedId)) {
      fail(`${note.id} has invalid related id ${relatedId}`);
    }
  }

  for (const version of note.externalVersions || []) {
    if (!version.publisher || !version.url?.startsWith("https://")) {
      fail(`${note.id} has an invalid syndicated external version`);
    }
  }
}

for (const publication of EXTERNAL_PUBLICATIONS) {
  if (publication.kind !== "external-only") {
    fail(`${publication.id} must use kind external-only`);
  }

  if (!publication.publisher || !publication.url?.startsWith("https://")) {
    fail(`${publication.id} requires a publisher and HTTPS URL`);
  }
}

const writingIndex = read("website/writing/index.html");
for (const entry of ALL_WRITING) {
  const marker = `data-writing-id="${entry.id}"`;
  if (count(writingIndex, marker) !== 1) {
    fail(`/writing/ must list ${entry.id} exactly once`);
  }

  const destination = entry.kind === "official" ? entry.path : entry.url;
  if (!writingIndex.includes(destination.replace(/^\//, "../"))) {
    fail(`/writing/ is missing the destination for ${entry.id}`);
  }
}

const middleware = read("website/functions/_middleware.js");
for (const required of [
  'from "./writing-catalog.js"',
  "findOfficialNote",
  "renderHomeWriting",
  "renderPublicationLine",
  "renderRelatedWriting",
  'href="/writing/"',
]) {
  if (!middleware.includes(required)) {
    fail(`middleware is missing ${required}`);
  }
}

for (const stale of ["DEV_ARTICLE_URL", "function isNote", "externalArticleLink", "relatedArticleBlock"]) {
  if (middleware.includes(stale)) {
    fail(`middleware still contains one-off writing logic: ${stale}`);
  }
}

const sitemap = read("website/sitemap.xml");
if (!sitemap.includes("https://doll.badjoke-lab.com/writing/")) {
  fail("sitemap must include the Writing index");
}
for (const note of OFFICIAL_NOTES) {
  if (!sitemap.includes(`https://doll.badjoke-lab.com${note.path}`)) {
    fail(`sitemap is missing ${note.path}`);
  }
}

for (const machineFile of ["website/llms.txt", "website/ai.txt"]) {
  if (!read(machineFile).includes("https://doll.badjoke-lab.com/writing/")) {
    fail(`${machineFile} must reference the Writing index`);
  }
}

const workflow = read(".github/workflows/public-site-status.yml");
if (!workflow.includes("scripts/check-public-writing.mjs")) {
  fail("public-site workflow must watch and run check-public-writing.mjs");
}
if (!workflow.includes("node scripts/check-public-writing.mjs")) {
  fail("public-site workflow must execute check-public-writing.mjs");
}

if (failed) {
  process.exitCode = 1;
} else {
  console.log("public-writing check passed");
}
