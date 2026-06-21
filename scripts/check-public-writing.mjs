import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
let failed = false;

const read = (file) => fs.readFileSync(path.join(root, file), "utf8");
const exists = (file) => fs.existsSync(path.join(root, file));
const fail = (message) => {
  console.error(`public-writing check failed: ${message}`);
  failed = true;
};
const count = (text, fragment) => text.split(fragment).length - 1;
const validDate = (value) => /^\d{4}-\d{2}-\d{2}$/.test(value || "");

const catalogPath = "website/src/writing-catalog.js";
const catalogSource = read(catalogPath);
const catalogUrl = `data:text/javascript;base64,${Buffer.from(catalogSource).toString("base64")}`;
const { OFFICIAL_NOTES, EXTERNAL_PUBLICATIONS, ALL_WRITING } = await import(catalogUrl);

if (!Array.isArray(OFFICIAL_NOTES) || OFFICIAL_NOTES.length === 0) {
  fail("catalog requires at least one official note");
}
if (!Array.isArray(EXTERNAL_PUBLICATIONS)) {
  fail("catalog requires an external-publications array");
}
if (!Array.isArray(ALL_WRITING) || ALL_WRITING.length !== OFFICIAL_NOTES.length + EXTERNAL_PUBLICATIONS.length) {
  fail("ALL_WRITING must contain all catalog entries exactly once");
}

const ids = new Set();
const notePaths = new Set();
for (const entry of ALL_WRITING) {
  if (!entry.id || ids.has(entry.id)) fail(`invalid or duplicate id: ${entry.id}`);
  ids.add(entry.id);
  if (!entry.title || !entry.summary || !validDate(entry.published)) {
    fail(`${entry.id} requires title, summary, and YYYY-MM-DD published date`);
  }
}

for (const note of OFFICIAL_NOTES) {
  if (note.kind !== "official") fail(`${note.id} must use kind official`);
  if (!note.path?.startsWith("/notes/") || !note.path.endsWith("/") || notePaths.has(note.path)) {
    fail(`${note.id} has an invalid or duplicate note path`);
  }
  notePaths.add(note.path);
  if (!note.description) fail(`${note.id} requires a metadata description`);
  if (note.updated && (!validDate(note.updated) || note.updated < note.published)) {
    fail(`${note.id} has an invalid updated date`);
  }
  if (!Array.isArray(note.related) || !Array.isArray(note.externalVersions)) {
    fail(`${note.id} requires related and externalVersions arrays`);
  }

  const noteFile = `website${note.path}index.html`;
  if (!exists(noteFile) || !read(noteFile).includes(`<h1>${note.title}</h1>`)) {
    fail(`${note.id} is missing its matching HTML document`);
  }

  for (const relatedId of note.related || []) {
    if (relatedId === note.id || !ALL_WRITING.some((entry) => entry.id === relatedId)) {
      fail(`${note.id} has invalid related id ${relatedId}`);
    }
  }
  for (const version of note.externalVersions || []) {
    if (!version.publisher || !version.url?.startsWith("https://")) {
      fail(`${note.id} has an invalid syndicated version`);
    }
  }
}

for (const publication of EXTERNAL_PUBLICATIONS) {
  if (publication.kind !== "external-only") fail(`${publication.id} must use kind external-only`);
  if (!publication.publisher || !publication.url?.startsWith("https://")) {
    fail(`${publication.id} requires a publisher and HTTPS URL`);
  }
}

const writingIndex = read("website/writing/index.html");
for (const entry of ALL_WRITING) {
  if (count(writingIndex, `data-writing-id="${entry.id}"`) !== 1) {
    fail(`/writing/ must list ${entry.id} exactly once`);
  }
  const destination = entry.kind === "official" ? entry.path.replace(/^\//, "../") : entry.url;
  if (!writingIndex.includes(destination)) fail(`/writing/ is missing ${entry.id}`);
}

const middleware = read("website/functions/_middleware.js");
for (const required of [
  'from "../src/writing-catalog.js"',
  "findOfficialNote",
  "renderHomeWriting",
  "renderPublicationLine",
  "renderRelatedWriting",
  'href="/writing/"',
]) {
  if (!middleware.includes(required)) fail(`middleware is missing ${required}`);
}
for (const stale of ["DEV_ARTICLE_URL", "function isNote", "externalArticleLink", "relatedArticleBlock"]) {
  if (middleware.includes(stale)) fail(`middleware contains stale one-off logic: ${stale}`);
}
if (exists("website/functions/writing-catalog.js")) {
  fail("catalog must be outside the file-routed Functions directory");
}

const sitemap = read("website/sitemap.xml");
if (!sitemap.includes("https://doll.badjoke-lab.com/writing/")) fail("sitemap is missing /writing/");
for (const note of OFFICIAL_NOTES) {
  if (!sitemap.includes(`https://doll.badjoke-lab.com${note.path}`)) fail(`sitemap is missing ${note.path}`);
}
for (const file of ["website/llms.txt", "website/ai.txt"]) {
  if (!read(file).includes("https://doll.badjoke-lab.com/writing/")) fail(`${file} is missing /writing/`);
}

const workflow = read(".github/workflows/public-site-status.yml");
if (!workflow.includes("scripts/check-public-writing.mjs") || !workflow.includes("node scripts/check-public-writing.mjs")) {
  fail("public-site workflow must watch and run the Writing check");
}

if (failed) process.exitCode = 1;
else console.log("public-writing check passed");
