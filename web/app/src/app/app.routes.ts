import { Routes } from '@angular/router';
import { EnjoyPage } from './enjoy/enjoy';

/**
 * The Enjoy-only deployment (branch `deploy/enjoy-only`): Enjoy is the whole
 * app. The solver pages (Dyno, Grid, Cycle, Spec, Sweep, Durability, Drive)
 * have no route here, so the build leaves them out and never needs Pyodide.
 * An old link to any of them, or to the site's root, lands on Enjoy, with its
 * query (`?route=`, `?goal=`) kept.
 */
export const routes: Routes = [
  { path: '', redirectTo: 'enjoy', pathMatch: 'full' },
  { path: 'enjoy', component: EnjoyPage, title: 'Enjoy — Diesel Sim' },
  { path: '**', redirectTo: 'enjoy' },
];
