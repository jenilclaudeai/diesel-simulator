import { ChangeDetectionStrategy, Component, ElementRef, inject, input, output, signal } from '@angular/core';

/**
 * A pedal's position from a finger's height in it (ADR-012: "pressed harder
 * by sliding up"): 0 at the bottom, 1 at the top, with a dead band at each
 * end so a thumb can reach both 0 and full travel.
 */
export function pedalValue(clientY: number, top: number, height: number, deadband = 0.08): number {
  if (!(height > 0)) return 0;
  const f = (top + height - clientY) / height;           // 0 at the bottom edge, 1 at the top
  return Math.min(1, Math.max(0, (f - deadband) / (1 - 2 * deadband)));
}

/**
 * A touch pedal. It follows one pointer from press to release (so two
 * thumbs can hold two pedals), and returns to 0 when that pointer lifts,
 * leaves or is cancelled.
 */
@Component({
  selector: 'app-pedal',
  template: `
    <div class="pedal" role="slider" [attr.aria-label]="label()" aria-valuemin="0" aria-valuemax="100"
         [attr.aria-valuenow]="pct()" [class.down]="value() > 0"
         (pointerdown)="down($event)" (pointermove)="move($event)"
         (pointerup)="up($event)" (pointercancel)="up($event)" (lostpointercapture)="up($event)">
      <span class="fill" [style.height.%]="pct()"></span>
      <span class="name">{{ label() }}</span>
    </div>`,
  styles: [`
    :host { display: block; }
    .pedal {
      position: relative; height: 100%; border-radius: 14px; overflow: hidden;
      background: rgba(223, 227, 220, 0.10); border: 2px solid rgba(223, 227, 220, 0.35);
      touch-action: none; user-select: none; -webkit-user-select: none; cursor: ns-resize;
      container-type: inline-size;
    }
    .pedal.down { border-color: var(--amber); }
    .fill { position: absolute; left: 0; right: 0; bottom: 0; background: var(--amber); opacity: 0.85; }
    .name {
      position: absolute; left: 0; right: 0; bottom: 10px; text-align: center;
      font-weight: 600; letter-spacing: 0.04em; color: var(--grey); mix-blend-mode: difference;
      /* B-05 put three pedals at ~68 px; the name shrinks with a narrow pedal, so no font
         or text size clips "Throttle" (a wide Linux font is ~5.3 em for it) */
      font-size: min(1em, 16cqi);
    }
  `],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Pedal {
  readonly label = input.required<string>();
  readonly changed = output<number>();
  protected readonly value = signal(0);
  private readonly el = inject<ElementRef<HTMLElement>>(ElementRef);
  private pointer: number | null = null;

  protected pct(): number { return Math.round(this.value() * 100); }

  protected down(e: PointerEvent): void {
    if (this.pointer !== null) return;
    this.pointer = e.pointerId;
    (e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId);
    e.preventDefault();
    this.set(e);
  }

  protected move(e: PointerEvent): void {
    if (e.pointerId === this.pointer) this.set(e);
  }

  protected up(e: PointerEvent): void {
    if (e.pointerId !== this.pointer) return;
    this.pointer = null;
    this.value.set(0);
    this.changed.emit(0);
  }

  private set(e: PointerEvent): void {
    const r = (this.el.nativeElement.firstElementChild as HTMLElement).getBoundingClientRect();
    const v = pedalValue(e.clientY, r.top, r.height);
    this.value.set(v);
    this.changed.emit(v);
  }
}
