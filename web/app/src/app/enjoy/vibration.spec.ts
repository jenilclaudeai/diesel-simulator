import { TestBed } from '@angular/core/testing';
import {
  breakerPattern, eventPattern, firingHz, LIMITER, shakePattern, SHIFT, STALL, START, VIBRATION_KEY, VibrationSetting, Vibrator,
  type VibInfo, type VibState,
} from './vibration';

const I4: VibInfo = { idle_rpm: 800, max_rpm: 4600, cylinders: 4 };
const SINGLE: VibInfo = { idle_rpm: 600, max_rpm: 2200, cylinders: 1 };
const st = (o: Partial<VibState> = {}): VibState =>
  ({ rpm: 800, gear: '1', throttle: 0, stalled: false, engine_stopped: false, ...o });

describe('P01 vibration', () => {
  it('a four-stroke fires once per cylinder every two turns', () => {
    expect(firingHz(800, 4)).toBeCloseTo(26.667, 3);
    expect(firingHz(600, 1)).toBe(5);
  });

  it('events: stall, start, a gear change, the limiter; nothing on a steady frame', () => {
    expect(eventPattern(st(), st({ stalled: true, rpm: 0 }), I4)).toBe(STALL);
    expect(eventPattern(st({ stalled: true, rpm: 0 }), st(), I4)).toBe(START);
    expect(eventPattern(st({ gear: '1' }), st({ gear: '2', rpm: 2000 }), I4)).toBe(SHIFT);
    expect(eventPattern(st({ rpm: 4400 }), st({ rpm: 4560 }), I4)).toBe(LIMITER);
    expect(eventPattern(st({ rpm: 4560 }), st({ rpm: 4570 }), I4)).toBeNull();     // only on reaching it
    expect(eventPattern(st(), st(), I4)).toBeNull();
    expect(eventPattern(null, st(), I4)).toBeNull();
  });

  it('P06: a speed breaker hit too fast buzzes twice (front axle, rear), harder for a harder jolt', () => {
    const hit = eventPattern(st({ breaker_hits: 2 }), st({ breaker_hits: 3, jolt: 0.5 }), I4)!;
    expect(hit).toEqual(breakerPattern(0.5));
    expect(hit).toHaveLength(3);
    expect(breakerPattern(1)[0]!).toBeGreaterThan(breakerPattern(0.2)[0]!);
    expect(breakerPattern(1)[2]!).toBeGreaterThan(breakerPattern(0.2)[2]!);
    expect(breakerPattern(5)).toEqual(breakerPattern(1));                          // clipped
    expect(eventPattern(st({ breaker_hits: 3 }), st({ breaker_hits: 3, jolt: 0.5 }), I4)).toBeNull();
    expect(eventPattern(st(), st({ jolt: 0.5 }), I4)).toBeNull();                  // no route: no hits
    // stalling on the breaker: the stall wins
    expect(eventPattern(st({ breaker_hits: 0 }), st({ breaker_hits: 1, jolt: 1, stalled: true, rpm: 0 }), I4)).toBe(STALL);
  });

  it('the shake: pulsed at the firing rate for the single, a light buzz for a four, stronger when lugging, none cruising', () => {
    const single = shakePattern(st({ rpm: 600 }), SINGLE)!;
    expect(single.slice(0, 2)).toEqual([35, 165]);                     // 5 Hz: 200 ms a firing
    const four = shakePattern(st({ rpm: 800 }), I4)!;
    expect(four.slice(0, 2)).toEqual([12, 38]);                        // 27 Hz is too fast: a 24% buzz
    const lug = shakePattern(st({ rpm: 1000, throttle: 0.9 }), I4)!;
    expect(lug.slice(0, 2)).toEqual([25, 25]);                         // 50%: stronger
    expect(four.reduce((a, b) => a + b, 0)).toBeGreaterThanOrEqual(400);
    expect(shakePattern(st({ rpm: 2500, throttle: 0.3 }), I4)).toBeNull();
    expect(shakePattern(st({ rpm: 0, stalled: true }), I4)).toBeNull();
  });

  it('the controller: an event plays whole, the shake is refreshed every 300 ms and stopped when idling ends', () => {
    const calls: (number[] | number)[] = [];
    const v = new Vibrator(p => { calls.push(p); return true; });
    v.started();
    v.frame(st(), I4, 0);                                              // the first running frame: START
    expect(calls).toEqual([START]);
    v.frame(st(), I4, 100);                                            // START is 340 ms long: no shake yet
    expect(calls.length).toBe(1);
    v.frame(st(), I4, 400);                                            // idle: the shake starts
    expect(calls.length).toBe(2);
    v.frame(st(), I4, 550);                                            // within 300 ms: no new call
    expect(calls.length).toBe(2);
    v.frame(st(), I4, 710);                                            // refreshed
    expect(calls.length).toBe(3);
    v.frame(st({ rpm: 2500, throttle: 0.4 }), I4, 800);                // driving off: the motor stops
    expect(calls.at(-1)).toBe(0);
    v.frame(st({ rpm: 2600, gear: '2', throttle: 0.4 }), I4, 900);     // a shift: one jolt
    expect(calls.at(-1)).toBe(SHIFT);
    v.stop();
    expect(calls.at(-1)).toBe(0);
  });

  it("the start's shudder survives the page stopping the motor while the engine loads", () => {
    const calls: (number[] | number)[] = [];
    const v = new Vibrator(p => { calls.push(p); return true; });
    v.started();          // the Start tap
    v.stop();             // Enjoy's effect while the status is still 'loading'
    v.stop();
    v.frame(st(), I4, 0); // the first running frame
    expect(calls[0]).toBe(START);
  });

  it('the switch: on by default, off kept per browser, on clears it', () => {
    localStorage.removeItem(VIBRATION_KEY);
    TestBed.resetTestingModule();
    const s = TestBed.inject(VibrationSetting);
    expect(s.on()).toBe(true);
    s.set(false);
    expect(localStorage.getItem(VIBRATION_KEY)).toBe('off');
    s.set(true);
    expect(localStorage.getItem(VIBRATION_KEY)).toBeNull();
  });
});
