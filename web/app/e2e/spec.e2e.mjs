// The spec editor (Phase 6, ADR-015) in a real headless Chrome: every field of
// the engine shown in its subsystem; an edit is counted and shows the engine's
// own value; filter; a spec file opened (and a bad one refused, with the
// reason); then the cycle page solves the edited engine, and its numbers are
// native Python's for the same overrides. The edits survive a reload (m-3). Projects
// (Phase 7 step 7): opened and saved on /spec, and reaching /drive and /enjoy.
//
//   npm run build:pages && CHROME_PATH=... npm run e2e:spec      (~1 min)
import http from "node:http";
import fs from "node:fs";
import os from "node:os";
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

const EDIT = { "geom.compression_ratio": 17 };
let ref;
try {
  ref = JSON.parse(process.env.NATIVE_SPEC_CYCLE ?? execFileSync("python3", [path.join(here, "native_cycle.py")],
    { cwd: path.resolve(here, "..", "..", ".."), encoding: "utf8", env: { ...process.env, OVERRIDES: JSON.stringify(EDIT) } }));
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

await page.goto(`http://localhost:${port}${BASE}spec?e2e`, { waitUntil: "load" });
await page.waitForSelector('tr[data-path="geom.compression_ratio"] input', { timeout: 180_000 });
const layout = await page.evaluate(() => ({
  groups: [...document.querySelectorAll("section.group h2")].map(h => h.firstChild.textContent.trim()),
  rows: document.querySelectorAll("tr[data-path]").length,
  editable: document.querySelectorAll("tr[data-path] input").length,
  cr: Number(document.querySelector('tr[data-path="geom.compression_ratio"] input').value),
}));
check("every field, in seven subsystems: 190 rows, 182 of them editable",
  layout.groups.length === 7 && layout.rows === 190 && layout.editable === 182,
  `${layout.groups.join(" | ")}; ${layout.rows} rows, ${layout.editable} inputs; compression ratio ${layout.cr}`);
const thinNotes = await page.evaluate(() => Object.fromEntries(["thermal.ambient_p", "ecu_modern"].map(p =>
  [p, document.querySelector(`tr[data-path="${p}"] .note`)?.textContent.replace(/\s+/g, " ").trim() ?? ""])));
check("thin air (FINDING-026): ambient pressure and the ECU switch say the model's limits beside the field",
  /Below 90 kPa/.test(thinNotes["thermal.ambient_p"]) && /no turbo-overspeed/.test(thinNotes["thermal.ambient_p"])
  && /mechanical pump/.test(thinNotes.ecu_modern) && /no turbo-overspeed/.test(thinNotes.ecu_modern),
  `ambient: "${thinNotes["thermal.ambient_p"].slice(0, 50)}…"; ECU: "${thinNotes.ecu_modern.slice(0, 90)}…"`);
const humRow = await page.evaluate(() => {
  const tr = document.querySelector('tr[data-path="thermal.ambient_humidity"]');
  return { value: Number(tr?.querySelector("input")?.value), unit: tr?.querySelector(".unit")?.textContent.trim() ?? "",
    note: tr?.querySelector(".note")?.textContent.replace(/\s+/g, " ").trim() ?? "" };
});
check("humidity (ADR-016 item 3): its own field, 10.71 g/kg, saying it corrects NOx only",
  humRow.value === 10.71 && humRow.unit === "g/kg" && /NOx only/.test(humRow.note) && /isn't in the cycle/.test(humRow.note),
  `${humRow.value} ${humRow.unit}; "${humRow.note.slice(0, 80)}…"`);

// ADR-009: the four live schematics, drawn from the spec
await page.waitForSelector("figure.schematic.compressor polyline.speed", { timeout: 60_000 }).catch(() => {});
const schem = await page.evaluate(() => ({
  kinds: [...document.querySelectorAll("figure.schematic")].map(f => [...f.classList].find(c => c !== "schematic")),
  speedLines: document.querySelectorAll("figure.compressor polyline.speed").length,
  surge: !!document.querySelector("figure.compressor polyline.surge"),
  dial: document.querySelector("figure.valves figcaption")?.textContent.replace(/\s+/g, " ").trim() ?? "",
  aria: [...document.querySelectorAll("figure.schematic svg")].every(s => (s.getAttribute("aria-label") ?? "").length > 30),
}));
check("four schematics from the spec: cross-section, valve dial (crdi15's 18° overlap), compressor map (6 speed lines, surge), ring pack",
  JSON.stringify(schem.kinds) === JSON.stringify(["cylinder", "valves", "compressor", "friction"]) && schem.speedLines === 6 && schem.surge
  && /overlap 18°/.test(schem.dial) && schem.aria, `${schem.kinds.join(", ")}; ${schem.speedLines} speed lines; "${schem.dial.slice(0, 70)}…"`);

const setValue = async (p, v) => {
  await page.$eval(`tr[data-path="${p}"] input`, (el, val) => {
    el.value = String(val);
    el.dispatchEvent(new Event("change", { bubbles: true }));
  }, v);
};
await setValue("geom.compression_ratio", 17);
await page.waitForFunction(() => /1 field changed/.test(document.querySelector(".changed-count")?.textContent ?? ""), { timeout: 5000 }).catch(() => {});
const edited = await page.evaluate(() => {
  const tr = document.querySelector('tr[data-path="geom.compression_ratio"]');
  return { count: document.querySelector(".changed-count")?.textContent.trim(), changed: tr?.classList.contains("changed"),
    was: tr?.querySelector(".was")?.textContent.replace(/\s+/g, " ").trim() };
});
check("an edit is counted, marked, and shows the engine's own value",
  edited.count === "1 field changed" && edited.changed && new RegExp(`engine: ${layout.cr}`).test(edited.was ?? ""),
  `${edited.count}; ${edited.was}`);

await page.type("input.filter", "bore");
await new Promise(r => setTimeout(r, 300));
const filtered = await page.$$eval("tr[data-path]", trs => trs.map(t => t.getAttribute("data-path")));
check("the filter finds fields by name, path or note", filtered.length > 0 && filtered.length < 20 && filtered.includes("geom.bore"),
  `${filtered.length} rows: ${filtered.slice(0, 5).join(", ")}…`);
await page.$eval("input.filter", el => { el.value = ""; el.dispatchEvent(new Event("input", { bubbles: true })); });

// a spec file: a bad one refused with the reason, a good one loaded
const dir = fs.mkdtempSync(path.join(os.tmpdir(), "spec-e2e-"));
const bad = path.join(dir, "bad.json"), good = path.join(dir, "good.json");
fs.writeFileSync(bad, JSON.stringify({ preset: "crdi15", overrides: { "geom.compresion_ratio": 17 } }));
fs.writeFileSync(good, JSON.stringify({ preset: "crdi15", overrides: { ...EDIT, "inj.n_holes": 8 } }));
const input = await page.$(".open-project input[type=file]");   // step 7: "Open project" opens old spec files too
await input.uploadFile(bad);
await page.waitForSelector("p.err[role=alert]", { timeout: 5000 }).catch(() => {});
const refused = await page.$eval("p.err[role=alert]", e => e.textContent.trim()).catch(() => "");
await input.uploadFile(good);
await page.waitForFunction(() => /2 fields changed/.test(document.querySelector(".changed-count")?.textContent ?? ""), { timeout: 5000 }).catch(() => {});
const loaded = await page.$eval(".changed-count", e => e.textContent.trim());
check("a spec file: a bad one refused with the reason, a good one loaded", /unknown field "geom.compresion_ratio"/.test(refused) && loaded === "2 fields changed",
  `refused: "${refused}"; then ${loaded}`);
await page.$eval('tr[data-path="inj.n_holes"] button.reset', b => b.click());
await page.screenshot({ path: path.join(out, "spec.png"), fullPage: false });

// the cycle page solves the edited engine
await page.click("a.solve");
await page.waitForSelector("button.run:not([disabled])", { timeout: 60_000 });
// the note can render a moment after Solve enables: wait for it (CI on #96 once read it empty)
await page.waitForSelector("p.edits", { timeout: 10_000 }).catch(() => {});
const note = await page.$eval("p.edits", e => e.textContent.replace(/\s+/g, " ").trim()).catch(() => "");
await page.click("button.run");
await page.waitForSelector(".cycle-data", { timeout: 5 * 60_000 });
const peak = await page.evaluate(() => [...document.querySelectorAll(".cycle-data tr")]
  .find(tr => tr.querySelector("th")?.textContent.trim() === "Peak pressure")?.querySelector("td")?.textContent.trim() ?? "");
const peakBar = Number((peak.match(/[\d.,]+/)?.[0] ?? "NaN").replace(/,/g, ""));
check("the cycle page solves the edited engine: native Python's peak pressure for the same override",
  /1 field changed/.test(note) && peakBar.toFixed(1) === ref.p_max_bar.toFixed(1),
  `"${note}"; page ${peak}; native ${ref.p_max_bar.toFixed(1)} bar (compression ratio 17)`);

// the invalidation banner (PLAN.md Phase 6): edit again, come back, and the old
// result is flagged out of date until it is solved again. In-app navigation
// only: a reload would drop the kept results.
let ref18;
try {
  ref18 = JSON.parse(process.env.NATIVE_SPEC_CYCLE18 ?? execFileSync("python3", [path.join(here, "native_cycle.py")],
    { cwd: path.resolve(here, "..", "..", ".."), encoding: "utf8", env: { ...process.env, OVERRIDES: JSON.stringify({ "geom.compression_ratio": 18 }) } }));
} catch (e) { ref18 = { p_max_bar: NaN }; }
const navTo = async label => {
  await page.evaluate(l => [...document.querySelectorAll("nav a")].find(a => a.textContent.trim() === l)?.click(), label);
};
await navTo("Spec");
await page.waitForSelector('tr[data-path="geom.compression_ratio"] input', { timeout: 60_000 });
// the compressor map places the last cycle's operating point, while that cycle is of this engine as edited
await page.waitForSelector("figure.compressor circle.op", { timeout: 10_000 }).catch(() => {});
const opBefore = !!(await page.$("figure.compressor circle.op"));
await setValue("geom.compression_ratio", 18);
await page.waitForFunction(() => !document.querySelector("figure.compressor circle.op"), { timeout: 5000 }).catch(() => {});
const opAfterEdit = !!(await page.$("figure.compressor circle.op"));
check("the compressor map shows the cycle's operating point, and drops it once an edit makes that cycle stale",
  opBefore && !opAfterEdit, `point with the CR 17 cycle: ${opBefore}; after the CR 18 edit: ${opAfterEdit}`);
await page.click("a.solve");
await page.waitForSelector(".cycle-data", { timeout: 60_000 }).catch(() => {});   // a forgotten result fails the check below
const staleShown = await page.$eval("app-spec-status .stale", e => e.textContent.replace(/\s+/g, " ").trim()).catch(() => "");
const oldPeak = await page.evaluate(() => [...document.querySelectorAll(".cycle-data tr")]
  .find(tr => tr.querySelector("th")?.textContent.trim() === "Peak pressure")?.querySelector("td")?.textContent.trim() ?? "");
// clicked only if shown: a missing banner must fail the check below, not crash the test
await page.$eval("app-spec-status button.rerun", b => b.click()).catch(() => {});
await page.waitForFunction(() => !document.querySelector("app-spec-status .stale") && !document.querySelector("button.run[disabled]"),
  { timeout: 5 * 60_000, polling: 500 }).catch(() => {});
const staleAfter = await page.$("app-spec-status .stale");
const peak18 = await page.evaluate(() => [...document.querySelectorAll(".cycle-data tr")]
  .find(tr => tr.querySelector("th")?.textContent.trim() === "Peak pressure")?.querySelector("td")?.textContent.trim() ?? "");
const peak18Bar = Number((peak18.match(/[\d.,]+/)?.[0] ?? "NaN").replace(/,/g, ""));
check("after another edit the kept result is flagged out of date; solved again, it is native Python's for the new edit",
  /out of date/.test(staleShown) && oldPeak === peak && !staleAfter && peak18Bar.toFixed(1) === ref18.p_max_bar.toFixed(1),
  `banner: "${staleShown.slice(0, 60)}…" over ${oldPeak}; after: ${staleAfter ? "still stale" : "clear"}, ${peak18} (native ${ref18.p_max_bar.toFixed(1)}, compression ratio 18)`);

await navTo("Spec");
await page.waitForSelector('tr[data-path="geom.compression_ratio"] input', { timeout: 60_000 });
const beforeReset = await page.$eval(".changed-count", e => e.textContent.trim());
await page.click("button.reset-all").catch(() => {});
await page.waitForFunction(() => document.querySelector(".changed-count")?.textContent.trim() === "0 fields changed",
  { timeout: 5000 }).catch(() => {});
const afterReset = await page.$eval(".changed-count", e => e.textContent.trim());
check("Reset all clears the edits", afterReset === "0 fields changed", `${beforeReset} -> ${afterReset}`);

// live: the schematics redraw as fields change (one source of truth, ADR-009)
const ratio = () => page.evaluate(() => {
  const l = [...document.querySelectorAll("figure.cylinder line.liner")].map(x => Number(x.getAttribute("x1")));
  return (l[1] - l[0]) / (2 * Number(document.querySelector("figure.cylinder circle.crankcircle")?.getAttribute("r")));
});
const r0 = await ratio();
await setValue("geom.bore", 0.0924);
await setValue("valves.evc_deg", 382);
await new Promise(r => setTimeout(r, 400));
const r1 = await ratio();
const dial2 = await page.$eval("figure.valves figcaption", e => e.textContent.replace(/\s+/g, " ").trim());
check("live: a 20% bigger bore redraws the cross-section to scale (liner / crank diameter = bore / stroke), EVC 382 gives 28° overlap",
  Math.abs(r0 - 0.077 / 0.0805) < 0.01 && Math.abs(r1 - 0.0924 / 0.0805) < 0.01 && /overlap 28°/.test(dial2),
  `liner/crank ${r0.toFixed(3)} -> ${r1.toFixed(3)} (want ${(0.077 / 0.0805).toFixed(3)} -> ${(0.0924 / 0.0805).toFixed(3)}); "${dial2.slice(0, 60)}…"`);

// REVIEW-008 m-3: a reload kept nothing, and the page didn't say so. Now the edits survive a
// real reload (results don't: the page solves again, and says so).
await page.click("button.reset-all").catch(() => {});
await setValue("geom.compression_ratio", 17);
await page.waitForFunction(() => /1 field changed/.test(document.querySelector(".changed-count")?.textContent ?? ""), { timeout: 5000 }).catch(() => {});
await page.reload({ waitUntil: "load" });
await page.waitForSelector('tr[data-path="geom.compression_ratio"] input', { timeout: 180_000 });
const kept = await page.evaluate(() => ({
  count: document.querySelector(".changed-count")?.textContent.trim(),
  cr: Number(document.querySelector('tr[data-path="geom.compression_ratio"] input')?.value),
  note: document.querySelector("p.kept-note")?.textContent.replace(/\s+/g, " ").trim() ?? "",
}));
check("a reload keeps the edits (REVIEW-008 m-3), and the page says results are solved again",
  kept.count === "1 field changed" && kept.cr === 17 && /kept in this browser/.test(kept.note) && /solves again/.test(kept.note),
  `after reload: ${kept.count}, compression ratio ${kept.cr}; "${kept.note.slice(0, 70)}…"`);
await page.click("button.reset-all").catch(() => {});

// Phase 7 step 7 (ADR-016 item 6): projects. Opened and saved on /spec, the
// "Drive with" box, and the same choice reaching /drive and /enjoy (one browser).
const project = (preset, overrides, gearbox, place, fuel) =>
  JSON.stringify({ format: "dieselsim-project", version: 1, engine: { preset, overrides }, drive: { gearbox, place, fuel } });
const pfile = (name, text) => { const f = path.join(dir, name); fs.writeFileSync(f, text); return f; };
const selects = () => page.evaluate(() => Object.fromEntries(["drive-gearbox", "drive-env", "drive-fuel"]
  .map(c => [c, document.querySelector(`select.${c}`)?.value ?? null])));
const open = async (sel, file) => { await (await page.$(`${sel} input[type=file]`)).uploadFile(file); await new Promise(r => setTimeout(r, 400)); };
await open(".open-project", pfile("p1.json", project("crdi15", {}, "dct", "winter", "summer")));
const opened = await selects();
await open(".open-project", pfile("old.json", JSON.stringify({ preset: "crdi15", overrides: { "inj.n_holes": 8 } })));
const afterOld = { ...(await selects()), note: await page.$eval("p.file-note", e => e.textContent.trim()).catch(() => ""),
  count: await page.$eval(".changed-count", e => e.textContent.trim()) };
await open(".open-project", pfile("newer.json", JSON.stringify({ ...JSON.parse(project("crdi15", {}, "tc", "standard", "local")), version: 2 })));
const newer = await page.$eval("p.err[role=alert]", e => e.textContent.trim()).catch(() => "");
check("a project opens on /spec: its gearbox, place and fuel in the Drive with box; an old spec file sets the engine only and says so; a newer format is refused",
  opened["drive-gearbox"] === "dct" && opened["drive-env"] === "winter" && opened["drive-fuel"] === "summer"
  && afterOld["drive-gearbox"] === "dct" && afterOld["drive-env"] === "winter" && afterOld.count === "1 field changed"
  && /old spec file/.test(afterOld.note) && /newer version of the app \(project format 2/.test(newer),
  `${JSON.stringify(opened)}; old: ${afterOld.count}, "${afterOld.note.slice(0, 40)}…"; newer: "${newer}"`);
// Save project: the file's text, caught at the download (the anchor's click, the blob kept)
await page.evaluate(() => {
  window.__saved = [];
  HTMLAnchorElement.prototype.click = function () { window.__saved.push({ href: this.href, name: this.download }); };
  URL.revokeObjectURL = () => {};
});
await page.select("select.drive-gearbox", "manual");
await page.click("button.save-project");
const saved = await page.evaluate(async () => { const s = window.__saved[0]; return s ? { name: s.name, text: await (await fetch(s.href)).text() } : null; });
const sj = saved ? JSON.parse(saved.text) : {};
check("Save project: <engine>-project.json, a format version, the engine's edits and the Drive with choice",
  saved?.name === "crdi15-project.json" && sj.format === "dieselsim-project" && sj.version === 1
  && JSON.stringify(sj.engine) === JSON.stringify({ preset: "crdi15", overrides: { "inj.n_holes": 8 } })
  && JSON.stringify(sj.drive) === JSON.stringify({ gearbox: "manual", place: "winter", fuel: "summer" }),
  `${saved?.name}: ${saved?.text.replace(/\s+/g, " ").slice(0, 160)}`);

// /drive starts with the same choice, and opens a project itself
await page.goto(`http://localhost:${port}${BASE}drive?e2e`, { waitUntil: "load" });
await page.waitForSelector("select.drive-gearbox", { timeout: 60_000 });
const onDrive = await selects();
const engineSel = () => page.$eval(".controls select", s => s.value);
await open(".open-project", pfile("p2.json", project("ld_i4", {}, "tc", "desert", "local")));
const drive2 = { ...(await selects()), engine: await engineSel(), note: await page.$eval("p.project-note", e => e.textContent.trim()).catch(() => "") };
await open(".open-project", pfile("p3.json", project("crdi15", { "geom.compression_ratio": 17 }, "manual", "plateau", "winter")));
const drive3err = await page.$eval(".import-err", e => e.textContent.trim()).catch(() => "");
check("/drive starts with /spec's Drive with choice; a project there picks its engine, gearbox, place and fuel; an edited engine with no grid built says how to build it",
  onDrive["drive-gearbox"] === "manual" && onDrive["drive-env"] === "winter" && onDrive["drive-fuel"] === "summer"
  && drive2.engine === "ld_i4" && drive2["drive-gearbox"] === "tc" && drive2["drive-env"] === "desert" && drive2["drive-fuel"] === "local"
  && /Opened p2\.json/.test(drive2.note) && /1 edited field.*isn't built in this browser.*Build drivable grid/.test(drive3err),
  `from /spec ${JSON.stringify(onDrive)}; p2 ${JSON.stringify(drive2)}; p3 "${drive3err.slice(0, 60)}…"`);

// /enjoy: the kept gearbox (p3's manual) starts it in Manual; a dual-clutch project drives as Auto, and says so
await page.goto(`http://localhost:${port}${BASE}enjoy?e2e`, { waitUntil: "load" });
await page.waitForSelector("select[aria-label=Engine]", { timeout: 60_000 });
const pressed = () => page.evaluate(() => [...document.querySelectorAll("button[aria-pressed=true]")].map(b => b.textContent.trim()));
const enjoyStart = await pressed();
await open(".open-project", pfile("p4.json", project("hatch15", {}, "dct", "tropics", "local")));
const enjoy4 = { pressed: await pressed(), engine: await page.$eval("select[aria-label=Engine]", s => s.value),
  place: await page.$eval("select.drive-env", s => s.value), note: await page.$eval("p.project-note", e => e.textContent.trim()).catch(() => "") };
check("/enjoy starts in the kept gearbox (Manual); a project picks its engine and place, and a dual clutch drives as Auto, said",
  enjoyStart.includes("Manual") && enjoy4.pressed.includes("Auto") && enjoy4.engine === "hatch15" && enjoy4.place === "tropics"
  && /no dual clutch, so it drives as Auto/.test(enjoy4.note),
  `start ${enjoyStart.join("/")}; p4 ${JSON.stringify(enjoy4).slice(0, 160)}`);
await page.evaluate(() => localStorage.clear());
check("no page errors or console errors", problems.length === 0, problems.slice(0, 3).join(" | "));

await browser.close();
server.close();
const failed = results.filter(r => !r).length;
console.log(`\n${results.length - failed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
