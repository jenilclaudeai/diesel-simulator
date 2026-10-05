// The spec editor (Phase 6, ADR-015) in a real headless Chrome: every field of
// the engine shown in its subsystem; an edit is counted and shows the engine's
// own value; filter; a spec file imported (and a bad one refused, with the
// reason); then the cycle page solves the edited engine, and its numbers are
// native Python's for the same overrides.
//
//   npm run build:pages && CHROME_PATH=... npm run e2e:spec      (~1 min)
import http from "node:http";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { execFileSync } from "node:child_process";
import puppeteer from "puppeteer-core";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "..", "dist", "app", "browser");
const out = path.join(here, "out");
fs.mkdirSync(out, { recursive: true });
const MIME = { ".html": "text/html", ".js": "text/javascript", ".mjs": "text/javascript",
  ".css": "text/css", ".json": "application/json", ".wasm": "application/wasm",
  ".zip": "application/zip", ".whl": "application/zip", ".ico": "image/x-icon" };
const BASE = "/diesel-simulator/";
const server = http.createServer((req, res) => {
  const url = decodeURIComponent(new URL(req.url, "http://x").pathname);
  if (!url.startsWith(BASE)) { res.writeHead(404).end(); return; }
  let f = path.join(root, url.slice(BASE.length));
  if (!f.startsWith(root)) { res.writeHead(403).end(); return; }
  if (!fs.existsSync(f) || fs.statSync(f).isDirectory()) f = path.join(root, "index.html");
  res.writeHead(200, { "content-type": MIME[path.extname(f)] ?? "application/octet-stream" });
  fs.createReadStream(f).pipe(res);
}).listen(0);
const port = server.address().port;

const results = [];
const check = (name, ok, note = "") => {
  results.push(ok);
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${note ? "  -- " + note : ""}`);
};

const EDIT = { "geom.compression_ratio": 17 };
let ref;
try {
  ref = JSON.parse(process.env.NATIVE_SPEC_CYCLE ?? execFileSync("python3", [path.join(here, "native_cycle.py")],
    { cwd: path.resolve(here, "..", "..", ".."), encoding: "utf8", env: { ...process.env, OVERRIDES: JSON.stringify(EDIT) } }));
} catch (e) {
  console.log(`FAIL  no native reference: ${e.message.split("\n")[0]}`);
  server.close();
  process.exit(1);
}

const browser = await puppeteer.launch({ executablePath: process.env.CHROME_PATH, headless: true, protocolTimeout: 10 * 60_000,
  args: ["--no-sandbox", "--disable-dev-shm-usage"] });
const page = await browser.newPage();
await page.setViewport({ width: 1200, height: 1000 });
const problems = [];
page.on("pageerror", e => problems.push(`pageerror: ${e.message}`));
page.on("console", m => { if (m.type() === "error") problems.push(`console: ${m.text()}`); });

await page.goto(`http://localhost:${port}${BASE}spec?e2e`, { waitUntil: "load" });
await page.waitForSelector('tr[data-path="geom.compression_ratio"] input', { timeout: 180_000 });
const layout = await page.evaluate(() => ({
  groups: [...document.querySelectorAll("section.group h2")].map(h => h.firstChild.textContent.trim()),
  rows: document.querySelectorAll("tr[data-path]").length,
  editable: document.querySelectorAll("tr[data-path] input").length,
  cr: Number(document.querySelector('tr[data-path="geom.compression_ratio"] input').value),
}));
check("every field, in seven subsystems: 188 rows, 180 of them editable",
  layout.groups.length === 7 && layout.rows === 188 && layout.editable === 180,
  `${layout.groups.join(" | ")}; ${layout.rows} rows, ${layout.editable} inputs; compression ratio ${layout.cr}`);

const setValue = async (p, v) => {
  await page.$eval(`tr[data-path="${p}"] input`, (el, val) => {
    el.value = String(val);
    el.dispatchEvent(new Event("change", { bubbles: true }));
  }, v);
};
await setValue("geom.compression_ratio", 17);
await page.waitForFunction(() => /1 field changed/.test(document.querySelector(".changed-count")?.textContent ?? ""), { timeout: 5000 }).catch(() => {});
const edited = await page.evaluate(() => {
  const tr = document.querySelector('tr[data-path="geom.compression_ratio"]');
  return { count: document.querySelector(".changed-count")?.textContent.trim(), changed: tr?.classList.contains("changed"),
    was: tr?.querySelector(".was")?.textContent.replace(/\s+/g, " ").trim() };
});
check("an edit is counted, marked, and shows the engine's own value",
  edited.count === "1 field changed" && edited.changed && new RegExp(`engine: ${layout.cr}`).test(edited.was ?? ""),
  `${edited.count}; ${edited.was}`);

await page.type("input.filter", "bore");
await new Promise(r => setTimeout(r, 300));
const filtered = await page.$$eval("tr[data-path]", trs => trs.map(t => t.getAttribute("data-path")));
check("the filter finds fields by name, path or note", filtered.length > 0 && filtered.length < 20 && filtered.includes("geom.bore"),
  `${filtered.length} rows: ${filtered.slice(0, 5).join(", ")}…`);
await page.$eval("input.filter", el => { el.value = ""; el.dispatchEvent(new Event("input", { bubbles: true })); });

// a spec file: a bad one refused with the reason, a good one loaded
const dir = fs.mkdtempSync(path.join(os.tmpdir(), "spec-e2e-"));
const bad = path.join(dir, "bad.json"), good = path.join(dir, "good.json");
fs.writeFileSync(bad, JSON.stringify({ preset: "crdi15", overrides: { "geom.compresion_ratio": 17 } }));
fs.writeFileSync(good, JSON.stringify({ preset: "crdi15", overrides: { ...EDIT, "inj.n_holes": 8 } }));
const input = await page.$(".import input[type=file]");
await input.uploadFile(bad);
await page.waitForSelector("p.err[role=alert]", { timeout: 5000 }).catch(() => {});
const refused = await page.$eval("p.err[role=alert]", e => e.textContent.trim()).catch(() => "");
await input.uploadFile(good);
await page.waitForFunction(() => /2 fields changed/.test(document.querySelector(".changed-count")?.textContent ?? ""), { timeout: 5000 }).catch(() => {});
const loaded = await page.$eval(".changed-count", e => e.textContent.trim());
check("a spec file: a bad one refused with the reason, a good one loaded", /unknown field "geom.compresion_ratio"/.test(refused) && loaded === "2 fields changed",
  `refused: "${refused}"; then ${loaded}`);
await page.$eval('tr[data-path="inj.n_holes"] button.reset', b => b.click());
await page.screenshot({ path: path.join(out, "spec.png"), fullPage: false });

// the cycle page solves the edited engine
await page.click("a.solve");
await page.waitForSelector("button.run:not([disabled])", { timeout: 60_000 });
const note = await page.$eval("p.edits", e => e.textContent.replace(/\s+/g, " ").trim()).catch(() => "");
await page.click("button.run");
await page.waitForSelector(".cycle-data", { timeout: 5 * 60_000 });
const peak = await page.evaluate(() => [...document.querySelectorAll(".cycle-data tr")]
  .find(tr => tr.querySelector("th")?.textContent.trim() === "Peak pressure")?.querySelector("td")?.textContent.trim() ?? "");
const peakBar = Number((peak.match(/[\d.,]+/)?.[0] ?? "NaN").replace(/,/g, ""));
check("the cycle page solves the edited engine: native Python's peak pressure for the same override",
  /1 field changed/.test(note) && peakBar.toFixed(1) === ref.p_max_bar.toFixed(1),
  `"${note}"; page ${peak}; native ${ref.p_max_bar.toFixed(1)} bar (compression ratio 17)`);

// the invalidation banner (PLAN.md Phase 6): edit again, come back, and the old
// result is flagged out of date until it is solved again. In-app navigation
// only: a reload would drop the kept results.
let ref18;
try {
  ref18 = JSON.parse(process.env.NATIVE_SPEC_CYCLE18 ?? execFileSync("python3", [path.join(here, "native_cycle.py")],
    { cwd: path.resolve(here, "..", "..", ".."), encoding: "utf8", env: { ...process.env, OVERRIDES: JSON.stringify({ "geom.compression_ratio": 18 }) } }));
} catch (e) { ref18 = { p_max_bar: NaN }; }
const navTo = async label => {
  await page.evaluate(l => [...document.querySelectorAll("nav a")].find(a => a.textContent.trim() === l)?.click(), label);
};
await navTo("Spec");
await page.waitForSelector('tr[data-path="geom.compression_ratio"] input', { timeout: 60_000 });
await setValue("geom.compression_ratio", 18);
await page.click("a.solve");
await page.waitForSelector(".cycle-data", { timeout: 60_000 });
const staleShown = await page.$eval("app-spec-status .stale", e => e.textContent.replace(/\s+/g, " ").trim()).catch(() => "");
const oldPeak = await page.evaluate(() => [...document.querySelectorAll(".cycle-data tr")]
  .find(tr => tr.querySelector("th")?.textContent.trim() === "Peak pressure")?.querySelector("td")?.textContent.trim() ?? "");
await page.click("app-spec-status button.rerun");
await page.waitForFunction(() => !document.querySelector("app-spec-status .stale") && !document.querySelector("button.run[disabled]"),
  { timeout: 5 * 60_000, polling: 500 }).catch(() => {});
const staleAfter = await page.$("app-spec-status .stale");
const peak18 = await page.evaluate(() => [...document.querySelectorAll(".cycle-data tr")]
  .find(tr => tr.querySelector("th")?.textContent.trim() === "Peak pressure")?.querySelector("td")?.textContent.trim() ?? "");
const peak18Bar = Number((peak18.match(/[\d.,]+/)?.[0] ?? "NaN").replace(/,/g, ""));
check("after another edit the kept result is flagged out of date; solved again, it is native Python's for the new edit",
  /out of date/.test(staleShown) && oldPeak === peak && !staleAfter && peak18Bar.toFixed(1) === ref18.p_max_bar.toFixed(1),
  `banner: "${staleShown.slice(0, 60)}…" over ${oldPeak}; after: ${staleAfter ? "still stale" : "clear"}, ${peak18} (native ${ref18.p_max_bar.toFixed(1)}, compression ratio 18)`);

await navTo("Spec");
await page.waitForSelector('tr[data-path="geom.compression_ratio"] input', { timeout: 60_000 });
const beforeReset = await page.$eval(".changed-count", e => e.textContent.trim());
await page.click("button.reset-all").catch(() => {});
await page.waitForFunction(() => document.querySelector(".changed-count")?.textContent.trim() === "0 fields changed",
  { timeout: 5000 }).catch(() => {});
const afterReset = await page.$eval(".changed-count", e => e.textContent.trim());
check("Reset all clears the edits", afterReset === "0 fields changed", `${beforeReset} -> ${afterReset}`);
check("no page errors or console errors", problems.length === 0, problems.slice(0, 3).join(" | "));

await browser.close();
server.close();
const failed = results.filter(r => !r).length;
console.log(`\n${results.length - failed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
