// How the drive page's work fits a phone (Phase 5's exit criterion is a
// mid-range phone with audio). Chrome's CPU throttling stands in for the
// phone: DevTools calls 4x "mid-tier mobile" and 6x "low-end". A real phone
// remains the final test.
//
//   node e2e/perf.mjs [rates...]      (CHROME_PATH as for the other e2e)
//
// Measured, on the prebuilt grids (public/grids/), with @dieselsim/physics
// bundled from source:
//   synth        one 128-sample quantum per call: the audio thread's budget
//                is 128/44100 s = 2.90 ms, every quantum
//   loop, plain  one 1/60 s live-loop step: budget 16.7 ms
//   loop, fric.  a step that also evaluates live friction (every 6th)
// Each runs on the page's main thread and in a Web Worker: Chrome's CPU
// throttling is meant to reach both, and this shows whether it does.
// Reports only; it has no pass/fail threshold (timings vary by machine).
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { build } from "esbuild";
import puppeteer from "puppeteer-core";

const here = path.dirname(fileURLToPath(import.meta.url));
const app = path.resolve(here, "..");
const rates = process.argv.slice(2).map(Number).filter(Boolean);
const RATES = rates.length ? rates : [1, 4, 6];
const SECONDS = Number(process.env.PERF_SECONDS ?? 10);

const bundle = (await build({
  entryPoints: [path.join(here, "perf-bench.ts")], bundle: true, format: "iife", target: "es2022",
  write: false, tsconfig: path.join(app, "tsconfig.json"), logLevel: "warning",
})).outputFiles[0].text;
const page = `<!doctype html><meta charset="utf-8"><title>perf</title><script>${bundle}</script>`;
const server = http.createServer((req, res) => {
  const u = new URL(req.url, "http://x").pathname;
  if (u === "/") { res.writeHead(200, { "content-type": "text/html" }).end(page); return; }
  if (u === "/bench.js") { res.writeHead(200, { "content-type": "text/javascript" }).end(bundle); return; }
  const f = path.join(app, "public", u);
  if (!f.startsWith(path.join(app, "public")) || !fs.existsSync(f)) { res.writeHead(404).end(); return; }
  res.writeHead(200, { "content-type": "application/json" });
  fs.createReadStream(f).pipe(res);
}).listen(0);
const base = `http://localhost:${server.address().port}`;

const browser = await puppeteer.launch({ timeout: 120_000,   // Chrome's start: 30 s timed out on loaded CI runners (#108, #115)
 
  executablePath: process.env.CHROME_PATH, headless: true, protocolTimeout: 30 * 60_000,
  args: ["--no-sandbox", "--disable-dev-shm-usage"],
});
const tab = await browser.newPage();
await tab.goto(base + "/", { waitUntil: "load" });
const cdp = await tab.createCDPSession();

const fmt = s => `${s.mean.toFixed(2)} mean, ${s.p99.toFixed(2)} p99, ${s.p999.toFixed(2)} p99.9, ${s.max.toFixed(1)} max ms; over budget ${s.over}/${s.n}`;
for (const preset of ["crdi15", "hd_i6"]) {
  for (const rate of RATES) {
    await cdp.send("Emulation.setCPUThrottlingRate", { rate });
    const r = await tab.evaluate(async (preset, seconds) => {
      const g = await (await fetch(`/grids/${preset}.json`)).json();
      const main = { synth: globalThis.bench.synth(g, seconds), loop: globalThis.bench.loop(g, seconds * 3) };
      // the same, in a dedicated worker
      const w = new Worker(URL.createObjectURL(new Blob([
        `importScripts(${JSON.stringify(location.origin + "/bench.js")});` +
        `onmessage = e => postMessage({ synth: bench.synth(e.data.g, e.data.s), loop: bench.loop(e.data.g, e.data.s * 3) });`,
      ], { type: "text/javascript" })));
      const worker = await new Promise(res => { w.onmessage = e => res(e.data); w.postMessage({ g, s: seconds }); });
      w.terminate();
      return { main, worker };
    }, preset, SECONDS);
    for (const where of ["main", "worker"]) {
      const x = r[where];
      console.log(`${preset} ${rate}x ${where.padEnd(6)} synth       ${fmt(x.synth)}  (budget 2.90 ms: ${(100 * x.synth.mean / 2.902).toFixed(0)}% of the audio thread)`);
      console.log(`${preset} ${rate}x ${where.padEnd(6)} loop plain  ${fmt(x.loop.plain)}`);
      console.log(`${preset} ${rate}x ${where.padEnd(6)} loop fric.  ${fmt(x.loop.friction)}`);
    }
  }
}
await browser.close();
server.close();
