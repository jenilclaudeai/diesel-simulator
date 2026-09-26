// Differential tests for the live-loop port (ADR-004 addendum: per-step and
// terminal bounds) against fixtures/live.json, which dieselsim/live.py wrote.
//
//   per-step  load Python's state before step k, take one TypeScript step,
//             compare every field with Python's state after it: 1e-12 rel
//             (floored at 1e-9 absolute), strings, booleans and null exactly
//   terminal  run the whole scripted 60 s drive free: the list of discrete
//             events (gear, shift phase, lock-up, rigid, neutral -- with the
//             step each happened at) must be identical, and the final
//             integrated quantities within 1e-6 rel
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import type { LiveSpec, Perf } from "../src/live/common.js";
import { handleKey, LiveEngine, pedalReturn, type LiveState } from "../src/live/engine.js";
import { PerfGrid } from "../src/live/grid.js";
import { finishVehicle, vehicleFor, type Transmission } from "../src/live/vehicle.js";

const here = path.dirname(fileURLToPath(import.meta.url));
const fx = JSON.parse(readFileSync(path.resolve(here, "..", "..", "fixtures", "live.json"), "utf8")) as {
  meta: { physics_hash: string };
  inputs: {
    preset: string; spec: LiveSpec; sample_every: number;
    grid: { rpms: number[]; loads: number[]; perf: Perf[][] };
    drives: { name: string; trans: Transmission; script: Script; init: Record<string, number> }[];
  };
  outputs: Record<string, {
    veh: Record<string, unknown>;
    snapshots: { step: number; before: LiveState; after: LiveState }[];
    events: number[][];
    hints: [number, string][];
    trace: number[][];
    final: Record<string, number>;
  }>;
};

interface Script {
  dt: number; n: number; throttle: number[]; brake: [number, number, number][];
  grade: [number, number][]; keys: [number, string][]; holds?: [number, number, string][];
}

const results: [string, boolean][] = [];
const check = (name: string, ok: boolean, note = "") => {
  results.push([name, ok]);
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${note ? "  -- " + note : ""}`);
};

const PER_STEP = 1e-12, TERMINAL = 1e-6;
const grid = new PerfGrid(fx.inputs.spec, fx.inputs.grid.rpms, fx.inputs.grid.loads, fx.inputs.grid.perf);
const fresh = (tr: Transmission) => new LiveEngine(grid, fx.inputs.preset, tr);

/** Worst relative difference between two states; Infinity on a structural or exact mismatch. */
function diffState(got: LiveState, want: LiveState): { worst: number; where: string } {
  let worst = 0, where = "";
  for (const part of ["live", "dl", "gb", "tc"] as const) {
    const g = got[part], w = want[part];
    const keys = new Set([...Object.keys(g), ...Object.keys(w)]);
    for (const k of keys) {
      const a = g[k], b = w[k];
      if (!(k in g) || !(k in w)) return { worst: Infinity, where: `${part}.${k} missing on one side` };
      if (typeof b === "number" && typeof a === "number") {
        const r = Math.abs(a - b) / Math.max(Math.abs(b), 1e-9);
        if (!(r <= worst)) { worst = Number.isNaN(r) ? Infinity : r; where = `${part}.${k} (${a} vs ${b})`; }
      } else if (k === "perf") {
        for (const [pk, pv] of Object.entries(b as Perf)) {
          const pa = (a as Perf)[pk]!;
          const r = Math.abs(pa - pv) / Math.max(Math.abs(pv), 1e-9);
          if (!(r <= worst)) { worst = Number.isNaN(r) ? Infinity : r; where = `${part}.perf.${pk}`; }
        }
      } else if (a !== b) {
        return { worst: Infinity, where: `${part}.${k}: ${JSON.stringify(a)} vs ${JSON.stringify(b)}` };
      }
    }
  }
  return { worst, where };
}

/** The fixture generator's live_run(), in TypeScript. */
function drive(d: (typeof fx.inputs.drives)[number]) {
  const live = fresh(d.trans), sc = d.script;
  for (const [k, v] of Object.entries(d.init)) {  // dotted paths: "dl.gb.gear"
    const path = k.split("."), last = path.pop()!;
    let obj = live as unknown as Record<string, unknown>;
    for (const p of path) obj = obj[p] as Record<string, unknown>;
    obj[last] = v;
  }
  const keys = new Map(sc.keys), grade = new Map(sc.grade);
  const events: number[][] = [], hints: [number, string][] = [];
  let prev = "", prevHint = "";
  for (let n = 0; n < sc.n; n++) {
    const t = n * sc.dt;
    if (!live.cruise_on) live.throttle = sc.throttle[n]!;
    for (const [t0, t1, b] of sc.brake) if (t0 <= t && t < t1) live.dl.brake = b;
    if (grade.has(n)) live.dl.grade = grade.get(n)!;
    for (const [t0, t1, k] of sc.holds ?? []) if (t0 <= t && t < t1) handleKey(live, k); // held keys repeat
    if (keys.has(n)) handleKey(live, keys.get(n)!);
    pedalReturn(live, sc.dt);
    live.step(sc.dt);
    const gb = live.dl.gb;
    const ev = [gb.gear, gb.phase, +live.dl.lockup, +live.dl.rigid, +gb.neutral, +live.dl.lock_allowed, +live.fan_on,
      +live.stalled, +live.dl.assist];
    if (ev.join() !== prev) { events.push([n, ...ev]); prev = ev.join(); }
    if (live.hint !== prevHint) { hints.push([n, live.hint]); prevHint = live.hint; }
  }
  return { live, events, hints };
}

for (const drv of fx.inputs.drives) {
  const tr = drv.name;
  const out = fx.outputs[tr]!;

  // ---- vehicle parameters ----
  const veh = finishVehicle(vehicleFor(fx.inputs.preset, drv.trans)) as unknown as Record<string, unknown>;
  const vehBad = Object.keys(out.veh).filter(k => JSON.stringify(veh[k]) !== JSON.stringify(out.veh[k]));
  check(`${tr}: vehicle parameters match Python`, vehBad.length === 0 && Object.keys(veh).length === Object.keys(out.veh).length,
    vehBad.length ? `differ: ${vehBad.join(", ")}` : `${Object.keys(out.veh).length} fields`);

  // ---- per-step ----
  let worst = 0, where = "";
  for (const s of out.snapshots) {
    const e = fresh(drv.trans);
    e.setState(s.before);
    e.step(drv.script.dt);
    const d = diffState(e.getState(), s.after);
    if (!(d.worst <= worst)) { worst = d.worst; where = `step ${s.step}: ${d.where}`; }
  }
  check(`${tr}: per-step, one TypeScript step from Python's state (${out.snapshots.length} steps)`, worst <= PER_STEP,
    `worst rel ${worst.toExponential(2)}${where ? " at " + where : ""} (bound ${PER_STEP})`);

  // ---- terminal ----
  const { live, events, hints } = drive(drv);
  const firstBad = events.findIndex((e, i) => JSON.stringify(e) !== JSON.stringify(out.events[i]));
  check(`${tr}: terminal, every discrete event at the same step`, events.length === out.events.length && firstBad < 0,
    firstBad < 0 && events.length === out.events.length ? `${events.length} events (gear, shift phase, lock-up, rigid, neutral)`
      : `first mismatch at #${firstBad}: TS ${JSON.stringify(events[firstBad])} vs Python ${JSON.stringify(out.events[firstBad])}; ${events.length} vs ${out.events.length}`);
  check(`${tr}: terminal, every driver message at the same step`, JSON.stringify(hints) === JSON.stringify(out.hints),
    `${hints.length} messages: ${hints.map(h => JSON.stringify(h[1])).join(", ")}`);
  const fin: Record<string, number> = {
    rpm: live.rpm, odo_m: live.odo_m, trip_m: live.trip_m, fuel_L: live.fuel_L, trip_L: live.trip_L,
    T_coolant: live.T_coolant, boost: live.boost, turbo_rpm: live.turbo_rpm, tank_L: live.tank_L,
    inst_kmpl: live.inst_kmpl, v: live.dl.v, fan_frac: live.fan_frac, fan_power: live.fan_power, derate: live.derate,
  };
  let tw = 0, tk = "";
  for (const [k, want] of Object.entries(out.final)) {
    const r = Math.abs(fin[k]! - want) / Math.max(Math.abs(want), 1e-9);
    if (!(r <= tw)) { tw = r; tk = `${k} (${fin[k]} vs ${want})`; }
  }
  check(`${tr}: terminal, final integrated quantities after ${(drv.script.n * drv.script.dt).toFixed(0)} s`, tw <= TERMINAL,
    `worst rel ${tw.toExponential(2)} at ${tk} (bound ${TERMINAL}); ${(live.dl.v * 3.6).toFixed(3)} km/h, ${live.trip_L.toFixed(5)} L`);
}

// ---- the test of the test: a 1e-9 nudge in one state value must fail the per-step bound ----
{
  const drv = fx.inputs.drives[0]!;
  const s = fx.outputs[drv.name]!.snapshots[10]!;
  const nudged = structuredClone(s.before);
  (nudged.live as Record<string, number>)["rpm"]! *= 1 + 1e-9;
  const e = fresh(drv.trans);
  e.setState(nudged);
  e.step(drv.script.dt);
  const d = diffState(e.getState(), s.after);
  check("self-test: a 1e-9 nudge to rpm fails the per-step bound", d.worst > PER_STEP, `gives ${d.worst.toExponential(2)} at ${d.where}`);
}

const failed = results.filter(([, ok]) => !ok).length;
console.log(`\n${results.length - failed} passed, ${failed} failed  (physics ${fx.meta.physics_hash.slice(0, 12)})`);
process.exit(failed ? 1 : 0);
