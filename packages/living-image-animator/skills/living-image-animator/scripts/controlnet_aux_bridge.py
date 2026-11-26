#!/usr/bin/env python3
"""ComfyUI ControlNet Aux DWPose/OpenPose/AnimalPose -> measured pose-guide JSON.

Direct integration with REAL node JSON exposed by Save Pose Keypoints or
ComfyUI /history/{prompt_id} openpose_json. Pure standard library. Does NOT
render character pixels or fabricate annotations. Blocks missing/ambiguous
actors, implausible keypoints, fixed poses, discontinuities and wrong schemas.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

HUMAN18 = {'left_shoulder':5,'right_shoulder':2,'left_hip':11,'right_hip':8,
           'left_knee':12,'right_knee':9,'left_ankle':13,'right_ankle':10,
           'left_elbow':6,'right_elbow':3,'left_wrist':7,'right_wrist':4,
           'neck':1,'nose':0}
HUMAN25 = {**HUMAN18,'left_hip':12,'right_hip':9,'left_knee':13,'right_knee':10,
           'left_ankle':14,'right_ankle':11}
AP10K = {'nose':2,'neck':3,'tail_base':4,'left_shoulder':5,'right_shoulder':8,
         'front_left_foot':7,'front_right_foot':10,'hind_left_foot':13,
         'hind_right_foot':16,'left_hip':11,'right_hip':14}

class PoseAuxError(ValueError): pass

def _finite(x):
    return type(x) in (int,float) and math.isfinite(x)

def _safe_path(root,relative):
    if not isinstance(relative,str) or not relative or Path(relative).is_absolute():
        raise PoseAuxError('Pose JSON must be a scene-relative file')
    p=(root/relative).resolve()
    if p!=root and root not in p.parents:
        raise PoseAuxError('Pose JSON escapes scene directory')
    if not p.is_file():raise PoseAuxError('Missing pose JSON '+str(p))
    return p

def _extract(raw,config):
    # ComfyUI node `openpose_json` is an array of JSON-encoded batch strings.
    if isinstance(raw,dict) and 'openpose_json' in raw:
        values=raw['openpose_json']
        if not isinstance(values,list) or len(values)!=1:
            raise PoseAuxError('openpose_json must contain one unambiguous batch')
        raw=json.loads(values[0]) if isinstance(values[0],str) else values[0]
    if isinstance(raw,dict) and 'outputs' in raw:
        node=config.get('node_id')
        if not isinstance(node,(str,int)) or str(node) not in raw['outputs']:
            raise PoseAuxError('ComfyUI history requires exact node_id')
        return _extract(raw['outputs'][str(node)],config)
    if isinstance(raw,dict) and (config.get('prompt_id') or config.get('history_prompt_id')):
        pid=str(config.get('prompt_id') or config.get('history_prompt_id'))
        if pid not in raw:raise PoseAuxError('prompt_id absent from ComfyUI history')
        return _extract(raw[pid],config)
    if isinstance(raw,dict) and len(raw)==1 and isinstance(next(iter(raw.values())),dict):
        only=next(iter(raw.values()))
        if 'outputs' in only:return _extract(only,config)
    if isinstance(raw,dict) and 'poses' in raw:raw=raw['poses']
    if not isinstance(raw,list) or len(raw)<12:
        raise PoseAuxError('Need >=12 REAL sequential pose frames, not a still frame')
    if len(raw)>1500:raise PoseAuxError('Pose batch exceeds 1500 frames')
    return raw

def _read_raw(root,config,comfyui_base=None):
    keys=[x for x in ('json','history_json','prompt_id') if config.get(x)]
    if len(keys)!=1:raise PoseAuxError('Specify exactly one of json, history_json, prompt_id')
    if keys[0]=='prompt_id':
        url=comfyui_base or 'http://127.0.0.1:8188'
        u=urlparse(url)
        if u.scheme!='http' or u.hostname not in ('127.0.0.1','localhost','::1') or u.username or u.password or u.query or u.fragment:
            raise PoseAuxError('ComfyUI history requests restricted to local HTTP loopback')
        pid=str(config['prompt_id'])
        if not pid or not all(c.isascii() and (c.isalnum() or c in '-_') for c in pid):
            raise PoseAuxError('Unsafe ComfyUI prompt_id')
        with urlopen(f'{url.rstrip("/")}/history/{pid}',timeout=15) as response:
            data=response.read(16_000_001)
        if len(data)>16_000_000:raise PoseAuxError('ComfyUI history JSON too large')
        return json.loads(data),None
    path=_safe_path(root,config[keys[0]])
    if path.stat().st_size>16_000_000:raise PoseAuxError('Pose JSON too large')
    return json.loads(path.read_text('utf-8')),path

def _decoded_points(raw, count, width, height):
    if not isinstance(raw,list):raise PoseAuxError('Pose keypoints missing')
    if len(raw)==count*3 and all(_finite(x) for x in raw):
        triples=[raw[i:i+3] for i in range(0,len(raw),3)]
    elif len(raw)==count and all(isinstance(x,list) and len(x)>=3 for x in raw):
        triples=[x[:3] for x in raw]
    else:
        raise PoseAuxError(f'Expected exactly {count} x/y/confidence keypoints')
    # OpenPose poses in normalized or pixel units. Must be consistent across frames.
    high=max((max(abs(x),abs(y)) for x,y,c in triples if _finite(c) and c>.01),default=0)
    normalized=high<=1.00001
    pts=[]
    for x,y,c in triples:
        if not all(_finite(z) for z in (x,y,c)) or not 0<=c<=1.00001:
            raise PoseAuxError('Invalid keypoint coordinate/confidence')
        X=x*width if normalized else x
        Y=y*height if normalized else y
        if c>.1 and not (-2<=X<=width+2 and -2<=Y<=height+2):
            raise PoseAuxError('Keypoint outside reference canvas')
        pts.append(([float(X),float(Y)],float(c)))
    return pts

def _per_frame(frame, schema, config):
    if not isinstance(frame,dict):raise PoseAuxError('Frame must be a JSON object')
    w=frame.get('canvas_width');h=frame.get('canvas_height')
    if not (type(w) is int and type(h) is int and 16<=w<=8192 and 16<=h<=8192):
        raise PoseAuxError('canvas_width/canvas_height missing or invalid')
    if schema=='ap10k':
        if frame.get('version') not in ('ap10k',None):raise PoseAuxError('AnimalPose version mismatch')
        candidates=frame.get('animals',[])
        key=AP10K;count=17
    else:
        candidates=frame.get('people',[])
        key=HUMAN18 if schema=='openpose18' else HUMAN25
        count=18 if schema=='openpose18' else 25
    if not isinstance(candidates,list) or len(candidates)!=1:
        raise PoseAuxError(f'Require exactly one visible target per pose frame; found {len(candidates) if isinstance(candidates,list) else "invalid"}')
    item=candidates[0]
    if schema=='ap10k': pose=item
    else:
        if not isinstance(item,dict):raise PoseAuxError('Human person must be OpenPose person object')
        pose=item.get('pose_keypoints_2d')
    p=_decoded_points(pose,count,w,h)
    req= ('front_left_foot','front_right_foot','hind_left_foot','hind_right_foot','neck','tail_base') if schema=='ap10k' else ('left_hip','right_hip','left_ankle','right_ankle','left_knee','right_knee','left_shoulder','right_shoulder')
    threshold=float(config.get('confidence',.3))
    if not .1<=threshold<=.95:raise PoseAuxError('confidence must be within .1.. .95')
    for role in req:
        if p[key[role]][1]<threshold:
            raise PoseAuxError(f'Low-confidence or absent required joint {role}')
    return {'joints':{name:points[0] for name,idx in key.items() for points in [p[idx]] if points[1]>=threshold},
            'scores':{name:round(p[idx][1],5) for name,idx in key.items() if p[idx][1]>=threshold},
            'canvas':[w,h]}

def _movement(frames, schema):
    human=schema!='ap10k'
    h=[];separation=[];movements={}
    required=('left_ankle','right_ankle') if human else ('front_left_foot','front_right_foot','hind_left_foot','hind_right_foot')
    for name in required:movements[name]=[]
    for f in frames:
        j=f['joints']
        if human:
            root=[(j['left_hip'][i]+j['right_hip'][i])/2 for i in (0,1)]
            shoulders=[(j['left_shoulder'][i]+j['right_shoulder'][i])/2 for i in (0,1)]
            scale=math.dist(root,shoulders)*2.3
        else:
            root=j['tail_base'];scale=math.dist(j['neck'],root)
        if scale<3:raise PoseAuxError('Pose body scale too small for gait analysis')
        h.append(scale)
        for name in required:
            movements[name].append([(j[name][i]-root[i])/scale for i in (0,1)])
        separation.append((movements[required[0]][-1][0]-movements[required[1]][-1][0]))
    sweep={name:max(math.dist(a,b) for a in pos for b in pos) for name,pos in movements.items()}
    if human:
        if min(sweep.values())<.14 or max(separation)-min(separation)<.16:
            raise PoseAuxError('Human guide has insufficient alternating steps')
    else:
        front=max(separation)-min(separation)
        hind=[movements[required[2]][k][0]-movements[required[3]][k][0] for k in range(len(frames))]
        if sum(v>=.16 for v in sweep.values())<3 or front<.10 or max(hind)-min(hind)<.10:
            raise PoseAuxError('AnimalPose guide lacks genuine four-paw gait')
    if any(max(math.dist(a,b) for a,b in zip(pos,pos[1:]))>1.1 for pos in movements.values()):
        raise PoseAuxError('Pose tracking jumps between adjacent frames')
    return {'tracked_frames':len(frames),'joint_sweep':{k:round(v,4) for k,v in sweep.items()},
            'reference_only':True,'drawn_spot_positions_required':True}

def compile_reference(scene, actor, config, destination, comfyui_base=None):
    root=Path(scene).resolve().parent
    schema=config.get('schema')
    if schema not in ('openpose18','body25','ap10k'):
        raise PoseAuxError('Explicit schema must be openpose18, body25 or ap10k')
    role=actor.get('role')
    if schema=='ap10k' and role not in ('cat','dog','animal'):
        raise PoseAuxError('AP10K animal landmarks cannot certify human character')
    if schema!='ap10k' and role!='human':
        raise PoseAuxError('Human OpenPose landmarks cannot certify animal character')
    fps=config.get('fps')
    if not _finite(fps) or not 5<=fps<=240:raise PoseAuxError('Explicit reference FPS required (5..240)')
    raw,source=_read_raw(root,config,comfyui_base)
    batch=_extract(raw,config)
    items=[_per_frame(frame,schema,config) for frame in batch]
    if len({tuple(item['canvas']) for item in items})!=1:
        raise PoseAuxError('Canvas dimensions change across frames')
    metrics=_movement(items,schema)
    info={'engine':'comfyui-controlnet-aux','schema':schema,'reference_fps':fps,
          'actor_id':actor['id'],'node_id':str(config.get('node_id','')),
          'frames':[{'frame':i,'joints':v['joints'],'scores':v['scores']} for i,v in enumerate(items)],
          'canvas':items[0]['canvas'],'metrics':metrics,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest() if source else None,
          'source':'Real ComfyUI DWPose/OpenPose/AnimalPose pose output; DOES NOT generate actor cels'}
    destination=Path(destination).resolve();destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(info,ensure_ascii=False,indent=2),'utf8')
    return destination,source,metrics

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--scene',type=Path,required=True)
    p.add_argument('--actor',required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--comfyui-url',default=None)
    a=p.parse_args();scene=json.loads(a.scene.read_text('utf8'))
    actors=[z for z in scene.get('actors',[]) if z.get('id')==a.actor]
    if len(actors)!=1:raise PoseAuxError('Unknown or ambiguous actor id')
    config=actors[0].get('controlnet_aux_pose')
    if not isinstance(config,dict):raise PoseAuxError('Actor requires controlnet_aux_pose config')
    path,_,metrics=compile_reference(a.scene,actors[0],config,a.out,a.comfyui_url)
    print(json.dumps({'pose_guide':str(path),'metrics':metrics},ensure_ascii=False))

if __name__=='__main__':main()
