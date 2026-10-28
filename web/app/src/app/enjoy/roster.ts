// Enjoy mode's engines (ADR-012, roster B; ADR-023, P14): built with builder.py from
// the brochure numbers in engines/<key>.json, tuned until verify() holds each
// plateau (engines/ROSTER.md), each with a vehicle and a converged grid.
// /drive keeps the development presets.
//
// P14's engines are named by what they are, in the vehicle they drive; the real
// engine whose published figures they follow is named by reference only
// (`modelledOn`, ADR-023 N2), never as the product's name.
export interface RosterEngine {
  readonly key: string;
  readonly name: string;
  readonly group: string;
  readonly modelledOn?: string;
}

const CARS = 'Cars and SUVs', TRUCKS = 'Trucks', TRACTORS = 'Tractors';

/** The first is the page's default engine. */
export const ROSTER: readonly RosterEngine[] = [
  { key: 'hatch15', name: 'Hatchback · 1.5 L, 115 ps', group: CARS },
  { key: 'crdi22', name: 'SUV · 2.2 L, 150 ps', group: CARS },
  { key: 'vw19tdi', name: 'Hatchback · 1.9 L four, 90 ps', group: CARS, modelledOn: "Volkswagen's 1.9 TDI (ALH)" },
  { key: 'mhawk75', name: 'Car · 1.5 L three, 75 bhp', group: CARS, modelledOn: "Mahindra's mHawk75 (Bolero)" },
  { key: 'mhawk22', name: 'SUV · 2.2 L four, 175 ps', group: CARS, modelledOn: "Mahindra's mHawk 2.2 (Scorpio-N)" },
  { key: 'gd28', name: 'SUV · 2.8 L four, 204 ps', group: CARS, modelledOn: "Toyota's 1GD-FTV (Fortuner, Hilux)" },
  { key: 'duratorq32', name: 'SUV · 3.2 L five, 200 ps', group: CARS, modelledOn: "Ford's 3.2 Duratorq (Endeavour, Ranger)" },
  { key: 'b57', name: 'Car · 3.0 L six, 265 ps', group: CARS, modelledOn: "BMW's B57 3.0 (330d, 530d)" },
  { key: 'truck127', name: 'Truck · 12.7 L, 530 hp', group: TRUCKS },
  { key: 'v8hd', name: 'Truck · 15 L V8, 600 ps', group: TRUCKS },
  { key: 'single10', name: 'Tractor · 1.0 L single, 15 hp', group: TRACTORS },
];

/** The roster in `<optgroup>`s, groups in order of first appearance. */
export function rosterGroups(roster: readonly RosterEngine[] = ROSTER): { label: string; engines: RosterEngine[] }[] {
  const out: { label: string; engines: RosterEngine[] }[] = [];
  for (const e of roster) {
    const g = out.find(x => x.label === e.group);
    if (g) g.engines.push(e);
    else out.push({ label: e.group, engines: [e] });
  }
  return out;
}
