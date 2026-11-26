#!/usr/bin/env python3
"""Strict SAM 2 identity masks -> MMPose human reference -> original 2D/2.5D full-cel renderer.

All earlier Krita, OpenToonz, Pixelorama, DeepLabCut and GIF/ZIP validators remain
in the pipeline; MMPose keypoints never replace character pose artwork.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
import sys
import zipfile
from krita_bridge import compile_scene as compile_krita, create_handoff as krita_handoff
from opentoonz_bridge import compile_scene
from opentoonz_preflight import validate_scene
from mmpose_bridge import infer_video, read_guide, gait_metrics, MotionError
from mmpose_sam2_bridge import infer_masked_video, verify_masked_guide
from pixelorama_handoff import compile_and_handoff
from deeplabcut_bridge import (AnimalMotionError, read_guide as read_animal_guide,
    compile_csv_or_h5, analyze_video, gait_metrics as animal_metrics, read_table)
from sam2_bridge import compile_scene as compile_sam2, preflight as sam2_preflight, _id as sam2_actor_id

QUADRUPEDS={'cat','dog','animal'}


def resolve(root, raw):
    if not isinstance(raw,str) or not raw or Path(raw).is_absolute():
        raise ValueError('Reference path must be scene-relative: '+repr(raw))
    p=(root/raw).resolve()
    if p!=root and root not in p.parents:raise ValueError('Reference escapes scene root')
    if not p.is_file():raise ValueError('Missing reference: '+str(p))
    return p


def video_resolution(video):
    try:
        import cv2
    except ImportError as exc:
        raise MotionError('OpenCV required to verify SAM 2/MMPose reference video dimensions') from exc
    cap=cv2.VideoCapture(str(video))
    try:
        if not cap.isOpened():raise MotionError('MMPose/SAM 2 video cannot be read')
        w,h=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    finally:cap.release()
    if w<16 or h<16:raise MotionError('Invalid original video resolution')
    return (w,h)


def prepare_references(scene_path,out,preflight=False,device=None,sam2_masks=None):
    """No inferred human poses without a real video and, when provided, real SAM 2 identity masks."""
    root=scene_path.parent.resolve(); cfg=json.loads(scene_path.read_text('utf8'))
    originals=[];metrics={};dlc_metrics={}
    for actor in cfg.get('actors',[]):
        loc=actor.get('locomotion')
        if not loc:continue
        aid,mode=str(actor['id']),loc.get('mode')
        guide,video=loc.get('mmpose_guide'),loc.get('mmpose_video')
        animal_guide=loc.get('deeplabcut_guide')
        animal_table=loc.get('deeplabcut_predictions')
        animal_video=loc.get('deeplabcut_video')
        if sum(bool(x) for x in (guide,video))>1:
            raise MotionError(aid+': choose MMPose guide OR video')
        if sum(bool(x) for x in (animal_guide,animal_table,animal_video))>1:
            raise AnimalMotionError(aid+': choose one DeepLabCut source only')
        if (guide or video) and (animal_guide or animal_table or animal_video):
            raise ValueError(aid+': never blend human MMPose with animal DeepLabCut')
        # Only pair same original video; never match mask frames from unrelated footage.
        tracked=actor.get('sam2_video_prompt') if (guide or video) else None
        shared_video=None;mask_dir=None
        if tracked:
            if actor.get('role')!='human':
                raise MotionError(aid+': SAM 2 + MMPose COCO17 identity matching is human-only')
            shared_video=resolve(root,tracked.get('video'))
            if video and resolve(root,video)!=shared_video:
                raise MotionError(aid+': MMPose and SAM 2 must reference the exact same video')
            if sam2_masks is not None:
                mask_dir=(Path(sam2_masks)/sam2_actor_id(aid)).resolve()
        if guide or video:
            if actor.get('role')!='human':
                raise MotionError(aid+': COCO17 MMPose does not certify animals')
            if guide:
                path=resolve(root,guide);data=read_guide(path);originals.append(path)
                if shared_video:
                    if data.get('source_video')!=shared_video.name:
                        raise MotionError(aid+': stored MMPose guide belongs to a different SAM 2 video')
                    if preflight:
                        metrics[aid]={'inference':'verified guide; SAM 2 identity masks required at render'}
                    else:
                        verified=verify_masked_guide(data,mask_dir,video_resolution(shared_video),shared_video)
                        metrics[aid]={**gait_metrics(data,mode),**verified}
            else:
                path=resolve(root,video)
                if preflight:
                    metrics[aid]={'inference':'requires installed MMPose human model',
                                  'sam2_identity_required':bool(shared_video)}
                    originals.append(path)
                else:
                    target=out/'mmpose_references'/(sam2_actor_id(aid)+'.json')
                    if shared_video:
                        if mask_dir is None or not mask_dir.is_dir():
                            raise MotionError(aid+': real SAM 2 identity mask sequence was not generated')
                        generated=infer_masked_video(path,target,mask_dir,device=device)
                    else:
                        generated=infer_video(path,target,device=device)
                    data=read_guide(generated)
                    originals.extend([path,target])
            if not preflight and aid not in metrics:
                metrics[aid]=gait_metrics(data,mode)
        if not (animal_guide or animal_table or animal_video):continue
        if actor.get('role') not in QUADRUPEDS:
            raise AnimalMotionError(aid+': quadruped reference only for cat/dog/animal')
        if mode not in ('walk','run','stairs_up','stairs_down'):
            raise AnimalMotionError(aid+': DLC reference only for locomotion actions')
        if animal_guide:
            path=resolve(root,animal_guide)
            data=read_animal_guide(path)
            originals.append(path)
        else:
            bodymap=loc.get('deeplabcut_bodypart_map')
            if not isinstance(bodymap,dict) or not bodymap:
                raise AnimalMotionError(aid+': explicit DLC bodypart_map required')
            fps=loc.get('deeplabcut_fps')
            if fps is None:raise AnimalMotionError(aid+': require real video/source FPS, not guessed FPS')
            confidence=loc.get('deeplabcut_confidence',.6)
            individual=loc.get('deeplabcut_individual')
            scorer=loc.get('deeplabcut_scorer')
            target=out/'deeplabcut_references'/(aid+'.json')
            if animal_table:
                source=resolve(root,animal_table)
                if preflight:read_table(source)
                else:
                    target=compile_csv_or_h5(source,target,bodymap,individual,scorer,confidence,fps)
                    data=read_animal_guide(target)
                originals.append(source)
            else:
                source=resolve(root,animal_video)
                config=resolve(root,loc.get('deeplabcut_config'))
                originals.extend([source,config])
                if preflight:
                    dlc_metrics[aid]={'inference':'requires installed DeepLabCut and trained matching animal model'}
                    continue
                target=analyze_video(config,source,target,bodymap,individual,fps,confidence,scorer)
                data=read_animal_guide(target)
            if not preflight:originals.append(target)
        if animal_guide or not preflight:
            dlc_metrics[aid]=animal_metrics(data,mode)
    return originals,metrics,dlc_metrics


def main():
    p=argparse.ArgumentParser()
    p.add_argument('source',type=Path)
    p.add_argument('--scene',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--seconds',type=int,default=48)
    p.add_argument('--fps',type=int,default=24)
    p.add_argument('--max-width',type=int,default=720)
    p.add_argument('--pixelorama',default=None)
    p.add_argument('--opentoonz',default=None)
    p.add_argument('--mmpose-device',default=None)
    p.add_argument('--preflight-only',action='store_true')
    args=p.parse_args()
    if not args.source.is_file():p.error('Original illustration missing')
    if args.fps<24:p.error('24fps minimum')
    if not 40<=args.seconds<=60 and not args.preflight_only:p.error('40-60s scene loop required')
    scene=args.scene.resolve();out=args.out.resolve()
    if args.preflight_only:
        summary_sam=sam2_preflight(scene,args.source.resolve())
        cfg=json.loads(scene.read_text('utf8'))
        if summary_sam['image_actors']:
            summary={'sam2_pending_masks':summary_sam['image_actors'],'actors':len(cfg.get('actors',[]))}
        else:
            krita_compiled,_=compile_krita(scene,out,args.fps)
            summary=validate_scene(krita_compiled)
        prepare_references(scene,out,True,args.mmpose_device)
        print(json.dumps({'preflight':'model required','sam2':summary_sam,'summary':summary},ensure_ascii=False))
        return
    out.mkdir(parents=True,exist_ok=True)
    # Run official SAM 2 first: only its real mask outputs may disambiguate
    # MMPose among multiple riders/soldiers in each reference video frame.
    segmented,samfiles,sammeta=compile_sam2(scene,args.source.resolve(),out)
    refs,mmetrics,ametrics=prepare_references(scene,out,False,args.mmpose_device,
                                                 out/'sam2_generated/video_masks')
    krita_compiled,krita_originals=compile_krita(segmented,out,args.fps)
    validate_scene(krita_compiled)
    open_compiled,open_originals=compile_scene(krita_compiled,out,args.opentoonz)
    compiled,interchange,interchange_meta=compile_and_handoff(open_compiled,out,args.pixelorama)
    krita_files,krita_meta=krita_handoff(compiled,out)
    originals=list(krita_originals)+list(open_originals)+list(samfiles)
    interchange=list(interchange)+list(krita_files)
    cmd=[sys.executable,str(Path(__file__).resolve().parent/'pose_sequence_delivery.py'),
         str(args.source.resolve()),'--scene',str(compiled),'--out',str(out),
         '--seconds',str(args.seconds),'--fps',str(args.fps),'--max-width',str(args.max_width)]
    proc=subprocess.run(cmd,check=False)
    if proc.returncode:raise SystemExit(proc.returncode)
    zip_path,gif_path=out/'living_scene_assets.zip',out/'living_scene.gif'
    if not zip_path.is_file() or not gif_path.is_file():
        raise RuntimeError('Renderer did not output both GIF and ZIP')
    root=scene.parent
    with zipfile.ZipFile(zip_path,'a',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        existing=set(z.namelist())
        for path in sorted(set(originals+refs)):
            if path.is_relative_to(root):rel=path.relative_to(root).as_posix()
            elif path.is_relative_to(out):rel='inferred/'+path.relative_to(out).as_posix()
            else:raise RuntimeError('Untrusted source package path')
            member='project/animation_sources/'+rel
            if member in existing:raise RuntimeError('Duplicate source ZIP member')
            z.write(path,member);existing.add(member)
        for path in sorted(set(interchange)):
            member='interchange_2d/'+path.relative_to(out/'interchange_2d').as_posix()
            if member in existing:raise RuntimeError('Duplicate interchange ZIP member')
            z.write(path,member);existing.add(member)
        z.writestr('mmpose_reference_metrics.json',json.dumps(mmetrics,ensure_ascii=False,indent=2))
        z.writestr('deeplabcut_reference_metrics.json',json.dumps(ametrics,ensure_ascii=False,indent=2))
        z.writestr('sam2_reference_metrics.json',json.dumps(sammeta,ensure_ascii=False,indent=2))
    with zipfile.ZipFile(zip_path) as z:
        if z.testzip() is not None:raise RuntimeError('Corrupt ZIP output')
    print(json.dumps({'gif':str(gif_path),'zip':str(zip_path),
                     'human_references':len(mmetrics),'animal_references':len(ametrics),
                     **sammeta,**interchange_meta,**krita_meta},ensure_ascii=False))

if __name__=='__main__':main()
