"""Run simulated winters through the hourly model, many at once."""
from dataclasses import fields

import numpy as np

from .forcing import Forcing, hourly_from_daily
from .grid import NDAYS, PROBLEMS
from .state import empty_state
from .step import ICE, SOFT, step

AFTERNOON_H = 14


def _stack(forcings):
    """One Forcing with a leading season axis, every array shaped (n, NB, 1) or (n, 1, 1)."""
    out = {}
    for fld in fields(Forcing):
        values = [getattr(f, fld.name) for f in forcings]
        if fld.name in ("doy", "hour", "sw_down"):
            out[fld.name] = values[0]
        else:
            a = np.stack([np.asarray(v, dtype=float) for v in values])
            out[fld.name] = a.reshape(a.shape + (1,) * (3 - a.ndim))
    return Forcing(**out)


def run_hourly_seasons(wxs, p, horizon=None):
    """Hourly model over a list of simulated winters (weather.make_season output).

    Returns the daily model's keys as (n, NDAYS, NB, 8) daily values: problem
    indices are the day's hourly max, ice is 1 if the surface was still ice in
    the afternoon and 0.5 if it was ice only part of the day, ft is a refreeze
    after a thaw, corn is a day that went soft and refroze, swe is at 23:00.
    Also surface_hourly (n, NDAYS, 24, NB, 8) and snowfall (n, NB).
    """
    s = empty_state((len(wxs),), p)
    shape = s.new_mm.shape
    out = {k: np.zeros((NDAYS,) + shape) for k in PROBLEMS + ["ice", "swe", "ft", "corn"]}
    surface = np.zeros((NDAYS, 24) + shape, np.int8)
    snowfall = np.zeros(shape[:-1])
    for d in range(NDAYS):
        cycle = np.zeros(shape, bool)
        for h, f in enumerate(_stack(day) for day in zip(*[hourly_from_daily(wx, d, p) for wx in wxs])):
            s, o = step(s, f, p, horizon)
            for k in PROBLEMS:
                out[k][d] = np.maximum(out[k][d], getattr(o, k))
            surface[d, h] = o.surface
            cycle |= o.cycle
            snowfall += o.snow_mm[..., 0]
        out["swe"][d] = o.swe_mm
        ice = surface[d] == ICE
        out["ice"][d] = np.where(ice[AFTERNOON_H], 1.0, np.where(ice.any(axis=0), 0.5, 0.0))
        out["ft"][d] = cycle
        out["corn"][d] = cycle & (surface[d] == SOFT).any(axis=0)
    res = {k: np.moveaxis(v, 0, 1) for k, v in out.items()}
    res["surface_hourly"] = np.moveaxis(surface, 2, 0)
    res["snowfall"] = snowfall
    return res
