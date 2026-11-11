#!/usr/bin/env python3
"""Split the undated mast-lab / mini-room iperf3 logs into runs.

Location for dataset1 and RIS state for every run were not recorded.
Writes processed/mastlab_runs.csv (one row per run) and
processed/mastlab_timeseries.csv (one row per 1-s interval).
"""
import re, subprocess
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parents[1]
RAW, OUT = ROOT / "raw" / "mastlab_sessions", ROOT / "processed"
U = {"": 1e-6, "K": 1e-3, "M": 1.0, "G": 1e3}
L = re.compile(r"\]\s+(\d+\.\d+)-(\d+\.\d+)\s+sec\s+[\d.]+\s+\w?Bytes\s+([\d.]+)\s+(\w?)bits/sec")

def text(p):
    if p.suffix == ".odt":
        return subprocess.run(["pandoc", "-f", "odt", "-t", "plain", "--wrap=none", str(p)], capture_output=True, text=True, check=True).stdout
    return p.read_text(errors="ignore")

rows, ts = [], []
for f in sorted(RAW.iterdir()):
    run, cmd = None, None
    for line in text(f).splitlines():
        if "iperf3 -c" in line or "Accepted connection" in line:
            run = (run or 0) + 1; cmd = line.split("$")[-1].strip(); continue
        m = L.search(line)
        if m and run and float(m.group(2)) - float(m.group(1)) <= 1.01:
            ts.append(dict(source_file=f.name, run=run, command=cmd, t_end_s=float(m.group(2)),
                           throughput_mbps=float(m.group(3)) * U[m.group(4)]))
t = pd.DataFrame(ts)
t.to_csv(OUT / "mastlab_timeseries.csv", index=False)
r = t.groupby(["source_file", "run", "command"], sort=False).throughput_mbps.agg(
    samples="size", mean_mbps="mean", median_mbps="median", zero_pct=lambda x: (x == 0).mean() * 100).reset_index()
r.to_csv(OUT / "mastlab_runs.csv", index=False, float_format="%.3f")
print(r.round(2).to_string())
