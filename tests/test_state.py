import dataclasses

import numpy as np
import pytest

from socal_snowpack.grid import NB
from socal_snowpack.params import load_params
from socal_snowpack.state import (CRUST, NEW, SETTLED, add_snow, buried_weak, empty_state,
                                  load_state, save_state, top)

P = load_params()


def snow(mm):
    return np.full((NB, 8), float(mm))


def aged(s, hours):
    return dataclasses.replace(s, age_h=s.age_h + hours)


def test_snowfall_makes_a_layer():
    s = add_snow(empty_state((), P), snow(10), P)
    assert (top(s) == 0).all()
    assert (s.kind[0] == NEW).all()
    assert (s.swe_mm[0] == 10).all()


def test_snow_within_six_hours_joins_the_top_layer():
    s = add_snow(empty_state((), P), snow(10), P)
    s = add_snow(aged(s, 3), snow(5), P)
    assert (top(s) == 0).all()
    assert (s.swe_mm[0] == 15).all()
    s = add_snow(aged(s, 7), snow(5), P)
    assert (top(s) == 1).all()


def test_no_snow_changes_nothing():
    s0 = add_snow(empty_state((), P), snow(10), P)
    s1 = add_snow(s0, snow(0), P)
    assert np.array_equal(s0.swe_mm, s1.swe_mm) and np.array_equal(s0.kind, s1.kind)


def test_full_stack_merges_bottom_and_conserves_swe():
    s = empty_state((), P)
    for i in range(40):
        s = add_snow(aged(s, 24), snow(i + 1), P)
    assert s.swe_mm.sum(axis=0)[0, 0] == pytest.approx(sum(range(1, 41)))
    assert (top(s) == P.hourly.max_layers - 1).all()
    assert (s.kind[0] == SETTLED).all()
    assert (s.swe_mm[-1] == 40).all()


def test_buried_crust_is_found():
    s = add_snow(empty_state((), P), snow(30), P)
    s = dataclasses.replace(s, kind=np.where(s.kind == NEW, CRUST, s.kind).astype(np.int8),
                            facet=np.where(s.kind == NEW, 0.5, s.facet))
    s = add_snow(aged(s, 24), snow(20), P)
    weak, load = buried_weak(s, P)
    assert (weak == 0.5).all()
    assert (load == 20).all()


def test_thin_cover_does_not_bury():
    s = add_snow(empty_state((), P), snow(30), P)
    s = dataclasses.replace(s, kind=np.full_like(s.kind, CRUST), facet=np.full_like(s.facet, 0.5))
    s = add_snow(aged(s, 24), snow(5), P)
    weak, _ = buried_weak(s, P)
    assert (weak == 0).all()


def test_round_trip(tmp_path):
    s = add_snow(empty_state((3,), P), np.full((3, NB, 8), 12.0), P)
    path = tmp_path / "state.npz"
    save_state(s, path)
    back = load_state(path)
    for f in dataclasses.fields(s):
        assert np.array_equal(getattr(s, f.name), getattr(back, f.name)), f.name


def test_wrong_version_is_refused(tmp_path):
    path = tmp_path / "state.npz"
    save_state(empty_state((), P), path)
    data = dict(np.load(path))
    data["version"] = np.array(999)
    np.savez_compressed(path, **data)
    with pytest.raises(ValueError, match="version"):
        load_state(path)


def test_lead_shape():
    s = empty_state((34,), P)
    assert s.new_mm.shape == (34, NB, 8)
    assert s.swe_mm.shape == (P.hourly.max_layers, 34, NB, 8)
