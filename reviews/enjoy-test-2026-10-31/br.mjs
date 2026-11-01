// Browser checks for the ENJ triage, against the live site (built from main).
//   node br.mjs <scenario>    scenarios: layout | wax | grade | cruise | derate2
import puppeteer from "/Users/jenil/Projects/diesel-simulator/web/app/node_modules/puppeteer-core/lib/puppeteer/puppeteer-core.js";

const URL0 = process.env.ENJ_URL ?? "https://jenilclaudeai.github.io/diesel-simulator/enjoy?e2e";
const sc = process.argv[2];
const sleep = ms => new Promise(r => setTimeout(r, ms));
const browser = await puppeteer.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", headless: true, protocolTimeout: 300_000,
  args: ["--autoplay-policy=no-user-gesture-required", "--disable-audio-output",
    "--disable-background-timer-throttling", "--disable-renderer-backgrounding"],
});
const page = await browser.newPage();
const errs = [];
page.on("pageerror", e => errs.push(e.message));
page.on("console", m => { if (m.type() === "error") errs.push(m.text()); });
page.on("response", r => { if (r.status() >= 400) errs.push(`${r.status()} ${r.url()}`); });
const W = Number(process.env.W ?? 1280), H = Number(process.env.H ?? 800);
await page.emulate({ viewport: { width: W, height: H, deviceScaleFactor: 2, isMobile: W < 1000, hasTouch: W < 1000, isLandscape: W > H },
  userAgent: "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Mobile Safari/537.36" });
await page.goto(URL0 + (process.env.Q ?? ""), { waitUntil: "load" });
await page.evaluate(() => localStorage.clear());
await page.reload({ waitUntil: "load" });

const view = () => page.evaluate(() => globalThis.__enjoy.view());
const key = (k, down) => page.evaluate((k, d) => document.dispatchEvent(new KeyboardEvent(d ? "keydown" : "keyup", { key: k })), k, down);
const tap = async k => { await key(k, true); await sleep(40); await key(k, false); };
async function pick(sel, value) { await page.select(sel, value); await sleep(200); }
async function start() {
  await page.$eval("button.start", b => b.click());
  await page.waitForFunction(() => globalThis.__enjoy.view() && document.querySelector(".gauges"), { timeout: 60_000 });
  await sleep(2500);
}
const r1 = v => Math.round(v * 10) / 10;
const brief = v => ({ t: r1(v.t), rpm: Math.round(v.rpm), kmh: r1(v.kmh), gear: v.gear, thr: r1(v.throttle), stalled: v.stalled,
  stopped: v.engine_stopped, hint: v.hint, Tc: r1(v.T_coolant - 273.15), Tch: r1(v.T_charge - 273.15), derate: Math.round(v.derate * 1000) / 1000,
  heat: Math.round(v.derate_heat * 1000) / 1000, waxed: v.fuel_waxed, wax: Math.round(v.wax_frac * 100) / 100, fuel: Math.round(v.fuel_kg_h * 100) / 100 });

if (sc === "layout") {
  // ENJ-03: Manual, stall in 1st, Restart without the clutch -> the toast; measure at this viewport
  await page.evaluate(() => [...document.querySelectorAll(".seg button")].find(b => b.textContent.trim() === "Manual").click());
  await sleep(300);
  await start();
  await key("z", true); await sleep(600); await tap("."); await sleep(400); await key("z", false);
  await page.waitForFunction(() => globalThis.__enjoy.view()?.stalled, { timeout: 15_000 });
  await sleep(1500);
  const before = await page.evaluate(() => document.querySelector(".toast")?.textContent ?? null);
  await page.$eval("button.restart", b => b.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true })));
  await sleep(500);
  const m = await page.evaluate(() => {
    const r = s => { const e = document.querySelector(s); if (!e) return null; const b = e.getBoundingClientRect(); return [Math.round(b.top), Math.round(b.bottom), Math.round(b.left), Math.round(b.right)]; };
    const all = s => [...document.querySelectorAll(s)].map(e => { const b = e.getBoundingClientRect(); return [e.textContent.trim().slice(0, 30), Math.round(b.top), Math.round(b.bottom)]; });
    return { vh: innerHeight, vw: innerWidth, scrollW: document.documentElement.scrollWidth, toast: document.querySelector(".toast")?.textContent,
      toastR: r(".toast"), restart: r("button.restart"), mid: r(".mid"), gauges: r(".gauges"), strip: r(".strip"), road: r(".road"),
      lamps: r(".lamps"), top: r("header.top"), kv: all(".strip .kv, .strip .note") };
  });
  console.log(JSON.stringify({ W, H, toastBefore: before, ...m }, null, 0));
  await page.screenshot({ path: `${process.env.OUT ?? "."}/layout_${W}x${H}.png` });
} else if (sc === "wax") {
  // ENJ-04: Arctic winter + summer diesel, auto; 20 s idle then 30 s full throttle
  await pick("select.drive-env", "winter"); await pick("select.drive-fuel", "summer");
  await start();
  const log = [];
  for (let i = 0; i < 10; i++) { log.push(brief(await view())); await sleep(2000); }
  await tap(" ");
  for (let i = 0; i < 10; i++) { log.push(brief(await view())); await sleep(3000); }
  const toast = await page.evaluate(() => ({ toast: document.querySelector(".toast")?.textContent ?? null,
    restart: !!document.querySelector("button.restart"), lamps: [...document.querySelectorAll(".lamp.on")].map(l => l.textContent.trim()) }));
  for (const l of log) console.log(JSON.stringify(l));
  console.log("DOM", JSON.stringify(toast));
} else if (sc === "grade") {
  // ENJ-13: the strip's grade and the loop's, sampled in the same tick, along the Mountain pass
  await pick("select.route", "pass");
  await start();
  await tap(" ");
  let n = 0, bad = [];
  const t0 = Date.now();
  while (Date.now() - t0 < 90_000) {
    const s = await page.evaluate(() => { const v = globalThis.__enjoy.view(), r = globalThis.__enjoy.road();
      return { s: v.route_s, g: v.grade, strip: r?.grade, text: document.querySelector(".road-kv")?.textContent ?? "" }; });
    n++;
    const tg = /grade (-?[\d.]+) %/.exec(s.text.replace("−", "-"));
    if (s.strip !== s.g) bad.push(s);
    await sleep(250);
    if (n % 40 === 0) console.log("at", Math.round(s.s), "m: view", s.g, "road()", s.strip, "text", tg?.[1]);
  }
  console.log("samples", n, "road().grade != view().grade in", bad.length, bad.slice(0, 3));
} else if (sc === "cruise") {
  // ENJ-11: as the agent did -- full throttle (sticky), then c at ~117 km/h with the throttle still at 1
  await start();
  await tap(" ");
  await page.waitForFunction(() => globalThis.__enjoy.view().kmh >= 116.7, { timeout: 120_000, polling: 50 });
  await tap("c");
  const set = (await view()).kmh;
  const log = [];
  for (let i = 0; i < 12; i++) { await sleep(2500); const v = await view(); log.push([r1(v.t), r1(v.kmh), r1(v.throttle * 100) / 100, v.cruise]); }
  console.log("set at", r1(set), JSON.stringify(log));
} else if (sc === "derate2") {
  // ENJ-14: v8hd, desert, pass; '.' to 2nd (manual shift), full throttle, 200 s
  await pick('select[aria-label="Engine"]', "v8hd"); await pick("select.drive-env", "desert"); await pick("select.route", "pass");
  await start();
  await tap("."); await sleep(300); await tap(" ");
  let worst = { Tch: 0 }, unlitHot = 0, n = 0;
  for (let i = 0; i < 200; i++) {
    const s = await page.evaluate(() => ({ v: globalThis.__enjoy.view(), lit: document.querySelector(".lamp.derate")?.classList.contains("on") }));
    const b = brief(s.v); n++;
    if (b.Tch > worst.Tch) worst = { ...b, lit: s.lit };
    if (s.v.T_charge > 353.15 && !s.lit) unlitHot++;
    if (i % 20 === 0) console.log(JSON.stringify({ ...b, lit: s.lit }));
    await sleep(1000);
  }
  console.log("hottest", JSON.stringify(worst), "samples over 80 C with the lamp unlit:", unlitHot, "of", n);
}
console.log("errors", JSON.stringify(errs));
await browser.close();
