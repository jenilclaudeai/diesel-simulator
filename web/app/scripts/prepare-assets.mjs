// Build-time assets for the in-browser solver. ADR-010: Pyodide is
// self-hosted, and the dieselsim sources are bundled at build time.
//
//   public/pyodide/         Pyodide runtime, copied from node_modules
//   public/pyodide/numpy-*  numpy wheel - not in the npm package, so fetched
//                           here at BUILD time (never at runtime) and checked
//                           against pyodide-lock.json's sha256
//   public/physics/         dieselsim/*.py as ONE content-hashed file, so a
//                           browser can never hold a mix of old and new files
//   public/audio/           the engine-sound AudioWorklet, bundled here by
//                           esbuild (Angular bundles workers, not worklets)
//   src/app/solver/physics-version.ts
//                           the physics fingerprint, so a cached grid can be
//                           opened without booting Pyodide at all, and the
//                           worklet's content-hashed file name
//
// numpy source: $PYODIDE_WHEEL_DIR if set (offline or CDN-blocked builds),
// otherwise the Pyodide CDN ($PYODIDE_CDN overrides its base URL, for a
// mirror). A runtime CDN dependency was rejected in ADR-010; this is a
// build-time one, and the checksum makes it safe.
//
// If the wheel cannot be had, the script says why and what to do. With
// --dev (npm start) and outside CI it then carries on without numpy: the
// Drive page needs none, and the Dyno and Grid pages say it is missing
// (NUMPY_BUNDLED below). Builds and CI stay strict, so a deployable build
// can never ship without it.
import { createHash } from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const app = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const repo = path.resolve(app, "..", "..");
const pyo = path.join(app, "node_modules", "pyodide");
const outPy = path.join(app, "public", "pyodide");
const outPhys = path.join(app, "public", "physics");
const sha256 = b => createHash("sha256").update(b).digest("hex");

// 1. runtime
fs.mkdirSync(outPy, { recursive: true });
const RUNTIME = ["pyodide.mjs", "pyodide.asm.mjs", "pyodide.asm.wasm", "python_stdlib.zip", "pyodide-lock.json"];
for (const f of RUNTIME) fs.copyFileSync(path.join(pyo, f), path.join(outPy, f));
const version = JSON.parse(fs.readFileSync(path.join(pyo, "package.json"))).version;

// 2. numpy
const lock = JSON.parse(fs.readFileSync(path.join(pyo, "pyodide-lock.json")));
const np = lock.packages.numpy;
const wheelOut = path.join(outPy, np.file_name);
const lenient = process.argv.includes("--dev") && !process.env.CI;
let numpyOk = fs.existsSync(wheelOut) && sha256(fs.readFileSync(wheelOut)) === np.sha256;
if (!numpyOk) {
  const cdn = (process.env.PYODIDE_CDN ?? "https://cdn.jsdelivr.net/pyodide").replace(/\/+$/, "");
  const url = `${cdn}/v${version}/full/${np.file_name}`;
  let bytes, why;
  try {
    if (process.env.PYODIDE_WHEEL_DIR) {
      bytes = fs.readFileSync(path.join(process.env.PYODIDE_WHEEL_DIR, np.file_name));
    } else {
      const r = await fetch(url);
      if (!r.ok) why = `HTTP ${r.status} from ${url}`;
      else bytes = Buffer.from(await r.arrayBuffer());
    }
  } catch (e) {
    // a network failure (no route, DNS, proxy) lands here, not in r.ok
    const cause = e.cause?.code ?? e.cause?.message ?? e.code ?? "";
    why = process.env.PYODIDE_WHEEL_DIR
      ? `cannot read ${path.join(process.env.PYODIDE_WHEEL_DIR, np.file_name)} (${e.code ?? e.message})`
      : `cannot reach ${new URL(url).host}${cause ? ` (${cause})` : ""}`;
  }
  if (bytes) {
    const got = sha256(bytes);
    if (got !== np.sha256) throw new Error(`numpy wheel checksum mismatch: expected ${np.sha256}, got ${got}`);
    fs.writeFileSync(wheelOut, bytes);
    numpyOk = true;
  } else {
    const help = [
      `numpy wheel not available: ${why}.`,
      ``,
      `The in-browser solver (Dyno and Grid pages) needs this one file, fetched once:`,
      `  ${np.file_name}`,
      `  sha256 ${np.sha256}`,
      `Fix it in one of three ways:`,
      `  1. Behind a proxy? Node's fetch ignores it unless told (Node 22.21+):`,
      `       export HTTPS_PROXY=http://<host>:<port>   # npm config get https-proxy shows npm's`,
      `       export NODE_USE_ENV_PROXY=1`,
      `  2. Download the file elsewhere (${url}),`,
      `     put it in a folder and run with PYODIDE_WHEEL_DIR=/that/folder`,
      `     (tools/pyodide/README.md shows how to take it from Pyodide's GitHub release).`,
      `  3. A mirror of the Pyodide CDN: PYODIDE_CDN=https://<mirror>/pyodide`,
      `The file is checked against the sha256 above whichever way it arrives.`,
    ].join("\n");
    if (!lenient) throw new Error(help);
    console.warn(`\n*** WARNING: carrying on WITHOUT numpy (npm start only). ***\n` +
      `The Drive page works; the Dyno and Grid pages will say numpy is missing.\n\n${help}\n`);
  }
}

// 3. physics bundle. Hash algorithm must match dieselsim/bridge.py
// source_hash() and web/solver sourceHash(): for each .py in sorted name
// order, name + NUL + raw bytes + NUL. The app checks this against the
// worker at runtime and refuses a mismatch as a stale bundle.
const pkg = path.join(repo, "dieselsim");
const names = fs.readdirSync(pkg).filter(f => f.endsWith(".py")).sort();
const h = createHash("sha256");
const files = {};
for (const n of names) {
  const b = fs.readFileSync(path.join(pkg, n));
  h.update(Buffer.concat([Buffer.from(n), Buffer.from([0]), b, Buffer.from([0])]));
  files[n] = b.toString("utf8");
}
const physics = h.digest("hex");
// grid hash: the same, without the real-time loop and its synth --
// dieselsim/bridge.py grid_hash(). Prebuilt grids (public/grids/) carry it;
// the drive page uses one only when it matches this build. The exclusions
// are read from bridge.py itself: a second copy here drifted once
// (FINDING-021's synth), and every prebuilt grid read as stale.
const exm = files["bridge.py"].match(/^GRID_HASH_EXCLUDES = \(([^)]*)\)/m);
if (!exm) throw new Error("prepare-assets: GRID_HASH_EXCLUDES not found in dieselsim/bridge.py");
const GRID_HASH_EXCLUDES = [...exm[1].matchAll(/"([^"]+)"/g)].map(m => m[1]);
const gh = createHash("sha256");
for (const n of names.filter(n => !GRID_HASH_EXCLUDES.includes(n))) {
  gh.update(Buffer.concat([Buffer.from(n), Buffer.from([0]), fs.readFileSync(path.join(pkg, n)), Buffer.from([0])]));
}
const gridVersion = gh.digest("hex");
fs.rmSync(outPhys, { recursive: true, force: true });
fs.mkdirSync(outPhys, { recursive: true });
const bundle = `physics.${physics.slice(0, 12)}.json`;
fs.writeFileSync(path.join(outPhys, bundle), JSON.stringify({ physics, files }));

// 4. the engine-sound AudioWorklet (Phase 4): one self-contained ES module,
// content-hashed like the physics bundle so a browser never mixes versions
const { build } = await import("esbuild");
const outAudio = path.join(app, "public", "audio");
const res = await build({
  entryPoints: [path.join(app, "src", "app", "drive", "sound.worklet.ts")],
  bundle: true, format: "esm", target: "es2022", minify: true, write: false,
  tsconfig: path.join(app, "tsconfig.json"), logLevel: "warning",
});
const workletCode = res.outputFiles[0].contents;
const worklet = `engine-sound.${sha256(workletCode).slice(0, 12)}.js`;
fs.rmSync(outAudio, { recursive: true, force: true });
fs.mkdirSync(outAudio, { recursive: true });
fs.writeFileSync(path.join(outAudio, worklet), workletCode);

// 5. fingerprint for the app
const gen = path.join(app, "src", "app", "solver", "physics-version.ts");
fs.mkdirSync(path.dirname(gen), { recursive: true });
fs.writeFileSync(gen,
  `// GENERATED by scripts/prepare-assets.mjs - do not edit, not committed.\n` +
  `export const PHYSICS_VERSION = "${physics}";\n` +
  `export const PHYSICS_BUNDLE = "${bundle}";\n` +
  `export const PYODIDE_VERSION = "${version}";\n` +
  `export const GRID_VERSION = "${gridVersion}";\n` +
  `export const SOUND_WORKLET = "${worklet}";\n` +
  `/** false only in an npm start without the numpy wheel: Dyno and Grid cannot run */\n` +
  `export const NUMPY_BUNDLED = ${numpyOk};\n`);

const mb = d => (fs.readdirSync(d).reduce((n, f) => n + fs.statSync(path.join(d, f)).size, 0) / 1e6).toFixed(1);
console.log(`assets: pyodide ${version} (${mb(outPy)} MB), numpy ${numpyOk ? `${np.version} verified` : "MISSING"}, ` +
            `physics ${physics.slice(0, 12)} (${names.length} files), worklet ${worklet} (${(workletCode.length / 1024).toFixed(0)} KiB)`);
