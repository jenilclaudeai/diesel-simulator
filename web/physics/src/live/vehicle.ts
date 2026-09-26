// Port of dieselsim/live.py Vehicle: everything downstream of the flywheel,
// per preset. The live fixture checks every field against Python's.

export type Transmission = "tc" | "dct";

export interface Vehicle {
  trans: Transmission;
  launch_rpm: number;
  fuel_tank_L: number;
  clutch_cap_max: number; // 0 -> derived from engine torque
  name: string;
  mass: number;           // kg
  r_wheel: number;        // m
  gears: number[];
  final: number;
  CdA: number;            // m^2, drag area
  Crr: number;            // rolling resistance
  eta: number;            // driveline efficiency
  J_trans: number;        // kg.m^2 at gearbox input
  J_wheel: number;        // kg.m^2 all wheels
  TR_stall: number;
  stall_rpm: number;
  tc_diameter_gain: number;
  v_lock_min: number;     // m/s before lockup allowed
}

export function vehicleFor(preset: string, trans: Transmission = "dct"): Vehicle {
  const base = { trans, launch_rpm: 2000.0, fuel_tank_L: 60.0, clutch_cap_max: 0.0 };
  switch (preset) {
    case "hd_i6": // tractor unit, laden
      return { ...base, name: "40 t tractor-trailer", fuel_tank_L: 400.0, stall_rpm: 1900.0, mass: 24000.0,
        r_wheel: 0.506, gears: [3.49, 1.86, 1.41, 1.0, 0.75, 0.65], final: 3.7, CdA: 8.0, Crr: 0.0068,
        eta: 0.94, J_trans: 0.6, J_wheel: 46.0, TR_stall: 1.95, tc_diameter_gain: 1.0, v_lock_min: 8.0 };
    case "ld_i4": // mid-size car / small van
      return { ...base, name: "1.75 t passenger car", fuel_tank_L: 55.0, stall_rpm: 2250.0, mass: 1750.0,
        r_wheel: 0.32, gears: [4.15, 2.37, 1.56, 1.16, 0.86, 0.69], final: 3.63, CdA: 0.72, Crr: 0.01,
        eta: 0.93, J_trans: 0.085, J_wheel: 4.2, TR_stall: 2.1, tc_diameter_gain: 1.0, v_lock_min: 12.0 };
    case "crdi15": // compact car, 7-speed
      return { ...base, name: "1.5 t compact, 7-speed auto", fuel_tank_L: 45.0, mass: 1500.0, r_wheel: 0.315,
        gears: [3.62, 2.05, 1.36, 1.0, 0.79, 0.67, 0.58], final: 4.3, CdA: 0.7, Crr: 0.0092, eta: 0.94,
        launch_rpm: 2100.0, J_trans: 0.07, J_wheel: 3.6, TR_stall: 1.85, stall_rpm: 2100.0,
        tc_diameter_gain: 1.0, v_lock_min: 9.0 };
    default: // small utility tractor
      return { ...base, name: "3 t utility tractor", fuel_tank_L: 60.0, stall_rpm: 1800.0, mass: 3000.0,
        r_wheel: 0.42, gears: [4.5, 2.2, 1.3, 0.9], final: 4.1, CdA: 2.4, Crr: 0.018, eta: 0.88,
        J_trans: 0.12, J_wheel: 9.0, TR_stall: 2.0, tc_diameter_gain: 1.0, v_lock_min: 4.0 };
  }
}

/** _finish_vehicle: a dual clutch has no converter slip to pay for. */
export function finishVehicle(v: Vehicle): Vehicle {
  if (v.trans === "dct") v.eta = Math.min(0.975, v.eta + 0.035);
  return v;
}
