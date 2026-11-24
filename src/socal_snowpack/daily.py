"""The daily snowpack model: one step per day over 5 bands x 8 aspects.

A toy model for learning, not an avalanche forecast. Every threshold is in params.toml.
"""
import math

import numpy as np

from .grid import ASPECTS, BANDS_M, LAPSE, NB, NDAYS, PROBLEMS, Z_REF


def band_precip_factor(q):
    """More precip up high."""
    return np.clip(q.pfac_base + q.pfac_slope * (BANDS_M - q.band_ref_m) / q.band_span_m, q.pfac_min, q.pfac_max)


def band_exposure(q):
    """Wind exposure by band."""
    return np.clip(q.expo_base + q.expo_slope * (BANDS_M - q.band_ref_m) / q.band_span_m, q.expo_min, q.expo_max)


def run_season(wx, gmean, gpeak, p):
    q = p.daily
    shape = (NB, len(ASPECTS))
    dz = (Z_REF - BANDS_M)[:, None] * LAPSE               # temp offset per band
    pfac = band_precip_factor(q)[:, None]
    expo = band_exposure(q)[:, None]
    asp = np.radians(ASPECTS)[None, :]

    swe = np.zeros(shape)        # total snow water, mm
    new = np.zeros(shape)        # recent storm snow, mm water
    dry = np.zeros(shape)        # recent snow still dry and movable by wind
    age = np.full(shape, q.age_init_days)   # days since last real snowfall (albedo)
    wslab = np.zeros(shape)      # wind slab index
    crust = np.zeros(shape, bool)
    facet = np.zeros(shape)      # near-surface facet growth, 0..1
    buried = np.zeros(shape)     # strength of buried weak layer, 0..1
    load = np.zeros(shape)       # snow load on top of buried layer
    melt_since = np.zeros(shape)
    bond_bad = np.zeros(shape)   # new snow sitting on crust or facets
    mf = np.zeros(shape)         # melt-freeze cycles since the last real snowfall
    crust_below = np.zeros(shape, bool)   # a crust buried under recent dry snow

    out = {k: np.zeros((NDAYS,) + shape) for k in PROBLEMS + ["ice", "swe", "ft", "corn"]}
    out["snowfall"] = np.zeros(NB)
    for d in range(NDAYS):
        Tm = wx["Tm"][d] + dz + 0 * swe
        Tmax = wx["Tmax"][d] + dz + 0 * swe
        Tmin = wx["Tmin"][d] + dz + 0 * swe
        cf = 1.0 - q.cloud_block * wx["cloud"][d]
        P = wx["P"][d] * pfac
        if P.max() > 0:
            frac = np.clip((BANDS_M[:, None] - (wx["SL"][d] - q.snow_ramp_below_m)) / q.snow_ramp_m, 0, 1)
        else:
            frac = np.zeros((NB, 1))
        snow = (P * frac) + 0 * swe
        rain = (P * (1 - frac)) + 0 * swe

        # snowfall
        landing_bad = (snow > q.snow_event_mm) & (new < q.bare_new_mm) & (crust | (facet > q.facet_weak)) \
            & (swe > q.crust_min_swe_mm)
        bond_bad = np.where(landing_bad, 1.0, bond_bad)
        bury = (snow >= q.bury_mm) & (facet > q.facet_weak) & (swe > q.crust_min_swe_mm)
        buried = np.where(bury, np.maximum(buried, facet), buried)
        load = np.where(bury & (load == 0), 0.0, load)
        melt_since = np.where(bury, 0.0, melt_since)
        facet = np.where(bury, q.facet_after_bury, facet)
        swe += snow
        out["snowfall"] += snow[:, 0]
        new += snow
        dry += snow
        load += np.where(buried > q.buried_min, snow, 0.0)
        age = np.where(snow > q.snow_event_mm, 0.0, age + 1)
        crust_below = np.where((snow > q.snow_event_mm) & crust & (swe > q.crust_min_swe_mm), True, crust_below)
        mf = np.where(snow > q.snow_event_mm, 0.0, mf)
        crust = np.where(snow > q.snow_event_mm, False, crust)

        # wind transport
        w = wx["wind"][d]
        lee = np.cos(asp - math.radians((wx["wdir"][d] + 180.0) % 360.0)) + 0 * swe
        strength = float(np.clip((w - q.wind_min_ms) / q.wind_span_ms, 0, q.wind_strength_cap))
        avail = np.clip(dry / q.dry_full_mm, 0, 1)
        wslab = wslab * math.exp(-1 / q.wind_slab_tau_days) + q.wind_load_rate * strength * np.clip(lee, 0, 1) \
            * avail * expo
        wslab = np.clip(wslab, 0, q.index_cap)
        scour = strength * np.clip(-lee, 0, 1) * expo
        dry *= (1 - q.scour_dry * np.clip(scour, 0, 1))
        new *= (1 - q.scour_new * np.clip(scour, 0, 1))

        # surface energy and melt
        has = swe > q.has_snow_mm
        alb = q.albedo_fresh - q.albedo_drop * (1 - np.exp(-age / q.albedo_tau_days))
        e_mid = (1 - alb) * gpeak[d][None, :] * cf - q.mid_loss_wm2 + q.mid_sens_wm2_per_c * Tmax
        e_day = (1 - alb) * gmean[d][None, :] * cf - q.day_loss_wm2 + q.day_sens_wm2_per_c * Tm
        melt = np.where(has, np.clip(e_day, 0, None) * q.melt_mm_per_wm2_day, 0.0)
        melt = np.minimum(melt, swe)
        wetted = has & ((e_mid > 0) | (rain > q.rain_wet_mm))
        swe -= melt
        melt_since += melt + rain

        # wet problem
        water = melt + rain
        loose = q.loose_base + q.loose_new * np.clip(new / q.wet_new_full_mm, 0, 1)
        wet = np.clip(water / q.wet_water_full_mm, 0, 1) * loose
        wet = np.maximum(wet, q.wet_new_weight * np.clip(new / q.wet_new_full_mm, 0, 1) * (e_mid > q.wet_new_sun_wm2))
        # snow that has been through several melt-freeze cycles is coarse and drains well,
        # so the same melt gives less wet-avalanche hazard, unless it stops refreezing at night
        wet = np.where((mf >= q.corn_cycles) & (Tmin <= 0), wet * q.corn_wet_factor, wet)
        wet = np.where(Tmin > 0, wet * q.no_refreeze_factor, wet)
        wet = np.where(swe > q.problem_min_swe_mm, np.clip(wet, 0, q.index_cap), 0.0)

        # storm slab
        storm = np.clip(new / q.storm_full_mm, 0, q.index_cap) * (1 + q.bad_bond_boost * bond_bad)
        storm = np.where(wetted & (snow < q.dry_day_snow_mm), storm * q.storm_wet_factor, storm)
        storm = np.clip(storm, 0, q.index_cap)

        # persistent slab
        depth_cm = swe / q.swe_per_cm
        grow = (~wetted) & has & (snow < q.dry_day_snow_mm)
        facet += np.where(grow, q.facet_rate_per_day * np.clip((-Tmin - q.facet_min_cold_c) / q.facet_cold_span_c, 0, 1)
                          * np.clip((q.facet_max_depth_cm - depth_cm) / q.facet_depth_span_cm, 0, 1), 0.0)
        # facets also grow next to a buried crust under thin, cold, dry snow
        near_crust = crust_below & grow & (new < q.crust_facet_max_new_mm) & (Tmin < q.crust_facet_cold_c)
        buried = np.where(near_crust, np.minimum(buried + q.crust_facet_rate, 1.0), buried)
        load = np.where(near_crust & (load == 0), new, load)
        crust_below = np.where(wetted, False, crust_below)
        facet = np.where(wetted, facet * q.facet_wet_factor, facet)
        facet = np.clip(facet, 0, 1)
        buried *= math.exp(-1 / q.buried_tau_days)
        buried = np.where((melt_since > q.buried_melt_mm) | (rain > q.buried_rain_mm),
                          buried * q.buried_heal_factor, buried)
        pers = buried * np.clip(load / q.pers_load_full_mm, 0, q.index_cap)
        pers = np.where(swe > q.problem_min_swe_mm, pers, 0.0)
        load = np.where(buried < q.buried_min, 0.0, load)

        # settle and age the new snow
        tau = np.where(Tm < q.settle_cold_c, q.settle_tau_cold_days, q.settle_tau_days)
        new *= np.exp(-1 / tau)
        dry *= np.exp(-1 / tau)
        dry = np.where(wetted, 0.0, dry)
        wslab = np.where(wetted & (snow < q.dry_day_snow_mm), wslab * q.wind_slab_wet_factor, wslab)
        bond_bad = np.where(new < q.bond_reset_mm, 0.0, bond_bad)

        # refreeze: crust and hard-ice surface
        cycle = wetted & (Tmin < q.refreeze_c) & (swe > q.crust_min_swe_mm)   # thawed by day, refrozen at night
        mf = mf + cycle
        crust = np.where(cycle, True, crust)
        crust = crust & (swe > q.crust_min_swe_mm)
        bare = new < q.bare_new_mm
        ice = np.where(crust & bare, np.where(e_mid > 0, q.ice_morning_only, 1.0), 0.0)
        ice = np.where((rain > q.ice_rain_mm) & (Tmin < q.refreeze_c) & (swe > q.crust_min_swe_mm) & bare, 1.0, ice)

        out["storm"][d] = storm
        out["wind"][d] = np.where(swe > q.problem_min_swe_mm, wslab, 0.0)
        out["wet"][d] = wet
        out["persistent"][d] = pers
        out["ice"][d] = ice
        out["ft"][d] = cycle
        out["corn"][d] = crust & bare & (e_mid > q.corn_sun_wm2) & (mf >= q.corn_cycles) & (Tmin < q.refreeze_c) \
            & (snow < q.dry_day_snow_mm) & (rain < q.dry_day_rain_mm)
        out["swe"][d] = swe
    return out
