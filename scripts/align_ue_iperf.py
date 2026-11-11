#!/usr/bin/env python3
"""Align the srsUE per-second timeline with the EPC-side iperf3 goodput series.

The iperf3 logs carry no wall-clock time, and srsUE occasionally skips a
one-second metrics line during RRC procedures, so a single offset does not
fit a whole run. The UE timeline is split into segments at RRC events; each
segment k is mapped to iperf3 seconds j = i + lag_k with lags non-decreasing
in time (skipped UE lines can only push the UE clock behind). Lags are chosen
by dynamic programming to maximise the covariance of the standardised
UE MAC uplink bitrate and TCP goodput series. Writes processed/ue_to_iperf_map.csv and processed/aligned_timeline.csv
(one row per iperf3 second, with the UE state mapped onto it where available).
"""
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "processed"
EV = ["rlf", "reest_reject", "reest_ok", "rrc_release", "sr_fail", "service_req_fail", "t301", "cell_unsuitable"]
LAGS = {"Location 2": range(380, 430), "Location 3": range(-90, 30), "Location 3, door closed": range(-60, 30)}
MAXSTEP = 12


def align(g, t, lags):
    ub = t.ul_brate_mbps.fillna(0).values
    zu = (ub - ub.mean()) / ub.std(); zg = (g - g.mean()) / g.std()
    seg = ((t[EV].sum(axis=1) > 0) | (t.state != t.state.shift())).cumsum().values
    segs = [np.where(seg == k)[0] for k in np.unique(seg)]
    L = list(lags)
    def cost(idx, lag):
        j = idx + lag
        ok = (j >= 0) & (j < len(g))
        c = -(zu[idx[ok]] * zg[j[ok]]).sum()    # negative covariance of standardised series
        return c + 5.0 * (~ok).sum()            # penalty for falling off the iperf series
    INF = 1e18
    D = np.full((len(segs), len(L)), INF); B = np.zeros((len(segs), len(L)), int)
    for b, lag in enumerate(L):
        D[0, b] = cost(segs[0], lag)
    for k in range(1, len(segs)):
        for b, lag in enumerate(L):
            lo = max(0, b - MAXSTEP)
            p = lo + int(np.argmin(D[k - 1, lo:b + 1]))
            D[k, b] = D[k - 1, p] + cost(segs[k], lag); B[k, b] = p
    b = int(np.argmin(D[-1])); lag_of = [0] * len(segs)
    for k in range(len(segs) - 1, -1, -1):
        lag_of[k] = L[b]; b = B[k, b]
    m = np.zeros(len(t), int)
    for k, idx in enumerate(segs):
        m[idx] = idx + lag_of[k]
    return m, lag_of, seg


rows, maps = [], []
ip = pd.read_csv(P / "iperf_uplink_timeseries.csv"); tl = pd.read_csv(P / "ue_timeline.csv")
for s, lags in LAGS.items():
    e = ip[(ip.scenario == s) & ip.side.str.startswith("EPC")].reset_index(drop=True)
    g = e.throughput_mbps.values
    t = tl[tl.scenario == s].reset_index(drop=True)
    m, lag_of, seg = align(g, t, lags)
    maps.append(pd.DataFrame({"scenario": s, "ue_line": range(len(t)), "iperf_second": m, "segment": seg}))
    a = pd.DataFrame({"scenario": s, "iperf_second": range(len(g)), "run": e.run, "goodput_mbps": g})
    for c in ["state", "rsrp_dbm", "dl_snr_db", "dl_mcs", "ul_mcs", "ul_brate_mbps", "ul_bler_pct"] + EV:
        a[c] = np.nan if c != "state" else "not logged"
    a["state"] = a["state"].astype(object)
    for i, j in enumerate(m):
        if 0 <= j < len(g):
            for c in ["state", "rsrp_dbm", "dl_snr_db", "dl_mcs", "ul_mcs", "ul_brate_mbps", "ul_bler_pct"] + EV:
                a.at[j, c] = t.at[i, c]
    ok = a.state == "connected"
    r = np.corrcoef(a.goodput_mbps[ok], a.ul_brate_mbps[ok])[0, 1]
    print(f"{s}: {len(lag_of)} segments, lag {lag_of[0]}..{lag_of[-1]}, UE rows mapped {((m>=0)&(m<len(g))).sum()}/{len(t)}, "
          f"corr(goodput, UE MAC UL bitrate) = {r:.3f}")
    rows.append(a)
pd.concat(rows).to_csv(P / "aligned_timeline.csv", index=False)
pd.concat(maps).to_csv(P / "ue_to_iperf_map.csv", index=False)
