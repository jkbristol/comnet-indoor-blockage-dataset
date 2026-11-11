import re,glob,os,csv,collections
# iperf line: <end>.00 sec <transfer> <KB/MB>ytes <rate> <K/M>bits/sec
ip=re.compile(r'(\d{1,4})[.,]\d\d\s*sec\s+(\d+(?:[.,]\d+)?)\s*([KMG])Bytes\s+(\d+(?:[.,]\d+)?)\s*([KMG]?)bits/sec',re.I)
U={'K':1e-3,'M':1.0,'G':1e3,'':1e-6}
rows=[]
for d in sorted(glob.glob('frames/*/')):
    v=os.path.basename(d.rstrip('/'))
    for t in sorted(glob.glob(d+'*.txt')):
        fr=int(os.path.basename(t)[:4])
        for line in open(t):
            m=ip.search(line)
            if not m: continue
            end=int(m.group(1)); tb=float(m.group(2).replace(',','.')); tu=m.group(3).upper()
            r=float(m.group(4).replace(',','.')); ru=m.group(5).upper()
            mbytes=tb*(1/1024 if tu=='K' else 1 if tu=='M' else 1024)  # iperf uses 1024-based bytes
            rate=r*U[ru]
            implied=mbytes*1024*1024*8/1e6  # Mbit over 1 s
            ok=abs(implied-rate)<=max(0.02*rate,0.02)
            rows.append((v,fr,end,round(mbytes,5),rate,ok))
with open('ocr_iperf_checked.csv','w') as f:
    w=csv.writer(f); w.writerow(['video','frame_s','interval_end_s','transfer_MiB','bitrate_mbps','consistent']); w.writerows(rows)
c=collections.defaultdict(lambda:[0,0])
for r in rows: c[r[0]][0]+=1; c[r[0]][1]+=r[5]
for k,v in c.items(): print(f'{k:60s} {v[0]:4d} lines, {v[1]:4d} consistent')
