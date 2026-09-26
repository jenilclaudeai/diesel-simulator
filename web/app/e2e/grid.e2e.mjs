// End-to-end: a full operating grid built in a real headless Chrome, through
// the app's own worker and SolverPort, matches a native-Python build of the
// same grid cell for cell (PLAN.md Phase 2 exit criterion).
//
//   npm run build:pages && CHROME_PATH=/path/to/chrome npm run e2e:grid
//
// NATIVE_GRID=<file> supplies the reference; without it the script runs
// e2e/native_grid.py itself (python3 with numpy), and fails if it cannot.
// Every perf value of every cell is compared at 1e-5 relative, with the
// denominator floored at 1e-3 of that quantity's largest |value| across the
// grid (near-zero torque at the no-load/fuel-cut boundary). 1e-5 is the
// SolverPort's bound: the limiter's calibration chain amplifies a ~1e-10
// platform difference to ~1e-6 (web/solver/test/roundtrip.test.ts).
// Then builds again and checks the second build comes from the cache.
import http from "node:http";
import fs from "node:fs";
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
const REL_TOL = 1e-5;
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

let ref;
const t0 = Date.now();
try {
  ref = JSON.parse(process.env.NATIVE_GRID ? fs.readFileSync(process.env.NATIVE_GRID, "utf8")
    : execFileSync("python3", [path.join(here, "native_grid.py")],
      { encoding: "utf8", cwd: path.resolve(here, "..", "..", ".."), maxBuffer: 64 << 20 }));
} catch (e) {
  ref = undefined;
  console.log(`native reference failed: ${String(e.message).split("\n")[0]}`);
}
const nRef = ref ? Object.keys(ref.cells).length : 0;
check("native Python grid available", nRef === 48, `${nRef} cells in ${((Date.now() - t0) / 1000).toFixed(0)} s`);

const browser = await puppeteer.launch({
  executablePath: process.env.CHROME_PATH,
  args: ["--no-sandbox", "--disable-dev-shm-usage", ...(process.env.CHROME_ARGS?.split(" ") ?? [])],
  headless: process.env.CHROME_HEADLESS === "shell" ? "shell" : true,
});
const page = await browser.newPage();
await page.setViewport({ width: 1100, height: 900 });
const problems = [];
page.on("pageerror", e => problems.push(`pageerror: ${e.message}`));
page.on("console", m => { if (m.type() === "error") problems.push(`console: ${m.text()}`); });
page.on("requestfailed", r => problems.push(`requestfailed: ${r.url()}`));

await page.goto(`http://localhost:${port}${BASE}grid`, { waitUntil: "load" });
await page.waitForFunction(() => {
  const s = document.querySelector("select");
  return (s && !s.disabled && s.options.length > 0) || document.querySelector(".status .err");
}, { timeout: 180_000 });
if (!(await page.$("select:not([disabled])"))) {
  const st = await page.$eval(".status", e => e.textContent.trim()).catch(() => "no status element");
  console.log(`FAIL  page did not become ready: ${st}\n  ${problems.slice(0, 3).join("\n  ")}`);
  await page.screenshot({ path: path.join(out, "grid-failed.png"), fullPage: true });
  process.exit(1);
}
const engines = await page.$$eval("select option", o => o.map(x => x.textContent.trim()));
check("grid page boots Python in its worker", engines.length === 5, `engine list from the solver: ${engines.join(" | ")}`);

// progress: the status line must move through the cells while building
const seen = new Set();
const tb = Date.now();
await page.click("button.run");
while (true) {
  const st = await page.$eval(".status", e => e.textContent.replace(/\s+/g, " ").trim());
  const m = st.match(/Solving cell (\d+) of (\d+)/);
  if (m) seen.add(Number(m[1]));
  if (/Grid complete|err/.test(st) || (await page.$(".status .err"))) break;
  if (Date.now() - tb > 40 * 60_000) break;
  await new Promise(r => setTimeout(r, 250));
}
const buildS = (Date.now() - tb) / 1000;
const status = await page.$eval(".status", e => e.textContent.replace(/\s+/g, " ").trim());
check("grid builds in the browser", /Grid complete: 48 cells/.test(status), `${status} (${buildS.toFixed(0)} s wall)`);
check("progress is reported per cell", seen.size >= 40, `${seen.size} distinct cells seen in the status line`);

const cells = await page.$$eval("td[data-perf]", tds => tds.map(td =>
  ({ rpm: Number(td.dataset.rpm), load: Number(td.dataset.load), perf: JSON.parse(td.dataset.perf) })));
check("every cell shown", cells.length === 48, `${cells.length} cells`);

if (ref) {
  // locate each browser cell in the reference by its exact axis values
  const iOf = r => ref.rpms.indexOf(r), jOf = l => ref.loads.indexOf(l);
  const keys = Object.keys(ref.cells["0,0"] ?? {});
  const big = Object.fromEntries(keys.map(k => [k, Math.max(...Object.values(ref.cells).map(p => Math.abs(p[k])))]));
  let worst = 0, where = "", compared = 0, unmatched = 0;
  for (const c of cells) {
    const want = ref.cells[`${iOf(c.rpm)},${jOf(c.load)}`];
    if (!want) { unmatched++; continue; }
    for (const k of keys) {
      const w = want[k], g = c.perf[k];
      const rel = Math.abs(g - w) / Math.max(Math.abs(w), 1e-3 * big[k], 1e-300);
      compared++;
      if (!(rel <= worst)) { worst = Number.isNaN(rel) ? Infinity : rel; where = `${k} at ${c.rpm.toFixed(0)} rpm / load ${c.load.toFixed(2)} (browser ${g}, native ${w})`; }
    }
  }
  check("every cell matches native Python", unmatched === 0 && compared === 48 * keys.length && worst <= REL_TOL,
    `${compared} values (${keys.length} per cell), worst rel ${worst.toExponential(2)}${where ? " at " + where : ""}, tolerance ${REL_TOL}` +
    (unmatched ? `, ${unmatched} cells not found in the reference` : ""));
}
await page.screenshot({ path: path.join(out, "grid.png"), fullPage: true });

// second build: from the IndexedDB cache, no solving
const t2 = Date.now();
await page.click("button.run");
await page.waitForFunction(() => /Grid complete/.test(document.querySelector(".status")?.textContent ?? ""), { timeout: 120_000 });
const again = (Date.now() - t2) / 1000;
check("a second build comes from the cache", again < 5, `${again.toFixed(2)} s`);

check("no page errors, console errors or failed requests", problems.length === 0, problems.slice(0, 3).join(" ; "));
await browser.close();
server.close();
const failed = results.filter(r => !r).length;
console.log(`\n${results.length - failed} passed, ${failed} failed  (${((Date.now() - t0) / 1000).toFixed(0)} s)`);
process.exit(failed ? 1 : 0);
