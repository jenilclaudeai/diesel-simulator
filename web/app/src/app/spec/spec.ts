import { ChangeDetectionStrategy, Component, computed, effect, inject, OnInit, signal } from '@angular/core';
import { NgTemplateOutlet } from '@angular/common';
import { RouterLink } from '@angular/router';
import type { SpecField } from '@dieselsim/solver';
import { describe, SolverService } from '../solver/solver.service';
import { parseSpecFile, SpecEdits } from './spec-edits';
import { GROUPS, groupFields, label, noteRest, readOnly, type SchemaRow, unitFor } from './spec-meta';

const fmtValue = (v: unknown) => typeof v === 'number' ? String(Number(v.toPrecision(6))) : Array.isArray(v) ? v.join(', ') : String(v);

interface Row { f: SchemaRow; label: string; unit: string; note: string; ro: boolean; engine: unknown; value: unknown; changed: boolean }

/**
 * The spec editor (Phase 6, ADR-015): every field of the engine, grouped by
 * physical subsystem, the influential ones first and the rest collapsed. An
 * edit is an override on the base engine; the cycle page solves with them.
 */
@Component({
  selector: 'app-spec',
  imports: [RouterLink, NgTemplateOutlet],
  templateUrl: './spec.html',
  styleUrl: './spec.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SpecPage implements OnInit {
  protected readonly solver = inject(SolverService);
  protected readonly edits = inject(SpecEdits);
  protected readonly fmtValue = fmtValue;

  /** the base engine's own values, by path (describeSpec without overrides) */
  private readonly engineValues = signal<Record<string, unknown> | undefined>(undefined);
  protected readonly loadError = signal<string | undefined>(undefined);
  protected readonly fileError = signal<string | undefined>(undefined);
  protected readonly filter = signal('');

  protected readonly presets = computed(() => {
    const info = this.solver.info();
    return info ? info.presets.map(k => ({ key: k, ...info.preset_info[k]! })) : [];
  });
  protected readonly name = computed(() => this.solver.info()?.preset_info[this.edits.base()]?.name ?? 'Spec editor');

  protected readonly groups = computed(() => {
    const vals = this.engineValues(), ov = this.edits.overrides(), q = this.filter().trim().toLowerCase();
    if (!vals) return [];
    const row = (f: SchemaRow): Row => {
      const engine = vals[f.path], value = f.path in ov ? ov[f.path] : engine;
      return { f, label: label(f.path), unit: unitFor(f), note: noteRest(f.note), ro: readOnly(f), engine, value, changed: f.path in ov };
    };
    const hit = (r: Row) => !q || r.label.toLowerCase().includes(q) || r.f.path.toLowerCase().includes(q) || r.note.toLowerCase().includes(q);
    return GROUPS.map(g => {
      const { primary, more } = groupFields(g);
      const p = primary.map(row).filter(hit), m = more.map(row).filter(hit);
      return { key: g.key, title: g.title, primary: p, more: m, changed: [...primary, ...more].filter(f => f.path in ov).length };
    }).filter(g => g.primary.length + g.more.length > 0);
  });

  constructor() {
    // the base engine's own values, whenever the base changes and the solver is ready
    effect(() => {
      const base = this.edits.base();
      if (this.solver.status() !== 'ready') return;
      this.engineValues.set(undefined);
      this.loadError.set(undefined);
      this.solver.describeSpec({ preset: base })
        .then(d => this.engineValues.set(Object.fromEntries(d.fields.map((f: SpecField) => [f.path, f.value]))))
        .catch(e => this.loadError.set(describe(e)));
    });
  }

  ngOnInit(): void {
    this.solver.start().catch(() => { /* surfaced through solver.error() */ });
  }

  protected selectEngine(key: string): void {
    if (this.edits.count() && !confirmDrop(this.edits.count())) return;
    this.edits.setBase(key);
  }

  protected edit(r: Row, raw: string | boolean): void {
    let v: number | boolean;
    if (r.f.type === 'bool') v = raw === true || raw === 'true';
    else {
      const n = Number(raw);
      if (raw === '' || !Number.isFinite(n)) return;
      v = r.f.type === 'int' ? Math.round(n) : n;
    }
    this.edits.set(r.f.path, v, r.engine);
  }

  protected exportFile(): void {
    const blob = new Blob([JSON.stringify(this.edits.toFile(), null, 1) + '\n'], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `${this.edits.base()}-spec.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  protected async importFile(input: HTMLInputElement): Promise<void> {
    this.fileError.set(undefined);
    const file = input.files?.[0];
    input.value = '';
    if (!file) return;
    const parsed = parseSpecFile(await file.text());
    if (typeof parsed === 'string') { this.fileError.set(`${file.name}: ${parsed}`); return; }
    if (!this.solver.info()?.presets.includes(parsed.preset)) { this.fileError.set(`${file.name}: unknown engine "${parsed.preset}"`); return; }
    this.edits.load(parsed);
  }
}

/** Changing the base engine drops the edits: ask first (not in tests: no dialogs there). */
function confirmDrop(n: number): boolean {
  return typeof window.confirm !== 'function' || location.search.includes('e2e')
    || window.confirm(`Changing the engine drops your ${n} edited ${n === 1 ? 'field' : 'fields'}. Continue?`);
}
