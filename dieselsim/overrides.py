"""
Validated spec overrides: {"turbo.turbine_area_eff": 4.0e-4, "afr_limit": 18.0}.

Shared by batch.py and the browser bridge. Previously batch._apply did a bare
setattr, so a typo such as "turbo.turbin_area_eff" silently created a new
attribute and left the real field untouched -- a parameter sweep would return
"no effect" instead of an error. Here an unknown path, a type mismatch or a
non-finite number raises, naming the problem.
"""
import difflib
import math
from dataclasses import fields, is_dataclass


class OverrideError(ValueError):
    pass


def _field_names(obj):
    return [f.name for f in fields(obj)] if is_dataclass(obj) else list(vars(obj))


def apply_overrides(spec, overrides):
    for path, val in (overrides or {}).items():
        obj = spec
        parts = path.split(".")
        for depth, p in enumerate(parts):
            names = _field_names(obj)
            if p not in names:
                near = difflib.get_close_matches(p, names, n=3)
                hint = f" -- did you mean {', '.join(near)}?" if near else ""
                where = ".".join(parts[:depth]) or "spec"
                raise OverrideError(f"unknown field '{p}' in {where} "
                                    f"(override '{path}'){hint}")
            if depth < len(parts) - 1:
                obj = getattr(obj, p)
        name = parts[-1]
        cur = getattr(obj, name)
        setattr(obj, name, _coerce(path, cur, val))
    return spec


def _coerce(path, cur, val):
    if isinstance(cur, bool):
        if not isinstance(val, bool):
            raise OverrideError(f"'{path}' is a bool, got {type(val).__name__}")
        return val
    if isinstance(cur, (int, float)):
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            raise OverrideError(f"'{path}' is a number, got {type(val).__name__}")
        if not math.isfinite(val):
            raise OverrideError(f"'{path}' must be finite, got {val}")
        return type(cur)(val) if isinstance(cur, float) else val
    if isinstance(cur, tuple):
        if not isinstance(val, (list, tuple)):
            raise OverrideError(f"'{path}' is a sequence, got {type(val).__name__}")
        return tuple(val)
    if isinstance(cur, str) and not isinstance(val, str):
        raise OverrideError(f"'{path}' is a string, got {type(val).__name__}")
    return val
