#!/usr/bin/env python3
"""Nevergrad -> real BlenderProc passes -> held-out validation -> Blender apply.
Run on an immutable directed.blend (Infinigen or existing authored geometry).
"""
import argparse
import importlib.metadata as md
import json
import subprocess
from pathlib import Path
import numpy as np
import nevergrad as ng
from refine import RECIPES, recipe, metrics

ROLES = ('Key', 'Fill', 'Rim')
LOW = np.array([.15, .05, .05, .55])
HIGH = np.array([1.5, 1.5, 1.7, 1.8])

def vector(r):
    return np.array([*(r['energy'][k] for k in ROLES), r['size']], dtype=float)

def from_vector(x):
    x = np.asarray(x, dtype=float)
    if x.shape != (4,) or not np.isfinite(x).all() or np.any(x < LOW-1e-8) or np.any(x > HIGH+1e-8):
        raise ValueError('Invalid candidate')
    x = np.clip(x, LOW, HIGH)
    return {'energy': dict(zip(ROLES, map(float, x[:3]))), 'size': float(x[3])}

def score(rows):
    return min(r['score'] for r in rows)

def feasible(rows, base, direct):
    return len(rows)==len(base)==len(direct) and all(
        r['area'] >= .99*max(b['area'], d['area']) and r['finite_depth'] >= .99
        and r['white'] <= max(.08,b['white']+.02) and r['dark'] <= max(.20,b['dark']+.02)
        and r['score'] >= max(b['score'],d['score'])-.005
        for r,b,d in zip(rows,base,direct))

def improvement(rows, base, direct):
    return feasible(rows,base,direct) and score(rows) > max(score(base),score(direct))+.005

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--scene',type=Path,required=True);p.add_argument('--focus',required=True)
    p.add_argument('--cameras',nargs='+',required=True);p.add_argument('--frames',nargs='+',type=int,default=[1]);p.add_argument('--validation-frames',nargs='+',type=int)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--budget',type=int,default=16);p.add_argument('--seed',type=int,default=17)
    p.add_argument('--samples',type=int,default=32);p.add_argument('--validation-samples',type=int,default=96)
    p.add_argument('--blenderproc',default='blenderproc');p.add_argument('--blender',default='blender');a=p.parse_args()
    if a.budget<1 or a.samples<1 or a.validation_samples<=a.samples: p.error('positive budget/samples and higher validation samples required')
    scene=a.scene.resolve(strict=True);root=Path(__file__).resolve().parent;out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    cameras=list(dict.fromkeys(a.cameras));frames=list(dict.fromkeys(a.frames));vf=list(dict.fromkeys(a.validation_frames or frames))
    def evaluate(name,r,frames,samples):
        rows=[]
        for j,frame in enumerate(frames):
            for i,cam in enumerate(cameras):
                dest=out/name/f'f{j:03d}-v{i:03d}'
                subprocess.run([a.blenderproc,'run',str(root/'measure.py'),'--scene',str(scene),'--focus',a.focus,'--camera',cam,'--recipe',json.dumps(r),'--out',str(dest),'--frame',str(frame),'--samples',str(samples)],check=True)
                rows.append(metrics(dest/'passes.npz'))
        return rows
    trials=[]
    for name in RECIPES:
        r=recipe(name);rows=evaluate('initial-'+name,r,frames,a.samples)
        trials.append({'name':name,'recipe':r,'rows':rows})
    base,direct=trials[0]['rows'],trials[1]['rows']
    eligible=[t for t in trials[1:] if feasible(t['rows'],base,direct)]
    prior=max(eligible,key=lambda t:score(t['rows']))['recipe'] if eligible else recipe('director')
    param=ng.p.Array(init=vector(prior)).set_bounds(LOW,HIGH)
    param.random_state.seed(a.seed)
    opt=ng.optimizers.NGOpt(parametrization=param,budget=a.budget,num_workers=1)
    for i in range(a.budget):
        candidate=opt.ask();r=from_vector(candidate.value);name=f'ng-{i:04d}'
        rows=evaluate(name,r,frames,a.samples)
        valid=feasible(rows,base,direct)
        loss=-score(rows) if valid else 10+max(0.,-score(rows))
        opt.tell(candidate,float(loss));trials.append({'name':name,'recipe':r,'rows':rows})
    # No recommendation that was not actually rendered. Re-evaluate best fixed and
    # optimized recipes at higher quality and optional independent animation frames.
    validation={};selected=None
    vb=evaluate('validate-baseline',recipe('baseline'),vf,a.validation_samples)
    vd=evaluate('validate-director',recipe('director'),vf,a.validation_samples)
    validation.update(baseline=vb,director=vd)
    winners=sorted((t for t in trials[2:] if improvement(t['rows'],base,direct)),key=lambda t:score(t['rows']),reverse=True)
    # At most three best trials, plus best fixed recipe if not already included.
    finalists=winners[:3];fixed=next((t for t in winners if not t['name'].startswith('ng-')),None)
    if fixed and fixed not in finalists:finalists.append(fixed)
    for t in finalists:
        rows=evaluate('validate-'+t['name'],t['recipe'],vf,a.validation_samples);validation[t['name']]=rows
        if improvement(rows,vb,vd) and (selected is None or score(rows)>score(validation[selected['name']])):selected=t
    if selected:
        subprocess.run([a.blender,'-b',str(scene),'--python-exit-code','1','--python',str(root/'apply_recipe.py'),'--','--recipe',json.dumps(selected['recipe']),'--out',str(out/'refined.blend')],check=True)
        if not (out/'refined.blend').is_file():raise RuntimeError('Missing refined scene')
    (out/'selection.json').write_text(json.dumps({'scene':str(scene),'nevergrad_version':md.version('nevergrad'),'seed':a.seed,'cameras':cameras,'frames':frames,'validation_frames':vf,'trials':trials,'validation':validation,'selected':selected['name'] if selected else None,'recipe':selected['recipe'] if selected else None,'note':'Rendered lighting heuristic only; no artistic/gameplay approval.'},indent=2,allow_nan=False))
    print('Selected '+selected['name'] if selected else 'No validated improvement; retain original directed scene.')
if __name__=='__main__':main()
