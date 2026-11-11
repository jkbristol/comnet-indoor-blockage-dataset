#!/usr/bin/env python3
"""Rebuild a complete one-second srsUE timeline from the console traces.

srsUE prints one line per second: a metrics line while RRC-connected, or
'--- disconnected ---' otherwise. Event messages (RLF, re-establishment,
RRC state changes) are attached to the second in which they appear.
Writes processed/ue_timeline.csv.
"""
import re, subprocess
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW, OUT = ROOT / "raw" / "march2025_locations", ROOT / "processed"
TR = {"Location 2": "loc2_ue_trace.odt", "Location 3": "loc3_ue_trace.odt",
      "Location 3, door closed": "loc3_doorclosed_ue_trace.odt"}
UNIT = {"": 1e-6, "k": 1e-3, "K": 1e-3, "M": 1.0}
MET = re.compile(r"^\s*\d+\s+\d+\s+(-?\d+)\s+(\d+)\s+\S+\s*\|\s*(\d+)\s+(-?[\d.]+)\s+\S+\s+([\d.]+)([kKM]?)\s+(\d+)%\s+\S+\s*\|"
                 r"\s*(\d+)\s+\S+\s+([\d.]+)([kKM]?)\s+(\d+)%")
EVENTS = {"rlf": "Detected Radio-Link Failure", "reest_reject": "Reestablishment Reject",
          "reest_ok": "Reestablishment OK", "rrc_release": "Received RRC Connection Release",
          "sr_fail": "Scheduling request failed", "service_req_fail": "RRC connection for Service Request failed",
          "t301": "Timer T301 expired", "cell_unsuitable": "Selected cell no longer suitable"}


def timeline(scen, fname):
    txt = subprocess.run(["pandoc", "-f", "odt", "-t", "plain", "--wrap=none", str(RAW / fname)],
                         check=True, capture_output=True, text=True).stdout
    rows, pending, started = [], {k: 0 for k in EVENTS}, False
    for line in txt.splitlines():
        if line.strip() == "t":            # trace switched on
            started = True
        for k, pat in EVENTS.items():
            if pat in line:
                pending[k] += 1
        m = MET.match(line)
        if m and started:
            r = dict(state="connected", rsrp_dbm=int(m[1]), dl_mcs=int(m[3]), dl_snr_db=float(m[4]),
                     dl_brate_mbps=float(m[5]) * UNIT[m[6]], dl_bler_pct=int(m[7]), ul_mcs=int(m[8]),
                     ul_brate_mbps=float(m[9]) * UNIT[m[10]], ul_bler_pct=int(m[11]))
        elif "--- disconnected ---" in line and started:
            r = dict(state="disconnected")
        else:
            continue
        r.update(pending); pending = {k: 0 for k in EVENTS}
        rows.append(r)
    d = pd.DataFrame(rows)
    d.insert(0, "second", range(len(d))); d.insert(0, "scenario", scen)
    return d


if __name__ == "__main__":
    d = pd.concat([timeline(s, f) for s, f in TR.items()], ignore_index=True)
    d.to_csv(OUT / "ue_timeline.csv", index=False)
    print(d.groupby(["scenario", "state"]).size().unstack(fill_value=0))
    print(d.groupby("scenario")[list(EVENTS)].sum())
