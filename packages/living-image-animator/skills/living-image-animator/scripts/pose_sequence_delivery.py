#!/usr/bin/env python3
"""Living Image Animator v0.9: full-frame cels with true 2D/2.5D world locomotion.

Release gate and composer for independent, pre-drawn RGBA character frames.
Accepts only explicitly authored continuous full-character pose sequences. No
rig rotations, skeletal warps, pixel interpolation, screen-bob or optical flow
on characters. Unsupported character animation FAILS CLOSED.

Scene schema: references/full-frame-poses.md
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import shutil
import subprocess
import tempfile
import zipfile
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageChops, ImageStat
from locomotion import verify as verify_locomotion, sample as locomotion_sample, validate_pose_steps, LocomotionError, LOCO_ACTIONS


def stop(msg):
    raise ValueError('CHARACTER MOTION BLOCKED: '+str(msg))


def read_image(path, mode='RGBA'):
    if not path.is_file(): stop('missing image '+str(path))
    with Image.open(path) as im:
        return im.convert(mode)


def path_in(root, rel):
    if not isinstance(rel,str) or not rel or Path(rel).is_absolute():
        stop('asset path must be relative: '+repr(rel))
    p=(root/rel).resolve()
    if p!=root and root not in p.parents: stop('unsafe asset path '+rel)
    return p


def pixel_diff(a,b):
    """Alpha+ink change percentage; not background/lighting movement."""
    aa=np.asarray(a,np.uint8);bb=np.asarray(b,np.uint8)
    mask=(aa[:,:,3]>70)|(bb[:,:,3]>70)
    denom=max(1,int(mask.sum()))
    changed=((np.abs(aa[:,:,3].astype('i2')-bb[:,:,3].astype('i2'))>65)|
             ((np.max(np.abs(aa[:,:,:3].astype('i2')-bb[:,:,:3].astype('i2')),axis=2)>46)&mask))
    return float(np.count_nonzero(changed & mask)/denom)


def unshifted_shape_difference(a,b):
    """Residual shape difference after aligning alpha centroids.

    Rigid translation alone must never count as a new action pose.
    Shift is used ONLY for the validator, never to render a single frame.
    """
    aa=(np.asarray(a.getchannel('A'))>80).astype('uint8')
    bb=(np.asarray(b.getchannel('A'))>80).astype('uint8')
    ay,ax=np.where(aa>0);by,bx=np.where(bb>0)
    if not len(ax) or not len(bx):return 0.0
    dx=int(round(ax.mean()-bx.mean()));dy=int(round(ay.mean()-by.mean()))
    t=np.float32([[1,0,dx],[0,1,dy]])
    aligned=cv2.warpAffine(bb,t,(bb.shape[1],bb.shape[0]),flags=cv2.INTER_NEAREST,borderValue=0)
    return float(np.count_nonzero(aa!=aligned)/max(1,np.count_nonzero((aa|aligned)>0)))


def parse_clips(actor, scene_root, source_size, fps):
    name=str(actor['id']);clips=actor.get('clips')
    if not isinstance(clips,list) or len(clips)<2:stop(name+': needs two or more frame clips')
    x,y,w,h=[int(z) for z in actor['box']]
    W,H=source_size
    if w<6 or h<6 or x<0 or y<0 or x+w>W or y+h>H:
        stop(name+': invalid original-image coordinates in box')
    clip_sequence=[]; clip_stats=[]; actorset=set();active_frames=0
    previous_joints=None; first_joints=None; max_instant_joint=0.
    active_types=set()
    for c in clips:
        action=str(c.get('action',''))
        if not action:stop(name+': action label missing')
        frames=c.get('frames',[])
        if not isinstance(frames,list) or len(frames)<12:
            stop(f'{name}/{action}: require >=12 distinct-time authored 24fps frames, not a 2-pose wiggle')
        images=[];landmarks=[];asset_paths=[]
        hash_list=[];last_identical=0;max_identical=0
        for frame in frames:
            if not isinstance(frame,dict):stop(name+': every frame must provide png and landmarks')
            p=path_in(scene_root,frame.get('png'))
            im=read_image(p)
            if im.size!=(w,h): stop(f'{name}/{action}: {p.name} must be {w}x{h}, is {im.size}')
            alpha=np.asarray(im.getchannel('A'))
            if int(np.count_nonzero(alpha>85))<10:
                stop(name+'/'+action+': an empty/invisible character frame')
            joints=frame.get('joints')
            if not isinstance(joints,dict) or not isinstance(joints.get('root'),list):
                stop(name+'/'+action+': each pose requires visible root and joint landmarks')
            for k,v in joints.items():
                if not (isinstance(v,list) and len(v)==2 and all(isinstance(n,(int,float)) for n in v)):
                    stop(name+'/'+action+': malformed joint '+str(k))
                px,py=v
                if not (0<=px<w and 0<=py<h):stop(name+'/'+action+': joint outside sprite '+k)
                if k != 'root':
                    # Allow label over a 3px empty edge; detect fake hand labels in air.
                    ix,iy=round(px),round(py)
                    if not np.any(alpha[max(0,iy-3):min(h,iy+4),max(0,ix-3):min(w,ix+4)]>60):
                        stop(name+'/'+action+': joint has no nearby drawn body pixels: '+k)
            data=hashlib.sha1(np.asarray(im).tobytes()).hexdigest()
            if hash_list and hash_list[-1]==data:last_identical+=1
            else:last_identical=1
            max_identical=max(max_identical,last_identical)
            hash_list.append(data)
            images.append(im);landmarks.append(joints);asset_paths.append(p)
        unique=len(set(hash_list))
        if action!='idle':
            active_types.add(action);active_frames+=len(frames)
            if unique<8:stop(f'{name}/{action}: only {unique} authored poses; need >=8')
            if max_identical>2:stop(f'{name}/{action}: freezes for {max_identical} consecutive frames at {fps}fps')
        elif max_identical>6:stop(f'{name}/idle: frame hold exceeds 6 frames')
        reference=images[0]
        variation=max(unshifted_shape_difference(reference,z) for z in images[1:])
        if action!='idle' and variation<.22:
            stop(f'{name}/{action}: articulated silhouette change {variation:.1%}<22%; whole-crop movement does not count')
        # Two independent joints must move relative to the actor's own root
        # at >=22% of the source character height (large, perceptible sweep).
        jnames=set.intersection(*(set(d) for d in landmarks))-{'root'}
        excursions={}
        for joint in sorted(jnames):
            coords=np.array([[d[joint][0]-d['root'][0],d[joint][1]-d['root'][1]] for d in landmarks])
            excursions[joint]=round(float(np.linalg.norm(coords[:,None,:]-coords[None,:,:],axis=2).max()),2)
            step=float(np.max(np.linalg.norm(np.diff(coords,axis=0),axis=1)))
            max_instant_joint=max(max_instant_joint,step)
        semantic=[j for j,span in excursions.items() if span>=max(4.,.22*h)]
        if action!='idle' and len(semantic)<2:
            stop(f'{name}/{action}: only {len(semantic)} joints reach 22% height amplitude; require TWO independent visible joints')
        # Large individual poses are fine; discontinuous pose swaps are not.
        jumps=[pixel_diff(images[i],images[i+1]) for i in range(len(images)-1)]
        for k,dis in enumerate(jumps):
            if dis>.43:stop(f'{name}/{action}: hard frame snap {dis:.1%} between #{k} and #{k+1}')
        # Check action boundaries too, not just adjacent poses within a clip.
        if clip_sequence and pixel_diff(clip_sequence[-1][0],images[0])>.43:
            stop(f'{name}: abrupt sprite swap at boundary before action {action}')
        if previous_joints is not None:
            for joint in set(previous_joints)&set(landmarks[0]):
                if joint=='root':continue
                a=np.array(previous_joints[joint])-np.array(previous_joints['root'])
                b=np.array(landmarks[0][joint])-np.array(landmarks[0]['root'])
                if np.linalg.norm(a-b)>max(10.,h*.18):
                    stop(f'{name}: joint {joint} snaps at action boundary before {action}')
        if first_joints is None:first_joints=landmarks[0]
        previous_joints=landmarks[-1]
        clip_sequence.extend(zip(images,asset_paths,[action]*len(images)))
        clip_stats.append({'action':action,'frames':len(images),'unique_poses':unique,
                          'nonrigid_silhouette_variation':round(variation,3),'joint_sweeps_px':excursions,
                          'max_frame_pixel_change':round(max(jumps or [0.]),3)})
        actorset.update(asset_paths)
    if len(active_types)<2:stop(name+': two DISTINCT fully articulated ACTIVE actions required')
    if active_frames/len(clip_sequence)<.60:stop(name+': >=60% of sequence must contain real actions')
    if max_instant_joint>max(10.,h*.18):
        stop(f'{name}: a joint jumps {max_instant_joint:.1f}px between adjacent 24fps frames')
    first=clip_sequence[0][0];last=clip_sequence[-1][0]
    if pixel_diff(first,last)>.12:
        stop(name+': loop seam mismatch >12% character pixels')
    if previous_joints is not None and first_joints is not None:
        for joint in set(first_joints)&set(previous_joints):
            if joint=='root':continue
            a=np.array(previous_joints[joint])-np.array(previous_joints['root'])
            b=np.array(first_joints[joint])-np.array(first_joints['root'])
            if np.linalg.norm(a-b)>max(10.,h*.18):
                stop(f'{name}: joint {joint} jumps across the GIF cycle seam')
    frames_n=len(clip_sequence)
    return {'sequence':clip_sequence,'stats':clip_stats,'frames':frames_n,'resources':actorset,
            'active_fraction':round(active_frames/frames_n,3)}


def verify_and_load(scene,root,source,fps,seconds):
    if scene.get('version')!=3 or scene.get('mode')!='full-frame-pose-sprites':
        stop('v0.5 requires version:3, mode:full-frame-pose-sprites (old rotating rigs blocked)')
    if not scene.get('seamless',True):stop('seamless must be true')
    if not (40<=seconds<=60 and fps>=24 and fps*seconds<=1500):
        stop('full scene must be 40-60 s, >=24 FPS, <=1500 total frames')
    if float(fps)!=int(fps) or round(seconds*fps)!=seconds*fps:
        stop('fps and total frame count must be integral')
    actors=scene.get('actors',[])
    declared=scene.get('inventory',{}).get('actors',[])
    ids=[a.get('id') for a in actors]
    if not actors or not declared or len(set(ids))!=len(ids) or set(declared)!=set(ids):
        stop('every visible character ID must match inventory.actors exactly; none may be skipped')
    total=round(seconds*fps);observed=[];masks=[];data={};allfiles=set()
    for a in actors:
        ident=a['id']
        if not (a.get('role') in {'human','cat','dog','bird','animal'}):
            stop(ident+': provide explicit human/animal role')
        m=read_image(path_in(root,a.get('source_mask')),'L')
        if m.size!=source.size:stop(ident+': source_mask must align exactly with source')
        mask=np.asarray(m)
        if int(np.count_nonzero(mask>85))<20:stop(ident+': source mask is empty')
        mask_y,mask_x=np.where(mask>85)
        if int(mask_y.max()-mask_y.min())<15:
            stop(ident+': original actor <15px; must author enlarged consistent pose sprites first')
        # Include editable Pixelorama source projects and their landmark sidecars in the ZIP.
        for clip in a.get('clips',[]):
            origin=clip.get('pixelorama_source')
            if origin:
                project=path_in(root,origin.get('project'))
                landmarks=path_in(root,origin.get('joints_json'))
                if hashlib.sha256(project.read_bytes()).hexdigest()!=origin.get('source_sha256'):
                    stop(f'{ident}: Pixelorama project changed after sprite export; rebuild with pixelorama_bridge')
                allfiles.add(project);allfiles.add(landmarks)
        resources=parse_clips(a,root,source.size,fps)
        try:
            motion=verify_locomotion(a,resources['frames'],source.size,fps)
            validate_pose_steps(a,resources['sequence'],motion)
        except LocomotionError as exc:
            stop(str(exc))
        if total%resources['frames']!=0:
            stop(f'{ident}: cycle {resources["frames"]} frames does not evenly divide {total}-frame GIF')
        phase=int(a.get('phase_frames',0))
        if not 0<=phase<resources['frames']:stop(ident+': invalid phase_frames')
        masks.append(mask);allfiles|=resources['resources'];allfiles.add(path_in(root,a.get('source_mask')))
        data[ident]={**resources,'actor':a,'phase':phase,'world_motion':motion}
        observed.append({'id':ident,'role':a['role'],'cycle_frames':resources['frames'],
                         'active_fraction':resources['active_fraction'],'actions':resources['stats'],
                         'world_motion':{'mode':motion['mode'], 'world_travel_px':motion['world_travel_px'],
                                         'max_displacement_px':motion['max_displacement_px']} if motion else None})
    expected=set(scene.get('locomotion_required_for',[]))
    if expected:
        if expected-set(ids):stop('Required walking/running actors missing from cast')
        without=sorted(ident for ident in expected if data[ident]['world_motion'] is None)
        if without:stop('Required characters have no actual world travel: '+', '.join(without))
    # Every actor starts and ends at a loop-compatible pose on its own cycle.
    return data,masks,allfiles,{'gate':'pose-only-v0.5','mode':'independent-drawn-frame-sprites',
                               'actors':observed,'all_actors_pass':True,
                               'note':'No rotation/warp/flow interpolation on characters. Visual review still required.'}


def render(source,scene_path,out,seconds=48,fps=24,max_width=720):
    root=scene_path.parent.resolve();scene=json.loads(scene_path.read_text('utf8'))
    src=read_image(source,'RGB')
    actor_data,masks,allfiles,quality=verify_and_load(scene,root,src,fps,seconds)
    out.mkdir(parents=True,exist_ok=True)
    assets=out/'assets';assets.mkdir(exist_ok=True)
    np_src=np.asarray(src).copy()
    removed=np.maximum.reduce(masks)
    repaired=cv2.cvtColor(cv2.inpaint(cv2.cvtColor(np_src,cv2.COLOR_RGB2BGR),
                                      removed,5,cv2.INPAINT_TELEA),cv2.COLOR_BGR2RGB)
    bg=Image.fromarray(repaired,'RGB').convert('RGBA')
    W,H=src.size
    scale=min(1.,max_width/W) if max_width else 1.
    size=(round(W*scale),round(H*scale))
    bg=bg.resize(size,Image.Resampling.LANCZOS) if scale!=1 else bg
    # Exact pose sprite assets are never modified, interpolated, rotated or warped.
    poses={}
    for ident,item in actor_data.items():
        x,y,w,h=map(int,item['actor']['box'])
        sequences=[]
        for img,_,act in item['sequence']:
            img=img.resize((round(w*scale),round(h*scale)),Image.Resampling.NEAREST) if scale!=1 else img
            sequences.append((img,act))
        poses[ident]=((round(x*scale),round(y*scale)),sequences,item['phase'],item['world_motion'])
    from render_scene import atmosphere
    from streamed_animator import cyclic_lamps,cyclic_particles,ffmpeg_command
    # Registered source-matched day plates, if requested, must be real files.
    day=dict(scene.get('day_night',{}))
    for field in ('day_background','sky_mask'):
        if day.get(field):
            p=path_in(root,day[field]);allfiles.add(p)
            day[field]=str(p)
    framecount=round(seconds*fps)
    activity=defaultdict(int)
    with tempfile.TemporaryDirectory(prefix='living_poses_v05_') as work:
        temp=Path(work)
        # Support registered day/sky plates at output size without modifying original.
        for field in ('day_background','sky_mask'):
            if day.get(field):
                p=Path(day[field]);im=read_image(p,'L' if field=='sky_mask' else 'RGBA')
                if im.size!=size:
                    im=im.resize(size,Image.Resampling.NEAREST if field=='sky_mask' else Image.Resampling.LANCZOS)
                q=temp/(field+'.png');im.save(q);day[field]=str(q)
        for k in range(framecount):
            t=k/framecount
            frame=atmosphere(bg.copy(),t,day,temp)
            for actor in sorted(scene['actors'],key=lambda a:a.get('z',20)):
                ident=actor['id'];loc,seq,phase,motion=poses[ident]
                local_frame=(k+phase)%len(seq)
                sprite,act=seq[local_frame]
                if motion:
                    dx,dy=locomotion_sample(motion['path'],local_frame)
                    dest=(loc[0]+round(dx*scale),loc[1]+round(dy*scale))
                else:dest=loc
                frame.alpha_composite(sprite,dest=dest)
                activity[ident+':'+act]+=1
            frame=cyclic_lamps(frame,scene.get('lights',[]),t)
            frame=cyclic_particles(frame,scene.get('particles',[]),t,seconds)
            frame.convert('RGB').save(temp/f'{k:05d}.png',compress_level=1)
        pp=str(temp/'%05d.png');palette=temp/'palette.png'
        ffmpeg_command(['ffmpeg','-v','error','-y','-framerate',str(fps),'-i',pp,
                        '-vf','palettegen=max_colors=240:stats_mode=full','-frames:v','1',str(palette)])
        ffmpeg_command(['ffmpeg','-v','error','-y','-framerate',str(fps),'-i',pp,
                        '-i',str(palette),'-filter_complex','paletteuse=dither=bayer:bayer_scale=3',
                        '-loop','0',str(out/'living_scene.gif')])
    # Pack all genuine source sheets and every unique transparent pose PNG.
    src.save(assets/'source.png');Image.fromarray(repaired).save(assets/'background_clean.png')
    (assets/'scene.json').write_text(json.dumps(scene,ensure_ascii=False,indent=2),'utf8')
    (assets/'motion_gate.json').write_text(json.dumps(quality,ensure_ascii=False,indent=2),'utf8')
    (assets/'actions_actual.json').write_text(json.dumps(dict(activity),ensure_ascii=False,indent=2),'utf8')
    for file in sorted(allfiles):
        rel=file.relative_to(root)
        dest=assets/'project'/'inputs'/rel
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(file,dest)
        if file.suffix.lower()=='.png' and any(file in v['resources'] for v in actor_data.values()):
            dest2=assets/'poses'/rel;dest2.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(file,dest2)
    zpath=out/'living_scene_assets.zip'
    with zipfile.ZipFile(zpath,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for file in sorted(assets.rglob('*')):
            if file.is_file():z.write(file,file.relative_to(assets).as_posix())
    with Image.open(out/'living_scene.gif') as gif:
        if getattr(gif,'n_frames',1)<24 or gif.info.get('loop')!=0:stop('GIF not properly animated or looping')
    with zipfile.ZipFile(zpath) as z:
        if z.testzip() is not None:stop('corrupted ZIP')
    return {'gif':str(out/'living_scene.gif'),'zip':str(zpath),
            'actor_count':len(actor_data),'fps':fps,'seconds':seconds,'character_deformation':False}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('source',type=Path)
    ap.add_argument('--scene',required=True,type=Path)
    ap.add_argument('--out',required=True,type=Path)
    ap.add_argument('--seconds',type=int,default=48)
    ap.add_argument('--fps',type=int,default=24)
    ap.add_argument('--max-width',type=int,default=720)
    ap.add_argument('--pixelorama',default=None,help='Pixelorama executable; also PIXELORAMA_BIN')
    opts=ap.parse_args()
    from pixelorama_bridge import compile_scene
    original=opts.scene.resolve()
    compiled=compile_scene(original,opts.out,opts.pixelorama)
    print(json.dumps(render(opts.source.resolve(),compiled,opts.out.resolve(),opts.seconds,opts.fps,opts.max_width),ensure_ascii=False))

if __name__=='__main__':main()
