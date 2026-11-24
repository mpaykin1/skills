#!/usr/bin/env python3
"""Author 8 directional recipes or an orbit for Grange's canonical stack_pipeline.
The same approved stack, camera scale, source hashes and part IDs are retained.
Parent-local poses are flattened to world rigid transforms before rendering.
"""
import argparse, json, math, copy
from pathlib import Path
import numpy as np
from stack_pipeline import rotation, finite, sha


def euler(r):
    y=math.asin(float(np.clip(-r[2,0],-1,1)))
    if abs(math.cos(y))>1e-7:
        x=math.atan2(r[2,1],r[2,2]);z=math.atan2(r[1,0],r[0,0])
    else:
        x=0.;z=math.atan2(-r[0,1],r[1,1])
    return np.degrees([x,y,z]).tolist()


def local_track(default, spec, phase, key):
    v=finite(default,3).copy()
    if 'turns' in spec:
        if key!='rotation_deg':raise ValueError('turns only for rotation')
        turns=finite(spec['turns'],3)
        if not np.allclose(turns,np.rint(turns)):raise ValueError('cyclic turns must be integral')
        v+=360*turns*phase
    if 'amplitude' in spec:
        c=float(spec.get('cycles',1));d=float(spec.get('phase_deg',0))/360
        if c<=0 or not math.isclose(c,round(c)) or not math.isfinite(d):raise ValueError('invalid cycle')
        v+=finite(spec['amplitude'],3)*math.sin(2*math.pi*(c*phase+d))
    if not np.isfinite(v).all():raise ValueError('invalid animated pose')
    return v


def motion(base,n,yaw,pitch,tracks,orbit):
    m=copy.deepcopy(base);parts={p['id']:p for p in m['parts']}
    if len(parts)!=len(m['parts']) or not parts or set(tracks)-parts.keys():raise ValueError('invalid part IDs/tracks')
    if m['schema']!='grange-stack-v1':raise ValueError('canonical recipe schema required')
    frames=[]
    for i in range(n):
        phase=i/n;resolved={}
        def world(name,ancestry=()):
            if name in resolved:return resolved[name]
            if name not in parts or name in ancestry:raise ValueError('unknown or cyclic parent')
            p=parts[name];spec=tracks.get(name,{})
            t=local_track(p.get('translation',[0,0,0]),spec.get('translation',{}),phase,'translation')
            r=rotation(local_track(p.get('rotation_deg',[0,0,0]),spec.get('rotation_deg',{}),phase,'rotation_deg'))
            if p.get('parent'):
                pt,pr=world(p['parent'],ancestry+(name,));t=pt+pr@t;r=pr@r
            resolved[name]=(t,r);return t,r
        pose={}
        for name in parts:
            t,r=world(name);pose[name]={'translation':t.tolist(),'rotation_deg':euler(r)}
        frames.append({'camera':[yaw+(360*phase if orbit else 0),pitch],'parts':pose})
    for p in m['parts']:p.pop('parent',None)
    m['frames']=frames;m['once']=False;return m


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('base');p.add_argument('--mode',choices=['orbit','drive8','fixed'],default='orbit');p.add_argument('--frames',type=int,default=16);p.add_argument('--yaw',type=float,default=0);p.add_argument('--pitch',type=float,default=65);p.add_argument('--tracks');a=p.parse_args()
    if not 12<=a.frames<=24 or not -90<=a.pitch<=90:raise ValueError('Grange frames/pitch limits')
    base=Path(a.base).resolve();m=json.loads(base.read_text());tracks=json.loads(Path(a.tracks).read_text()) if a.tracks else {}
    if sha(base.parent/m['source_art'])!=m['source_art_sha256']:raise ValueError('source art changed')
    for part in m['parts']:
        if sha(base.parent/part['stack'])!=part['stack_sha256']:raise ValueError('stack manifest changed')
    yaws=[a.yaw+45*i for i in range(8)] if a.mode=='drive8' else [a.yaw]
    for y in yaws:
        s=motion(m,a.frames,y,a.pitch,tracks,a.mode=='orbit');name='orbit.recipe.json' if a.mode=='orbit' else f'direction_{int(y)%360:03}.recipe.json';dest=base.parent/name
        dest.write_text(json.dumps(s,indent=2));print(str(dest))

if __name__=='__main__':main()
