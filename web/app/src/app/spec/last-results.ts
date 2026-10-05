import { Injectable, signal } from '@angular/core';

/**
 * Each solving page's last results, kept while the app is open (Phase 6,
 * ADR-015). Spec edits happen on /spec, which unloads the page that solved;
 * keeping its results is what lets that page, on return, show them flagged
 * out of date (SpecStatus) rather than silently forget them.
 */
@Injectable({ providedIn: 'root' })
export class LastResults {
  private readonly store = signal<Record<string, unknown>>({});

  get<T>(page: string): T | undefined {
    return this.store()[page] as T | undefined;
  }

  set<T>(page: string, value: T): void {
    this.store.update(s => ({ ...s, [page]: value }));
  }

  clear(page: string): void {
    this.store.update(s => { const n = { ...s }; delete n[page]; return n; });
  }
}
