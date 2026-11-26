#!/usr/bin/env python3
"""Authentic SAM 2 prompted image/video masks -> source-registered 2D layer inputs.

Only mask extraction and reference segmentation. Character actions still need
separately painted complete pose frames in Krita/OpenToonz/Pixelorama. No proxy
rigging, invented body poses, inpainting or video frame morphing.

SAM 2 itself and its checkpoint must be installed separately. Error if absent.
"""
from __future__ import annotations
import copy
import hashlib
import json
import math
import os
import re
import shutil
import tempfile
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

class SAM2BridgeError(ValueError):
    pass


def _relative(root: Path, raw: str, *, directory=False) -> Path:
    if not isinstance(raw, str) or not raw or Path(raw).is_absolute() or '..' in Path(raw).parts:
        raise SAM2BridgeError('Source must be scene-relative, no traversal: '+repr(raw))
    base=root.resolve(); p=(base/raw).resolve()
    if base not in p.parents or p==base:
        raise SAM2BridgeError('Source escapes scene root: '+raw)
    if directory and not p.is_dir() or not directory and not p.is_file():
        raise SAM2BridgeError('Missing input: '+str(p))
    return p


def _id(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',value):
        raise SAM2BridgeError('SAM 2 actor ID must contain ASCII letters, digits, _ or -')
    return value


def _pts(prompt, size):
    """Validate user-given point/box prompts; never infer imaginary targets."""
    W,H=size
    b=prompt.get('box')
    if b is None:
        box=None
    else:
        if not isinstance(b,list) or len(b)!=4 or not all(type(n) in (int,float) and math.isfinite(n) for n in b):
            raise SAM2BridgeError('SAM2 box must be [x0,y0,x1,y1] in source pixels')
        x0,y0,x1,y1=b
        if not (0<=x0<x1<=W and 0<=y0<y1<=H):
            raise SAM2BridgeError('SAM2 prompt box outside source image')
        box=np.array(b,dtype=np.float32)
    coords=[];labels=[]
    for p in prompt.get('points',[]):
        if not isinstance(p,dict) or 'xy' not in p or 'label' not in p:
            raise SAM2BridgeError('Point requires {xy:[x,y],label:0|1}')
        xy=p['xy'];label=p['label']
        if not isinstance(xy,list) or len(xy)!=2 or not all(type(v) in (int,float) and math.isfinite(v) for v in xy):
            raise SAM2BridgeError('Invalid SAM2 point')
        if label not in (0,1) or type(label) is not int or not (0<=xy[0]<W and 0<=xy[1]<H):
            raise SAM2BridgeError('SAM2 point/label outside source')
        coords.append(xy);labels.append(label)
    if box is None and not any(labels):
        raise SAM2BridgeError('SAM2 actor needs a prompt box or foreground point')
    return box, np.array(coords,dtype=np.float32) if coords else None, np.array(labels,dtype=np.int32) if coords else None


def _model(config):
    if not isinstance(config,dict): raise SAM2BridgeError('sam2 must be object with model_cfg, checkpoint')
    model_cfg=config.get('model_cfg','configs/sam2.1/sam2.1_hiera_s.yaml')
    checkpoint=config.get('checkpoint') or os.environ.get('SAM2_CHECKPOINT')
    if not isinstance(model_cfg,str) or not model_cfg:
        raise SAM2BridgeError('SAM2 model_cfg required')
    if not checkpoint or not Path(checkpoint).expanduser().is_file():
        raise SAM2BridgeError('Real SAM 2 checkpoint missing. Provide sam2.checkpoint or SAM2_CHECKPOINT; never use dummy masks')
    device=config.get('device','cuda')
    if device not in ('cpu','cuda','mps'):raise SAM2BridgeError('SAM2 device must be cpu/cuda/mps')
    try:
        import torch
        from sam2.build_sam import build_sam2, build_sam2_video_predictor
        from sam2.sam2_image_predictor import SAM2ImagePredictor
    except (ImportError, OSError) as e:
        raise SAM2BridgeError('Install official facebookresearch/sam2 and torch in Python environment first') from e
    if device=='cuda' and not torch.cuda.is_available():
        raise SAM2BridgeError('SAM2 requested CUDA but no CUDA device available')
    return model_cfg,str(Path(checkpoint).expanduser().resolve()),device,build_sam2,build_sam2_video_predictor,SAM2ImagePredictor,torch


def _coverage(mask, W,H, actor, min_px=20):
    if mask.shape != (H,W):raise SAM2BridgeError(actor+': SAM 2 mask has mismatched dimensions')
    area=int(np.count_nonzero(mask))
    if area < min_px or area>=W*H*.85:
        raise SAM2BridgeError(actor+': empty, tiny or implausibly dominant SAM 2 mask; refine positive/negative prompts')
    return area


def _safe_copy(scene, origin, work):
    """Mirror only referenced scene assets; do not copy unrelated/private files."""
    def copy_file(rel):
        src=_relative(origin,rel)
        dst=(work/rel).resolve();dst.parent.mkdir(parents=True,exist_ok=True)
        if work not in dst.parents:raise SAM2BridgeError('Unsafe target path')
        if dst!=src:shutil.copy2(src,dst)
    def copy_dir(rel):
        folder=_relative(origin,rel,directory=True)
        dest=(work/rel).resolve()
        if work not in dest.parents:raise SAM2BridgeError('Unsafe directory path')
        if any(p.is_symlink() for p in folder.rglob('*')):
            raise SAM2BridgeError('Symlinks in Krita source folder are unsupported')
        shutil.copytree(folder,dest,dirs_exist_ok=True)
    for actor in scene.get('actors',[]):
        mask=actor.get('source_mask')
        if mask and 'sam2_prompt' not in actor: copy_file(mask)
        for clip in actor.get('clips',[]):
            if 'krita_sequence' in clip:
                seq=clip['krita_sequence'];copy_dir(seq['directory'])
                copy_file(seq['source_kra']);copy_file(seq['joints_json'])
            elif 'opentoonz_scene' in clip:
                copy_file(clip['opentoonz_scene']);copy_file(clip['joints_json'])
                for path in clip.get('dependencies',[]):copy_file(path)
            elif 'pixelorama_project' in clip:
                copy_file(clip['pixelorama_project']);copy_file(clip['joints_json'])
            else:
                for frame in clip.get('frames',[]): copy_file(frame['png'])
        loc=actor.get('locomotion') or {}
        for field in ('mmpose_guide','mmpose_video','deeplabcut_guide','deeplabcut_predictions','deeplabcut_video','deeplabcut_config'):
            if loc.get(field):copy_file(loc[field])
        ref=actor.get('sam2_video_prompt')
        if ref and ref.get('video'):copy_file(ref['video'])
    for name in ('day_background','sky_mask'):
        rel=scene.get('day_night',{}).get(name)
        if rel:copy_file(rel)


def _image_segmentation(scene, source, work, cfg, model):
    model_cfg, ckpt, device, build_image, _, ImagePredictor, torch=model
    image=np.asarray(Image.open(source).convert('RGB'))
    H,W=image.shape[:2]
    predictor=ImagePredictor(build_image(model_cfg,ckpt,device=device))
    outputs=[]; masks=[]
    with torch.inference_mode():
        predictor.set_image(image)
        for actor in scene.get('actors',[]):
            prompt=actor.get('sam2_prompt')
            if prompt is None:continue
            aid=_id(actor['id']); b,pts,labels=_pts(prompt,(W,H))
            candidate,scores,_=predictor.predict(point_coords=pts,point_labels=labels,box=b,multimask_output=True)
            scoreidx=int(np.argmax(scores))
            score=float(scores[scoreidx])
            min_score=float(prompt.get('min_score',0.0))
            if not math.isfinite(score) or score<min_score:
                raise SAM2BridgeError(aid+': low model prediction confidence; refine prompts manually')
            mask=np.asarray(candidate[scoreidx],dtype=bool)
            area=_coverage(mask,W,H,aid)
            x,y,w,h=actor['box']
            if x<0 or y<0 or w<=0 or h<=0 or x+w>W or y+h>H:
                raise SAM2BridgeError(aid+': actor.box must fit source image')
            if np.count_nonzero(mask[y:y+h,x:x+w]) < .95*area:
                raise SAM2BridgeError(aid+': actor.box crops detected silhouette; enlarge actor bounds or refine prompt')
            for prev,oldid in masks:
                inter=int(np.count_nonzero(prev&mask))
                if inter>max(15,min(np.count_nonzero(prev),area)*.12):
                    raise SAM2BridgeError(f'SAM2 masks overlap strongly for {oldid} and {aid}; refine disambiguating prompts')
            masks.append((mask,aid))
            rel=f'sam2_generated/masks/{aid}.png'
            dst=work/rel;dst.parent.mkdir(parents=True,exist_ok=True)
            Image.fromarray(mask.astype('uint8')*255,'L').save(dst)
            rgbcrop=image[y:y+h,x:x+w]
            layer=np.concatenate([rgbcrop, (mask[y:y+h,x:x+w].astype('uint8')*255)[...,None]],axis=2)
            layerpath=work/f'sam2_generated/reference_layers/{aid}.png';layerpath.parent.mkdir(parents=True,exist_ok=True)
            Image.fromarray(layer,'RGBA').save(layerpath)
            actor['source_mask']=rel
            actor.pop('sam2_prompt')
            outputs.extend([dst,layerpath])
    return outputs,[{'actor_id':k,'mask_pixels':int(m.sum()),'image_pixels':[W,H]} for m,k in masks]


def _video_segmentation(scene, root, out, cfg, model):
    """Optional tracked original-video masks; not full-pose or action sprites."""
    refs=[a for a in scene.get('actors',[]) if a.get('sam2_video_prompt')]
    if not refs:return [],[]
    model_cfg,ckpt,device,_,build_video,_,torch=model
    videos={a['sam2_video_prompt'].get('video') for a in refs}
    if len(videos)!=1:raise SAM2BridgeError('One synchronized SAM2 reference video per scene; split unrelated footage')
    video=_relative(root,next(iter(videos)))
    frame_limit=cfg.get('max_video_frames',120)
    if type(frame_limit) is not int or not 1<=frame_limit<=240:
        raise SAM2BridgeError('max_video_frames must be 1..240')
    files=[];meta=[]
    with tempfile.TemporaryDirectory(prefix='sam2_reference_') as folder:
        jpg=Path(folder);cap=cv2.VideoCapture(str(video))
        if not cap.isOpened():raise SAM2BridgeError('Reference video cannot be decoded: '+str(video))
        count=0; first_size=None
        try:
            while count<frame_limit:
                ok,raw=cap.read()
                if not ok:break
                H,W=raw.shape[:2]
                if first_size is None:first_size=(W,H)
                elif (W,H)!=first_size:raise SAM2BridgeError('Video resolution changes between frames')
                if not cv2.imwrite(str(jpg/f'{count:05d}.jpg'),raw,[int(cv2.IMWRITE_JPEG_QUALITY),96]):
                    raise SAM2BridgeError('Could not extract reference video frame')
                count+=1
        finally:cap.release()
        if count<2:raise SAM2BridgeError('Need >=2 actual reference frames for video tracking')
        W,H=first_size
        pred=build_video(model_cfg,ckpt,device=device)
        with torch.inference_mode():
            state=pred.init_state(video_path=str(jpg))
            idmap={}
            for obj_id,actor in enumerate(refs,start=1):
                aid=_id(actor['id']); b,points,labels=_pts(actor['sam2_video_prompt'],first_size)
                idmap[obj_id]=aid
                pred.add_new_points_or_box(inference_state=state,frame_idx=0,obj_id=obj_id,
                                           points=points,labels=labels,box=b)
            counts={aid:0 for aid in idmap.values()}
            for fidx,obj_ids,logits in pred.propagate_in_video(state):
                if fidx>=count:continue
                for idx,obj in enumerate(obj_ids):
                    aid=idmap.get(int(obj))
                    if aid is None:raise SAM2BridgeError('SAM2 yielded untracked object ID')
                    mask=(logits[idx]>0).detach().cpu().numpy().squeeze().astype(bool)
                    _coverage(mask,W,H,aid)
                    target=out/'sam2_generated/video_masks'/aid/f'{fidx:05d}.png'
                    target.parent.mkdir(parents=True,exist_ok=True)
                    Image.fromarray(mask.astype('uint8')*255,'L').save(target)
                    counts[aid]+=1;files.append(target)
            for aid,n in counts.items():
                if n!=count:raise SAM2BridgeError(f'{aid}: only {n}/{count} video frames segmented; refuse partial reference')
            if hasattr(pred,'reset_state'):pred.reset_state(state)
        meta=[{'actor_id':aid,'tracked_frames':n,'source_video':str(video.name),'source_dimensions':[W,H]}
              for aid,n in counts.items()]
    return files,meta


def compile_scene(scene_file:Path, source_image:Path, out_dir:Path):
    """Returns (compiled scene, provenance files, metadata). Does not fake motion."""
    scene_file=Path(scene_file).resolve(); source_image=Path(source_image).resolve();root=scene_file.parent
    scene=json.loads(scene_file.read_text('utf8'))
    image_targets=[a for a in scene.get('actors',[]) if 'sam2_prompt' in a]
    video_targets=[a for a in scene.get('actors',[]) if 'sam2_video_prompt' in a]
    if not image_targets and not video_targets:return scene_file, [], {'sam2_image_actors':0,'sam2_video_actors':0}
    cfg=scene.get('sam2')
    if not isinstance(cfg,dict):raise SAM2BridgeError('scene.sam2 configuration required when sam2_prompt exists')
    if not source_image.is_file():raise SAM2BridgeError('Original scene image missing')
    model=_model(cfg)
    out_dir=Path(out_dir).resolve();work=out_dir/'compiled_sam2_scene';work.mkdir(parents=True,exist_ok=True)
    prepared=copy.deepcopy(scene)
    _safe_copy(prepared,root,work)
    images, image_meta=_image_segmentation(prepared,source_image,work,cfg,model) if image_targets else ([],[])
    videos,video_meta=_video_segmentation(scene,root,out_dir,cfg,model) if video_targets else ([],[])
    for actor in prepared.get('actors',[]):actor.pop('sam2_video_prompt',None)
    # Final scene passes unaltered to Krita/OpenToonz/Pixelorama pose compiler.
    prepared.pop('sam2',None)
    prepared['sam2_segmentation']={'engine':'real SAM 2 predictor','checkpoint_sha256':hashlib.sha256(Path(model[1]).read_bytes()).hexdigest(),
         'image':image_meta,'video':video_meta,'note':'Masks only, not painted animations; source pixels untouched'}
    compiled=work/'scene.json';compiled.write_text(json.dumps(prepared,ensure_ascii=False,indent=2),'utf8')
    provenance=work/'sam2_generated'/'segmentation.json';provenance.parent.mkdir(parents=True,exist_ok=True)
    provenance.write_text(json.dumps(prepared['sam2_segmentation'],ensure_ascii=False,indent=2),'utf8')
    return compiled,[provenance,*images,*videos],{'sam2_image_actors':len(image_targets),'sam2_video_actors':len(video_targets)}


def preflight(scene_file:Path,source_image:Path):
    scene=json.loads(Path(scene_file).read_text('utf8'))
    with Image.open(source_image) as image:size=image.size
    image_targets=[];video_targets=[]
    for actor in scene.get('actors',[]):
        if 'sam2_prompt' in actor:
            _id(actor['id']);_pts(actor['sam2_prompt'],size);image_targets.append(actor['id'])
        if 'sam2_video_prompt' in actor:
            _id(actor['id']);video_targets.append(actor['id'])
    if image_targets or video_targets:
        cfg=scene.get('sam2')
        if not isinstance(cfg,dict):raise SAM2BridgeError('SAM2 model config missing')
    return {'image_actors':image_targets,'video_actors':video_targets,'model_execution':'required for final render'}
