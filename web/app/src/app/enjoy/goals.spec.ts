import { TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';
import type { ParResult } from '@dieselsim/physics';
import { bestKey, GoalBests, judge, LapRun, lapTime, parseGoal, PB_KEY, type RunFrame } from './goals';

const frame = (o: Partial<RunFrame> = {}): RunFrame =>
  ({ t: 0, throttle: 0, route_s: 0, trip_L: 0, breaker_hits: 0, engine_stopped: false, out_of_fuel: false, ...o });
const par = (o: Partial<ParResult> = {}): ParResult =>
  ({ t_s: 240, time_s: 240, fuel_L: 0.85, hits: 0, finished: true, stopped: false, ...o });

describe('P06 goals: a lap', () => {
  it('waits for the first throttle (or the first metre), then times and meters the lap to the route length', () => {
    const r = new LapRun(2500);
    expect(r.feed(frame({ t: 3, trip_L: 0.01 }))).toBe('waiting');                 // idling at the start
    expect(r.feed(frame({ t: 5, throttle: 0.04, route_s: 0.5, trip_L: 0.02 }))).toBe('waiting');
    expect(r.feed(frame({ t: 6, throttle: 0.6, route_s: 0.6, trip_L: 0.03 }))).toBe('running');
    expect(r.feed(frame({ t: 100, throttle: 0.6, route_s: 2499, trip_L: 0.4, breaker_hits: 2 }))).toBe('running');
    expect(r.feed(frame({ t: 101, throttle: 0.6, route_s: 2500.2, trip_L: 0.41, breaker_hits: 2 }))).toBe('finished');
    expect(r.t_s).toBe(95);                                  // from t = 6
    expect(r.fuel_L).toBeCloseTo(0.38, 12);                  // the idle before excluded
    expect(r.hits).toBe(2);
    expect(r.time_s).toBe(105);                              // + 5 s a breaker
    expect(r.feed(frame({ t: 200, route_s: 9000, trip_L: 9 }))).toBe('finished');   // frozen once done
    expect(r.t_s).toBe(95);
    // a car rolling off (converter creep) starts the clock too
    const creep = new LapRun(100);
    expect(creep.feed(frame({ t: 2, route_s: 1.2 }))).toBe('running');
  });

  it('fails when the engine stops (overheat) or runs dry', () => {
    const a = new LapRun(5000);
    a.feed(frame({ t: 1, throttle: 1 }));
    expect(a.feed(frame({ t: 300, throttle: 1, route_s: 3000, engine_stopped: true }))).toBe('failed');
    expect(a.failure).toBe('the engine stopped');
    const b = new LapRun(5000);
    b.feed(frame({ t: 1, throttle: 1 }));
    expect(b.feed(frame({ t: 300, route_s: 3000, out_of_fuel: true }))).toBe('failed');
    expect(b.failure).toBe('out of fuel');
  });
});

describe('P06 goals: the verdict against the par', () => {
  it('time trial: the time scores, the par\'s fuel limits', () => {
    expect(judge('time', { time_s: 230, fuel_L: 0.84 }, par())).toMatchObject({ ok: true, score: 230, limit: 0.85 });
    expect(judge('time', { time_s: 200, fuel_L: 0.86 }, par())).toMatchObject({ ok: false, why: "over the par's fuel" });
    expect(judge('time', { time_s: 200, fuel_L: 0.85 }, par()).ok).toBe(true);           // driving like the par meets it
  });
  it('economy run: the fuel scores, the par\'s time (with its penalties) limits', () => {
    expect(judge('economy', { time_s: 250, fuel_L: 0.7 }, par({ time_s: 255 }))).toMatchObject({ ok: true, score: 0.7, limit: 255 });
    expect(judge('economy', { time_s: 256, fuel_L: 0.7 }, par({ time_s: 255 }))).toMatchObject({ ok: false, why: "over the par's time" });
  });
  it('a par that never finished its lap sets no limit', () => {
    const v = judge('time', { time_s: 2000, fuel_L: 3 }, par({ finished: false, stopped: true }));
    expect(v).toMatchObject({ ok: true, limit: null });
  });
});

describe('P06 goals: bests and words', () => {
  it('keeps the lowest score per key, per browser', () => {
    localStorage.removeItem(PB_KEY);
    const b = TestBed.inject(GoalBests);
    const k = bestKey('hatch15', 'city', 'time', 'standard', 'tc');
    expect(b.get(k)).toBeUndefined();
    expect(b.offer(k, 120)).toBe(true);
    expect(b.offer(k, 125)).toBe(false);
    expect(b.offer(k, 118.5)).toBe(true);
    expect(b.get(k)).toBe(118.5);
    expect(JSON.parse(localStorage.getItem(PB_KEY)!)).toEqual({ [k]: 118.5 });
    expect(b.get(bestKey('hatch15', 'city', 'time', 'plateau', 'tc'))).toBeUndefined();   // another place, another best
  });
  it('reads goals from the link and prints lap times', () => {
    expect([parseGoal('time'), parseGoal('economy'), parseGoal('race'), parseGoal(null)]).toEqual(['time', 'economy', 'free', 'free']);
    expect([lapTime(0), lapTime(9.94), lapTime(59.96), lapTime(61.25), lapTime(238)]).toEqual(['0:00.0', '0:09.9', '1:00.0', '1:01.3', '3:58.0']);
  });
});
