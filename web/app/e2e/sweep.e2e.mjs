// The sweep page (Phase 6, ADR-015) in a real headless Chrome, against native
// Python: crdi15's compression ratio from 15 to 18 in 4 points at full load,
// each point's torque as native Python's; the plots drawn; Stop halts a run
// part-way.
//
//   npm run build:pages && CHROME_PATH=... npm run e2e:sweep      (~1 min)
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
  ref = JSON.parse(process.env.NATIVE_SWEEP ?? execFileSync("python3", [path.join(here, "native_sweep.py")],
    { cwd: path.resolve(here, "..", "..", ".."), encoding: "utf8" }));
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

await page.goto(`http://localhost:${port}${BASE}sweep`, { waitUntil: "load" });
await page.waitForFunction(() => /This engine:/.test(document.body.textContent), { timeout: 180_000, polling: 250 });
const setValue = async (sel, v) => page.$eval(sel, (el, val) => { el.value = String(val); el.dispatchEvent(new Event("change", { bubbles: true })); }, v);
await setValue("input.from-in", 15);
await setValue("input.to-in", 18);
await setValue("input.steps-in", 4);
const shownRpm = await page.$eval("input.rpm-in", e => Number(e.value));
const planNote = await page.$eval("p.note", e => e.textContent.replace(/\s+/g, " ").trim());
check("the plan: compression ratio 15, 16, 17, 18 at the default speed", /15, 16, 17, 18/.test(planNote) && shownRpm === ref.rpm,
  `"${planNote}"; ${shownRpm} rpm (native ${ref.rpm})`);

await page.$eval("button.run", b => b.click());
await page.waitForFunction(() => document.querySelectorAll(".sweep-data tbody tr").length === 4 && !/Solving/.test(document.querySelector(".status")?.textContent ?? ""),
  { timeout: 5 * 60_000, polling: 500 }).catch(() => {});
const rows = await page.$$eval(".sweep-data tbody tr", trs => trs.map(tr => [...tr.querySelectorAll("td")].map(td => td.textContent.trim())));
const torques = rows.map(r => Number(r[1].replace(/,/g, "")));
const want = ref.torque.map(t => Number(t.toFixed(1)));
check("each point's torque is native Python's, to the digit shown", JSON.stringify(torques) === JSON.stringify(want),
  `page ${torques.join(", ")}; native ${want.join(", ")} N·m`);
const plots = await page.$$eval("figure.plot", fs => fs.map(f => ({ t: f.querySelector("figcaption")?.textContent.trim(),
  n: f.querySelector("polyline")?.getAttribute("points").trim().split(/\s+/).length })));
check("two plots of the 4 points, the economy one labelled steady-state",
  plots.length === 2 && plots.every(p => p.n === 4) && /steady state/.test(plots[1]?.t ?? ""), JSON.stringify(plots));
const resolution = await page.$eval("p.resolution", e => e.textContent.replace(/\s+/g, " ").trim()).catch(() => "");
check("the page says how far apart points must be to mean anything: crdi15's measured 5.8% (this build's accuracy table)",
  /noise, not physics/.test(resolution) && /5\.8%/.test(resolution), `"${resolution.slice(0, 160)}…"`);
await page.screenshot({ path: path.join(out, "sweep.png"), fullPage: true });

// Stop: a second run halted after its first point
await page.$eval("button.run", b => b.click());
await page.waitForFunction(() => document.querySelectorAll(".sweep-data tbody tr").length === 1, { timeout: 120_000, polling: 200 }).catch(() => {});
await page.$eval("button.run", b => b.click());   // the same button reads Stop while running
await page.waitForFunction(() => !/Solving/.test(document.querySelector(".status")?.textContent ?? ""), { timeout: 120_000, polling: 300 }).catch(() => {});
const afterStop = await page.$$eval(".sweep-data tbody tr", trs => trs.length);
check("Stop halts a sweep between points", afterStop >= 1 && afterStop < 4, `${afterStop} of 4 points`);
check("no page errors or console errors", problems.length === 0, problems.slice(0, 3).join(" | "));

await browser.close();
server.close();
const failed = results.filter(r => !r).length;
console.log(`\n${results.length - failed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
