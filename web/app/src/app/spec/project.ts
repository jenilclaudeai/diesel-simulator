import type { Transmission } from '@dieselsim/physics';
import { editedEngine, MY, type MyEngine } from '../engine/my-engines';
import { type DriveEnv, FUELS, GEARBOXES, PLACES, SOLD_HERE } from '../weather/drive-env';
import { parseSpecFile, type SpecEdits, type SpecFile } from './spec-edits';

/**
 * A project (ADR-007, ADR-016 item 6, Phase 7 step 7): the engine (a base
 * engine and its edits, the spec file's part), and what it is driven with --
 * the gearbox, the place and the fuel (the owner's "Drive with" box on
 * /spec, 2026-10-10). The vehicle is the base engine's own. The solved grid
 * is not in the file (ADR-007): an edited engine's grid is built in the
 * browser, and found again by its edits (editedEngine's key).
 */
export const PROJECT_FORMAT = 'dieselsim-project';
export const PROJECT_VERSION = 1;

export interface DriveWith { gearbox: Transmission; place: string; fuel: string }
export interface ProjectFile { format: typeof PROJECT_FORMAT; version: number; engine: SpecFile; drive: DriveWith }

/** What an opened file gave: a project, or an old spec file (the engine only, `drive` absent). */
export interface OpenedProject { engine: SpecFile; drive?: DriveWith }

export function toProject(engine: SpecFile, drive: DriveWith): ProjectFile {
  return { format: PROJECT_FORMAT, version: PROJECT_VERSION,
    engine: { preset: engine.preset, overrides: { ...engine.overrides } }, drive: { ...drive } };
}

/**
 * Read a project, or an old spec file ({preset, overrides}: ADR-016, "old
 * spec files still open"). Every part is checked, and the reason comes back
 * in words for the page to show. A known engine key is the caller's check.
 */
export function parseProject(text: string): OpenedProject | string {
  let d: unknown;
  try { d = JSON.parse(text); } catch { return 'not JSON'; }
  if (!d || typeof d !== 'object' || Array.isArray(d)) return 'not a project or spec file';
  const o = d as Record<string, unknown>;
  if (!('format' in o)) {                                  // an old spec file
    const f = parseSpecFile(text);
    return typeof f === 'string' ? f : { engine: f };
  }
  if (o['format'] !== PROJECT_FORMAT) return `not a project file: format "${String(o['format'])}"`;
  const v = o['version'];
  if (typeof v !== 'number' || !Number.isInteger(v) || v < 1) return 'a project file with no valid "version"';
  if (v > PROJECT_VERSION) return `made by a newer version of the app (project format ${v}; this one reads up to ${PROJECT_VERSION})`;
  const engine = parseSpecFile(JSON.stringify(o['engine'] ?? null));
  if (typeof engine === 'string') return `engine: ${engine}`;
  const dr = o['drive'];
  if (!dr || typeof dr !== 'object' || Array.isArray(dr)) return 'a project file with no "drive"';
  const { gearbox, place, fuel } = dr as Record<string, unknown>;
  if (!GEARBOXES.includes(gearbox as Transmission)) return `drive: unknown gearbox "${String(gearbox)}"`;
  if (!PLACES.some(p => p.key === place)) return `drive: unknown place "${String(place)}"`;
  if (fuel !== SOLD_HERE && !FUELS.some(f => f.key === fuel)) return `drive: unknown fuel "${String(fuel)}"`;
  return { engine, drive: { gearbox: gearbox as Transmission, place: place as string, fuel: fuel as string } };
}

/**
 * Which engine a Drive or Enjoy page should select for a project's engine:
 * the base engine itself when nothing is edited and the page offers it; an
 * edited engine's grid saved in this browser ("Your engines", under MY);
 * otherwise the reason it can't, in words.
 */
export function engineChoice(engine: SpecFile, offered: readonly string[], mine: readonly MyEngine[]):
    { choice: string } | { reason: string } {
  const n = Object.keys(engine.overrides).length;
  if (!n) {
    return offered.includes(engine.preset) ? { choice: engine.preset }
      : { reason: `this page doesn't offer the engine "${engine.preset}"` };
  }
  const key = editedEngine(engine.preset, '', engine.overrides).key;     // the key is the base and the edits
  if (mine.some(e => e.key === key)) return { choice: MY + key };
  return { reason: `this project's engine has ${n} edited ${n === 1 ? 'field' : 'fields'}, and its drivable grid ` +
    `isn't built in this browser yet. Open the project on /spec, press "Build drivable grid" there, then open it here.` };
}

/** The project as the app holds it now: /spec's edits, and the shared gearbox, place and fuel. */
export function currentProject(edits: SpecEdits, env: DriveEnv): ProjectFile {
  return toProject(edits.toFile(), { gearbox: env.gearbox(), place: env.current(), fuel: env.fuel() });
}

/**
 * Open a project into the app: /spec's edits become its engine's, and the
 * gearbox, place and fuel its own. An old spec file sets the engine only.
 * Returns what that left unchanged, in words ('' for nothing), for the page to say.
 */
export function applyProject(p: OpenedProject, edits: SpecEdits, env: DriveEnv): string {
  edits.load(p.engine);
  if (!p.drive) return 'An old spec file: it holds the engine only, so the gearbox, place and fuel stay as they were.';
  env.setGearbox(p.drive.gearbox);
  env.set(p.drive.place);
  env.setFuel(p.drive.fuel);
  return '';
}

/** Save a project file: <base engine>-project.json. */
export function downloadProject(p: ProjectFile): void {
  const blob = new Blob([JSON.stringify(p, null, 1) + '\n'], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `${p.engine.preset}-project.json`;
  a.click();
  URL.revokeObjectURL(a.href);
}
