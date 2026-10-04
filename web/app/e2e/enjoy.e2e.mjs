// End-to-end: Enjoy mode (Phase 5, ADR-012) on an emulated landscape phone,
// driven by real touch events (CDP Input.dispatchTouchEvent).
//
//   npm run build:pages && CHROME_PATH=/path/to/chrome npm run e2e:enjoy
//
// Engines: the Enjoy roster (ADR-012), starting on the hatchback.
// 1. One tap starts the engine and the sound.
// 2. Holding the throttle high revs the engine and moves the car; lifting
//    it returns the throttle to 0 (a real pedal, not the keyboard's sticky one).
// 3. Holding the brake slows the car.
// 4. Two thumbs at once: throttle and brake both register.
// 5. The shift paddle changes gear.
// 6. The dashboard shows the truth:
//    - both needles point where the readings say;
//    - the trip computer counts distance and labels its figures steady-state;
//    - a stalled manual lights the Stalled lamp;
//    - the heavy truck's speedometer has a slower scale than the hatchback's.
// 7. In portrait, the page asks to be turned sideways.
// 8. No Pyodide is fetched, and there are no page errors.
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

// ---- the dashboard ----
/** Each dial's needle angle next to what the digits say, read in one go. */
const dials = () => page.evaluate(() => {
  const ang = sel => Number(document.querySelector(`${sel} .needle`)?.getAttribute("transform")?.match(/rotate\(([-\d.e]+)\)/)?.[1]);
  const top = sel => Math.max(...[...document.querySelectorAll(`${sel} .num`)].map(t => Number(t.textContent)));
  const max = sel => Number(document.querySelector(`${sel} svg`)?.getAttribute("data-max"));
  const scale = sel => Number(document.querySelector(`${sel} svg`)?.getAttribute("data-label-scale"));
  // the digits drawn in the same render as the needles (the worker's latest
  // view can be a frame ahead of what is on screen)
  const num = sel => Number(document.querySelector(sel)?.textContent?.replace(/[^0-9.]/g, ""));
  return { rpm: num(".digits .rpm"), kmh: num(".digits .kmh"), tach: ang(".tach"), speedo: ang(".speedo"),
    tachTop: top(".tach") * scale(".tach"), speedTop: top(".speedo") * scale(".speedo"),
    tachMax: max(".tach"), speedMax: max(".speedo") };
});
await touch("touchStart", [await at(".throttle .pedal", 0.7)]);
await sleep(1500);
const d = await dials();
await touch("touchEnd", []);
// each dial publishes its scale (data-max); inferring it from the labels was wrong once
const angleOf = (v, max) => -120 + 240 * Math.min(1, Math.max(0, v / max));
const tachMax = d.tachMax, speedMax = d.speedMax;
const eT = Math.abs(d.tach - angleOf(d.rpm, tachMax)), eS = Math.abs(d.speedo - angleOf(d.kmh, speedMax));
// the digits are whole numbers: rounding moves a needle by < 0.5 of a unit
check("the needles point where the readings say, and each scale's end is labelled",
  d.rpm > 900 && eT < 0.5 && eS < 1 && d.speedTop === d.speedMax && d.tachTop === d.tachMax,
  `${Math.round(d.rpm)} rpm -> ${d.tach.toFixed(1)} deg (off ${eT.toFixed(2)}, tach labelled to ${d.tachTop} of ${d.tachMax}); ` +
  `${d.kmh.toFixed(1)} km/h -> ${d.speedo.toFixed(1)} deg (off ${eS.toFixed(2)}, speedo labels to ${d.speedTop})`);
const trip = await page.evaluate(() => ({ km: document.querySelector(".trip-km")?.textContent, note: document.querySelector(".trip .note")?.textContent,
  v: globalThis.__enjoy.view() }));
check("the trip computer counts the drive, labelled steady-state (FINDING-009)",
  trip.v.trip_km > 0.02 && Number(trip.km) === Number(trip.v.trip_km.toFixed(1)) && /steady-state/.test(trip.note ?? ""),
  `${trip.v.trip_km.toFixed(3)} km, ${trip.v.trip_L.toFixed(3)} L; shows "${trip.km}"`);

// a manual, stalled: clutch down, 1st gear, clutch up with no throttle
await tapEl(".seg button:nth-child(2)");                 // Manual (stops the engine)
await page.waitForSelector("button.start");              // re-rendered: tapping before it raced once
await tapEl("button.start");
await page.waitForFunction(() => globalThis.__enjoy.view()?.trans === "manual", { timeout: 30_000 });
await sleep(800);
// brake and clutch held, then a tap on the + paddle; then the clutch comes up
// with the brake still on, which must stall it (a light car on the flat may
// otherwise idle away in 1st: the roster hatchback does)
const brake = await at(".brake .pedal", 0.95), clutch = await at(".clutch .pedal", 0.95), plus = await at("button.paddle.plus", 0.5);
await touch("touchStart", [brake]);
await touch("touchStart", [brake, clutch]);
await sleep(300);
await touch("touchStart", [brake, clutch, plus]);         // a third finger on the paddle (it acts on press)
await sleep(400);
const shifted = await view();
// CDP cannot lift one finger of several: a touchMove that leaves a point out
// keeps it pressed (measured: the clutch stayed at 1.00), and touchEnd lifts
// them all. So lift all three and put the brake straight back down
await touch("touchEnd", []);
await touch("touchStart", [brake]);
check("with the clutch held, the paddle shifts (two thumbs)", shifted.gear !== "N",
  `gear ${shifted.gear}, clutch ${shifted.clutch.toFixed(2)}`);
await page.waitForFunction(() => globalThis.__enjoy.view()?.stalled, { timeout: 8000 }).catch(() => {});
await touch("touchEnd", []);
const stall = await page.evaluate(() => ({ stalled: globalThis.__enjoy.view().stalled, gear: globalThis.__enjoy.view().gear,
  lit: document.querySelector(".lamp.stall")?.classList.contains("on"), others: [...document.querySelectorAll(".lamp.on")].map(l => l.textContent.trim()) }));
check("a stalled manual lights the Stalled lamp, and no lamp lights falsely",
  stall.stalled && stall.lit && stall.others.every(t => t === "Stalled"),
  `stalled ${stall.stalled} in gear ${stall.gear}; lit: ${stall.others.join(", ") || "none"}`);

// the dial scale follows the vehicle
const hatchTop = d.speedTop;
await page.select('select[aria-label="Engine"]', "truck127");      // the roster's truck (ADR-012)
await tapEl(".seg button:nth-child(1)");                 // Auto again: the stall test left it in Manual
await page.waitForSelector("button.start");
await tapEl("button.start");
await page.waitForFunction(() => globalThis.__enjoy.view(), { timeout: 60_000 });
await sleep(800);
const truck = await dials();
check("the truck's dials: a slower speedometer than the hatchback's, both scales labelled to the end",
  truck.speedTop < hatchTop && truck.speedTop >= 80 && truck.speedTop <= 160
  && truck.speedTop === truck.speedMax && truck.tachTop === truck.tachMax,
  `speedometer to ${truck.speedTop} km/h (truck) vs ${hatchTop} (hatchback); tach labelled to ${truck.tachTop} of ${truck.tachMax} rpm`);
await page.screenshot({ path: path.join(here, "out", "enjoy-truck.png") });

// the truck flat out from a standstill: the charge air heats and the model
// cuts fuel (the 5% rule once lit Derate here, at 66 C); the lamp means
// protection, so it must stay dark below the charge-air threshold
await touch("touchStart", [await at(".throttle .pedal", 0.95)]);
// held until the model really cuts fuel for the warm charge air (not a guessed duration)
await page.waitForFunction(() => globalThis.__enjoy.view()?.derate < 0.95, { timeout: 30_000, polling: 100 }).catch(() => {});
const hot = await page.evaluate(() => ({ v: globalThis.__enjoy.view(),
  lit: [...document.querySelectorAll(".lamp.on")].map(l => l.textContent.trim()) }));
await touch("touchEnd", []);
check("the truck flat out: the fuel cut from a warm charge cooler does not light Derate",
  hot.v.derate < 0.95 && hot.v.T_charge < 353.15 && !hot.lit.includes("Derate"),
  `charge ${(hot.v.T_charge - 273.15).toFixed(0)} C, derate ${hot.v.derate.toFixed(3)}, lit: ${hot.lit.join(", ") || "none"}`);

// ---- a custom engine's grid file (ADR-014) ----
// the hatchback's grid, relabelled as a custom engine that drives the SUV: if
// the worker honours the file's "vehicle", the dash reports the SUV
const gridsDir = path.join(here, "..", "public", "grids");
const custom = JSON.parse(fs.readFileSync(path.join(gridsDir, "hatch15.json"), "utf8"));
Object.assign(custom, { preset: "testeng", name: "Test engine", custom: true, vehicle: "crdi22" });
fs.mkdirSync(path.join(here, "out"), { recursive: true });
const customPath = path.join(here, "out", "custom.grid.json"), badPath = path.join(here, "out", "not-a-grid.json");
fs.writeFileSync(customPath, JSON.stringify(custom));
fs.writeFileSync(badPath, JSON.stringify({ hello: 1 }));
if (await page.$("button.stop")) await tapEl("button.stop");
await page.waitForSelector("input[type=file]");
await (await page.$("input[type=file]")).uploadFile(badPath);
await page.waitForSelector(".import-err", { timeout: 5000 }).catch(() => {});
const badMsg = await page.$eval(".import-err", e => e.textContent).catch(() => "");
check("a file that is not a grid is refused, with the reason", /not a grid file/.test(badMsg), badMsg.trim());
await (await page.$("input[type=file]")).uploadFile(customPath);
await page.waitForFunction(() => [...document.querySelectorAll("select option")].some(o => o.selected && /Test engine/.test(o.textContent)),
  { timeout: 5000 }).catch(() => {});
await tapEl("button.start");
await page.waitForFunction(() => globalThis.__enjoy.info()?.vehicle, { timeout: 60_000 }).catch(() => {});
const cinfo = await page.evaluate(() => globalThis.__enjoy.info());
const csel = await page.$eval("select", s => s.selectedOptions[0]?.textContent ?? "");
check("an imported custom engine drives, in the vehicle its file names", /Test engine/.test(csel) && /SUV/.test(cinfo?.vehicle ?? ""),
  `engine "${csel.trim()}", vehicle "${cinfo?.vehicle}"`);

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
