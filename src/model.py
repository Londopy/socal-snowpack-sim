"""Simulated SoCal winter weather driving a simple snowpack hazard model.

This is a TOY MODEL for learning. The weather is randomly generated from
rough SoCal-like statistics, and the snowpack rules are simplified textbook
relationships. Nothing here is calibrated against measurements, and it is
not an avalanche forecast.

Grid: 8 aspects x 5 elevation bands, all on a 38-degree slope.
Daily time step, 15 Nov to 30 Apr. The same weather is applied to every
range; only aspect and elevation differ.

Usage:  python src/model.py        (writes results/model.json and data/model.npz)
"""
import json
import math
import os

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAT = 34.28
SLOPE = 38.0
ASPECTS = np.arange(0, 360, 45.0)                      # N, NE, E, SE, S, SW, W, NW
ASP_NAMES = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
BAND_EDGES_M = np.array([2000.0, 2300.0, 2600.0, 2900.0, 3200.0, 3510.0])
BANDS_M = (BAND_EDGES_M[:-1] + BAND_EDGES_M[1:]) / 2.0  # band mid elevations
BAND_NAMES = ["%s-%s ft" % (format(int(round(a * 3.28084, -2)), ","), format(int(round(b * 3.28084, -2)), ","))
              for a, b in zip(BAND_EDGES_M[:-1], BAND_EDGES_M[1:])]
NB = len(BANDS_M)
MID = 2      # 8,500-9,500 ft band, used for the summary statistics
HIGH_B = 3   # 9,500-10,500 ft band
Z_REF = 2600.0
LAPSE = 0.0065
START_DOY = 319                                        # 15 Nov
NDAYS = 167                                            # to 30 Apr
PROBLEMS = ["storm", "wind", "wet", "persistent"]
CONSIDERABLE = 0.45
HIGH = 0.75


# ---------------------------------------------------------------- solar ----
def solar_tables():
    """Clear-sky daily-mean and sunniest-3-hour irradiance (W/m2) on a 38-degree
    slope for each aspect and each day of the season. No terrain shading."""
    lat = math.radians(LAT)
    sl = math.radians(SLOPE)
    mean = np.zeros((NDAYS, 8))
    peak = np.zeros((NDAYS, 8))
    hours = np.arange(0, 24, 1 / 6.0)
    for d in range(NDAYS):
        doy = (START_DOY + d - 1) % 365 + 1
        dec = math.radians(23.44) * math.sin(2 * math.pi * (284 + doy) / 365.0)
        ha = np.radians(15.0 * (hours - 12.0))
        sin_el = math.sin(lat) * math.sin(dec) + math.cos(lat) * math.cos(dec) * np.cos(ha)
        el = np.arcsin(np.clip(sin_el, -1, 1))
        up = sin_el > 0.02
        az = np.arctan2(-np.cos(dec) * np.sin(ha),
                        np.sin(dec) * math.cos(lat) - np.cos(dec) * np.cos(ha) * math.sin(lat))
        am = 1.0 / np.maximum(sin_el, 0.02)
        direct = 1353.0 * 0.7 ** (am ** 0.678) * up          # Meinel clear-sky direct beam
        diffuse = 0.1 * direct * np.maximum(sin_el, 0) + 15.0 * up
        for a, asp in enumerate(np.radians(ASPECTS)):
            cos_i = np.cos(el) * math.sin(sl) * np.cos(az - asp) + sin_el * math.cos(sl)
            g = direct * np.maximum(cos_i, 0) + diffuse
            mean[d, a] = g.mean()
            peak[d, a] = np.sort(g)[-18:].mean()      # mean of the sunniest 3 hours
    return mean, peak


# -------------------------------------------------------------- weather ----
STORMS_PER_MONTH = {11: 0.8, 12: 1.5, 1: 2.0, 2: 2.1, 3: 1.6, 4: 0.7}


def month_of(d):
    doy = (START_DOY + d - 1) % 365 + 1
    edges = [(31, 1), (59, 2), (90, 3), (120, 4), (151, 5), (181, 6), (212, 7),
             (243, 8), (273, 9), (304, 10), (334, 11), (365, 12)]
    for e, m in edges:
        if doy <= e:
            return m
    return 12


def make_season(rng):
    """One random SoCal-style winter at the 2,600 m reference level."""
    wet = rng.lognormal(mean=-0.45, sigma=0.6)       # big year-to-year swings
    P = np.zeros(NDAYS)          # precip, mm water
    SL = np.full(NDAYS, np.nan)  # snow level, m
    wind = np.zeros(NDAYS)       # ridge wind, m/s
    wdir = np.zeros(NDAYS)       # direction wind comes FROM, deg
    cloud = np.zeros(NDAYS)
    storm = np.zeros(NDAYS, bool)
    santa = np.zeros(NDAYS, bool)
    d = 0
    while d < NDAYS:
        rate = STORMS_PER_MONTH[month_of(d)] * wet / 30.0
        if rng.random() < rate:
            dur = int(rng.choice([1, 2, 3, 4], p=[0.35, 0.35, 0.2, 0.1]))
            warm = rng.random() < 0.25                       # atmospheric-river type
            sl0 = rng.normal(2550, 300) if warm else rng.normal(1750, 380)
            size = rng.gamma(1.6, 26.0 if warm else 16.0)
            sdir = rng.normal(215, 30)                       # S to W flow
            for k in range(dur):
                if d + k >= NDAYS:
                    break
                storm[d + k] = True
                P[d + k] = size * rng.uniform(0.5, 1.4)
                SL[d + k] = sl0 - 180.0 * k + rng.normal(0, 80)   # cools as front passes
                wind[d + k] = rng.gamma(4.0, 3.2)
                wdir[d + k] = (sdir + 25.0 * k + rng.normal(0, 15)) % 360   # veers W/NW
                cloud[d + k] = 0.85
            d += dur
            # post-frontal north wind day, sometimes
            if d < NDAYS and rng.random() < 0.5:
                wind[d] = rng.gamma(4.0, 2.8)
                wdir[d] = rng.normal(340, 25) % 360
            d += 1
        else:
            d += 1
    # Santa Ana events on non-storm days
    d = 0
    while d < NDAYS:
        if not storm[d] and rng.random() < 0.045:
            dur = int(rng.integers(1, 4))
            for k in range(dur):
                if d + k < NDAYS and not storm[d + k]:
                    santa[d + k] = True
                    wind[d + k] = rng.gamma(5.0, 3.6)
                    wdir[d + k] = rng.normal(40, 20) % 360
            d += dur
        d += 1
    # background wind on the remaining days
    calm = wind == 0
    wind[calm] = rng.gamma(2.0, 2.2, calm.sum())
    wdir[calm] = rng.uniform(0, 360, calm.sum())
    # temperature at 2,600 m
    t = np.arange(NDAYS)
    clim = 3.2 - 2.2 * np.cos(2 * np.pi * (t - 62) / 365.0)   # coldest early-mid Jan
    anom = np.zeros(NDAYS)
    for i in range(1, NDAYS):
        anom[i] = 0.72 * anom[i - 1] + rng.normal(0, 2.3)
    Tm = clim + anom + 2.0 * santa
    st = storm & ~np.isnan(SL)
    Tm[st] = (SL[st] - Z_REF) * LAPSE + 1.0                   # snow level sits near +1 C
    half = np.where(storm, 2.0, 4.0)
    return dict(P=P, SL=SL, wind=wind, wdir=wdir, cloud=cloud, storm=storm, santa=santa,
                Tm=Tm, Tmax=Tm + half, Tmin=Tm - half, wet=wet)


# ------------------------------------------------------------- snowpack ----
def run_season(wx, gmean, gpeak):
    shape = (NB, 8)                                       # band, aspect
    dz = (Z_REF - BANDS_M)[:, None] * LAPSE               # temp offset per band
    pfac = np.clip(0.85 + 0.25 * (BANDS_M - 2300.0) / 650.0, 0.75, 1.2)[:, None]   # more precip up high
    expo = np.clip(0.6 + 0.4 * (BANDS_M - 2300.0) / 650.0, 0.45, 1.1)[:, None]     # wind exposure
    asp = np.radians(ASPECTS)[None, :]

    swe = np.zeros(shape)        # total snow water, mm
    new = np.zeros(shape)        # recent storm snow, mm water
    dry = np.zeros(shape)        # recent snow still dry and movable by wind
    age = np.full(shape, 30.0)   # days since last real snowfall (albedo)
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
        cf = 1.0 - 0.7 * wx["cloud"][d]
        P = wx["P"][d] * pfac
        if P.max() > 0:
            frac = np.clip((BANDS_M[:, None] - (wx["SL"][d] - 150.0)) / 300.0, 0, 1)
        else:
            frac = np.zeros((NB, 1))
        snow = (P * frac) + 0 * swe
        rain = (P * (1 - frac)) + 0 * swe

        # --- snowfall
        landing_bad = (snow > 5) & (new < 5) & (crust | (facet > 0.3)) & (swe > 10)
        bond_bad = np.where(landing_bad, 1.0, bond_bad)
        bury = (snow >= 12) & (facet > 0.3) & (swe > 10)
        buried = np.where(bury, np.maximum(buried, facet), buried)
        load = np.where(bury & (load == 0), 0.0, load)
        melt_since = np.where(bury, 0.0, melt_since)
        facet = np.where(bury, 0.1, facet)
        swe += snow
        out["snowfall"] += snow[:, 0]
        new += snow
        dry += snow
        load += np.where(buried > 0.05, snow, 0.0)
        age = np.where(snow > 5, 0.0, age + 1)
        crust_below = np.where((snow > 5) & crust & (swe > 10), True, crust_below)
        mf = np.where(snow > 5, 0.0, mf)
        crust = np.where(snow > 5, False, crust)

        # --- wind transport
        w = wx["wind"][d]
        lee = np.cos(asp - math.radians((wx["wdir"][d] + 180.0) % 360.0)) + 0 * swe
        strength = float(np.clip((w - 7.0) / 10.0, 0, 1.5))
        avail = np.clip(dry / 15.0, 0, 1)
        wslab = wslab * math.exp(-1 / 2.5) + 0.8 * strength * np.clip(lee, 0, 1) * avail * expo
        wslab = np.clip(wslab, 0, 1.2)
        scour = strength * np.clip(-lee, 0, 1) * expo
        dry *= (1 - 0.5 * np.clip(scour, 0, 1))
        new *= (1 - 0.3 * np.clip(scour, 0, 1))

        # --- surface energy and melt
        has = swe > 1
        alb = 0.85 - 0.35 * (1 - np.exp(-age / 5.0))
        e_mid = (1 - alb) * gpeak[d][None, :] * cf - 90.0 + 8.0 * Tmax    # midday W/m2
        e_day = (1 - alb) * gmean[d][None, :] * cf - 70.0 + 10.0 * Tm      # daily mean W/m2
        melt = np.where(has, np.clip(e_day, 0, None) * 0.259, 0.0)
        melt = np.minimum(melt, swe)
        wetted = has & ((e_mid > 0) | (rain > 1))
        swe -= melt
        melt_since += melt + rain

        # --- wet problem
        water = melt + rain
        loose = 0.4 + 0.6 * np.clip(new / 20.0, 0, 1)
        wet = np.clip(water / 15.0, 0, 1) * loose
        wet = np.maximum(wet, 0.6 * np.clip(new / 20.0, 0, 1) * (e_mid > 20))
        # snow that has been through several melt-freeze cycles is coarse and drains well,
        # so the same melt gives less wet-avalanche hazard, unless it stops refreezing at night
        wet = np.where((mf >= 3) & (Tmin <= 0), wet * 0.6, wet)
        wet = np.where(Tmin > 0, wet * 1.5, wet)             # no overnight refreeze
        wet = np.where(swe > 20, np.clip(wet, 0, 1.2), 0.0)

        # --- storm slab
        storm = np.clip(new / 35.0, 0, 1.2) * (1 + 0.3 * bond_bad)
        storm = np.where(wetted & (snow < 1), storm * 0.5, storm)
        storm = np.clip(storm, 0, 1.2)

        # --- persistent slab
        depth_cm = swe / 3.0
        grow = (~wetted) & has & (snow < 1)
        facet += np.where(grow, 0.12 * np.clip((-Tmin - 4) / 6.0, 0, 1)
                          * np.clip((80 - depth_cm) / 60.0, 0, 1), 0.0)
        # facets also grow next to a buried crust under thin, cold, dry snow
        near_crust = crust_below & grow & (new < 25) & (Tmin < -6)
        buried = np.where(near_crust, np.minimum(buried + 0.06, 1.0), buried)
        load = np.where(near_crust & (load == 0), new, load)
        crust_below = np.where(wetted, False, crust_below)
        facet = np.where(wetted, facet * 0.5, facet)
        facet = np.clip(facet, 0, 1)
        buried *= math.exp(-1 / 12.0)
        buried = np.where((melt_since > 30) | (rain > 10), buried * 0.5, buried)
        pers = buried * np.clip(load / 30.0, 0, 1.2)
        pers = np.where(swe > 20, pers, 0.0)
        load = np.where(buried < 0.05, 0.0, load)

        # --- settle / age the new snow
        tau = np.where(Tm < -3, 2.0, 1.2)
        new *= np.exp(-1 / tau)
        dry *= np.exp(-1 / tau)
        dry = np.where(wetted, 0.0, dry)
        wslab = np.where(wetted & (snow < 1), wslab * 0.6, wslab)
        bond_bad = np.where(new < 3, 0.0, bond_bad)

        # --- refreeze: crust and hard-ice surface
        cycle = wetted & (Tmin < -1) & (swe > 10)            # thawed by day, refrozen at night
        mf = mf + cycle
        crust = np.where(cycle, True, crust)
        crust = crust & (swe > 10)
        bare = new < 5
        ice = np.where(crust & bare, np.where(e_mid > 0, 0.5, 1.0), 0.0)
        ice = np.where((rain > 5) & (Tmin < -1) & (swe > 10) & bare, 1.0, ice)

        out["storm"][d] = storm
        out["wind"][d] = np.where(swe > 20, wslab, 0.0)
        out["wet"][d] = wet
        out["persistent"][d] = pers
        out["ice"][d] = ice
        out["ft"][d] = cycle
        out["corn"][d] = crust & bare & (e_mid > 20) & (mf >= 3) & (Tmin < -1) & (snow < 1) & (rain < 1)
        out["swe"][d] = swe
    return out


# ---------------------------------------------------------------- driver ----
def main(n_seasons=400, seed=7):
    rng = np.random.default_rng(seed)
    gmean, gpeak = solar_tables()
    days = {k: np.zeros((NB, 8)) for k in PROBLEMS + ["any", "high", "ice", "ice_allday", "ft", "corn", "snow"]}
    monthly = {m: {k: 0.0 for k in PROBLEMS + ["any", "ice", "snow"]} for m in [11, 12, 1, 2, 3, 4]}
    months = np.array([month_of(d) for d in range(NDAYS)])
    after_storm = {"N": np.zeros(8), "S": np.zeros(8), "n": np.zeros(8)}
    season_any = []
    cands = []
    wets = []
    peak_swe = []
    snowfall = []
    for s in range(n_seasons):
        wx = make_season(rng)
        o = run_season(wx, gmean, gpeak)
        stack = np.stack([o[k] for k in PROBLEMS])
        idx = stack.max(axis=0)
        snow = o["swe"] > 20
        for i, k in enumerate(PROBLEMS):
            days[k] += (stack[i] >= CONSIDERABLE).sum(axis=0)
        days["any"] += (idx >= CONSIDERABLE).sum(axis=0)
        days["high"] += (idx >= HIGH).sum(axis=0)
        days["ice"] += (o["ice"] >= 0.5).sum(axis=0)
        days["ice_allday"] += (o["ice"] >= 1.0).sum(axis=0)
        days["snow"] += snow.sum(axis=0)
        days["ft"] += o["ft"].sum(axis=0)
        days["corn"] += o["corn"].sum(axis=0)
        for m in monthly:
            sel = months == m
            for i, k in enumerate(PROBLEMS):
                monthly[m][k] += (stack[i][sel, MID] >= CONSIDERABLE).mean(axis=1).sum()
            monthly[m]["any"] += (idx[sel, MID] >= CONSIDERABLE).mean(axis=1).sum()
            monthly[m]["ice"] += (o["ice"][sel, MID] >= 0.5).mean(axis=1).sum()
            monthly[m]["snow"] += snow[sel, MID].mean(axis=1).sum()
        # hazard decay after the last day of each storm (upper band)
        st = wx["storm"]
        for d in range(NDAYS - 8):
            if st[d] and not st[d + 1] and wx["P"][d] > 14 and wx["SL"][d] < 2700:
                if not st[d + 1:d + 8].any():
                    after_storm["N"] += idx[d:d + 8, HIGH_B, 0]
                    after_storm["S"] += idx[d:d + 8, HIGH_B, 4]
                    after_storm["n"] += 1
        season_any.append((idx[:, MID, :] >= CONSIDERABLE).any(axis=1).sum())
        wets.append(wx["wet"])
        peak_swe.append(o["swe"][:, MID, 0].max())
        snowfall.append(o["snowfall"])
        if s < 40:
            cands.append((o["snowfall"][MID], dict(
                wx={k: np.asarray(v) for k, v in wx.items() if k != "wet"},
                out={k: v for k, v in o.items() if k != "snowfall"})))

    n = float(n_seasons)
    target = np.mean([c[0] for c in cands])          # a roughly average winter
    example = min(cands, key=lambda c: abs(c[0] - target))[1]
    res = {
        "n_seasons": n_seasons,
        "aspects": ASP_NAMES, "bands": BAND_NAMES, "band_edges_m": BAND_EDGES_M.tolist(),
        "summary_band": BAND_NAMES[MID], "high_band": BAND_NAMES[HIGH_B],
        "days": {k: (v / n).round(2).tolist() for k, v in days.items()},
        "wet_share_of_snow_days_pct": (100 * days["wet"] / np.maximum(days["snow"], 1)).round(0).tolist(),
        "ice_share_of_snow_days_pct": (100 * days["ice"] / np.maximum(days["snow"], 1)).round(0).tolist(),
        "monthly": {str(m): {k: round(float(v) / n, 2) for k, v in d.items()} for m, d in monthly.items()},
        "after_storm": {"N": (after_storm["N"] / after_storm["n"]).round(3).tolist(),
                        "S": (after_storm["S"] / after_storm["n"]).round(3).tolist()},
        "season_any_days": {"p10": float(np.percentile(season_any, 10)),
                            "median": float(np.median(season_any)),
                            "p90": float(np.percentile(season_any, 90))},
        "snowfall_mm_water_by_band": {"mean": np.mean(snowfall, axis=0).round(0).tolist(),
                                      "p10": np.percentile(snowfall, 10, axis=0).round(0).tolist(),
                                      "p50": np.percentile(snowfall, 50, axis=0).round(0).tolist(),
                                      "p90": np.percentile(snowfall, 90, axis=0).round(0).tolist()},
        "peak_swe_mm_north_summary_band": {"p10": float(np.percentile(peak_swe, 10)),
                              "median": float(np.median(peak_swe)),
                              "p90": float(np.percentile(peak_swe, 90))},
    }
    os.makedirs(os.path.join(ROOT, "results"), exist_ok=True)
    os.makedirs(os.path.join(ROOT, "data"), exist_ok=True)
    with open(os.path.join(ROOT, "results", "model.json"), "w") as f:
        json.dump(res, f, indent=1)
    np.savez_compressed(os.path.join(ROOT, "data", "model.npz"),
                        **{"ex_" + k: v for k, v in example["out"].items()},
                        **{"wx_" + k: v for k, v in example["wx"].items()},
                        **{"days_" + k: v / n for k, v in days.items()})
    return res


if __name__ == "__main__":
    r = main()
    print(json.dumps({k: r[k] for k in ["season_any_days", "snowfall_mm_water_by_band", "peak_swe_mm_north_summary_band", "after_storm"]}, indent=1))
    for k in PROBLEMS + ["any", "high", "ice", "ice_allday", "ft", "corn", "snow"]:
        print(k)
        for b in range(NB - 1, -1, -1):
            print("  ", BAND_NAMES[b].ljust(20), " ".join(f"{v:5.1f}" for v in r["days"][k][b]))
    print("      aspects:         ", "     ".join(ASP_NAMES))
    for m, v in r["monthly"].items():
        print(m, v)
