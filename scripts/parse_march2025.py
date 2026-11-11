#!/usr/bin/env python3
"""Parse the raw 11 March 2025 location-campaign logs into tidy CSV files.

Inputs  : raw/march2025_locations/*  (unchanged originals)
Outputs : processed/*.csv

No values are interpolated or estimated. Rows that cannot be parsed are
skipped and counted; the counts are printed so the extraction is auditable.
Requires: python3, pandas, pandoc (for .odt -> text).
"""
import re, subprocess, sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "raw" / "march2025_locations"
OUT = ROOT / "processed"
OUT.mkdir(exist_ok=True)

SCEN = {"loc2": "Location 2", "loc3": "Location 3", "loc3_doorclosed": "Location 3, door closed"}
UNIT = {"": 1e-6, "K": 1e-3, "M": 1.0, "G": 1e3}


def text_of(p: Path) -> str:
    if p.suffix == ".odt":
        return subprocess.run(["pandoc", "-f", "odt", "-t", "plain", "--wrap=none", str(p)],
                              check=True, capture_output=True, text=True).stdout
    return p.read_text(errors="ignore")


def to_mbps(v: str) -> float:
    """srsRAN rate strings: '2.8M', '203k', '0.0'."""
    v = v.strip()
    m = re.fullmatch(r"([\d.]+)([kKmMgG]?)", v)
    if not m:
        raise ValueError(v)
    return float(m.group(1)) * UNIT[m.group(2).upper()]


# ---------------------------------------------------------------- iperf3
IPERF = re.compile(r"\[\s*\d+\]\s+(\d+\.\d+)-(\d+\.\d+)\s+sec\s+[\d.]+\s+[KMG]?Bytes\s+"
                   r"([\d.]+)\s+([KMG]?)bits/sec(?:\s+(\d+))?")


def parse_iperf(path: Path, scen: str, side: str):
    rows, run = [], 0
    last_end = None
    for line in text_of(path).splitlines():
        if "iperf3 -c" in line or "iperf3 -s" in line:
            run += 1
            last_end = None
            continue
        m = IPERF.search(line)
        if not m:
            continue
        a, b = float(m.group(1)), float(m.group(2))
        if b - a > 1.01:          # skip end-of-run summary lines
            continue
        if last_end is not None and a < last_end:   # new connection inside same invocation
            run += 1
        last_end = b
        rows.append(dict(scenario=SCEN[scen], side=side, source_file=path.name, run=max(run, 1),
                         t_start_s=a, t_end_s=b,
                         throughput_mbps=float(m.group(3)) * UNIT[m.group(4)],
                         tcp_retransmissions=int(m.group(5)) if m.group(5) else None))
    return rows


# ---------------------------------------------------------------- srsUE metrics
UE = re.compile(r"^\s*(\d+)\s+(\d+)\s+(-?\d+)\s+(\d+)\s+(\S+)\s*\|\s*(\d+)\s+(-?\d+)\s+([\d.]+)\s+(\S+)\s+(\d+)%\s+"
                r"([\d.]+)\s*\|\s*(\d+)\s+(\S+)\s+(\S+)\s+(\d+)%")


def parse_ue_trace(path: Path, scen: str):
    rows, bad = [], 0
    for line in text_of(path).splitlines():
        m = UE.match(line)
        if not m:
            if re.match(r"^\s*\d+\s+\d+\s+-\d+", line):
                bad += 1
            continue
        g = m.groups()
        rows.append(dict(scenario=SCEN[scen], source_file=path.name, sample=len(rows),
                         rsrp_dbm=int(g[2]), path_loss_db=int(g[3]),
                         dl_mcs=int(g[5]), dl_snr_db=int(g[6]), dl_turbo_iter=float(g[7]),
                         dl_brate_mbps=to_mbps(g[8]), dl_bler_pct=int(g[9]),
                         ul_mcs=int(g[11]), ul_buffer_mb=to_mbps(g[12]), ul_brate_mbps=to_mbps(g[13]),
                         ul_bler_pct=int(g[14])))
    return rows, bad


# ---------------------------------------------------------------- srsENB metrics
ENB = re.compile(r"^\s*lte\s+([0-9a-f]+)\s+(\S+)\s+(\d+)\s+(\d+)\s+(\S+)\s+(\d+)\s+(\d+)\s+(\d+)%\s*\|\s*"
                 r"(\S+)\s+(\S+)\s+(-?\d+)\s+(\d+)\s+(\S+)\s+(\d+)\s+(\d+)\s+(\d+)%\s+(\S+)")


def parse_enb(path: Path, scen: str):
    rows = []
    for line in text_of(path).splitlines():
        m = ENB.match(line)
        if not m:
            continue
        g = m.groups()
        f = lambda s: None if s in ("n/a", "-") else float(s)
        rows.append(dict(scenario=SCEN[scen], source_file=path.name, sample=len(rows), rnti=g[0],
                         dl_cqi=f(g[1]), dl_ri=int(g[2]), dl_mcs=int(g[3]), dl_brate_mbps=to_mbps(g[4]),
                         dl_ok=int(g[5]), dl_nok=int(g[6]), dl_bler_pct=int(g[7]),
                         ul_pusch_snr_db=f(g[8]), ul_pucch_snr_db=f(g[9]), ul_phr=int(g[10]),
                         ul_mcs=int(g[11]), ul_brate_mbps=to_mbps(g[12]), ul_ok=int(g[13]),
                         ul_nok=int(g[14]), ul_bler_pct=int(g[15]), ul_bsr=g[16]))
    return rows


# ---------------------------------------------------------------- video QoE CSV
def parse_video(path: Path, label: str):
    d = pd.read_csv(path, na_values=["N/A", "NaN"])
    d.columns = ["timestamp_utc", "latency_ms", "packet_loss_pct", "fps", "jitter_ms", "pli_count", "pause_count"]
    d.insert(0, "source_file", path.name)
    d.insert(0, "session", label)
    return d


def main():
    ip = []
    for k in SCEN:
        ip += parse_iperf(RAW / f"{k}_epc_iperf.txt", k, "EPC client (iperf3 -R)")
        ip += parse_iperf(RAW / f"{k}_ue_iperf.odt", k, "UE server")
    ip = pd.DataFrame(ip)
    ip.to_csv(OUT / "iperf_uplink_timeseries.csv", index=False)

    ue, bad_total = [], 0
    for k in SCEN:
        r, bad = parse_ue_trace(RAW / f"{k}_ue_trace.odt", k)
        ue += r
        bad_total += bad
    ue = pd.DataFrame(ue)
    ue.to_csv(OUT / "ue_phy_metrics.csv", index=False)

    enb = pd.DataFrame(parse_enb(RAW / "loc2_enb_trace.txt", "loc2") +
                       parse_enb(RAW / "loc3_doorclosed_enb_trace.txt", "loc3_doorclosed"))
    enb.to_csv(OUT / "enb_mac_metrics.csv", index=False)

    vids = {"video_1336.csv": "13:36 (location not recorded)",
            "video_1422_t1.csv": "14:22 t=1 (location not recorded)",
            "video_1428_t2.csv": "14:28 t=2",
            "video_1522_loc3.csv": "15:22 Location 3",
            "video_1557_doorclosed.csv": "15:57 door closed"}
    vq = pd.concat([parse_video(RAW / f, lab) for f, lab in vids.items()])
    vq.to_csv(OUT / "video_stream_qoe.csv", index=False)

    print("iperf rows:", len(ip), ip.groupby(["scenario", "side"]).size().to_dict())
    print("UE rows:", len(ue), ue.groupby("scenario").size().to_dict(), "unparsed metric-like lines:", bad_total)
    print("eNB rows:", len(enb), enb.groupby("scenario").size().to_dict())
    print("video rows:", len(vq), vq.groupby("session").size().to_dict())


if __name__ == "__main__":
    sys.exit(main())
