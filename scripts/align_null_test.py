#!/usr/bin/env python3
"""Null test for the piecewise alignment: re-run it against the iperf3 series
reversed in time, and against circularly shifted copies, to see how much
correlation the segment-wise lag freedom produces on its own."""
import importlib.util, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("al", ROOT / "scripts" / "align_ue_iperf.py")
src = (ROOT / "scripts" / "align_ue_iperf.py").read_text().split("\nrows = []")[0]
ns = {"__file__": str(ROOT / "scripts" / "align_ue_iperf.py")}; exec(compile(src, "align", "exec"), ns)
ip = pd.read_csv(ROOT / "processed/iperf_uplink_timeseries.csv"); tl = pd.read_csv(ROOT / "processed/ue_timeline.csv")
rng = np.random.default_rng(1); out = []
for s, lags in ns["LAGS"].items():
    g0 = ip[(ip.scenario == s) & ip.side.str.startswith("EPC")].throughput_mbps.values
    t = tl[tl.scenario == s].reset_index(drop=True)
    def score(g):
        m, _ = ns["align"](g, t, lags); ok = (m >= 0) & (m < len(g)) & (t.state.values == "connected")
        return np.corrcoef(t.ul_brate_mbps.values[ok], g[m[ok]])[0, 1]
    real = score(g0)
    null = [score(np.roll(g0, int(rng.integers(60, len(g0) - 60)))) for _ in range(20)] + [score(g0[::-1].copy())]
    out.append(dict(scenario=s, r_aligned=real, r_null_median=np.nanmedian(null), r_null_max=np.nanmax(null)))
print(pd.DataFrame(out).round(3).to_string(index=False))
pd.DataFrame(out).to_csv(ROOT / "processed/alignment_null_test.csv", index=False, float_format="%.3f")
