import numpy as np
import pytest

from socal_snowpack.daily import band_precip_factor
from socal_snowpack.forcing import hourly_from_daily, lapse_to_bands, snow_fraction
from socal_snowpack.grid import BANDS_M, LAPSE, Z_REF
from socal_snowpack.params import load_params
from socal_snowpack.weather import make_season

P = load_params()


def test_snow_fraction_is_half_at_snow_level():
    f = snow_fraction(np.array([2500.0]), 2500.0, 0.0, 5.0, P)
    assert f[0] == pytest.approx(0.5)


def test_snow_fraction_widens_with_sd():
    band = np.array([2800.0])
    sharp = snow_fraction(band, 2500.0, 0.0, 5.0, P)[0]
    wide = snow_fraction(band, 2500.0, 400.0, 5.0, P)[0]
    assert sharp > 0.95
    assert wide < sharp


def test_no_precip_gives_zero_not_nan():
    f = snow_fraction(BANDS_M, np.nan, 0.0, 0.0, P)
    assert (f == 0).all()


def test_precip_without_a_snow_level_raises():
    with pytest.raises(ValueError, match="snow level"):
        snow_fraction(BANDS_M, np.nan, 0.0, 3.0, P)


def test_lapse():
    t = lapse_to_bands(0.0, 2000.0, np.array([2000.0, 3000.0]), LAPSE)
    np.testing.assert_allclose(t, [0.0, -6.5])


def test_hourly_from_daily_conserves_the_day():
    wx = make_season(np.random.default_rng(3), P)
    d = int(np.argmax(wx["P"]))
    hours = hourly_from_daily(wx, d, P)
    assert len(hours) == 24
    assert [f.hour for f in hours] == list(range(24))
    dz = (Z_REF - BANDS_M)[:, None] * LAPSE
    precip = sum(f.precip_mm for f in hours)
    np.testing.assert_allclose(precip, wx["P"][d] * band_precip_factor(P.daily)[:, None], rtol=1e-12)
    t = np.stack([f.t_c for f in hours])
    np.testing.assert_allclose(t.mean(axis=0), wx["Tm"][d] + dz, atol=1e-9)
    np.testing.assert_allclose(t.max(axis=0), wx["Tmax"][d] + dz, atol=1e-9)
    np.testing.assert_allclose(t.min(axis=0), wx["Tmin"][d] + dz, atol=1e-9)
