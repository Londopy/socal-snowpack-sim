"""The hourly model has to reproduce the daily model's findings over the same simulated winters."""
import time

import numpy as np
import pytest

from socal_snowpack import daily, solar, weather
from socal_snowpack.forcing import hourly_from_daily
from socal_snowpack.grid import HIGH_B, MID, NB, NDAYS, PROBLEMS
from socal_snowpack.params import load_params
from socal_snowpack.season import run_hourly_seasons
from socal_snowpack.state import empty_state
from socal_snowpack.step import step

P = load_params()
N_SEASONS = 30
N, NE, SE, S, SW = 0, 1, 3, 4, 5
ELEVATED = P.levels.considerable


@pytest.fixture(scope="module")
def runs():
    rng = np.random.default_rng(7)
    wxs = [weather.make_season(rng, P) for _ in range(N_SEASONS)]
    gmean, gpeak = solar.solar_tables(P)
    old = [daily.run_season(wx, gmean, gpeak, P) for wx in wxs]
    old = {k: np.stack([o[k] for o in old]) for k in old[0]}
    new = run_hourly_seasons(wxs, P)
    return wxs, old, new


def days(o, k):
    return (o[k] >= ELEVATED).sum(axis=1).mean(axis=0)


def test_output_shapes(runs):
    _, _, new = runs
    assert new["storm"].shape == (N_SEASONS, NDAYS, NB, 8)
    assert new["surface_hourly"].shape == (N_SEASONS, NDAYS, 24, NB, 8)
    assert new["snowfall"].shape == (N_SEASONS, NB)


def test_storm_slab_days_by_band(runs):
    _, old, new = runs
    for band in (MID, HIGH_B):
        a, b = days(old, "storm")[band].mean(), days(new, "storm")[band].mean()
        assert abs(b - a) <= 0.35 * a, (band, a, b)


def test_sun_slopes_wetter(runs):
    _, _, new = runs
    snow = (new["swe"] > 20).sum(axis=1).mean(axis=0)
    share = days(new, "wet") / np.maximum(snow, 1)
    assert share[MID, S] > share[MID, N]


def test_wind_slab_is_lee(runs):
    _, _, new = runs
    w = days(new, "wind")[3]
    assert w[NE] > 0
    assert w[NE] >= 5 * w[SW]


def test_persistent_stays_shaded(runs):
    _, _, new = runs
    assert (days(new, "persistent")[:, [SE, S, SW]] < 0.2).all()


def after_storm(wxs, o):
    idx = np.stack([o[k] for k in PROBLEMS]).max(axis=0)
    total, n = np.zeros(8), 0
    for i, wx in enumerate(wxs):
        st = wx["storm"]
        for d in range(NDAYS - 8):
            if st[d] and not st[d + 1] and wx["P"][d] > 14 and wx["SL"][d] < 2700 and not st[d + 1:d + 8].any():
                total += idx[i, d:d + 8, HIGH_B, N]
                n += 1
    return total / n


def test_storms_fade_in_days(runs):
    wxs, _, new = runs
    curve = after_storm(wxs, new)
    assert curve[0] >= ELEVATED
    assert curve[3] < ELEVATED


def test_freeze_thaw_south_over_north(runs):
    _, _, new = runs
    snow = (new["swe"] > 20).sum(axis=1).mean(axis=0)
    share = new["ft"].sum(axis=1).mean(axis=0) / np.maximum(snow, 1)
    assert share[MID, S] > 1.5 * share[MID, N]


def test_step_is_fast():
    rng = np.random.default_rng(1)
    wx = weather.make_season(rng, P)
    s = empty_state((34,), P)
    forcings = [f for d in range(10) for f in hourly_from_daily(wx, d, P)]
    times = []
    for f in forcings[:200]:
        t0 = time.perf_counter()
        s, _ = step(s, f, P)
        times.append(time.perf_counter() - t0)
    assert np.median(times) < 0.020


def test_persistent_shows_up_high_and_shaded(runs):
    _, _, new = runs
    assert days(new, "persistent")[4, N] > 0.5


def test_corn_on_sunny_slopes(runs):
    _, _, new = runs
    snow = (new["swe"] > 20).sum(axis=1).mean(axis=0)
    corn = new["corn"].sum(axis=1).mean(axis=0) / np.maximum(snow, 1)
    assert corn[MID, S] > corn[MID, N]
