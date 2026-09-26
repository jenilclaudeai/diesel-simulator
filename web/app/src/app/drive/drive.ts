import { ChangeDetectionStrategy, Component, computed, HostListener, OnDestroy, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import type { Transmission } from '@dieselsim/physics';
import { GRID_VERSION } from '../solver/physics-version';
import { controlKey, DRIVE_PRESETS, KEY_HELP } from './drive-keys';
import type { DriveScript, FromWorker, GridFile, LiveView } from './protocol';

const fmt0 = new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 });
const fmt1 = new Intl.NumberFormat(undefined, { maximumFractionDigits: 1, minimumFractionDigits: 1 });
const fmt2 = new Intl.NumberFormat(undefined, { maximumFractionDigits: 2, minimumFractionDigits: 2 });

interface GridStatus { converged: boolean; unsettled: number; stale: boolean; cells: number }

/**
 * The real-time drive (Phase 3). Prebuilt converged grids -- no Python in
 * the browser -- driven by the TypeScript live loop in a 60 Hz worker.
 */
@Component({
  selector: 'app-drive',
  imports: [RouterLink],
  templateUrl: './drive.html',
  styleUrl: '../dyno/dyno.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DrivePage implements OnDestroy {
  protected readonly fmt0 = fmt0;
  protected readonly fmt1 = fmt1;
  protected readonly fmt2 = fmt2;
  protected readonly presets = DRIVE_PRESETS;
  protected readonly keyHelp = KEY_HELP;
  protected readonly preset = signal('crdi15');
  protected readonly trans = signal<Transmission>('tc');
  protected readonly status = signal<'idle' | 'loading' | 'driving' | 'error'>('idle');
  protected readonly error = signal<string | undefined>(undefined);
  protected readonly gridStatus = signal<GridStatus | undefined>(undefined);
  protected readonly v = signal<LiveView | undefined>(undefined);
  protected readonly rpmFrac = computed(() => Math.min(1, (this.v()?.rpm ?? 0) / 5000));

  private worker?: Worker;
  private readonly held = new Set<string>();
  private scriptWaiter?: (r: Extract<FromWorker, { type: 'scriptResult' }>) => void;

  constructor() {
    // e2e hook (only with ?e2e): run a frame-exact script through the real worker
    if (typeof location !== 'undefined' && location.search.includes('e2e')) {
      (globalThis as Record<string, unknown>)['__drive'] = {
        load: (preset: string, trans: Transmission) => this.load(preset, trans, false),
        script: (script: DriveScript, init: Record<string, number> = {}) => this.runScript(script, init),
      };
    }
  }

  protected selectPreset(p: string): void { this.preset.set(p); this.stop(); }
  protected selectTrans(t: string): void { this.trans.set(t as Transmission); this.stop(); }

  protected async start(): Promise<void> {
    await this.load(this.preset(), this.trans(), true);
  }

  private async load(preset: string, trans: Transmission, run: boolean): Promise<void> {
    this.stop();
    this.status.set('loading');
    this.error.set(undefined);
    try {
      const url = new URL(`grids/${preset}.json`, document.baseURI).href;
      const r = await fetch(url);
      if (!r.ok) throw new Error(`no prebuilt grid for ${preset} (HTTP ${r.status})`);
      const grid = (await r.json()) as GridFile;
      this.gridStatus.set({ converged: grid.converged, unsettled: grid.unsettled_cells,
        stale: grid.grid_hash !== GRID_VERSION, cells: 2 * grid.rpms.length * grid.loads.length });
      const w = new Worker(new URL('./live.worker', import.meta.url), { type: 'module' });
      this.worker = w;
      await new Promise<void>((resolve, reject) => {
        w.addEventListener('error', e => reject(new Error(`the drive worker failed: ${e.message || 'script error'}`)));
        w.addEventListener('message', (ev: MessageEvent<FromWorker>) => {
          const m = ev.data;
          if (m.type === 'ready') { w.postMessage({ type: 'load', grid, trans }); resolve(); }
          else if (m.type === 'state') this.v.set(m.view);
          else if (m.type === 'scriptResult') this.scriptWaiter?.(m);
        });
      });
      if (run) w.postMessage({ type: 'run' });
      this.status.set('driving');
    } catch (e) {
      this.error.set(e instanceof Error ? e.message : String(e));
      this.status.set('error');
    }
  }

  private runScript(script: DriveScript, init: Record<string, number>) {
    return new Promise(resolve => {
      this.scriptWaiter = resolve;
      this.worker!.postMessage({ type: 'script', script, init });
    });
  }

  protected stop(): void {
    this.worker?.terminate();
    this.worker = undefined;
    this.v.set(undefined);
    if (this.status() === 'driving') this.status.set('idle');
  }

  @HostListener('document:keydown', ['$event'])
  protected keydown(ev: KeyboardEvent): void { this.key(ev, true); }

  @HostListener('document:keyup', ['$event'])
  protected keyup(ev: KeyboardEvent): void { this.key(ev, false); }

  private key(ev: KeyboardEvent, down: boolean): void {
    if (!this.worker || this.status() !== 'driving') return;
    if ((ev.target as HTMLElement | null)?.closest?.('select, input, button')) return;
    const k = controlKey(ev.key);
    if (!k) return;
    ev.preventDefault();
    // OS auto-repeat is ignored: taps act once, and held keys (w s b z) are
    // repeated every frame by the worker itself
    if (down && ev.repeat) return;
    if (down) this.held.add(k);
    else this.held.delete(k);
    this.worker.postMessage({ type: 'key', key: k, down });
  }

  /** A key held while the window loses focus never sends its keyup: release everything. */
  @HostListener('window:blur')
  protected blur(): void {
    for (const k of this.held) this.worker?.postMessage({ type: 'key', key: k, down: false });
    this.held.clear();
  }

  ngOnDestroy(): void { this.stop(); }
}
