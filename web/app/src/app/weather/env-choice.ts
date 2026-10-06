import { computed, Injectable, signal } from '@angular/core';
import type { EngineRef, EnvironmentPreset } from '@dieselsim/solver';

/** Where the chosen environment is kept between visits, like the spec edits (REVIEW-008 m-3). */
export const ENV_KEY = 'dieselsim-environment';
export const STANDARD = 'standard';

/**
 * The engine a solving page should solve, in an environment (Phase 7, ADR-016): the environment's
 * spec overrides (ambient pressure and temperature, the fuel's cetane) under the page's own. An
 * explicit spec edit of the same field wins: it was set on purpose, on this engine. No overrides
 * (standard air) leaves the reference exactly as it was, so its results and cache keys don't move.
 */
export function withEnvironment(ref: EngineRef, env: Record<string, number> | undefined): EngineRef {
  if (!env || !Object.keys(env).length) return ref;
  const r = ref as EngineRef & { overrides?: Record<string, number | boolean> };
  return { ...r, overrides: { ...env, ...(r.overrides ?? {}) } } as EngineRef;
}

function kept(): string | undefined {
  try { return globalThis.localStorage?.getItem(ENV_KEY) ?? undefined; } catch { return undefined; }
}

/**
 * The environment the solving pages use (Dyno, Grid, Cycle, Sweep, Durability). Not /spec, whose
 * values are the engine's own, and not Drive, whose weather comes from its own table (ADR-016 item 1).
 * The presets arrive with the solver's runtime info (dieselsim/environment.py).
 */
@Injectable({ providedIn: 'root' })
export class EnvChoice {
  readonly presets = signal<EnvironmentPreset[]>([]);
  readonly key = signal(kept() ?? STANDARD);
  /** the chosen preset, once the presets have arrived; a kept key this build doesn't have reads as standard */
  readonly current = computed(() => this.presets().find(p => p.key === this.key()) ?? this.presets().find(p => p.key === STANDARD));
  /** what the environment adds to a solve: nothing for standard air */
  readonly overrides = computed(() => {
    const c = this.current();
    return c && c.key !== STANDARD ? c.overrides : undefined;
  });

  set(key: string): void {
    this.key.set(key);
    try {
      if (key === STANDARD) globalThis.localStorage?.removeItem(ENV_KEY); else globalThis.localStorage?.setItem(ENV_KEY, key);
    } catch { /* storage off: the choice lasts this visit */ }
  }

  /** the reference a page solves: its engine, in the chosen environment */
  solveRef(ref: EngineRef): EngineRef { return withEnvironment(ref, this.overrides()); }
}
