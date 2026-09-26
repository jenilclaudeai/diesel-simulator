import { Routes } from '@angular/router';
import { Dyno } from './dyno/dyno';
import { GridPage } from './grid/grid';

export const routes: Routes = [
  { path: '', component: Dyno, title: 'Dyno pull — Diesel Sim' },
  { path: 'grid', component: GridPage, title: 'Operating grid — Diesel Sim' },
];
