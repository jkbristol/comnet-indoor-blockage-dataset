#!/usr/bin/env python3
"""Figures and summary table for the 11 March 2025 location campaign.

Reads only processed/*.csv produced by parse_march2025.py.
Writes figures/*.pdf|png and processed/summary_march2025.csv.
"""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
P, F = ROOT / "processed", ROOT / "figures"
F.mkdir(exist_ok=True)

ORDER = ["Location 2", "Location 3", "Location 3, door closed"]
SHORT = {"Location 2": "L2", "Location 3": "L3", "Location 3, door closed": "L3-DC"}
COL = {"Location 2": "#2a78d6", "Location 3": "#eb6834", "Location 3, door closed": "#1baf7a"}
INK, MUTED, GRID = "#1f1f1e", "#6b6a64", "#e6e5df"

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8, "axes.edgecolor": MUTED,
                     "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
                     "savefig.dpi": 300, "savefig.bbox": "tight"})

ip = pd.read_csv(P / "iperf_uplink_timeseries.csv")
ue = pd.read_csv(P / "ue_phy_metrics.csv")
vq = pd.read_csv(P / "video_stream_qoe.csv", parse_dates=["timestamp_utc"])
epc = ip[ip.side.str.startswith("EPC")].copy()


def _active(x):
    """True except for the final continuous zero-goodput period of a run (revision: applied per run)."""
    k = len(x)
    while k > 0 and x[k - 1] == 0:
        k -= 1
    return np.arange(len(x)) < k


epc["active"] = epc.groupby(["scenario", "run"]).throughput_mbps.transform(lambda x: _active(x.values))


def box(ax, data, ylabel, title):
    vals = [data[s].dropna().values for s in ORDER]
    b = ax.boxplot(vals, widths=0.5, patch_artist=True, showfliers=False,
                   medianprops=dict(color=INK, lw=1.2), whiskerprops=dict(color=MUTED),
                   capprops=dict(color=MUTED))
    for patch, s in zip(b["boxes"], ORDER):
        patch.set(facecolor=COL[s], alpha=0.85, edgecolor="white", linewidth=1)
    ax.set_xticks(range(1, 4), [SHORT[s] for s in ORDER])
    ax.set_ylabel(ylabel)
    ax.set_title(title, fontsize=8.5, color=INK, loc="left")
    ax.grid(axis="x", visible=False)


# ---- Figure 1: cross-layer degradation (4 panels)
fig, axs = plt.subplots(1, 4, figsize=(7.2, 2.2))
box(axs[0], {s: ue[ue.scenario == s].dl_snr_db for s in ORDER}, "dB", "(a) DL SNR (UE)")
box(axs[1], {s: ue[ue.scenario == s].dl_mcs for s in ORDER}, "index", "(b) DL MCS (UE)")
box(axs[2], {s: ue[ue.scenario == s].ul_bler_pct for s in ORDER}, "%", "(c) UL BLER (UE)")
box(axs[3], {s: epc[(epc.scenario == s) & epc.active].throughput_mbps for s in ORDER}, "Mbit/s", "(d) UL TCP goodput")
fig.tight_layout(w_pad=1.2)
for ext in ("pdf", "png"):
    fig.savefig(F / f"fig_crosslayer_boxplots.{ext}")
plt.close(fig)

# ---- Figure 2: uplink goodput time series (small multiples, shared y)
fig, axs = plt.subplots(3, 1, figsize=(7.2, 3.6), sharey=True)
for ax, s in zip(axs, ORDER):
    d = epc[epc.scenario == s].reset_index(drop=True)
    ax.plot(np.arange(len(d)), d.throughput_mbps, color=COL[s], lw=0.8)
    zero = (d.throughput_mbps == 0).mean() * 100
    ax.set_title(f"{s}: {len(d)} one-second samples, {zero:.0f}% at zero", fontsize=8, color=INK, loc="left")
    ax.set_ylabel("Mbit/s")
axs[-1].set_xlabel("Sample index (1 s per sample; concatenated iperf3 runs)")
fig.tight_layout(h_pad=0.6)
for ext in ("pdf", "png"):
    fig.savefig(F / f"fig_uplink_timeseries.{ext}")
plt.close(fig)

# ---- Figure 3: video stream QoE per session (cumulative packet loss and PLI requests)
sess = list(dict.fromkeys(vq.session))
cols = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]
fig, axs = plt.subplots(1, 2, figsize=(7.2, 2.4))
for c, s in zip(cols, sess):
    d = vq[vq.session == s]
    t = (d.timestamp_utc - d.timestamp_utc.iloc[0]).dt.total_seconds() / 60
    axs[0].plot(t, d.packet_loss_pct, color=c, lw=1.2, label=s)
    axs[1].plot(t, d.pli_count, color=c, lw=1.2, label=s)
axs[0].set_ylabel("Reported packet loss (%)"); axs[0].set_xlabel("Minutes from session start")
axs[1].set_ylabel("Cumulative PLI requests"); axs[1].set_xlabel("Minutes from session start")
fig.legend(*axs[1].get_legend_handles_labels(), fontsize=6.5, frameon=False, loc="lower center", ncol=3, bbox_to_anchor=(0.5, -0.12))
fig.tight_layout()
for ext in ("pdf", "png"):
    fig.savefig(F / f"fig_video_qoe.{ext}")
plt.close(fig)

# ---- Summary table
rows = []
for s in ORDER:
    u, e = ue[ue.scenario == s], epc[epc.scenario == s]
    x = e.throughput_mbps.values
    xt = e[e.active].throughput_mbps.values   # final zero period of every run removed
    k = len(xt)
    rows.append(dict(scenario=s, ue_samples=len(u), rsrp_dbm_mean=u.rsrp_dbm.mean(),
                     dl_snr_db_mean=u.dl_snr_db.mean(), dl_snr_db_sd=u.dl_snr_db.std(),
                     dl_mcs_median=u.dl_mcs.median(), dl_bler_pct_mean=u.dl_bler_pct.mean(),
                     ul_bler_pct_mean=u.ul_bler_pct.mean(), iperf_samples=len(e),
                     ul_goodput_mbps_mean=e.throughput_mbps.mean(), ul_goodput_mbps_median=e.throughput_mbps.median(),
                     ul_goodput_mbps_sd=e.throughput_mbps.std(), zero_goodput_pct=(e.throughput_mbps == 0).mean() * 100,
                     final_zero_tail_s=len(x) - k, ul_goodput_mbps_mean_excl_tail=xt.mean(),
                     ul_goodput_mbps_median_excl_tail=np.median(xt), zero_goodput_pct_excl_tail=(xt == 0).mean() * 100))
sm = pd.DataFrame(rows)
sm.to_csv(P / "summary_march2025.csv", index=False, float_format="%.3f")

vs = vq.groupby("session", sort=False).agg(rows=("fps", "size"),
        duration_min=("timestamp_utc", lambda t: (t.max() - t.min()).total_seconds() / 60),
        latency_ms_median=("latency_ms", "median"), latency_missing_pct=("latency_ms", lambda x: x.isna().mean() * 100),
        final_packet_loss_pct=("packet_loss_pct", lambda x: x.dropna().iloc[-1]),
        jitter_ms_median=("jitter_ms", "median"), pli_total=("pli_count", "max"), pauses_total=("pause_count", "max"))
vs.to_csv(P / "summary_video_qoe.csv", float_format="%.3f")
print(sm.round(2).to_string()); print(vs.round(2).to_string())
