import { beforeEach, describe, expect, it } from 'vitest';
import type { EnvironmentPreset } from '@dieselsim/solver';
import { ENV_KEY, EnvChoice, withEnvironment } from './env-choice';

const PLATEAU = { 'thermal.ambient_p': 65764, 'thermal.ambient_T': 293.15, 'inj.cetane_number': 51 };
const preset = (key: string, overrides: Record<string, number>): EnvironmentPreset => ({
  key, name: key, place: key, altitude_m: 0, T_C: 25, rh_pct: 50, fuel: 'x', cetane: null, cfpp_C: null, sources: '',
  p_amb: 101325, T_amb: 298, humidity_g_kg: 10.7, overrides,
});
const PRESETS = [preset('standard', { 'thermal.ambient_p': 101325, 'thermal.ambient_T': 298 }), preset('plateau', PLATEAU)];

describe('withEnvironment', () => {
  it('leaves the reference untouched in standard air (no overrides): results and cache keys do not move', () => {
    const ref = { preset: 'crdi15', overrides: { 'geom.compression_ratio': 17 } };
    expect(withEnvironment(ref, undefined)).toBe(ref);
    expect(withEnvironment(ref, {})).toBe(ref);
  });

  it("puts the environment under the page's own overrides: an explicit spec edit of the same field wins", () => {
    expect(withEnvironment({ preset: 'crdi15' }, PLATEAU)).toEqual({ preset: 'crdi15', overrides: PLATEAU });
    expect(withEnvironment({ preset: 'crdi15', overrides: { 'thermal.ambient_T': 250, 'geom.bore': 0.09 } }, PLATEAU))
      .toEqual({ preset: 'crdi15', overrides: { ...PLATEAU, 'thermal.ambient_T': 250, 'geom.bore': 0.09 } });
  });

  it('applies to a custom engine too', () => {
    const h = { displacement: 2, n_cyl: 4 } as never;
    expect(withEnvironment({ headline: h }, PLATEAU)).toEqual({ headline: h, overrides: PLATEAU });
  });
});

describe('EnvChoice', () => {
  beforeEach(() => localStorage.clear());

  it('adds nothing in standard air, and the plateau overrides once chosen; the choice survives a reload', () => {
    const a = new EnvChoice();
    a.presets.set(PRESETS);
    const ref = { preset: 'crdi15' };
    expect([a.key(), a.overrides(), a.solveRef(ref)]).toEqual(['standard', undefined, ref]);
    a.set('plateau');
    expect(a.solveRef(ref)).toEqual({ preset: 'crdi15', overrides: PLATEAU });
    const b = new EnvChoice();
    b.presets.set(PRESETS);
    expect([b.key(), b.overrides()]).toEqual(['plateau', PLATEAU]);
    b.set('standard');
    expect(localStorage.getItem(ENV_KEY)).toBeNull();
  });

  it('reads a kept key this build no longer has as standard air', () => {
    localStorage.setItem(ENV_KEY, 'atlantis');
    const c = new EnvChoice();
    c.presets.set(PRESETS);
    expect([c.current()?.key, c.overrides()]).toEqual(['standard', undefined]);
  });
});
