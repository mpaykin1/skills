#!/usr/bin/env python3
"""Rhubarb Lip Sync 1.14.0 + original per-pose full-body RGBA cels + Howler.js.

No face warping, cutout mouths, AI poses, overlays, animation gate weakening or fake
speech recognition. Only *genuinely authored* whole-body alternate frames, with
exactly unchanged original pixels outside a tightly limited mouth region.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import zipfile
from PIL import Image, ImageChops, ImageDraw
from pixijs_bridge import load_scene

VERSION='1.14.0'
SHAPES='ABCDEFX'
class LipSyncError(ValueError): pass

def stop(message): raise LipSyncError('Rhubarb Lip Sync integration blocked: '+str(message))

def safe(root,relative):
    if not isinstance(relative,str) or not relative or len(relative)>255 or '\\' in relative or ':' in relative:
        stop('Expected safe author-owned scene-relative file/folder')
    parts=relative.split('/')
    if any(x in ('','.','..') for x in parts) or Path(relative).is_absolute():stop('Path traversal rejected')
    root=Path(root).resolve(); candidate=(root/relative).resolve()
    if root not in candidate.parents:stop('File or directory outside original scene')
    return candidate

def cli(binary):
    executable=shutil.which(str(binary)) if binary else None
    if not executable: stop('Install the authentic Rhubarb Lip Sync 1.14.0 CLI or use --rhubarb /path/to/rhubarb')
    try:
        p=subprocess.run([executable,'--version'],capture_output=True,text=True,timeout=12,check=False)
    except (OSError,subprocess.TimeoutExpired) as e:stop('Rhubarb executable failed: '+str(e))
    if p.returncode or not re.search(r'(?<![\d.])1\.14\.0(?![\d.])',p.stdout+' '+p.stderr):
        stop('Only genuine Rhubarb Lip Sync 1.14.0 is supported')
    return executable

def run_tool(command,secs=130):
    try: result=subprocess.run(command,capture_output=True,text=True,timeout=secs,check=False)
    except (OSError,subprocess.TimeoutExpired) as e:stop('Native audio tool failed: '+str(e))
    if result.returncode:stop('Native audio tool returned error: '+(result.stderr or result.stdout)[-650:])
    return result

def authored_audio(scene,source,archive,speaker):
    pixi=source.get('pixi') or {}; audio=pixi.get('audio') or {}
    sounds=audio.get('sounds',[])
    if not isinstance(sounds,list):stop('Howler audio source declarations missing')
    chosen=[s for s in sounds if isinstance(s,dict) and s.get('id')==speaker['sound_id']]
    if len(chosen)!=1:stop('Lip track sound_id must name ONE existing genuine Howler sound')
    item=chosen[0]
    if item.get('mode')!='actor' or item.get('actor_id')!=speaker['actor_id'] or item.get('loop',True) is not False:
        stop('Dialogue must be one original non-looping Howler actor sound tied to this same actor')
    path=safe(scene.parent,item.get('file'))
    if not path.is_file() or path.suffix.lower() not in ('.wav','.ogg','.mp3'):
        stop('Dialogue requires an original WAV, OGG or MP3 file')
    raw=path.read_bytes()
    if not 100<=len(raw)<=8_000_000:stop('Dialogue source absent or oversized')
    member='project/audio/originals/'+item['id']+path.suffix.lower()
    if member not in archive.namelist() or archive.read(member)!=raw:
        stop('Dialogue bytes do not match verified Howler audio packaged earlier')
    return path,raw

def detect(audio,rhubarb,recognizer,dialog,ffmpeg,fps):
    if recognizer not in ('phonetic','pocketSphinx'):stop('Unsupported Rhubarb recognizer')
    with tempfile.TemporaryDirectory(prefix='lia_rhubarb_') as td:
        root=Path(td); original=audio
        if audio.suffix.lower()=='.mp3':
            ff=shutil.which(str(ffmpeg)) if ffmpeg else None
            if not ff:stop('Real FFmpeg needed to convert original MP3 to Rhubarb WAV input')
            original=root/'original_audio.wav'
            run_tool([ff,'-hide_banner','-v','error','-nostdin','-y','-i',str(audio),
                      '-ac','1','-ar','16000','-c:a','pcm_s16le',str(original)])
        out=root/'rhubarb.json';dat=root/'opentoonz.dat'
        args=['-r',recognizer,'--extendedShapes','X']
        if dialog:args+=['--dialogFile',str(dialog)]
        run_tool([rhubarb,'-f','json','-o',str(out),*args,str(original)])
        run_tool([rhubarb,'-f','dat','--datFrameRate',str(fps),'--datUsePrestonBlair','-o',str(dat),*args,str(original)])
        try: data=json.loads(out.read_text('utf8'))
        except (OSError,ValueError) as e:stop('Rhubarb JSON invalid: '+str(e))
        cues=data.get('mouthCues')
        try: duration=float(data.get('metadata',{}).get('duration'))
        except (ValueError,TypeError):stop('Rhubarb metadata.duration missing')
        if not .15<=duration<=40 or not isinstance(cues,list) or not 2<=len(cues)<=1200:
            stop('Rhubarb speech duration/cue count invalid')
        prev=0.; output=[]
        for c in cues:
            if not isinstance(c,dict) or c.get('value') not in SHAPES:stop('Rhubarb returned unexpected viseme')
            a,b=c.get('start'),c.get('end')
            if type(a) not in (int,float) or type(b) not in (int,float) or not (math.isfinite(a) and math.isfinite(b)):
                stop('Nonfinite Rhubarb cue times')
            if abs(a-prev)>.025 or b<=a or b>duration+.025:stop('Overlapping/gapped Rhubarb mouth cues')
            output.append([round(float(a),4),round(float(b),4),c['value']]);prev=b
        if abs(prev-duration)>.025 or output[0][0]>.025:stop('Rhubarb cues do not cover original dialogue')
        return output,duration,dat.read_bytes()

def png(raw,dimensions,label):
    if not 30<=len(raw)<=2_000_000:stop(label+': invalid or oversized author-painted PNG')
    with Image.open(io.BytesIO(raw)) as im:
        if im.format!='PNG' or im.size!=dimensions or im.mode not in ('RGBA','LA','P'):
            stop(label+': original full-body pose must be alpha PNG of source dimensions')
        result=im.convert('RGBA')
    lo,hi=result.getchannel('A').getextrema()
    if lo==255 or hi==0:stop(label+': missing actual transparent sprite silhouette')
    return result

def load_tracks(approved_zip,scene_path,rhubarb_binary,ffmpeg='ffmpeg',fps=24):
    """Synchronized annotated speech; 7 original mouth cels for EVERY original body pose.
    """
    if type(fps) is not int or not 24<=fps<=120:stop('Author animation must run at 24..120 fps')
    approved_zip=Path(approved_zip).resolve();scene_path=Path(scene_path).resolve()
    original=load_scene(approved_zip)  # Original all-actor gate may not be bypassed.
    author=json.loads(scene_path.read_text('utf8'))
    with zipfile.ZipFile(approved_zip) as z:
        if z.testzip():stop('Approved original sprite ZIP is damaged')
        source=json.loads(z.read('scene.json'))
        if json.loads(z.read('motion_gate.json')).get('all_actors_pass') is not True:
            stop('Original full-body motion gate failed')
        conf=author.get('pixi',{}).get('lipsync')
        if conf!=source.get('pixi',{}).get('lipsync') or author.get('inventory')!=source.get('inventory'):
            stop('Current lip sync config or original cast differs from approved source')
        if author.get('pixi',{}).get('audio')!=source.get('pixi',{}).get('audio'):
            stop('Original Howler audio declarations have changed')
        if not isinstance(conf,dict) or set(conf)-{'speakers'}:stop('Expected source.pixi.lipsync.speakers only')
        speakers=conf['speakers']
        if not isinstance(speakers,list) or not 1<=len(speakers)<=3:stop('Use 1..3 approved speaking actors')
        verified={actor['id']:actor for actor in original['actors']}
        compiled={actor['id']:actor for actor in source['actors']}
        registered=set();tracks=[];assets=[];byte_budget=0
        rhubarb=cli(rhubarb_binary)
        for spec in speakers:
            if not isinstance(spec,dict) or set(spec)-{'actor_id','sound_id','viseme_dir','mouth_roi','recognizer','dialog_file'}:
                stop('Unknown speaker declaration')
            actor_id=spec.get('actor_id')
            if actor_id not in verified or actor_id in registered:stop('Speaker must have one original unique approved actor ID')
            registered.add(actor_id)
            actor=compiled[actor_id];info=verified[actor_id]
            w,h=info['box'][2:4];roi=spec.get('mouth_roi')
            if not isinstance(roi,list) or len(roi)!=4 or any(type(x) is not int for x in roi):
                stop('mouth_roi needs 4 local integer pixel coordinates')
            x,y,mw,mh=roi
            if not (0<=x<w and 0<=y<h and 2<=mw<=w//2 and 2<=mh<=h//2 and x+mw<=w and y+mh<=h):
                stop('Original mouth ROI must be a small bounding box within full-body sprite')
            frames=[fr['png'] for clip in actor['clips'] for fr in clip['frames']]
            if len(frames)!=len(info['frames']) or not 24<=len(frames)<=120:
                stop('Lip sync actor timeline does not match source-authored full-body frames')
            basedir=safe(scene_path.parent,spec.get('viseme_dir'))
            if not basedir.is_dir():stop('No genuine author-drawn mouth variant directory')
            sourceframes=[png(z.read('project/inputs/'+p),(w,h),p) for p in frames]
            voices,orig_audio=authored_audio(scene_path,author,z,spec)
            transcript=spec.get('dialog_file')
            if transcript:
                transcript=safe(scene_path.parent,transcript)
                if not transcript.is_file() or transcript.stat().st_size>64_000:stop('Missing/oversized real dialogue transcript')
            cues,duration,opentoonz_dat=detect(voices,rhubarb,spec.get('recognizer','phonetic'),transcript,ffmpeg,fps)
            variants={};raws={};shape_pix={}
            for shape in SHAPES:
                variants[shape]=[];raws[shape]=[];shape_pix[shape]=[]
                for j,base in enumerate(sourceframes):
                    path=basedir/shape/f'{j:03d}.png'
                    if not path.is_file() or basedir not in path.resolve().parents:
                        stop(f'{actor_id}: missing original full-body viseme {shape}/{j:03d}.png')
                    raw=path.read_bytes();frame=png(raw,(w,h),f'{actor_id} {shape} frame {j}')
                    # Full exact body, clothes, root position and silhouette unchanged outside artist mouth rectangle.
                    outside=Image.new('L',(w,h),255)
                    ImageDraw.Draw(outside).rectangle((x,y,x+mw-1,y+mh-1),fill=0)
                    differ=ImageChops.difference(base,frame)

                    if any(ImageChops.multiply(differ.getchannel(channel),outside).getbbox() for channel in ('R','G','B','A')):
                        stop(f'{actor_id} {shape}/{j}: original full-body pixels changed outside mouth ROI')
                    vis=frame.crop((x,y,x+mw,y+mh)).tobytes()
                    shape_pix[shape].append(hashlib.sha256(vis).hexdigest())
                    variants[shape].append('data:image/png;base64,'+base64.b64encode(raw).decode('ascii'))
                    raws[shape].append(raw)
                    byte_budget+=len(raw)
                    if byte_budget>35_000_000:stop('Authentic mouth variant budget >35MB; split source scene')
            for j in range(len(frames)):
                if len({shape_pix[s][j] for s in SHAPES})<4:
                    stop(f'{actor_id} frame {j}: source art contains fewer than four genuinely different mouth shapes')
            frame_cues=[]
            for j in range(math.ceil(duration*fps)):
                mid=(j+.5)/fps;shape=next((v for a,b,v in cues if a<=mid<b),'X')
                frame_cues.append(shape)
            safe_id=re.sub('[^A-Za-z0-9_-]','_',actor_id)
            soundid=re.sub('[^A-Za-z0-9_-]','_',str(spec['sound_id']))
            for shape in SHAPES:
                for i,raw in enumerate(raws[shape]):
                    assets.append((f'project/lipsync/{safe_id}/{shape}/{i:03d}.png',raw))
            assets.append((f'project/lipsync/{safe_id}/opentoonz.dat',opentoonz_dat))
            if transcript:assets.append((f'project/lipsync/{safe_id}/dialog.txt',transcript.read_bytes()))
            tracks.append({'actor':actor_id,'sound':spec['sound_id'],'duration':duration,
                'shape_names':SHAPES,'cues':cues,'frame_cues':frame_cues,
                'variants':variants,'frame_count':len(frames),'voice_sha256':hashlib.sha256(orig_audio).hexdigest(),
                'source_frame_hashes':[hashlib.sha256(z.read('project/inputs/'+p)).hexdigest() for p in frames],
                'rhubarb_version':VERSION,'recognizer':spec.get('recognizer','phonetic'),
                'source_roi':roi,'opentoonz_dat':f'project/lipsync/{safe_id}/opentoonz.dat'})
        return tracks,assets,{'rhubarb_version':VERSION,'actors':len(tracks),'full_cel_variants':sum(t['frame_count']*len(SHAPES) for t in tracks),
            'source_audio_mode':'Howler actor sound; non-looping','original_actor_cels_changed':False,
            'new_audio_synthesized':False,'pose_warp':False,'offline':True}

LIP_JS=r'''    // Original full-body cels are NEVER deformed, overlaid, skeleton warped, or resized.
    // Each speaking pose has 7 separately painted full-body variants, exactly
    // matching the approved body pixels outside the artist-declared mouth ROI.
    const LIA_LIPSYNC=__DATA__;
    const LIA_LIP_PLAYERS=[];
    for(const t of LIA_LIPSYNC){
      const v=avatars.find(a=>a.actor.id===t.actor);
      if(!v || v.tiles.length!==t.frame_count) throw new Error('Authentic speech actor pose count changed');
      const mouthFrames={};
      for(const shape of 'ABCDEFX'){
        mouthFrames[shape]=[];
        for(const uri of t.variants[shape]){
          const source=await sourceFromData(uri);
          mouthFrames[shape].push(new PIXI.Texture({source}));
        }
      }
      LIA_LIP_PLAYERS.push({def:t,avatar:v,mouthFrames});
    }
    // This callback is registered after the ORIGINAL artist-pose ticker.
    // Read the precise Howler playback clock, not the wall clock of a GIF loop.
    app.ticker.add(()=>{
      if(!on)return;
      const elapsed=(performance.now()-launched)/1000;
      const ix=Math.floor((elapsed%S.seconds)*S.fps);
      for(const player of LIA_LIP_PLAYERS){
        const sound=audioItems.find(s=>s.def.id===player.def.sound);
        if(!sound || !sound.howl.playing())continue;
        const at=Number(sound.howl.seek());
        if(!Number.isFinite(at)||at<0||at>=player.def.duration)continue;
        const cue=player.def.cues.find(([start,end])=>start<=at && at<end);
        if(!cue)continue;
        const frame=(ix+player.avatar.actor.phase)%player.avatar.tiles.length;
        player.avatar.figure.texture=player.mouthFrames[cue[2]][frame];
      }
    });
    window.__livingLipSync={engine:'Rhubarb Lip Sync 1.14.0',speakers:LIA_LIP_PLAYERS.length,
      authorDrawnFullCels:true,characterBodyDeformation:false,clock:'Howler.js seek()'};
'''

def html_patch(upstream,out,tracks):
    upstream=Path(upstream).resolve();html=upstream.read_text('utf8')
    anchor='    app.ticker.add(()=>{if(on)updateSpatial();});'
    if html.count(anchor)!=1 or html.count('    const avatars=[];')!=1 or 'window.Howler' not in html or 'sourceFromData(' not in html:
        stop('Previously verified PixiJS viewport + Howler audio HTML is required')
    if 'LIA_LIPSYNC=' in html:stop('Lip sync already present')
    payload=json.dumps([{k:v for k,v in tr.items() if k in ('actor','sound','duration','cues','variants','frame_count')} for tr in tracks],ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
    html=html.replace(anchor,anchor+'\n'+LIP_JS.replace('__DATA__',payload),1)
    if len(html.encode('utf8'))>150*1024*1024:stop('Standalone HTML larger than 150MiB')
    out=Path(out).resolve();out.parent.mkdir(parents=True,exist_ok=True)
    if out.exists():stop('Refusing to overwrite existing standalone HTML')
    tmp=out.with_suffix('.tmp');tmp.write_text(html,'utf8');os.replace(tmp,out)
    return out,{'html_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'speakers':len(tracks),'offline':True,
                'same_original_character_identities':True,'mouths_full_body_no_warp':True}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--approved-zip',type=Path,required=True)
    p.add_argument('--scene',type=Path,required=True);p.add_argument('--audio-html',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--rhubarb',default='rhubarb')
    p.add_argument('--ffmpeg',default='ffmpeg');p.add_argument('--fps',type=int,default=24)
    q=p.parse_args();tr,_,meta=load_tracks(q.approved_zip,q.scene,q.rhubarb,q.ffmpeg,q.fps)
    output,render=html_patch(q.audio_html,q.out,tr)
    print(json.dumps({'html':str(output),**meta,**render},ensure_ascii=False))
