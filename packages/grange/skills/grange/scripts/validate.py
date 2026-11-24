#!/usr/bin/env python3
"""Measure exported GIFs; numeric gate only, visual identity remains mandatory."""
import argparse, hashlib, json
from pathlib import Path
import numpy as np
from PIL import Image, ImageSequence


def load(path):
    with Image.open(path) as im:
        loop = im.info.get('loop')
        frames, times = [], []
        for f in ImageSequence.Iterator(im):
            times.append(f.info.get('duration', 0))
            a = np.array(f.convert('RGBA'))
            a[a[...,3] == 0, :3] = 0
            frames.append(a)
        return frames, times, loop


def diff(a,b):
    mask = (a[...,3]>0)|(b[...,3]>0)
    return float(np.abs(a.astype(np.int16)-b.astype(np.int16))[mask].mean()) if mask.any() else 0.


def bbox(m):
    y,x = np.nonzero(m)
    if not len(x): raise ValueError('empty object mask')
    return np.array([x.min(),y.min(),x.max()+1,y.max()+1])


def read_masks(path, frames):
    if path is None: return [a[...,3]==255 for a in frames]
    files = sorted(path.glob('*.png')) if path.is_dir() else [path]
    if len(files) not in (1,len(frames)): raise ValueError('mask count mismatch')
    out=[]
    for i,a in enumerate(frames):
        with Image.open(files[i if len(files)>1 else 0]) as m:
            mask=np.asarray(m.convert('L'))>=128
        if mask.shape != a.shape[:2]: raise ValueError('mask size mismatch')
        out.append(mask & (a[...,3]==255))
    return out


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('candidate',type=Path); p.add_argument('reference',type=Path)
    p.add_argument('--ref-indices',required=True,help='one index or comma-separated index per frame')
    p.add_argument('--candidate-masks',type=Path);p.add_argument('--reference-masks',type=Path)
    p.add_argument('--rigid',action='store_true');p.add_argument('--once',action='store_true')
    p.add_argument('--preserve-prefix',type=Path,help='original GIF when only adding seam frames')
    a=p.parse_args()
    fs,ts,loop=load(a.candidate); rs,_,_=load(a.reference)
    if len(fs)<2: p.error('candidate not animated')
    ids=list(map(int,a.ref_indices.split(',')))
    if len(ids)==1: ids*=len(fs)
    if len(ids)!=len(fs) or min(ids)<0 or max(ids)>=len(rs): p.error('invalid reference mapping')
    cm=read_masks(a.candidate_masks,fs); rm=read_masks(a.reference_masks,rs)
    adj=[diff(x,y) for x,y in zip(fs,fs[1:])]; seam=diff(fs[-1],fs[0]); mx=max(adj)
    delta=[]; rigid=[]; errors=[]
    for i,(f,j) in enumerate(zip(fs,ids)):
        r=rs[j]; m=cm[i]; n=rm[j]
        if not m.any() or not n.any(): p.error('empty object mask')
        delta.append(np.abs(f[m,:3].mean(0)-r[n,:3].mean(0)))
        if a.rigid:
            if m.shape!=n.shape: p.error('rigid comparison requires equal canvas dimensions')
            b,c=bbox(m),bbox(n); sz=b[2:]-b[:2]; ref=c[2:]-c[:2]
            shift=np.max(np.abs((b[:2]+b[2:]-c[:2]-c[2:])/2))
            iou=float((m&n).sum()/(m|n).sum()); d=np.abs(sz-ref)
            rigid.append({'frame':i,'bbox_delta_px':d.tolist(),'center_delta_px':float(shift),'iou':iou})
            if np.any(d>np.maximum(1,ref*.02)) or shift>2 or iou<.95: errors.append(f'rigid frame {i}')
        fg=f[...,3]>0
        if not fg.any() or fg.all(): errors.append(f'alpha frame {i}')
        elif fg[0].any() or fg[-1].any() or fg[:,0].any() or fg[:,-1].any(): errors.append(f'border frame {i}')
    d=np.max(delta,axis=0)
    if np.any(d>10): errors.append('RGB')
    if not a.once and seam>mx+1e-10: errors.append('seam')
    if min(adj)==0 or (not a.once and seam==0): errors.append('duplicate adjacent frames')
    if not a.once and loop!=0: errors.append('not infinite loop')
    if a.once and loop==0: errors.append('unexpected infinite loop')
    if min(ts)<=0: errors.append('invalid duration')
    preservation=None
    if a.preserve_prefix:
        old,ot,_=load(a.preserve_prefix)
        if len(old)<2 or len(fs)<=len(old) or old[0].shape!=fs[0].shape:
            errors.append('invalid preserved prefix or no new seam frames')
        else:
            prefix_delta=max(diff(x,y) for x,y in zip(old,fs[:len(old)]))
            old_max=max(diff(x,y) for x,y in zip(old,old[1:]))
            new_seam_max=max(adj[len(old)-1:]+[seam])
            timing_exact=ts[:len(old)]==ot
            new_timing_ok=all(min(ot)<=t<=max(ot) for t in ts[len(old):])
            preservation={'prefix_delta':prefix_delta,'prefix_timing_exact':timing_exact,'new_timing_ok':new_timing_ok,'original_adjacent_max':old_max,'new_seam_region_max':new_seam_max}
            if prefix_delta!=0 or not timing_exact or not new_timing_ok or new_seam_max>old_max+1e-10:
                errors.append('original frames/timing or repaired seam changed beyond allowed bounds')
    print(json.dumps({'numeric_pass':not errors,'visual_identity':'REQUIRED_MANUAL_P1','errors':errors,'delta_rgb_max':d.tolist(),'adjacent_mean':float(np.mean(adj)),'adjacent_max':mx,'seam':None if a.once else seam,'size_px':[fs[0].shape[1],fs[0].shape[0]],'frames':len(fs),'bytes':a.candidate.stat().st_size,'durations_ms':ts,'reference_sha256':hashlib.sha256(a.reference.read_bytes()).hexdigest(),'reference_indices':ids,'rigid':rigid,'preservation':preservation},ensure_ascii=False,indent=2))
    return 1 if errors else 0

if __name__=='__main__': raise SystemExit(main())
