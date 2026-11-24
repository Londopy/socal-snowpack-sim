"""Run 400 simulated SoCal winters through the daily snowpack model.

This is a TOY MODEL for learning. The weather is randomly generated from
rough SoCal-like statistics, and the snowpack rules are simplified textbook
relationships. Nothing here is calibrated against measurements, and it is
not an avalanche forecast. The model itself lives in src/socal_snowpack.

Usage:  python src/model.py        (writes results/model.json and data/model.npz)
"""
import json
import os

import numpy as np

from socal_snowpack.daily import run_season
from socal_snowpack.grid import ASP_NAMES, BAND_EDGES_M, BAND_NAMES, HIGH_B, MID, NB, NDAYS, PROBLEMS
from socal_snowpack.params import load_params
from socal_snowpack.solar import solar_tables
from socal_snowpack.weather import make_season, month_of

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main(n_seasons=400, seed=7):
    p = load_params()
    elevated, high = p.levels.considerable, p.levels.high
    rng = np.random.default_rng(seed)
    gmean, gpeak = solar_tables(p)
    days = {k: np.zeros((NB, 8)) for k in PROBLEMS + ["any", "high", "ice", "ice_allday", "ft", "corn", "snow"]}
    monthly = {m: {k: 0.0 for k in PROBLEMS + ["any", "ice", "snow"]} for m in [11, 12, 1, 2, 3, 4]}
    months = np.array([month_of(d) for d in range(NDAYS)])
    after_storm = {"N": np.zeros(8), "S": np.zeros(8), "n": np.zeros(8)}
    season_any = []
    cands = []
    wets = []
    peak_swe = []
    snowfall = []
    for s in range(n_seasons):
        wx = make_season(rng, p)
        o = run_season(wx, gmean, gpeak, p)
        stack = np.stack([o[k] for k in PROBLEMS])
        idx = stack.max(axis=0)
        snow = o["swe"] > 20
        for i, k in enumerate(PROBLEMS):
            days[k] += (stack[i] >= elevated).sum(axis=0)
        days["any"] += (idx >= elevated).sum(axis=0)
        days["high"] += (idx >= high).sum(axis=0)
        days["ice"] += (o["ice"] >= 0.5).sum(axis=0)
        days["ice_allday"] += (o["ice"] >= 1.0).sum(axis=0)
        days["snow"] += snow.sum(axis=0)
        days["ft"] += o["ft"].sum(axis=0)
        days["corn"] += o["corn"].sum(axis=0)
        for m in monthly:
            sel = months == m
            for i, k in enumerate(PROBLEMS):
                monthly[m][k] += (stack[i][sel, MID] >= elevated).mean(axis=1).sum()
            monthly[m]["any"] += (idx[sel, MID] >= elevated).mean(axis=1).sum()
            monthly[m]["ice"] += (o["ice"][sel, MID] >= 0.5).mean(axis=1).sum()
            monthly[m]["snow"] += snow[sel, MID].mean(axis=1).sum()
        # hazard decay after the last day of each storm (upper band)
        st = wx["storm"]
        for d in range(NDAYS - 8):
            if st[d] and not st[d + 1] and wx["P"][d] > 14 and wx["SL"][d] < 2700:
                if not st[d + 1:d + 8].any():
                    after_storm["N"] += idx[d:d + 8, HIGH_B, 0]
                    after_storm["S"] += idx[d:d + 8, HIGH_B, 4]
                    after_storm["n"] += 1
        season_any.append((idx[:, MID, :] >= elevated).any(axis=1).sum())
        wets.append(wx["wet"])
        peak_swe.append(o["swe"][:, MID, 0].max())
        snowfall.append(o["snowfall"])
        if s < 40:
            cands.append((o["snowfall"][MID], dict(
                wx={k: np.asarray(v) for k, v in wx.items() if k != "wet"},
                out={k: v for k, v in o.items() if k != "snowfall"})))

    n = float(n_seasons)
    target = np.mean([c[0] for c in cands])          # a roughly average winter
    example = min(cands, key=lambda c: abs(c[0] - target))[1]
    res = {
        "n_seasons": n_seasons,
        "aspects": ASP_NAMES, "bands": BAND_NAMES, "band_edges_m": BAND_EDGES_M.tolist(),
        "summary_band": BAND_NAMES[MID], "high_band": BAND_NAMES[HIGH_B],
        "days": {k: (v / n).round(2).tolist() for k, v in days.items()},
        "wet_share_of_snow_days_pct": (100 * days["wet"] / np.maximum(days["snow"], 1)).round(0).tolist(),
        "ice_share_of_snow_days_pct": (100 * days["ice"] / np.maximum(days["snow"], 1)).round(0).tolist(),
        "monthly": {str(m): {k: round(float(v) / n, 2) for k, v in d.items()} for m, d in monthly.items()},
        "after_storm": {"N": (after_storm["N"] / after_storm["n"]).round(3).tolist(),
                        "S": (after_storm["S"] / after_storm["n"]).round(3).tolist()},
        "season_any_days": {"p10": float(np.percentile(season_any, 10)),
                            "median": float(np.median(season_any)),
                            "p90": float(np.percentile(season_any, 90))},
        "snowfall_mm_water_by_band": {"mean": np.mean(snowfall, axis=0).round(0).tolist(),
                                      "p10": np.percentile(snowfall, 10, axis=0).round(0).tolist(),
                                      "p50": np.percentile(snowfall, 50, axis=0).round(0).tolist(),
                                      "p90": np.percentile(snowfall, 90, axis=0).round(0).tolist()},
        "peak_swe_mm_north_summary_band": {"p10": float(np.percentile(peak_swe, 10)),
                              "median": float(np.median(peak_swe)),
                              "p90": float(np.percentile(peak_swe, 90))},
    }
    os.makedirs(os.path.join(ROOT, "results"), exist_ok=True)
    os.makedirs(os.path.join(ROOT, "data"), exist_ok=True)
    with open(os.path.join(ROOT, "results", "model.json"), "w") as f:
        json.dump(res, f, indent=1)
    np.savez_compressed(os.path.join(ROOT, "data", "model.npz"),
                        **{"ex_" + k: v for k, v in example["out"].items()},
                        **{"wx_" + k: v for k, v in example["wx"].items()},
                        **{"days_" + k: v / n for k, v in days.items()})
    return res


if __name__ == "__main__":
    r = main()
    print(json.dumps({k: r[k] for k in ["season_any_days", "snowfall_mm_water_by_band", "peak_swe_mm_north_summary_band", "after_storm"]}, indent=1))
    for k in PROBLEMS + ["any", "high", "ice", "ice_allday", "ft", "corn", "snow"]:
        print(k)
        for b in range(NB - 1, -1, -1):
            print("  ", BAND_NAMES[b].ljust(20), " ".join(f"{v:5.1f}" for v in r["days"][k][b]))
    print("      aspects:         ", "     ".join(ASP_NAMES))
    for m, v in r["monthly"].items():
        print(m, v)
