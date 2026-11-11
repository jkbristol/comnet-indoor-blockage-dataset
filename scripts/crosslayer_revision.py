#!/usr/bin/env python3
"""Analyses added in the revision (Computer Networks COMNET-D-26-07667).

Inputs : processed/iperf_uplink_timeseries.csv, ue_timeline.csv, aligned_timeline.csv,
         enb_mac_metrics.csv, raw UE traces (C-RNTIs), raw video CSVs
Outputs: processed/revision_metrics.csv, processed/zero_goodput_classification.csv,
         processed/rlf_epochs.csv, processed/video_events_vs_rlf.csv (and prints everything)
Exclusion rule (applied everywhere): for each iperf3 run, the final continuous
zero-goodput period is removed ('active' seconds).
"""
import re, subprocess
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
P, RAW = ROOT / "processed", ROOT / "raw" / "march2025_locations"
ORDER = ["Location 2", "Location 3", "Location 3, door closed"]
ip = pd.read_csv(P / "iperf_uplink_timeseries.csv")
epc = ip[ip.side.str.startswith("EPC")]
al = pd.read_csv(P / "aligned_timeline.csv")
tl = pd.read_csv(P / "ue_timeline.csv")
enb = pd.read_csv(P / "enb_mac_metrics.csv", dtype={"rnti": str})
pd.set_option("display.width", 200)


def active_mask(g):
    m = np.ones(len(g), bool); k = len(g)
    while k > 0 and g[k - 1] == 0:
        k -= 1
    m[k:] = False
    return m


def runs_of(b):
    out, start = [], None
    for i, v in enumerate(b):
        if v and start is None: start = i
        if not v and start is not None: out.append((start, i)); start = None
    if start is not None: out.append((start, len(b)))
    return out


# ------------------------------------------------------------ 1. consistent goodput / outage metrics
al["active"] = False
for (s, r), d in al.groupby(["scenario", "run"]):
    al.loc[d.index, "active"] = active_mask(d.goodput_mbps.values)
rows = []
for s in ORDER:
    a = al[al.scenario == s]
    act = a[a.active]
    outs = []
    for r, d in a.groupby("run"):
        z = (d.goodput_mbps.values == 0) & d.active.values
        outs += [e - b for b, e in runs_of(z)]
    o = np.array(outs)
    rlf_act = int(act.rlf.fillna(0).sum())
    ue_s = int((tl.scenario == s).sum())
    rows.append(dict(scenario=s, samples=len(a), tail_s=int((~a.active).sum()), active_s=len(act),
                     mean_all=a.goodput_mbps.mean(), mean_active=act.goodput_mbps.mean(),
                     median_active=act.goodput_mbps.median(),
                     zero_s_active=int((act.goodput_mbps == 0).sum()),
                     zero_pct_active=(act.goodput_mbps == 0).mean() * 100,
                     below1_pct_active=(act.goodput_mbps < 1).mean() * 100,
                     below5_pct_active=(act.goodput_mbps < 5).mean() * 100,
                     n_outages=len(o), outage_s_total=int(o.sum()), outages_per_10min=len(o) / len(act) * 600,
                     outage_median=float(np.median(o)), outage_max=int(o.max()), outages_ge5=int((o >= 5).sum()),
                     rlf_total=int(tl[tl.scenario == s].rlf.sum()), ue_timeline_s=ue_s,
                     rlf_per10_ue_timeline=tl[tl.scenario == s].rlf.sum() / ue_s * 600,
                     rlf_in_active=rlf_act, rlf_per10_active=rlf_act / len(act) * 600))
M = pd.DataFrame(rows)
L2, DC, L3 = M.set_index("scenario").loc["Location 2"], M.set_index("scenario").loc["Location 3, door closed"], M.set_index("scenario").loc["Location 3"]
print(M.round(2).T.to_string())
print(f"\nfold L2/DC  all={L2.mean_all/DC.mean_all:.0f}  active={L2.mean_active/DC.mean_active:.0f};  L2/L3 all={L2.mean_all/L3.mean_all:.0f} active={L2.mean_active/L3.mean_active:.0f}")
print(f"outage-rate ratio DC/L2 = {DC.outages_per_10min/L2.outages_per_10min:.0f}")

# ------------------------------------------------------------ 2. BLER: UE vs eNB, mean vs median
print("\nUplink BLER (%)")
ue = pd.read_csv(P / "ue_phy_metrics.csv")
for s in ORDER:
    u = ue[ue.scenario == s].ul_bler_pct
    e = enb[(enb.scenario == s) & ((enb.ul_ok + enb.ul_nok) > 0)].ul_bler_pct
    print(f"  {s:25s} UE mean {u.mean():5.1f} median {u.median():4.0f} | eNB mean {e.mean() if len(e) else np.nan:5.1f} median {e.median() if len(e) else np.nan:4.0f} (n={len(e)})")
    M.loc[M.scenario == s, ["ue_ul_bler_mean", "ue_ul_bler_median", "enb_ul_bler_mean", "enb_ul_bler_median"]] = \
        [u.mean(), u.median(), e.mean() if len(e) else np.nan, e.median() if len(e) else np.nan]

# ------------------------------------------------------------ 3. RNTI provenance and SNR-MCS correlation
print("\neNB RNTIs vs the UE's own C-RNTIs (from srsUE 'Random Access Complete' lines)")
TR = {"Location 2": "loc2_ue_trace.odt", "Location 3, door closed": "loc3_doorclosed_ue_trace.odt"}
for s, f in TR.items():
    t = subprocess.run(["pandoc", "-f", "odt", "-t", "plain", str(RAW / f)], capture_output=True, text=True).stdout
    own = {x.lower() for x in re.findall(r"c-rnti=0x([0-9a-fA-F]+)", t)}
    e = enb[enb.scenario == s]
    a = e[e.ul_pusch_snr_db.notna() & ((e.ul_ok + e.ul_nok) > 0)]
    print(f"  {s}: eNB rows {len(e)}, own-RNTI rows {e.rnti.str.lower().isin(own).sum()}; UL-active rows {len(a)}, own {a.rnti.str.lower().isin(own).sum()}")
a = enb[enb.ul_pusch_snr_db.notna() & ((enb.ul_ok + enb.ul_nok) > 0)]
loaded = a[a.ul_brate_mbps >= 0.5]
print(f"  corr UL SNR-MCS all UL-active rows: {a.ul_pusch_snr_db.corr(a.ul_mcs):.3f} (n={len(a)});"
      f" rows with >=0.5 Mbit/s UL: {loaded.ul_pusch_snr_db.corr(loaded.ul_mcs):.3f} (n={len(loaded)});"
      f" original filter (RNTI 75/81 removed): {a[~a.rnti.isin(['75','81'])].pipe(lambda x: x.ul_pusch_snr_db.corr(x.ul_mcs)):.3f}")
lowrate = a[a.rnti.isin(["75", "81"])]
print(f"  RNTIs 75/81 (end of L2 run, same UE): n={len(lowrate)}, median UL rate {lowrate.ul_brate_mbps.median():.2f} Mbit/s, MCS {lowrate.ul_mcs.median():.0f}, SNR {lowrate.ul_pusch_snr_db.median():.1f} dB")
u = ue[ue.dl_brate_mbps.notna()]
print(f"  corr DL SNR-MCS (UE, all rows): {ue.dl_snr_db.corr(ue.dl_mcs):.3f} (n={len(ue)})")
M.loc[:, "corr_ul_all"] = a.ul_pusch_snr_db.corr(a.ul_mcs); M.loc[:, "corr_ul_loaded"] = loaded.ul_pusch_snr_db.corr(loaded.ul_mcs)
M.loc[:, "n_ul_all"] = len(a); M.loc[:, "n_ul_loaded"] = len(loaded); M.loc[:, "corr_dl"] = ue.dl_snr_db.corr(ue.dl_mcs)
M.to_csv(P / "revision_metrics.csv", index=False, float_format="%.3f")

# ------------------------------------------------------------ 4. what the UE was doing during zero-goodput seconds
def ue_class(r):
    if r.state != "connected": return "UE not RRC-connected (no metrics line)"
    if r.ul_brate_mbps < 0.1: return "connected, UL MAC < 0.1 Mbit/s"
    return "connected, UL MAC >= 0.1 Mbit/s"
z = al[al.active & (al.goodput_mbps == 0)].copy()
z["ue_class"] = z.apply(ue_class, axis=1)
# within 3 s of an RLF?
rlf_sec = {s: set(al[(al.scenario == s) & (al.rlf > 0)].iperf_second) for s in ORDER}
z["near_rlf"] = [any(abs(i - j) <= 3 for j in rlf_sec[s]) for s, i in zip(z.scenario, z.iperf_second)]
C = z.groupby(["scenario", "ue_class"]).size().unstack(fill_value=0)
print("\nActive zero-goodput seconds by UE state at the same second"); print(C.T.to_string())
C.to_csv(P / "zero_goodput_by_ue_state.csv")
print("share within +-3 s of an RLF:", z.groupby("scenario").near_rlf.mean().round(3).to_dict())
z.to_csv(P / "zero_goodput_classification.csv", index=False)
# outage-level
print("\nOutages (active) and RLF")
OUT = []
for s in ORDER:
    a_ = al[al.scenario == s]
    for r, d in a_.groupby("run"):
        zz = (d.goodput_mbps.values == 0) & d.active.values
        for b, e in runs_of(zz):
            secs = d.iperf_second.values[b:e]
            st = d.state.values[b:e]
            OUT.append(dict(scenario=s, start=int(secs[0]), dur=e - b,
                            rlf_in_or_near=any(abs(i - j) <= 3 for i in secs for j in rlf_sec[s]),
                            ue_disconnected_any=bool((st != "connected").any()),
                            ue_mac_active_all=bool(((st == "connected") & (d.ul_brate_mbps.values[b:e] > 0)).all())))
O = pd.DataFrame(OUT)
print(O.groupby(["scenario", "rlf_in_or_near"]).dur.agg(["size", "sum", "median", "max"]).to_string())
print(O.groupby("scenario")[["rlf_in_or_near", "ue_disconnected_any", "ue_mac_active_all"]].sum().to_string())
_unused = (O.groupby("scenario").agg(n=("dur", "size"), with_rlf=("rlf_in_or_near", "sum"),
                                 with_ue_gap=("ue_disconnected_any", "sum"), mac_active_throughout=("ue_mac_active_all", "sum"),
                                 med_dur_rlf=("dur", lambda x: np.median(x[O.loc[x.index, 'rlf_in_or_near']]) if O.loc[x.index, 'rlf_in_or_near'].any() else np.nan),
                                 med_dur_norlf=("dur", lambda x: np.median(x[~O.loc[x.index, 'rlf_in_or_near']]) if (~O.loc[x.index, 'rlf_in_or_near']).any() else np.nan)))
# RLF context: radio state in the 5 s before each RLF
pre = []
for s_ in ORDER:
    a_ = al[al.scenario == s_].set_index("iperf_second")
    for j in sorted(rlf_sec[s_]):
        w = a_.loc[[k for k in range(j - 5, j) if k in a_.index]]
        w = w[w.state == "connected"]
        pre.append(dict(scenario=s_, rlf_at=j, dl_snr=w.dl_snr_db.mean(), rsrp=w.rsrp_dbm.mean(), ul_bler=w.ul_bler_pct.mean()))
print("\nRadio state in the 5 s before each RLF (means over RLFs):")
print(pd.DataFrame(pre).groupby("scenario")[["dl_snr", "rsrp", "ul_bler"]].agg(["mean", "min", "max"]).round(1).to_string())
O.to_csv(P / "outages_with_ue_state.csv", index=False)
print("RLFs falling inside or within 3 s of a zero-goodput period:")
for s in ORDER:
    zs = set(al[(al.scenario == s) & al.active & (al.goodput_mbps == 0)].iperf_second)
    rl = sorted(rlf_sec[s]); inact = [j for j in rl if al[(al.scenario == s) & (al.iperf_second == j)].active.any()]
    hit = sum(any(abs(j - k) <= 3 for k in zs) for j in inact)
    print(f"  {s}: RLFs mapped {len(rl)}, in active period {len(inact)}, coinciding with zero goodput {hit}")

# ------------------------------------------------------------ 5. final zero-goodput period: UE state
print("\nFinal zero-goodput period: UE state")
for s in ORDER:
    a_ = al[(al.scenario == s) & ~al.active]
    for r, d in a_.groupby("run"):
        c = d[d.state == "connected"]
        print(f"  {s} run {r}: {len(d)} s; UE lines mapped {len(c)}; median DL SNR {c.dl_snr_db.median()}; "
              f"median UE UL MAC {c.ul_brate_mbps.median()} Mbit/s; RLF {int(d.rlf.fillna(0).sum())}")
    t = tl[tl.scenario == s]
    last = t[t.rlf > 0].second.max() if (t.rlf > 0).any() else None
    print(f"    UE trace length {len(t)} lines; last RLF at line {last}; last state {t.state.iloc[-1]}")

# ------------------------------------------------------------ 6. superposed epochs around RLF
W = 15; E = []
for s in ["Location 3", "Location 3, door closed", "Location 2"]:
    a_ = al[al.scenario == s].set_index("iperf_second")
    for j in sorted(rlf_sec[s]):
        for k in range(-W, W + 1):
            if j + k in a_.index:
                r = a_.loc[j + k]
                E.append(dict(scenario=s, rlf_at=j, k=k, goodput=r.goodput_mbps, dl_snr=r.dl_snr_db,
                              ul_mcs=r.ul_mcs, ul_mac=r.ul_brate_mbps, ul_bler=r.ul_bler_pct,
                              connected=float(r.state == "connected")))
EP = pd.DataFrame(E); EP.to_csv(P / "rlf_epochs.csv", index=False)
blk = EP[EP.scenario != "Location 2"]
g = blk.groupby(pd.cut(blk.k, [-16, -11, -6, -1, 0, 5, 10, 15], labels=["-15..-11", "-10..-6", "-5..-1", "0", "1..5", "6..10", "11..15"]), observed=True)
print("\nAround RLF (L3 and L3-DC pooled, aligned seconds)")
print(g.agg(goodput=("goodput", "mean"), dl_snr=("dl_snr", "mean"), ul_mcs=("ul_mcs", "median"),
            ul_mac=("ul_mac", "mean"), ul_bler=("ul_bler", "mean"), connected=("connected", "mean")).round(2))
base = al[al.active & (al.scenario != "Location 2") & (al.state == "connected")]
print("baseline (all active connected s, L3+DC): goodput %.2f, DL SNR %.2f, UL MCS med %.0f, UL BLER %.1f"
      % (base.goodput_mbps.mean(), base.dl_snr_db.mean(), base.ul_mcs.median(), base.ul_bler_pct.mean()))

# ------------------------------------------------------------ 7. video events vs RLF (wall clock)
T0 = {"Location 2": "2025-03-11T14:28:30", "Location 3": "2025-03-11T15:21:13", "Location 3, door closed": "2025-03-11T15:56:03"}
VID = {"Location 2": ["video_1428_t2.csv"], "Location 3": ["video_1522_loc3.csv"], "Location 3, door closed": ["video_1557_doorclosed.csv"]}
mp = pd.read_csv(P / "ue_to_iperf_map.csv")
print("\nVideo PLI/pause events vs RLF (UE banner time + aligned clock; window RLF-2 s .. RLF+10 s)")
VV = []
for s in ORDER:
    m = mp[mp.scenario == s].merge(tl[tl.scenario == s][["second", "rlf", "ul_brate_mbps"]], left_on="ue_line", right_on="second")
    ref = m[m.ul_brate_mbps.fillna(0) > 0.5].ue_line.min()
    m["wall"] = pd.Timestamp(T0[s]) + pd.to_timedelta(ref + (m.iperf_second - m.loc[m.ue_line == ref, "iperf_second"].iloc[0]), unit="s")
    rl = m[m.rlf > 0].wall.tolist(); lo, hi = m.wall.min(), m.wall.max()
    for f in VID[s]:
        v = pd.read_csv(RAW / f); v["t"] = pd.to_datetime(v.Timestamp).dt.tz_localize(None)
        v = v[(v.t >= lo) & (v.t <= hi)]
        for col in ["PLI Count", "Pause Count"]:
            x = pd.to_numeric(v[col], errors="coerce").ffill()
            ev_t = v.t[x.diff() > 0].tolist()
            hit = sum(any(-2 <= (e - r).total_seconds() <= 10 for r in rl) for e in ev_t)
            grid = pd.date_range(max(lo, v.t.min()), min(hi, v.t.max()), freq="1s")
            cover = np.mean([any(-2 <= (g - r).total_seconds() <= 10 for r in rl) for g in grid]) if len(grid) else np.nan
            VV.append(dict(scenario=s, file=f, event=col, overlap_s=len(grid), n_events=len(ev_t), near_rlf=hit,
                           frac_near=hit / len(ev_t) if ev_t else np.nan, chance=cover))
VV = pd.DataFrame(VV); print(VV.round(3).to_string(index=False)); VV.to_csv(P / "video_events_vs_rlf.csv", index=False)

# robustness of the video/RLF association to the clock offset, and binomial tail probability
from math import comb
def binom_sf(k, n, p):
    return sum(comb(n, i) * p**i * (1 - p)**(n - i) for i in range(k, n + 1))
print("\nPLI association: binomial P(X>=hits) under chance coverage")
for _, r in VV[VV.event == "PLI Count"].iterrows():
    if r.n_events: print(f"  {r.scenario}: {r.near_rlf}/{r.n_events}, chance {r.chance:.3f}, p = {binom_sf(int(r.near_rlf), int(r.n_events), r.chance):.1e}")
print("Sensitivity to an error in the UE start time (shift in s -> PLI hits L3, L3-DC):")
for sh in [-10, -5, -3, 0, 3, 5, 10]:
    out = []
    for s in ["Location 3", "Location 3, door closed"]:
        m = mp[mp.scenario == s].merge(tl[tl.scenario == s][["second", "rlf", "ul_brate_mbps"]], left_on="ue_line", right_on="second")
        ref = m[m.ul_brate_mbps.fillna(0) > 0.5].ue_line.min()
        wall = pd.Timestamp(T0[s]) + pd.to_timedelta(ref + sh + (m.iperf_second - m.loc[m.ue_line == ref, "iperf_second"].iloc[0]), unit="s")
        rl = wall[m.rlf > 0].tolist()
        v = pd.read_csv(RAW / VID[s][0]); v["t"] = pd.to_datetime(v.Timestamp).dt.tz_localize(None)
        v = v[(v.t >= wall.min()) & (v.t <= wall.max())]
        x = pd.to_numeric(v["PLI Count"], errors="coerce").ffill(); ev_t = v.t[x.diff() > 0]
        out.append(f"{sum(any(-2 <= (e - r).total_seconds() <= 10 for r in rl) for e in ev_t)}/{len(ev_t)}")
    print(f"  {sh:+d} s: {out}")
