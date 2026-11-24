"""Terrain analysis: download public elevation tiles around each peak and
compute slope angle and aspect.

Elevation source: AWS Open Data "Terrain Tiles" (Terrarium PNG), which in the
US are built from USGS 3DEP. Zoom 13 is about 16 m per pixel at this latitude.

Usage:  python src/terrain.py        (writes data/<slug>.npz)
"""
import math
import os
import urllib.request

import numpy as np
from PIL import Image

from peaks import PEAKS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
ZOOM = 13
HALF_WIDTH_M = 3600.0
URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"


def tile_xy(lat, lon, z=ZOOM):
    n = 2 ** z
    x = (lon + 180.0) / 360.0 * n
    y = (1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n
    return x, y


def fetch_tile(x, y, z=ZOOM):
    cache = os.path.join(DATA, "tiles", f"{z}_{x}_{y}.png")
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    if not os.path.exists(cache):
        with urllib.request.urlopen(URL.format(z=z, x=x, y=y), timeout=60) as r:
            raw = r.read()
        with open(cache, "wb") as f:
            f.write(raw)
    im = np.asarray(Image.open(cache).convert("RGB"), dtype=np.float64)
    return im[:, :, 0] * 256.0 + im[:, :, 1] + im[:, :, 2] / 256.0 - 32768.0


def slope_aspect(dem, res):
    """Slope (degrees) and aspect (direction the slope faces, degrees clockwise from north)."""
    k = np.array([1, 2, 1], dtype=float) / 4.0          # light smoothing against quantisation
    sm = np.apply_along_axis(lambda v: np.convolve(v, k, mode="same"), 0, dem)
    sm = np.apply_along_axis(lambda v: np.convolve(v, k, mode="same"), 1, sm)
    d_row, d_col = np.gradient(sm, res)
    gx, gy = d_col, -d_row                              # east, north
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    aspect = (np.degrees(np.arctan2(-gx, -gy)) + 360.0) % 360.0
    return slope, aspect


def build(lat, lon):
    res = 156543.03392 * math.cos(math.radians(lat)) / 2 ** ZOOM
    x, y = tile_xy(lat, lon)
    half_px = HALF_WIDTH_M / res
    x0, x1 = int((x * 256 - half_px) // 256), int((x * 256 + half_px) // 256)
    y0, y1 = int((y * 256 - half_px) // 256), int((y * 256 + half_px) // 256)
    dem = np.vstack([np.hstack([fetch_tile(tx, ty) for tx in range(x0, x1 + 1)])
                     for ty in range(y0, y1 + 1)])
    r, c = (y - y0) * 256.0, (x - x0) * 256.0
    w = int(150 / res)                                  # snap to the true high point
    r0, c0 = int(r), int(c)
    sub = dem[r0 - w:r0 + w + 1, c0 - w:c0 + w + 1]
    i, j = np.unravel_index(np.argmax(sub), sub.shape)
    r, c = r0 - w + i, c0 - w + j
    h = int(half_px)
    win = (slice(max(r - h, 0), r + h + 1), slice(max(c - h, 0), c + h + 1))
    dem = dem[win]
    slope, aspect = slope_aspect(dem, res)
    return dem, slope, aspect, res, (r - win[0].start, c - win[1].start)


def main():
    os.makedirs(DATA, exist_ok=True)
    for slug, name, rng, lat, lon, listed in PEAKS:
        dem, slope, aspect, res, (r, c) = build(lat, lon)
        top_ft = dem[r, c] * 3.28084
        flag = "" if abs(top_ft - listed) < 60 else "   <-- CHECK COORDINATES"
        print(f"{name:28s} DEM high point {top_ft:7.0f} ft   listed {listed} ft{flag}")
        np.savez_compressed(os.path.join(DATA, slug + ".npz"), dem=dem.astype(np.float32),
                            slope=slope.astype(np.float32), aspect=aspect.astype(np.float32),
                            res=res, peak=np.array([r, c]))


if __name__ == "__main__":
    main()
