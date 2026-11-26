#!/usr/bin/env python3
"""Closed loop: authored geometry -> real renders -> conservative light selection."""
import argparse,json,subprocess
from pathlib import Path
import numpy as np

RECIPES={
 'baseline':([0,0,0],1), 'director':([1,1,1],1),
 'chiaroscuro':([.85,.35,1.15],.85), 'soft':([.75,1.1,.8],1.55),
 'silhouette':([.7,.5,1.4],1), 'restrained':([.55,.65,.75],1.2),
 'warm-focus':([1.2,.6,.7],1.1)}
def recipe(name):
    energy,size=RECIPES[name];return {'energy':dict(zip(('Key','Fill','Rim'),energy)),'size':size}
def metrics(path):
    with np.load(path) as d: rgb=d['rgb']; mask=d['mask'].astype(bool); depth=d['depth']
    rgb=rgb.astype(float)/(255 if rgb.max()>1.01 else 1);lum=rgb@np.array([.2126,.7152,.0722]);
    # Adjacent foreground and background pixels; no wraparound at image borders.
    diffs=[]
    for m,n,l,r in [(mask[:-1],mask[1:],lum[:-1],lum[1:]),(mask[:,:-1],mask[:,1:],lum[:,:-1],lum[:,1:])]:
        edge=m!=n
        if edge.any():diffs.extend(np.abs(l[edge]-r[edge]))
    boundary=float(np.mean(diffs)) if diffs else 0.
    area=float(mask.mean()); white=float((lum[mask]>.96).mean()); dark=float((lum[mask]<.035).mean()); finite=float(np.isfinite(depth[mask]).mean())
    if not np.isfinite([boundary,area,white,dark,finite]).all():raise ValueError('Nonfinite image metrics')
    return dict(boundary=boundary,area=area,white=white,dark=dark,finite_depth=finite,score=boundary-.45*white-.35*dark)
def main():
    p=argparse.ArgumentParser();p.add_argument('--scene',type=Path,required=True);p.add_argument('--focus',required=True);p.add_argument('--cameras',nargs='+',required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--blenderproc',default='blenderproc');p.add_argument('--blender',default='blender');p.add_argument('--frame',type=int,default=1);a=p.parse_args()
    a.out=a.out.resolve();a.out.mkdir(parents=True,exist_ok=False);root=Path(__file__).resolve().parent;scene=a.scene.resolve();views=list(dict.fromkeys(a.cameras));results={}
    for name in RECIPES:
        rows=[]
        for i,cam in enumerate(views):
            dest=a.out/name/f'view-{i:02d}';subprocess.run([a.blenderproc,'run',str(root/'measure.py'),'--scene',str(scene),'--focus',a.focus,'--camera',cam,'--recipe',json.dumps(recipe(name)),'--out',str(dest),'--frame',str(a.frame)],check=True);rows.append(metrics(dest/'passes.npz'))
        results[name]=rows
    base=results['baseline'];direct=results['director'];valid=[]
    for name,rows in results.items():
        if name=='baseline':continue
        if all(x['area']>=.99*b['area'] and x['finite_depth']>=.99 and x['white']<=max(.08,b['white']+.02) and x['dark']<=max(.20,b['dark']+.02) and x['score']>=b['score']-.005 and x['score']>=d['score']-.005 for x,b,d in zip(rows,base,direct)):
            if min(x['score'] for x in rows)>max(min(x['score'] for x in base),min(x['score'] for x in direct))+.005:valid.append(name)
    selected=max(valid,key=lambda n:min(x['score'] for x in results[n])) if valid else None
    record={'scene':str(scene),'focus':a.focus,'cameras':views,'frame':a.frame,'selected':selected,'metrics':results,'note':'Lighting heuristic only; no aesthetic or gameplay pass.'}
    (a.out/'selection.json').write_text(json.dumps(record,indent=2))
    if selected:
        subprocess.run([a.blender,'-b',str(scene),'--python-exit-code','1','--python',str(root/'apply_recipe.py'),'--','--recipe',json.dumps(recipe(selected)),'--out',str(a.out/'refined.blend')],check=True)
    else:print('No lighting recipe exceeded both baselines; keep input unchanged and inspect actual frames.')
if __name__=='__main__':main()
