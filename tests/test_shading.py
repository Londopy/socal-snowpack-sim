import numpy as np

from socal_snowpack.grid import BAND_EDGES_M
from socal_snowpack.shading import horizon_by_zone

RES = 16.0


def north_wall():
    """Flat valley floor at 2,100 m to the north, a 35-degree north-facing slope up to 2,800 m, flat on top."""
    rows = np.arange(240)
    rise = np.tan(np.radians(35.0)) * RES
    z = np.clip(2100.0 + (rows - 100) * rise, 2100.0, 2800.0)
    dem = np.repeat(z[:, None], 160, axis=1)
    on_slope = (z > 2100.0) & (z < 2800.0)
    slope = np.repeat(np.where(on_slope, 35.0, 0.0)[:, None], 160, axis=1)
    aspect = np.zeros_like(dem)
    return dem, slope, aspect


def test_foot_of_a_north_wall_sees_a_high_south_horizon():
    h = horizon_by_zone(*north_wall(), RES, BAND_EDGES_M)
    assert h.shape == (5, 8, 36)
    assert h[0, 0, 18] > 30          # looking south, up the wall
    assert h[0, 0, 0] < 5            # looking north over the valley


def test_bands_the_dem_never_reaches_are_nan():
    h = horizon_by_zone(*north_wall(), RES, BAND_EDGES_M)
    assert np.isnan(h[3:]).all()
    assert np.isnan(h[0, 4]).all()   # no south-facing cells at all
