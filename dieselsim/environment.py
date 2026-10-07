"""
Environment presets (Phase 7, ADR-016): five real places and seasons, each
the air an engine breathes and the fuel sold there.

A preset is data. It reaches the solver only as spec overrides
(`thermal.ambient_p`, `thermal.ambient_T`, `inj.cetane_number`), which a
grid already records, so this module is outside the grid hash
(bridge.GRID_HASH_EXCLUDES) and nothing on a grid's path imports it.
Humidity and the fuel's cold-filter plugging point (CFPP) are carried for
the humidity correction and the cold-flow cap (ADR-016 items 3 and 4); the
solver does not read them.

"Very close, not perfect" (PLAN.md): each number is a typical value with
its source, not a forecast. Altitude becomes pressure through the ICAO
standard atmosphere, so local weather (a high or a low) is not in it.
"""
import math
from dataclasses import asdict, dataclass

P_STD = 101325.0        # Pa, sea level, ICAO standard atmosphere
T_STD = 298.0           # K, the air every engine was rated at (engine.RATING_T_AMB)
H_REF = 10.71           # g water / kg dry air: ISO 8178's reference humidity


def pressure_at(altitude_m: float) -> float:
    """Static pressure at an altitude, ICAO standard atmosphere (troposphere), Pa."""
    return P_STD * (1.0 - 2.25577e-5 * altitude_m) ** 5.25588


def saturation_pressure(T: float) -> float:
    """Water vapour saturation pressure over water, Pa (Magnus, Alduchov-Eskridge 1996)."""
    t = T - 273.15
    return 610.94 * math.exp(17.625 * t / (t + 243.04))


def humidity_ratio(T: float, p: float, rh_pct: float) -> float:
    """Absolute humidity, g water per kg dry air (ISO 8178's H)."""
    pv = rh_pct / 100.0 * saturation_pressure(T)
    return 621.98 * pv / (p - pv)


@dataclass(frozen=True)
class Environment:
    key: str
    name: str              # what the picker shows
    place: str             # the real place and season
    altitude_m: float
    T_C: float             # ambient temperature, deg C
    rh_pct: float          # relative humidity, %
    fuel: str              # the grade sold there
    cetane: float | None   # None: keep the engine's own fuel
    cfpp_C: float | None   # the fuel's cold-filter plugging point; None: not specified
    sources: str

    @property
    def p_amb(self) -> float:
        return pressure_at(self.altitude_m)

    @property
    def T_amb(self) -> float:
        return self.T_C + 273.15

    def overrides(self) -> dict:
        """The spec fields this environment sets (the bridge's dotted paths)."""
        out = {"thermal.ambient_p": self.p_amb, "thermal.ambient_T": self.T_amb}
        if self.cetane is not None:
            out["inj.cetane_number"] = self.cetane
        return out

    def describe(self) -> dict:
        d = asdict(self)
        d.update(p_amb=self.p_amb, T_amb=self.T_amb, overrides=self.overrides(),
                 humidity_g_kg=humidity_ratio(self.T_amb, self.p_amb, self.rh_pct))
        return d


# Fuel grades (sources checked 2026-10-07):
#  - IS 1460:2017 (India, BS-VI): cetane >= 51; CFPP <= 6 C (winter), <= 18 C (summer).
#    BPCL and CPCL product data sheets; dieselnet.com/standards/in/fuel_diesel.php
#  - EN 590: cetane >= 51 (temperate grades); arctic class 2 CFPP -32 C.
#    en.wikipedia.org/wiki/EN_590; Neste: arctic diesel CFPP -32 C
ENVIRONMENTS = {
    "standard": Environment(
        key="standard", name="Standard air", place="The reference: sea level, 25 °C",
        # T_STD is 298.0 K, the air the engines were rated at, so this preset changes nothing;
        # 54.74% RH at 298 K is ISO 8178's reference humidity, 10.71 g/kg (by this module's Magnus)
        altitude_m=0.0, T_C=24.85, rh_pct=54.74,   # 24.85 + 273.15 == 298.0 exactly (T_STD)
        fuel="the engine's own", cetane=None, cfpp_C=None,
        sources="ISO 8178 reference humidity 10.71 g/kg; ICAO standard atmosphere"),
    "desert": Environment(
        key="desert", name="Desert summer", place="Jaisalmer, Rajasthan, May afternoon",
        altitude_m=225.0, T_C=42.0, rh_pct=15.0,
        fuel="BS-VI summer diesel (IS 1460)", cetane=51.0, cfpp_C=18.0,
        sources="May mean daily maximum 41.9 C (weather2travel, IMD); afternoon RH ~13-15%; "
                "altitude ~225 m (approx.); IS 1460 summer grade"),
    "winter": Environment(
        key="winter", name="Arctic winter", place="Rovaniemi, Finland, a cold January morning",
        altitude_m=201.0, T_C=-20.0, rh_pct=85.0,
        fuel="arctic diesel (EN 590 class 2)", cetane=51.0, cfpp_C=-32.0,
        sources="Rovaniemi 201 m; January daily lows -10.5 (warmest) to -29.3 C (coldest) on record "
                "(extremeweatherwatch); RH ~85% (approx.); EN 590 arctic class 2, Neste arctic diesel"),
    "plateau": Environment(
        key="plateau", name="High plateau", place="Leh, Ladakh, June",
        altitude_m=3500.0, T_C=20.0, rh_pct=35.0,
        fuel="BS-VI winter diesel (IS 1460)", cetane=51.0, cfpp_C=6.0,
        sources="Leh ~3500 m (11,600 ft); June highs ~21 C, lows ~7 C; RH mostly under 40% "
                "(Ladakh disaster management authority, climate-data.org); IS 1460 winter grade"),
    "tropics": Environment(
        key="tropics", name="Humid tropics", place="Mumbai, July (monsoon)",
        altitude_m=14.0, T_C=29.0, rh_pct=85.0,
        fuel="BS-VI summer diesel (IS 1460)", cetane=51.0, cfpp_C=18.0,
        sources="Santacruz July mean high 29 C, low 24 C; RH usually over 80% (NOAA GHCND, 53 years); "
                "altitude ~14 m (approx.); IS 1460 summer grade"),
}


def describe_environments() -> list:
    """Every preset, in picker order, with its derived numbers and spec overrides."""
    return [e.describe() for e in ENVIRONMENTS.values()]
