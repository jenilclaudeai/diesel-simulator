"""dieselsim -- a physics-based diesel engine and sound simulator."""
from .config import (EngineSpec, get_preset, PRESETS, heavy_truck_i6,
                     light_duty_i4, industrial_single)

__all__ = ["EngineSpec", "get_preset", "PRESETS", "heavy_truck_i6",
           "light_duty_i4", "industrial_single"]
__version__ = "1.0.0"
