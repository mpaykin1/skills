#!/usr/bin/env python3
"""Strict 2D/2.5D world locomotion for humans and real four-foot quadrupeds.

Foot contacts are from AUTHOR-DRAWN pose cels, never inferred falsely from
video or DLC pose alone. No warping/deformation of characters is permitted.
"""
from __future__ import annotations
import math
import numpy as np

LOCO_ACTIONS={'walk','run','stairs_up','stairs_down'}
QUADRUPEDS={'cat','dog','animal'}
FEET=('front_left_foot','front_right_foot','hind_left_foot','hind_right_foot')
ALIASES={
  'front_left_foot':('front_left_foot','front_left_paw','front_left_hoof'),
  'front_right_foot':('front_right_foot','front_right_paw','front_right_hoof'),
  'hind_left_foot':('hind_left_foot','hind_left_paw','hind_left_hoof'),
  'hind_right_foot':('hind_right_foot','hind_right_paw','hind_right_hoof')}

class LocomotionError(ValueError):pass

def _num(x):return isinstance(x,(float,int)) and not isinstance(x,bool) and math.isfinite(x)

def sample(points,t):
    if t<=points[0][0]:return points[0][1:]
    if t>=points[-1][0]:return points[-1][1:]
    for a,b in zip(points,points[1:]):
        if a[0]<=t<=b[0]:
            u=(t-a[0])/(b[0]-a[0]);u=u*u*(3-2*u)
            return (a[1]+(b[1]-a[1])*u,a[2]+(b[2]-a[2])*u)
    raise LocomotionError('Unreachable path time')

def verify(actor,cycle_frames,canvas,fps):
    """Validate real world displacement without position teleportation/gliding."""
    actions={c.get('action') for c in actor.get('clips',[])}
    needs=actions&LOCO_ACTIONS
    loco=actor.get('locomotion')
    if not needs and not loco:return None
    if not loco:raise LocomotionError(f'{actor["id"]}: walk/run declared but world trajectory missing')
    mode=loco.get('mode')
    if mode not in LOCO_ACTIONS or mode not in needs:
        raise LocomotionError(f'{actor["id"]}: locomotion.mode must match an authored moving action')
    points=loco.get('path')
    if not isinstance(points,list) or len(points)<3:raise LocomotionError('Trajectory needs >=3 points and a closed seam')
    parsed=[]
    for p in points:
        if not isinstance(p,dict) or set(('frame','dx','dy'))-set(p):
            raise LocomotionError('Path point requires frame, dx, dy')
        f,dx,dy=p['frame'],p['dx'],p['dy']
        if not (type(f) is int and _num(dx) and _num(dy)):
            raise LocomotionError('Invalid locomotion frame/coordinates')
        parsed.append((f,float(dx),float(dy)))
    if parsed[0][0]!=0 or parsed[-1][0]!=cycle_frames:
        raise LocomotionError('Trajectory must span frame 0 to exact actor cycle length')
    if any(b[0]<=a[0] for a,b in zip(parsed,parsed[1:])):
        raise LocomotionError('Trajectory keyframes must increase')
    if math.dist(parsed[0][1:],parsed[-1][1:])>1:
        raise LocomotionError('Trajectory must return to initial world position at seam')
    pos=[sample(parsed,k) for k in range(cycle_frames+1)]
    x0,y0,w,h=map(int,actor['box']);W,H=canvas
    if any((x0+x<0 or y0+y<0 or x0+x+w>W or y0+y+h>H) for x,y in pos):
        raise LocomotionError('Character goes outside the scene; create art/occlusions')
    distances=[math.dist(a,b) for a,b in zip(pos,pos[1:])]
    travel=sum(distances);extent=max(math.dist(pos[0],p) for p in pos)
    if travel<max(12.,h*1.1) or extent<max(6.,h*.55):
        raise LocomotionError('Character walks/runs in place: world displacement too small')
    if max(distances)>max(4.5,h*.15):
        raise LocomotionError('Position teleports between adjacent 24fps frames')
    if math.dist(np.subtract(pos[1],pos[0]),np.subtract(pos[-1],pos[-2]))>max(4.,h*.11):
        raise LocomotionError('World trajectory velocity snaps at loop seam')
    seq_actions=[c['action'] for c in actor['clips'] for _ in range(len(c.get('frames',[])) or len(c.get('support_sequence',[])))]
    if len(seq_actions)==cycle_frames:
        nonmoving=sum(distances[i] for i,act in enumerate(seq_actions) if act not in LOCO_ACTIONS)
        if nonmoving>max(2.,travel*.10):
            raise LocomotionError('Path glides while actor not walking/running')
    if mode=='run' and max(distances)<max(.6,h*.012):
        raise LocomotionError('Running displacement visually imperceptible')
    return {'mode':mode,'path':parsed,'cycle_frames':cycle_frames,
            'world_travel_px':round(travel,2),'max_displacement_px':round(extent,2)}

def _joint_map(joints):
    if not isinstance(joints,dict):raise LocomotionError('Invalid quadruped joint map')
    mapped={}
    for foot,aliases in ALIASES.items():
        matches=[key for key in aliases if key in joints]
        if len(matches)!=1:
            raise LocomotionError(f'Each four-foot pose requires exactly one real landmark for {foot}')
        xy=joints[matches[0]]
        if not (isinstance(xy,list) and len(xy)==2 and all(_num(v) for v in xy)):
            raise LocomotionError('Invalid drawn foot landmark '+foot)
        mapped[foot]=xy
    return mapped

def _stance_set(source):
    if not isinstance(source,list) or len(set(source))!=len(source):
        raise LocomotionError('Quadruped support must be a list of distinct grounded feet (empty for flight)')
    out=set()
    for raw in source:
        found=next((canonical for canonical,names in ALIASES.items() if raw in names),None)
        if not found:raise LocomotionError('Unknown quadruped support foot '+str(raw))
        out.add(found)
    return out

def _quadruped_steps(actor,locomotion):
    """All 4 paws; stance contacts, locomotion phase, no hopping/walking in place."""
    all_positions=[];all_stances=[];all_actions=[]
    for clip in actor['clips']:
        action=clip.get('action');frames=clip.get('frames',[])
        if action not in LOCO_ACTIONS:
            all_positions.extend([None]*len(frames))
            all_stances.extend([None]*len(frames))
            all_actions.extend([action]*len(frames))
            continue
        supports=[f.get('support') for f in frames]
        if any(s is None for s in supports):supports=clip.get('support_sequence',[])
        if len(supports)!=len(frames):
            raise LocomotionError(f'{actor["id"]}/{action}: 1 real contact map per cel required')
        paws=[_joint_map(f.get('joints')) for f in frames]
        stance=[_stance_set(s) for s in supports]
        if action=='run' and not any(not s for s in stance):
            raise LocomotionError(f'{actor["id"]}/run: no independently DRAWN four-foot flight pose')
        if action!='run' and any(not s for s in stance):
            raise LocomotionError(f'{actor["id"]}/{action}: walking quadruped has airborne pose')
        if len(set(map(frozenset,stance)))<3:
            raise LocomotionError(f'{actor["id"]}/{action}: no meaningful four-foot stance alternation')
        if any(not any(p in s for s in stance) for p in FEET):
            raise LocomotionError(f'{actor["id"]}/{action}: at least one paw never contacts the ground')
        h=actor['box'][3]
        motion=[]
        for paw in FEET:
            root_relative=[[f[paw][0]-frame['joints']['root'][0],f[paw][1]-frame['joints']['root'][1]]
                           for f,frame in zip(paws,frames)]
            excursion=max(math.dist(a,b) for a in root_relative for b in root_relative)
            motion.append(excursion)
        if sum(d>=max(3.5,h*.14) for d in motion)<3:
            raise LocomotionError(f'{actor["id"]}/{action}: insufficient independent paw movement')
        all_positions.extend(paws)
        all_stances.extend(stance)
        all_actions.extend([action]*len(frames))
    # Foot must stay near world position while contact persists on adjacent cels.
    h=actor['box'][3]
    for i in range(len(all_positions)-1):
        if all_positions[i] is None or all_positions[i+1] is None:continue
        common=all_stances[i]&all_stances[i+1]
        if not common:continue
        p0=sample(locomotion['path'],i);p1=sample(locomotion['path'],i+1)
        for paw in common:
            f0=all_positions[i][paw];f1=all_positions[i+1][paw]
            if math.dist((p0[0]+f0[0],p0[1]+f0[1]),(p1[0]+f1[0],p1[1]+f1[1]))>max(3.5,h*.11):
                raise LocomotionError(f'{actor["id"]}: planted {paw} slides during {all_actions[i]}')

def validate_pose_steps(actor,sequence,locomotion):
    """Humans use ankles/left-right contacts; quadrupeds need four independent feet."""
    if locomotion is None:return
    mode=locomotion['mode']
    moving=[(i,src) for i,src in enumerate(sequence) if src[2] in LOCO_ACTIONS]
    if len(moving)<12:raise LocomotionError(f'{actor["id"]}: moving clips need >=12 authored gait poses')
    if actor.get('role') in QUADRUPEDS:
        _quadruped_steps(actor,locomotion)
        return
    for clip in actor['clips']:
        action=clip.get('action')
        if action not in LOCO_ACTIONS:continue
        pose_frames=clip.get('frames',[])
        supports=[f.get('support') for f in pose_frames]
        if any(s is None for s in supports) and isinstance(clip.get('support_sequence'),list):
            supports=clip['support_sequence']
        if len(supports)<12 or any(s not in ('left','right','flight','double') for s in supports):
            raise LocomotionError(f'{actor["id"]}/{mode}: every real pose requires foot support')
        if 'left' not in supports or 'right' not in supports:
            raise LocomotionError(f'{actor["id"]}/{mode}: gait never alternates grounded feet')
        if action=='run' and 'flight' not in supports:
            raise LocomotionError(f'{actor["id"]}/run: missing aerial running phase')
        if action!='run' and 'flight' in supports:
            raise LocomotionError(f'{actor["id"]}/walk: airborne pose requires run')
        joints=[f.get('joints',{}) for f in pose_frames]
        if not all('left_ankle' in j and 'right_ankle' in j for j in joints):
            raise LocomotionError(f'{actor["id"]}/{mode}: ankles must be drawn/annotated')
        shift=[j['left_ankle'][0]-j['right_ankle'][0] for j in joints]
        if max(shift)-min(shift)<max(3.5,actor['box'][3]*.20):
            raise LocomotionError(f'{actor["id"]}/{mode}: foot separation scarcely changes')
        start=sum(len(c.get('frames',[])) for c in actor['clips'][:actor['clips'].index(clip)])
        for i in range(len(supports)-1):
            stance=supports[i]
            if stance not in ('left','right') or supports[i+1]!=stance:continue
            ankle=stance+'_ankle';p0=sample(locomotion['path'],start+i);p1=sample(locomotion['path'],start+i+1)
            w0=(p0[0]+joints[i][ankle][0],p0[1]+joints[i][ankle][1])
            w1=(p1[0]+joints[i+1][ankle][0],p1[1]+joints[i+1][ankle][1])
            if math.dist(w0,w1)>max(3.5,actor['box'][3]*.11):
                raise LocomotionError(f'{actor["id"]}/{mode}: planted {stance} foot visibly slides')
