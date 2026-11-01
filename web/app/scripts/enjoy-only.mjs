// The Enjoy-only deployment (branch `deploy/enjoy-only`), run after
// `build:pages` by `npm run build:enjoy`.
//
// Enjoy drives prebuilt grids and never boots Python, so the Pyodide runtime
// (public/pyodide/, ~16.5 MB) and the bundled solver sources (public/physics/)
// that prepare-assets copies into every build are dead weight here. They are
// removed from dist/.
//
// Angular also emits a worker bundle for every `new Worker(new URL(...))` in
// the TypeScript program, reachable or not, so solver.service.ts's worker
// (which boots Pyodide) is built though nothing that ships starts it. Such a
// chunk, named by no other shipped file, is removed too, and dropped from the
// service worker's manifest (ngsw.json), which would otherwise prefetch it, or
// fail to install on its 404 once it is gone. A chunk that IS referenced and
// names Pyodide refuses the build.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const dist = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "dist", "app", "browser");
const size = d => fs.readdirSync(d, { withFileTypes: true, recursive: true })
  .filter(e => e.isFile()).reduce((s, e) => s + fs.statSync(path.join(e.parentPath, e.name)).size, 0);
const mb = b => (b / 1e6).toFixed(2) + " MB";
const fail = msg => { console.error(`enjoy-only: ${msg}`); process.exit(1); };
const PYODIDE = /pyodide\.asm|pyodide\.mjs|loadPyodide|pyodide\//;

const before = size(dist);
for (const d of ["pyodide", "physics"]) fs.rmSync(path.join(dist, d), { recursive: true, force: true });

// every shipped text file that could name a chunk: the page, the app's JS, the worklet
const texts = ["index.html", ...fs.readdirSync(dist).filter(f => f.endsWith(".js")),
  ...fs.readdirSync(path.join(dist, "audio")).map(f => path.join("audio", f))];
const read = f => fs.readFileSync(path.join(dist, f), "utf8");
const ngswPath = path.join(dist, "ngsw.json");
const ngsw = JSON.parse(fs.readFileSync(ngswPath, "utf8"));
const removed = [];
for (const f of texts.filter(f => /^worker-[^/]+\.js$/.test(f))) {
  if (!PYODIDE.test(read(f))) continue;
  const named = texts.filter(o => o !== f && fs.existsSync(path.join(dist, o)) && read(o).includes(f));
  if (named.length) fail(`${f} names Pyodide and is loaded by ${named.join(", ")}`);
  fs.rmSync(path.join(dist, f));
  for (const g of ngsw.assetGroups) g.urls = g.urls.filter(u => !u.endsWith(`/${f}`));
  for (const u of Object.keys(ngsw.hashTable)) if (u.endsWith(`/${f}`)) delete ngsw.hashTable[u];
  removed.push(f);
}
fs.writeFileSync(ngswPath, JSON.stringify(ngsw, null, 2));

// nothing left that ships may name Pyodide or the solver's sources
if (Object.keys(ngsw.hashTable).some(u => /pyodide|\/physics\//.test(u))) fail("ngsw.json still lists Pyodide or physics/");
for (const f of fs.readdirSync(dist).filter(f => f.endsWith(".js") && /^(main|worker|chunk)-/.test(f)))
  if (PYODIDE.test(read(f))) fail(`${f} still names Pyodide`);
const listed = Object.keys(ngsw.hashTable).map(u => u.replace(/^.*?\/diesel-simulator\//, "").replace(/^\//, ""));
const missing = listed.filter(f => !fs.existsSync(path.join(dist, f)));
if (missing.length) fail(`ngsw.json lists files not in dist: ${missing.join(", ")}`);

console.log(`enjoy-only: removed pyodide/, physics/${removed.length ? " and the orphan " + removed.join(", ") : ""} `
  + `(${mb(before)} -> ${mb(size(dist))})`);
