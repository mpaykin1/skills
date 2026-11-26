"""Audit foot drift during authored contacts; not a visual approval."""
import argparse,json,math,pathlib,sys
p=argparse.ArgumentParser();p.add_argument('motion',type=pathlib.Path);p.add_argument('--max-drift-m',type=float,default=.04);a=p.parse_args();d=json.loads(a.motion.read_text());assert d['schema']=='rigify-motion-v1' and 0<a.max_drift_m<1
errors=[]
for name,c in d['clips'].items():
    frames={f['frame']:f for f in c['frames']}; vel=c['root_velocity_mps'];assert len(vel)==3 and all(math.isfinite(v) for v in vel)
    for foot,intervals in c['contacts'].items():
        for lo,hi in intervals:
            f0=frames[lo];p0=f0['world'][foot]
            drift=max(math.dist(p0,[frames[f]['world'][foot][i]+vel[i]*(frames[f]['time']-f0['time']) for i in range(3)]) for f in range(lo,hi+1))
            if not math.isfinite(drift) or drift>a.max_drift_m: errors.append(f'{name} {foot} {lo}:{hi} drift={drift:.3f}m')
print('\n'.join(errors) if errors else 'Contact metric within threshold; visual front/side/back review still required');sys.exit(bool(errors))
