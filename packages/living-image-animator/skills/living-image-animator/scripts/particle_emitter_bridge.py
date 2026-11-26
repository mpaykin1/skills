#!/usr/bin/env python3
"""Official Pixi v8 particle emitter (1.0.2): original post-effect only.

Keeps verified original full-cel actor images, paths, identities and the entire
PixiJS Filters/viewport chain byte-for-byte. No character asset is generated.
"""
from __future__ import annotations
import argparse
import json
import math
import os
from pathlib import Path
import re
import zipfile
from PIL import Image

ENGINE='@spd789562/particle-emitter'
VERSION='1.0.2'

class ParticleBridgeError(ValueError):pass

def fail(msg):raise ParticleBridgeError('PixiJS particles stage blocked: '+str(msg))

def runtime_binary(path=None):
    target=path or os.environ.get('PIXI_V8_PARTICLE_EMITTER_BUNDLE') or Path(__file__).resolve().parent.parent/'vendor'/'pixi-particle-emitter.min.js'
    p=Path(target).expanduser().resolve()
    if not p.is_file():fail('Real PixiJS v8 particle-emitter bundle missing; use --fetch-particles or --particles-js')
    data=p.read_bytes()
    if not 6000<=len(data)<=4_000_000 or b'Emitter' not in data:
        fail('Unknown particle emitter artifact; expected genuine @spd789562/particle-emitter@1.0.2')
    try:text=data.decode('utf8')
    except UnicodeError:fail('Particle emitter browser bundle is not valid UTF-8')
    return p,text

def read_config(approved):
    approved=Path(approved).resolve()
    with zipfile.ZipFile(approved) as z:
        if z.testzip() is not None:fail('Approved original assets ZIP damaged')
        names=z.namelist()
        if len(names)!=len(set(names)):fail('Duplicate source ZIP paths')
        try:cfg=json.loads(z.read('scene.json'));motion=json.loads(z.read('motion_gate.json'))
        except (ValueError,KeyError) as e:fail('Original source scene/motion certification missing: '+str(e))
        try:
            with z.open('source.png') as stream, Image.open(stream) as im:
                canvas=im.size
        except (OSError,KeyError):fail('Approved original source.png image is required')
    if motion.get('all_actors_pass') is not True:fail('Original individual full-body pose validation not passed')
    actors=cfg.get('actors',[])
    ids=[a.get('id') for a in actors]
    if not ids or any(type(x) is not str or not x for x in ids) or len(ids)!=len(set(ids)) or set(ids)!=set(cfg.get('inventory',{}).get('actors',[])):
        fail('Original human/animal identity roster invalid')
    original=cfg.get('pixi',{})
    if not isinstance(original,dict):fail('pixi settings must be an object')
    requested=original.get('particles',[])
    if not isinstance(requested,list) or len(requested)>12:fail('pixi.particles needs an array (maximum 12 emitters)')
    valid=[]
    types={'snow','rain','embers','dust'}
    used=set();total=0
    for i,d in enumerate(requested):
        if not isinstance(d,dict) or set(d)-{'id','type','region','density','z_index','angle','tint','speed','scale'}:
            fail('Unknown particle source configuration at index '+str(i))
        kind=d.get('type')
        if kind not in types:fail('Unsupported ambient particle type: '+str(kind))
        name=d.get('id')
        if not isinstance(name,str) or not re.fullmatch('[a-zA-Z0-9_-]{1,48}',name) or name in used:fail('Particle system IDs must be distinct safe names')
        used.add(name)
        region=d.get('region')
        if not isinstance(region,list) or len(region)!=4 or any(type(n) not in (int,float) or not math.isfinite(n) for n in region):
            fail('Ambient particles need real source-canvas region [x,y,width,height]')
        x,y,w,h=region
        if x<0 or y<0 or w<=0 or h<=0 or x+w>canvas[0] or y+h>canvas[1]:fail('Particle region must fit original source image')
        count=d.get('density',50)
        if type(count) is not int or not 1<=count<=300:fail('density must be 1..300 particles')
        total+=count
        if total>900:fail('Total active GPU particles must be <=900 for mobile performance')
        speed=d.get('speed',30)
        if type(speed) not in (int,float) or not math.isfinite(speed) or not 2<=speed<=180:fail('Particle speed outside 2..180 px/s')
        tint=d.get('tint',{'snow':'#d5e7ed','rain':'#98b4cb','embers':'#ec9038','dust':'#d4c6a4'}[kind])
        if not isinstance(tint,str) or not re.fullmatch('#[0-9A-Fa-f]{6}',tint):fail('Particle tint must be literal hex #RRGGBB')
        angle=d.get('angle',{'snow':80,'rain':94,'embers':270,'dust':345}[kind])
        if type(angle) not in (float,int) or not math.isfinite(angle) or not -360<=angle<=360:fail('Particle drift angle invalid')
        z=d.get('z_index',65)
        if type(z) is not int or not -1000<=z<=1000:fail('z_index must be integer in -1000..1000')
        scale=d.get('scale',{'snow':1.3,'rain':0.8,'embers':1.4,'dust':1}[kind])
        if type(scale) not in (float,int) or not math.isfinite(scale) or not 0.25<=scale<=4:fail('Particle scale out of bounds')
        valid.append({'id':name,'type':kind,'region':[float(v) for v in region],
            'density':count,'speed':float(speed),'z_index':z,'angle':float(angle),
            'color':tint[1:],'scale':float(scale)})
    return valid

def replace_unique(source,marker,patch,label):
    count=source.count(marker)
    if count!=1:fail(f'Unexpected original filtered HTML at {label}: {count} anchors')
    return source.replace(marker,patch,1)


def create_html(filtered_html,output_html,approved_zip,js_file=None):
    """Extra bundled HTML, does not mutate original filters/atlas/physics output."""
    emitters=read_config(approved_zip)
    lib_path,bundle=runtime_binary(js_file)
    html=Path(filtered_html).resolve().read_text('utf8')
    if '<script>const LIVING_SCENE=' not in html or 'const avatars=[];' not in html or 'pixi_viewport' not in html:
        fail('Expected approved PixiJS Filters + viewport HTML, not an arbitrary page')
    bundle=re.sub(r'</script',r'<\\/script',bundle,flags=re.I)
    html=replace_unique(html,'<script>const LIVING_SCENE=',
        '<script>/* genuine @spd789562/particle-emitter 1.0.2 (MIT), original LICENSE in ZIP */\n'+bundle+'</script><script>const LIVING_SCENE=',
        'real particle engine injection')
    cfg=json.dumps(emitters,separators=(',',':'),ensure_ascii=False).replace('<','\\u003c')
    code=r'''
    // Real PixiJS v8 ParticleContainer + genuine open-source particle Emitter.
    // All effect nodes are isolated; actor atlas sprites are never filtered,
    // resampled, stretched or used as particle images.
    const LIA_PARTICLES=__CFG__;
    const EngineNS=(window.LIA_ParticleEmitter && window.LIA_ParticleEmitter.Emitter)
      ? window.LIA_ParticleEmitter : (window.PixiParticleEmitter && window.PixiParticleEmitter.Emitter)
      ? window.PixiParticleEmitter : (window.ParticleEmitter && window.ParticleEmitter.Emitter)
      ? window.ParticleEmitter : (window.pixi_particle_emitter && window.pixi_particle_emitter.Emitter)
      ? window.pixi_particle_emitter : (window.pixiParticles && window.pixiParticles.Emitter)
      ? window.pixiParticles : (window.PIXI && window.PIXI.particles && window.PIXI.particles.Emitter)
      ? window.PIXI.particles : null;
    if(LIA_PARTICLES.length && (!EngineNS || typeof EngineNS.Emitter!=='function'))
      throw new Error('Actual PixiJS v8 particle emitter UMD did not expose Emitter');
    const ambientEmitters=[];
    for(const fx of LIA_PARTICLES){
      if(!PIXI.ParticleContainer||!PIXI.Texture?.WHITE)throw new Error('PixiJS v8 GPU ParticleContainer unavailable');
      const group=new PIXI.ParticleContainer({dynamicProperties:{position:true,rotation:true,scale:true,color:true}});
      group.zIndex=fx.z_index;world.addChild(group);
      const [x,y,w,h]=fx.region;
      const life=fx.type==='rain' ? Math.max(.4,h/fx.speed): fx.type==='embers' ? 2.3 : Math.max(1,h/fx.speed);
      const alpha0=fx.type==='dust'?0.26:fx.type==='snow'?.68:fx.type==='rain'?.35:.8;
      const cfg={lifetime:{min:life*.7,max:life},frequency:Math.max(.035,life/fx.density),
         spawnChance:1,particlesPerWave:1,emitterLifetime:-1,maxParticles:fx.density,
         pos:{x:x,y:y},addAtBack:false,
         behaviors:[
          {type:'alpha',config:{alpha:{list:[{value:alpha0,time:0},{value:0,time:1}]}}},
          {type:'scale',config:{scale:{list:[{value:fx.scale,time:0},{value:fx.scale*.6,time:1}]}}},
          {type:'color',config:{color:{list:[{value:fx.color,time:0},{value:fx.color,time:1}]}}},
          {type:'moveSpeed',config:{speed:{list:[{value:fx.speed,time:0},{value:fx.speed*.7,time:1}]},isStepped:false}},
          {type:'rotationStatic',config:{min:fx.angle,max:fx.angle}},
          {type:'spawnShape',config:{type:'rect',data:{x:0,y:0,w:w,h:h*.15}}},
          {type:'textureSingle',config:{texture:PIXI.Texture.WHITE}}
         ]};
      const emitter=new EngineNS.Emitter(group,cfg);
      emitter.autoUpdate=true;emitter.emit=true;
      ambientEmitters.push({name:fx.id,system:emitter});
    }
    window.__livingParticles={engine:'@spd789562/particle-emitter@1.0.2',
      emitters:ambientEmitters.map(e=>e.name),environmentOnly:true};
'''.replace('__CFG__',cfg)
    html=replace_unique(html,'    const avatars=[];',code+'    const avatars=[];','source-preserving particles')
    if len(html.encode('utf8'))>150*1024*1024:fail('Fully offline browser output exceeds 150MiB limit')
    output_html=Path(output_html).resolve();output_html.parent.mkdir(parents=True,exist_ok=True)
    temp=output_html.with_suffix('.tmp');temp.write_text(html,'utf8');os.replace(temp,output_html)
    return output_html,{'particle_emitter':ENGINE+'@'+VERSION,'emitters':len(emitters),
        'active_particle_budget':sum(x['density'] for x in emitters),'original_png_unchanged':True,
        'runtime':str(lib_path),'offline_html':True,'html_bytes':output_html.stat().st_size}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--approved-zip',type=Path,required=True)
    p.add_argument('--filtered-html',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--particles-js',type=Path);a=p.parse_args()
    print(json.dumps(create_html(a.filtered_html,a.out,a.approved_zip,a.particles_js)[1],ensure_ascii=False))
