import { beforeEach, describe, expect, it } from 'vitest';
import { editedEngine, MY, type MyEngine } from '../engine/my-engines';
import { DRIVE_GEARBOX_KEY, DriveEnv } from '../weather/drive-env';
import { applyProject, currentProject, engineChoice, parseProject, PROJECT_FORMAT, PROJECT_VERSION, toProject } from './project';
import { SpecEdits } from './spec-edits';

const EDITS = { 'geom.compression_ratio': 17, 'turbo.vgt': false };
const DRIVE = { gearbox: 'manual' as const, place: 'winter', fuel: 'arctic' };

// Phase 7 step 7 (ADR-016 item 6): a project is the engine and what it drives with.
describe('a project file', () => {
  beforeEach(() => localStorage.clear());

  it('round-trips: saved, then opened, gives the same engine and drive', () => {
    const text = JSON.stringify(toProject({ preset: 'crdi15', overrides: EDITS }, DRIVE));
    const p = parseProject(text);
    expect(p).toEqual({ engine: { preset: 'crdi15', overrides: EDITS }, drive: DRIVE });
    expect(JSON.parse(text)).toMatchObject({ format: PROJECT_FORMAT, version: PROJECT_VERSION });
  });

  it('opens an old spec file as the engine only (ADR-016: old spec files still open)', () => {
    expect(parseProject(JSON.stringify({ preset: 'ld_i4', overrides: { 'inj.n_holes': 8 } })))
      .toEqual({ engine: { preset: 'ld_i4', overrides: { 'inj.n_holes': 8 } } });
    expect(parseProject(JSON.stringify({ preset: 'ld_i4', overrides: { 'geom.compresion_ratio': 17 } })))
      .toBe('unknown field "geom.compresion_ratio"');
  });

  it('refuses, in words: a newer format, a bad version, a bad engine, an unknown gearbox, place or fuel', () => {
    const ok = toProject({ preset: 'crdi15', overrides: {} }, DRIVE);
    const bad = (patch: object) => parseProject(JSON.stringify({ ...ok, ...patch }));
    expect(parseProject('{')).toBe('not JSON');
    expect(parseProject('[1]')).toBe('not a project or spec file');
    expect(bad({ format: 'something-else' })).toBe('not a project file: format "something-else"');
    expect(bad({ version: 2 })).toBe('made by a newer version of the app (project format 2; this one reads up to 1)');
    expect(bad({ version: 0 })).toBe('a project file with no valid "version"');
    expect(bad({ version: 1.5 })).toBe('a project file with no valid "version"');
    expect(bad({ engine: { preset: 'crdi15', overrides: { 'geom.bore': 'wide' } } })).toBe('engine: "geom.bore" must be a number');
    expect(bad({ drive: undefined })).toBe('a project file with no "drive"');
    expect(bad({ drive: { ...DRIVE, gearbox: 'cvt' } })).toBe('drive: unknown gearbox "cvt"');
    expect(bad({ drive: { ...DRIVE, place: 'atlantis' } })).toBe('drive: unknown place "atlantis"');
    expect(bad({ drive: { ...DRIVE, fuel: 'kerosene' } })).toBe('drive: unknown fuel "kerosene"');
    expect(bad({ drive: { ...DRIVE, fuel: 'local' } })).toMatchObject({ drive: { fuel: 'local' } });   // "Sold here"
  });

  it('opening one sets /spec\'s edits and the gearbox, place and fuel -- and saving gives them back', () => {
    const edits = new SpecEdits(), env = new DriveEnv();
    expect(applyProject({ engine: { preset: 'ld_i4', overrides: EDITS }, drive: DRIVE }, edits, env)).toBe('');
    expect([edits.base(), edits.overrides(), env.gearbox(), env.current(), env.fuel()])
      .toEqual(['ld_i4', EDITS, 'manual', 'winter', 'arctic']);
    expect(currentProject(edits, env)).toEqual(toProject({ preset: 'ld_i4', overrides: EDITS }, DRIVE));
    // kept across a reload, like the place and the fuel
    expect(new DriveEnv().gearbox()).toBe('manual');
    expect(localStorage.getItem(DRIVE_GEARBOX_KEY)).toBe('manual');
  });

  it('an old spec file leaves the drive settings as they were, and says so', () => {
    const edits = new SpecEdits(), env = new DriveEnv();
    env.setGearbox('dct');
    env.set('desert');
    const note = applyProject({ engine: { preset: 'hd_i6', overrides: {} } }, edits, env);
    expect(note).toMatch(/old spec file.*stay as they were/);
    expect([edits.base(), env.gearbox(), env.current()]).toEqual(['hd_i6', 'dct', 'desert']);
  });

  it('the gearbox: an unknown one is ignored, automatic is the default and is not stored', () => {
    const env = new DriveEnv();
    expect(env.gearbox()).toBe('tc');
    env.setGearbox('cvt');
    expect(env.gearbox()).toBe('tc');
    env.setGearbox('dct');
    env.setGearbox('tc');
    expect(localStorage.getItem(DRIVE_GEARBOX_KEY)).toBeNull();
    localStorage.setItem(DRIVE_GEARBOX_KEY, 'warp');
    expect(new DriveEnv().gearbox()).toBe('tc');
  });
});

describe('which engine a Drive or Enjoy page selects for a project', () => {
  const mine = (keys: string[]): MyEngine[] => keys.map(key => ({ key, name: key, vehicle: 'hatch', savedAt: 0 }) as MyEngine);

  it('the preset itself when nothing is edited and the page offers it', () => {
    expect(engineChoice({ preset: 'crdi15', overrides: {} }, ['crdi15', 'ld_i4'], [])).toEqual({ choice: 'crdi15' });
    expect(engineChoice({ preset: 'hatch15', overrides: {} }, ['crdi15'], []))
      .toEqual({ reason: 'this page doesn\'t offer the engine "hatch15"' });
  });

  it('an edited engine: its grid built in this browser (the same edits, the same key), or why not', () => {
    const key = editedEngine('crdi15', 'any name', EDITS).key;
    expect(engineChoice({ preset: 'crdi15', overrides: EDITS }, ['crdi15'], mine(['other', key])))
      .toEqual({ choice: MY + key });
    // the key ignores the order the edits were made in
    const reordered = { 'turbo.vgt': false, 'geom.compression_ratio': 17 };
    expect(engineChoice({ preset: 'crdi15', overrides: reordered }, ['crdi15'], mine([key]))).toEqual({ choice: MY + key });
    const none = engineChoice({ preset: 'crdi15', overrides: EDITS }, ['crdi15'], mine(['other']));
    expect(none).toMatchObject({ reason: expect.stringMatching(/2 edited fields.*isn't built in this browser.*Build drivable grid/) });
    const one = engineChoice({ preset: 'crdi15', overrides: { 'geom.compression_ratio': 17 } }, ['crdi15'], []);
    expect(one).toMatchObject({ reason: expect.stringMatching(/has 1 edited field,/) });
  });
});
