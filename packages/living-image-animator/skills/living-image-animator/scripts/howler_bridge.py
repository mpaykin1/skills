#!/usr/bin/env python3
"""Source-authored 2.5D spatial sound using Howler.js 2.2.4.

Additive ONLY: operates on verified original GIF/assets ZIP and PixiJS camera HTML,
never modifies original pose PNGs, actor sprite atlas, CullerPlugin, or physics.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import math
import os
from pathlib import Path
import re
import zipfile
from pixijs_bridge import load_scene

VERSION='2.2.4'
class HowlerBridgeError(ValueError): pass

def stop(message):raise HowlerBridgeError('Howler.js spatial-audio export blocked: '+str(message))

def scalar(v,lo,hi,label):
    if type(v) not in (int,float) or not math.isfinite(v) or not lo<=v<=hi:
        stop(f'{label} must be finite number between {lo} and {hi}')
    return float(v)

def read_file(root,relative):
    if not isinstance(relative,str) or not relative or len(relative)>256 or '\\' in relative or ':' in relative:
        stop('Audio file must be a short, safe project-relative path')
    rel=Path(relative)
    if rel.is_absolute() or any(x in ('','.','..') for x in relative.split('/')):
        stop('Audio path traversal is forbidden')
    root=Path(root).resolve();path=(root/rel).resolve()
    if root not in path.parents or not path.is_file():stop('Original sound file missing or outside project: '+relative)
    return path

def howler_bundle(path):
    path=path or os.environ.get('LIA_HOWLER_JS')
    if not path:stop('Actual howler.js 2.2.4 bundle required: --fetch-howler or --howler-js')
    p=Path(path).expanduser().resolve()
    if not p.is_file():stop('Original howler library missing at '+str(p))
    raw=p.read_bytes()
    if not 10000<len(raw)<250000 or b'howler.js v2.2.4' not in raw[:250] or b'Howler' not in raw:
        stop('Expected original pinned full howler.js 2.2.4, including spatial audio')
    try:code=raw.decode('utf8')
    except UnicodeError:stop('Invalid JavaScript file encoding')
    return p,code

def audio_config(approved_zip,original_scene):
    # Requires the previous strict loader's original cast, source-pose and gate checks.
    verified=load_scene(approved_zip)
    original_scene=Path(original_scene).resolve()
    with zipfile.ZipFile(approved_zip) as archive:
        if archive.testzip() is not None:stop('Verified sprite ZIP is corrupt')
        try:
            compiled=json.loads(archive.read('scene.json'))
            motion=json.loads(archive.read('motion_gate.json'))
        except (ValueError,KeyError) as error:stop('Verified source scene and motion gate missing: '+str(error))
    if motion.get('all_actors_pass') is not True:stop('Original actor animation validation did not pass')
    source=json.loads(original_scene.read_text('utf8'))
    if source.get('inventory')!=compiled.get('inventory'):
        stop('Author-defined audio scene cast differs from original approved cast')
    if source.get('pixi',{}).get('audio')!=compiled.get('pixi',{}).get('audio'):
        stop('Audio declarations differ from the approved original scene')
    pixi=source.get('pixi',{})
    if not isinstance(pixi,dict):stop('scene.pixi should be a JSON object')
    cfg=pixi.get('audio')
    if not isinstance(cfg,dict):stop('Author must define pixi.audio with genuine source recordings')
    if set(cfg)-{'sounds','pixels_per_unit','master_volume','listener'}:
        stop('Unknown pixi.audio settings')
    scale=scalar(cfg.get('pixels_per_unit',100),10,2000,'pixels_per_unit')
    volume=scalar(cfg.get('master_volume',0.75),0,1,'master_volume')
    sounds=cfg.get('sounds')
    if not isinstance(sounds,list) or not 1<=len(sounds)<=12:
        stop('pixi.audio.sounds needs 1–12 original source audio files')
    cast={a['id'] for a in verified['actors']}
    listener=cfg.get('listener','camera')
    if listener!='camera' and listener not in cast:stop('Listener must be camera or an approved actor ID')
    out=[];assets=[];ids=set();total=0
    for i,item in enumerate(sounds):
        if not isinstance(item,dict) or set(item)-{'id','file','mode','loop','volume','position','actor_id','ref_distance','max_distance','rolloff'}:
            stop('Unknown audio sound declaration #'+str(i))
        name=item.get('id')
        if not isinstance(name,str) or not re.fullmatch('[A-Za-z][A-Za-z0-9_-]{0,47}',name) or name in ids:
            stop('Audio IDs must be distinct safe strings')
        ids.add(name)
        file=read_file(original_scene.parent,item.get('file'))
        ext=file.suffix.lower()
        mime={'.mp3':'audio/mpeg','.ogg':'audio/ogg','.wav':'audio/wav'}
        if ext not in mime:stop('Supported audio source formats: mp3/ogg/wav (others need authored conversion)')
        payload=file.read_bytes()
        if len(payload)>8_000_000:stop('Single original audio file exceeds 8MB offline budget')
        total+=len(payload)
        if total>24_000_000:stop('Offline audio files exceed 24MB total mobile budget')
        if ext=='.ogg' and not payload.startswith(b'OggS'):stop('Audio .ogg header invalid')
        if ext=='.wav' and not (payload.startswith(b'RIFF') and payload[8:12]==b'WAVE'):
            stop('Audio .wav header invalid')
        if ext=='.mp3' and not (payload.startswith(b'ID3') or (len(payload)>2 and payload[0]==255 and payload[1]&224==224)):
            stop('Audio .mp3 header invalid')
        mode=item.get('mode','ambience')
        if mode not in ('ambience','world','actor'):
            stop('Sound mode must be ambience, world or actor')
        actor_id=item.get('actor_id')
        pos=item.get('position')
        if mode=='actor':
            if not isinstance(actor_id,str) or actor_id not in cast or pos is not None:
                stop('Actor sound must follow one verified actor, with no fixed position')
        elif mode=='world':
            if actor_id is not None or not isinstance(pos,list) or len(pos)!=2:
                stop('World sound requires authored [x,y], not an actor ID')
            pos=[scalar(pos[0],0,verified['width'],'world x'),
                 scalar(pos[1],0,verified['height'],'world y')]
        elif actor_id is not None or pos is not None:
            stop('Ambience must not have positional anchor')
        loop=item.get('loop',True)
        if type(loop) is not bool:stop('Sound loop must be boolean')
        direct_volume=scalar(item.get('volume',.5),0,1,'sound volume')
        refdist=scalar(item.get('ref_distance',1.5),.1,100,'ref_distance')
        maxdist=scalar(item.get('max_distance',30),refdist,500,'max_distance')
        rolloff=scalar(item.get('rolloff',1),0,5,'rolloff')
        if mode=='ambience' and any(k in item for k in ('ref_distance','max_distance','rolloff')):
            stop('Non-spatial ambience cannot configure distance attenuation')
        out.append({'id':name,'uri':'data:'+mime[ext]+';base64,'+base64.b64encode(payload).decode('ascii'),
            'format':ext[1:],'mode':mode,'actor':actor_id,'position':pos,
            'loop':loop,'volume':direct_volume,
            'ref_distance':refdist,'max_distance':maxdist,'rolloff':rolloff,
            'source_sha256':hashlib.sha256(payload).hexdigest()})
        assets.append(('project/audio/originals/'+name+ext,payload))
    return {'sounds':out,'pixel_scale':scale,'master_volume':volume,
        'listener':listener,'actor_count':len(verified['actors']),
        'total_original_audio_bytes':total},assets

RUNTIME=r'''    // Complete original artist-painted character frames remain untouched.
    // No audio starts before a real user gesture (mobile Safari, iOS/Android).
    const LIA_SOUNDS=__AUDIO_DATA__;
    if(typeof window.Howler!=='object'||typeof window.Howl!=='function'||
       typeof window.Howler.pos!=='function'||typeof window.Howl.prototype.pos!=='function')
      throw new Error('Official Howler.js spatial-enabled runtime did not initialize');
    const byActor=new Map(avatars.map(v=>[v.actor.id,v]));
    const ui=document.createElement('button');
    ui.type='button';ui.textContent='Звук: выкл';ui.setAttribute('aria-label','Включить или выключить звук');
    ui.style.cssText='position:fixed;z-index:9999;right:12px;top:12px;background:rgba(13,23,34,.82);color:#f0eee4;border:1px solid #647283;border-radius:8px;padding:10px 13px;font:14px system-ui;cursor:pointer';
    document.body.appendChild(ui);
    let on=false,ready=false;
    let audioItems=[];
    function actorPosition(id){
      const v=byActor.get(id);
      if(!v)throw new Error('Verified original sound anchor actor is missing');
      return [v.figure.x+v.actor.box[2]*.5,v.figure.y+v.actor.box[3]*.5];
    }
    function updateSpatial(){
      if(!ready)return;
      const listener=LIA_SOUNDS.listener==='camera'
        ? [world.center.x,world.center.y] : actorPosition(LIA_SOUNDS.listener);
      window.Howler.pos(listener[0]/LIA_SOUNDS.pixel_scale,
                        listener[1]/LIA_SOUNDS.pixel_scale,0);
      for(const entry of audioItems){
        if(entry.def.mode==='ambience')continue;
        const p=entry.def.mode==='actor'?actorPosition(entry.def.actor):entry.def.position;
        entry.howl.pos(p[0]/LIA_SOUNDS.pixel_scale,p[1]/LIA_SOUNDS.pixel_scale,0);
      }
    }
    function setupAudio(){
      audioItems=LIA_SOUNDS.sounds.map(def=>{
        const positional=def.mode!=='ambience';
        const opts={src:[def.uri],format:[def.format],autoplay:false,
          html5:false,loop:def.loop,volume:def.volume};
        if(positional)opts.pannerAttr={panningModel:'HRTF',distanceModel:'inverse',
          refDistance:def.ref_distance,maxDistance:def.max_distance,rolloffFactor:def.rolloff};
        return {def,howl:new window.Howl(opts)};
      });
      window.Howler.volume(LIA_SOUNDS.master_volume);
      ready=true;updateSpatial();
    }
    ui.addEventListener('click',async()=>{
      if(!ready)setupAudio();
      if(on){for(const x of audioItems)x.howl.pause();on=false;}
      else{
        // Browser audio autoplay policy: must start from this explicit click/tap.
        if(window.Howler.ctx && window.Howler.ctx.state==='suspended'){
          try{await window.Howler.ctx.resume();}catch(e){ui.textContent='Звук недоступен';return;}
        }
        updateSpatial();
        for(const x of audioItems)x.howl.play();
        on=true;
      }
      ui.textContent=on?'Звук: вкл':'Звук: выкл';
    });
    app.ticker.add(()=>{if(on)updateSpatial();});
    window.__livingAudio={engine:'Howler.js 2.2.4',count:LIA_SOUNDS.sounds.length,
       get active(){return on;},sourceOnly:true,actorFramesChanged:false};
'''

def insert_once(src,marker,value,label):
    if src.count(marker)!=1:stop('Upstream browser HTML incompatible at '+label)
    return src.replace(marker,value,1)

def make_html(upstream_html,output_html,approved_zip,scene_path,howler_js):
    audio,assets=audio_config(approved_zip,scene_path)
    _,bundle=howler_bundle(howler_js)
    html=Path(upstream_html).resolve().read_text('utf8')
    if (html.count('<script>const LIVING_SCENE=')!=1 or html.count('    const avatars=[];')!=1
        or 'window.pixi_viewport' not in html or 'const LIA_TILEMAP=' not in html):
        stop('Original verified PixiJS 8 + camera + tilemap player missing')
    if 'const LIA_SOUNDS=' in html:stop('Sound already injected')
    bundle=re.sub(r'</script',r'<\\/script',bundle,flags=re.I)
    html=insert_once(html,'<script>const LIVING_SCENE=',
        '<script>/*! Source: howler@2.2.4 MIT; bundled full spatial runtime. */\n'+bundle+
        '</script><script>const LIVING_SCENE=','howler bundled library')
    data=json.dumps(audio,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
    # Install after original per-frame pose update: sound follows the CURRENT frame.
    anchor="    document.addEventListener('visibilitychange',()=>{app.ticker.started=!document.hidden;});"
    if html.count(anchor)!=1:stop('Approved actor animation ticker marker changed; cannot anchor sound')
    html=insert_once(html,anchor,RUNTIME.replace('__AUDIO_DATA__',data)+'\n'+anchor,'original actor timeline')
    output_html=Path(output_html).resolve();output_html.parent.mkdir(parents=True,exist_ok=True)
    if len(html.encode('utf8'))>150*1024*1024:stop('Offline HTML exceeds 150MB original browser cap')
    temporary=output_html.with_name(output_html.name+'.tmp')
    temporary.write_text(html,'utf8');os.replace(temporary,output_html)
    hashes={x['id']:x['source_sha256'] for x in audio['sounds']}
    return output_html,assets,{'engine':'Howler.js 2.2.4 + genuine PixiJS 8',
      'source_audio_tracks':len(audio['sounds']),'original_source_sha256':hashes,
      'mobile_user_gesture_required':True,'offline':True,
      'original_sprite_frames_untouched':True,'html_sha256':hashlib.sha256(output_html.read_bytes()).hexdigest()}

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--upstream-html',type=Path,required=True)
    p.add_argument('--approved-zip',type=Path,required=True)
    p.add_argument('--scene',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--howler-js',type=Path,required=True)
    a=p.parse_args();print(json.dumps(make_html(a.upstream_html,a.out,a.approved_zip,a.scene,a.howler_js)[2],ensure_ascii=False))
