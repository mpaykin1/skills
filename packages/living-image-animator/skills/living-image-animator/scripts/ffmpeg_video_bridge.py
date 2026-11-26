#!/usr/bin/env python3
"""Verified, source-locked GIF -> MP4/WebM with author-owned Howler ambience.

Use *existing approved* all-actors-full-pose GIF/ZIP. Time-normalize existing
GIF frames to requested integer FPS; never tween, warp, synthesize, or replace
sprites. Spatial/actor sounds remain interactive in Howler HTML, NOT falsely
presented as spatial in a linear exported movie. External real FFmpeg required.
"""
from __future__ import annotations
import argparse
import bisect
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import zipfile
from PIL import Image
from pixijs_bridge import load_scene

class VideoBridgeError(ValueError):pass

def block(reason):raise VideoBridgeError('FFmpeg original-pose video blocked: '+str(reason))

def command(binary):
    path=shutil.which(str(binary)) if binary else None
    if not path:block('Real FFmpeg and ffprobe must be installed; executable not found')
    return path

def run_capture(args,timeout=90):
    try:proc=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout,check=False)
    except (OSError,subprocess.TimeoutExpired) as e:block('External video tool unavailable: '+str(e))
    if proc.returncode: block('Native media command failed: '+proc.stderr.decode('utf8','replace')[-700:])
    return proc.stdout.decode('utf8','replace')

def media_probe(path,ffprobe='ffprobe',count=False):
    cmd=[command(ffprobe),'-v','error']
    if count:cmd+=['-count_frames']
    cmd+=['-show_entries','format=duration:stream=codec_type,codec_name,nb_read_frames,avg_frame_rate,width,height',
          '-of','json',str(path)]
    try:result=json.loads(run_capture(cmd,timeout=100))
    except (ValueError,KeyError) as e:block('FFprobe output invalid: '+str(e))
    if 'streams' not in result:block('No verifiable media streams')
    return result

def check_ffmpeg(ffmpeg='ffmpeg',ffprobe='ffprobe',formats=('mp4','webm')):
    binary=command(ffmpeg);command(ffprobe)
    version=run_capture([binary,'-version'])
    if not re.search(r'ffmpeg version\s+\d+',version,re.I):block('Not a real FFmpeg executable')
    encoders=run_capture([binary,'-hide_banner','-encoders'])
    needed={'mp4':'libx264','webm':'libvpx-vp9'}
    missing=[v for k,v in needed.items() if k in formats and not re.search(r'^\s*V.{5}\s+'+re.escape(v)+r'\s',encoders,re.M)]
    if missing:block('FFmpeg missing required native encoder(s): '+','.join(missing))
    return binary

def approved_art(approved_zip,gif,scene_path,fps,seconds):
    if type(fps) is not int or not 24<=fps<=120 or type(seconds) is not int or not 40<=seconds<=60:
        block('Prior original motion gate requires integer 24–120 FPS and 40–60 seconds')
    approved_zip=Path(approved_zip).resolve();gif=Path(gif).resolve();scene_path=Path(scene_path).resolve()
    if not approved_zip.is_file() or not gif.is_file() or not scene_path.is_file():
        block('Original verified scene.json, sprite ZIP and completed GIF required')
    original=load_scene(approved_zip)  # Existing strict artist motion/identity/source gate.
    with zipfile.ZipFile(approved_zip) as z:
        if z.testzip() is not None:block('Approved original ZIP corrupted')
        cfg=json.loads(z.read('scene.json'))
        motion=json.loads(z.read('motion_gate.json'))
    if motion.get('all_actors_pass') is not True:block('Full-body pose, gait and identity checks did not pass')
    authored=json.loads(scene_path.read_text('utf8'))
    if authored.get('inventory')!=cfg.get('inventory'):
        block('Authored scene identity roster changed after source approval')
    if authored.get('pixi',{}).get('audio')!=cfg.get('pixi',{}).get('audio'):
        block('Howler audio declarations changed after approval')
    with Image.open(gif) as im:
        if im.format!='GIF' or im.n_frames<24 or im.info.get('loop')!=0:
            block('Original approved GIF must be genuinely animated and looping')
        if im.size!=(original['width'],original['height']):
            # Original user requested max-width render may differ from full project size.
            orig_w,orig_h=original['width'],original['height'];w,h=im.size
            if not (0<w<=orig_w and 0<h<=orig_h and abs(w/orig_w-h/orig_h)<.005):
                block('GIF dimensions mismatch original scene aspect ratio')
        size=im.size
    return {'original_actors':len(original['actors']),'size':size,'fps':fps,'seconds':seconds,
            'motion_gate':True,'original_gif_sha256':hashlib.sha256(gif.read_bytes()).hexdigest()}

def source_audio(approved_zip,scene_path,with_ambience):
    if not with_ambience:return [],[]
    # Reuse the existing official Howler.js author-file validation (including source SHA).
    from howler_bridge import audio_config,read_file
    cfg,assets=audio_config(approved_zip,scene_path)
    authored=json.loads(Path(scene_path).read_text('utf8'))['pixi']['audio']['sounds']
    declared={s['id']:s for s in authored}
    chosen=[]
    for rec in cfg['sounds']:
        if rec['mode']!='ambience':continue
        original=declared[rec['id']]
        path=read_file(Path(scene_path).resolve().parent,original['file'])
        if hashlib.sha256(path.read_bytes()).hexdigest()!=rec['source_sha256']:
            block('Howler source audio file changed during export')
        chosen.append({'path':path,'id':rec['id'],'volume':rec['volume'],
                       'loop':bool(original.get('loop',True)),'sha256':rec['source_sha256']})
    if not chosen:block('--with-ambience requires at least one real Howler mode=ambience source')
    return chosen,assets

def gif_timeline(gif):
    """Source frames and centisecond timing: no interpolated animation frames."""
    ends=[];total=0
    with Image.open(gif) as im:
        count=im.n_frames
        if count>10000:block('Original GIF frame budget exceeded')
        for index in range(count):
            im.seek(index)
            delay=int(im.info.get('duration',0))
            if delay<=0 or delay>1000:block('Malformed GIF frame timestamps')
            total+=delay;ends.append(total)
    return ends,total

def encode(gif,output,fps,seconds,kind,ambiences=(),master_volume=1.,ffmpeg='ffmpeg',ffprobe='ffprobe'):
    if kind not in ('mp4','webm'):block('Only MP4 and WebM video formats supported')
    binary=check_ffmpeg(ffmpeg,ffprobe,(kind,))
    gif=Path(gif).resolve(); output=Path(output).resolve(); output.parent.mkdir(parents=True,exist_ok=True)
    if output.exists():block('Will not overwrite an already exported video')
    boundaries,total=gif_timeline(gif)
    if not 10_000<=total<=90_000:block('Original GIF duration outside safe limits')
    with Image.open(gif) as src:width,height=src.size
    if width*height>4_000_000:block('Large original video: reduce render resolution without changing original sprite artwork')
    count=round(fps*seconds)
    base=[binary,'-hide_banner','-loglevel','error','-nostdin','-y',
          '-f','rawvideo','-pixel_format','rgb24','-video_size',f'{width}x{height}',
          '-framerate',str(fps),'-i','pipe:0']
    if len(ambiences)>8:block('Limit linear soundtrack to 8 authored ambient sources')
    for a in ambiences:
        if a['loop']:base+=['-stream_loop','-1']
        base+=['-i',str(a['path'])]
    base+=['-map','0:v:0']
    if ambiences:
        filters=[]
        for j,a in enumerate(ambiences,1):
            if not 0<=a['volume']<=1:block('Original ambience volume outside 0..1')
            filters.append(f'[{j}:a:0]aresample=48000,volume={a["volume"]:.5f},apad=pad_dur={seconds}[a{j}]')
        joined=''.join(f'[a{j}]' for j in range(1,len(ambiences)+1))
        if not 0<=master_volume<=1:block('Original Howler master_volume outside 0..1')
        filters.append(f'{joined}amix=inputs={len(ambiences)}:duration=longest:normalize=0,'
                       f'volume={master_volume:.5f},atrim=duration={seconds},asetpts=PTS-STARTPTS[aout]')
        base+=['-filter_complex',';'.join(filters),'-map','[aout]']
    if kind=='mp4':
        base+=['-c:v','libx264','-preset','medium','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart']
        if ambiences:base+=['-c:a','aac','-b:a','160k']
    else:
        base+=['-c:v','libvpx-vp9','-b:v','0','-crf','29','-deadline','good','-cpu-used','3','-row-mt','1','-pix_fmt','yuv420p']
        if ambiences:base+=['-c:a','libopus','-b:a','128k']
    base+=['-r',str(fps),'-frames:v',str(count),'-t',str(seconds),str(output)]
    with Image.open(gif) as image:
        index=-1;cached=None
        try:
            proc=subprocess.Popen(base,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        except OSError as e:block('Cannot launch original FFmpeg encoder: '+str(e))
        try:
            for k in range(count):
                # Map GIF timing to required authored final video duration; index is monotonic.
                moment=((k+0.5)/count)*total
                desired=min(image.n_frames-1,bisect.bisect_right(boundaries,moment))
                if desired!=index:
                    image.seek(desired);cached=image.convert('RGB').tobytes();index=desired
                proc.stdin.write(cached)
            proc.stdin.close()
            err=proc.stderr.read();status=proc.wait(timeout=max(120,min(1800,seconds*30)))
        except (BrokenPipeError,OSError,subprocess.TimeoutExpired) as exc:
            proc.kill();proc.wait();output.unlink(missing_ok=True)
            block('FFmpeg video process failed: '+str(exc))
        if status!=0:
            output.unlink(missing_ok=True)
            block('FFmpeg failed to encode the real source frames: '+err.decode('utf8','replace')[-800:])
    if not output.is_file() or output.stat().st_size<200:block('FFmpeg returned empty video')
    info=media_probe(output,ffprobe,True)
    video=next((s for s in info['streams'] if s['codec_type']=='video'),None)
    expected_codec='h264' if kind=='mp4' else 'vp9'
    if not video or video.get('codec_name')!=expected_codec or [video.get('width'),video.get('height')]!=[width,height]:
        output.unlink(missing_ok=True);block('Output video codec or source dimensions invalid')
    if str(video.get('nb_read_frames'))!=str(count):
        output.unlink(missing_ok=True);block('Output video frame count changed from original display clock')
    duration=float(info.get('format',{}).get('duration') or 0)
    if abs(duration-seconds)>.25:
        output.unlink(missing_ok=True);block('Output video playback duration changed')
    has_audio=any(s['codec_type']=='audio' for s in info['streams'])
    if has_audio!=bool(ambiences):
        output.unlink(missing_ok=True);block('Soundtrack not present or unexpectedly added')
    return {'path':str(output),'kind':kind,'size_bytes':output.stat().st_size,
            'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),
            'frames':count,'fps':fps,'seconds':seconds,'codec':expected_codec,
            'soundtrack': 'authored Howler ambience only' if ambiences else 'silent',
            'spatial_audio':'interactive Howler HTML only', 'source_gif_timing_normalized':True,
            'source_character_art_modified':False,'character_motion_interpolation':False}

def build(gif,approved_zip,scene_path,out,fps=24,seconds=48,fmt='both',with_ambience=False,
          ffmpeg='ffmpeg',ffprobe='ffprobe'):
    if fmt not in ('both','mp4','webm'):block('Invalid format')
    output=Path(out).resolve();output.mkdir(parents=True,exist_ok=True)
    validated=approved_art(approved_zip,gif,scene_path,fps,seconds)
    audio,assets=source_audio(approved_zip,scene_path,with_ambience)
    original=json.loads(Path(scene_path).read_text('utf8'))
    master=original.get('pixi',{}).get('audio',{}).get('master_volume',.75) if audio else 1.
    results=[]
    for typ in (('mp4','webm') if fmt=='both' else (fmt,)):
        results.append(encode(gif,output/f'living_scene_video.{typ}',fps,seconds,typ,audio,master,ffmpeg,ffprobe))
    return {'source':validated,'files':results,'soundtracks':[{'id':a['id'],'sha256':a['sha256']} for a in audio],
            'original_audio_assets':assets,'original_gif_retained':True,
            'source_content': 'verified original rendered GIF (palette limited), no added character poses',
            'license':'External FFmpeg LGPL/GPL depending native configured binary; executable not redistributed'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--approved-zip',type=Path,required=True)
    p.add_argument('--gif',type=Path,required=True);p.add_argument('--scene',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--fps',type=int,default=24)
    p.add_argument('--seconds',type=int,default=48);p.add_argument('--format',choices=('both','mp4','webm'),default='both')
    p.add_argument('--with-ambience',action='store_true');p.add_argument('--ffmpeg',default='ffmpeg');p.add_argument('--ffprobe',default='ffprobe')
    a=p.parse_args();data=build(a.gif,a.approved_zip,a.scene,a.out,a.fps,a.seconds,a.format,a.with_ambience,a.ffmpeg,a.ffprobe)
    print(json.dumps({k:v for k,v in data.items() if k!='original_audio_assets'},ensure_ascii=False))
if __name__=='__main__':main()
