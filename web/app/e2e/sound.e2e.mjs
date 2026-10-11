// End-to-end: the engine's sound (Phase 4) in a real headless Chrome.
//
//   npm run build:pages && CHROME_PATH=/path/to/chrome npm run e2e:sound
//
// The drive page's AudioWorklet runs @dieselsim/physics's LiveSynth (held to
// dieselsim/livesound.py by fixtures/sound.json) on crdi15's prebuilt grid,
// fed by the 60 Hz loop. Checked in the browser, on what the worklet
// actually renders (captured from the audio thread):
// 1. sound starts from a real click, with no worklet error, and is not silent;
// 2. at idle, the firing harmonics (n_cyl/2 x rpm/60 and multiples 2-4) stand
//    above the spectrum's floor, at the rpm the loop reports;
// 3. revved in neutral they move with the rpm -- the pitch follows the engine;
// 4. keys go to the engine, not to the last-clicked button (space would
//    otherwise turn the sound off);
// 5. changing the microphone changes what is heard;
// 6. no page errors, console errors or failed requests.
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

/** Power at frequency f (Hann-windowed Goertzel). */
function power(x, rate, f) {
  const n = x.length, w = 2 * Math.PI * f / rate, c = 2 * Math.cos(w);
  let s1 = 0, s2 = 0;
  for (let i = 0; i < n; i++) {
    const s0 = x[i] * (0.5 - 0.5 * Math.cos(2 * Math.PI * i / (n - 1))) + c * s1 - s2;
    s2 = s1; s1 = s0;
  }
  return s1 * s1 + s2 * s2 - c * s1 * s2;
}
/**
 * Each of the first k firing harmonics against the spectrum's floor, in dB:
 * the peak is the largest 0.5 Hz bin within 2 Hz of h * f0 (the rpm is read
 * before and after the capture), the floor the median of every bin more than
 * 4 Hz from any harmonic. (A single-bin floor was tried first: a noise-like
 * floor's single bin varies by ~5 dB, and the check flaked at idle.)
 */
function harmonics(x, rate, f0, k = 4, at = f0) {
  const lo = 0.5 * f0, hi = (k + 0.5) * f0, bins = [];
  for (let f = lo; f <= hi; f += 0.5) bins.push([f, power(x, rate, f)]);
  const near = (f, g) => { for (let h = 1; h <= k + 1; h++) if (Math.abs(f - h * g) <= 4) return true; return false; };
  const floor = bins.filter(([f]) => !near(f, f0)).map(([, p]) => p).sort((a, b) => a - b);
  const med = floor[Math.floor(floor.length / 2)];
  const db = [];
  for (let h = 1; h <= k; h++) {
    let pk = 0;
    for (let f = h * at - 2; f <= h * at + 2; f += 0.5) pk = Math.max(pk, power(x, rate, f));
    db.push(10 * Math.log10(pk / med));
  }
  return db;
}

const N_CYL = 4;                    // crdi15
const browser = await puppeteer.launch({ timeout: 120_000,   // Chrome's start: 30 s timed out on loaded CI runners (#108, #115)
 
  executablePath: process.env.CHROME_PATH,
  // a fake audio sink that runs in real time: the test judges what the
  // worklet renders, not whether this machine's speakers are awake (a stuck
  // macOS output once left every worklet uncalled, and CI has no device)
  args: ["--no-sandbox", "--disable-dev-shm-usage", "--autoplay-policy=no-user-gesture-required",
    ...(process.env.SOUND_REAL_DEVICE ? [] : ["--disable-audio-output"]),
    ...(process.env.CHROME_ARGS?.split(" ") ?? [])],
  headless: process.env.CHROME_HEADLESS === "shell" ? "shell" : true,
  protocolTimeout: 120_000,
});
const page = await browser.newPage();
const problems = [];
page.on("pageerror", e => problems.push(`pageerror: ${e.message}`));
page.on("console", m => { if (m.type() === "error") problems.push(`console: ${m.text()}`); });
page.on("requestfailed", r => problems.push(`requestfailed: ${r.url()}`));

await page.goto(`http://localhost:${port}${BASE}drive?e2e`, { waitUntil: "load" });
await page.select("select", "crdi15");
await page.click("button.run");
await page.waitForSelector(".rpm", { timeout: 60_000 });
await page.click("button.sound-toggle");
await page.waitForFunction(() => document.querySelector("button.sound-toggle")?.textContent?.includes("Sound off")
  || document.querySelector(".err"), { timeout: 30_000 });
await page.evaluate(() => globalThis.__drive.sound.mic("exhaust_tip"));
// time from the click to the worklet's first level report: it decodes the grid first
const tClick = Date.now();
await page.waitForFunction(() => Number.isFinite(globalThis.__drive.sound.level()) || globalThis.__drive.sound.error(),
  { timeout: 20_000, polling: 50 }).catch(() => {});
const startMs = Date.now() - tClick;
await sleep(1500);                       // let the shape trackers (0.3 s) and the source glide settle
const err = await page.evaluate(() => globalThis.__drive.sound.error() ?? null);
const level = await page.evaluate(() => globalThis.__drive.sound.level());
check("sound starts from a click and is not silent", !err && level > -60,
  err ?? `level ${level.toFixed(1)} dBFS at idle; first sound ${startMs} ms after the click`);

const rpm = () => page.$eval(".rpm", e => Number(e.textContent.replace(/[^0-9]/g, "")));
async function listen(seconds) {
  const r0 = await rpm();
  // a capture that never returns (the worklet stopped) is a failure, not a hang
  const cap = await page.evaluate(async s => {
    const m = await Promise.race([globalThis.__drive.sound.capture(s), new Promise(r => setTimeout(() => r(null), 10_000))]);
    return m ? { rate: m.rate, samples: Array.from(m.samples) } : { rate: 44100, samples: [] };
  }, seconds);
  const r1 = await rpm();
  return { ...cap, r0, r1 };
}

// ---- idle ----
const idle = await listen(2.0);
const fIdle = N_CYL / 2 * (idle.r0 + idle.r1) / 2 / 60;
const hIdle = idle.samples.length ? harmonics(idle.samples, idle.rate, fIdle) : [-Infinity];
// harmonics 2-4 only: an I4 at ~780 rpm fires at ~26 Hz, below the exhaust
// chain's 35 Hz high-pass and the tip mic's 28 Hz (acoustics.py), so the
// fundamental is attenuated by the model itself and is reported, not asserted
// a capture must have samples: an empty one made Math.min() over no values
// +Infinity, and this check once passed on silence
check("at idle, the firing harmonics stand out at the loop's rpm",
  idle.samples.length > 0 && Math.abs(idle.r1 - idle.r0) < 0.03 * idle.r0 && Math.min(...hIdle.slice(1)) > 6,
  `${idle.r0}-${idle.r1} rpm, firing ${fIdle.toFixed(1)} Hz: harmonics 1-4 at ${hIdle.map(d => d.toFixed(1)).join(", ")} dB over the floor`);

// ---- revved in neutral ----
await page.keyboard.press("n");
await page.keyboard.press(" ");
await sleep(3500);
// space is full throttle; a focused button would take it instead (restart, or sound off)
const stillOn = await page.$eval("button.sound-toggle", e => e.textContent.includes("Sound off"));
check("keys drive the engine, not the last-clicked button", stillOn, stillOn ? "sound still on after space" : "space pressed a button");
const rev = await listen(0.5);
const fRev = N_CYL / 2 * (rev.r0 + rev.r1) / 2 / 60;
const hRev = rev.samples.length ? harmonics(rev.samples, rev.rate, fRev, 3) : [-Infinity];
// the idle pitch, where it no longer is: against the same (revved) floor
const hWrong = rev.samples.length ? harmonics(rev.samples, rev.rate, fRev, 3, fIdle) : [Infinity];
check("revved, the harmonics move with the rpm", rev.samples.length > 0 && rev.r0 > 1.5 * idle.r0 && Math.abs(rev.r1 - rev.r0) < 0.05 * rev.r0
  && Math.min(...hRev) > 6 && Math.max(...hWrong) < Math.min(...hRev),
  `${rev.r0}-${rev.r1} rpm, firing ${fRev.toFixed(1)} Hz: ${hRev.map(d => d.toFixed(1)).join(", ")} dB; ` +
  `at the idle pitch ${hWrong.map(d => d.toFixed(1)).join(", ")} dB`);

// ---- microphone ----
const before = await page.evaluate(() => globalThis.__drive.sound.level());
await page.keyboard.press("4");                                   // cabin
await sleep(1500);
const cabin = await page.evaluate(() => globalThis.__drive.sound.level());
check("changing the microphone changes what is heard", Math.abs(cabin - before) > 1,
  `exhaust tip ${before.toFixed(1)} dBFS -> cabin ${cabin.toFixed(1)} dBFS (key 4)`);

check("no page errors, console errors or failed requests", problems.length === 0, problems.slice(0, 3).join(" | "));

await browser.close();
server.close();
const failed = results.filter(r => !r).length;
console.log(`\n${results.length - failed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
