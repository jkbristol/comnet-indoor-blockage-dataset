#!/usr/bin/env python3
"""Additional analysis for the research article: link adaptation, outages, RLF rate.

Reads processed/*.csv and raw UE traces. Writes figures/fig_link_adaptation.*,
figures/fig_outage_ccdf.* and processed/paper_metrics.csv.
"""
from pathlib import Path
import re, subprocess
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
P, F, RAW = ROOT / "processed", ROOT / "figures", ROOT / "raw" / "march2025_locations"
ORDER = ["Location 2", "Location 3", "Location 3, door closed"]
SHORT = {"Location 2": "L2", "Location 3": "L3", "Location 3, door closed": "L3-DC"}
COL = {"Location 2": "#2a78d6", "Location 3": "#eb6834", "Location 3, door closed": "#1baf7a"}
INK, MUTED, GRID = "#1f1f1e", "#6b6a64", "#e6e5df"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8, "axes.edgecolor": MUTED,
                     "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": True, "grid.color": GRID,
                     "grid.linewidth": 0.6, "axes.axisbelow": True, "savefig.dpi": 300, "savefig.bbox": "tight"})

ip = pd.read_csv(P / "iperf_uplink_timeseries.csv")
epc = ip[ip.side.str.startswith("EPC")]
ue = pd.read_csv(P / "ue_phy_metrics.csv")
enb = pd.read_csv(P / "enb_mac_metrics.csv")

# ---------------------------------------------------------------- outages
def outages(x):
    k = len(x)
    while k > 0 and x[k - 1] == 0:
        k -= 1
    out, run = [], 0
    for v in x[:k] == 0:
        if v:
            run += 1
        elif run:
            out.append(run); run = 0
    if run:
        out.append(run)
    return out, k

rows, dur = [], {}
for s in ORDER:
    d = epc[epc.scenario == s]
    o, active = [], 0
    for _, dd in d.groupby("run"):
        oo, k = outages(dd.throughput_mbps.values)
        o += oo; active += k
    dur[s] = np.array(o)
    x = np.concatenate([dd.throughput_mbps.values[:outages(dd.throughput_mbps.values)[1]] for _, dd in d.groupby("run")])  # active seconds
    rows.append(dict(scenario=s, active_s=active, n_outages=len(o),
                     outages_per_10min=len(o) / active * 600, outage_median_s=float(np.median(o)) if o else 0,
                     outage_max_s=max(o) if o else 0, outages_ge_5s=int((np.array(o) >= 5).sum()),
                     pct_s_below_1mbps=(x < 1).mean() * 100, pct_s_below_5mbps=(x < 5).mean() * 100))

# ---------------------------------------------------------------- radio-link failures from srsUE console
TR = {"Location 2": "loc2_ue_trace.odt", "Location 3": "loc3_ue_trace.odt", "Location 3, door closed": "loc3_doorclosed_ue_trace.odt"}
for r in rows:
    t = subprocess.run(["pandoc", "-f", "odt", "-t", "plain", str(RAW / TR[r["scenario"]])],
                       capture_output=True, text=True, check=True).stdout
    n_s = (ue.scenario == r["scenario"]).sum()          # one metrics line per second
    r["rlf_events"] = len(re.findall(r"Detected Radio-Link Failure", t))
    r["reestablishment_rejects"] = len(re.findall(r"Reestablishment Reject", t))
    r["ue_metric_seconds"] = int(n_s)
    r["rlf_per_10min_ue_metric_lines"] = r["rlf_events"] / n_s * 600
pm = pd.DataFrame(rows)
pm.to_csv(P / "paper_metrics.csv", index=False, float_format="%.3f")
print(pm.round(2).to_string())

# ---------------------------------------------------------------- Fig: link adaptation
# eNB rows with uplink traffic. All RNTIs in these logs are C-RNTIs of our UE (checked against the srsUE
# 'Random Access Complete' lines, see crosslayer_revision.py). The last 144 rows of the L2 eNB log (C-RNTIs 0x75 and
# 0x81, after the uplink test traffic had stopped: ~0.24 Mbit/s at MCS 14-16 with PUSCH SNR > 30 dB) do not show link
# adaptation under load and are excluded; with them the correlation is 0.864 (reported in the paper).
a = enb[enb.ul_pusch_snr_db.notna() & ((enb.ul_ok + enb.ul_nok) > 0) & ~enb.rnti.isin(["75", "81"])]
fig, axs = plt.subplots(1, 3, figsize=(7.2, 2.3))
for s in ["Location 2", "Location 3, door closed"]:
    d = a[a.scenario == s]
    axs[0].scatter(d.ul_pusch_snr_db, d.ul_mcs + np.random.default_rng(0).uniform(-.25, .25, len(d)),
                   s=4, alpha=.35, color=COL[s], label=SHORT[s], linewidths=0)
    axs[1].scatter(d.ul_pusch_snr_db, d.ul_brate_mbps, s=4, alpha=.35, color=COL[s], linewidths=0)
for s in ORDER:
    d = ue[ue.scenario == s]
    axs[2].scatter(d.dl_snr_db + np.random.default_rng(1).uniform(-.25, .25, len(d)),
                   d.dl_mcs + np.random.default_rng(2).uniform(-.25, .25, len(d)),
                   s=4, alpha=.35, color=COL[s], label=SHORT[s], linewidths=0)
axs[0].set(xlabel="PUSCH SNR at eNB (dB)", ylabel="UL MCS"); axs[0].set_title("(a) UL link adaptation", fontsize=8, loc="left")
axs[1].set(xlabel="PUSCH SNR at eNB (dB)", ylabel="UL MAC bitrate (Mbit/s)"); axs[1].set_title("(b) UL MAC bitrate", fontsize=8, loc="left")
axs[2].set(xlabel="DL SNR at UE (dB)", ylabel="DL MCS"); axs[2].set_title("(c) DL link adaptation", fontsize=8, loc="left")
axs[2].legend(fontsize=6.5, frameon=False, markerscale=2.5, loc="upper left")
fig.tight_layout(w_pad=1.2)
for ext in ("pdf", "png"):
    fig.savefig(F / f"fig_link_adaptation.{ext}")
plt.close(fig)
print("eNB rows used:", len(a), a.groupby("scenario").size().to_dict(),
      "corr(snr,mcs) UL", round(np.corrcoef(a.ul_pusch_snr_db, a.ul_mcs)[0, 1], 3),
      "DL", round(np.corrcoef(ue.dl_snr_db, ue.dl_mcs)[0, 1], 3))

# ---------------------------------------------------------------- Fig: outage duration CCDF
fig, ax = plt.subplots(figsize=(3.5, 2.3))
for s in ORDER:
    o = np.sort(dur[s])
    if len(o):
        ccdf = 1 - np.arange(len(o)) / len(o)
        ax.step(o, ccdf, where="post", color=COL[s], lw=1.6, label=f"{SHORT[s]} (n={len(o)})")
ax.set_xscale("log"); ax.set_xticks([1, 2, 5, 10, 20, 40], ["1", "2", "5", "10", "20", "40"]); ax.minorticks_off(); ax.set_xlabel("Zero-goodput period (s)"); ax.set_ylabel("P(duration ≥ x)")
ax.legend(fontsize=6.5, frameon=False)
fig.tight_layout()
for ext in ("pdf", "png"):
    fig.savefig(F / f"fig_outage_ccdf.{ext}")
