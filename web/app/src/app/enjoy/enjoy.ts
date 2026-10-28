import { ChangeDetectionStrategy, Component, computed, effect, HostListener, inject, OnDestroy, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import type { Transmission } from '@dieselsim/physics';
import { releaseFocus } from '../drive/drive';
import { controlKey, MIC_KEYS, MICS } from '../drive/drive-keys';
import { LiveSession } from '../drive/live-session';
import { DriveEnv } from '../weather/drive-env';
import { DriveEnvPicker } from '../weather/drive-env-picker';
import { applyProject, engineChoice, parseProject } from '../spec/project';
import { SpecEdits } from '../spec/spec-edits';
import { IMPORTED, readGridFile } from '../drive/grid-file';
import { engineLibrary, MY, type MyEngine } from '../engine/my-engines';
import type { GridFile, Pedals } from '../drive/protocol';
import { avgL100, nowL100, rangeKm } from './economy';
import { Gauge, speedScale, tachScale } from './gauge';
import { touchHint } from './hints';
import { derateLit } from './lamps';
import { Pedal } from './pedal';
import { ROSTER, rosterGroups } from './roster';
import { testNote, VibrationSetting, Vibrator } from './vibration';
import { bestKey, GoalBests, GOALS, judge, LapRun, lapTime, parseGoal, type GoalKind } from './goals';
import { newSeed, parseRouteParam, roadAhead, ROUTE_CHOICES, routeKey, routeOf, routeSummary, SURFACE_FILL } from './road';
import {
  distance, distanceUnit, economy, economyUnit, elevation, elevationUnit, pressureBar, pressureUnit, speed, speedUnit,
  temperature, temperatureUnit, Units, volume, volumeUnit,
} from '../units/units';

const fmt0 = new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 });
const PHASE = ['', 'shifting: torque phase', 'shifting: inertia phase'];

/**
 * Enjoy mode (Phase 5, ADR-012): pick an engine, tap Start, drive with your
 * thumbs. Pedals at the edges (throttle right, brake left, clutch beside it
 * on the manual), shift paddles in the top corners. Prebuilt grids only: no
 * Pyodide is ever fetched. The keys still work on a desktop.
 */
@Component({
  selector: 'app-enjoy',
  imports: [RouterLink, Pedal, Gauge, DriveEnvPicker],
  templateUrl: './enjoy.html',
  styleUrl: './enjoy.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class EnjoyPage implements OnDestroy {
  protected readonly fmt0 = fmt0;
  protected readonly touchHint = touchHint;
  protected readonly presets = ROSTER;
  protected readonly presetGroups = rosterGroups();
  protected readonly preset = signal(ROSTER[0]!.key);
  /** ADR-023 (N2): the real engine a P14 roster engine follows, named by reference */
  protected readonly modelledOn = computed(() => ROSTER.find(p => p.key === this.preset())?.modelledOn);
  /** A custom engine's grid, imported from a file (ADR-014). */
  protected readonly imported = signal<GridFile | undefined>(undefined);
  protected readonly importError = signal<string | undefined>(undefined);
  protected readonly IMPORTED = IMPORTED;
  /** "Your engines": custom engines with a drivable grid, built in this browser (ADR-014) */
  protected readonly mine = signal<MyEngine[]>([]);
  protected readonly MY = MY;
  private readonly s = new LiveSession();
  private readonly env = inject(DriveEnv);
  /** Phase 7 step 7: starts in the kept gearbox (a project's, or /spec's "Drive with"); Enjoy has auto or manual */
  protected readonly manual = signal(this.env.gearbox() === 'manual');
  private readonly edits = inject(SpecEdits);
  protected readonly projectNote = signal<string | undefined>(undefined);
  protected readonly status = this.s.status;
  protected readonly error = this.s.error;
  protected readonly v = this.s.v;
  protected readonly soundOn = this.s.soundOn;
  protected readonly soundError = this.s.soundError;
  protected readonly micName = computed(() => MICS.find(m => m.key === this.s.mic())?.name ?? '');
  protected readonly rpmFrac = computed(() => Math.min(1, (this.v()?.rpm ?? 0) / 5000));
  protected readonly phase = computed(() => PHASE[this.v()?.phase ?? 0] ?? '');
  protected readonly info = this.s.info;
  /** Phase 8: the driver's units (Metric, US or UK), kept per browser and shared with /drive. */
  protected readonly u = inject(Units).system;
  protected readonly U = computed(() => {
    const s = this.u();
    return { speed: speedUnit(s), dist: distanceUnit(s), vol: volumeUnit(s), econ: economyUnit(s),
             temp: temperatureUnit(s), pres: pressureUnit(s) };
  });
  protected readonly sp = (kmh: number) => speed(kmh, this.u());
  protected readonly T = (K: number) => temperature(K - 273.15, this.u());
  protected readonly dist = (km: number) => distance(km, this.u());
  protected readonly vol = (L: number) => volume(L, this.u());
  protected readonly pres = (bar: number) => pressureBar(bar, this.u());
  /** Dial scales from the engine and vehicle (the worker's info message). */
  protected readonly tach = computed(() => tachScale(this.info()?.max_rpm ?? 5000));
  protected readonly speed = computed(() => speedScale(this.info()?.vmax_kmh ?? 200, this.u()));
  /** The lamp cluster: every lamp always shown, lit when on, as a real dash is. */
  protected readonly lamps = computed(() => {
    const s = this.v(), i = this.info();
    if (!s || !i) return [];
    const lowFuel = s.out_of_fuel || s.tank_L < 0.12 * i.tank_L;
    return [
      { key: 'stall', text: 'Stalled', on: s.stalled, warn: true },
      { key: 'stopped', text: 'Engine off', on: s.engine_stopped, warn: true },
      { key: 'hot', text: 'Overheat', on: !!s.overheat || s.T_coolant >= i.T_warn, warn: true },
      { key: 'derate', text: 'Derate', on: derateLit(s.T_charge, s.derate_heat), warn: true },
      { key: 'fuel', text: s.out_of_fuel ? 'Out of fuel' : 'Low fuel', on: lowFuel, warn: true },
      { key: 'fan', text: 'Fan', on: s.fan_on, warn: false },
      { key: 'cruise', text: 'Cruise', on: s.cruise, warn: false },
      { key: 'lockup', text: 'Lock-up', on: s.lockup, warn: false },
    ];
  });
  /** A temperature bar's fill, 20 C to the shutdown temperature. */
  protected tempFrac(K: number): number {
    const top = this.info()?.T_shutdown ?? 393.15, lo = 293.15;
    return Math.min(1, Math.max(0, (K - lo) / (top - lo)));
  }
  /** The coolant bar's marks in words: on screen they differ by shape and colour, which a screen reader can't see. */
  protected readonly coolantMarks = computed(() => {
    const i = this.info();
    const t = this.U().temp;
    return i ? `Warning from ${fmt0.format(this.T(i.T_warn))} ${t}, derate from ${fmt0.format(this.T(i.T_derate))} ${t}` : null;
  });
  // economy() and distance() are in the driver's units; economy() stays null where there is no figure
  protected readonly avg = computed(() => { const s = this.v(); return s ? economy(avgL100(s.trip_L, s.trip_km), this.u()) : null; });
  protected readonly now = computed(() => { const s = this.v(); return s ? economy(nowL100(s.inst_kmpl, s.kmh), this.u()) : null; });
  protected readonly range = computed(() => {
    const s = this.v(), r = s ? rangeKm(s.tank_L, s.trip_L, s.trip_km) : null;
    return r === null ? null : distance(r, this.u());
  });
  protected fmt1(x: number | null): string { return x === null ? '—' : x.toFixed(1); }
  private pedals: Pedals = { throttle: null, brake: 0, clutch: 0 };
  private readonly held = new Set<string>();

  /** P01: the phone vibrates (events, and a shake while idling or lugging); on unless switched off */
  protected readonly vibration = inject(VibrationSetting);
  private readonly vibes: (number[] | number)[] = [];
  private readonly vib = new Vibrator(p => this.buzz(p));
  private buzz(p: number[] | number): boolean {
    if (this.e2e) this.vibes.push(p);
    return this.canVibrate() ? navigator.vibrate(p) : false;
  }
  private canVibrate(): boolean { return typeof navigator !== 'undefined' && typeof navigator.vibrate === 'function'; }
  /** The start screen's Test tap: a 300 ms buzz, and a note on what the browser did with it. */
  protected readonly vibTest = signal<string | null>(null);
  protected testVibration(): void {
    const accepted = this.buzz([300]);
    this.vibTest.set(testNote(this.canVibrate(), accepted));
  }
  private readonly e2e = typeof location !== 'undefined' && location.search.includes('e2e');

  /** P06 (ADR-021): the road. `?route=city` or `?route=random:1234` opens on it: the address is the link to share. */
  protected readonly ROUTE_CHOICES = ROUTE_CHOICES;
  protected readonly SURFACE_FILL = SURFACE_FILL;
  private readonly router = inject(Router);
  private readonly initialRoute = parseRouteParam(
    typeof location !== 'undefined' ? new URLSearchParams(location.search).get('route') : null);
  protected readonly routeChoice = signal(this.initialRoute.choice);
  protected readonly seed = signal<number | null>(this.initialRoute.seed);
  protected readonly routeKey = computed(() => routeKey(this.routeChoice(), this.seed()));
  /** The picker's note: length, highest point, breakers */
  protected readonly routeNote = computed(() => {
    const r = routeOf(this.routeKey());
    if (!r) return null;
    const m = routeSummary(r), u = this.u();
    const b = m.breakers ? `${m.breakers} speed breaker${m.breakers > 1 ? 's' : ''} (take them at ${fmt0.format(speed(15, u))} ${speedUnit(u)})` : 'no speed breakers';
    return `${distance(m.km, u).toFixed(1)} ${distanceUnit(u)} a lap, up to ${fmt0.format(elevation(m.top, u))} ${elevationUnit(u)} above the start, ${b}. To share it, copy this page's address.`;
  });
  /** The route the engine is driving (set at Start; the picker stops the engine) */
  private readonly driven = signal<string | undefined>(undefined);
  private readonly drivenRoute = computed(() => routeOf(this.driven()));
  protected readonly road = computed(() => {
    const r = this.drivenRoute(), s = this.v();
    return r && s ? roadAhead(r, s.route_s) : null;
  });
  /** The strip's words (and its screen-reader label): grade, surface, wind, height, the next breaker */
  protected readonly roadText = computed(() => {
    const r = this.road(), s = this.v(), u = this.u();
    if (!r || !s) return '';
    const kmh = Math.abs(s.wind) * 3.6;
    const wind = kmh < 1 ? 'calm' : `${s.wind > 0 ? 'headwind' : 'tailwind'} ${fmt0.format(speed(kmh, u))} ${speedUnit(u)}`;
    const up = elevation(s.route_alt, u);
    const parts = [`grade ${(r.grade * 100).toFixed(1)} %`, r.surface, wind,
      `${up >= 0 ? '+' : '−'}${fmt0.format(Math.abs(up))} ${elevationUnit(u)}`];
    if (r.nextBreakerM !== null) parts.push(`breaker in ${fmt0.format(elevation(r.nextBreakerM, u))} ${elevationUnit(u)}`);
    return parts.join(' · ');
  });

  /** P06 tier 2: a goal on the route (`?goal=time`); free driving otherwise */
  protected readonly GOALS = GOALS;
  protected readonly goal = signal<GoalKind>(parseGoal(
    typeof location !== 'undefined' ? new URLSearchParams(location.search).get('goal') : null));
  private readonly bests = inject(GoalBests);
  protected readonly par = this.s.par;
  /** The lap being timed (set at Start when there is a goal and a route) and what it shows */
  private lap?: LapRun;
  private lapGoal: GoalKind = 'free';
  private lapKey = '';
  private offered = false;
  protected readonly lapView = signal<{ phase: string; time_s: number; fuel_L: number; hits: number; failure: string } | null>(null);
  protected readonly lapBest = signal<{ best?: number; newBest: boolean }>({ newBest: false });
  protected readonly verdict = computed(() => {
    const l = this.lapView(), p = this.par();
    if (!l || l.phase !== 'finished' || !p || typeof p === 'string' || this.lapGoal === 'free') return null;
    return judge(this.lapGoal, l, p);
  });
  /** The goal's line on the dash */
  protected readonly goalText = computed(() => {
    const l = this.lapView(), p = this.par(), g = this.lapGoal, u = this.u();
    if (!l || g === 'free') return '';
    const name = GOALS.find(x => x.key === g)!.name;
    const fuel = (L: number) => `${this.vol(L).toFixed(u === 'us' ? 4 : 3)} ${volumeUnit(u)}`;
    const pen = l.hits ? ` (+${5 * l.hits} s, ${l.hits} breaker${l.hits > 1 ? 's' : ''})` : '';
    const parTxt = p === 'working' ? 'par: working it out…' : p === 'failed' || p === undefined ? 'no par'
      : !p.finished ? 'no par: its lap did not finish' : g === 'time' ? `par fuel ${fuel(p.fuel_L)}` : `par time ${lapTime(p.time_s)}`;
    if (l.phase === 'waiting') return `${name}: the clock starts with the throttle · ${parTxt}`;
    if (l.phase === 'failed') return `${name} over: ${l.failure}`;
    const now = `${lapTime(l.time_s)}${pen} on ${fuel(l.fuel_L)}`;
    if (l.phase === 'running') return `${name} · ${now} · ${parTxt}`;
    const v = this.verdict(), b = this.lapBest();
    if (!v) return `${name} lap: ${now} -- waiting for the par`;
    const best = b.newBest ? ' · a new best!' : b.best !== undefined ? ` · best ${g === 'time' ? lapTime(b.best) : fuel(b.best)}` : '';
    return `${name} lap: ${now} -- ${v.why} ${v.ok ? '✓' : '✗'}${best}`;
  });

  protected selectGoal(g: string): void {
    this.goal.set(parseGoal(g));
    this.routeChanged();
  }

  protected selectRoute(choice: string): void {
    this.routeChoice.set(choice);
    if (choice === 'random' && this.seed() === null) this.seed.set(newSeed());
    this.routeChanged();
  }
  protected setSeed(raw: string): void {
    const n = Math.floor(Number(raw));
    this.seed.set(Number.isFinite(n) && n >= 1 ? Math.min(n, 999_999) : null);
    this.routeChanged();
  }
  protected rollSeed(): void { this.seed.set(newSeed()); this.routeChanged(); }
  private routeChanged(): void {
    this.s.stop();
    void this.router.navigate([], { queryParams: { route: this.routeKey() ?? null,
      goal: this.routeKey() && this.goal() !== 'free' ? this.goal() : null }, queryParamsHandling: 'merge', replaceUrl: true });
  }

  constructor() {
    effect(() => {
      const s = this.v(), i = this.info();
      if (!this.vibration.on() || this.status() !== 'driving' || !s || !i) { this.vib.stop(); return; }
      this.vib.frame(s, { idle_rpm: i.idle_rpm, max_rpm: i.max_rpm, cylinders: i.cylinders }, performance.now());
    });
    effect(() => {
      const s = this.v(), lap = this.lap;
      if (!s || !lap || this.status() !== 'driving') return;
      lap.feed(s);
      this.lapView.set({ phase: lap.phase, time_s: lap.time_s, fuel_L: lap.fuel_L, hits: lap.hits, failure: lap.failure });
    });
    effect(() => {                       // a finished, valid lap is offered as a best once
      const v = this.verdict();
      if (!v || this.offered) return;
      this.offered = true;
      const best = this.bests.get(this.lapKey);
      const newBest = v.ok && this.bests.offer(this.lapKey, v.score);
      this.lapBest.set({ best: newBest ? v.score : best, newBest });
    });
    void engineLibrary().list().then(list => {
      this.mine.set(list);
      const want = typeof location !== 'undefined' ? new URLSearchParams(location.search).get('engine') : null;
      if (want?.startsWith(MY) && list.some(e => MY + e.key === want)) this.preset.set(want);
    }).catch(() => { /* no saved engines: the roster still works */ });
    if (typeof location !== 'undefined' && location.search.includes('e2e')) {
      (globalThis as Record<string, unknown>)['__enjoy'] = {
        view: () => this.v(), level: () => this.s.levelDb(), soundError: () => this.soundError(),
        info: () => this.s.info(), vibes: () => this.vibes.slice(), road: () => this.road(), routeKey: () => this.routeKey(),
        par: () => this.par(), parMs: () => this.s.parMs(), lap: () => this.lapView(), goalText: () => this.goalText(),
        verdict: () => this.verdict(),
      };
    }
  }

  protected trans(): Transmission { return this.manual() ? 'manual' : 'tc'; }

  protected selectPreset(p: string): void { this.preset.set(p); this.s.stop(); }
  protected setManual(m: boolean): void { this.manual.set(m); this.s.stop(); }

  /** One tap starts the engine and the sound (the tap is the audio gesture). */
  protected async start(): Promise<void> {
    releaseFocus();
    this.pedals = { throttle: null, brake: 0, clutch: 0 };
    this.vib.started();
    if (!this.soundOn()) await this.s.soundStart();
    const g = this.imported();
    const p = this.preset();
    const route = this.routeKey();
    this.driven.set(route);
    const r = routeOf(route);
    this.lapGoal = r ? this.goal() : 'free';
    this.lap = r && this.lapGoal !== 'free' ? new LapRun(r.length) : undefined;
    this.lapKey = route ? bestKey(this.preset(), route, this.lapGoal, this.env.current(), this.trans()) : '';
    this.offered = false;
    this.lapBest.set({ newBest: false });
    this.lapView.set(null);
    if (p === IMPORTED && g) await this.s.loadGrid(g, this.trans(), true, this.env.air(), this.env.cfpp(), route);
    else if (p.startsWith(MY)) {
      const saved = await engineLibrary().grid(p.slice(MY.length)).catch(() => undefined);
      if (saved) await this.s.loadGrid(saved, this.trans(), true, this.env.air(), this.env.cfpp(), route);
      else this.s.error.set('that engine is no longer saved in this browser');
    } else await this.s.load(p, this.trans(), true, this.env.air(), this.env.cfpp(), route);
  }

  /** "Open project" (Phase 7 step 7): as on /drive; a dual clutch drives as Auto here. */
  protected async openProject(input: HTMLInputElement): Promise<void> {
    const file = input.files?.[0];
    input.value = '';
    if (!file) return;
    this.importError.set(undefined);
    this.projectNote.set(undefined);
    const parsed = parseProject(await file.text());
    if (typeof parsed === 'string') { this.importError.set(`${file.name}: ${parsed}`); return; }
    const note = applyProject(parsed, this.edits, this.env);
    this.stop();
    if (parsed.drive) this.manual.set(parsed.drive.gearbox === 'manual');
    const c = engineChoice(parsed.engine, this.presets.map(p => p.key), this.mine());
    if ('choice' in c) this.preset.set(c.choice);
    else { this.importError.set(`${file.name}: ${c.reason}`); return; }
    const dct = parsed.drive?.gearbox === 'dct' ? ' Enjoy has no dual clutch, so it drives as Auto.' : '';
    this.projectNote.set(`Opened ${file.name}.${note ? ' ' + note : ''}${dct}`);
  }

  /** "Import": a custom engine's grid file (tools/build_live_grids.py --engine). */
  protected async importGrid(input: HTMLInputElement): Promise<void> {
    const file = input.files?.[0];
    input.value = '';
    if (!file) return;
    this.importError.set(undefined);
    try {
      this.imported.set(await readGridFile(file));
      this.selectPreset(IMPORTED);
    } catch (e) {
      this.importError.set(e instanceof Error ? e.message : String(e));
    }
  }

  protected stop(): void { releaseFocus(); this.s.stop(); }

  protected pedal(which: 'throttle' | 'brake' | 'clutch', value: number): void {
    this.pedals = { ...this.pedals, [which]: value };
    this.s.pedals(this.pedals);
    // a released throttle is sent as 0 once; after that the keys have it back
    if (which === 'throttle' && value === 0) this.pedals = { ...this.pedals, throttle: null };
  }

  /** A paddle or Restart, on pointerdown: acts at once, whatever other fingers are down. */
  protected press(key: string, e: PointerEvent): void {
    e.preventDefault();
    this.tap(key);
  }

  /** A paddle or Restart activated from the keyboard (Enter or Space: a click with detail 0). */
  protected keyTap(key: string, e: MouseEvent): void {
    if (e.detail === 0) this.tap(key);
  }

  /** A tap: the key goes down and up, as a keyboard press does. */
  protected tap(key: string): void {
    releaseFocus();
    this.s.key(key, true);
    this.s.key(key, false);
  }

  protected nextMic(): void {
    releaseFocus();
    const i = MICS.findIndex(m => m.key === this.s.mic());
    this.s.setMic(MICS[(i + 1) % MICS.length]!.key);
  }

  protected toggleSound(): void {
    releaseFocus();
    if (this.soundOn()) this.s.soundStop();
    else void this.s.soundStart();
  }

  @HostListener('document:keydown', ['$event'])
  protected keydown(ev: KeyboardEvent): void { this.key(ev, true); }

  @HostListener('document:keyup', ['$event'])
  protected keyup(ev: KeyboardEvent): void { this.key(ev, false); }

  private key(ev: KeyboardEvent, down: boolean): void {
    if (!this.s.running) return;
    if ((ev.target as HTMLElement | null)?.closest?.('select, input, button')) return;
    const mic = MIC_KEYS[ev.key];
    if (mic) { if (down && !ev.repeat) this.s.setMic(mic); return; }
    const k = controlKey(ev.key);
    if (!k) return;
    ev.preventDefault();
    if (down && ev.repeat) return;
    if (down) this.held.add(k); else this.held.delete(k);
    this.s.key(k, down);
  }

  @HostListener('window:blur')
  protected blur(): void {
    for (const k of this.held) this.s.key(k, false);
    this.held.clear();
  }

  ngOnDestroy(): void { this.s.dispose(); }
}
