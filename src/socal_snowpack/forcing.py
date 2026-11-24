"""One hour of weather per elevation band, and the rain/snow split."""
import math
from dataclasses import dataclass

import numpy as np

from .daily import band_precip_factor
from .grid import BANDS_M, LAPSE, START_DOY, Z_REF

_erf = np.vectorize(math.erf, otypes=[float])


@dataclass(frozen=True)
class Forcing:
    """Weather for one hour. Arrays broadcast to (..., NB, 1)."""
    t_c: np.ndarray
    precip_mm: np.ndarray
    snow_level_m: np.ndarray
    snow_level_sd_m: np.ndarray
    wind_ms: np.ndarray
    wind_from_deg: np.ndarray
    cloud: np.ndarray
    doy: int
    hour: int
    sw_down: np.ndarray | None = None


def lapse_to_bands(t_ref_c, z_ref_m, bands_m, lapse):
    return t_ref_c + (z_ref_m - bands_m) * lapse


def snow_fraction(bands_m, snow_level_m, sd_m, precip_mm, p):
    """Share of precip falling as snow at each band, from a snow level with an uncertainty in metres."""
    bands_m, level, sd, precip = np.broadcast_arrays(bands_m, snow_level_m, sd_m, precip_mm)
    wet = precip > 0
    if (wet & np.isnan(level)).any():
        raise ValueError("precip with no snow level")
    width = np.maximum(sd, p.hourly.snow_transition_m)
    z = np.where(wet, (bands_m - np.nan_to_num(level)) / width, 0.0)
    frac = 0.5 * (1 + _erf(z / math.sqrt(2)))
    # the normal tails would put a trace of rain into every cold storm and snow into every warm one
    lo = p.hourly.snow_frac_min
    frac = np.where(frac < lo, 0.0, np.where(frac > 1 - lo, 1.0, frac))
    return np.where(wet, frac, 0.0)


def hourly_from_daily(wx, d, p):
    """Spread one simulated day into 24 hourly forcings: a cosine temperature curve
    peaking at 15:00, precip spread evenly, wind and cloud held for the day."""
    dz = (Z_REF - BANDS_M)[:, None] * LAPSE
    half = (wx["Tmax"][d] - wx["Tmin"][d]) / 2
    precip = np.full((len(BANDS_M), 1), wx["P"][d] / 24) * band_precip_factor(p.daily)[:, None]
    doy = (START_DOY + d - 1) % 365 + 1
    return [Forcing(t_c=wx["Tm"][d] + half * math.cos(2 * math.pi * (h - 15) / 24) + dz,
                    precip_mm=precip,
                    snow_level_m=np.asarray(wx["SL"][d]),
                    snow_level_sd_m=np.asarray(0.0),
                    wind_ms=np.asarray(wx["wind"][d]),
                    wind_from_deg=np.asarray(wx["wdir"][d]),
                    cloud=np.asarray(wx["cloud"][d]),
                    doy=doy, hour=h)
            for h in range(24)]
