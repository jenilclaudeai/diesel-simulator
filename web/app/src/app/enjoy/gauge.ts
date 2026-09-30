import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

/** The dial's sweep: 240 degrees, from -120 (zero) to +120 (full scale). */
export const SWEEP = 240;

/** A value's needle angle in degrees (0 = straight up), clamped to the dial. */
export function gaugeAngle(value: number, max: number): number {
  if (!(max > 0) || !Number.isFinite(value)) return -SWEEP / 2;
  const f = Math.min(1, Math.max(0, value / max));
  return -SWEEP / 2 + f * SWEEP;
}

/** A tidy full scale for a dial: `v` rounded up to a multiple of `step`. */
export function dialMax(v: number, step: number): number {
  return Math.max(step, Math.ceil(v / step) * step);
}

export interface Scale { max: number; step: number; labelEvery: number; labelScale: number; unit: string }

/** A tachometer's scale: a truck's reads x100 rpm labelled every 500, a
 *  car's x1000 every 1000, and the full scale is rounded so its end is labelled. */
export function tachScale(maxRpm: number): Scale {
  if (maxRpm <= 3000) return { max: dialMax(maxRpm, 500), step: 100, labelEvery: 5, labelScale: 100, unit: '×100 rpm' };
  return { max: dialMax(maxRpm, 1000), step: 250, labelEvery: 4, labelScale: 1000, unit: '×1000 rpm' };
}

/** A speedometer's scale, to at most 240 km/h: labels every 10, 20 or 40,
 *  and the full scale rounded so its end is labelled. */
export function speedScale(vmaxKmh: number): Scale {
  const max = Math.min(240, vmaxKmh > 160 ? dialMax(vmaxKmh, 40) : dialMax(vmaxKmh, 20));
  const step = max <= 60 ? 5 : 10;
  return { max, step, labelEvery: max > 160 ? 4 : 2, labelScale: 1, unit: 'km/h' };
}

interface Tick { x1: number; y1: number; x2: number; y2: number; label?: { x: number; y: number; text: string } }

/**
 * An analogue dial (tachometer or speedometer): ticks every `step`,
 * labelled every `labelEvery`, an optional red band from `redFrom`, and a
 * needle at `value`.
 */
@Component({
  selector: 'app-gauge',
  template: `
    <svg viewBox="-110 -110 220 190" role="img" [attr.aria-label]="label() + ' ' + round(value()) + ' ' + unit()"
         [attr.data-max]="max()" [attr.data-label-scale]="labelScale()">
      <path class="track" [attr.d]="arc(0, max())" />
      @if (redFrom() !== null) { <path class="red" [attr.d]="arc(redFrom()!, max())" /> }
      @for (t of ticks(); track $index) {
        <line class="tick" [attr.x1]="t.x1" [attr.y1]="t.y1" [attr.x2]="t.x2" [attr.y2]="t.y2" />
        @if (t.label) { <text class="num" [attr.x]="t.label.x" [attr.y]="t.label.y">{{ t.label.text }}</text> }
      }
      <g class="needle" [attr.transform]="'rotate(' + angle() + ')'">
        <line x1="0" y1="12" x2="0" y2="-84" />
      </g>
      <circle class="hub" r="7" />
      <text class="unit" x="0" y="44">{{ unit() }}</text>
    </svg>`,
  styles: [`
    :host { display: block; }
    svg { width: 100%; height: 100%; overflow: visible; }
    .track { fill: none; stroke: rgba(223, 227, 220, 0.25); stroke-width: 6; }
    .red { fill: none; stroke: #e0634f; stroke-width: 6; }
    .tick { stroke: var(--grey); stroke-width: 2; }
    .num { fill: var(--grey); font-size: 13px; text-anchor: middle; dominant-baseline: middle; }
    .needle line { stroke: var(--amber); stroke-width: 4; stroke-linecap: round; }
    .hub { fill: var(--amber); }
    .unit { fill: var(--grey); opacity: 0.8; font-size: 12px; text-anchor: middle; }
  `],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Gauge {
  readonly value = input.required<number>();
  readonly max = input.required<number>();
  readonly step = input.required<number>();
  readonly labelEvery = input(1);
  readonly labelScale = input(1);           // e.g. 1000 to label rpm in thousands
  readonly unit = input('');
  readonly label = input('');
  readonly redFrom = input<number | null>(null);

  protected readonly angle = computed(() => gaugeAngle(this.value(), this.max()));

  protected readonly ticks = computed<Tick[]>(() => {
    const out: Tick[] = [], max = this.max(), step = this.step();
    if (!(max > 0 && step > 0)) return out;
    const n = Math.round(max / step);
    for (let i = 0; i <= n; i++) {
      const a = (gaugeAngle(i * step, max) * Math.PI) / 180, major = i % this.labelEvery() === 0;
      const r1 = major ? 78 : 84, r2 = 92, s = Math.sin(a), c = -Math.cos(a);
      const t: Tick = { x1: r1 * s, y1: r1 * c, x2: r2 * s, y2: r2 * c };
      if (major) t.label = { x: 64 * s, y: 64 * c, text: String(Math.round((i * step) / this.labelScale())) };
      out.push(t);
    }
    return out;
  });

  protected round(v: number): number { return Math.round(v); }

  /** An arc path along the dial from value a to value b, at radius 92. */
  protected arc(a: number, b: number): string {
    const r = 92, max = this.max();
    const p = (v: number) => { const t = (gaugeAngle(v, max) * Math.PI) / 180; return `${(r * Math.sin(t)).toFixed(2)} ${(-r * Math.cos(t)).toFixed(2)}`; };
    const large = gaugeAngle(b, max) - gaugeAngle(a, max) > 180 ? 1 : 0;
    return `M ${p(a)} A ${r} ${r} 0 ${large} 1 ${p(b)}`;
  }
}
