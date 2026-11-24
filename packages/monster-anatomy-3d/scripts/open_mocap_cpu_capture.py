#!/usr/bin/env python3
"""Open Mocap CPU video -> 40 landmark coordinates for existing MONSTER_RIG.

Derived pose normalizer from Larenju-Rai/open-mocap-blender MIT, pinned commit
1ec7457dad228661cbd8a1d98163e8288d3f7db5. Runs WITHOUT Blender 4.0.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'vendor'))
from open_mocap_cpu_pose import PoseTrackingCPU


def capture(path,max_frames):
    try:
        import cv2
    except ImportError as e:
        raise RuntimeError('Install opencv-python-headless and requirements-open-mocap-cpu.txt for CPU video capture') from e
    source=cv2.VideoCapture(str(path))
    if not source.isOpened():raise RuntimeError('Cannot open video: '+str(path))
    fps=float(source.get(cv2.CAP_PROP_FPS))
    if not math.isfinite(fps) or fps<=0 or fps>240:raise ValueError('Video FPS is invalid')
    tracker=PoseTrackingCPU()
    frames=[];missing=0
    try:
        for _ in range(max_frames):
            ok,frame=source.read()
            if not ok:break
            points=tracker.detect_pose(frame)
            if points is None:missing+=1
            frames.append(points)
    finally:source.release()
    if len(frames)<2 or all(p is None for p in frames):raise ValueError('Video has fewer than two frames or no detected body poses')
    return fps,frames,missing


def interpolate_missing(frames):
    # Preserve timeline. Long dropout holds pose; do not invent character moves.
    first=next(i for i,f in enumerate(frames) if f is not None)
    for i in range(first):frames[i]=frames[first][:]
    known=first
    for i in range(first+1,len(frames)):
        if frames[i] is None:continue
        if i-known>1:
            before=frames[known];after=frames[i]
            for mid in range(known+1,i):
                t=(mid-known)/(i-known)
                frames[mid]=[a+(b-a)*t for a,b in zip(before,after)]
        known=i
    for i in range(known+1,len(frames)):frames[i]=frames[known][:]
    return frames


def main(argv=None):
    p=argparse.ArgumentParser(description='Extract real Open Mocap 40-point pose tracking on CPU')
    p.add_argument('--video',type=Path,required=True)
    p.add_argument('--side-video',type=Path)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--max-frames',type=int,default=1800)
    p.add_argument('--overwrite',action='store_true')
    a=p.parse_args(argv)
    if not a.video.is_file():p.error('Input video not found')
    if a.side_video and not a.side_video.is_file():p.error('Side video not found')
    if not 2<=a.max_frames<=2400:p.error('Use 2..2400 video frames')
    out=a.output.expanduser().resolve()
    if out.suffix.lower()!='.json':p.error('Output must be .json')
    if out.exists() and not a.overwrite:p.error('Output already exists')
    fps,front,missing=capture(a.video,a.max_frames)
    if a.side_video:
        fps2,side,other_missing=capture(a.side_video,a.max_frames)
        # An unsynchronized camera can corrupt the pose, so refuse an unverified pair.
        if abs(fps-fps2)>1e-3 or len(front)!=len(side):
            raise RuntimeError('Side video FPS/frame count mismatch. Use synchronized cameras, or only front view.')
        side=interpolate_missing(side)
        for frame,second in zip(front,side):
            if frame is not None:
                # Original Open Mocap side-view depth substitution (f[2] = -side x).
                for j in range(40):frame[3*j+2] = -second[3*j]
        missing+=other_missing
    front=interpolate_missing(front)
    payload={
        'format':'monster-open-mocap-cpu-v1', 'fps':fps,
        'points':40,'count':len(front),'landmarks':front,
        'missing_detections':missing,
        'coordinates':'OpenMocap xyz normalized, front; optional side depth',
        'provenance':'Larenju-Rai/open-mocap-blender MIT 1ec7457dad228661cbd8a1d98163e8288d3f7db5'
    }
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(payload,separators=(',',':')),encoding='utf8')
    print('Open Mocap CPU:',len(front),'frames;',missing,'missing detections; FPS',fps)

if __name__=='__main__':main()
