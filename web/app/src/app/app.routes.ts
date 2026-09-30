import { Routes } from '@angular/router';
import { Dyno } from './dyno/dyno';
import { GridPage } from './grid/grid';
import { DrivePage } from './drive/drive';
import { EnjoyPage } from './enjoy/enjoy';

export const routes: Routes = [
  { path: '', component: Dyno, title: 'Dyno pull — Diesel Sim' },
  { path: 'grid', component: GridPage, title: 'Operating grid — Diesel Sim' },
  { path: 'drive', component: DrivePage, title: 'Drive — Diesel Sim' },
  { path: 'enjoy', component: EnjoyPage, title: 'Enjoy — Diesel Sim' },
];
