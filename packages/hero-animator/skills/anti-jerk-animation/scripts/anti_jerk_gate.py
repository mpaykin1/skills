#!/usr/bin/env python3
"""Strict anti-jerk validation of released GIFs, character art, camera, and loop.
Rejects temporal scene cuts, non-looping/strobed GIFs, missing full-body frames,
and camera teleports; structural result is not artistic approval.
"""
from __future__ import annotations
import argparse, json, math, statistics, hashlib
from pathlib import Path
import numpy as np
from PIL import Image

def validate(gif_path:Path,manifest:Path,scene:Path):
    if not all(p.is_file() for p in [gif_path,manifest,scene]):
        raise ValueError('BLOCKED: GIF, manifest and scene plan are all required')
    im=Image.open(gif_path)
    try:return _validate_open_gif(im,manifest,scene)
    finally:im.close()

def _validate_open_gif(im,manifest,scene):
    if im.format!='GIF' or im.info.get('loop')!=0:
        raise ValueError('BLOCKED: real infinitely looping GIF is required')
    w,h=im.size
    if not (.55 <= w/h <= .575):raise ValueError('BLOCKED: expected portrait 9:16')
    if im.n_frames < 1000:raise ValueError('BLOCKED: new 40s scene needs 1000+ rendered frames')
    m=json.loads(manifest.read_text('utf-8'))
    s=json.loads(scene.read_text('utf-8'))
    durations=[];deltas=[];previous=None;first=None;last=None
    # To disambiguate full-body sprite switches from architectural cuts, inspect a
    # stable upper architectural region, outside the foreground hero sprite.
    for i in range(im.n_frames):
        im.seek(i)
        durations.append(im.info.get('duration',100))
        a=np.asarray(im.convert('L').resize((160,284)),dtype=np.int16)[:148]
        if first is None:first=a
        if previous is not None:deltas.append(float(np.abs(a-previous).mean()))
        previous=a;last=a
    seconds=sum(durations)/1000
    fps=im.n_frames/seconds
    if not (40<=seconds<=60):raise ValueError(f'BLOCKED: loop {seconds:.2f}s outside 40–60s')
    if fps<24.9:raise ValueError(f'BLOCKED: jerk risk at {fps:.2f} FPS, need 25 FPS')
    typical=max(1,statistics.median(deltas))
    if np.quantile(deltas,.995)>max(12,2.5*typical):
        raise ValueError('BLOCKED: sudden room cut / full-image flash')
    seam=float(np.abs(last-first).mean())
    if seam>max(8,2.4*typical):
        raise ValueError(f'BLOCKED: broken last-to-first seam ({seam:.2f} vs {typical:.2f})')
    camera=s.get('camera',{})
    laps=float(camera.get('laps',0)); world_width=float(camera.get('width_pixels',0))
    if laps<=0 or world_width<=0:
        raise ValueError('BLOCKED: no documented looped camera/world coordinates')
    frame_step=laps*world_width/im.n_frames
    if frame_step > 2.5*(w/240):
        raise ValueError(f'BLOCKED: camera moves {frame_step:.2f}px/frame; limit is 2.5px at 240px output')
    characters=m.get('characters')
    if not isinstance(characters,list) or not characters:
        raise ValueError('BLOCKED: no separate character sprite sequences')
    for actor in characters:
        frames=actor.get('poseFrames',[])
        hashes=actor.get('poseSHA256',[])
        if len(frames)<8 or len(frames)!=len(hashes):
            raise ValueError('BLOCKED: fewer than 8 named artist-authored pose files')
        checks=[];dims=[]
        for p,hsh in zip(frames,hashes):
            file=manifest.parent/p
            if not file.is_file() or file.suffix.lower()!='.png':
                raise ValueError('BLOCKED: missing RGBA pose')
            if hashlib.sha256(file.read_bytes()).hexdigest()!=hsh:
                raise ValueError('BLOCKED: sprite SHA256 mismatch')
            with Image.open(file) as sr:
                if sr.mode!='RGBA':raise ValueError('BLOCKED: character frame not RGBA')
                dims.append(sr.size)
                checks.append(hashlib.sha256(sr.tobytes()).digest())
        if len(set(dims))!=1 or len(set(checks))<8:
            raise ValueError('BLOCKED: sprite poses are duplicated or misframed')
    return {'status':'STRUCTURALLY SMOOTH / ARTIST REVIEW REQUIRED',
            'fps':round(fps,2),'frames':im.n_frames,'seconds':round(seconds,2),
            'seam_mean_abs':round(seam,3),'typical_background_delta':round(typical,3),
            'camera_step_px_per_frame':round(frame_step,3),'characters':len(characters)}

def validate_game_replay(replay_path:Path,manifest:Path,scene:Path):
    """Interactive games have user-triggered starts/stops, not a GIF's 40-second seam.
    Check real sampled world motion, causal input and clip/speed agreement instead.
    This is not a pixel-flicker, GPU FPS, collision-engine or artistic certificate.
    """
    replay=json.loads(replay_path.read_text('utf8'));plan=json.loads(scene.read_text('utf8'))
    if replay.get('kind')!='hero-game-replay' or plan.get('kind')!='interactive-game':
        raise ValueError('BLOCKED: explicit interactive-game replay/scene required')
    if plan.get('motionProfile')!='ash-adventure-v1':
        raise ValueError('BLOCKED: unsupported motion profile; this preset is for the measured Ash Adventure runtime')
    viewport=replay.get('viewport',{})
    if viewport!=plan.get('viewport') or not all(isinstance(viewport.get(k),int) and viewport[k]>0 for k in ('width','height')):
        raise ValueError('BLOCKED: matching measured viewport required')
    actors=json.loads(manifest.read_text('utf8')).get('characters',[])
    if not actors:raise ValueError('BLOCKED: character frame manifest required')
    for actor in actors:
        paths=actor.get('poseFrames',[]);hashes=actor.get('poseSHA256',[])
        if len(paths)<8 or len(paths)!=len(hashes):raise ValueError('BLOCKED: 8 real full-body pose files required')
        decoded=set();sizes=set()
        for rel,expected in zip(paths,hashes):
            p=(manifest.parent/rel).resolve()
            if manifest.parent.resolve() not in p.parents or p.suffix.lower()!='.png' or not p.is_file():raise ValueError('BLOCKED: invalid pose path')
            if hashlib.sha256(p.read_bytes()).hexdigest()!=expected:raise ValueError('BLOCKED: pose hash changed')
            with Image.open(p) as im:
                if im.mode!='RGBA':raise ValueError('BLOCKED: RGBA poses required')
                decoded.add(hashlib.sha256(im.tobytes()).digest());sizes.add(im.size)
        if len(decoded)<8 or len(sizes)!=1:raise ValueError('BLOCKED: distinct stable-canvas poses required')
    samples=replay.get('samples',[])
    if len(samples)<60:raise ValueError('BLOCKED: at least 60 actual rendered-frame samples required')
    hero=plan.get('heroId');previous=None;max_step=0.;max_speed=0.
    move_keys={'KeyW','KeyA','KeyS','KeyD','ArrowUp','ArrowDown','ArrowLeft','ArrowRight','up','down','left','right'}
    dash_actions={'dodge','roll'}
    for row in samples:
        if row.get('heroId')!=hero or not hero:raise ValueError('BLOCKED: actor identity changed')
        values=[row.get('gameTime'),row.get('wallTimeMs')]+[row.get('position',{}).get(k) for k in ('x','y','z')]+[row.get('camera',{}).get(k) for k in ('x','y','z')]
        if not all(isinstance(v,(int,float)) and math.isfinite(v) for v in values):raise ValueError('BLOCKED: nonfinite trajectory')
        if row.get('glError')!=0:raise ValueError('BLOCKED: WebGL error in rendered run')
        if not isinstance(row.get('frame'),int) or not 0<=row['frame']<8:raise ValueError('BLOCKED: invalid authored pose index')
        if previous:
            dt=row['gameTime']-previous['gameTime'];wall=row['wallTimeMs']-previous['wallTimeMs']
            if dt<0 or dt>.051 or wall<0:raise ValueError('BLOCKED: discontinuous/reversed game clock')
            camera_step=math.sqrt(sum((row['camera'][k]-previous['camera'][k])**2 for k in ('x','y','z')))
            if camera_step>15*wall/1000+.35:raise ValueError('BLOCKED: camera teleport in recorded follow-camera run')
            dx=row['position']['x']-previous['position']['x'];dz=row['position']['z']-previous['position']['z'];step=math.hypot(dx,dz)
            max_step=max(max_step,step)
            if step>7*dt+1e-5:raise ValueError('BLOCKED: character teleport or excess displacement')
            action=row.get('action');prior=previous.get('action')
            keys=set(row.get('held',[]))|set(previous.get('held',[]))
            if step>1e-5 and not move_keys.intersection(keys) and action not in dash_actions and prior not in dash_actions:
                raise ValueError('BLOCKED: unsolicited character locomotion')
            if dt>0 and step>1e-5:
                speed=step/dt;max_speed=max(max_speed,speed)
                if action=='run' and prior=='run' and speed<5.9:raise ValueError('BLOCKED: run clip at walking speed')
                if action=='walk' and prior=='walk' and speed>3.9:raise ValueError('BLOCKED: walk clip at sprint speed')
        previous=row
    if samples[-1]['wallTimeMs']-samples[0]['wallTimeMs']<2000:raise ValueError('BLOCKED: sampled run too short')
    return {'status':'GAME MOTION STRUCTURE PASS / ARTIST REVIEW REQUIRED','samples':len(samples),
            'max_step_world_units':round(max_step,6),'max_speed_world_units_per_second':round(max_speed,6),
            'scope':'Ash Adventure sampled XZ/input/clock/clip agreement, follow-camera continuity and source poses only; no GIF seam, GPU FPS or artistic claim'}

def main():
    a=argparse.ArgumentParser()
    a.add_argument('gif',type=Path,nargs='?');a.add_argument('--manifest',type=Path,required=True)
    a.add_argument('--game-replay',type=Path,help='Actual rendered interactive-game samples; GIF validation is unchanged')
    a.add_argument('--scene',type=Path,required=True)
    args=a.parse_args()
    try:
        if bool(args.gif)==bool(args.game_replay):raise ValueError('Choose GIF or --game-replay, not both')
        result=validate_game_replay(args.game_replay,args.manifest,args.scene) if args.game_replay else validate(args.gif,args.manifest,args.scene)
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except (ValueError,OSError,KeyError) as e:raise SystemExit(str(e))
if __name__=='__main__':main()

