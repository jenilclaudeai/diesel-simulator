// Custom engines, end to end in Chrome (ADR-014 step 3): on the Dyno page a
// custom engine's drivable grid is built by the page's worker pool (a 2 x 2
// grid through the e2e-only ?gridsize hook, so it takes minutes, not half an
// hour), stopped part-way and resumed from what it kept, saved to "Your
// engines", then driven on /enjoy in the vehicle the engine names.
//
//   npm run build:pages && CHROME_PATH=... npm run e2e:custom     (~6-10 min)
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
const browser = await puppeteer.launch({
  executablePath: process.env.CHROME_PATH, headless: true, protocolTimeout: 45 * 60_000,
  args: ["--no-sandbox", "--disable-dev-shm-usage", "--disable-audio-output", "--autoplay-policy=no-user-gesture-required"],
});
const page = await browser.newPage();
await page.setViewport({ width: 1100, height: 900 });
const problems = [];
page.on("pageerror", e => problems.push(`pageerror: ${e.message}`));
page.on("console", m => { if (m.type() === "error") problems.push(`console: ${m.text()}`); });
const t0 = Date.now();
const status = () => page.$eval(".build-status", e => e.textContent.replace(/\s+/g, " ").trim()).catch(() => "");

await page.goto(`http://localhost:${port}${BASE}?e2e&gridsize=2x2`, { waitUntil: "load" });
await page.waitForFunction(() => { const s = document.querySelector("select"); return s && !s.disabled && s.options.length > 1; },
  { timeout: 120_000, polling: 250 });
await page.select("select", "__custom");
await page.waitForSelector("button.build-drivable:not([disabled])", { timeout: 60_000 });

// build, and stop once the two fuel rows are kept
await page.click("button.build-drivable");
await page.waitForFunction(() => /\b([2-9]|10) of 10\b/.test(document.querySelector(".build-status")?.textContent ?? ""),
  { timeout: 20 * 60_000, polling: 1000 }).catch(() => {});
const before = await status();
const tStop = Date.now();
await page.click("button.cancel-build").catch(() => {});
await page.waitForSelector(".build-err", { timeout: 10 * 60_000 }).catch(() => {});
const stopMs = Date.now() - tStop;
const stopped = await page.$eval(".build-err", e => e.textContent.trim()).catch(() => "");
check("a build stopped part-way says it keeps what it finished", /kept/.test(stopped), `${before} -> "${stopped}"`);
// B-04: Stop used to wait for every running piece (up to a whole row, minutes)
check("Stop answers at once, mid-piece", stopMs < 5000, `${stopMs} ms`);

// carry on: the resumed build starts from what was kept, then saves
await page.click("button.build-drivable");
await page.waitForFunction(() => /from before/.test(document.querySelector(".build-status")?.textContent ?? "")
  || document.querySelector(".built"), { timeout: 10 * 60_000, polling: 250 }).catch(() => {});
const resumedText = await status();
await page.waitForSelector(".built, .build-err", { timeout: 20 * 60_000 }).catch(() => {});
const built = await page.$eval(".built", e => e.textContent.replace(/\s+/g, " ").trim()).catch(() => "");
check("the resumed build carries on from what it kept, and saves the engine", /from before/.test(resumedText)
  && /Saved to your engines: 2\.0 L four, 140 ps, in the 1\.5 t compact/.test(built), `"${resumedText}" -> "${built}"`);
await page.screenshot({ path: path.join(out, "custom-built.png"), fullPage: true });

// drive it: the Drive it link opens /enjoy with the engine chosen
await page.click(".built a[href*='/enjoy']");
await page.waitForFunction(() => location.pathname.endsWith("/enjoy"), { timeout: 10_000 });
await page.goto(page.url() + "&e2e", { waitUntil: "load" });           // the e2e hooks
await page.waitForFunction(() => [...document.querySelectorAll("select option")].some(o => o.selected && /2\.0 L four/.test(o.textContent)),
  { timeout: 10_000 }).catch(() => {});
const chosen = await page.$eval("select", s => s.selectedOptions[0]?.textContent.trim() ?? "");
await page.setViewport({ width: 915, height: 412, isMobile: true, hasTouch: true, isLandscape: true });
await page.click("button.start");
await page.waitForFunction(() => globalThis.__enjoy?.info()?.vehicle && globalThis.__enjoy.view()?.rpm > 0, { timeout: 60_000 }).catch(() => {});
const info = await page.evaluate(() => ({ vehicle: globalThis.__enjoy?.info()?.vehicle, rpm: Math.round(globalThis.__enjoy?.view()?.rpm ?? 0) }));
check("Drive it opens /enjoy with the saved engine, which drives in its own vehicle",
  /2\.0 L four/.test(chosen) && /1\.5 t compact/.test(info.vehicle ?? "") && info.rpm > 500,
  `chose "${chosen}", vehicle "${info.vehicle}", idling at ${info.rpm} rpm`);
await page.screenshot({ path: path.join(out, "custom-enjoy.png") });

check("no page errors or console errors", problems.length === 0, problems.slice(0, 3).join(" | "));
await browser.close();
server.close();
const failed = results.filter(r => !r).length;
console.log(`\n${results.length - failed} passed, ${failed} failed  (${((Date.now() - t0) / 1000).toFixed(0)} s)`);
process.exit(failed ? 1 : 0);
