import pandas as pd, numpy as np, sys
src=sys.argv[1] if len(sys.argv)>1 else 'ocr_iperf_checked.csv'
d=pd.read_csv(src); d=d[d.consistent]
out=[]
for v,g in d.groupby('video'):
    run=1; prev=None
    fmax=g.groupby('frame_s').interval_end_s.max().sort_index()
    runof={}
    for fr,mx in fmax.items():
        if prev is not None and mx < prev-30: run+=1
        runof[fr]=run; prev=mx
    g=g.assign(run=g.frame_s.map(runof))
    for (r,e),gg in g.groupby(['run','interval_end_s']):
        vals=gg.bitrate_mbps.round(3)
        m=vals.mode().iloc[0]
        out.append(dict(video=v,run=r,interval_end_s=e,bitrate_mbps=m,n_frames_seen=len(gg),n_agree=(vals==m).sum(),first_frame_s=gg.frame_s.min()))
o=pd.DataFrame(out).sort_values(['video','run','interval_end_s'])
o.to_csv(src.replace('checked','readings'),index=False)
s=o.groupby('video').bitrate_mbps.agg(['count','median','mean','min','max']).round(2)
print(s.to_string())
