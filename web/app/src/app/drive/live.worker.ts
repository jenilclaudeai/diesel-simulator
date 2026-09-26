/// <reference lib="webworker" />
// The real-time loop (Phase 3): @dieselsim/physics's LiveEngine -- the
// TypeScript port held to dieselsim/live.py -- stepped at a fixed 60 Hz,
// decoupled from the page's render rate. An accumulator turns wall time
// into whole 1/60 s frames; if the tab stalls, the backlog is dropped
// rather than replayed (at most 5 frames catch up per tick).
import { Adr011Grid, handleKey, LiveEngine, pedalReturn } from '@dieselsim/physics';
import type { FromWorker, LiveView, ToWorker } from './protocol';

const DT = 1 / 60;
const HOLD = new Set(['w', 's', 'b', 'z']); // repeat every frame while held, like key auto-repeat
let live: LiveEngine | undefined;
let running = false;
const held = new Set<string>();
let acc = 0, last = 0, frames = 0, hzFrames = 0, hzT = 0, hz = 0;

const post = (m: FromWorker) => postMessage(m);

function view(): LiveView {
  const e = live!, d = e.dl, gb = d.gb;
  return {
    t: frames * DT, frames, hz,
    rpm: e.rpm, kmh: d.v * 3.6, gear: gb.neutral ? 'N' : String(gb.gear + 1), trans: e.veh.trans,
    throttle: e.throttle, brake: d.brake, clutch: d.clutch_pedal, grade: d.grade,
    boost: e.boost, T_coolant: e.T_coolant, T_oil: e.T_oil, fmep_bar: e.fmep_live / 1e5, torque: e.torque,
    hint: e.hint, overheat: e.overheat_msg, stalled: e.stalled, assist: d.assist, cruise: e.cruise_on,
    lockup: d.lockup, trip_L: e.trip_L, trip_km: e.trip_m / 1000, inst_kmpl: e.inst_kmpl,
  };
}

function frame(): void {
  const e = live!;
  for (const k of held) if (HOLD.has(k)) handleKey(e, k);
  pedalReturn(e, DT);
  e.step(DT);
  frames++;
  hzFrames++;
}

function tick(): void {
  if (!live || !running) return;
  const now = performance.now();
  acc += now - last;
  last = now;
  if (acc > 250) acc = 0; // the tab was asleep: drop the backlog
  let n = 0;
  while (acc >= DT * 1000 && n < 5) { frame(); acc -= DT * 1000; n++; }
  if (now - hzT >= 1000) { hz = (hzFrames * 1000) / (now - hzT); hzFrames = 0; hzT = now; }
  if (n) post({ type: 'state', view: view() });
}

setInterval(tick, 4);

addEventListener('message', (ev: MessageEvent<ToWorker>) => {
  const m = ev.data;
  switch (m.type) {
    case 'load': {
      const grid = new Adr011Grid(m.grid.spec, m.grid);
      live = new LiveEngine(grid, m.grid.preset, m.trans, m.grid.engine_view);
      frames = 0; held.clear();
      post({ type: 'state', view: view() });
      break;
    }
    case 'run': running = true; last = hzT = performance.now(); acc = 0; hzFrames = 0; break;
    case 'pause': running = false; break;
    case 'key':
      if (!live) break;
      if (m.down) {
        if (HOLD.has(m.key)) held.add(m.key);
        handleKey(live, m.key);
      } else {
        held.delete(m.key);
      }
      break;
    case 'script': {
      // frame-exact, as fast as possible: the fixture generator's live_run()
      if (!live) break;
      running = false;
      const e = live, sc = m.script;
      for (const [k, v] of Object.entries(m.init)) (e as unknown as Record<string, number>)[k] = v;
      if (Object.keys(m.init).length) e.update_friction();
      const keys = new Map(sc.keys), grade = new Map(sc.grade);
      const events: number[][] = [];
      let prev = '';
      const t0 = performance.now();
      for (let n = 0; n < sc.n; n++) {
        const t = n * sc.dt;
        if (!e.cruise_on) e.throttle = sc.throttle[n]!;
        for (const [a, b, br] of sc.brake) if (a <= t && t < b) e.dl.brake = br;
        if (grade.has(n)) e.dl.grade = grade.get(n)!;
        for (const [a, b, k] of sc.holds ?? []) if (a <= t && t < b) handleKey(e, k);
        if (keys.has(n)) handleKey(e, keys.get(n)!);
        pedalReturn(e, sc.dt);
        e.step(sc.dt);
        const gb = e.dl.gb;
        const evt = [gb.gear, gb.phase, +e.dl.lockup, +e.dl.rigid, +gb.neutral, +e.dl.lock_allowed, +e.fan_on, +e.stalled, +e.dl.assist];
        if (evt.join() !== prev) { events.push([n, ...evt]); prev = evt.join(); }
      }
      post({ type: 'scriptResult', events, frames: sc.n, ms: performance.now() - t0, final: {
        rpm: e.rpm, v: e.dl.v, odo_m: e.odo_m, trip_L: e.trip_L, T_coolant: e.T_coolant, T_oil: e.T_oil,
        fmep_live: e.fmep_live, boost: e.boost,
      } });
      break;
    }
  }
});

post({ type: 'ready' });
