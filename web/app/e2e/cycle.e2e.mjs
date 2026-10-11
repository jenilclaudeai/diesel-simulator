// The cycle page (Phase 6, ADR-015) in a real headless Chrome, against native
// Python: the page's default point for crdi15 solved in the browser's worker,
// its numbers checked against e2e/native_cycle.py (in standard air and in the plateau
// environment preset, Phase 7), its four plots drawn with
// the right number of points, its events marked, its figures labelled.
//
//   npm run build:pages && CHROME_PATH=... npm run e2e:cycle      (~1 min)
//
// NATIVE_CYCLE='{"rpm":..,"p_max_bar":..,"mfb50":..,"imep_net_bar":..,"theta_pmax":..}'
// supplies the reference; without it the script runs e2e/native_cycle.py
// (python3 with numpy), and fails rather than skipping if it can't.
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
  ref = JSON.parse(process.env.NATIVE_CYCLE ?? execFileSync("python3", [path.join(here, "native_cycle.py")],
    { cwd: path.resolve(here, "..", "..", ".."), encoding: "utf8" }));
} catch (e) {
  console.log(`FAIL  no native reference: ${e.message.split("\n")[0]}`);
  server.close();
  process.exit(1);
}

const browser = await puppeteer.launch({ timeout: 120_000,   // Chrome's start: 30 s timed out on loaded CI runners (#108, #115)
 
  executablePath: process.env.CHROME_PATH, headless: true, protocolTimeout: 10 * 60_000,
  args: ["--no-sandbox", "--disable-dev-shm-usage"],
});
const page = await browser.newPage();
await page.setViewport({ width: 1200, height: 1000 });
const problems = [];
page.on("pageerror", e => problems.push(`pageerror: ${e.message}`));
page.on("console", m => { if (m.type() === "error") problems.push(`console: ${m.text()}`); });

await page.goto(`http://localhost:${port}${BASE}cycle`, { waitUntil: "load" });
await page.waitForFunction(() => { const s = document.querySelector("select"); return s && !s.disabled && s.options.length > 1; },
  { timeout: 180_000, polling: 250 });
const rpmShown = await page.$eval("input.rpm-in", e => Number(e.value));
check("the page's default point is crdi15 at 60% of idle-to-rated", rpmShown === ref.rpm, `${rpmShown} rpm (native ${ref.rpm})`);

const t0 = Date.now();
await page.click("button.run");
await page.waitForSelector(".cycle-data", { timeout: 5 * 60_000 });
const solveS = (Date.now() - t0) / 1000;
const shown = await page.evaluate(() => {
  const row = name => [...document.querySelectorAll(".cycle-data tr")].find(tr => tr.querySelector("th")?.textContent.trim() === name)
    ?.querySelector("td")?.textContent.trim() ?? "";
  return { peak: row("Peak pressure"), mfb50: row("50% burned (MFB50)"), imep: row("IMEP, net (gross)"), bsfc: row("BSFC (steady state)"),
    figures: [...document.querySelectorAll("figure.plot")].map(f => ({
      title: f.querySelector("figcaption")?.textContent.trim(),
      aria: f.querySelector("svg")?.getAttribute("aria-label") ?? "",
      lines: [...f.querySelectorAll("polyline")].map(p => p.getAttribute("points").trim().split(/\s+/).length),
      markers: [...f.querySelectorAll(".mlabel")].map(t => t.textContent.trim()),
      shade: !!f.querySelector("rect.shade"),
    })) };
});
const num = s => Number((s.match(/[+−-]?[\d.,]+/)?.[0] ?? "NaN").replace("−", "-").replace(/,/g, ""));
const peakBar = num(shown.peak), mfb = num(shown.mfb50), imep = num(shown.imep);
check("peak pressure, MFB50 and net IMEP as native Python, to the digits shown",
  peakBar.toFixed(1) === ref.p_max_bar.toFixed(1) && mfb.toFixed(1) === ref.mfb50.toFixed(1) && imep.toFixed(2) === ref.imep_net_bar.toFixed(2),
  `page: ${shown.peak}, MFB50 ${shown.mfb50}, IMEP ${shown.imep}; native: ${ref.p_max_bar.toFixed(1)} bar at +${ref.theta_pmax}°, MFB50 ${ref.mfb50}, IMEP ${ref.imep_net_bar.toFixed(2)}`);
check("economy is labelled steady-state (FINDING-009)", /steady state/i.test(await page.$eval(".cycle-data", e => e.textContent))
  && /g\/kWh/.test(shown.bsfc), shown.bsfc);

const f = Object.fromEntries(shown.figures.map(x => [x.title, x]));
const pv = f["Pressure against volume (log-log)"], pt = f["Pressure against crank angle"],
  hr = f["Heat release rate"], vl = f["Valve lift"];
check("four plots, each with an accessible description", shown.figures.length === 4 && shown.figures.every(x => x.aria.length > 30),
  shown.figures.map(x => x.title).join(" | "));
check("each trace has its window's points: p–V 720 and 720, p–θ −180..180 361 and 361, heat release −40..100 141, lift 720 and 720",
  JSON.stringify(pv?.lines) === "[720,720]" && JSON.stringify(pt?.lines) === "[361,361]" && JSON.stringify(hr?.lines) === "[141]"
  && JSON.stringify(vl?.lines) === "[720,720]",
  `p–V ${pv?.lines}, p–θ ${pt?.lines}, HRR ${hr?.lines}, lift ${vl?.lines}`);
check("events marked: main SOI, main SOC, MFB50 and p max on p–θ; the four valve events and the overlap on lift",
  ["main SOI", "main SOC", "MFB50", "p max"].every(m => pt?.markers.includes(m)) && ["EVO", "EVC", "IVO", "IVC"].every(m => vl?.markers.includes(m)) && vl?.shade,
  `p–θ ${pt?.markers.join(",")}; lift ${vl?.markers.join(",")}, overlap ${vl?.shade}`);
check("it solved in the browser in a reasonable time", solveS < 120, `${solveS.toFixed(1)} s`);
await page.screenshot({ path: path.join(out, "cycle.png"), fullPage: true });

// Phase 7 (ADR-016): the same point in Leh in June (3500 m). The choice marks the result out of
// date, and solved again it is native Python's for the plateau preset's overrides.
let refPlateau;
try {
  refPlateau = JSON.parse(process.env.NATIVE_CYCLE_PLATEAU ?? execFileSync("python3", [path.join(here, "native_cycle.py")],
    { cwd: path.resolve(here, "..", "..", ".."), encoding: "utf8", env: { ...process.env, ENVIRONMENT: "plateau" } }));
} catch (e) { refPlateau = { p_max_bar: NaN, imep_net_bar: NaN }; }
await page.select("select.env", "plateau");
await page.waitForSelector("app-spec-status .stale", { timeout: 5000 }).catch(() => {});
const envStale = await page.$eval("app-spec-status .stale", e => e.textContent.replace(/\s+/g, " ").trim()).catch(() => "");
const envNote = await page.$eval("p.env-note", e => e.textContent.replace(/\s+/g, " ").trim()).catch(() => "");
await page.click("button.run");
await page.waitForFunction(() => !document.querySelector("app-spec-status .stale") && !document.querySelector("button.run[disabled]"),
  { timeout: 5 * 60_000, polling: 500 }).catch(() => {});
const high = await page.evaluate(() => {
  const row = name => [...document.querySelectorAll(".cycle-data tr")].find(tr => tr.querySelector("th")?.textContent.trim() === name)
    ?.querySelector("td")?.textContent.trim() ?? "";
  return { peak: row("Peak pressure"), imep: row("IMEP, net (gross)") };
});
check("Leh in June: the choice marks the result out of date; solved again it is native Python's for the plateau preset",
  /out of date/.test(envStale) && /Leh/.test(envNote) && /65\.8 kPa/.test(envNote) && /FINDING-013/.test(envNote)
  && num(high.peak).toFixed(1) === refPlateau.p_max_bar.toFixed(1) && num(high.imep).toFixed(2) === refPlateau.imep_net_bar.toFixed(2)
  && num(high.peak) < peakBar,
  `"${envNote.slice(0, 60)}…"; page ${high.peak}, IMEP ${high.imep}; native ${refPlateau.p_max_bar.toFixed(1)} bar, `
  + `IMEP ${refPlateau.imep_net_bar.toFixed(2)} (standard air ${shown.peak})`);
const thinLeh = await page.$eval("p.env-note .env-thin", e => e.textContent.replace(/\s+/g, " ").trim()).catch(() => "");
const humidLeh = await page.$eval("p.env-note .env-humid", e => e.textContent.replace(/\s+/g, " ").trim()).catch(() => "");
await page.select("select.env", "standard");
const thinStd = await page.$eval("p.env-note .env-thin", e => e.textContent).catch(() => "");
const humidStd = await page.$eval("p.env-note .env-humid", e => e.textContent).catch(() => "");
check("humidity (ADR-016 item 3): at Leh the picker says NOx is corrected, and only NOx; at standard air it doesn't",
  /NOx only/.test(humidLeh) && /40 CFR 1065\.670/.test(humidLeh) && humidStd === "",
  `Leh: "${humidLeh.slice(0, 70)}…"; standard: "${humidStd}"`);
check("thin air: at Leh the picker says the ECU's limits (FINDING-026); at standard air it doesn't",
  /no turbo-overspeed protection/.test(thinLeh) && /37% less torque/.test(thinLeh) && /FINDING-026/.test(thinLeh) && thinStd === "",
  `Leh: "${thinLeh.slice(0, 70)}…"; standard: "${thinStd}"`);
check("no page errors or console errors", problems.length === 0, problems.slice(0, 3).join(" | "));

await browser.close();
server.close();
const failed = results.filter(r => !r).length;
console.log(`\n${results.length - failed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
