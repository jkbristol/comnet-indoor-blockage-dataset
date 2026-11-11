#!/usr/bin/env python3
"""Within-run variability of the per-position metrics (revision, R1.4/R2.2).
Moving-block bootstrap (60-s blocks, 2000 resamples) over the active seconds of the
EPC-side iperf3 series, plus first-half/second-half values. Also UE-side uplink metrics
at L3 vs L3-DC. Writes processed/within_run_variability.csv."""
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]; P = ROOT / "processed"
al = pd.read_csv(P / "aligned_timeline.csv")
rng = np.random.default_rng(7); B, BL = 2000, 60
def act(d):
    g = d.goodput_mbps.values; k = len(g)
    while k and g[k - 1] == 0: k -= 1
    return g[:k]
rows = []
for s, d in al.groupby("scenario", sort=False):
    x = np.concatenate([act(dd) for _, dd in d.groupby("run")])
    n = len(x); starts = np.arange(n - BL + 1)
    def boot(f):
        v = []
        for _ in range(B):
            idx = np.concatenate([np.arange(st, st + BL) for st in rng.choice(starts, int(np.ceil(n / BL)))])[:n]
            v.append(f(x[idx]))
        return np.percentile(v, [2.5, 97.5])
    zf = lambda y: (y == 0).mean() * 100
    def outr(y):
        z = (y == 0).astype(int); return ((np.diff(np.r_[0, z]) == 1).sum()) / len(y) * 600
    h = n // 2
    bm, bz, bo = boot(np.mean), boot(zf), boot(outr)
    rows.append(dict(scenario=s, n=n, mean=x.mean(), mean_lo=bm[0], mean_hi=bm[1],
                     zero_pct=zf(x), zero_lo=bz[0], zero_hi=bz[1],
                     outages_10min=outr(x), out_lo=bo[0], out_hi=bo[1],
                     mean_h1=x[:h].mean(), mean_h2=x[h:].mean(), zero_h1=zf(x[:h]), zero_h2=zf(x[h:]),
                     out_h1=outr(x[:h]), out_h2=outr(x[h:])))
R = pd.DataFrame(rows); print(R.round(2).T.to_string()); R.to_csv(P / "within_run_variability.csv", index=False, float_format="%.3f")
ue = pd.read_csv(P / "ue_phy_metrics.csv")
print("\nUE-side metrics, L3 vs L3-DC (median / mean)")
for c in ["dl_snr_db", "rsrp_dbm", "ul_mcs", "ul_bler_pct", "ul_brate_mbps", "dl_bler_pct", "ul_buffer_mb"]:
    a = ue[ue.scenario == "Location 3"][c]; b = ue[ue.scenario == "Location 3, door closed"][c]
    print(f"  {c:14s} L3 {a.median():7.2f} / {a.mean():7.2f}   L3-DC {b.median():7.2f} / {b.mean():7.2f}")
