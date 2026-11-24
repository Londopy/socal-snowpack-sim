"""Horizon angles per zone, so shaded bowls stop being treated as sunlit."""
import numpy as np


def cell_horizons(dem, rows, cols, res, n_az, max_dist_m):
    """Horizon elevation angle (degrees) from each cell in each of n_az directions."""
    dist = np.arange(1, int(max_dist_m / res) + 1) * res
    z0 = dem[rows, cols][:, None]
    out = np.empty((len(rows), n_az))
    for i, az in enumerate(np.radians(np.arange(n_az) * 360.0 / n_az)):
        r = np.rint(rows[:, None] - np.cos(az) * dist / res).astype(int)
        c = np.rint(cols[:, None] + np.sin(az) * dist / res).astype(int)
        inside = (r >= 0) & (r < dem.shape[0]) & (c >= 0) & (c < dem.shape[1])
        z = dem[np.clip(r, 0, dem.shape[0] - 1), np.clip(c, 0, dem.shape[1] - 1)]
        ang = np.where(inside, np.degrees(np.arctan2(z - z0, dist)), -90.0)
        out[:, i] = ang.max(axis=1)
    return out


def horizon_by_zone(dem, slope, aspect, res, band_edges_m, n_az=36, max_dist_m=3000.0,
                    min_slope=30.0, stride=4):
    """Median horizon (degrees) over each zone's steep cells, shape (NB, 8, n_az).

    DEM rows run north to south. Zones with no steep cells are NaN.
    """
    nb = len(band_edges_m) - 1
    band = np.digitize(dem, band_edges_m) - 1
    sector = np.rint(aspect / 45.0).astype(int) % 8
    rows, cols = np.nonzero((slope >= min_slope) & (band >= 0) & (band < nb))
    rows, cols = rows[::stride], cols[::stride]
    h = cell_horizons(dem, rows, cols, res, n_az, max_dist_m)
    zb, za = band[rows, cols], sector[rows, cols]
    out = np.full((nb, 8, n_az), np.nan)
    for b in range(nb):
        for a in range(8):
            sel = (zb == b) & (za == a)
            if sel.any():
                out[b, a] = np.median(h[sel], axis=0)
    return out
