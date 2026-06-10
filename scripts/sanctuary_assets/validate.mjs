/**
 * CI gate for Sanctuary 3D assets (mirrors scripts/validate_content.py:
 * per-item report, exit 0/1).
 *
 * Checks:
 *   1. Coverage  -- every icon key in content/sanctuary/*.json resolves to a
 *      manifest element OR is allowlisted in placeholders.json (and nothing
 *      is in BOTH, and nothing in the allowlist is stale).
 *   2. Files     -- every manifest GLB exists on disk.
 *   3. Budgets   -- per-model KB/tris from report.json, and total committed
 *      asset payload <= 15 MB soft / 20 MB hard.
 *   4. Licenses  -- every sources.json entry is literally CC0.
 *   5. Anchors   -- element/scenery anchors resolve into layout/<zone>.json
 *      (skipped per-entry when anchor is null).
 *
 * Usage: node validate.mjs
 */

import { readdir, readFile, stat } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.join(HERE, "..", "..");
const CONTENT_DIR = path.join(REPO, "content", "sanctuary");
const MODELS_DIR = path.join(REPO, "mobile", "assets", "sanctuary", "models");

const SOFT_TOTAL_BYTES = 15 * 1024 * 1024;
const HARD_TOTAL_BYTES = 20 * 1024 * 1024;

let failures = 0;
const fail = (msg) => {
  failures += 1;
  console.error(`✗ ${msg}`);
};
const ok = (msg) => console.log(`✓ ${msg}`);

async function readJson(p) {
  return JSON.parse(await readFile(p, "utf8"));
}

// --- gather content icon keys ----------------------------------------------

const contentIconKeys = new Set();
for (const file of await readdir(CONTENT_DIR)) {
  if (!file.endsWith(".json")) continue;
  const data = await readJson(path.join(CONTENT_DIR, file));
  const walk = (node) => {
    if (Array.isArray(node)) node.forEach(walk);
    else if (node && typeof node === "object") {
      if (typeof node.icon === "string") contentIconKeys.add(node.icon);
      Object.values(node).forEach(walk);
    }
  };
  walk(data);
}

// --- load manifest + allowlist ----------------------------------------------

let manifest = { elements: [], scenery: [] };
try {
  manifest = await readJson(path.join(HERE, "manifest.gen.json"));
} catch {
  fail("manifest.gen.json missing -- run build_manifest.mjs");
}
const allowlist = new Set((await readJson(path.join(HERE, "placeholders.json"))).allowlist);
const manifestKeys = new Set(manifest.elements.map((e) => e.iconKey));

// 1. Coverage
for (const key of contentIconKeys) {
  if (!manifestKeys.has(key) && !allowlist.has(key)) {
    fail(`content icon key '${key}' has no manifest entry and is not in placeholders.json`);
  }
  if (manifestKeys.has(key) && allowlist.has(key)) {
    fail(`'${key}' is BOTH in the manifest and placeholders.json -- remove it from the allowlist`);
  }
}
for (const key of allowlist) {
  if (!contentIconKeys.has(key)) {
    fail(`placeholders.json lists '${key}' which no content file references (stale)`);
  }
}
for (const key of manifestKeys) {
  if (!contentIconKeys.has(key)) {
    fail(`manifest element '${key}' has no matching content icon key (stale manifest)`);
  }
}
if (failures === 0) {
  ok(`coverage: ${contentIconKeys.size} content icon keys (${manifestKeys.size} modeled, ${allowlist.size} placeholder)`);
}

// 2. Files exist
for (const entry of [...manifest.elements, ...manifest.scenery]) {
  try {
    await stat(path.join(MODELS_DIR, entry.out));
  } catch {
    fail(`manifest entry '${entry.name}' GLB missing: ${entry.out}`);
  }
}

// 3. Budgets (report.json from normalize.mjs)
let report = [];
try {
  report = await readJson(path.join(HERE, "report.json"));
} catch {
  // No report yet is acceptable while the manifest is empty.
  if (manifest.elements.length + manifest.scenery.length > 0) {
    fail("report.json missing -- run normalize.mjs");
  }
}
for (const item of report) {
  if (item.error) fail(`normalize failed for '${item.name}': ${item.error}`);
  else if (item.withinBudget === false) {
    fail(`'${item.name}' over budget: ${item.kb} KB / ${item.tris} tris (max ${item.budget.maxKB} KB / ${item.budget.maxTris})`);
  }
}

async function dirSize(dir) {
  let total = 0;
  let entries = [];
  try {
    entries = await readdir(dir, { withFileTypes: true });
  } catch {
    return 0;
  }
  for (const e of entries) {
    const p = path.join(dir, e.name);
    total += e.isDirectory() ? await dirSize(p) : (await stat(p)).size;
  }
  return total;
}

const totalBytes = await dirSize(MODELS_DIR);
const totalMB = (totalBytes / (1024 * 1024)).toFixed(2);
if (totalBytes > HARD_TOTAL_BYTES) {
  fail(`total committed asset payload ${totalMB} MB exceeds the 20 MB hard ceiling`);
} else if (totalBytes > SOFT_TOTAL_BYTES) {
  console.warn(`! total asset payload ${totalMB} MB exceeds the 15 MB target (hard ceiling 20 MB)`);
} else {
  ok(`total asset payload ${totalMB} MB (target <= 15 MB)`);
}

// 4. Licenses
const sources = (await readJson(path.join(HERE, "sources.json"))).sources;
for (const source of sources) {
  if (source.license !== "CC0") {
    fail(`source '${source.id}' license is '${source.license}' -- CC0 only`);
  }
}
ok(`licenses: ${sources.length} sources, all CC0`);

// 5. Anchors
const layoutCache = new Map();
async function layoutFor(zone) {
  if (!layoutCache.has(zone)) {
    try {
      const data = await readJson(path.join(HERE, "layout", `${zone}.json`));
      layoutCache.set(zone, new Set(data.anchors.map((a) => a.name)));
    } catch {
      layoutCache.set(zone, null);
    }
  }
  return layoutCache.get(zone);
}
for (const entry of [...manifest.elements, ...manifest.scenery]) {
  if (!entry.anchor) continue;
  const anchors = await layoutFor(entry.zone);
  if (anchors === null) {
    fail(`'${entry.name}' references anchor '${entry.anchor}' but layout/${entry.zone}.json does not exist`);
  } else if (!anchors.has(entry.anchor)) {
    fail(`'${entry.name}' anchor '${entry.anchor}' not found in layout/${entry.zone}.json`);
  }
}

// --- summary -----------------------------------------------------------------

if (failures > 0) {
  console.error(`\n${failures} validation failure(s)`);
  process.exit(1);
}
console.log("\nAll sanctuary asset checks passed.");
