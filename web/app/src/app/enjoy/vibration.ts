// P01 (ADR-016 item 7): the phone vibrates in /enjoy. The owner's choices
// (2026-10-19): events (start, stall, gear change, the limiter) plus a shake
// while idling or lugging; on by default, with a switch kept per browser.
// Widened 2026-10-21: the owner expected it while driving too, so the shake
// now runs whenever the engine does and follows the pedal, and idle is firmer
// (it was 12 ms of every 50, likely too short for a phone's motor to feel).
//
// The Vibration API (Android Chrome; none on iOS Safari) takes on/off
// durations only, with no strength, and a new call replaces the running
// pattern. Chrome on Android drops every call while the phone is on Mute
// (VibrationManagerAndroid.java: ringer mode SILENT), with no error. A
// phone's motor can't follow a 4-cylinder's 27 Hz idle firing, so the shake
// pulses at the firing rate only up to FIRING_PULSE_HZ (the single at idle,
// ~5 Hz) and is a buzz above it; "stronger" is a longer on-time.
import { Injectable, signal } from '@angular/core';

export const VIBRATION_KEY = 'dieselsim-vibration';
export const FIRING_PULSE_HZ = 12;

// event patterns [on, off, on, ...] in ms
export const START = [60, 40, 60, 40, 140];       // the engine catching: a short shudder
export const STALL = [160, 50, 90, 60, 40];       // dying: strong, then fading
export const SHIFT = [45];                        // a gear change: one jolt
export const LIMITER = [30, 30, 30, 30, 30];      // bouncing off the limiter

/** P06: a speed breaker taken too fast -- the front axle, then the rear; longer on-times for a harder jolt (0-1). */
export function breakerPattern(jolt: number): number[] {
  const j = Math.min(1, Math.max(0, jolt));
  return [Math.round(50 + 110 * j), 70, Math.round(30 + 80 * j)];
}

export interface VibState {
  rpm: number; gear: string; throttle: number; stalled: boolean; engine_stopped: boolean;
  breaker_hits?: number; jolt?: number;   // P06: absent or 0 without a route
}
export interface VibInfo { idle_rpm: number; max_rpm: number; cylinders: number }

/** A four-stroke's firing rate [Hz]: one firing per cylinder every two turns. */
export function firingHz(rpm: number, cylinders: number): number {
  return (rpm / 60) * cylinders / 2;
}

const running = (s: VibState, i: VibInfo) => !s.stalled && !s.engine_stopped && s.rpm > 0.5 * i.idle_rpm;

/** The event between two frames, if any: start, stall, a speed breaker hit, a gear change, the limiter reached. */
export function eventPattern(prev: VibState | null, now: VibState, info: VibInfo): number[] | null {
  if (!prev) return null;
  if (!prev.stalled && now.stalled) return STALL;
  if ((now.breaker_hits ?? 0) > (prev.breaker_hits ?? 0)) return breakerPattern(now.jolt ?? 1);
  if (!running(prev, info) && running(now, info)) return START;
  if (running(now, info) && prev.gear !== now.gear) return SHIFT;
  const lim = 0.985 * info.max_rpm;
  if (prev.rpm < lim && now.rpm >= lim) return LIMITER;
  return null;
}

// the buzz's on-time of every BUZZ_MS (the owner's choice, 2026-10-21): idle, lugging, and
// driving from CRUISE_ON with the pedal up to FULL_ON
export const BUZZ_MS = 50;
export const IDLE_ON = 20, LUG_ON = 35, CRUISE_ON = 15, FULL_ON = 35;
// the same for the firing-rate pulse (the single): its on-time per firing
const PULSE_IDLE_ON = 35, PULSE_LUG_ON = 55, PULSE_CRUISE_ON = 30, PULSE_FULL_ON = 55;

/**
 * The shake for the next `windowMs`, whenever the engine runs (else null): firmer
 * idling (near idle rpm, pedal up), firmest lugging (low rpm, pedal down), and in
 * between it follows the pedal. Pulsed at the firing rate where a phone can feel
 * it, a buzz above that.
 */
export function shakePattern(s: VibState, info: VibInfo, windowMs = 400): number[] | null {
  if (!running(s, info)) return null;
  const idling = s.rpm < 1.25 * info.idle_rpm && s.throttle < 0.15;
  const lugging = s.rpm < 1.4 * info.idle_rpm && s.throttle > 0.5;
  const pedal = Math.min(1, Math.max(0, s.throttle));
  const f = firingHz(s.rpm, info.cylinders);
  let on: number, off: number;
  if (f <= FIRING_PULSE_HZ) {
    const period = 1000 / f;
    on = lugging ? PULSE_LUG_ON : idling ? PULSE_IDLE_ON : PULSE_CRUISE_ON + (PULSE_FULL_ON - PULSE_CRUISE_ON) * pedal;
    off = Math.max(10, period - on);
  } else {
    on = lugging ? LUG_ON : idling ? IDLE_ON : CRUISE_ON + (FULL_ON - CRUISE_ON) * pedal;
    off = BUZZ_MS - on;
  }
  const out: number[] = [];
  for (let t = 0; t < windowMs; t += on + off) out.push(Math.round(on), Math.round(off));
  return out;
}

/** What the start screen's Test tap says: whether the browser has vibration, took the call, and what to check if nothing was felt. */
export function testNote(supported: boolean, accepted: boolean): string {
  if (!supported) return 'This browser has no vibration (iPhones and iPads have none).';
  if (!accepted) return 'The browser refused to vibrate: tap the page once, then try again.';
  return 'Sent: a short buzz. Felt nothing? On Mute, Chrome stays still: switch the phone to Vibrate or Sound, and check its vibration settings.';
}

const total = (p: number[]) => p.reduce((a, b) => a + b, 0);

/**
 * Drives navigator.vibrate from the live frames: an event plays whole (the
 * shake waits for it), the shake is refreshed every `refreshMs` (its pattern
 * overlaps, so the motor never stops between calls, and a pedal change is felt
 * within `refreshMs`) and stopped when the engine stops.
 */
export class Vibrator {
  private prev: VibState | null = null;
  private busyUntil = 0;
  private nextShake = 0;
  private shaking = false;
  private armed = false;

  constructor(private readonly vibrate: (p: number[] | number) => boolean, private readonly refreshMs = 300) {}

  /** The Start tap: the first running frame plays START (a first frame has no previous one to compare). */
  started(): void { this.armed = true; this.prev = null; }

  frame(now: VibState, info: VibInfo, tMs: number): void {
    let ev = eventPattern(this.prev, now, info);
    if (this.armed && running(now, info)) { ev = START; this.armed = false; }
    this.prev = now;
    if (ev) {
      this.vibrate(ev);
      this.busyUntil = tMs + total(ev);
      this.shaking = false;
      return;
    }
    if (tMs < this.busyUntil) return;
    const shake = shakePattern(now, info);
    if (shake) {
      if (!this.shaking || tMs >= this.nextShake) {
        this.vibrate(shake);
        this.nextShake = tMs + this.refreshMs;
        this.shaking = true;
      }
    } else if (this.shaking) {
      this.vibrate(0);
      this.shaking = false;
    }
  }

  /**
   * Not driving (stopped, loading) or vibration switched off: stop the motor and forget the last
   * frame. The start stays armed: Enjoy calls this while the engine loads, between the Start tap
   * (started()) and the first frame, and disarming here lost every start's shudder (the e2e found it).
   */
  stop(): void {
    if (this.shaking || this.busyUntil > 0) this.vibrate(0);
    this.prev = null;
    this.busyUntil = 0;
    this.shaking = false;
  }
}

function restoreOn(): boolean {
  try { return globalThis.localStorage?.getItem(VIBRATION_KEY) !== 'off'; } catch { return true; }
}

/** The switch: on unless turned off, kept per browser. */
@Injectable({ providedIn: 'root' })
export class VibrationSetting {
  readonly on = signal(restoreOn());

  set(on: boolean): void {
    this.on.set(on);
    try {
      if (on) globalThis.localStorage?.removeItem(VIBRATION_KEY);
      else globalThis.localStorage?.setItem(VIBRATION_KEY, 'off');
    } catch { /* private mode: the choice lasts the page */ }
  }
}
