"""Export terrain, lidar hillshade and a few simulated winters for the 3D site.

Writes site/public/data/. Elevation comes from the same AWS Terrain Tiles as
terrain.py (one zoom finer), the hillshade from the USGS 3DEP ImageServer,
which uses 1 m lidar where it has been flown. The winters are re-run with the
same seed as model.py, so they are the same seasons its statistics came from.

Usage:  python src/export_site.py        (after terrain.py, model.py and analyze.py)
"""
import json
import math
import os
import urllib.parse
import urllib.request

import numpy as np
from PIL import Image

import model
from peaks import PEAKS
from terrain import HALF_WIDTH_M, fetch_tile, tile_xy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "site", "public", "data")
CACHE = os.path.join(ROOT, "data", "lidar")
R_EARTH = 6378137.0
GRID = 512
REGION_ZOOM = 10
REGION_W = 1024
PEAK_ZOOM = 14
HILLSHADE_PX = 2048
HILLSHADE_URL = "https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer/exportImage"


def merc(lat, lon):
    x = R_EARTH * math.radians(lon)
    y = R_EARTH * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))
    return x, y


def unmerc(x, y):
    return math.degrees(2 * math.atan(math.exp(y / R_EARTH)) - math.pi / 2), math.degrees(x / R_EARTH)


def mosaic(x0, y0, x1, y1, z):
    """Elevation mosaic covering a mercator bbox, plus a function mapping mercator to pixel."""
    lat0, lon0 = unmerc(x0, y1)
    lat1, lon1 = unmerc(x1, y0)
    tx0, ty0 = (int(v) for v in tile_xy(lat0, lon0, z))
    tx1, ty1 = (int(v) for v in tile_xy(lat1, lon1, z))
    dem = np.vstack([np.hstack([fetch_tile(tx, ty, z) for tx in range(tx0, tx1 + 1)])
                     for ty in range(ty0, ty1 + 1)])
    world = 2 * math.pi * R_EARTH
    scale = 256 * 2 ** z / world

    def to_px(mx, my):
        return (mx + world / 2) * scale - tx0 * 256, (world / 2 - my) * scale - ty0 * 256
    return dem, to_px


def bilinear(img, px, py):
    px = np.clip(px, 0, img.shape[1] - 1.001)
    py = np.clip(py, 0, img.shape[0] - 1.001)
    x0, y0 = np.floor(px).astype(int), np.floor(py).astype(int)
    fx, fy = px - x0, py - y0
    a = img[y0, x0] * (1 - fx) + img[y0, x0 + 1] * fx
    b = img[y0 + 1, x0] * (1 - fx) + img[y0 + 1, x0 + 1] * fx
    return a * (1 - fy) + b * fy


def sample_grid(x0, y0, x1, y1, z, w, h):
    dem, to_px = mosaic(x0, y0, x1, y1, z)
    mx = np.linspace(x0, x1, w)[None, :].repeat(h, 0)
    my = np.linspace(y1, y0, h)[:, None].repeat(w, 1)
    px, py = to_px(mx, my)
    # terrarium values sit at pixel centres
    return bilinear(dem, px - 0.5, py - 0.5)


def despike(elev, limit=300.0):
    """Replace cells more than `limit` m off their 3x3 median; a few source tiles carry bad pixels."""
    pad = np.pad(elev, 1, mode="edge")
    stack = np.stack([pad[i:i + elev.shape[0], j:j + elev.shape[1]] for i in range(3) for j in range(3)])
    med = np.median(stack, axis=0)
    return np.where(np.abs(elev - med) > limit, med, elev)


def terrarium_png(elev, path):
    v = np.clip(elev, -32768, 32767) + 32768.0
    r = np.floor(v / 256.0)
    g = np.floor(v) - r * 256.0
    b = np.floor((v - np.floor(v)) * 256.0)
    Image.fromarray(np.dstack([r, g, b]).astype(np.uint8), "RGB").save(path, optimize=True)


def snap_summit(lat, lon):
    """Highest cell within 150 m of the listed point, as terrain.py does."""
    x, y = merc(lat, lon)
    r = 150.0 / math.cos(math.radians(lat))
    elev = sample_grid(x - r, y - r, x + r, y + r, PEAK_ZOOM, 41, 41)
    i, j = np.unravel_index(np.argmax(elev), elev.shape)
    mx = x - r + 2 * r * j / 40.0
    my = y + r - 2 * r * i / 40.0
    return unmerc(mx, my), float(elev[i, j])


def fetch_hillshade(slug, bbox):
    # the bbox is in the name so a moved window never reuses a misregistered image
    tag = "_".join("%d" % round(v) for v in bbox)
    cache = os.path.join(CACHE, f"{slug}_{tag}.jpg")
    if not os.path.exists(cache):
        q = urllib.parse.urlencode({
            "bbox": ",".join("%.2f" % v for v in bbox), "bboxSR": 3857, "imageSR": 3857,
            "size": "%d,%d" % (HILLSHADE_PX, HILLSHADE_PX), "format": "jpg",
            "renderingRule": json.dumps({"rasterFunction": "Hillshade Multidirectional"}),
            "f": "image"})
        with urllib.request.urlopen(HILLSHADE_URL + "?" + q, timeout=180) as r:
            raw = r.read()
            if not r.headers.get("Content-Type", "").startswith("image/"):
                raise RuntimeError(f"3DEP returned {r.headers.get('Content-Type')} for {slug}: {raw[:200]!r}")
        os.makedirs(CACHE, exist_ok=True)
        with open(cache, "wb") as f:
            f.write(raw)
    Image.open(cache).convert("L").save(os.path.join(OUT, "lidar", slug + ".jpg"), quality=82, optimize=True)


def export_peaks():
    stats = json.load(open(os.path.join(ROOT, "results", "peaks.json")))
    os.makedirs(os.path.join(OUT, "terrain"), exist_ok=True)
    os.makedirs(os.path.join(OUT, "lidar"), exist_ok=True)
    peaks = []
    for slug, name, area, lat, lon, listed in PEAKS:
        (slat, slon), top = snap_summit(lat, lon)
        half = HALF_WIDTH_M / math.cos(math.radians(slat))
        cx, cy = merc(slat, slon)
        bbox = [cx - half, cy - half, cx + half, cy + half]
        elev = sample_grid(*bbox, PEAK_ZOOM, GRID, GRID)
        terrarium_png(elev, os.path.join(OUT, "terrain", slug + ".png"))
        fetch_hillshade(slug, bbox)
        print(f"{name:28s} {top * 3.28084:7.0f} ft  relief {elev.min():.0f}-{elev.max():.0f} m")
        peaks.append(dict(slug=slug, name=name, area=area, lat=round(slat, 5), lon=round(slon, 5),
                          listed_ft=listed, bbox=[round(v, 1) for v in bbox], size_m=2 * HALF_WIDTH_M,
                          grid=GRID, stats={k: v for k, v in stats[slug].items() if k not in ("name", "area")}))
    return peaks


def export_region(peaks):
    lats = [p["lat"] for p in peaks]
    lons = [p["lon"] for p in peaks]
    x0, y0 = merc(min(lats) - 0.12, min(lons) - 0.12)
    x1, y1 = merc(max(lats) + 0.12, max(lons) + 0.12)
    h = int(round(REGION_W * (y1 - y0) / (x1 - x0)))
    elev = despike(sample_grid(x0, y0, x1, y1, REGION_ZOOM, REGION_W, h))
    terrarium_png(elev, os.path.join(OUT, "terrain", "region.png"))
    k = math.cos(math.radians(unmerc((x0 + x1) / 2, (y0 + y1) / 2)[0]))
    return dict(bbox=[round(v, 1) for v in (x0, y0, x1, y1)], width=REGION_W, height=h,
                size_m=[(x1 - x0) * k, (y1 - y0) * k])


def export_winters(n_seasons=400, seed=7):
    """Re-run model.py's seasons and keep the dry, typical and big winters at 8,500-9,500 ft."""
    rng = np.random.default_rng(seed)
    gmean, gpeak = model.solar_tables()
    seasons = []
    for _ in range(n_seasons):
        wx = model.make_season(rng)
        o = model.run_season(wx, gmean, gpeak)
        seasons.append((float(o["snowfall"][model.MID]), wx))
    falls = np.array([s[0] for s in seasons])
    # guard against this loop drifting from model.main's RNG order
    ref = json.load(open(os.path.join(ROOT, "results", "model.json")))["snowfall_mm_water_by_band"]
    for pct in (10, 50, 90):
        if round(float(np.percentile(falls, pct))) != ref["p%d" % pct][model.MID]:
            raise RuntimeError("re-run seasons no longer match results/model.json; run model.py first")
    picks = [("dry", "Dry winter", 10), ("typical", "Typical winter", 50), ("big", "Big winter", 90)]
    winters = []
    for key, label, pct in picks:
        i = int(np.argmin(np.abs(falls - np.percentile(falls, pct))))
        wx = seasons[i][1]
        o = model.run_season(wx, gmean, gpeak)
        grid = {k: np.round(o[k] * 100).astype(int).ravel().tolist()
                for k in model.PROBLEMS + ["ice", "ft", "corn"]}
        grid["swe"] = np.round(o["swe"]).astype(int).ravel().tolist()
        winters.append(dict(
            key=key, label=label, percentile=pct, season_index=i,
            snowfall_mm_by_band=np.round(o["snowfall"]).astype(int).tolist(),
            weather=dict(
                precip_mm=np.round(wx["P"], 1).tolist(),
                snow_level_m=[None if np.isnan(v) else int(round(v)) for v in wx["SL"]],
                wind_ms=np.round(wx["wind"], 1).tolist(),
                wind_from_deg=np.round(wx["wdir"]).astype(int).tolist(),
                tmax_c=np.round(wx["Tmax"], 1).tolist(),
                tmin_c=np.round(wx["Tmin"], 1).tolist(),
                storm=wx["storm"].astype(int).tolist(),
                santa_ana=wx["santa"].astype(int).tolist()),
            grid=grid))
    return winters


def main():
    os.makedirs(OUT, exist_ok=True)
    peaks = export_peaks()
    region = export_region(peaks)
    res = json.load(open(os.path.join(ROOT, "results", "model.json")))
    meta = dict(
        days=model.NDAYS, aspects=model.ASP_NAMES, bands=model.BAND_NAMES,
        band_edges_m=model.BAND_EDGES_M.tolist(), elevated=model.CONSIDERABLE, high=model.HIGH,
        index_scale=100, region=region, peaks=peaks)
    with open(os.path.join(OUT, "site.json"), "w") as f:
        json.dump(meta, f, separators=(",", ":"))
    with open(os.path.join(OUT, "model.json"), "w") as f:
        json.dump(res, f, separators=(",", ":"))
    with open(os.path.join(OUT, "winters.json"), "w") as f:
        json.dump(export_winters(), f, separators=(",", ":"))


if __name__ == "__main__":
    main()
