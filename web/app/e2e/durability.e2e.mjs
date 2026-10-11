// The durability page (Phase 6, ADR-015) in a real headless Chrome, against
// native Python: crdi15 aged 100 h in 50 h blocks in the browser's worker; the
// last block's life consumed, bore wear and rated torque as native
// durability_run's; four plots; Stop halts a long run between blocks.
//
//   npm run build:pages && CHROME_PATH=... npm run e2e:durability      (~2 min)
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
try {
  ref = JSON.parse(process.env.NATIVE_DURABILITY ?? execFileSync("python3", [path.join(here, "native_durability.py")],
    { cwd: path.resolve(here, "..", "..", ".."), encoding: "utf8" }));
} catch (e) {
  console.log(`FAIL  no native reference: ${e.message.split("\n")[0]}`);
  server.close();
  process.exit(1);
}

const browser = await puppeteer.launch({ timeout: 120_000,   // Chrome's start: 30 s timed out on loaded CI runners (#108, #115)
  executablePath: process.env.CHROME_PATH, headless: true, protocolTimeout: 10 * 60_000,
  args: ["--no-sandbox", "--disable-dev-shm-usage"] });
const page = await browser.newPage();
await page.setViewport({ width: 1200, height: 1000 });
const problems = [];
page.on("pageerror", e => problems.push(`pageerror: ${e.message}`));
page.on("console", m => { if (m.type() === "error") problems.push(`console: ${m.text()}`); });

await page.goto(`http://localhost:${port}${BASE}durability`, { waitUntil: "load" });
await page.waitForSelector("button.run:not([disabled])", { timeout: 180_000 });
const cost = await page.$eval("p.cost", e => e.textContent.replace(/\s+/g, " ").trim());
const hoursDefault = await page.$eval("input.hours-in", e => Number(e.value));
check("the default is 1,000 h, its cost stated before it starts", hoursDefault === 1000 && /1,?000 hours take about 8 min/.test(cost), `${hoursDefault} h; "${cost.slice(0, 110)}…"`);

const setValue = async (sel, v) => page.$eval(sel, (el, val) => { el.value = String(val); el.dispatchEvent(new Event("change", { bubbles: true })); }, v);
await setValue("input.hours-in", 100);
await setValue("input.step-in", 50);
await page.$eval("button.run", b => b.click());
await page.waitForFunction(() => /100 hours run/.test(document.querySelector(".status")?.textContent ?? ""), { timeout: 5 * 60_000, polling: 500 }).catch(() => {});
const table = await page.$$eval(".durability-data tr", trs => Object.fromEntries(trs.map(tr => [tr.querySelector("th")?.textContent.trim(), tr.querySelector("td")?.textContent.trim()])));
const num = s => Number(String(s ?? "").match(/[\d.,]+/)?.[0]?.replace(/,/g, "") ?? NaN);
const life = num(table["Life consumed (0 = new)"]), bore = num(table["Bore wear at TDC"]), torque = num(table["Rated torque, power"]);
check("after 100 h: life consumed, bore wear and rated torque are native durability_run's, to the digits shown",
  life.toFixed(3) === ref.health.toFixed(3) && bore.toFixed(3) === ref.bore_wear_um.toFixed(3) && torque.toFixed(1) === ref.torque.toFixed(1),
  `page ${life}%, ${bore} µm, ${torque} N·m; native ${ref.health.toFixed(3)}%, ${ref.bore_wear_um.toFixed(3)} µm, ${ref.torque.toFixed(1)} N·m`);
const plots = await page.$$eval("figure.plot", fs => fs.map(f => ({ t: f.querySelector("figcaption")?.textContent.trim(),
  y: f.querySelectorAll("text.axis")[1]?.textContent.trim(), n: f.querySelector("polyline")?.getAttribute("points").trim().split(/\s+/).length })));
check("four plots, each from new through the 2 blocks; life consumed labelled 0 = new (FINDING-019)",
  plots.length === 4 && plots.every(p => p.n === 3) && /0 = new/.test(plots[0]?.y ?? ""), JSON.stringify(plots.map(p => [p.t, p.n])));
await page.screenshot({ path: path.join(out, "durability.png"), fullPage: true });

// Stop: a 1,000 h run halted after its first block
await setValue("input.hours-in", 1000);
await page.$eval("button.run", b => b.click());
// (the first run left "100 hours run." behind: so the check needs this run seen running, of 1,000)
const seenRunning = await page.waitForFunction(() => /Running: [1-9][\d,]* of 1,?000/.test(document.querySelector(".status")?.textContent ?? ""),
  { timeout: 3 * 60_000, polling: 300 }).then(() => true).catch(() => false);
await page.$eval("button.run", b => b.click());   // reads Stop while running
await page.waitForFunction(() => !/Running/.test(document.querySelector(".status")?.textContent ?? ""), { timeout: 3 * 60_000, polling: 300 }).catch(() => {});
const stoppedAt = await page.$eval(".status", e => e.textContent.replace(/\s+/g, " ").trim());
const caption = await page.$eval(".durability-data caption", e => e.textContent.trim()).catch(() => "");
const hoursRun = num(stoppedAt);
check("Stop halts a 1,000 h run between blocks", seenRunning && hoursRun >= 50 && hoursRun < 1000 && caption === `After ${hoursRun} hours`,
  `seen running of 1,000: ${seenRunning}; "${stoppedAt}"; table "${caption}"`);
check("no page errors or console errors", problems.length === 0, problems.slice(0, 3).join(" | "));

await browser.close();
server.close();
const failed = results.filter(r => !r).length;
console.log(`\n${results.length - failed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
