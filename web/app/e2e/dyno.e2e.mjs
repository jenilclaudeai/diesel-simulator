// End-to-end: the built app in a real headless Chrome.
//
//   npm run build && CHROME_PATH=/path/to/chrome node e2e/dyno.e2e.mjs
//
// Serves dist/ with the content types a real host uses (application/wasm
// matters: browsers only stream-compile WebAssembly served as that), loads
// the page, waits for Python to boot in the worker, runs a dyno pull like a
// user would, and checks the numbers against native Python.
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import puppeteer from "puppeteer-core";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "..", "dist", "app", "browser");
const out = path.join(here, "out");
fs.mkdirSync(out, { recursive: true });
const MIME = { ".html": "text/html", ".js": "text/javascript", ".mjs": "text/javascript",
  ".css": "text/css", ".json": "application/json", ".wasm": "application/wasm",
  ".zip": "application/zip", ".whl": "application/zip", ".ico": "image/x-icon" };

// Served under a subfolder, as GitHub Pages serves a project site.
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

const ref = JSON.parse(process.env.NATIVE_REF ?? "{}");
const physics = fs.readFileSync(path.resolve(here, "..", "src", "app", "solver", "physics-version.ts"), "utf8")
  .match(/PHYSICS_VERSION = "([0-9a-f]+)"/)[1];

const browser = await puppeteer.launch({
  executablePath: process.env.CHROME_PATH,
  args: ["--no-sandbox", "--disable-dev-shm-usage", ...(process.env.CHROME_ARGS?.split(" ") ?? [])],
  // Some Chrome builds (e.g. headless-shell) need "shell". Deliberately no
  // --disable-web-security or similar: they would hide the MIME, CORS and
  // secure-context problems this test exists to catch.
  headless: process.env.CHROME_HEADLESS === "shell" ? "shell" : true,
});
const page = await browser.newPage();
await page.setViewport({ width: 1100, height: 900 });
const problems = [];
page.on("pageerror", e => problems.push(`pageerror: ${e.message}`));
page.on("console", m => { if (m.type() === "error") problems.push(`console: ${m.text()}`); });
page.on("requestfailed", r => problems.push(`requestfailed: ${r.url()}`));

const t0 = Date.now();
await page.goto(`http://localhost:${port}${BASE}`, { waitUntil: "load" });
check("WebCrypto available on localhost (cache on)", await page.evaluate(() => !!crypto.subtle));

// Wait for a select that EXISTS, is enabled and has options - or for an
// error. (An earlier version waited on `!select?.disabled`, which is also
// true when there is no select at all, and passed on a blank page.)
await page.waitForFunction(() => {
  const s = document.querySelector("select");
  const err = document.querySelector(".status .err");
  return (s && !s.disabled && s.options.length > 0) || err;
}, { timeout: 180_000 });
const bootErr = await page.$eval(".status", e => e.textContent.trim()).catch(() => "no status element");
if (!(await page.$("select:not([disabled])"))) {
  console.log(`FAIL  page did not become ready: ${bootErr}\n  ${problems.slice(0, 3).join("\n  ")}`);
  await page.screenshot({ path: path.join(out, "failed.png"), fullPage: true });
  process.exit(1);
}
const loadS = (Date.now() - t0) / 1000;
const about = await page.$eval(".about", e => e.textContent);
check("Python boots in the page's worker", /Python 3\.14/.test(about), `ready after ${loadS.toFixed(0)} s`);
check("worker runs the physics this build expects", about.includes(physics.slice(0, 12)), physics.slice(0, 12));
const engines = await page.$$eval("select option", o => o.map(x => x.textContent.trim()));
check("engine list comes from the solver", engines.length === 5, engines.join(" | "));
check("page is not showing a cache-off warning", !about.includes("caching is off"));

await page.click("button.run");
await page.waitForFunction(() => /Pull complete/.test(document.querySelector(".status")?.textContent ?? ""),
  { timeout: 900_000 });
const rows = await page.$$eval(".data tbody tr", trs => trs.map(tr => [...tr.cells].map(c => c.textContent.trim())));
check("all ten points solved", rows.length === 10);
const num = s => Number(s.replace(/[^0-9.\-]/g, ""));
for (const [rpm, want] of Object.entries(ref)) {
  const row = rows.find(r => num(r[0]) === Number(rpm));
  const got = row ? num(row[1]) : NaN;
  check(`${rpm} rpm matches native Python`, Math.abs(got - want) < 0.06, `browser ${got}, native ${want.toFixed(3)}`);
}
const peak = await page.$eval(".readouts", e => e.innerText.replace(/\s+/g, " ").trim());
check("peak readouts shown", /Peak torque \d+ N·m at [\d,]+ rpm/.test(peak), peak);
check("governed region explained", await page.$(".note") !== null);
await page.screenshot({ path: path.join(out, "dyno.png"), fullPage: true });

check("no page errors, console errors or failed requests", problems.length === 0, problems.slice(0, 3).join(" ; "));
await browser.close();
server.close();
const failed = results.filter(r => !r).length;
console.log(`\n${results.length - failed} passed, ${failed} failed  (${((Date.now() - t0) / 1000).toFixed(0)} s)`);
process.exit(failed ? 1 : 0);
