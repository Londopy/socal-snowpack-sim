"""Clear-sky sun on the 38-degree slope for each aspect."""
import math

import numpy as np

from .grid import ASPECTS, LAT, NDAYS, SLOPE, START_DOY


def solar_tables(p):
    """Clear-sky daily-mean and sunniest-hours irradiance (W/m2) on a 38-degree
    slope for each aspect and each day of the season. No terrain shading."""
    s = p.solar
    lat = math.radians(LAT)
    sl = math.radians(SLOPE)
    mean = np.zeros((NDAYS, 8))
    peak = np.zeros((NDAYS, 8))
    hours = np.arange(0, 24, 1 / s.substeps_per_hour)
    n_peak = s.peak_hours * s.substeps_per_hour
    for d in range(NDAYS):
        doy = (START_DOY + d - 1) % 365 + 1
        dec = math.radians(23.44) * math.sin(2 * math.pi * (284 + doy) / 365.0)
        ha = np.radians(15.0 * (hours - 12.0))
        sin_el = math.sin(lat) * math.sin(dec) + math.cos(lat) * math.cos(dec) * np.cos(ha)
        el = np.arcsin(np.clip(sin_el, -1, 1))
        up = sin_el > s.min_sin_el
        az = np.arctan2(-np.cos(dec) * np.sin(ha),
                        np.sin(dec) * math.cos(lat) - np.cos(dec) * np.cos(ha) * math.sin(lat))
        am = 1.0 / np.maximum(sin_el, s.min_sin_el)
        direct = s.solar_const_wm2 * s.meinel_base ** (am ** s.meinel_exp) * up
        diffuse = s.diffuse_frac * direct * np.maximum(sin_el, 0) + s.diffuse_floor_wm2 * up
        for a, asp in enumerate(np.radians(ASPECTS)):
            cos_i = np.cos(el) * math.sin(sl) * np.cos(az - asp) + sin_el * math.cos(sl)
            g = direct * np.maximum(cos_i, 0) + diffuse
            mean[d, a] = g.mean()
            peak[d, a] = np.sort(g)[-n_peak:].mean()
    return mean, peak
