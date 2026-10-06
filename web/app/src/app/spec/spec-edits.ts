import { computed, Injectable, signal } from '@angular/core';
import type { EngineRef } from '@dieselsim/solver';
import { FIELDS, readOnly } from './spec-meta';

export type Overrides = Record<string, number | boolean>;

/** What a spec file holds: a base engine and the fields changed on it (ADR-007's spec part). */
export interface SpecFile { preset: string; overrides: Overrides }

/**
 * Check a spec file before it is used: a known engine key is the caller's
 * check; here every path must be an editable field of the schema, with a
 * value of its type. The reason comes back in words, for the page to show.
 */
export function parseSpecFile(text: string): SpecFile | string {
  let d: unknown;
  try { d = JSON.parse(text); } catch { return 'not JSON'; }
  if (!d || typeof d !== 'object') return 'not a spec file: expected {"preset": ..., "overrides": {...}}';
  const o = d as Record<string, unknown>;
  if (typeof o['preset'] !== 'string') return 'not a spec file: no "preset"';
  const ov = o['overrides'] ?? {};
  if (typeof ov !== 'object' || Array.isArray(ov) || ov === null) return '"overrides" must be an object';
  const out: Overrides = {};
  for (const [path, v] of Object.entries(ov as Record<string, unknown>)) {
    const f = FIELDS.find(x => x.path === path);
    if (!f) return `unknown field "${path}"`;
    if (readOnly(f)) return `"${path}" can't be edited here`;
    if (f.type === 'bool' ? typeof v !== 'boolean' : typeof v !== 'number' || !Number.isFinite(v)) return `"${path}" must be a ${f.type === 'bool' ? 'true/false' : 'number'}`;
    if (f.type === 'int' && !Number.isInteger(v)) return `"${path}" must be a whole number`;
    out[path] = v as number | boolean;
  }
  return { preset: o['preset'], overrides: out };
}

/** Where the edits are kept between visits (REVIEW-008 m-3): this browser's localStorage. */
export const EDITS_KEY = 'dieselsim-spec-edits';
export const DEFAULT_BASE = 'crdi15';

/** The kept edits, if any and if they still pass parseSpecFile (a field renamed since is dropped, not shown). */
function keptEdits(): SpecFile | undefined {
  let text: string | null = null;
  try { text = globalThis.localStorage?.getItem(EDITS_KEY) ?? null; } catch { return undefined; }
  if (!text) return undefined;
  const f = parseSpecFile(text);
  return typeof f === 'string' ? undefined : f;
}

function keep(f: SpecFile): void {
  try {
    if (f.preset === DEFAULT_BASE && !Object.keys(f.overrides).length) globalThis.localStorage?.removeItem(EDITS_KEY);
    else globalThis.localStorage?.setItem(EDITS_KEY, JSON.stringify(f));
  } catch { /* storage off (private mode, quota): the edits stay in memory, as before */ }
}

/**
 * The spec editor's edits, shared with the pages that solve (Phase 6,
 * ADR-015): a base engine and the fields changed on it. Changing the base
 * engine drops the edits; they belong to one engine. Kept in this browser
 * across reloads (REVIEW-008 m-3); every change goes through a method here.
 */
@Injectable({ providedIn: 'root' })
export class SpecEdits {
  private readonly kept = keptEdits();
  readonly base = signal(this.kept?.preset ?? DEFAULT_BASE);
  readonly overrides = signal<Overrides>(this.kept?.overrides ?? {});
  readonly count = computed(() => Object.keys(this.overrides()).length);

  setBase(key: string): void {
    if (key === this.base()) return;
    this.base.set(key);
    this.overrides.set({});
    keep(this.toFile());
  }

  /** Set a field; a value equal to the engine's own removes the override. */
  set(path: string, value: number | boolean, engineValue: unknown): void {
    const next = { ...this.overrides() };
    if (value === engineValue) delete next[path]; else next[path] = value;
    this.overrides.set(next);
    keep(this.toFile());
  }

  reset(path: string): void {
    const next = { ...this.overrides() };
    delete next[path];
    this.overrides.set(next);
    keep(this.toFile());
  }

  resetAll(): void { this.overrides.set({}); keep(this.toFile()); }

  /** The engine a page should solve: the edits apply only to their own base engine. */
  engineRef(preset: string): EngineRef {
    return preset === this.base() && this.count() ? { preset, overrides: { ...this.overrides() } } : { preset };
  }

  toFile(): SpecFile { return { preset: this.base(), overrides: { ...this.overrides() } }; }

  load(f: SpecFile): void {
    this.base.set(f.preset);
    this.overrides.set({ ...f.overrides });
    keep(this.toFile());
  }
}
