// P06 tier 2 (PROPOSAL-P06-goals, decided 2026-10-20): goals on a route. One score with a
// limit from the par (a ghost lap at a constant throttle, live.par_run):
//   time trial    the fastest lap on at most the par's fuel
//   economy run   the least fuel within the par's time
// A breaker taken too fast adds BREAKER_PENALTY_S to the lap's time; an engine that stops
// (overheat) or runs dry fails the run. Personal bests are kept per browser.
import { Injectable, signal } from '@angular/core';
import { BREAKER_PENALTY_S, type ParResult } from '@dieselsim/physics';

export type GoalKind = 'free' | 'time' | 'economy';
export const GOALS: readonly { key: GoalKind; name: string }[] = [
  { key: 'free', name: 'Free drive' },
  { key: 'time', name: 'Time trial' },
  { key: 'economy', name: 'Economy run' },
];

export function parseGoal(q: string | null): GoalKind {
  return q === 'time' || q === 'economy' ? q : 'free';
}

/** What a run reads from each frame (LiveView's fields). */
export interface RunFrame {
  t: number; throttle: number; route_s: number; trip_L: number; breaker_hits: number;
  engine_stopped: boolean; out_of_fuel: boolean;
}

export type RunPhase = 'waiting' | 'running' | 'finished' | 'failed';

/**
 * One lap of a route, from the first throttle (or the car's first metre) to the route's
 * length. The par's lap starts at its first frame, at its constant throttle, so both clocks
 * start when the driving does.
 */
export class LapRun {
  phase: RunPhase = 'waiting';
  failure = '';
  private t0 = 0;
  private L0 = 0;
  private hits0 = 0;
  t_s = 0;          // the lap's elapsed time
  fuel_L = 0;
  hits = 0;

  constructor(readonly length: number) {}

  /** The lap's time with the breaker penalty. */
  get time_s(): number { return this.t_s + BREAKER_PENALTY_S * this.hits; }

  feed(f: RunFrame): RunPhase {
    if (this.phase === 'finished' || this.phase === 'failed') return this.phase;
    if (this.phase === 'waiting') {
      if (f.throttle <= 0.05 && f.route_s <= 1.0) return this.phase;
      this.phase = 'running';
      this.t0 = f.t; this.L0 = f.trip_L; this.hits0 = f.breaker_hits;
    }
    this.t_s = f.t - this.t0;
    this.fuel_L = f.trip_L - this.L0;
    this.hits = f.breaker_hits - this.hits0;
    if (f.engine_stopped || f.out_of_fuel) {
      this.phase = 'failed';
      this.failure = f.out_of_fuel ? 'out of fuel' : 'the engine stopped';
    } else if (f.route_s >= this.length) {
      this.phase = 'finished';
    }
    return this.phase;
  }
}

export interface Verdict {
  ok: boolean;
  score: number;          // the time trial's time_s, or the economy run's fuel_L
  limit: number | null;   // the par's fuel or time; null when the par didn't finish its lap
  why: string;
}

/** A finished lap against the par. A par that didn't finish (overheated, or too slow) sets no limit. */
export function judge(kind: 'time' | 'economy', lap: { time_s: number; fuel_L: number }, par: ParResult): Verdict {
  const limit = par.finished ? (kind === 'time' ? par.fuel_L : par.time_s) : null;
  const score = kind === 'time' ? lap.time_s : lap.fuel_L;
  if (limit === null) return { ok: true, score, limit, why: 'the par did not finish its lap, so there is no limit' };
  const within = kind === 'time' ? lap.fuel_L <= limit : lap.time_s <= limit;
  return { ok: within, score, limit, why: within ? 'within the par' : kind === 'time' ? 'over the par\'s fuel' : 'over the par\'s time' };
}

export const PB_KEY = 'dieselsim-goal-bests';

/** The best's key: engine, route, goal, place and gearbox (a manual box can beat an automatic's lap). */
export function bestKey(engine: string, route: string, goal: GoalKind, place: string, box: string): string {
  return [engine, route, goal, place, box].join('|');
}

/** Personal bests (lower is better for both goals), kept per browser. */
@Injectable({ providedIn: 'root' })
export class GoalBests {
  private readonly all = signal<Record<string, number>>(load());

  get(key: string): number | undefined { return this.all()[key]; }

  /** Records `score` if it beats the best; returns whether it did. */
  offer(key: string, score: number): boolean {
    const best = this.all()[key];
    if (best !== undefined && best <= score) return false;
    const next = { ...this.all(), [key]: score };
    this.all.set(next);
    try { globalThis.localStorage?.setItem(PB_KEY, JSON.stringify(next)); } catch { /* private mode: lasts the page */ }
    return true;
  }
}

function load(): Record<string, number> {
  try {
    const v = JSON.parse(globalThis.localStorage?.getItem(PB_KEY) ?? '{}') as unknown;
    if (!v || typeof v !== 'object') return {};
    return Object.fromEntries(Object.entries(v as Record<string, unknown>).filter(([, x]) => typeof x === 'number' && Number.isFinite(x))) as Record<string, number>;
  } catch { return {}; }
}

/** m:ss.s */
export function lapTime(s: number): string {
  const tenths = Math.round(s * 10);              // round first: 59.96 s is 1:00.0, not 0:60.0
  const m = Math.floor(tenths / 600), r = (tenths - 600 * m) / 10;
  return `${m}:${r < 10 ? '0' : ''}${r.toFixed(1)}`;
}
