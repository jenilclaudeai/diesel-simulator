import { ChangeDetectionStrategy, Component, DestroyRef, inject, signal } from '@angular/core';
import { SwUpdate } from '@angular/service-worker';

/**
 * ADR-024: the offline copy tells you when a newer version is ready.
 *
 * The service worker keeps a page on the version it opened with, so an installed app left
 * open (or reopened from the background) keeps running the old one after a deploy, with no
 * error. It checks for a new version whenever the page comes back into view, and this bar
 * offers the reload instead of forcing one: a reload mid-drive ends the drive.
 */
@Component({
  selector: 'app-update',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (state() === 'ready') {
      <div class="update" role="status">
        <span>A new version is ready.</span>
        <button type="button" class="reload" (click)="reload()">Reload</button>
        <button type="button" class="later" (click)="state.set('none')">Later</button>
      </div>
    } @else if (state() === 'broken') {
      <div class="update" role="alert">
        <span>The offline copy is out of date and can't be used.</span>
        <button type="button" class="reload" (click)="reload()">Reload</button>
      </div>
    }
  `,
  styles: `
    .update {
      position: fixed; top: 8px; left: 50%; transform: translateX(-50%); z-index: 1000;
      display: flex; gap: 12px; align-items: center; max-width: calc(100vw - 32px);
      padding: 8px 12px; border-radius: 6px;
      background: var(--slate); color: var(--grey); font-size: 0.95rem;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
    }
    button {
      font: inherit; padding: 4px 12px; border-radius: 4px; cursor: pointer;
      border: 1px solid var(--grey); background: transparent; color: var(--grey);
    }
    button.reload { background: var(--amber); border-color: var(--amber); color: var(--slate); }
  `,
})
export class AppUpdate {
  protected readonly state = signal<'none' | 'ready' | 'broken'>('none');
  constructor() {
    const sw = inject(SwUpdate, { optional: true });
    if (!sw?.isEnabled) return;
    const a = sw.versionUpdates.subscribe(e => {
      if (e.type === 'VERSION_READY') this.state.set('ready');
    });
    const b = sw.unrecoverable.subscribe(() => this.state.set('broken'));
    const onShow = () => {
      if (document.visibilityState === 'visible') sw.checkForUpdate().catch(() => { /* offline */ });
    };
    document.addEventListener('visibilitychange', onShow);
    inject(DestroyRef).onDestroy(() => {
      a.unsubscribe(); b.unsubscribe();
      document.removeEventListener('visibilitychange', onShow);
    });
  }

  protected reload(): void { location.reload(); }
}
