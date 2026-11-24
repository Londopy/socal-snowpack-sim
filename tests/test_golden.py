import os

import numpy as np

from socal_snowpack import daily, solar, weather
from socal_snowpack.params import load_params

GOLDEN = os.path.join(os.path.dirname(__file__), "golden", "daily_seed7.npz")


def test_daily_matches_golden():
    p = load_params()
    ref = np.load(GOLDEN)
    rng = np.random.default_rng(7)
    gmean, gpeak = solar.solar_tables(p)
    for i in range(3):
        out = daily.run_season(weather.make_season(rng, p), gmean, gpeak, p)
        for k, v in out.items():
            assert np.array_equal(v, ref[f"s{i}_{k}"]), f"season {i} key {k} drifted"
