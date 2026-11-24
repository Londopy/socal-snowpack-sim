"""Snowpack state carried hour to hour: a small layer stack per zone plus a few zone totals.

Layer arrays are shaped (L, ..., NB, 8) with layer 0 at the bottom and layers packed
from the bottom up. Zone arrays are shaped (..., NB, 8).
"""
import os
from dataclasses import dataclass, fields, replace

import numpy as np

from .grid import NB

EMPTY, NEW, SETTLED, FACET, CRUST = 0, 1, 2, 3, 4
LAYER_FIELDS = ("swe_mm", "kind", "age_h", "facet", "liquid_mm")
VERSION = 1


@dataclass(frozen=True)
class State:
    swe_mm: np.ndarray
    kind: np.ndarray
    age_h: np.ndarray
    facet: np.ndarray            # weakness of facets in or on the layer, 0..1
    liquid_mm: np.ndarray
    new_mm: np.ndarray           # recent storm snow, settling away
    dry_mm: np.ndarray           # recent snow still dry enough for the wind to move
    wind_slab: np.ndarray
    bond_bad: np.ndarray         # new snow sitting on a crust or facets
    mf_cycles: np.ndarray        # melt-freeze cycles since the last real snowfall
    hours_since_snow: np.ndarray
    melt_since_mm: np.ndarray    # water through the pack since the weak layer was buried
    thaw_h: np.ndarray           # hours the surface has held water since it last refroze
    since_wet_h: np.ndarray      # hours since the surface was last wet
    hour_index: int


def empty_state(lead, p):
    zone = tuple(lead) + (NB, 8)
    layers = (p.hourly.max_layers,) + zone
    z = np.zeros(zone)
    return State(swe_mm=np.zeros(layers), kind=np.zeros(layers, np.int8), age_h=np.zeros(layers),
                 facet=np.zeros(layers), liquid_mm=np.zeros(layers),
                 new_mm=z, dry_mm=z.copy(), wind_slab=z.copy(), bond_bad=z.copy(), mf_cycles=z.copy(),
                 hours_since_snow=np.full(zone, p.daily.age_init_days * 24), melt_since_mm=z.copy(),
                 thaw_h=z.copy(), since_wet_h=np.full(zone, p.daily.age_init_days * 24), hour_index=0)


def top(s):
    """Index of the top layer in each zone, -1 where there is no snow."""
    return (s.kind != EMPTY).sum(axis=0) - 1


def top_value(a, t):
    return np.take_along_axis(a, np.maximum(t, 0)[None], 0)[0]


def _merge_bottom(s, full):
    """Where the stack is full, merge layers 0 and 1 and shift the rest down one."""
    out = {}
    for name in LAYER_FIELDS:
        a = getattr(s, name)
        if name in ("swe_mm", "liquid_mm"):
            bottom = a[0] + a[1]
        elif name == "kind":
            weak = (a[:2] == FACET) | (a[:2] == CRUST)
            bottom = np.where(weak[1], a[1], np.where(weak[0], a[0], SETTLED)).astype(a.dtype)
        else:
            bottom = np.maximum(a[0], a[1])
        shifted = np.concatenate([bottom[None], a[2:], np.zeros_like(a[:1])], axis=0)
        out[name] = np.where(full, shifted, a)
    return out


def add_snow(s, snow_mm, p):
    """Put new snow (mm SWE) on top: onto a young, dry NEW layer, else as a new layer."""
    L = s.swe_mm.shape[0]
    snow = np.broadcast_to(snow_mm, s.new_mm.shape)
    falls = snow > 0
    t = top(s)
    young = (top_value(s.kind, t) == NEW) & (top_value(s.age_h, t) < p.hourly.new_layer_hours)
    join = falls & (t >= 0) & young & (top_value(s.liquid_mm, t) <= p.hourly.damp_mm)
    push = falls & ~join
    full = push & (t == L - 1)
    layers = _merge_bottom(s, full)
    t = np.where(full, t - 1, t)
    target = np.where(join, t, t + 1)
    idx = np.arange(L).reshape((L,) + (1,) * snow.ndim)
    at = (idx == target) & falls
    fresh = (idx == target) & push
    return replace(s,
                   swe_mm=layers["swe_mm"] + np.where(at, snow, 0.0),
                   kind=np.where(fresh, NEW, layers["kind"]).astype(np.int8),
                   age_h=np.where(fresh, 0.0, layers["age_h"]),
                   facet=np.where(fresh, 0.0, layers["facet"]),
                   liquid_mm=np.where(fresh, 0.0, layers["liquid_mm"]))


def buried_weak(s, p):
    """Weakness of the worst buried facet or crust layer per zone, and the snow load above it."""
    above = s.swe_mm.sum(axis=0) - np.cumsum(s.swe_mm, axis=0)
    weakish = ((s.kind == FACET) | (s.kind == CRUST)) & (above >= p.hourly.bury_mm)
    w = np.where(weakish, s.facet, 0.0)
    i = np.argmax(w, axis=0)[None]
    weak = np.take_along_axis(w, i, 0)[0]
    load = np.where(weak > 0, np.take_along_axis(above, i, 0)[0], 0.0)
    return weak, load


def _npz(path):
    path = str(path)
    return path if path.endswith(".npz") else path + ".npz"


def save_state(s, path):
    """Write state to path (".npz" added if missing), replacing any old file only once the new one is complete."""
    final = _npz(path)
    tmp = final[:-4] + ".tmp.npz"
    try:
        np.savez_compressed(tmp, version=np.array(VERSION), **{f.name: getattr(s, f.name) for f in fields(s)})
        os.replace(tmp, final)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def load_state(path):
    path = _npz(path)
    with np.load(path) as z:
        if int(z["version"]) != VERSION:
            raise ValueError(f"state file {path} is version {int(z['version'])}, this code reads version {VERSION}")
        values = {f.name: z[f.name] for f in fields(State)}
    values["hour_index"] = int(values["hour_index"])
    return State(**values)
