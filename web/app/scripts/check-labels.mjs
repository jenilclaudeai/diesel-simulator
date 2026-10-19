// PLAN, Phase 6: economy and BSFC shown anywhere are labelled steady-state
// (FINDING-009). The Dyno table's BSFC column went unlabelled until the
// Phase 6 exit review (REVIEW-008), so: every template that shows a fuel
// figure says "steady state" (or "steady-state") somewhere on it.
import { readdirSync, readFileSync } from 'node:fs';
import { join, relative } from 'node:path';

const APP = join(import.meta.dirname, '..', 'src', 'app');
// U().econ: Phase 8's driver units print the economy's unit (L/100 km or mpg) from
// units.ts, so /enjoy has no literal "L/100" left. Without it the check lost /enjoy
// and still passed (5 of 10, at the old floor of 5): the floor is now 6.
const FUEL = /BSFC|economy|L\/100|km\/L|mpg|fuel figures|U\(\)\.econ\b/i;

const templates = dir => readdirSync(dir, { withFileTypes: true }).flatMap(e =>
  e.isDirectory() ? templates(join(dir, e.name)) : e.name.endsWith('.html') ? [join(dir, e.name)] : []);

const files = templates(APP);
const showing = files.filter(f => FUEL.test(readFileSync(f, 'utf8')));
const unlabelled = showing.filter(f => !/steady[- ]state/i.test(readFileSync(f, 'utf8')));
const names = l => l.map(f => relative(APP, f)).join(', ');

if (files.length < 9 || showing.length < 6) {
  console.error(`check-labels: found ${files.length} templates, ${showing.length} with fuel figures; expected at least 9 and 6`);
  process.exit(1);
}
if (unlabelled.length) {
  console.error(`check-labels: fuel figures not labelled steady-state (FINDING-009): ${names(unlabelled)}`);
  process.exit(1);
}
console.log(`check-labels: ${showing.length} of ${files.length} templates show fuel figures, all labelled steady-state: ${names(showing)}`);
