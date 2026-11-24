"""Combine the terrain grids with the model output.

For every peak: slope and aspect statistics, a slope-angle map, and the model's
day counts weighted by how much steep terrain the peak really has on each
aspect and elevation band. Also draws the range-wide model figures.

Usage:  python src/analyze.py      (after terrain.py and model.py)
"""
import json
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LightSource, ListedColormap, BoundaryNorm

from peaks import PEAKS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
FIG = os.path.join(ROOT, "figures")
os.makedirs(os.path.join(FIG, "peaks"), exist_ok=True)
plt.rcParams.update({"font.size": 9, "axes.titlesize": 10})

R = json.load(open(os.path.join(ROOT, "results", "model.json")))
Z = np.load(os.path.join(DATA, "model.npz"))
ASP = R["aspects"]
EDGES = np.array(R["band_edges_m"])
NB = len(EDGES) - 1
BAND_SHORT = ["%.1f-%.1fk" % (a * 3.28084 / 1000, b * 3.28084 / 1000) for a, b in zip(EDGES[:-1], EDGES[1:])]
ZONE_RADIUS_M = 1500.0
ZONE_DROP_M = 750.0
KEYS = ["storm", "wind", "wet", "persistent", "any", "ice", "ft", "corn", "snow"]
FT = 3.28084


def load(slug):
    d = np.load(os.path.join(DATA, slug + ".npz"))
    return d["dem"].astype(float), d["slope"].astype(float), d["aspect"].astype(float), float(d["res"]), d["peak"]


def slope_map(ax, dem, slope, res, peak, name):
    ls = LightSource(azdeg=315, altdeg=45)
    ext = [0, dem.shape[1] * res / 1000, dem.shape[0] * res / 1000, 0]
    ax.imshow(ls.hillshade(dem, vert_exag=1.0, dx=res, dy=res), cmap="gray", extent=ext, vmin=0, vmax=1)
    cls = np.full(dem.shape, np.nan)
    cls[(slope >= 25) & (slope < 30)] = 0
    cls[(slope >= 30) & (slope < 35)] = 1
    cls[(slope >= 35) & (slope < 45)] = 2
    cls[slope >= 45] = 3
    cmap = ListedColormap(["#f6e58d", "#f0932b", "#d63031", "#6c1d6f"])
    im = ax.imshow(cls, cmap=cmap, norm=BoundaryNorm([-0.5, 0.5, 1.5, 2.5, 3.5], 4), extent=ext, alpha=0.6)
    x, y = peak[1] * res / 1000, peak[0] * res / 1000
    ax.plot(x, y, "^", color="white", mec="black", ms=8)
    ax.add_patch(plt.Circle((x, y), ZONE_RADIUS_M / 1000, fill=False, ec="white", lw=1, ls="--"))
    ax.set_title(f"{name}  ({dem[int(peak[0]), int(peak[1])] * FT:,.0f} ft)", fontsize=9)
    ax.set_xticks([]); ax.set_yticks([])
    return im


def peak_stats(slug, name, rng):
    dem, slope, aspect, res, peak = load(slug)
    rr, cc = np.indices(dem.shape)
    dist = np.hypot(rr - peak[0], cc - peak[1]) * res
    top = dem[int(peak[0]), int(peak[1])]
    floor = max(EDGES[0], top - ZONE_DROP_M)
    zone = (dist <= ZONE_RADIUS_M) & (dem >= floor)
    abin = ((aspect + 22.5) // 45).astype(int) % 8
    band = np.clip(np.digitize(dem, EDGES) - 1, 0, NB - 1)
    s = slope[zone]
    core = zone & (slope >= 30) & (slope < 45)
    steep = zone & (slope >= 30)
    share = [100.0 * (abin[core] == a).mean() for a in range(8)]
    st = {
        "name": name, "area": rng, "summit_ft": round(top * FT), "zone_floor_ft": round(floor * FT, -2),
        "zone_area_km2": round(zone.sum() * res * res / 1e6, 2),
        "pct_under_30": round(100 * (s < 30).mean(), 1),
        "pct_30_45": round(100 * ((s >= 30) & (s < 45)).mean(), 1),
        "pct_over_45": round(100 * (s >= 45).mean(), 1),
        "median_slope_deg": round(float(np.median(s)), 1),
        "aspect_share_of_30_45_pct": [round(v, 1) for v in share],
        "lee_share_pct": round(share[0] + share[1] + share[2], 1),          # N + NE + E
        "sunny_share_pct": round(share[3] + share[4] + share[5], 1),        # SE + S + SW
        "dominant_aspect": ASP[int(np.argmax(share))],
    }
    # model day counts weighted by the real steep terrain (aspect x elevation)
    for k in KEYS:
        tab = np.array(R["days"][k])
        st["model_days_" + k] = round(float(tab[band[steep], abin[steep]].mean()), 1)
    st["wet_share_of_snow_days_pct"] = round(100 * st["model_days_wet"] / max(st["model_days_snow"], 0.1))
    st["ice_share_of_snow_days_pct"] = round(100 * st["model_days_ice"] / max(st["model_days_snow"], 0.1))
    st["freeze_thaw_share_of_snow_days_pct"] = round(100 * st["model_days_ft"] / max(st["model_days_snow"], 0.1))
    return st, (dem, slope, res, peak)


def main():
    stats, grids = {}, {}
    for slug, name, rng, *_ in PEAKS:
        stats[slug], grids[slug] = peak_stats(slug, name, rng)
    json.dump(stats, open(os.path.join(ROOT, "results", "peaks.json"), "w"), indent=1)

    # ---- slope maps, all peaks on one sheet plus one file each
    ncol = 6
    nrow = -(-len(PEAKS) // ncol)
    fig, axs = plt.subplots(nrow, ncol, figsize=(2.6 * ncol, 2.75 * nrow))
    for ax in axs.ravel():
        ax.axis("off")
    for ax, (slug, name, *_rest) in zip(axs.ravel(), PEAKS):
        ax.axis("on")
        im = slope_map(ax, *grids[slug], name.split(" (")[0])
    cb = fig.colorbar(im, ax=axs, ticks=[0, 1, 2, 3], shrink=0.35, orientation="horizontal", pad=0.02)
    cb.ax.set_xticklabels(["25-30", "30-35", "35-45", "45+"]); cb.set_label("slope angle (degrees)")
    fig.suptitle("Slope angle around each peak (7.2 km squares, north up, dashed circle = 1.5 km analysis zone)", y=0.915)
    fig.savefig(os.path.join(FIG, "slope_maps.png"), dpi=110, bbox_inches="tight"); plt.close(fig)
    for slug, name, *_rest in PEAKS:
        fig, ax = plt.subplots(figsize=(5, 5))
        im = slope_map(ax, *grids[slug], name)
        cb = fig.colorbar(im, ax=ax, ticks=[0, 1, 2, 3], shrink=0.7)
        cb.ax.set_yticklabels(["25-30", "30-35", "35-45", "45+"]); cb.set_label("slope angle (degrees)")
        fig.savefig(os.path.join(FIG, "peaks", slug + "_slope.png"), dpi=90, bbox_inches="tight"); plt.close(fig)

    # ---- aspect roses
    fig, axs = plt.subplots(nrow, ncol, figsize=(2.3 * ncol, 2.6 * nrow), subplot_kw=dict(projection="polar"))
    th = np.radians(np.arange(0, 360, 45))
    for ax in axs.ravel()[len(PEAKS):]:
        ax.axis("off")
    for ax, (slug, name, *_rest) in zip(axs.ravel(), PEAKS):
        name = name.split(" (")[0]
        ax.bar(th, stats[slug]["aspect_share_of_30_45_pct"], width=np.radians(40), color="#d63031", alpha=0.8)
        ax.set_theta_zero_location("N"); ax.set_theta_direction(-1)
        ax.set_xticks(th); ax.set_xticklabels(ASP, fontsize=7); ax.set_yticklabels([])
        ax.set_title(name, fontsize=9, pad=10)
    fig.suptitle("Which way each peak's 30-45 degree terrain faces", y=1.0)
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "aspect_roses.png"), dpi=140, bbox_inches="tight"); plt.close(fig)

    # ---- peak comparison bars
    names = [stats[s]["name"].split(" (")[0] for s, *_ in PEAKS]
    y = np.arange(len(names))
    fig, axs = plt.subplots(1, 5, figsize=(12.5, 0.24 * len(PEAKS) + 1.4), sharey=True)
    for ax, key, title, col in [
            (axs[0], "pct_30_45", "% of zone at 30-45 degrees", "#d63031"),
            (axs[1], "model_days_storm", "storm slab days / winter", "#2e86de"),
            (axs[2], "model_days_wind", "wind slab days / winter", "#8e44ad"),
            (axs[3], "wet_share_of_snow_days_pct", "% of snow days with wet problem", "#e67e22"),
            (axs[4], "model_days_ft", "freeze-thaw cycles / winter", "#16a085")]:
        v = [stats[s][key] for s, *_ in PEAKS]
        ax.barh(y, v, color=col)
        for i, val in enumerate(v):
            ax.text(val, i, f" {val:.1f}" if val < 10 and key == "model_days_wind" else f" {val:.0f}", va="center", fontsize=7)
        ax.set_title(title, fontsize=8.5); ax.set_xlim(0, max(v) * 1.18)
    axs[0].set_yticks(y); axs[0].set_yticklabels(names, fontsize=8); axs[0].invert_yaxis()
    fig.suptitle("Model output weighted by each peak's real steep terrain (slopes of 30 degrees or more)", fontsize=9.5)
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "peak_comparison.png"), dpi=140); plt.close(fig)

    # ---- model heatmaps
    panels = [("storm", "Storm slab"), ("wind", "Wind slab"), ("wet", "Wet avalanches"),
              ("persistent", "Persistent slab"), ("any", "Any avalanche problem"), ("ft", "Freeze-thaw cycles"),
              ("ice", "Refrozen surface exposed"), ("corn", "Refrozen surface that softens by midday")]
    fig, axs = plt.subplots(2, 4, figsize=(13, 5.4))
    for ax, (k, title) in zip(axs.ravel(), panels):
        a = np.array(R["days"][k])[::-1]
        ax.imshow(a, cmap="Blues" if k in ("ice", "ft", "corn") else "YlOrRd", aspect="auto", vmin=0)
        ax.set_xticks(range(8)); ax.set_xticklabels(ASP, fontsize=7)
        ax.set_yticks(range(NB)); ax.set_yticklabels(BAND_SHORT[::-1], fontsize=7)
        for i in range(NB):
            for j in range(8):
                v = a[i, j]
                ax.text(j, i, f"{v:.0f}" if v >= 9.5 else f"{v:.1f}", ha="center", va="center", fontsize=6.5,
                        color="white" if v > 0.6 * a.max() else "black")
        ax.set_title(title, fontsize=9)
    fig.suptitle("Average days per simulated winter, by aspect and elevation (thousand ft). Avalanche panels count days at 'elevated' or worse.", fontsize=9.5)
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "model_heatmaps.png"), dpi=140); plt.close(fig)

    # ---- decay after storms, and by month
    cols = {"storm": "#2e86de", "wind": "#8e44ad", "wet": "#e67e22", "persistent": "#2d3436"}
    lab = {"storm": "storm slab", "wind": "wind slab", "wet": "wet", "persistent": "persistent slab"}
    fig, axs = plt.subplots(1, 2, figsize=(9.6, 3.2))
    ax = axs[0]
    ax.plot(range(8), R["after_storm"]["N"], "o-", color="#2e86de", label="north-facing")
    ax.plot(range(8), R["after_storm"]["S"], "o-", color="#d63031", label="south-facing")
    ax.axhline(0.45, color="gray", lw=0.6, ls=":"); ax.axhline(0.75, color="gray", lw=0.6, ls=":")
    ax.set_xlabel("days after the last day of a storm"); ax.set_ylabel("mean model index, " + R["high_band"])
    ax.set_title("Hazard drops fast after storms"); ax.legend(fontsize=7)
    ax = axs[1]
    mo = ["11", "12", "1", "2", "3", "4"]
    for i, (k, c) in enumerate(cols.items()):
        ax.bar(np.arange(6) + (i - 1.5) * 0.2, [R["monthly"][m][k] for m in mo], 0.2, color=c, label=lab[k])
    ax.set_xticks(range(6)); ax.set_xticklabels(["Nov (15th on)", "Dec", "Jan", "Feb", "Mar", "Apr"], fontsize=8)
    ax.set_ylabel("days per month, " + R["summary_band"]); ax.set_title("When each problem shows up"); ax.legend(fontsize=7)
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "decay_and_months.png"), dpi=140); plt.close(fig)

    # ---- example winter
    days = np.arange(len(Z["wx_P"]))
    fig, axs = plt.subplots(4, 1, figsize=(8.4, 8), sharex=True)
    ax = axs[0]
    ax.bar(days, Z["wx_P"], color="#2e86de", width=1.0); ax.set_ylabel("precip at 8,500 ft\n(mm water)")
    a2 = ax.twinx(); a2.plot(days, Z["wx_SL"] * FT, "k.", ms=4); a2.set_ylabel("snow level (ft)")
    ax.set_title("One simulated winter (random example, not a real season)")
    ax = axs[1]
    ax.plot(days, Z["wx_Tmax"], color="#d63031", lw=0.9, label="daily high")
    ax.plot(days, Z["wx_Tmin"], color="#2e86de", lw=0.9, label="daily low"); ax.axhline(0, color="k", lw=0.5)
    sa = Z["wx_santa"].astype(bool)
    ax.plot(days[sa], np.full(sa.sum(), ax.get_ylim()[1] * 0.92), "v", color="#e67e22", ms=4, label="Santa Ana wind")
    ax.set_ylabel("temp at 8,500 ft (C)"); ax.legend(ncol=3, fontsize=7, loc="lower right")
    ax = axs[2]
    swe = Z["ex_swe"]
    for a_i, c, l in [(0, "#2e86de", "north"), (2, "#27ae60", "east"), (4, "#d63031", "south")]:
        ax.plot(days, swe[:, 2, a_i], color=c, label=l + "-facing")
    ax.set_ylabel("snow on the ground\n(mm water), " + R["summary_band"]); ax.legend(fontsize=7)
    ax = axs[3]
    for k in cols:
        ax.plot(days, Z["ex_" + k][:, 3, 1], color=cols[k], lw=1.0, label=lab[k] + " (NE)")
    ax.plot(days, Z["ex_wet"][:, 3, 4], color="#e67e22", lw=1.0, ls="--", label="wet (S)")
    ax.axhline(0.45, color="gray", lw=0.6, ls=":"); ax.axhline(0.75, color="gray", lw=0.6, ls=":")
    ax.set_ylabel("model index\n" + R["high_band"]); ax.set_ylim(0, 1.6); ax.legend(ncol=5, fontsize=6, loc="upper center")
    ax.set_xticks([0, 16, 47, 78, 106, 137]); ax.set_xticklabels(["15 Nov", "1 Dec", "1 Jan", "1 Feb", "1 Mar", "1 Apr"])
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "example_winter.png"), dpi=140); plt.close(fig)

    # ---- markdown tables, one per area
    L = []
    areas = []
    for _slug, _name, area, *_ in PEAKS:
        if area not in areas:
            areas.append(area)
    for area in areas:
        L += ["", f"### {area}", "",
              "| Peak | Summit (ft) | 30-45 deg | Steep terrain mostly faces | N+NE+E share | Storm slab days | "
              "Wind slab days | Wet (% of snow days) | Persistent days | Freeze-thaw cycles | Snow-cover days |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
        for slug, _name, a, *_ in PEAKS:
            if a != area:
                continue
            s = stats[slug]
            L.append(f"| {s['name']} | {s['summit_ft']:,} | {s['pct_30_45']:.0f}% | {s['dominant_aspect']} | "
                     f"{s['lee_share_pct']:.0f}% | {s['model_days_storm']:.0f} | {s['model_days_wind']:.1f} | "
                     f"{s['wet_share_of_snow_days_pct']}% | {s['model_days_persistent']:.1f} | "
                     f"{s['model_days_ft']:.0f} | {s['model_days_snow']:.0f} |")
    open(os.path.join(ROOT, "results", "peaks_table.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
