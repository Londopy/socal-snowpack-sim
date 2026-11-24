"""Export a close-up of Mt. Baldy's Baldy Bowl for the viewer's illustrated slide.

Pulls a 3 m elevation grid and a lidar hillshade from the USGS 3DEP ImageServer
and picks a release zone from the terrain: the largest connected patch of 32-45
degree ground facing east to south on the upper headwall. The viewer slides that
zone down the real fall line; nothing here predicts that the slope will fail.

Usage:  python src/export_bowl.py        (writes site/public/data/bowl/)
"""
import json
import math
import os
import urllib.parse
import urllib.request
from collections import deque

import numpy as np
from PIL import Image

import model
from export_site import HILLSHADE_URL, merc, terrarium_png

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "site", "public", "data", "bowl")
CACHE = os.path.join(ROOT, "data", "bowl")
CENTER = (34.2835, -117.6390)  # middle of the bowl, below the summit on its south-east side
HALF_M = 900.0
GRID = 600
LIDAR_PX = 1200
BLOCK_STRIDE = 3  # one slab block per 3 x 3 cells, 9 m apart


def bbox():
    lat, lon = CENTER
    x, y = merc(lat, lon)
    half = HALF_M / math.cos(math.radians(lat))
    return [x - half, y - half, x + half, y + half]


def fetch(name, params, box):
    # the box and size are in the name so a changed window never reuses an old download
    stem, ext = os.path.splitext(name)
    tag = "_".join("%d" % round(v) for v in box)
    path = os.path.join(CACHE, f"{stem}_{params['size'].replace(',', 'x')}_{tag}{ext}")
    if not os.path.exists(path):
        q = urllib.parse.urlencode({"bbox": ",".join("%.2f" % v for v in box), "bboxSR": 3857,
                                    "imageSR": 3857, "f": "image", **params})
        with urllib.request.urlopen(HILLSHADE_URL + "?" + q, timeout=180) as r:
            raw = r.read()
            if not r.headers.get("Content-Type", "").startswith("image/"):
                raise RuntimeError(f"3DEP returned {r.headers.get('Content-Type')} for {name}: {raw[:200]!r}")
        os.makedirs(CACHE, exist_ok=True)
        with open(path, "wb") as f:
            f.write(raw)
    return Image.open(path)


def release_zone(z, res):
    gy, gx = np.gradient(z, res)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    aspect = (np.degrees(np.arctan2(-gx, gy)) + 360) % 360
    r, c = np.indices(z.shape)
    # the headwall under the summit ridge; the window also holds Harwood's and the
    # ridge's own steep faces, which are not part of the bowl
    steep = ((slope >= 32) & (slope <= 45) & (z >= 2720) & (aspect >= 70) & (aspect <= 200)
             & (r >= 110) & (r <= 340) & (c >= 90) & (c <= 340))
    patch = largest_patch(steep)
    lo, hi = z[patch].min(), z[patch].max()
    # slabs break high on the headwall, so keep the upper part of the patch
    zone = largest_patch(patch & (z >= lo + 0.45 * (hi - lo)))
    return zone, slope, aspect


def largest_patch(mask):
    label = np.zeros(mask.shape, int)
    best, best_size, n = 0, 0, 0
    for i, j in zip(*np.nonzero(mask)):
        if label[i, j]:
            continue
        n += 1
        label[i, j] = n
        queue, size = deque([(i, j)]), 0
        while queue:
            a, b = queue.popleft()
            size += 1
            for x, y in ((a + 1, b), (a - 1, b), (a, b + 1), (a, b - 1)):
                if 0 <= x < mask.shape[0] and 0 <= y < mask.shape[1] and mask[x, y] and not label[x, y]:
                    label[x, y] = n
                    queue.append((x, y))
        if size > best_size:
            best, best_size = n, size
    if not best:
        raise RuntimeError("no 32-45 degree east-to-south ground on the headwall; check the DEM window")
    return label == best


def main():
    os.makedirs(OUT, exist_ok=True)
    dem = fetch("dem.tif", {"size": f"{GRID},{GRID}", "format": "tiff", "pixelType": "F32",
                            "noData": -9999, "interpolation": "RSP_BilinearInterpolation"}, bbox())
    z = np.asarray(dem, dtype=np.float64)
    if z.shape != (GRID, GRID):
        raise RuntimeError(f"3DEP sent a {z.shape} grid for the bowl, expected {GRID} x {GRID}")
    if (z < -1000).any():
        raise RuntimeError("3DEP grid for the bowl has missing cells")
    res = 2 * HALF_M / GRID
    terrarium_png(z, os.path.join(OUT, "terrain.png"))
    shade = fetch("lidar.jpg", {"size": f"{LIDAR_PX},{LIDAR_PX}", "format": "jpg",
                                "renderingRule": json.dumps({"rasterFunction": "Hillshade Multidirectional"})}, bbox())
    shade.convert("L").save(os.path.join(OUT, "lidar.jpg"), quality=82, optimize=True)

    zone, slope, aspect = release_zone(z, res)
    # each block carries the model cell (aspect, elevation band) its slope falls in
    asp_i = np.round(aspect / 45).astype(int) % len(model.ASP_NAMES)
    band_i = np.clip(np.digitize(z, model.BAND_EDGES_M) - 1, 0, len(model.BAND_NAMES) - 1)
    blocks = [[int(i), int(j), int(asp_i[i, j]), int(band_i[i, j])] for i, j in zip(*np.nonzero(zone))
              if i % BLOCK_STRIDE == 0 and j % BLOCK_STRIDE == 0]
    cells = {}
    for a, b in zip(asp_i[zone], band_i[zone]):
        cells[(int(a), int(b))] = cells.get((int(a), int(b)), 0) + 1
    shares = [dict(aspect=a, band=b, share=round(n / zone.sum(), 3)) for (a, b), n in sorted(cells.items())]
    meta = dict(
        name="Baldy Bowl", peak="baldy", center=list(CENTER), bbox=[round(v, 1) for v in bbox()],
        size_m=2 * HALF_M, grid=GRID, cell_m=res, block_stride=BLOCK_STRIDE, blocks=blocks, cells=shares,
        release=dict(area_m2=round(float(zone.sum()) * res * res), slope_deg=round(float(slope[zone].mean()), 1),
                     aspect_deg=round(float(aspect[zone].mean())), top_m=round(float(z[zone].max())),
                     bottom_m=round(float(z[zone].min()))))
    with open(os.path.join(OUT, "bowl.json"), "w") as f:
        json.dump(meta, f, separators=(",", ":"))
    print(f"release zone {meta['release']}, {len(blocks)} blocks")


if __name__ == "__main__":
    main()
