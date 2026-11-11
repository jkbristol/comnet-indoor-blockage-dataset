#!/usr/bin/env python3
"""Figures added in the revision: time-aligned cross-layer timeline (L3, L3-DC)
and superposed epochs around radio-link failures. Writes figures/fig_aligned_timeline.*
and figures/fig_rlf_epochs.*"""
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
ROOT = Path(__file__).resolve().parents[1]; P, F, RAW = ROOT / "processed", ROOT / "figures", ROOT / "raw" / "march2025_locations"
F.mkdir(exist_ok=True)
INK, MUTED, GRID = "#1f1f1e", "#6b6a64", "#e6e5df"
BLUE, ORANGE, GREEN = "#2a78d6", "#eb6834", "#1baf7a"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 7.5, "axes.edgecolor": MUTED, "axes.labelcolor": INK,
                     "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
                     "savefig.dpi": 300, "savefig.bbox": "tight"})
al = pd.read_csv(P / "aligned_timeline.csv"); tl = pd.read_csv(P / "ue_timeline.csv"); mp = pd.read_csv(P / "ue_to_iperf_map.csv")
T0 = {"Location 3": "2025-03-11T15:21:13", "Location 3, door closed": "2025-03-11T15:56:03"}
VID = {"Location 3": "video_1522_loc3.csv", "Location 3, door closed": "video_1557_doorclosed.csv"}
TITLE = {"Location 3": "L3 (door open)", "Location 3, door closed": "L3-DC (door closed)"}

def pli_seconds(s):
    m = mp[mp.scenario == s].merge(tl[tl.scenario == s][["second", "ul_brate_mbps"]], left_on="ue_line", right_on="second")
    ref = m[m.ul_brate_mbps.fillna(0) > 0.5].ue_line.min(); j0 = m.loc[m.ue_line == ref, "iperf_second"].iloc[0]
    t_ref = pd.Timestamp(T0[s]) + pd.to_timedelta(ref, unit="s")
    v = pd.read_csv(RAW / VID[s]); v["t"] = pd.to_datetime(v.Timestamp).dt.tz_localize(None)
    x = pd.to_numeric(v["PLI Count"], errors="coerce").ffill()
    return ((v.t[x.diff() > 0] - t_ref).dt.total_seconds() + j0).values

fig, ax = plt.subplots(4, 2, figsize=(7.2, 6.0), sharex="col", gridspec_kw=dict(width_ratios=[890, 330], hspace=0.12, wspace=0.12))
for c, s in enumerate(["Location 3", "Location 3, door closed"]):
    a = al[al.scenario == s].copy()
    g = a.goodput_mbps.values; k = len(g)
    while k and g[k - 1] == 0: k -= 1
    a = a[a.iperf_second < k + 15]
    t = a.iperf_second
    rl = a[a.rlf > 0].iperf_second.values
    gap = a.state != "connected"
    for r in range(4):
        A = ax[r, c]
        for j in rl: A.axvline(j, color=ORANGE, lw=0.8, alpha=0.9, zorder=1)
        for j in a[gap].iperf_second: A.axvspan(j - .5, j + .5, color="#d9d8d2", lw=0, zorder=0)
        A.axvline(k, color=MUTED, lw=0.8, ls="--")
    ax[0, c].plot(t, a.goodput_mbps, color=BLUE, lw=0.8, label="TCP goodput (EPC iperf3)")
    ax[0, c].plot(t, a.ul_brate_mbps, color=INK, lw=0.6, alpha=0.55, label="UE MAC UL bitrate")
    pl = pli_seconds(s); pl = pl[(pl >= t.min()) & (pl <= t.max())]
    ax[0, c].plot(pl, np.full(len(pl), 4.6), marker="v", ls="none", ms=4, color=GREEN, label="video PLI request")
    ax[0, c].set_ylim(-0.2, 5)
    ax[1, c].plot(t, a.dl_snr_db, color=INK, lw=0.7); ax[1, c].set_ylim(0, 12)
    ax[2, c].plot(t, a.ul_mcs, color=INK, lw=0.7); ax[2, c].set_ylim(-1, 26)
    ax[3, c].plot(t, a.ul_bler_pct, color=INK, lw=0.7); ax[3, c].set_ylim(-2, 80)
    ax[0, c].set_title(TITLE[s], color=INK, fontsize=8, loc="left")
    ax[3, c].set_xlabel("iperf3 time (s)")
for r, lab in enumerate(["Uplink rate\n(Mbit/s)", "DL SNR at UE\n(dB)", "UL MCS\n(UE)", "UL BLER at UE\n(%)"]):
    ax[r, 0].set_ylabel(lab)
h, l = ax[0, 0].get_legend_handles_labels()
h += [plt.Line2D([], [], color=ORANGE, lw=1), plt.Rectangle((0, 0), 1, 1, color="#d9d8d2"), plt.Line2D([], [], color=MUTED, lw=0.8, ls="--")]
l += ["radio-link failure (srsUE)", "UE not RRC-connected", "start of final zero-goodput period"]
fig.legend(h, l, loc="upper center", ncol=3, frameon=False, bbox_to_anchor=(0.5, 1.03))
for e in ["pdf", "png"]: fig.savefig(F / f"fig_aligned_timeline.{e}")

# superposed epochs
ep = pd.read_csv(P / "rlf_epochs.csv"); ep = ep[ep.scenario != "Location 2"]
fig, ax = plt.subplots(1, 4, figsize=(7.2, 1.9), sharex=True, gridspec_kw=dict(wspace=0.45))
for A, (col, lab, f) in zip(ax, [("goodput", "TCP goodput (Mbit/s)", "mean"), ("dl_snr", "DL SNR (dB)", "mean"),
                                 ("ul_bler", "UL BLER (%)", "mean"), ("connected", "UE RRC-connected (share)", "mean")]):
    m = ep.groupby("k")[col].agg(["mean", "count", "std"])
    se = m["std"] / np.sqrt(m["count"])
    A.fill_between(m.index, m["mean"] - se, m["mean"] + se, color=BLUE, alpha=0.18, lw=0)
    A.plot(m.index, m["mean"], color=BLUE, lw=1.6)
    A.axvline(0, color=ORANGE, lw=0.8); A.set_title(lab, fontsize=7.5, color=INK, loc="left"); A.set_xlabel("s from RLF")
for e in ["pdf", "png"]: fig.savefig(F / f"fig_rlf_epochs.{e}")
print("ok")
