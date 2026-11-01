import { TestBed } from '@angular/core/testing';
import { SwUpdate, type VersionEvent } from '@angular/service-worker';
import { Subject } from 'rxjs';
import { AppUpdate } from './app-update';

/** A stand-in SwUpdate: the real one needs a registered service worker. */
function fakeSw(isEnabled = true) {
  const versionUpdates = new Subject<VersionEvent>();
  const unrecoverable = new Subject<{ type: 'UNRECOVERABLE_STATE'; reason: string }>();
  let checks = 0;
  return {
    sw: { isEnabled, versionUpdates, unrecoverable, checkForUpdate: () => { checks++; return Promise.resolve(false); } },
    versionUpdates, unrecoverable, checks: () => checks,
  };
}

const VERSION = { hash: 'a', appData: undefined };

function mount(f: ReturnType<typeof fakeSw>) {
  TestBed.configureTestingModule({ providers: [{ provide: SwUpdate, useValue: f.sw }] });
  const fix = TestBed.createComponent(AppUpdate);
  fix.detectChanges();
  const text = () => { fix.detectChanges(); return (fix.nativeElement as HTMLElement).textContent?.trim() ?? ''; };
  return { fix, text };
}

describe('ADR-024: the update bar', () => {
  afterEach(() => TestBed.resetTestingModule());

  it('shows nothing until a new version is ready, then offers the reload', () => {
    const f = fakeSw();
    const { fix, text } = mount(f);
    expect(text()).toBe('');
    f.versionUpdates.next({ type: 'VERSION_DETECTED', version: VERSION });   // still downloading
    expect(text()).toBe('');
    f.versionUpdates.next({ type: 'VERSION_READY', currentVersion: VERSION, latestVersion: { hash: 'b', appData: undefined } });
    expect(text()).toContain('A new version is ready.');
    expect((fix.nativeElement as HTMLElement).querySelector('button.reload')).not.toBeNull();
  });

  it('Later hides it without reloading', () => {
    const f = fakeSw();
    const { fix, text } = mount(f);
    f.versionUpdates.next({ type: 'VERSION_READY', currentVersion: VERSION, latestVersion: { hash: 'b', appData: undefined } });
    expect(text()).toContain('ready');
    ((fix.nativeElement as HTMLElement).querySelector('button.later') as HTMLButtonElement).click();
    expect(text()).toBe('');
  });

  it('a broken offline copy says so', () => {
    const f = fakeSw();
    const { text } = mount(f);
    f.unrecoverable.next({ type: 'UNRECOVERABLE_STATE', reason: 'test' });
    expect(text()).toContain("can't be used");
  });

  it('checks for a new version when the page comes back into view', () => {
    const f = fakeSw();
    mount(f);
    expect(f.checks()).toBe(0);
    document.dispatchEvent(new Event('visibilitychange'));   // jsdom: visibilityState is 'visible'
    expect(f.checks()).toBe(1);
  });

  it('with the service worker off (ng serve), stays silent and listens to nothing', () => {
    const f = fakeSw(false);
    const { text } = mount(f);
    f.versionUpdates.next({ type: 'VERSION_READY', currentVersion: VERSION, latestVersion: { hash: 'b', appData: undefined } });
    document.dispatchEvent(new Event('visibilitychange'));
    expect(text()).toBe('');
    expect(f.checks()).toBe(0);
  });
});
