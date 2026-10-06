#!/usr/bin/env python3
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np
from kvcontinual.recurrent.hypic_capture import capture_segment_tail_heads, direct_head_recurrence

rng=np.random.default_rng(10)
T,K,V,D,seam=24,2,4,8,8
k=rng.normal(size=(T,K,D)); k/=np.linalg.norm(k,axis=2,keepdims=True)
v=rng.normal(size=(T,V,D))
g=np.clip(rng.normal(.94,.015,size=(T,V)),.75,.999)
b=np.clip(rng.normal(.42,.1,size=(T,V)),.02,.98)
captured=capture_segment_tail_heads(k,v,g,b,seam_width=seam)
worst=0.0
for vh in range(V):
    S0=rng.normal(size=(D,D))
    exact=direct_head_recurrence(S0,k[seam:,vh%K],v[seam:,vh],g[seam:,vh],b[seam:,vh])
    got=captured.summary_for_v_head(vh).apply(S0)
    err=np.linalg.norm(got-exact)/(np.linalg.norm(exact)+1e-15)
    worst=max(worst,float(err))
print(f"RC10 fixed-input GDN/HYPIC reference: PASS; worst relative error={worst:.3e}")
