#!/usr/bin/env python3
"""DeepLabCut -> source-grounded quadruped motion guides; no generated character pixels.

Reads actual DLC Pandas MultiIndex CSV/HDF5 predictions, optionally runs an
installed DeepLabCut model on a video. Supports single- and multi-animal DLC
outputs with explicit tracking identity; never guesses missing joints.
"""
from __future__ import annotations
import argparse
import json
import math
import shutil
import tempfile
from pathlib import Path

REQUIRED=('hip','shoulder','front_left_foot','front_right_foot','hind_left_foot','hind_right_foot')
OPTIONAL=('head','tail_base')

class AnimalMotionError(ValueError): pass

def finite(v):return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)

def safe_source(p):
    p=Path(p).resolve()
    if not p.is_file():raise AnimalMotionError('Missing DeepLabCut source '+str(p))
    if p.suffix.lower() not in ('.csv','.h5','.hdf5'):
        raise AnimalMotionError('DeepLabCut predictions must be .csv or .h5')
    return p

def read_table(source):
    try:import pandas as pd
    except ImportError as exc:raise AnimalMotionError('pandas required for DeepLabCut CSV/HDF5 input') from exc
    p=safe_source(source)
    try:
        if p.suffix.lower() in ('.h5','.hdf5'):
            table=pd.read_hdf(p,key='df_with_missing')
        else:
            import csv
            with p.open(newline='',encoding='utf-8-sig') as handle:
                headers=list(csv.reader(handle))[:4]
            if len(headers)<4 or not headers[0] or not headers[1] or not headers[2]:
                raise AnimalMotionError('Truncated DeepLabCut CSV MultiIndex headers')
            axis_row=next((i for i in (2,3) if i<len(headers) and any(s.strip()=='coords' for s in headers[i][:2])),None)
            # DLC saved pandas MultiIndex uses 3 header rows for single animal
            # and 4 header rows for multi-animal, indexed by header labels.
            labels=[str(row[0]).strip().lower() for row in headers]
            depth=4 if 'individuals' in labels[:4] else 3
            if labels[0]!='scorer' or (depth==3 and 'bodyparts' not in labels[:3]) or (depth==4 and 'bodyparts' not in labels[:4]):
                raise AnimalMotionError('CSV is not a DeepLabCut scorer/bodyparts/coords table')
            table=pd.read_csv(p,header=list(range(depth)),index_col=0)
    except AnimalMotionError:raise
    except Exception as exc:raise AnimalMotionError('Cannot parse DeepLabCut prediction table: '+str(exc)) from exc
    if not isinstance(table.columns,pd.MultiIndex) or table.columns.nlevels not in (3,4):
        raise AnimalMotionError('DLC predictions need 3/4-level MultiIndex columns')
    if len(table)<12:raise AnimalMotionError('DLC reference requires >=12 actual frames')
    return table

def frame_tracks(table,bodypart_map,individual=None,scorer=None,confidence=.6,fps=24):
    if not isinstance(bodypart_map,dict) or any(k not in bodypart_map for k in REQUIRED):
        raise AnimalMotionError('Explicit bodypart_map must map hip/shoulder/all four feet')
    if len(set(bodypart_map.values()))!=len(bodypart_map):
        raise AnimalMotionError('Body part mappings must be unique; do not reuse one paw')
    if not finite(fps) or not 5<=fps<=240:raise AnimalMotionError('Source FPS must be 5..240')
    if not finite(confidence) or not .3<=confidence<=1.:
        raise AnimalMotionError('Confidence cutoff must be .3..1')
    cols=list(table.columns);levels=len(cols[0]);multi=levels==4
    scorer_values=sorted(set(str(c[0]) for c in cols))
    if scorer is None:
        if len(scorer_values)!=1:raise AnimalMotionError('Multiple scorer names; specify scorer')
        scorer=scorer_values[0]
    if scorer not in scorer_values:raise AnimalMotionError('Unknown DLC scorer')
    if multi:
        candidates=sorted(set(str(c[1]) for c in cols if str(c[0])==scorer))
        if individual is None:
            if len(candidates)!=1:raise AnimalMotionError('Multi-animal DLC requires explicit individual identity')
            individual=candidates[0]
        if individual not in candidates:raise AnimalMotionError('Unknown tracked individual')
    elif individual is not None:
        raise AnimalMotionError('Single-animal DLC table has no individual level')
    def series_name(part,axis):
        return (scorer,individual,part,axis) if multi else (scorer,part,axis)
    bodyparts=set(str(c[-2]) for c in cols)
    for role,part in bodypart_map.items():
        if role not in REQUIRED+OPTIONAL:raise AnimalMotionError('Unsupported canonical body part '+role)
        if not isinstance(part,str) or part not in bodyparts:
            raise AnimalMotionError(f'Expected real DLC bodypart {part!r} for {role}')
        if not all(series_name(part,axis) in table.columns for axis in ('x','y','likelihood')):
            raise AnimalMotionError(f'{part} lacks x/y/likelihood coordinates')
    tracks=[]
    for i in range(len(table)):
        row=table.iloc[i]
        joints={};scores={}
        for role,part in bodypart_map.items():
            vals=[float(row[series_name(part,axis)]) for axis in ('x','y','likelihood')]
            if not all(finite(v) for v in vals) or vals[2]<confidence:
                raise AnimalMotionError(f'Low-confidence or missing {role} at source frame {i}')
            joints[role]=[round(vals[0],5),round(vals[1],5)]
            scores[role]=round(vals[2],5)
        tracks.append({'frame':i,'joints':joints,'scores':scores})
    return {'engine':'deeplabcut','schema':'quadruped-v1','fps':fps,'individual':individual,
            'scorer':scorer,'bodypart_map':bodypart_map,'confidence_cutoff':confidence,
            'frames':tracks,'source':'DeepLabCut prediction table; no synthetic keypoints'}

def read_guide(path):
    p=Path(path).resolve()
    if not p.is_file():raise AnimalMotionError('Missing DLC guide '+str(p))
    data=json.loads(p.read_text('utf8'))
    if data.get('engine')!='deeplabcut' or data.get('schema')!='quadruped-v1':
        raise AnimalMotionError('Only DeepLabCut quadruped-v1 guides supported')
    if not finite(data.get('fps')) or not 5<=data['fps']<=240:
        raise AnimalMotionError('Invalid guide FPS')
    frames=data.get('frames')
    if not isinstance(frames,list) or len(frames)<12:raise AnimalMotionError('Too few actual reference frames')
    for i,item in enumerate(frames):
        if not isinstance(item,dict) or item.get('frame')!=i:raise AnimalMotionError('Non-consecutive DLC frames')
        joints=item.get('joints',{});scores=item.get('scores',{})
        for part in REQUIRED:
            xy=joints.get(part);score=scores.get(part)
            if not isinstance(xy,list) or len(xy)!=2 or not all(finite(v) for v in xy):
                raise AnimalMotionError(f'Frame {i}: missing {part}')
            if not finite(score) or score<data.get('confidence_cutoff',.6):
                raise AnimalMotionError(f'Frame {i}: unreliable {part}')
    return data

def gait_metrics(guide,mode):
    if mode not in ('walk','run','stairs_up','stairs_down'):
        raise AnimalMotionError('Quadruped gait requires walk/run/stairs')
    frames=guide['frames']
    parts=REQUIRED[2:]
    tracks={p:[] for p in parts}
    torso_lengths=[]
    for fr in frames:
        j=fr['joints'];hip=j['hip'];shoulder=j['shoulder']
        span=math.dist(hip,shoulder)
        if span<3:raise AnimalMotionError('Unusable shoulder/hip scale')
        torso_lengths.append(span)
        for p in parts:
            tracks[p].append([(j[p][0]-hip[0])/span,(j[p][1]-hip[1])/span])
    # Root-relative motion; pan of entire video cannot satisfy gait.
    motion={}
    for name,positions in tracks.items():
        xs=[xy[0] for xy in positions];ys=[xy[1] for xy in positions]
        motion[name]=round(math.hypot(max(xs)-min(xs),max(ys)-min(ys)),4)
    active=[p for p,m in motion.items() if m>=.16]
    fore_d=[tracks['front_left_foot'][i][0]-tracks['front_right_foot'][i][0] for i in range(len(frames))]
    hind_d=[tracks['hind_left_foot'][i][0]-tracks['hind_right_foot'][i][0] for i in range(len(frames))]
    front_sweep=max(fore_d)-min(fore_d);hind_sweep=max(hind_d)-min(hind_d)
    if len(active)<3 or front_sweep<.10 or hind_sweep<.10:
        raise AnimalMotionError('DLC clip lacks 3 active paws and independent front/hind steps')
    return {'engine':'deeplabcut','mode':mode,'frames':len(frames),'source_fps':guide['fps'],
            'normalized_paw_sweeps':motion,'active_paws':len(active),
            'front_lr_sweep':round(front_sweep,4),'hind_lr_sweep':round(hind_sweep,4),
            'note':'2D reference movement only; real foot contacts and airborne run verified by drawn PNG poses'}

def analyze_video(config,video,dest,bodypart_map,individual=None,fps=24,confidence=.6,scorer=None):
    """Call installed DeepLabCut with a trained user model; never download weights."""
    config=Path(config).resolve();video=Path(video).resolve();dest=Path(dest).resolve()
    if not config.is_file() or not video.is_file():raise AnimalMotionError('DLC config.yaml and actual reference video required')
    try:import deeplabcut
    except ImportError as exc:raise AnimalMotionError('DeepLabCut not installed; provide exported CSV/H5 or install trained DLC') from exc
    with tempfile.TemporaryDirectory(prefix='dlc_living_') as tmp:
        try:deeplabcut.analyze_videos(str(config),[str(video)],save_as_csv=True,destfolder=tmp)
        except Exception as exc:raise AnimalMotionError('DeepLabCut video analysis failed: '+str(exc)) from exc
        files=sorted(Path(tmp).glob('*.csv'))
        if len(files)!=1:raise AnimalMotionError(f'DLC expected exactly one CSV output, got {len(files)}')
        table=read_table(files[0])
        data=frame_tracks(table,bodypart_map,individual,scorer,confidence,fps)
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf8')
        return dest

def compile_csv_or_h5(source,out,bodypart_map,individual=None,scorer=None,confidence=.6,fps=24):
    data=frame_tracks(read_table(source),bodypart_map,individual,scorer,confidence,fps)
    out=Path(out).resolve();out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf8')
    return out

def main():
    p=argparse.ArgumentParser(description='Use real DeepLabCut animal motion as an animation guide')
    p.add_argument('--predictions',type=Path)
    p.add_argument('--guide',type=Path)
    p.add_argument('--video',type=Path)
    p.add_argument('--config',type=Path)
    p.add_argument('--out',type=Path)
    p.add_argument('--bodypart-map',type=Path)
    p.add_argument('--fps',type=float,default=24.)
    p.add_argument('--confidence',type=float,default=.6)
    p.add_argument('--individual')
    p.add_argument('--scorer')
    p.add_argument('--mode',choices=('walk','run','stairs_up','stairs_down'),default='walk')
    a=p.parse_args()
    if sum(v is not None for v in (a.predictions,a.guide,a.video))!=1:
        p.error('Choose exactly one --predictions/--guide/--video')
    if a.guide:data=read_guide(a.guide)
    else:
        if not a.out or not a.bodypart_map:p.error('DLC analysis requires --out and --bodypart-map JSON')
        mapping=json.loads(a.bodypart_map.read_text('utf8'))
        if a.video:
            if not a.config:p.error('--config trained DLC config.yaml is required with video')
            guide=analyze_video(a.config,a.video,a.out,mapping,a.individual,a.fps,a.confidence,a.scorer)
        else:guide=compile_csv_or_h5(a.predictions,a.out,mapping,a.individual,a.scorer,a.confidence,a.fps)
        data=read_guide(guide)
    print(json.dumps(gait_metrics(data,a.mode),ensure_ascii=False))

if __name__=='__main__':main()
