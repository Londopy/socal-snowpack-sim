"""Clear-sky sun on the 38-degree slope for each aspect."""
import math

import numpy as np

from .grid import ASPECTS, LAT, NDAYS, SLOPE, START_DOY


def _sun(doy, hours, lat):
    """Sine of elevation, elevation and azimuth (radians, clockwise from north), local solar time."""
    dec = math.radians(23.44) * math.sin(2 * math.pi * (284 + doy) / 365.0)
    ha = np.radians(15.0 * (hours - 12.0))
    sin_el = math.sin(lat) * math.sin(dec) + math.cos(lat) * math.cos(dec) * np.cos(ha)
    el = np.arcsin(np.clip(sin_el, -1, 1))
    az = np.arctan2(-np.cos(dec) * np.sin(ha),
                    np.sin(dec) * math.cos(lat) - np.cos(dec) * np.cos(ha) * math.sin(lat))
    return sin_el, el, az


def _clear_sky(sin_el, s):
    """Meinel direct beam and a simple diffuse term, W/m2."""
    up = sin_el > s.min_sin_el
    am = 1.0 / np.maximum(sin_el, s.min_sin_el)
    direct = s.solar_const_wm2 * s.meinel_base ** (am ** s.meinel_exp) * up
    diffuse = s.diffuse_frac * direct * np.maximum(sin_el, 0) + s.diffuse_floor_wm2 * up
    return direct, diffuse


def _incidence(el, az, sin_el, asp):
    sl = math.radians(SLOPE)
    return np.cos(el) * math.sin(sl) * np.cos(az - asp) + sin_el * math.cos(sl)


def sun_position(doy, hour, lat_deg):
    """Sun elevation and azimuth in degrees (azimuth clockwise from north), local solar time."""
    _, el, az = _sun(doy, np.asarray(hour, dtype=float), math.radians(lat_deg))
    return np.degrees(el), np.degrees(az) % 360.0


def solar_tables(p):
    """Clear-sky daily-mean and sunniest-hours irradiance (W/m2) on a 38-degree
    slope for each aspect and each day of the season. No terrain shading."""
    s = p.solar
    lat = math.radians(LAT)
    mean = np.zeros((NDAYS, 8))
    peak = np.zeros((NDAYS, 8))
    hours = np.arange(0, 24, 1 / s.substeps_per_hour)
    n_peak = s.peak_hours * s.substeps_per_hour
    for d in range(NDAYS):
        doy = (START_DOY + d - 1) % 365 + 1
        sin_el, el, az = _sun(doy, hours, lat)
        direct, diffuse = _clear_sky(sin_el, s)
        for a, asp in enumerate(np.radians(ASPECTS)):
            g = direct * np.maximum(_incidence(el, az, sin_el, asp), 0) + diffuse
            mean[d, a] = g.mean()
            peak[d, a] = np.sort(g)[-n_peak:].mean()
    return mean, peak


def hourly_flat(doy, hour, p):
    """Mean clear-sky irradiance (W/m2) over one hour on flat ground."""
    s = p.solar
    hours = hour + np.arange(s.substeps_per_hour) / s.substeps_per_hour
    sin_el, _, _ = _sun(doy, hours, math.radians(LAT))
    direct, diffuse = _clear_sky(sin_el, s)
    return float((direct * np.maximum(sin_el, 0) + diffuse).mean())


def hourly_irradiance(doy, hour, p, horizon=None):
    """Mean clear-sky irradiance (W/m2) over one hour on the 38-degree slope.

    Without a horizon the result has shape (8,). With a horizon table shaped
    (..., NB, 8, n_az) in degrees, direct sun is cut whenever the sun is below
    the horizon at its azimuth, and the result has shape (..., NB, 8). A NaN
    horizon (a zone with no terrain) means no shading.
    """
    s = p.solar
    hours = hour + np.arange(s.substeps_per_hour) / s.substeps_per_hour
    sin_el, el, az = _sun(doy, hours, math.radians(LAT))
    direct, diffuse = _clear_sky(sin_el, s)
    asp = np.radians(ASPECTS)
    beam = direct[:, None] * np.maximum(_incidence(el[:, None], az[:, None], sin_el[:, None], asp[None, :]), 0)
    if horizon is None:
        return (beam + diffuse[:, None]).mean(axis=0)
    n_az = horizon.shape[-1]
    bins = np.round(np.degrees(az) % 360.0 / (360.0 / n_az)).astype(int) % n_az
    total = np.zeros(horizon.shape[:-1])
    for k in range(len(hours)):
        lit = ~(np.degrees(el[k]) < horizon[..., bins[k]])
        total += beam[k] * lit + diffuse[k]
    return total / len(hours)
