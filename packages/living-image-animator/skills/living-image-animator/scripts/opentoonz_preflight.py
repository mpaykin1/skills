#!/usr/bin/env python3
"""Fail-closed input validation for native OpenToonz / Pixelorama pose scenes.

This checks real source project and landmark metadata BEFORE any render. It
never invents cels, joint positions, transparent masks or missing levels.
"""
from __future__ import annotations
import argparse
import json
import math
import os
from pathlib import Path
import sys

class PreflightError(ValueError):
    pass


def source_file(root: Path, relative: str, label: str) -> Path:
    if not isinstance(relative, str) or not relative.strip():
        raise PreflightError(f'{label}: expected nonempty relative path')
    raw = Path(relative)
    if raw.is_absolute() or any(p == '..' for p in raw.parts):
        raise PreflightError(f'{label}: absolute/traversal paths forbidden: {relative}')
    root = root.resolve()
    resolved = (root / raw).resolve()
    if root not in resolved.parents:
        raise PreflightError(f'{label}: path must be inside scene directory: {relative}')
    if not resolved.is_file():
        raise PreflightError(f'{label}: source does not exist: {relative}')
    return resolved


def integer(value, min_value, max_value, label):
    if type(value) is not int or not min_value <= value <= max_value:
        raise PreflightError(f'{label}: integer in [{min_value},{max_value}] required')
    return value


def validate_landmarks(path: Path, count: int, width: int, height: int, actor: str):
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (ValueError, UnicodeError) as e:
        raise PreflightError(f'{actor}: invalid landmarks JSON: {e}') from e
    frames = data.get('frames') if isinstance(data, dict) else data
    if not isinstance(frames, list) or len(frames) != count:
        raise PreflightError(f'{actor}: {count} annotated poses required, found {len(frames) if isinstance(frames,list) else 0}')
    canonical = None
    for i, joints in enumerate(frames):
        if not isinstance(joints, dict) or 'root' not in joints or len(joints) < 3:
            raise PreflightError(f'{actor} frame {i}: root + 2 genuine visible joints required')
        names = frozenset(joints)
        if canonical is None:
            canonical = names
        if names != canonical:
            raise PreflightError(f'{actor} frame {i}: anatomical joint names changed')
        for name, pt in joints.items():
            if not (isinstance(pt, (list, tuple)) and len(pt) == 2 and
                    all(type(v) in (int,float) and math.isfinite(v) for v in pt) and
                    0 <= pt[0] < width and 0 <= pt[1] < height):
                raise PreflightError(f'{actor} frame {i}: {name} is not a finite visible pixel coordinate')


def validate_scene(scene_path: Path) -> dict:
    scene_path = Path(scene_path).resolve()
    try:
        data = json.loads(scene_path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as e:
        raise PreflightError(f'Cannot load scene JSON: {e}') from e
    if not isinstance(data, dict) or not isinstance(data.get('actors'), list):
        raise PreflightError('scene.json needs actors list')
    inv = data.get('inventory', {}).get('actors')
    ids = [a.get('id') for a in data['actors'] if isinstance(a, dict)]
    if len(ids) != len(data['actors']) or not all(isinstance(i,str) and i for i in ids):
        raise PreflightError('All actors need nonempty stable IDs')
    if len(set(ids)) != len(ids) or not isinstance(inv, list) or len(inv) != len(ids) or set(inv) != set(ids):
        raise PreflightError('Inventory must match every actor ID exactly, with no duplicates')
    root = scene_path.parent
    summary = {'actors':len(ids),'opentoonz_clips':0,'pixelorama_clips':0,'native_clips':0,'scene':str(scene_path)}
    for a in data['actors']:
        aid = a['id']
        box = a.get('box')
        if not isinstance(box,list) or len(box)!=4 or not all(type(x) is int for x in box) or box[2]<8 or box[3]<8:
            raise PreflightError(f'{aid}: integer sprite box [x,y,w,h] with w,h>=8 required')
        source_file(root, a.get('source_mask'), aid+'.source_mask')
        clips = a.get('clips')
        if not isinstance(clips,list) or len(clips)<2:
            raise PreflightError(f'{aid}: at least 2 independently authored action clips required')
        actions = []
        for ci,c in enumerate(clips):
            if not isinstance(c,dict):
                raise PreflightError(f'{aid}: invalid clip {ci}')
            action = c.get('action')
            if not isinstance(action,str) or not action.strip() or action in actions:
                raise PreflightError(f'{aid}: each action needs a distinct nonempty name')
            actions.append(action)
            label = f'{aid}/{action}'
            kinds = [k for k in ('opentoonz_scene','pixelorama_project','frames') if k in c]
            if len(kinds) != 1:
                raise PreflightError(f'{label}: exactly one .tnz, .pxo or full-frame PNG source required')
            if kinds[0]=='opentoonz_scene':
                scene = source_file(root,c['opentoonz_scene'],label+'.opentoonz_scene')
                if scene.suffix.lower()!='.tnz':
                    raise PreflightError(f'{label}: use native .tnz scene, not a still PNG')
                start = integer(c.get('start_frame',1),1,100000,label+'.start_frame')
                count = integer(c.get('frame_count'),12,720,label+'.frame_count')
                if start+count>100000:
                    raise PreflightError(f'{label}: frame range too large')
                joints = source_file(root,c.get('joints_json'),label+'.joints_json')
                validate_landmarks(joints,count,box[2],box[3],label)
                deps = c.get('dependencies',[])
                if not isinstance(deps,list) or len(deps)!=len(set(map(str,deps))):
                    raise PreflightError(f'{label}: duplicate or malformed dependencies')
                for dep in deps:
                    source_file(root,dep,label+'.dependencies')
                summary['opentoonz_clips']+=1
            elif kinds[0]=='pixelorama_project':
                project=source_file(root,c['pixelorama_project'],label+'.pixelorama_project')
                if project.suffix.lower()!='.pxo':
                    raise PreflightError(f'{label}: expected .pxo')
                source_file(root,c.get('joints_json'),label+'.joints_json')
                summary['pixelorama_clips']+=1
            else:
                frames=c['frames']
                if not isinstance(frames,list) or len(frames)<12:
                    raise PreflightError(f'{label}: need >=12 independent full-pose PNG frames')
                for n,f in enumerate(frames):
                    if not isinstance(f,dict) or 'joints' not in f:
                        raise PreflightError(f'{label} frame {n}: missing annotated full-pose object')
                    source_file(root,f.get('png'),label+f'.frames[{n}]')
                summary['native_clips']+=1
    if not summary['opentoonz_clips']:
        summary['message']='No .tnz clips; original pose delivery will handle other sources'
    return summary


def main():
    parser=argparse.ArgumentParser(description='Validate native OpenToonz scene references without substituting poses')
    parser.add_argument('scene',type=Path)
    args=parser.parse_args()
    try:
        print(json.dumps(validate_scene(args.scene),ensure_ascii=False,indent=2))
    except PreflightError as e:
        print('OpenToonz preflight blocked: '+str(e),file=sys.stderr)
        raise SystemExit(2)

if __name__=='__main__':
    main()
