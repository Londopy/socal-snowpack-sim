import ast
import dataclasses
import os

import numpy as np

import socal_snowpack.daily
from socal_snowpack import daily, solar, weather
from socal_snowpack.params import load_params

ALLOWED = {0, 1, -1, 180, 360}


def test_every_daily_threshold_is_named():
    tree = ast.parse(open(socal_snowpack.daily.__file__).read())
    bare = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            if node.value not in ALLOWED:
                bare.append((node.lineno, node.value))
    assert not bare, f"unnamed numbers in daily.py: {bare}"


def test_param_change_moves_output():
    p = load_params()
    rng = np.random.default_rng(7)
    wx = weather.make_season(rng, p)
    gmean, gpeak = solar.solar_tables(p)
    base = daily.run_season(wx, gmean, gpeak, p)
    slow = dataclasses.replace(p, daily=dataclasses.replace(p.daily, storm_full_mm=70.0))
    moved = daily.run_season(wx, gmean, gpeak, slow)
    assert moved["storm"].sum() < base["storm"].sum()


def test_load_params_from_a_file(tmp_path):
    src = open(os.path.join(os.path.dirname(socal_snowpack.daily.__file__), "params.toml")).read()
    path = tmp_path / "p.toml"
    path.write_text(src.replace("storm_full_mm = 35.0", "storm_full_mm = 50.0"))
    assert load_params(str(path)).daily.storm_full_mm == 50.0
