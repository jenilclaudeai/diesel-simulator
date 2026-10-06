import { Routes } from '@angular/router';
import { Dyno } from './dyno/dyno';
import { GridPage } from './grid/grid';
import { DrivePage } from './drive/drive';
import { EnjoyPage } from './enjoy/enjoy';
import { CyclePage } from './cycle/cycle';
import { SpecPage } from './spec/spec';
import { SweepPage } from './sweep/sweep';
import { DurabilityPage } from './durability/durability';

export const routes: Routes = [
  { path: '', component: Dyno, title: 'Dyno pull — Diesel Sim' },
  { path: 'grid', component: GridPage, title: 'Operating grid — Diesel Sim' },
  { path: 'cycle', component: CyclePage, title: 'Combustion cycle — Diesel Sim' },
  { path: 'spec', component: SpecPage, title: 'Spec editor — Diesel Sim' },
  { path: 'sweep', component: SweepPage, title: 'Parameter sweep — Diesel Sim' },
  { path: 'durability', component: DurabilityPage, title: 'Durability — Diesel Sim' },
  { path: 'drive', component: DrivePage, title: 'Drive — Diesel Sim' },
  { path: 'enjoy', component: EnjoyPage, title: 'Enjoy — Diesel Sim' },
];
