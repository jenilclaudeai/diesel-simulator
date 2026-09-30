// End-to-end: Enjoy mode (Phase 5, ADR-012) on an emulated landscape phone,
// driven by real touch events (CDP Input.dispatchTouchEvent).
//
//   npm run build:pages && CHROME_PATH=/path/to/chrome npm run e2e:enjoy
//
// 1. One tap starts the engine and the sound.
// 2. Holding the throttle high revs the engine and moves the car; lifting
//    it returns the throttle to 0 (a real pedal, not the keyboard's sticky one).
// 3. Holding the brake slows the car.
// 4. Two thumbs at once: throttle and brake both register.
// 5. The shift paddle changes gear.
// 6. In portrait, the page asks to be turned sideways.
// 7. No Pyodide is fetched, and there are no page errors.
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import puppeteer from "puppeteer-core";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "..", "dist", "app", "browser");
const MIME = { ".html": "text/html", ".js": "text/javascript", ".mjs": "text/javascript",
  ".css": "text/css", ".json": "application/json", ".wasm": "application/wasm", ".ico": "image/x-icon" };
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
const sleep = ms => new Promise(r => setTimeout(r, ms));

const browser = await puppeteer.launch({
  executablePath: process.env.CHROME_PATH,
  // a fake real-time audio sink: the test judges the page, not this machine's speakers
  args: ["--no-sandbox", "--disable-dev-shm-usage", "--autoplay-policy=no-user-gesture-required",
    "--disable-audio-output", ...(process.env.CHROME_ARGS?.split(" ") ?? [])],
  headless: process.env.CHROME_HEADLESS === "shell" ? "shell" : true,
  protocolTimeout: 120_000,
});
const page = await browser.newPage();
await page.emulate({ viewport: { width: 915, height: 412, deviceScaleFactor: 2.6, isMobile: true, hasTouch: true, isLandscape: true },
  userAgent: "Mozilla/5.0 (Linux; Android 14; Pixel 7a) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Mobile Safari/537.36" });
const problems = [], requests = [];
page.on("pageerror", e => problems.push(`pageerror: ${e.message}`));
page.on("console", m => { if (m.type() === "error") problems.push(`console: ${m.text()}`); });
page.on("requestfailed", r => problems.push(`requestfailed: ${r.url()}`));
page.on("request", r => requests.push(r.url()));
const cdp = await page.createCDPSession();

/** The centre-x and a point h (0 bottom .. 1 top) up a pedal, in CSS pixels. */
async function at(sel, h) {
  const r = await page.$eval(sel, e => { const b = e.getBoundingClientRect(); return { x: b.x, y: b.y, w: b.width, h: b.height }; });
  return { x: r.x + r.w / 2, y: r.y + r.h * (1 - h) };
}
const touch = (type, points) => cdp.send("Input.dispatchTouchEvent", { type, touchPoints: points.map((p, i) => ({ x: p.x, y: p.y, id: i + 1 })) });
const view = () => page.evaluate(() => globalThis.__enjoy.view());
async function tapEl(sel) { const p = await at(sel, 0.5); await touch("touchStart", [p]); await sleep(60); await touch("touchEnd", []); }

await page.goto(`http://localhost:${port}${BASE}enjoy?e2e`, { waitUntil: "load" });
await tapEl("button.start");
await page.waitForFunction(() => globalThis.__enjoy.view(), { timeout: 60_000 });
await sleep(1500);
const lvl = await page.evaluate(() => globalThis.__enjoy.level());
const idle = await view();
check("one tap starts the engine and the sound", !!idle && lvl > -60,
  `idle ${Math.round(idle?.rpm ?? 0)} rpm, sound ${lvl.toFixed(1)} dBFS`);

// ---- throttle: hold near the top, then lift ----
const thr = await at(".throttle .pedal", 0.85);
await touch("touchStart", [thr]);
await sleep(3000);
const going = await view();
check("holding the throttle revs the engine and moves the car",
  going.throttle > 0.7 && going.rpm > 1.5 * idle.rpm && going.kmh > 5,
  `throttle ${going.throttle.toFixed(2)}, ${Math.round(going.rpm)} rpm, ${going.kmh.toFixed(1)} km/h`);
await touch("touchEnd", []);
await sleep(400);
const lifted = await view();
check("lifting the throttle returns it to 0", lifted.throttle === 0, `throttle ${lifted.throttle}`);

// ---- brake ----
const v0 = lifted.kmh;
const brk = await at(".brake .pedal", 0.9);
await touch("touchStart", [brk]);
await sleep(1200);
const braking = await view();
await touch("touchEnd", []);
check("holding the brake slows the car", braking.brake > 0.8 && braking.kmh < v0 - 1,
  `brake ${braking.brake.toFixed(2)}, ${v0.toFixed(1)} -> ${braking.kmh.toFixed(1)} km/h`);

// ---- two thumbs ----
await sleep(600);
await touch("touchStart", [await at(".throttle .pedal", 0.5), await at(".brake .pedal", 0.5)]);
await sleep(500);
const both = await view();
await touch("touchEnd", []);
check("two thumbs: throttle and brake register together", both.throttle > 0.3 && both.brake > 0.3,
  `throttle ${both.throttle.toFixed(2)}, brake ${both.brake.toFixed(2)}`);

// ---- paddle ----
await sleep(800);
const g0 = (await view()).gear;
await tapEl("button.paddle.plus");
await sleep(1500);
const g1 = await view();
check("the shift paddle changes gear (and switches the automatic to manual shifting)",
  g1.gear !== g0 && g1.auto === false, `gear ${g0} -> ${g1.gear}, auto ${g1.auto}`);

await page.screenshot({ path: path.join(here, "out", "enjoy-landscape.png") });

// ---- portrait ----
await page.setViewport({ width: 412, height: 915, deviceScaleFactor: 2.6, isMobile: true, hasTouch: true, isLandscape: false });
await sleep(300);
const rotate = await page.$eval(".rotate", e => getComputedStyle(e).display !== "none");
check("in portrait, the page asks to be turned sideways", rotate);

check("no Pyodide or solver files are fetched", !requests.some(u => /pyodide|physics\.[0-9a-f]+\.json/.test(u)),
  `${requests.length} requests`);
check("no page errors, console errors or failed requests", problems.length === 0, problems.slice(0, 3).join(" | "));

await browser.close();
server.close();
const failed = results.filter(r => !r).length;
console.log(`\n${results.length - failed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
