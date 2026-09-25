// Grid cache tests. Fast: a fake inner solver and fake-indexeddb, no Pyodide.
// The real worker path is covered by roundtrip.test.ts.
import { IDBFactory } from "fake-indexeddb";
import { canonicalJson, gridCacheKey } from "../src/cache-key.js";
import { CachedSolver } from "../src/cached-solver.js";
import { gridBytes, IndexedDbGridCache, MemoryGridCache } from "../src/grid-cache.js";
import {
  SolverError,
  type Grid, type GridRequest, type PointResult, type RuntimeInfo, type SolverPort,
} from "../src/solver-port.js";

const results: [string, boolean][] = [];
const check = (name: string, ok: boolean, note = "") => {
  results.push([name, ok]);
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${note ? "  -- " + note : ""}`);
};

function fakeGrid(req: GridRequest, seed = 1): Grid {
  const cells = [];
  for (const [i, rpm] of req.rpms.entries())
    for (const [j, load] of req.loads.entries()) {
      const src: Record<string, Float32Array> = {};
      for (const k of ["exh_flow", "int_flow", "dpdth", "inj", "valve", "slap"]) {
        const a = new Float32Array(1440);
        for (let n = 0; n < a.length; n++) a[n] = Math.sin(n * 0.01 * seed + i + j) * rpm * load;
        src[k] = a;
      }
      cells.push({ i, j, perf: { torque: rpm * load * seed }, meta: { rpm }, src });
    }
  return { rpms: req.rpms, loads: req.loads, cells };
}

class FakeSolver implements SolverPort {
  readies = 0; builds = 0;
  constructor(private readonly hash: string) {}
  async ready(): Promise<RuntimeInfo> {
    this.readies++;
    return { source_hash: this.hash, contract: 1, python: "x", numpy: "x", presets: [], preset_info: {}, grid_cycles: 9, source_keys: [], load_s: 0 };
  }
  async solvePoint(): Promise<PointResult> { throw new Error("not used"); }
  async buildGrid(req: GridRequest) { this.builds++; return fakeGrid(req); }
  dispose() {}
}

const V = "a".repeat(64);
const REQ: GridRequest = { engine: { preset: "crdi15", overrides: { "turbo.turbine_area_eff": 5e-4, afr_limit: 18 } }, rpms: [800, 1800], loads: [0, 0.5, 1] };

// ------------------------------------------------------------------- keys
{
  const k1 = await gridCacheKey({ solverVersion: V, ...REQ });
  const reordered = { engine: { overrides: { afr_limit: 18, "turbo.turbine_area_eff": 0.0005 }, preset: "crdi15" }, rpms: [800, 1800], loads: [0, 0.5, 1] };
  check("key ignores property order and number spelling (5e-4 vs 0.0005)",
        k1 === await gridCacheKey({ solverVersion: V, ...reordered }));
  check("key changes with an override value",
        k1 !== await gridCacheKey({ solverVersion: V, ...REQ, engine: { preset: "crdi15", overrides: { "turbo.turbine_area_eff": 5.1e-4, afr_limit: 18 } } }));
  check("key changes with the physics version (any solver change invalidates)",
        k1 !== await gridCacheKey({ solverVersion: "b".repeat(64), ...REQ }));
  check("key changes with grid layout order",
        k1 !== await gridCacheKey({ solverVersion: V, ...REQ, rpms: [1800, 800] }));
  check("-0 and 0 are the same key", canonicalJson(-0) === canonicalJson(0));
  let threw = false; try { canonicalJson({ a: NaN }); } catch { threw = true; }
  check("NaN cannot enter a key", threw);
  // Change detector: if this fails, every user's cache silently misses.
  // Update deliberately, and bump GRID_FORMAT if the stored shape changed.
  // GRID_FORMAT 1 -> 2 (cells carry p_cyl, ADR-011) changes the key on purpose;
  // it was 8a04d424e48c50e0b969575abda16e9bf231eea49be7fc7af3770b3c1fce4f28.
  check("key format is stable", k1 === "647d08179d62ef0c080d8bf9a51c39b8cdf89e439e1dc70c6b22422db23b653f", k1);
}

// ------------------------------------------------------------------ memory
{
  const c = new MemoryGridCache();
  await c.put("k", fakeGrid(REQ));
  const got = (await c.get("k"))!;
  got.cells[0]!.perf["torque"] = -1;
  got.cells[0]!.src["dpdth"]![0] = 12345;
  const again = (await c.get("k"))!;
  check("memory cache does not alias stored grids",
        again.cells[0]!.perf["torque"] !== -1 && again.cells[0]!.src["dpdth"]![0] !== 12345);
}

// --------------------------------------------------------------- indexeddb
{
  const idb = new IDBFactory();
  const one = gridBytes(fakeGrid(REQ));
  const c = new IndexedDbGridCache("t1", Math.floor(2.5 * one), idb);
  const g = fakeGrid(REQ, 3);
  await c.put("A", g);
  const back = (await c.get("A"))!;
  const exact = back.cells.every((cell, n) => Object.entries(cell.src).every(([k, a]) =>
    a instanceof Float32Array && a.length === 1440 &&
    Buffer.from(a.buffer).equals(Buffer.from(g.cells[n]!.src[k]!.buffer))));
  check("IndexedDB round-trip is bit-exact Float32Array", exact);

  await c.put("B", fakeGrid(REQ, 4));
  await c.get("A");                                 // A becomes most recent
  const r = await c.put("C", fakeGrid(REQ, 5));
  const u = await c.usage();
  check("LRU evicts the least recently USED, not the oldest written",
        r.stored && r.evicted.join() === "B" && !!(await c.get("A")) && !(await c.get("B")),
        `evicted ${r.evicted.join()}`);
  check("usage stays within budget", u.bytes <= u.budget, `${u.bytes} of ${u.budget} bytes`);

  const big = await new IndexedDbGridCache("t2", 1000, idb).put("X", fakeGrid(REQ));
  check("a grid larger than the budget is refused, not thrown",
        !big.stored && big.reason === "larger-than-budget");

  const reopened = new IndexedDbGridCache("t1", Math.floor(2.5 * one), idb);
  check("entries survive a reload (new instance, same database)",
        (await reopened.get("C"))?.cells[0]?.perf["torque"] === fakeGrid(REQ, 5).cells[0]!.perf["torque"]);

  class QuotaOnce extends IndexedDbGridCache {
    fails = 0;                                   // armed after setup, below
    protected override async rawPut(e: Parameters<IndexedDbGridCache["rawPut"]>[0]) {
      if (this.fails-- > 0) throw new DOMException("full", "QuotaExceededError");
      return super.rawPut(e);
    }
  }
  const q = new QuotaOnce("t3", 10 * one, idb);
  await q.put("old", fakeGrid(REQ));
  q.fails = 1;                                   // fail the write under test, not the setup
  const qr = await q.put("new", fakeGrid(REQ, 2));
  check("browser quota error: evicts one more and retries", qr.stored && qr.evicted.join() === "old", JSON.stringify(qr));

  class QuotaAlways extends IndexedDbGridCache {
    protected override async rawPut() { throw new DOMException("full", "QuotaExceededError"); }
  }
  const qa = await new QuotaAlways("t4", 10 * one, idb).put("k", fakeGrid(REQ));
  check("persistent quota failure is reported, never thrown", !qa.stored && qa.reason === "quota");
}

// ------------------------------------------------------------ CachedSolver
{
  const idb = new IDBFactory();
  const inner = new FakeSolver(V);
  const s = new CachedSolver(inner, new IndexedDbGridCache("s1", undefined, idb), V);
  await s.buildGrid(REQ);
  check("miss builds once and stores", inner.builds === 1 && s.lastCacheEvent?.outcome === "miss" && !!s.lastCacheEvent.put?.stored);

  // a fresh page load: new solver, new wrapper, same browser storage
  const inner2 = new FakeSolver(V);
  const s2 = new CachedSolver(inner2, new IndexedDbGridCache("s1", undefined, idb), V);
  const reordered = { ...REQ, engine: { overrides: { afr_limit: 18, "turbo.turbine_area_eff": 0.0005 }, preset: "crdi15" } };
  let progress = "";
  const hit = await s2.buildGrid(reordered, { onProgress: p => (progress = `${p.done}/${p.total}`) });
  check("hit after reload never boots the solver (no Pyodide)",
        inner2.readies === 0 && inner2.builds === 0 && s2.lastCacheEvent?.outcome === "hit",
        `ready() calls: ${inner2.readies}, builds: ${inner2.builds}`);
  check("hit reports completed progress", progress === "6/6");
  check("hit returns the stored grid", hit.cells.length === 6 && hit.cells[0]!.src["dpdth"] instanceof Float32Array);

  const stale = new CachedSolver(new FakeSolver("f".repeat(64)), new MemoryGridCache(), V);
  let err: SolverError | undefined;
  try { await stale.buildGrid(REQ); } catch (e) { err = e as SolverError; }
  check("stale bundle fails loudly instead of poisoning the cache",
        err?.kind === "protocol" && /stale solver bundle/.test(err.message), err?.message ?? "no error");
}

const failed = results.filter(r => !r[1]).length;
console.log(`\n${results.length - failed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
