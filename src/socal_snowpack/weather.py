"""Random SoCal-style winters for the simulator. Not fitted to station records."""
import numpy as np

from .grid import LAPSE, NDAYS, START_DOY, Z_REF


def month_of(d):
    doy = (START_DOY + d - 1) % 365 + 1
    edges = [(31, 1), (59, 2), (90, 3), (120, 4), (151, 5), (181, 6), (212, 7),
             (243, 8), (273, 9), (304, 10), (334, 11), (365, 12)]
    for e, m in edges:
        if doy <= e:
            return m
    return 12


def make_season(rng, p):
    """One random SoCal-style winter at the 2,600 m reference level."""
    w = p.weather
    wet = rng.lognormal(mean=w.wet_year_mu, sigma=w.wet_year_sigma)
    P = np.zeros(NDAYS)          # precip, mm water
    SL = np.full(NDAYS, np.nan)  # snow level, m
    wind = np.zeros(NDAYS)       # ridge wind, m/s
    wdir = np.zeros(NDAYS)       # direction wind comes FROM, deg
    cloud = np.zeros(NDAYS)
    storm = np.zeros(NDAYS, bool)
    santa = np.zeros(NDAYS, bool)
    d = 0
    while d < NDAYS:
        rate = w.storms_per_month[str(month_of(d))] * wet / 30.0
        if rng.random() < rate:
            dur = int(rng.choice(w.storm_days, p=w.storm_days_p))
            warm = rng.random() < w.warm_storm_p
            sl0 = (rng.normal(w.warm_snow_level_m, w.warm_snow_level_sd_m) if warm
                   else rng.normal(w.cold_snow_level_m, w.cold_snow_level_sd_m))
            size = rng.gamma(w.storm_size_shape, w.warm_storm_size_mm if warm else w.cold_storm_size_mm)
            sdir = rng.normal(w.storm_dir_deg, w.storm_dir_sd_deg)
            for k in range(dur):
                if d + k >= NDAYS:
                    break
                storm[d + k] = True
                P[d + k] = size * rng.uniform(w.storm_day_min, w.storm_day_max)
                SL[d + k] = sl0 - w.snow_level_drop_m_per_day * k + rng.normal(0, w.snow_level_sd_m)
                wind[d + k] = rng.gamma(w.storm_wind_shape, w.storm_wind_scale)
                wdir[d + k] = (sdir + w.storm_veer_deg_per_day * k + rng.normal(0, w.storm_veer_sd_deg)) % 360
                cloud[d + k] = w.storm_cloud
            d += dur
            if d < NDAYS and rng.random() < w.post_front_p:
                wind[d] = rng.gamma(w.post_front_wind_shape, w.post_front_wind_scale)
                wdir[d] = rng.normal(w.post_front_dir_deg, w.post_front_dir_sd_deg) % 360
            d += 1
        else:
            d += 1
    d = 0
    while d < NDAYS:
        if not storm[d] and rng.random() < w.santa_ana_p:
            dur = int(rng.integers(w.santa_ana_min_days, w.santa_ana_max_days))
            for k in range(dur):
                if d + k < NDAYS and not storm[d + k]:
                    santa[d + k] = True
                    wind[d + k] = rng.gamma(w.santa_ana_wind_shape, w.santa_ana_wind_scale)
                    wdir[d + k] = rng.normal(w.santa_ana_dir_deg, w.santa_ana_dir_sd_deg) % 360
            d += dur
        d += 1
    calm = wind == 0
    wind[calm] = rng.gamma(w.calm_wind_shape, w.calm_wind_scale, calm.sum())
    wdir[calm] = rng.uniform(0, 360, calm.sum())
    t = np.arange(NDAYS)
    clim = w.clim_mean_c - w.clim_amp_c * np.cos(2 * np.pi * (t - w.clim_coldest_day) / 365.0)
    anom = np.zeros(NDAYS)
    for i in range(1, NDAYS):
        anom[i] = w.anom_persist * anom[i - 1] + rng.normal(0, w.anom_sd_c)
    Tm = clim + anom + w.santa_ana_warm_c * santa
    st = storm & ~np.isnan(SL)
    Tm[st] = (SL[st] - Z_REF) * LAPSE + w.snow_level_temp_c
    half = np.where(storm, w.storm_half_range_c, w.clear_half_range_c)
    return dict(P=P, SL=SL, wind=wind, wdir=wdir, cloud=cloud, storm=storm, santa=santa,
                Tm=Tm, Tmax=Tm + half, Tmin=Tm - half, wet=wet)
