import { TestBed } from '@angular/core/testing';
import {
  eventPattern, firingHz, LIMITER, shakePattern, SHIFT, STALL, START, testNote, VIBRATION_KEY, VibrationSetting, Vibrator,
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

  it('the shake: pulsed at the firing rate for the single, a buzz for a four, firmest lugging', () => {
    const single = shakePattern(st({ rpm: 600 }), SINGLE)!;
    expect(single.slice(0, 2)).toEqual([35, 165]);                     // 5 Hz: 200 ms a firing
    const four = shakePattern(st({ rpm: 800 }), I4)!;
    expect(four.slice(0, 2)).toEqual([20, 30]);                        // 27 Hz is too fast: a 40% buzz (was 12 of 50)
    const lug = shakePattern(st({ rpm: 1000, throttle: 0.9 }), I4)!;
    expect(lug.slice(0, 2)).toEqual([35, 15]);                         // 70%: firmest
    expect(four.reduce((a, b) => a + b, 0)).toBeGreaterThanOrEqual(400);
    expect(shakePattern(st({ rpm: 0, stalled: true }), I4)).toBeNull();
    expect(shakePattern(st({ rpm: 2000, engine_stopped: true }), I4)).toBeNull();
  });

  it('driving (2026-10-21): the shake runs whenever the engine does and follows the pedal', () => {
    const on = (rpm: number, throttle: number, i = I4) => shakePattern(st({ rpm, throttle }), i)!.slice(0, 2);
    expect(on(2000, 0)).toEqual([15, 35]);                             // coasting: the lightest
    expect(on(2500, 0.3)).toEqual([21, 29]);
    expect(on(3000, 1)).toEqual([35, 15]);                             // full throttle
    expect(on(3000, 1.4)).toEqual([35, 15]);                           // the pedal clamped
    expect(on(1000, 0.4, SINGLE)).toEqual([40, 80]);                   // the single at 8.3 Hz: 30 + 25 * 0.4 per firing
    expect(on(1000, 0, SINGLE)).toEqual([30, 90]);
  });

  it("the Test tap's note: no API, refused, or sent with what to check", () => {
    expect(testNote(false, false)).toContain('no vibration');
    expect(testNote(true, false)).toContain('refused');
    expect(testNote(true, true)).toContain('Mute');
  });

  it('the controller: an event plays whole, the shake is refreshed every 300 ms, follows the pedal and stops with the engine', () => {
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
    v.frame(st({ rpm: 2500, throttle: 0.4 }), I4, 800);                // driving off: the idle buzz runs on
    expect(calls.length).toBe(3);
    v.frame(st({ rpm: 2500, throttle: 0.4 }), I4, 1010);               // refreshed with the pedal's buzz
    expect((calls.at(-1) as number[]).slice(0, 2)).toEqual([23, 27]);
    v.frame(st({ rpm: 2600, gear: '2', throttle: 0.4 }), I4, 1100);    // a shift: one jolt
    expect(calls.at(-1)).toBe(SHIFT);
    v.frame(st({ rpm: 2600, gear: '2', throttle: 0.4 }), I4, 1200);    // the buzz back after the jolt
    expect((calls.at(-1) as number[]).slice(0, 2)).toEqual([23, 27]);
    v.frame(st({ rpm: 2600, gear: '2', engine_stopped: true }), I4, 1300); // the engine stopped: the motor stops
    expect(calls.at(-1)).toBe(0);
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
