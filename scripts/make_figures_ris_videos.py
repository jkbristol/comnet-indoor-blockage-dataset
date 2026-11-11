#!/usr/bin/env python3
"""Figures from the OCR-derived readings of the RIS-period screen recordings.

Reads processed/ris_videos/*.csv. Values are screen-recording transcriptions,
not machine logs; see README and the article for the validation rule.
"""
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
P, F = ROOT / "processed" / "ris_videos", ROOT / "figures"
INK, MUTED, GRID = "#1f1f1e", "#6b6a64", "#e6e5df"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8, "axes.edgecolor": MUTED,
                     "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": True, "grid.color": GRID,
                     "grid.linewidth": 0.6, "axes.axisbelow": True, "savefig.dpi": 300, "savefig.bbox": "tight"})

inv = pd.read_csv(P / "video_inventory.csv").set_index("file")
iv = pd.read_csv(P / "iperf_readings_interval.csv")
ps = pd.read_csv(P / "iperf_readings_per_second_frame.csv")
snr = pd.read_csv(P / "matlab_snr_per_configuration.csv")

# Panel (a): distribution per video (videos with >= 15 validated readings)
LAB = {
    "matlab_scripts_check_in_los__without_ris_in_robotics_lab.mp4": "R1  LOS, no RIS",
    "bit_rate_in_nlos_wwithout_ris_in_robotics_lab.mp4": "R2  NLOS, no RIS",
    "ris_on_case__with_no_enhancement__in_robotics_lab.mp4": "R3  RIS on, 'no enhancement'",
    "ris_off_case_in_robotics_lab.mp4": "R4  RIS off",
    "ris_configuration_before_runiing_experiment_in_mast_lab.mp4": "M1  before RIS run",
    "nlos_ris_enhaced_in_mast_lab.mp4": "M2  NLOS, RIS on",
    "ris_off_traffic.mp4": "U1  RIS off (room not shown)",
}
COL = {"R": "#2a78d6", "M": "#eb6834", "U": "#8a8984"}
data = [(lab, iv[iv.video == f].bitrate_mbps.values) for f, lab in LAB.items()]
data = [(l, v) for l, v in data if len(v) >= 15]

fig, axs = plt.subplots(1, 2, figsize=(7.2, 2.9), gridspec_kw=dict(width_ratios=[1.05, 1]))
ax = axs[0]
for i, (lab, v) in enumerate(data):
    c = COL[lab[0]]
    b = ax.boxplot([v], positions=[i], vert=False, widths=0.55, patch_artist=True, showfliers=False,
                   medianprops=dict(color=INK, lw=1.2), whiskerprops=dict(color=MUTED), capprops=dict(color=MUTED))
    b["boxes"][0].set(facecolor=c, alpha=0.8, edgecolor="white")
    ax.text(14.6, i, f"n={len(v)}", va="center", ha="right", fontsize=6.5, color=MUTED)
ax.set_yticks(range(len(data)), [l for l, _ in data], fontsize=6.8)
ax.invert_yaxis()
ax.set_xlim(0, 15); ax.set_xlabel("iperf3 bitrate (Mbit/s), per 1-s interval")
ax.set_title("(a) Per recording (R: robotics lab, M: mast lab)", fontsize=7.5, loc="left", color=INK)
ax.grid(axis="y", visible=False)

# Panel (b): RIS configuration sweep recording, per-second bottom-line reading
ax = axs[1]
d = ps[ps.video == "ris_configuration_in_mast_lab.mp4"]
ax.plot(d.frame_s, d.bottom_consistent_bitrate_mbps, color="#eb6834", lw=1.0, marker="o", ms=2.2)
ax.set_xlabel("Recording time (s)"); ax.set_ylabel("iperf3 bitrate (Mbit/s)")
ax.set_ylim(0, 14)
lo, hi = snr.snr_db.min(), snr.snr_db.max()
ax.set_title(f"(b) Sweep recording, configs 133-141", fontsize=7.5, loc="left", color=INK)
fig.tight_layout(w_pad=1.5)
for ext in ("pdf", "png"):
    fig.savefig(F / f"fig_ris_recordings.{ext}")
print([(l, len(v), round(float(pd.Series(v).median()), 2)) for l, v in data])
print("sweep readings:", len(d), "median", d.bottom_consistent_bitrate_mbps.median())
