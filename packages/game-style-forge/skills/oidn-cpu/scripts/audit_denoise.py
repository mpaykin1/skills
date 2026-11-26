"""Validate denoised candidates; does not assert visual improvement or temporal coherence."""
import argparse,json
from pathlib import Path
import numpy as np
from oidn_cpu import png,sha,require,protected_mask,checked_file

def audit(config,out):
    root=config.resolve().parent;c=json.loads(config.read_text());m=json.loads((out/'denoise.json').read_text());require(m['schema']=='oidn-cpu-v1' and m['device']=='cpu' and m['source_config_sha256']==sha(config) and m['asset_id']==c['asset_id'] and m['fps']==c['fps'],'Source metadata mismatch');require(len(c['frames'])==len(m['frames']),'Frame count changed');orig=[];final=[];max_mean=0
    for f,g in zip(c['frames'],m['frames']):
        p=checked_file(root,f);q=checked_file(out.resolve(),g);require(f['frame']==g['frame'] and sha(p)==g['input_sha256'],'Frame provenance');a,b=png(p),png(q);require(a.shape==b.shape and np.array_equal(a[...,3],b[...,3]),'Alpha or dimensions changed');mask=checked_file(root,f['protect']) if f.get('protect') else None;prot=protected_mask(a,mask);require(np.array_equal(a[prot],b[prot]),'Protected silhouette/detail changed');delta=np.abs(a[...,:3].astype(np.float32)-b[...,:3]);max_mean=max(max_mean,float(delta.mean()));require(delta.mean()<=18,'Excessive RGB change; lower blend or protect detail');orig.append(a[::4,::4].astype(np.float32));final.append(b[::4,::4].astype(np.float32))
    if len(orig)>1:
        for a in (orig,final):
            for x in a:x[...,:3]*=x[...,3:4]/255
        base=np.mean([np.abs(a-b).mean() for a,b in zip(orig,orig[1:])]);after=np.mean([np.abs(a-b).mean() for a,b in zip(final,final[1:])]);require(base<.01 or after>=.65*base,'Motion suppressed');require(after<=max(.3,1.4*base),'Temporal change increased; inspect for flicker')
    return {'max_frame_mean_rgb_delta':max_mean,'structural_only':True}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('config',type=Path);p.add_argument('out',type=Path);a=p.parse_args();audit(a.config,a.out)
