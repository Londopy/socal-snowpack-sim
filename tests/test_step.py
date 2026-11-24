import dataclasses

import numpy as np
import pytest

from socal_snowpack.forcing import Forcing
from socal_snowpack.grid import BANDS_M, LAPSE, NB
from socal_snowpack.params import load_params
from socal_snowpack.state import CRUST, add_snow, empty_state
from socal_snowpack.step import FIRM, ICE, SOFT, WET, step

P = load_params()
N, NE, SE, S, SW = 0, 1, 3, 4, 5


def hour(t_c, h=12, precip=0.0, snow_level=np.nan, wind=2.0, wind_from=0.0, cloud=0.0, doy=45, sw_down=None):
    return Forcing(t_c=np.full((NB, 1), float(t_c)) if np.ndim(t_c) == 0 else t_c,
                   precip_mm=np.full((NB, 1), precip), snow_level_m=np.asarray(snow_level),
                   snow_level_sd_m=np.asarray(0.0), wind_ms=np.asarray(wind),
                   wind_from_deg=np.asarray(wind_from), cloud=np.asarray(cloud), doy=doy, hour=h,
                   sw_down=sw_down)


def run(s, forcings):
    outs = []
    for f in forcings:
        s, o = step(s, f, P)
        outs.append(o)
    return s, outs


def old_pack(swe, hours=100):
    s = add_snow(empty_state((), P), np.full((NB, 8), float(swe)), P)
    return dataclasses.replace(s, age_h=np.where(s.swe_mm > 0, float(hours), 0.0),
                               hours_since_snow=np.full((NB, 8), float(hours)))


def crusted(s):
    return dataclasses.replace(s, kind=np.where(s.swe_mm > 0, CRUST, 0).astype(np.int8),
                               mf_cycles=np.full((NB, 8), 3.0))


def day(t_mean, half, band, **kw):
    """24 hourly forcings with a cosine temperature curve peaking at 15:00 at one band."""
    out = []
    for h in range(24):
        t = t_mean + half * np.cos(2 * np.pi * (h - 15) / 24) + (BANDS_M[band] - BANDS_M)[:, None] * LAPSE
        out.append(hour(t, h=h, **kw))
    return out


def test_storm_loads_all_aspects_then_decays():
    snowy = [hour(-8, h=h, precip=5.0, snow_level=1500.0, cloud=0.85) for h in range(6)]
    s, outs = run(empty_state((), P), snowy)
    assert (outs[-1].storm[2:] >= 0.45).all()
    clear = [hour(-8, h=(6 + i) % 24) for i in range(72)]
    _, outs = run(s, clear)
    assert outs[-1].storm[3, N] < 0.45


def test_south_softens_north_stays_frozen():
    s = crusted(old_pack(200, hours=72))
    _, outs = run(s, day(-2.0, 4.0, band=2))
    south = [int(o.surface[2, S]) for o in outs]
    north = [int(o.surface[2, N]) for o in outs]
    assert south[6] == ICE
    assert SOFT in south[7:12]
    assert all(v == WET for v in south[13:16])
    assert south[22] == ICE
    assert set(north) <= {ICE, FIRM}


def test_rain_on_snow_then_freeze_is_ice():
    s = old_pack(100)
    rain = [hour(3.0, h=20 + i, precip=2.0, snow_level=3300.0) for i in range(4)]
    s, outs = run(s, rain)
    assert outs[-1].surface[0, N] == WET
    _, outs = run(s, [hour(-5.0, h=h) for h in range(6)])
    assert (outs[-1].ice[0] == 1).all()


def test_wind_loads_the_lee():
    s = old_pack(50)
    s, _ = run(s, [hour(-8, h=0, precip=20.0, snow_level=1500.0)])
    _, outs = run(s, [hour(-8, h=1 + i, wind=15.0, wind_from=225.0) for i in range(6)])
    w = outs[-1].wind[3]
    assert w[NE] > 0.1
    assert w[NE] > 5 * w[SW]


def test_cold_clear_spell_then_snow_makes_persistent():
    s = old_pack(90)
    s, _ = run(s, [hour(-10, h=i % 24) for i in range(240)])
    _, outs = run(s, [hour(-10, h=0, precip=25.0, snow_level=1500.0)])
    assert outs[-1].persistent[3, N] > 0


def test_measured_sun_replaces_clear_sky():
    s = crusted(old_pack(200, hours=72))
    dark = [dataclasses.replace(f, sw_down=np.asarray(0.0)) for f in day(-2.0, 4.0, band=2)]
    _, outs = run(s, dark)
    assert all(int(o.surface[2, S]) == ICE for o in outs[:13])


def test_no_snow_is_all_zero():
    _, o = step(empty_state((), P), hour(5.0), P)
    for name in ("storm", "wind", "wet", "persistent", "ice", "swe_mm", "liquid_mm"):
        v = getattr(o, name)
        assert np.isfinite(v).all() and (v == 0).all(), name


def test_nan_horizon_zone_is_finite():
    horizon = np.zeros((NB, 8, 36))
    horizon[3:] = np.nan
    s = old_pack(100)
    _, o = step(s, hour(0.0), P, horizon)
    for name in ("storm", "wind", "wet", "persistent", "swe_mm", "liquid_mm"):
        assert np.isfinite(getattr(o, name)).all(), name


def test_nan_forcing_raises():
    f = hour(0.0)
    f = dataclasses.replace(f, t_c=np.full((NB, 1), np.nan))
    with pytest.raises(ValueError, match="t_c"):
        step(empty_state((), P), f, P)


def test_peak_lead_dim():
    one = old_pack(80)
    many = empty_state((34,), P)
    copied = {}
    for fld in dataclasses.fields(one):
        a, b = getattr(one, fld.name), getattr(many, fld.name)
        if isinstance(a, np.ndarray):
            a = a[:, None] if a.ndim == 3 else a
            copied[fld.name] = np.broadcast_to(a, b.shape).copy()
    many = dataclasses.replace(many, **copied)
    f = hour(1.0, precip=3.0, snow_level=2500.0)
    _, o_many = step(many, f, P)
    _, o_one = step(one, f, P)
    assert o_many.storm.shape == (34, NB, 8)
    np.testing.assert_array_equal(o_many.wet[0], o_one.wet)
    np.testing.assert_array_equal(o_many.surface[0], o_one.surface)


def test_step_does_not_mutate():
    s = old_pack(80)
    before = {f.name: np.copy(getattr(s, f.name)) for f in dataclasses.fields(s)}
    step(s, hour(2.0, precip=4.0, snow_level=2500.0, wind=12.0), P)
    for name, v in before.items():
        assert np.array_equal(getattr(s, name), v), name
