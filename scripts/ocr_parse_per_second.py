import re,glob,os,csv
L=re.compile(r'(\d+(?:[.,]\d+)?)\s*([KMG])Bytes\s+(\d+(?:[.,]\d+)?)\s*([KMG]?)bits/sec',re.I)
C=re.compile(r'Config\s*(\d+)\s*[:;]\s*SNR\s*[=:]\s*(\d+[.,]\d+)',re.I)
U={'K':1e-3,'M':1.0,'G':1e3,'':1e-6}
rows=[];snr=[]
for v in ['ris_configuration_in_mast_lab','partial_nlos_with_ris','after_ris_conf']:
    for t in sorted(glob.glob(f'frames/{v}/*.t3')):
        fr=int(os.path.basename(t)[:4]); last=None; nlines=0
        for line in open(t):
            for m in C.finditer(line): snr.append((v,fr,int(m.group(1)),float(m.group(2).replace(',','.'))))
            m=L.search(line)
            if not m: continue
            tb=float(m.group(1).replace(',','.')); tu=m.group(2).upper(); r=float(m.group(3).replace(',','.'))*U[m.group(4).upper()]
            mib=tb/1024 if tu=='K' else tb
            if abs(mib*8.388608-r)<=max(0.02*r,0.02): last=(round(mib,4),r); nlines+=1
        rows.append((v,fr,nlines,last[1] if last else ''))
with open('bottomline_readings.csv','w') as f:
    w=csv.writer(f); w.writerow(['video','frame_s','consistent_lines_in_frame','bottom_consistent_bitrate_mbps']); w.writerows(rows)
with open('matlab_snr_ocr.csv','w') as f:
    w=csv.writer(f); w.writerow(['video','frame_s','config','snr_db']); w.writerows(snr)
import pandas as pd
d=pd.read_csv('bottomline_readings.csv'); d=d[d.consistent_lines_in_frame>0]
print(d.groupby('video').bottom_consistent_bitrate_mbps.describe().round(2))
print(sorted(set((a,c,s) for a,_,c,s in snr)))
