// Enjoy mode's engines (ADR-012, roster B): built with builder.py from the
// brochure numbers in engines/<key>.json, tuned until verify() holds each
// plateau (engines/ROSTER.md), each with its own vehicle and converged grid.
// /drive keeps the development presets.
export const ROSTER: readonly { key: string; name: string }[] = [
  { key: 'hatch15', name: 'Hatchback · 1.5 L, 115 ps' },
  { key: 'crdi22', name: 'SUV · 2.2 L, 150 ps' },
  { key: 'truck127', name: 'Truck · 12.7 L, 530 hp' },
  { key: 'v8hd', name: 'Truck · 15 L V8, 600 ps' },
  { key: 'single10', name: 'Tractor · 1.0 L single, 15 hp' },
];
