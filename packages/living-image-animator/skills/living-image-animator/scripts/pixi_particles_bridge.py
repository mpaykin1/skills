#!/usr/bin/env python3
"""Add real PixiJS 8 particle emitters ONLY to original verified 2.5D atmosphere.

Upstream actor full-pose validation, authored PNG bytes, PixiJS camera,
filters and separate Matter.js collision export remain untouched.
"""
from __future__ import annotations
import argparse, base64, hashlib, io, json, math, os, re, zipfile
from pathlib import Path
from PIL import Image
from pixijs_bridge import load_scene

class ParticleBridgeError(ValueError):pass

def stop(msg):raise ParticleBridgeError('PixiJS8 particle emitter blocked: '+msg)
def num(x,lo,hi,name):
    if type(x) not in (int,float) or not math.isfinite(x) or not lo<=x<=hi:
        stop(f'{name} must be within {lo}..{hi}')
    return float(x)

def runtime_bundle(path):
    if path is None:path=os.environ.get('LIA_PIXI_PARTICLES_BUNDLE')
    if not path:stop('Genuine PixiJS 8 particle IIFE missing: use --fetch-particles or --particles-js')
    path=Path(path).expanduser().resolve()
    if not path.is_file():stop('Particle JS runtime absent at '+str(path))
    data=path.read_bytes()
    if not 15000<=len(data)<=2_500_000 or b'LIA_Particles' not in data or b'Emitter' not in data:
        stop('Expected genuine pixi-v8-particles UMD/IIFE built with pixi_particles_vendor.py')
    try:code=data.decode('utf8')
    except UnicodeError:stop('Particles JS is not UTF-8')
    return path,code

def config_from_zip(approved_zip):
    # Builtin exporter validates motion_gate, every source frame, actor inventory.
    base=load_scene(approved_zip)
    with zipfile.ZipFile(approved_zip) as z:
        if z.testzip() is not None:stop('Original approved animation ZIP is corrupt')
        cfg=json.loads(z.read('scene.json'))
        if json.loads(z.read('motion_gate.json')).get('all_actors_pass') is not True:
            stop('Upstream complete character animation gate failed')
        pixi=cfg.get('pixi',{})
        if not isinstance(pixi,dict):stop('pixi configuration must be an object')
        raw=pixi.get('emitters',[])
        if not isinstance(raw,list) or len(raw)>12:stop('pixi.emitters must be array of up to 12 effect emitters')
        if not raw and pixi.get('weather') in ('snow','rain'):
            raw=[{'id':'weather_'+pixi['weather'],'kind':pixi['weather']}]
        cast={a['id'] for a in base['actors']}
        forbidden={f.get('png') for a in cfg.get('actors',[]) for c in a.get('clips',[]) for f in c.get('frames',[])}
        kinds={'snow','rain','smoke','embers','sparks','dust'}
        defaults={
            'snow':('#dcecf8',0.70,5.5,56,1.5,0,90),
            'rain':('#9ec4dc',0.52,1.5,300,1.0,0,82),
            'smoke':('#89969f',0.28,3.5,32,8.0,0,268),
            'embers':('#ff9c41',0.92,1.6,85,2.7,0,275),
            'sparks':('#ffe7a5',0.96,.8,160,2.0,0,270),
            'dust':('#b8a28b',0.45,2.0,20,3.0,0,235),
        }
        out=[];ids=set(); total=0;ambient_assets={}
        for ent in raw:
            if not isinstance(ent,dict) or set(ent)-{'id','kind','position','zone','space','max_particles','rate','lifetime','speed','size','color','alpha','angle','z','attach_actor','particle_png'}:
                stop('Unsupported particle declaration; only bounded environmental effects are supported')
            aid=ent.get('id');kind=ent.get('kind')
            if not isinstance(aid,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}',aid) or aid in ids:
                stop('Duplicate/unsafe particle emitter ID')
            ids.add(aid)
            if kind not in kinds:stop('Unknown environmental emitter kind '+str(kind))
            color,alpha,life,speed,size,_,angle=defaults[kind]
            source_space=ent.get('space','world')
            if source_space not in ('world','screen'):stop('Particle space must be world or screen')
            follow=ent.get('attach_actor')
            if follow is not None and (follow not in cast or source_space!='world'):
                stop('Particle attachment must follow one real approved world-space actor')
            W,H=base['width'],base['height']
            default_zone=([0,-10,W,15] if kind in ('snow','rain') else [-10,-8,20,16])
            zone=ent.get('zone',default_zone)
            if not isinstance(zone,list) or len(zone)!=4:stop('Particle spawn zone must be [x,y,w,h]')
            zx,zy,zw,zh=[num(v,-max(W,H),max(W,H)*2,'zone') for v in zone]
            if not 0<zw<=W*2 or not 0<zh<=H*2:stop('Particle zone dimensions invalid')
            pos=ent.get('position', [0,0] if kind in ('snow','rain') else [W/2,H/2])
            if not isinstance(pos,list) or len(pos)!=2:stop('Particle position must be [x,y]')
            px=num(pos[0],0,W,'position x');py=num(pos[1],0,H,'position y')
            rate=num(ent.get('rate',13 if kind=='snow' else 65 if kind=='rain' else 12),.2,120,'rate')
            count=int(num(ent.get('max_particles',min(250,int(rate*life*1.5))),1,350,'max_particles'))
            total+=count
            if total>1200:stop('Mobile particle budget exceeded: max 1200 total')
            lifetime=num(ent.get('lifetime',life),.2,10,'lifetime')
            velocity=num(ent.get('speed',speed),0,700,'speed')
            radius=num(ent.get('size',size),.4,16,'size')
            opacity=num(ent.get('alpha',alpha),.04,1,'alpha')
            deg=num(ent.get('angle',angle),-720,720,'angle')
            z=int(num(ent.get('z',9000 if kind in ('snow','rain') else 50),-9500,9500,'z'))
            tint=ent.get('color',color)
            if not isinstance(tint,str) or not re.fullmatch('#[0-9a-fA-F]{6}',tint):stop('Particle color must be #RRGGBB')
            texture=None
            rel=ent.get('particle_png')
            if rel is not None:
                if not isinstance(rel,str) or not rel or rel.startswith('/') or '\\' in rel or ':' in rel or '..' in rel.split('/'):
                    stop('Particle source PNG must be a safe author-provided project path')
                if rel in forbidden:stop('A character pose PNG cannot be reused as an environmental particle')
                member='project/inputs/'+rel
                if member not in z.namelist():stop('Particle PNG missing from verified original input archive: '+rel)
                rawpng=z.read(member)
                if len(rawpng)>300_000:stop('Particle texture exceeds 300kB budget')
                with Image.open(io.BytesIO(rawpng)) as im:
                    if im.format!='PNG' or im.width>128 or im.height>128 or min(im.size)<1:
                        stop('Environmental particle must use transparent PNG <=128x128')
                    lo,hi=im.convert('RGBA').getchannel('A').getextrema()
                    if lo==255 or hi==0:stop('Environmental particle PNG needs an alpha silhouette')
                texture='data:image/png;base64,'+base64.b64encode(rawpng).decode('ascii')
                ambient_assets[rel]=hashlib.sha256(rawpng).hexdigest()
            out.append({'id':aid,'kind':kind,'space':source_space,'position':[px,py],
                        'zone':[zx,zy,zw,zh], 'rate':rate,'max':count,'lifetime':lifetime,
                        'speed':velocity,'size':radius,'alpha':opacity,'angle':deg,
                        'color':tint,'z':z,'follow':follow,'texture':texture})
        return {'emitters':out,'overrides_builtin_weather':any(e['kind'] in ('rain','snow') for e in out),
                'W':base['width'],'H':base['height'],'source_png_sha256':ambient_assets,
                'approved_cast':len(cast),'source_animation_certified':True}

def patch_html(filtered_html,out_html,approved_zip,particle_js):
    fx=config_from_zip(approved_zip)
    _,code=runtime_bundle(particle_js)
    src=Path(filtered_html).read_text('utf8')
    marker='<script>const LIVING_SCENE='
    if src.count(marker)!=1 or src.count('    const avatars=[];')!=1 or 'pixi_viewport' not in src or 'LIA_FILTERS' not in src:
        stop('Previous PixiJS v8 + pixi-viewport + pixi-filters offline output is required')
    lib=re.sub(r'</script',r'<\\/script',code,flags=re.I)
    src=src.replace(marker,'<script>/* pixi-v8-particles 0.1.3; MIT attribution in ZIP */\n'+lib+'</script>'+marker,1)
    settings=json.dumps(fx,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
    runtime=r'''    // Real PixiJS 8 particle emitter. Atmosphere only; original cel pixels untouched.
    const LIA_PARTICLES=__SETTINGS__;
    if(!window.LIA_Particles || !window.LIA_Particles.Emitter || !window.LIA_Particles.registerAllBehaviors)
      throw new Error('Real pixi-v8-particles runtime is unavailable');
    window.LIA_Particles.registerAllBehaviors();
    app.stage.sortableChildren=true;
    const installedEmitters=[];
    for(const def of LIA_PARTICLES.emitters){
      const holder=new PIXI.Container();holder.zIndex=def.z;
      (def.space==='screen'?app.stage:world).addChild(holder);
      if((def.kind==='embers'||def.kind==='sparks')&&Fx && Fx.GlowFilter){
        holder.filters=[new Fx.GlowFilter({distance:3,outerStrength:.8,innerStrength:0,
          color:0xff9f45,alpha:.65,quality:.08})];
      }
      let tex=PIXI.Texture.WHITE;
      if(def.texture) tex=await PIXI.Assets.load(def.texture);
      const behavior=[
       {type:'alpha',config:{alpha:{list:[{time:0,value:0},{time:.18,value:def.alpha},{time:.7,value:def.alpha},{time:1,value:0}]}}},
       {type:'scaleStatic',config:{min:Math.max(.2,def.size*.65),max:def.size}},
       {type:'colorStatic',config:{color:def.color}},
       {type:'moveSpeedStatic',config:{min:Math.max(0,def.speed*.8),max:Math.max(.01,def.speed*1.2)}},
       {type:'rotationStatic',config:{min:def.angle-10,max:def.angle+10}},
       {type:'textureSingle',config:{texture:tex}},
       {type:'spawnShape',config:{type:'rect',data:{x:def.zone[0],y:def.zone[1],w:def.zone[2],h:def.zone[3]}}}
      ];
      const config={lifetime:{min:Math.max(.1,def.lifetime*.8),max:def.lifetime},
        frequency:1/def.rate,particlesPerWave:1,spawnChance:1,emitterLifetime:-1,
        maxParticles:def.max,addAtBack:false,pos:{x:0,y:0},emit:true,autoUpdate:false,behaviors:behavior};
      const emitter=new window.LIA_Particles.Emitter(holder,config);
      installedEmitters.push({emitter,def});
    }
    app.ticker.add(t=>{
      const dt=Math.max(0,Math.min(.05,t.deltaMS/1000));
      for(const active of installedEmitters){
        const def=active.def;let x=def.position[0],y=def.position[1];
        if(def.follow){
          const ref=avatars.find(a=>a.actor.id===def.follow);
          if(!ref)throw new Error('Authentic source actor missing for particle anchor');
          x=ref.figure.x+ref.actor.box[2]*.5;
          y=ref.figure.y+ref.actor.box[3]*.5;
        }else if(def.space==='screen'){
          x=x/LIA_PARTICLES.W*app.renderer.screen.width;
          y=y/LIA_PARTICLES.H*app.renderer.screen.height;
        }
        active.emitter.updateOwnerPos(x,y);
        active.emitter.update(dt);
      }
    });
    window.__livingParticles={engine:'pixi-v8-particles',emitters:installedEmitters.length,
       totalBudget:installedEmitters.reduce((n,e)=>n+e.def.max,0),charactersModified:0};
'''.replace('__SETTINGS__',settings)
    src=src.replace('    const avatars=[];',runtime+'    const avatars=[];',1)
    if fx['overrides_builtin_weather']:
        old="if (S.weather === 'snow' || S.weather === 'rain') {"
        if src.count(old)!=1:stop('Original weather shader marker missing; cannot avoid doubled weather')
        src=src.replace(old,"if (!LIA_PARTICLES.overrides_builtin_weather && (S.weather === 'snow' || S.weather === 'rain')) {",1)
    dest=Path(out_html).resolve();dest.parent.mkdir(parents=True,exist_ok=True)
    if len(src.encode('utf8'))>150*1024*1024:stop('Standalone browser artifact >150MiB')
    tmp=dest.with_suffix('.tmp');tmp.write_text(src,encoding='utf8');os.replace(tmp,dest)
    return dest,{'emitter_count':len(fx['emitters']),'total_particle_limit':sum(e['max'] for e in fx['emitters']),
                 'engine':'pixi-v8-particles 0.1.3 with genuine PixiJS 8',
                 'source_actor_count':fx['approved_cast'],'original_character_pngs_modified':False,
                 'source_particle_images':fx['source_png_sha256'],'offline':True,
                 'sha256':hashlib.sha256(dest.read_bytes()).hexdigest()}

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--approved-zip',required=True,type=Path)
    ap.add_argument('--filters-html',required=True,type=Path);ap.add_argument('--out',required=True,type=Path)
    ap.add_argument('--particles-js',type=Path);a=ap.parse_args()
    print(json.dumps(patch_html(a.filters_html,a.out,a.approved_zip,a.particles_js)[1],ensure_ascii=False))
