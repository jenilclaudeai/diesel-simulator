// MOB triage: the live site at the agent's iPhone size (852x393 landscape), real CDP touches.
//   node mob.mjs <scenario>   paddle | layout | contrast | start
import puppeteer from "/Users/jenil/Projects/diesel-simulator/web/app/node_modules/puppeteer-core/lib/puppeteer/puppeteer-core.js";

const URL0 = process.env.ENJ_URL ?? "https://jenilclaudeai.github.io/diesel-simulator/enjoy?e2e";
const sc = process.argv[2];
const sleep = ms => new Promise(r => setTimeout(r, ms));
const browser = await puppeteer.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", headless: true, protocolTimeout: 300_000,
  args: ["--autoplay-policy=no-user-gesture-required", "--disable-audio-output"],
});
const page = await browser.newPage();
const W = Number(process.env.W ?? 852), H = Number(process.env.H ?? 393);
await page.emulate({ viewport: { width: W, height: H, deviceScaleFactor: 3, isMobile: true, hasTouch: true, isLandscape: true },
  userAgent: "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1" });
const cdp = await page.createCDPSession();
await page.goto(URL0 + (process.env.Q ?? ""), { waitUntil: "load" });
await page.evaluate(() => localStorage.clear());
await page.reload({ waitUntil: "load" });

const view = () => page.evaluate(() => globalThis.__enjoy.view());
const centre = sel => page.$eval(sel, e => { const b = e.getBoundingClientRect(); return { x: b.x + b.width / 2, y: b.y + b.height / 2 }; });
const touch = (type, pts) => cdp.send("Input.dispatchTouchEvent", { type, touchPoints: pts.map((p, i) => ({ x: p.x, y: p.y, id: i + 1 })) });
async function tapEl(sel) { const p = await centre(sel); await touch("touchStart", [p]); await sleep(60); await touch("touchEnd", []); }
const key = (k, down) => page.evaluate((k, d) => document.dispatchEvent(new KeyboardEvent(d ? "keydown" : "keyup", { key: k })), k, down);
const rect = sel => page.evaluate(s => { const e = document.querySelector(s); if (!e) return null; const b = e.getBoundingClientRect();
  return [Math.round(b.top), Math.round(b.bottom), Math.round(b.left), Math.round(b.right)]; }, sel);
async function start() {
  await page.$eval("button.start", b => b.scrollIntoView({ block: "center" }));
  await tapEl("button.start");
  await page.waitForFunction(() => globalThis.__enjoy.view() && document.querySelector(".gauges"), { timeout: 60_000 });
  await sleep(2000);
}

if (sc === "paddle") {
  // MOB-04: one real touch tap on a paddle -> how many gears? Auto (manual-shift mode) and Manual (clutch held by key)
  await start();
  const counts = [];
  for (let i = 0; i < 3; i++) {
    const g0 = (await view()).gear;
    await tapEl("button.paddle.plus"); await sleep(1500);
    counts.push(`${g0}->${(await view()).gear}`);
  }
  // the click a real tap makes: count what reached the page
  const ev = await page.evaluate(() => { const b = document.querySelector("button.paddle.plus"), seen = [];
    for (const t of ["pointerdown", "pointerup", "click"]) b.addEventListener(t, e => seen.push(`${t}:${e.detail ?? ""}`)); globalThis.__seen = seen; });
  await tapEl("button.paddle.plus"); await sleep(400);
  console.log("auto, manual-shift mode, one tap each:", counts.join(" "), "events of one tap:", JSON.stringify(await page.evaluate(() => globalThis.__seen)));
} else if (sc === "layout") {
  // MOB-01/02: route + goal from the URL (Q), stalled in Manual, Restart tapped without the clutch
  await page.evaluate(() => [...document.querySelectorAll(".seg button")].find(b => b.textContent.trim() === "Manual").click());
  await sleep(300);
  await start();
  await key("z", true); await sleep(600); await key(".", true); await sleep(40); await key(".", false); await sleep(400); await key("z", false);
  await page.waitForFunction(() => globalThis.__enjoy.view()?.stalled, { timeout: 15_000 });
  await sleep(1200);
  await tapEl("button.restart"); await sleep(500);
  const m = await page.evaluate(() => {
    const r = s => { const e = document.querySelector(s); if (!e) return null; const b = e.getBoundingClientRect(); return [Math.round(b.top), Math.round(b.bottom)]; };
    const snd = document.querySelector("button.snd"), b = snd.getBoundingClientRect();
    const hit = document.elementFromPoint(b.x + b.width / 2, b.y + b.height / 2);
    const dash = document.querySelector("main.dash");
    return { vh: innerHeight, toast: document.querySelector(".toast")?.textContent, toastR: r(".toast"), restart: r("button.restart"),
      gauges: r(".gauges"), road: r(".road"), goal: r(".goal-kv"), strip: r(".strip"), snd: r("button.snd"),
      sndHit: hit === snd, dashScroll: [dash.scrollHeight, dash.clientHeight] };
  });
  console.log(JSON.stringify({ W, H, q: process.env.Q ?? "", ...m }));
} else if (sc === "contrast") {
  // MOB-05: the start screen's labels: colour, background, contrast
  const out = await page.evaluate(() => {
    const rgb = s => s.match(/[\d.]+/g).map(Number);
    const lum = ([r, g, b]) => { const f = c => { c /= 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
    const bg = rgb(getComputedStyle(document.querySelector(".enjoy")).backgroundColor);
    return [...document.querySelectorAll("main.dash label.field > span, main.dash .drive-env-note, main.dash .drive-fuel-note")].map(e => {
      const c = rgb(getComputedStyle(e).color), a = c[3] ?? 1;
      const mix = [0, 1, 2].map(i => a * c[i] + (1 - a) * bg[i]);
      const L1 = lum(mix), L2 = lum(bg), ratio = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
      return `${e.textContent.trim().slice(0, 24)}: ${getComputedStyle(e).color} on rgb(${bg.join(",")}) = ${ratio.toFixed(2)}:1`;
    });
  });
  console.log(out.join("\n"));
} else if (sc === "start") {
  // MOB-06/10: the start screen's Start button and what sits below the fold
  const s = await page.evaluate(() => {
    const st = document.querySelector("button.start"), b = st.getBoundingClientRect(), cs = getComputedStyle(st), dash = document.querySelector("main.dash");
    return { start: [Math.round(b.top), Math.round(b.bottom), Math.round(b.height)], natural: st.scrollHeight, pad: cs.paddingTop + "/" + cs.paddingBottom,
      fontPx: cs.fontSize, dash: [dash.scrollHeight, dash.clientHeight], vib: Math.round(document.querySelector(".vibrate").getBoundingClientRect().top) };
  });
  console.log(JSON.stringify({ W, H, ...s }));
}
await browser.close();
