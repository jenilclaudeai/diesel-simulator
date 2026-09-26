// Public surface of @dieselsim/physics: the TypeScript ports the app runs.
export { SliderCrank, Cam, coreProfile, type CamSpec, type CrankGeometry } from "./kinematics.js";
export * as thermo from "./thermo.js";
export { Oil, type Lubricant, type OilCondition } from "./lubrication.js";
export { FrictionModel, type EngineView, type FrictionSpec, type WearState } from "./friction.js";
export { type LiveSpec, type Perf } from "./live/common.js";
export { PerfGrid } from "./live/grid.js";
export { Adr011Grid, type Adr011GridData } from "./live/adr011.js";
export { vehicleFor, finishVehicle, type Transmission, type Vehicle } from "./live/vehicle.js";
export { Driveline, Gearbox, LaunchClutch, ManualClutch, TorqueConverter } from "./live/driveline.js";
export { LiveEngine, handleKey, pedalReturn, type LiveState } from "./live/engine.js";
