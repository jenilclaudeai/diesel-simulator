// Every vehicle the live loop knows, under every gearbox, against Python
// (fixtures/vehicles.json, from dieselsim.live.Vehicle): plain data kept in
// two languages, so it is held field for field, exactly.
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { finishVehicle, vehicleFor, VEHICLE_KEYS, type Transmission } from "../src/live/vehicle.js";

const here = path.dirname(fileURLToPath(import.meta.url));
const fx = JSON.parse(readFileSync(path.resolve(here, "..", "..", "fixtures", "vehicles.json"), "utf8")) as {
  meta: { physics_hash: string };
  inputs: { keys: string[]; trans: Transmission[]; vehicle_keys: string[] };
  outputs: Record<string, Record<string, Record<string, unknown>>>;
};
let failed = 0, passed = 0;
const check = (name: string, ok: boolean, note = "") => {
  ok ? passed++ : failed++;
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${note ? "  -- " + note : ""}`);
};
for (const key of fx.inputs.keys) {
  const bad: string[] = [];
  let fields = 0;
  for (const t of fx.inputs.trans) {
    const want = fx.outputs[key]![t]!, got = finishVehicle(vehicleFor(key, t)) as unknown as Record<string, unknown>;
    fields = Object.keys(want).length;
    for (const f of new Set([...Object.keys(want), ...Object.keys(got)]))
      if (JSON.stringify(got[f]) !== JSON.stringify(want[f])) bad.push(`${t}.${f}`);
  }
  check(`vehicle ${key} matches Python under ${fx.inputs.trans.join("/")}`, bad.length === 0,
    bad.length ? `differ: ${bad.slice(0, 4).join(", ")}` : `${fields} fields x ${fx.inputs.trans.length}`);
}
check("the vehicles a custom engine may name match Python's (ADR-014)",
  JSON.stringify([...VEHICLE_KEYS]) === JSON.stringify(fx.inputs.vehicle_keys),
  `${VEHICLE_KEYS.join(", ")} vs ${fx.inputs.vehicle_keys.join(", ")}`);
console.log(`\n${passed} passed, ${failed} failed  (physics ${fx.meta.physics_hash.slice(0, 12)})`);
process.exit(failed ? 1 : 0);
