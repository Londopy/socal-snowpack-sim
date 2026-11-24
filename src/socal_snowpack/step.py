"""The hourly snowpack step.

The same processes as the daily model, run on the layer stack one hour at a time:
daily rates become rate / 24 per hour and daily decays exp(-1 / tau) become
exp(-1 / (24 tau)). A toy model for learning, not an avalanche forecast.
"""
import math
from dataclasses import dataclass, replace

import numpy as np

from .daily import band_exposure
from .forcing import snow_fraction
from .grid import ASPECTS, BANDS_M
from .solar import hourly_flat, hourly_irradiance
from .state import CRUST, EMPTY, FACET, NEW, SETTLED, add_snow, buried_weak, top, top_value

NONE, POWDER, WIND, FIRM, ICE, SOFT, WET = range(7)
SURFACE_NAMES = ["none", "powder", "wind-affected", "firm", "ice", "soft", "wet"]
DAY_H = 24.0
_CHECKED = ("t_c", "wind_ms", "wind_from_deg", "cloud")


@dataclass(frozen=True)
class Hourly:
    storm: np.ndarray
    wind: np.ndarray
    wet: np.ndarray
    persistent: np.ndarray
    ice: np.ndarray
    surface: np.ndarray
    swe_mm: np.ndarray
    liquid_mm: np.ndarray
    cycle: np.ndarray


def with_top(a, t, v):
    """Copy of layer array a with the top layer of each zone set to v (zones with no snow untouched)."""
    out = a.copy()
    v = np.where(t >= 0, v, top_value(a, t)).astype(a.dtype)
    np.put_along_axis(out, np.maximum(t, 0)[None], v[None], 0)
    return out


def _split(s, f, p):
    shape = s.new_mm.shape
    frac = snow_fraction(BANDS_M[:, None], f.snow_level_m, f.snow_level_sd_m, f.precip_mm, p)
    precip = np.broadcast_to(f.precip_mm, shape)
    return precip * frac, precip * (1 - frac)


def _snowfall(s, snow, p):
    q = p.daily
    t = top(s)
    total = s.swe_mm.sum(axis=0)
    weak_top = (t >= 0) & ((top_value(s.kind, t) == CRUST) | (top_value(s.facet, t) > q.facet_weak))
    landing = (snow > 0) & (s.new_mm < q.bare_new_mm) & weak_top & (total > q.crust_min_swe_mm)
    s = replace(s, bond_bad=np.where(landing, 1.0, s.bond_bad),
                melt_since_mm=np.where(landing, 0.0, s.melt_since_mm))
    s = add_snow(s, snow, p)
    t = top(s)
    real = (snow > 0) & (top_value(s.kind, t) == NEW) & (top_value(s.swe_mm, t) >= q.snow_event_mm)
    return replace(s, new_mm=s.new_mm + snow, dry_mm=s.dry_mm + snow,
                   hours_since_snow=np.where(real, 0.0, s.hours_since_snow),
                   mf_cycles=np.where(real, 0.0, s.mf_cycles),
                   thaw_h=np.where(real, 0.0, s.thaw_h))


def _wind(s, f, p):
    q = p.daily
    expo = band_exposure(q)[:, None]
    lee = np.cos(np.radians(ASPECTS) - np.radians((f.wind_from_deg + 180.0) % 360.0)[..., None, None])
    lee = np.broadcast_to(lee, s.new_mm.shape)
    strength = np.clip((f.wind_ms - q.wind_min_ms) / q.wind_span_ms, 0, q.wind_strength_cap)[..., None, None]
    avail = np.clip(s.dry_mm / q.dry_full_mm, 0, 1)
    slab = s.wind_slab * math.exp(-1 / (DAY_H * q.wind_slab_tau_days)) \
        + q.wind_load_rate / DAY_H * strength * np.clip(lee, 0, 1) * avail * expo
    scour = strength * np.clip(-lee, 0, 1) * expo
    keep_dry = (1 - q.scour_dry * np.clip(scour, 0, 1)) ** (1 / DAY_H)
    keep_new = (1 - q.scour_new * np.clip(scour, 0, 1)) ** (1 / DAY_H)
    s = replace(s, wind_slab=np.clip(slab, 0, q.index_cap), dry_mm=s.dry_mm * keep_dry, new_mm=s.new_mm * keep_new)
    return s, scour


def _sun(s, f, p, horizon):
    g = hourly_irradiance(f.doy, f.hour, p, horizon)
    if f.sw_down is None:
        return g * (1 - p.daily.cloud_block * f.cloud)[..., None, None]
    flat = hourly_flat(f.doy, f.hour, p)
    ratio = np.minimum(g / max(flat, p.hourly.min_flat_wm2), p.hourly.max_slope_ratio)
    return np.asarray(f.sw_down)[..., None, None] * ratio * (flat > p.hourly.min_flat_wm2)


def _energy(s, f, p, horizon):
    q = p.daily
    alb = q.albedo_fresh - q.albedo_drop * (1 - np.exp(-s.hours_since_snow / (DAY_H * q.albedo_tau_days)))
    e = (1 - alb) * _sun(s, f, p, horizon) - q.day_loss_wm2 + q.day_sens_wm2_per_c * f.t_c
    return np.broadcast_to(e, s.new_mm.shape)


def _water(s, e, rain, p):
    """Melt or refreeze the top layer, add rain, and drain what the surface can't hold."""
    h = p.hourly
    t = top(s)
    has = s.swe_mm.sum(axis=0) > p.daily.has_snow_mm
    swe, liq = top_value(s.swe_mm, t), top_value(s.liquid_mm, t)
    melt = np.where(has, np.minimum(np.maximum(e, 0) * h.melt_mm_per_wm2_hour, swe), 0.0)
    frz = np.where(has & (e < 0), np.minimum(liq, -e * h.melt_mm_per_wm2_hour), 0.0)
    rain_in = np.where(has, rain, 0.0)
    swe = swe - melt + frz
    liq = liq + melt + rain_in - frz
    drain = np.maximum(liq - h.liquid_hold_frac * np.minimum(swe, h.surface_mm), 0)
    liq = liq - drain
    gone = (t >= 0) & (swe <= 0)
    drain = drain + np.where(gone, liq, 0.0)
    liq = np.where(gone, 0.0, liq)
    wet_now = (liq > h.soft_liquid_mm) | (drain > 0) | (rain_in > h.rain_wet_mm_h)
    s = replace(s, swe_mm=with_top(s.swe_mm, t, np.where(gone, 0.0, swe)),
                liquid_mm=with_top(s.liquid_mm, t, liq),
                kind=with_top(s.kind, t, np.where(gone, EMPTY, top_value(s.kind, t))),
                facet=with_top(s.facet, t, np.where(gone, 0.0, top_value(s.facet, t))),
                melt_since_mm=s.melt_since_mm + drain + rain_in,
                thaw_h=np.where((s.thaw_h > 0) | (liq > 0), s.thaw_h + 1, 0.0),
                since_wet_h=np.where(wet_now, 0.0, s.since_wet_h + 1))
    return s, melt + rain_in, drain, wet_now


def _facets(s, t_c, snow, rain, p):
    q = p.daily
    t = top(s)
    total = s.swe_mm.sum(axis=0)
    dry_top = (t >= 0) & (top_value(s.liquid_mm, t) == 0) & (snow == 0) & (total > q.has_snow_mm)
    depth_cm = total / q.swe_per_cm
    rate = q.facet_rate_per_day / DAY_H * np.clip((-t_c - q.facet_min_cold_c) / q.facet_cold_span_c, 0, 1) \
        * np.clip((q.facet_max_depth_cm - depth_cm) / q.facet_depth_span_cm, 0, 1)
    wet_recent = s.since_wet_h < p.hourly.wet_recent_h
    f_top = top_value(s.facet, t) + np.where(dry_top, rate, 0.0)
    f_top = np.where(wet_recent, f_top * q.facet_wet_factor ** (1 / DAY_H), f_top)
    k_top = top_value(s.kind, t)
    k_top = np.where(dry_top & (f_top > q.facet_weak) & ((k_top == NEW) | (k_top == SETTLED)), FACET, k_top)

    idx = np.arange(s.swe_mm.shape[0]).reshape((-1,) + (1,) * t.ndim)
    buried = (idx < t) & (s.kind != EMPTY)
    above = total - np.cumsum(s.swe_mm, axis=0)
    near_crust = buried & (s.kind == CRUST) & (above < q.crust_facet_max_new_mm) & (t_c < q.crust_facet_cold_c) & dry_top
    heal = (s.melt_since_mm > q.buried_melt_mm) | (rain * DAY_H > q.buried_rain_mm)
    facet = s.facet + np.where(near_crust, q.crust_facet_rate / DAY_H, 0.0)
    facet = np.where(buried, facet * math.exp(-1 / (DAY_H * q.buried_tau_days)), facet)
    facet = np.where(buried & heal, facet * q.buried_heal_factor ** (1 / DAY_H), facet)
    facet = with_top(facet, t, f_top)
    return replace(s, facet=np.clip(facet, 0, 1), kind=with_top(s.kind, t, k_top))


def _indices(s, water, e, snow, p):
    q, h = p.daily, p.hourly
    present = s.swe_mm.sum(axis=0) > q.problem_min_swe_mm
    wet_recent = s.since_wet_h < h.wet_recent_h
    newish = np.clip(s.new_mm / q.wet_new_full_mm, 0, 1)

    loose = q.loose_base + q.loose_new * newish
    wet = np.clip(water / h.wet_water_full_mm, 0, 1) * loose
    wet = np.maximum(wet, q.wet_new_weight * newish * (e > q.wet_new_sun_wm2))
    no_refreeze = s.thaw_h > h.no_refreeze_h
    wet = np.where((s.mf_cycles >= q.corn_cycles) & ~no_refreeze, wet * q.corn_wet_factor, wet)
    wet = np.where(no_refreeze, wet * q.no_refreeze_factor, wet)

    storm = np.clip(s.new_mm / q.storm_full_mm, 0, q.index_cap) * (1 + q.bad_bond_boost * s.bond_bad)
    storm = np.where(wet_recent & (snow == 0), storm * q.storm_wet_factor, storm)

    weak, load = buried_weak(s, p)
    pers = weak * np.clip(load / q.pers_load_full_mm, 0, q.index_cap)

    def shown(v):
        return np.where(present, np.clip(v, 0, q.index_cap), 0.0)
    return shown(storm), shown(s.wind_slab), shown(wet), shown(pers)


def _settle(s, t_c, snow, wet_now, p):
    q = p.daily
    tau = np.where(t_c < q.settle_cold_c, q.settle_tau_cold_days, q.settle_tau_days)
    decay = np.exp(-1 / (DAY_H * tau))
    new = s.new_mm * decay
    wet_recent = s.since_wet_h < p.hourly.wet_recent_h
    slab = np.where(wet_recent & (snow == 0), s.wind_slab * q.wind_slab_wet_factor ** (1 / DAY_H), s.wind_slab)
    return replace(s, new_mm=new, dry_mm=np.where(wet_now, 0.0, s.dry_mm * decay), wind_slab=slab,
                   bond_bad=np.where((new < q.bond_reset_mm) & (snow == 0), 0.0, s.bond_bad))


def _refreeze(s, t_c, p):
    q = p.daily
    t = top(s)
    cycle = (s.thaw_h > 0) & (t >= 0) & (top_value(s.liquid_mm, t) == 0) & (t_c < q.refreeze_c) \
        & (s.swe_mm.sum(axis=0) > q.crust_min_swe_mm)
    s = replace(s, kind=with_top(s.kind, t, np.where(cycle, CRUST, top_value(s.kind, t))),
                mf_cycles=s.mf_cycles + cycle, thaw_h=np.where(cycle, 0.0, s.thaw_h))
    return s, cycle


def _surface(s, rain, drain, scour, p):
    q, h = p.daily, p.hourly
    t = top(s)
    kind, liq = top_value(s.kind, t), top_value(s.liquid_mm, t)
    dry = liq == 0
    total = s.swe_mm.sum(axis=0) + s.liquid_mm.sum(axis=0)
    powder = (kind == NEW) & dry & (top_value(s.age_h, t) <= h.powder_max_age_h) \
        & (top_value(s.swe_mm, t) >= q.snow_event_mm)
    choices = [
        (total <= q.has_snow_mm, NONE),
        ((liq > h.wet_liquid_mm) | (drain > 0) | (rain > h.rain_wet_mm_h), WET),
        (liq > h.soft_liquid_mm, SOFT),
        (powder, POWDER),
        ((s.wind_slab > p.levels.considerable) | (scour > h.scour_surface), WIND),
        ((kind == CRUST) & dry & (s.new_mm < q.bare_new_mm), ICE),
    ]
    return np.select([c for c, _ in choices], [v for _, v in choices], FIRM).astype(np.int8)


def _age(s):
    return replace(s, age_h=np.where(s.kind != EMPTY, s.age_h + 1, 0.0),
                   hours_since_snow=s.hours_since_snow + 1, hour_index=s.hour_index + 1)


def step(s, f, p, horizon=None):
    """Advance the snowpack one hour. Returns the new state and that hour's outputs; s is not changed."""
    for name in _CHECKED:
        if np.isnan(getattr(f, name)).any():
            raise ValueError(f"forcing {name} has NaN")
    t_c = np.broadcast_to(f.t_c, s.new_mm.shape)
    snow, rain = _split(s, f, p)
    s = _snowfall(s, snow, p)
    s, scour = _wind(s, f, p)
    e = _energy(s, f, p, horizon)
    s, water, drain, wet_now = _water(s, e, rain, p)
    s = _facets(s, t_c, snow, rain, p)
    storm, wind, wet, pers = _indices(s, water, e, snow, p)
    s = _settle(s, t_c, snow, wet_now, p)
    s, cycle = _refreeze(s, t_c, p)
    surface = _surface(s, rain, drain, scour, p)
    out = Hourly(storm=storm, wind=wind, wet=wet, persistent=pers, ice=(surface == ICE).astype(float),
                 surface=surface, swe_mm=s.swe_mm.sum(axis=0), liquid_mm=top_value(s.liquid_mm, top(s)),
                 cycle=cycle)
    return _age(s), out
