// End-to-end: Enjoy installs as an app and drives offline (ADR-024).
//
//   npm run build:pages && CHROME_PATH=/path/to/chrome npm run e2e:offline
//
// The site is served as GitHub Pages serves it (under /diesel-simulator/), on an
// emulated landscape phone. Then the server is SHUT DOWN, not throttled: nothing but
// the service worker's cache can answer.
// 1. Online: Chrome reads the manifest with no errors and finds the page installable;
//    it starts on /enjoy, landscape, full screen, with a maskable icon.
// 2. The service worker takes the page and keeps the app's files (and no Pyodide).
// 3. Starting the hatchback keeps its grid.
// 4. Server down, page reloaded: Enjoy loads, the hatchback starts and makes sound.
// 5. An engine never started says it isn't on this device yet (not "no prebuilt grid").
// 6. No page errors, other than that engine's grid answered 504 by the service worker.
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import puppeteer from "puppeteer-core";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "..", "dist", "app", "browser");
const MIME = { ".html": "text/html", ".js": "text/javascript", ".mjs": "text/javascript",
  ".css": "text/css", ".json": "application/json", ".wasm": "application/wasm", ".ico": "image/x-icon",
  ".png": "image/png", ".webmanifest": "application/manifest+json" };
const BASE = process.env.E2E_BASE ?? "/diesel-simulator/";   // "/" for build:cloudflare
let served = 0;
const server = http.createServer((req, res) => {
  served++;
  const url = decodeURIComponent(new URL(req.url, "http://x").pathname);
  if (!url.startsWith(BASE)) { res.writeHead(404).end(); return; }
  let f = path.join(root, url.slice(BASE.length));
  if (!f.startsWith(root)) { res.writeHead(403).end(); return; }
  if (!fs.existsSync(f) || fs.statSync(f).isDirectory()) f = path.join(root, "index.html");
  res.writeHead(200, { "content-type": MIME[path.extname(f)] ?? "application/octet-stream", "cache-control": "max-age=600" });
  fs.createReadStream(f).pipe(res);
}).listen(0);
const port = server.address().port;
const ORIGIN = `http://localhost:${port}`;

const results = [];
const check = (name, ok, note = "") => {
  results.push(ok);
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${note ? "  -- " + note : ""}`);
};
const sleep = ms => new Promise(r => setTimeout(r, ms));

const browser = await puppeteer.launch({ timeout: 120_000,
  executablePath: process.env.CHROME_PATH,
  args: ["--no-sandbox", "--disable-dev-shm-usage", "--autoplay-policy=no-user-gesture-required",
    "--disable-audio-output", ...(process.env.CHROME_ARGS?.split(" ") ?? [])],
  headless: process.env.CHROME_HEADLESS === "shell" ? "shell" : true,
  protocolTimeout: 120_000,
});
const page = await browser.newPage();
await page.emulate({ viewport: { width: 915, height: 412, deviceScaleFactor: 2.6, isMobile: true, hasTouch: true, isLandscape: true },
  userAgent: "Mozilla/5.0 (Linux; Android 14; Pixel 7a) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Mobile Safari/537.36" });
let problems = [];
page.on("pageerror", e => problems.push(`pageerror: ${e.message}`));
page.on("console", m => { if (m.type() === "error") problems.push(`console: ${m.text()}`); });
page.on("requestfailed", r => problems.push(`requestfailed: ${r.url()}`));
const cdp = await page.createCDPSession();

async function at(sel, h) {
  const r = await page.$eval(sel, e => { const b = e.getBoundingClientRect(); return { x: b.x, y: b.y, w: b.width, h: b.height }; });
  return { x: r.x + r.w / 2, y: r.y + r.h * (1 - h) };
}
const touch = (type, points) => cdp.send("Input.dispatchTouchEvent", { type, touchPoints: points.map((p, i) => ({ x: p.x, y: p.y, id: i + 1 })) });
async function tapEl(sel) { const p = await at(sel, 0.5); await touch("touchStart", [p]); await sleep(60); await touch("touchEnd", []); }
/** URLs held in the service worker's caches whose cache name contains `group` (ngsw: "...:assets:<group>:cache"). */
const cached = group => page.evaluate(async g => {
  const out = [];
  for (const name of await caches.keys()) {
    if (!name.includes(`:assets:${g}:cache`)) continue;
    for (const req of await (await caches.open(name)).keys()) out.push(new URL(req.url).pathname);
  }
  return out;
}, group);
async function until(fn, ms, what) {
  const t0 = Date.now();
  for (;;) {
    const v = await fn();
    if (v) return v;
    if (Date.now() - t0 > ms) throw new Error(`timed out after ${ms} ms waiting for ${what}`);
    await sleep(250);
  }
}

try {
  // ---- online ----
  await page.goto(`${ORIGIN}${BASE}enjoy?e2e`, { waitUntil: "load" });

  // 1. the manifest, as Chrome reads it, and installability
  const man = await cdp.send("Page.getAppManifest");
  const parsed = JSON.parse(man.data || "{}");
  const startUrl = new URL(parsed.start_url ?? "", man.url).pathname;
  const scopeUrl = new URL(parsed.scope ?? "", man.url).pathname;
  check("Chrome reads the manifest with no errors", !!man.url && man.errors.length === 0,
    `${man.url} errors ${JSON.stringify(man.errors)}`);
  check("installed, it opens Enjoy, landscape, full screen, scoped to the site",
    startUrl === `${BASE}enjoy` && scopeUrl === BASE && parsed.display === "fullscreen" && parsed.orientation === "landscape",
    `start ${startUrl}, scope ${scopeUrl}, ${parsed.display}, ${parsed.orientation}`);
  check("icons: 192 and 512 px, and a maskable one for Android's launcher",
    ["192x192", "512x512"].every(s => parsed.icons?.some(i => i.sizes === s)) && parsed.icons.some(i => i.purpose === "maskable"),
    JSON.stringify(parsed.icons?.map(i => `${i.sizes}/${i.purpose}`)));

  // 2. the service worker takes the page and keeps the app
  await until(() => page.evaluate(() => !!navigator.serviceWorker?.controller), 60_000, "the service worker to control the page");
  // deploy/enjoy-only: as many as ngsw.json's app group lists (main's build: 13; here 12, the
  // solver's orphan worker chunk removed by scripts/enjoy-only.mjs), not a fixed 13
  const appUrls = JSON.parse(fs.readFileSync(path.join(root, "ngsw.json"), "utf8")).assetGroups.find(g => g.name === "app").urls;
  const app = await until(async () => { const c = await cached("app"); return c.length >= appUrls.length ? c : null; }, 60_000, "the app's files in the cache");
  check("the service worker controls the page and keeps every file of the app group",
    app.some(u => /\/main-[^/]+\.js$/.test(u)) && app.some(u => u.startsWith(`${BASE}audio/`)) && app.includes(`${BASE}index.html`)
    && appUrls.every(u => app.includes(u)) && !app.some(u => /\/worker-[^/]+\.js$/.test(u) && !appUrls.includes(u)),
    `${app.length} files of ${appUrls.length}`);
  const inst = await cdp.send("Page.getInstallabilityErrors");
  check("Chrome finds the page installable", inst.installabilityErrors.length === 0,
    JSON.stringify(inst.installabilityErrors.map(e => e.errorId)));
  const all = [...await cached("app"), ...await cached("grids")];
  check("no Pyodide and no solver bundle is kept (the engineering pages stay online-only)",
    !all.some(u => /pyodide|\/physics\//.test(u)), `${all.length} files kept`);

  // 3. start the hatchback: its grid is kept
  await tapEl("button.start");
  await page.waitForFunction(() => globalThis.__enjoy.view()?.rpm > 300, { timeout: 60_000 });
  const grids = await until(async () => { const c = await cached("grids"); return c.length ? c : null; }, 30_000, "the grid in the cache");
  check("starting an engine keeps its grid, and only its grid", grids.length === 1 && grids[0] === `${BASE}grids/hatch15.json`,
    JSON.stringify(grids));
  const onlineProblems = problems; problems = [];

  // ---- the server goes away ----
  server.closeAllConnections();
  await new Promise(r => server.close(r));
  const servedBefore = served;

  // 4. reload: Enjoy loads and drives from the cache
  await page.reload({ waitUntil: "load" });
  const dash = await page.waitForSelector("main.dash button.start", { timeout: 30_000 }).then(() => true, () => false);
  check("server down: the reloaded page is Enjoy, from the cache", dash && (await page.title()).startsWith("Enjoy"),
    await page.title());

  // 5. an engine never started
  await page.select('select[aria-label="Engine"]', "truck127");
  await tapEl("button.start");
  const err = await until(() => page.evaluate(() => document.querySelector("main.dash .err")?.textContent?.trim() ?? ""), 30_000, "the error line");
  check("an engine never started says it isn't on this device yet", /isn't on this device yet/.test(err) && !/no prebuilt grid/.test(err), err);

  // 4, continued: the hatchback drives, with sound
  await page.select('select[aria-label="Engine"]', "hatch15");
  await tapEl("button.start");
  const ran = await page.waitForFunction(() => globalThis.__enjoy.view()?.rpm > 300, { timeout: 60_000 }).then(() => true, () => false);
  await sleep(1500);
  const v = await page.evaluate(() => globalThis.__enjoy.view());
  const lvl = await page.evaluate(() => globalThis.__enjoy.level());
  const sErr = await page.evaluate(() => globalThis.__enjoy.soundError());
  check("server down: the hatchback starts, idles and makes sound", ran && v?.rpm > 300 && lvl > -60 && !sErr,
    `${Math.round(v?.rpm ?? 0)} rpm, sound ${lvl.toFixed(1)} dBFS${sErr ? ", sound error " + sErr : ""}`);
  check("nothing reached the server after it closed", served === servedBefore, `${served - servedBefore} requests`);

  // 6. page errors
  // the never-started engine's grid fails (net::ERR_FAILED through the service worker), and
  // Chrome logs "Failed to load resource" for it; any other failed load has its own
  // requestfailed line, so it is still caught
  const expected = p => p === `requestfailed: ${ORIGIN}${BASE}grids/truck127.json` || /^console: Failed to load resource/.test(p);
  check("no page errors online", onlineProblems.length === 0, onlineProblems.slice(0, 3).join(" | "));
  const offlineBad = problems.filter(p => !expected(p));
  check("no page errors offline, beyond the never-started engine's grid", offlineBad.length === 0, offlineBad.slice(0, 3).join(" | "));
} catch (e) {
  check("the run finished", false, e instanceof Error ? e.message : String(e));
} finally {
  await browser.close();
  if (server.listening) server.close();
}

const failed = results.filter(r => !r).length;
console.log(`\n${results.length - failed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
