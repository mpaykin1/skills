#!/usr/bin/env python3
"""MMPose v1 adapter for real 2D human gait reference videos.

Produces actual inferred joint tracks, never character artwork. Fail closed if
missing model/runtime or ambiguous multi-person tracking. Model weights are
external and licensed separately. The bridge can validate stored reference
tracks without importing torch/mmpose, so the animator works offline.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
from statistics import median

COCO_17 = ('nose','left_eye','right_eye','left_ear','right_ear',
           'left_shoulder','right_shoulder','left_elbow','right_elbow',
           'left_wrist','right_wrist','left_hip','right_hip',
           'left_knee','right_knee','left_ankle','right_ankle')
NECESSARY = ('left_shoulder','right_shoulder','left_hip','right_hip',
             'left_knee','right_knee','left_ankle','right_ankle')

class MotionError(ValueError):
    pass

def point(a):
    return isinstance(a,(list,tuple)) and len(a)==2 and all(
        isinstance(n,(int,float)) and not isinstance(n,bool) and math.isfinite(n) for n in a)

def read_guide(path):
    p=Path(path)
    if not p.is_file(): raise MotionError('Missing MMPose track '+str(p))
    payload=json.loads(p.read_text(encoding='utf8'))
    if payload.get('engine')!='mmpose' or payload.get('keypoint_schema')!='coco17':
        raise MotionError('Only real mmpose COCO17 v1 motion tracks supported')
    frames=payload.get('frames')
    if not isinstance(frames,list) or len(frames)<12:
        raise MotionError('Reference requires >=12 genuinely inferred video frames')
    expected=None;coords=[]
    for index,rec in enumerate(frames):
        if rec.get('frame')!=index:raise MotionError('Frame numbers must be consecutive, starting at zero')
        joints=rec.get('joints',{});scores=rec.get('scores',{})
        if not all(point(joints.get(k)) and isinstance(scores.get(k), (int,float)) and scores[k]>=.30 for k in NECESSARY):
            raise MotionError(f'Missing/low-confidence body landmarks at reference frame {index}')
        for xy in joints.values():
            if not point(xy):raise MotionError('Nonfinite reference keypoint')
        coords.append(joints)
    fps=float(payload.get('fps',0))
    if not 5<=fps<=240:raise MotionError('Reference FPS outside 5..240')
    return payload

def gait_metrics(guide,mode):
    """Measure actual alternating left/right leg motion, not a static pose."""
    if mode not in ('walk','run','stairs_up','stairs_down'):
        raise MotionError('MMPose gait mode must be walk/run/stairs_up/stairs_down')
    frames=guide['frames']
    def joint(f,n):return f['joints'][n]
    h=[];diff=[];left=[];right=[]
    for f in frames:
        lh,rh=joint(f,'left_hip'),joint(f,'right_hip')
        ls,rs=joint(f,'left_shoulder'),joint(f,'right_shoulder')
        hip_y=(lh[1]+rh[1])/2.;shoulder_y=(ls[1]+rs[1])/2.
        scale=max(1.,abs(hip_y-shoulder_y)*2.3)
        h.append(scale)
        left.append((joint(f,'left_ankle')[0] - lh[0])/scale)
        right.append((joint(f,'right_ankle')[0] - rh[0])/scale)
        diff.append(left[-1]-right[-1])
    excursion=max(diff)-min(diff)
    movement_l=max(left)-min(left);movement_r=max(right)-min(right)
    transitions=sum((diff[i-1]<0<=diff[i]) or (diff[i-1]>0>=diff[i]) for i in range(1,len(diff)))
    # Walking in profile may never flip foot-order on low-resolution video,
    # so require independent limb motion and at least one stance alternation,
    # but do not pretend it confirms foot/ground contact.
    valid=(excursion>=.17 and movement_l>=.12 and movement_r>=.12 and transitions>=1)
    if not valid:
        raise MotionError('MMPose clip does not show verifiable alternating two-leg movement')
    return {'reference_frames':len(frames),'leg_separation_sweep':round(excursion,3),
            'left_ankle_sweep':round(movement_l,3),'right_ankle_sweep':round(movement_r,3),
            'alternations':transitions,'mode':mode}

def _extract_prediction_frame(result):
    predictions=result.get('predictions',[])
    if isinstance(predictions,dict):predictions=[predictions]
    if len(predictions)==1 and isinstance(predictions[0],list):predictions=predictions[0]
    if len(predictions)!=1:
        raise MotionError(f'Reference must contain exactly one visible human per frame; detected {len(predictions)}')
    raw=predictions[0]
    keypoints=raw.get('keypoints',[]);scores=raw.get('keypoint_scores')
    if scores is None or len(keypoints)<17 or len(scores)<17:
        raise MotionError('MMPose Inferencer returned no COCO17 scores/keypoints')
    # Inferencer API returns coordinates in the original video frame.
    joints={name:[round(float(keypoints[i][0]),4),round(float(keypoints[i][1]),4)] for i,name in enumerate(COCO_17)}
    conf={name:round(float(scores[i]),5) for i,name in enumerate(COCO_17)}
    return {'joints':joints,'scores':conf}

def infer_video(video,out,model='human',device=None,max_frames=1500):
    path=Path(video).resolve()
    if not path.is_file():raise MotionError('MMPose video missing')
    if model!='human':raise MotionError('This bridge supports COCO17 human reference only; do not apply human joints to animals')
    try:
        import cv2
        from mmpose.apis import MMPoseInferencer
    except ImportError as exc:
        raise MotionError('MMPose v1 and OpenCV are external optional dependencies; install them separately') from exc
    cap=cv2.VideoCapture(str(path))
    fps=float(cap.get(cv2.CAP_PROP_FPS));count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    if not 5<=fps<=240:raise MotionError('Unusable reference video FPS')
    if count>max_frames:raise MotionError('Reference too long; crop to a <=1500-frame single-human gait')
    inferencer=MMPoseInferencer(pose2d='human',device=device) if device else MMPoseInferencer(pose2d='human')
    frames=[]
    try:
        generator=inferencer(str(path),return_vis=False,show=False)
        for i,result in enumerate(generator):
            if i>=max_frames:raise MotionError('Video exceeds max_frames')
            frame=_extract_prediction_frame(result);frame['frame']=i;frames.append(frame)
    except MotionError:
        raise
    except Exception as exc:
        raise MotionError('MMPose inference failed; no fake reference exported: '+str(exc)) from exc
    if len(frames)<12:raise MotionError('Too few inferred frames')
    result={'engine':'mmpose','format':1,'model':model,'keypoint_schema':'coco17',
            'source_video':path.name,'fps':round(fps,5),'frames':frames,
            'note':'Motion-guide extraction only; does not create artwork or track identity across multiple people'}
    dst=Path(out).resolve();dst.parent.mkdir(parents=True,exist_ok=True)
    dst.write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8')
    read_guide(dst)
    return dst

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--video',type=Path)
    p.add_argument('--guide',type=Path)
    p.add_argument('--out',type=Path)
    p.add_argument('--mode',choices=('walk','run','stairs_up','stairs_down'),default='walk')
    p.add_argument('--device',default=None)
    a=p.parse_args()
    if a.video:
        if not a.out:p.error('--out required with --video')
        guide=read_guide(infer_video(a.video,a.out,device=a.device))
    elif a.guide:guide=read_guide(a.guide)
    else:p.error('Provide --video to infer or --guide to validate')
    print(json.dumps(gait_metrics(guide,a.mode),ensure_ascii=False))

if __name__=='__main__':main()
