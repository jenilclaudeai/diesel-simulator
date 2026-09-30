/// <reference lib="webworker" />
// The real-time loop (Phase 3): @dieselsim/physics's LiveEngine -- the
// TypeScript port held to dieselsim/live.py -- stepped at a fixed 60 Hz,
// decoupled from the page's render rate. An accumulator turns wall time
// into whole 1/60 s frames; if the tab stalls, the backlog is dropped
// rather than replayed (at most 5 frames catch up per tick).
import { Adr011Grid, handleKey, LiveEngine, pedalReturn } from '@dieselsim/physics';
import type { DashInfo, FromWorker, LiveView, Pedals, ToWorker } from './protocol';
import type { LoopSound } from './sound-protocol';

const DT = 1 / 60;
const HOLD = new Set(['w', 's', 'b', 'z']); // repeat every frame while held, like key auto-repeat
let live: LiveEngine | undefined;
let running = false;
const held = new Set<string>();
let acc = 0, last = 0, frames = 0, hzFrames = 0, hzT = 0, hz = 0;
let sound: MessagePort | null = null;      // straight to the audio thread, no page hop
let pedals: Pedals | null = null;           // touch pedals (ADR-012)

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
    phase: gb.phase, auto: gb.auto,
    tank_L: e.tank_L, out_of_fuel: e.out_of_fuel, fuel_kg_h: e.fuel_kg_h,
    fan_on: e.fan_on, T_charge: e.T_charge, derate: e.derate, engine_stopped: e.engine_stopped,
    derate_heat: e.derate_heat,
  };
}

/**
 * The speedometer's scale: the lower of the top gear at max rpm and the
 * speed where the engine's peak power, through the driveline, meets the same
 * drag and rolling resistance the driveline integrates (0.5 x 1.2 x CdA v^2 +
 * Crr m g). By gearing alone a laden 40 t truck showed 167 km/h.
 */
function topSpeedKmh(): number {
  const e = live!, s = e.spec, v = e.veh;
  const gear = (s.max_rpm / 60) * 2 * Math.PI * v.r_wheel / (v.gears[v.gears.length - 1]! * v.final);
  let P = 0;
  for (const row of e.g.perf) for (const c of row) P = Math.max(P, c['power'] ?? 0);
  P *= v.eta;
  const need = (u: number) => 0.5 * 1.2 * v.CdA * u ** 3 + v.Crr * v.mass * 9.81 * u;
  let lo = 0, hi = 150;
  for (let k = 0; k < 60; k++) { const mid = 0.5 * (lo + hi); if (need(mid) < P) lo = mid; else hi = mid; }
  return Math.min(gear, lo) * 3.6;
}

function info(): DashInfo {
  const e = live!, s = e.spec, v = e.veh, c = s.cooling;
  return {
    idle_rpm: s.idle_rpm, rated_rpm: s.rated_rpm, max_rpm: s.max_rpm,
    vmax_kmh: topSpeedKmh(),
    vehicle: v.name, tank_L: v.fuel_tank_L, gears: v.gears.length,
    T_warn: c.T_warn, T_derate: c.T_derate, T_shutdown: c.T_shutdown, fan_on_T: c.fan_on_T,
  };
}

function frame(): void {
  const e = live!;
  for (const k of held) if (HOLD.has(k)) handleKey(e, k);
  pedalReturn(e, DT);
  if (pedals) {
    // touch: the throttle follows the finger (0 once on release, then the
    // keys have it back); brake and clutch are held at least this far down
    // and otherwise spring back as the keys' do
    if (pedals.throttle !== null) {
      e.throttle = pedals.throttle;
      if (pedals.throttle === 0) pedals.throttle = null;
    }
    e.dl.brake = Math.max(e.dl.brake, pedals.brake);
    if (e.veh.trans === 'manual') e.dl.clutch_pedal = Math.max(e.dl.clutch_pedal, pedals.clutch);
  }
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
  if (n) {
    post({ type: 'state', view: view() });
    if (sound) {
      const e = live;
      // play.py's rule: silent only when stalled (a stopped engine still turns)
      const s: LoopSound = { rpm: e.rpm, load: e.load_eff, T: e.T_coolant, live: e.sound_inputs(), running: !e.stalled };
      sound.postMessage(s);
    }
  }
}

setInterval(tick, 4);

addEventListener('message', (ev: MessageEvent<ToWorker>) => {
  const m = ev.data;
  switch (m.type) {
    case 'load': {
      const grid = new Adr011Grid(m.grid.spec, m.grid);
      live = new LiveEngine(grid, m.grid.preset, m.trans, m.grid.engine_view);
      frames = 0; held.clear();
      post({ type: 'info', info: info() });
      post({ type: 'state', view: view() });
      break;
    }
    case 'run': running = true; last = hzT = performance.now(); acc = 0; hzFrames = 0; break;
    case 'pause': running = false; break;
    case 'sound': sound = m.port; break;
    case 'pedals': pedals = { ...m.pedals }; break;
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
