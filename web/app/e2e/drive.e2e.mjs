// End-to-end: the real-time drive (Phase 3) in a real headless Chrome.
//
//   npm run build:pages && CHROME_PATH=/path/to/chrome npm run e2e:drive
//
// 1. The page loads crdi15's prebuilt converged grid (public/grids/) and the
//    grid is current for this build (its grid_hash matches GRID_VERSION --
//    which also proves prepare-assets.mjs and bridge.grid_hash() agree).
// 2. Started for real, the worker's loop holds ~60 Hz for 3 s, and a held
//    throttle key reaches it (rpm rises).
// 3. The live fixture's 60 s script, run frame-exact through the page's own
//    worker, matches native Python driving the same grid
//    (e2e/native_drive.py): every discrete event at the same frame, final
//    quantities within 1e-6 (ADR-004's terminal bound).
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
  ".css": "text/css", ".json": "application/json", ".wasm": "application/wasm", ".ico": "image/x-icon" };
const BASE = "/diesel-simulator/";
const TERMINAL = 1e-6;
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

const t0 = Date.now();
let ref;
try {
  ref = JSON.parse(execFileSync("python3", [path.join(here, "native_drive.py"), "crdi15", "tc"],
    { encoding: "utf8", cwd: path.resolve(here, "..", "..", ".."), maxBuffer: 64 << 20 }));
} catch (e) {
  console.log(`native reference failed: ${String(e.message).split("\n")[0]}`);
}
check("native Python drive available", !!ref, ref ? `${ref.events.length} events in ${((Date.now() - t0) / 1000).toFixed(0)} s` : "");

const browser = await puppeteer.launch({
  executablePath: process.env.CHROME_PATH,
  args: ["--no-sandbox", "--disable-dev-shm-usage", ...(process.env.CHROME_ARGS?.split(" ") ?? [])],
  headless: process.env.CHROME_HEADLESS === "shell" ? "shell" : true,
  protocolTimeout: 30 * 60_000,
});
const page = await browser.newPage();
await page.setViewport({ width: 1100, height: 1000 });
const problems = [];
page.on("pageerror", e => problems.push(`pageerror: ${e.message}`));
page.on("console", m => { if (m.type() === "error") problems.push(`console: ${m.text()}`); });
page.on("requestfailed", r => problems.push(`requestfailed: ${r.url()}`));

// ---- 2. real time, with the keyboard ----
await page.goto(`http://localhost:${port}${BASE}drive`, { waitUntil: "load" });
await page.click("button.run");
await page.waitForFunction(() => /Running|clutch|lock/.test(document.querySelector(".status")?.textContent ?? "")
  || document.querySelector(".status .err"), { timeout: 60_000 });
// "Running" shows when the worker is ready; the gauges appear with its first state
await page.waitForSelector(".rpm", { timeout: 30_000 });
const note = await page.$eval(".note.accuracy", e => e.textContent.replace(/\s+/g, " ").trim()).catch(() => "");
check("prebuilt converged grid loaded and current for this build", /Converged grid, 96 cells/.test(note) && !/older physics build/.test(note), note);
const rpmIdle = await page.$eval(".rpm", e => Number(e.textContent.replace(/[^0-9]/g, "")));
await page.keyboard.down("w");
await new Promise(r => setTimeout(r, 1500));
await page.keyboard.up("w");
await new Promise(r => setTimeout(r, 1600));
const rpmAfter = await page.$eval(".rpm", e => Number(e.textContent.replace(/[^0-9]/g, "")));
const about = await page.$eval(".about", e => e.textContent);
const hz = Number(about.match(/Loop (\d+) Hz/)?.[1] ?? 0);
const frames = Number((about.match(/frame ([\d,]+)/)?.[1] ?? "0").replace(/,/g, ""));
check("a held throttle key reaches the loop", rpmAfter > rpmIdle + 300, `${rpmIdle} -> ${rpmAfter} rpm`);
check("the loop runs at 60 Hz in its worker", hz >= 55 && hz <= 65, `${hz} Hz, ${frames} frames in ~3.1 s`);
await page.screenshot({ path: path.join(out, "drive.png"), fullPage: true });

// ---- 3. frame-exact script through the real worker vs native Python ----
await page.goto(`http://localhost:${port}${BASE}drive?e2e`, { waitUntil: "load" });
await page.waitForFunction(() => !!globalThis.__drive, { timeout: 30_000 });
const res = await page.evaluate(async (script) => {
  await globalThis.__drive.load("crdi15", "tc");
  return globalThis.__drive.script(script, {});
}, ref?.script ?? { dt: 1 / 60, n: 1, throttle: [0], brake: [], grade: [], keys: [] });
if (ref) {
  const firstBad = res.events.findIndex((e, i) => JSON.stringify(e) !== JSON.stringify(ref.events[i]));
  check("every event at the same frame as native Python", firstBad < 0 && res.events.length === ref.events.length,
    firstBad < 0 ? `${res.events.length} events over ${res.frames} frames (${res.ms.toFixed(0)} ms in the worker)`
      : `first mismatch #${firstBad}: browser ${JSON.stringify(res.events[firstBad])} vs native ${JSON.stringify(ref.events[firstBad])}`);
  let worst = 0, where = "";
  for (const [k, want] of Object.entries(ref.final)) {
    const r = Math.abs(res.final[k] - want) / Math.max(Math.abs(want), 1e-9);
    if (!(r <= worst)) { worst = r; where = `${k} (${res.final[k]} vs ${want})`; }
  }
  check("final state within 1e-6 of native Python after 60 s", worst <= TERMINAL,
    `worst rel ${worst.toExponential(2)} at ${where || "-"}; ${(res.final.v * 3.6).toFixed(2)} km/h, oil ${(res.final.T_oil - 273.15).toFixed(1)} C`);
}

check("no page errors, console errors or failed requests", problems.length === 0, problems.slice(0, 3).join(" ; "));
await browser.close();
server.close();
const failed = results.filter(r => !r).length;
console.log(`\n${results.length - failed} passed, ${failed} failed  (${((Date.now() - t0) / 1000).toFixed(0)} s)`);
process.exit(failed ? 1 : 0);
