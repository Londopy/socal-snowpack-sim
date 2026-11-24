import numpy as np

from socal_snowpack.grid import NB, START_DOY
from socal_snowpack.params import load_params
from socal_snowpack.solar import hourly_irradiance, solar_tables, sun_position

P = load_params()


def test_hourly_mean_matches_daily_tables():
    d = 60
    doy = (START_DOY + d - 1) % 365 + 1
    daily_mean = solar_tables(P)[0][d]
    hourly = np.array([hourly_irradiance(doy, h, P) for h in range(24)])
    np.testing.assert_allclose(hourly.mean(axis=0), daily_mean, rtol=0.01)


def test_sun_is_south_and_low_at_december_noon():
    el, az = sun_position(355, 12.0, 34.28)
    assert 30 < el < 34
    assert abs(az - 180) < 1


def test_south_beats_north_at_noon_in_december():
    g = hourly_irradiance(355, 12, P)
    assert g[4] > 2 * g[0]


def test_high_south_horizon_blocks_direct_sun():
    flat = np.zeros((NB, 8, 36))
    south_wall = flat.copy()
    south_wall[..., 13:24] = 40.0          # 130 to 230 degrees
    sky = np.full((NB, 8, 36), 90.0)
    open_ = hourly_irradiance(355, 12, P, flat)
    walled = hourly_irradiance(355, 12, P, south_wall)
    diffuse_only = hourly_irradiance(355, 12, P, sky)
    np.testing.assert_allclose(open_, np.broadcast_to(hourly_irradiance(355, 12, P), open_.shape))
    np.testing.assert_allclose(walled[:, 4], diffuse_only[:, 4])
    assert (walled[:, 4] < open_[:, 4] / 2).all()


def test_nan_horizon_means_no_shading():
    h = np.full((NB, 8, 36), np.nan)
    np.testing.assert_allclose(hourly_irradiance(355, 12, P, h),
                               np.broadcast_to(hourly_irradiance(355, 12, P), (NB, 8)))


def test_horizon_with_a_peak_dimension():
    h = np.zeros((34, NB, 8, 36))
    assert hourly_irradiance(40, 10, P, h).shape == (34, NB, 8)
