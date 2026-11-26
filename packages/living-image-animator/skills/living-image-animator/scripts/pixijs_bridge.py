#!/usr/bin/env python3
"""Verified full-cel 2D/2.5D scene -> *offline* PixiJS v8 single HTML.

All subject imagery comes byte-for-byte from an already accepted pose ZIP.
Native frame pixels are neither re-generated nor interpolated; only whole
actor root placement follows the exact authored world-space route.
"""
from __future__ import annotations
import argparse
import base64
import io
import json
import math
import os
from pathlib import Path
import re
import shutil
import zipfile
from PIL import Image
from pathfinding_bridge import prepare as prepare_pathfinding
from pathfinding_vendor import locate as locate_pathfinding

class PixiBridgeError(ValueError): pass

def reject(msg):raise PixiBridgeError('PixiJS bridge blocked: '+str(msg))

def safe_member(relative):
    if not isinstance(relative,str) or not relative or '\\' in relative or ':' in relative or relative.startswith('/'):
        reject('Unsafe sprite path')
    if any(x in ('','.','..') for x in relative.split('/')):reject('Asset path traversal')
    return relative

def read_png(z,name,size=None,transparent=False):
    name=safe_member(name)
    try:raw=z.read(name)
    except KeyError:reject('Missing approved PNG '+name)
    if len(raw)>15_000_000:reject('Oversized PNG '+name)
    try:
        with Image.open(io.BytesIO(raw)) as im:
            if im.format!='PNG':reject('Asset must be PNG: '+name)
            if size and im.size!=tuple(size):reject('Wrong source canvas size: '+name)
            if transparent:
                if im.mode not in ('RGBA','LA','P'):
                    reject('Authored pose is not an alpha PNG: '+name)
                a=im.convert('RGBA').getchannel('A')
                low,high=a.getextrema()
                if low==255 or high==0:reject('Pose lacks actual silhouette transparency: '+name)
            dims=im.size
    except (OSError,ValueError) as e:reject('Unreadable real PNG '+name+': '+str(e))
    return 'data:image/png;base64,'+base64.b64encode(raw).decode('ascii'),dims

def json_inline(v):
    return json.dumps(v,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c').replace('\u2028','\\u2028').replace('\u2029','\\u2029')

def load_scene(verified_zip):
    verified_zip=Path(verified_zip).resolve()
    if not verified_zip.is_file():reject('Validated source ZIP absent')
    with zipfile.ZipFile(verified_zip) as z:
        if z.testzip() is not None:reject('Corrupted upstream pose ZIP')
        names=z.namelist()
        if len(names)!=len(set(names)):reject('Duplicate upstream ZIP members')
        try:
            cfg=json.loads(z.read('scene.json'))
            gate=json.loads(z.read('motion_gate.json'))
        except (KeyError,ValueError) as e:reject('Original motion certification missing: '+str(e))
        if gate.get('all_actors_pass') is not True:reject('Upstream full-pose gate not certified')
        if cfg.get('version')!=3 or cfg.get('mode')!='full-frame-pose-sprites':
            reject('Expected approved independent full-pose scene, not deformable rigs')
        actors=cfg.get('actors',[]);inv=cfg.get('inventory',{}).get('actors',[])
        ids=[a.get('id') for a in actors]
        if not actors or any(not isinstance(x,str) or not x for x in ids) or len(set(ids))!=len(ids) or set(ids)!=set(inv) or len(inv)!=len(ids):
            reject('Character inventory not authentic or complete')
        background,(w,h)=read_png(z,'background_clean.png')
        _, original_size=read_png(z,'source.png')
        if original_size!=(w,h):reject('Original background not source registered')
        sprite_data={}
        sprite_sizes={}
        converted=[]
        for actor in actors:
            aid=actor['id'];box=actor.get('box')
            if not isinstance(box,list) or len(box)!=4 or any(type(x)!=int for x in box):reject('Invalid source sprite box '+aid)
            x,y,bw,bh=box
            if min(bw,bh)<8 or x<0 or y<0 or x+bw>w or y+bh>h:reject('Actor outside source image '+aid)
            if len(actor.get('clips',[]))<2:reject('Missing individual animated actions '+aid)
            clips=[];textures=[];uniqs=set();total=0
            for clip in actor['clips']:
                action=clip.get('action');frames=clip.get('frames')
                if not isinstance(action,str) or not isinstance(frames,list) or len(frames)<12:
                    reject('Incomplete authored action '+aid)
                clip_paths=[]
                for frame in frames:
                    if not isinstance(frame,dict):reject('Unannotated frame '+aid)
                    rel=safe_member(frame.get('png'))
                    member='project/inputs/'+rel
                    if rel not in sprite_data:
                        png,_=read_png(z,member,(bw,bh),True)
                        sprite_data[rel]=png
                        sprite_sizes[rel]=(bw,bh)
                    elif sprite_sizes[rel]!=(bw,bh):reject("Sprite PNG reused with incompatible actor bounds")
                    clip_paths.append(rel)
                    uniqs.add(rel);total+=1
                clips.append({'action':action,'frames':clip_paths})
            if total<24 or len(uniqs)<16:reject('Frozen character '+aid)
            phase=actor.get('phase_frames',0)
            if type(phase)!=int or not 0<=phase<total:reject('Invalid actor phase '+aid)
            loc=actor.get('locomotion')
            if loc is not None:
                if not isinstance(loc,dict) or loc.get('mode') not in ('walk','run','stairs_up','stairs_down'):
                    reject('Unverified world locomotion mode '+aid)
                keys=loc.get('path')
                if not isinstance(keys,list) or len(keys)<3 or keys[0].get('frame')!=0 or keys[-1].get('frame')!=total:
                    reject('Actor trajectory is not a full cycle '+aid)
                last=-1
                for k in keys:
                    if type(k.get('frame'))!=int or k['frame']<=last or not all(type(k.get(s)) in (int,float) and math.isfinite(k[s]) for s in ('dx','dy')):
                        reject('Invalid world path keyframe '+aid)
                    last=k['frame']
                if math.dist((keys[0]['dx'],keys[0]['dy']),(keys[-1]['dx'],keys[-1]['dy']))>1:
                    reject('Trajectory not loopable '+aid)
            converted.append({'id':aid,'box':box,'phase':phase,'z':int(actor.get('z',20)),
                              'frames':[f for c in clips for f in c['frames']],
                              'actions':[c['action'] for c in clips for _ in c['frames']],
                              'locomotion':loc})
        layers=[];planes={}
        for layer in cfg.get('godot',{}).get('layers',[]):
            if not isinstance(layer,dict) or 'png' not in layer or 'z_index' not in layer:reject('Invalid registered 2.5D plane')
            rel=safe_member(layer['png']);zidx=layer['z_index']
            if type(zidx) not in (int,float) or not math.isfinite(zidx):reject('Invalid plane depth')
            if rel not in planes:
                png,_=read_png(z,'project/inputs/'+rel,(w,h),True)
                planes[rel]=png
            layers.append({'png':rel,'z':float(zidx)})
        # Blender can add unique planes; no duplicate compositing of same image.
        for layer in cfg.get('blender',{}).get('layers',[]):
            if not isinstance(layer,dict) or 'png' not in layer or 'z_index' not in layer:continue
            rel=safe_member(layer['png'])
            if any(x['png']==rel for x in layers):continue
            zidx=layer['z_index']
            if type(zidx) not in (int,float) or not math.isfinite(zidx):reject('Invalid Blender plane depth')
            if rel not in planes:
                png,_=read_png(z,'project/inputs/'+rel,(w,h),True)
                planes[rel]=png
            layers.append({'png':rel,'z':float(zidx)})
    if len(sprite_data)>25000:reject('Too many unique sprite frames for HTML playback')
    browser_nav=prepare_pathfinding(cfg,converted,w,h)
    return {'width':w,'height':h,'background':background,'actors':converted,
            'spriteData':sprite_data,'planes':planes,'layers':layers,'fps':24,
            'source':'approved full-cel PNGs', 'deformation':False,'browserNavigation':browser_nav}

def bundle_path(explicit=None):
    raw=explicit or os.environ.get('PIXIJS_BUNDLE')
    candidates=[raw] if raw else [str(Path(__file__).parent.parent/'vendor'/'pixi.min.js')]
    for cand in candidates:
        if not cand:continue
        p=Path(cand).expanduser().resolve()
        if p.is_file():
            rawbytes=p.read_bytes()
            if not 50000<=len(rawbytes)<=8_000_000 or b'Pixi' not in rawbytes[:30000]:
                reject('Unrecognized PixiJS v8 distribution; use official npm pixi.js@8.23.0')
            return p,rawbytes.decode('utf8')
    reject('Real PixiJS v8 bundle missing. Run pixijs_vendor.py --out vendor/pixi.min.js (needs npm/network), or provide --pixi-js /path/to/pixi.min.js. Never use a CDN in autonomous HTML.')

APP_JS=r'''(async function() {
'use strict';
const cfg = JSON.parse(document.getElementById('lia-scene').textContent);
if (!window.PIXI || !PIXI.Application) throw new Error('Real PixiJS runtime is unavailable');
const app=new PIXI.Application();
await app.init({width:cfg.width,height:cfg.height,backgroundAlpha:0,antialias:false,resolution:1,autoDensity:false,preference:'webgl'});
const viewport=document.getElementById('viewport');
viewport.appendChild(app.canvas);
app.canvas.setAttribute('aria-label','Living 2D animated world');
app.stage.sortableChildren=true;
app.stage.eventMode='static';
const textureCache=new Map();
async function texture(data){
  if(textureCache.has(data)) return textureCache.get(data);
  const img=new Image();
  const ready=new Promise((resolve,reject)=>{img.onload=()=>resolve(img);img.onerror=()=>reject(new Error('PNG decode failed'));});
  img.src=data;
  await ready;
  const tx=PIXI.Texture.from(img);
  tx.source.scaleMode='nearest';
  textureCache.set(data,tx);
  return tx;
}
function scaleViewport(){
 const sw=window.innerWidth, sh=window.innerHeight;
 const k=Math.min(sw/cfg.width,sh/cfg.height);
 app.canvas.style.width=Math.max(1,Math.floor(cfg.width*k))+'px';
 app.canvas.style.height=Math.max(1,Math.floor(cfg.height*k))+'px';
}
window.addEventListener('resize',scaleViewport,{passive:true});scaleViewport();
const bg=new PIXI.Sprite(await texture(cfg.background));bg.zIndex=-10000;app.stage.addChild(bg);
for(const layer of cfg.layers){const plane=new PIXI.Sprite(await texture(cfg.planes[layer.png]));plane.zIndex=layer.z;app.stage.addChild(plane);}
const navConfig=cfg.browserNavigation;
if(navConfig && (!window.PF || !PF.Grid || !PF.AStarFinder || !PF.DiagonalMovement))
  throw new Error('Authentic PathFinding.js A* runtime is unavailable');
const actors=[];
for(const a of cfg.actors){
 const node=new PIXI.Container();node.zIndex=a.z;app.stage.addChild(node);
 const visual=new PIXI.Sprite();node.addChild(visual);
 const textures=[];
 for(const name of a.frames) textures.push(await texture(cfg.spriteData[name]));
 actors.push({info:a,node,visual,textures,last:-1,
   navigation:null,movingFrames:[],restFrames:[]});
}
function sample(keys,frame){
 if(frame<=keys[0].frame)return [keys[0].dx,keys[0].dy];
 if(frame>=keys[keys.length-1].frame){const k=keys[keys.length-1];return [k.dx,k.dy];}
 for(let i=0;i<keys.length-1;i++){
   const a=keys[i],b=keys[i+1];
   if(frame>=a.frame && frame<=b.frame){
     let t=(frame-a.frame)/(b.frame-a.frame);t=t*t*(3-2*t);
     return [a.dx+(b.dx-a.dx)*t,a.dy+(b.dy-a.dy)*t];
   }
 }
 return [0,0];
}
// Real A* grid navigation from authored Tiled/LDtk/Godot geometry.
// No procedural character imagery, limb transforms, or camera-based motion.
function buildRoute(actor, point){
 const n=actor.navigation, grid=new PF.Grid(n.config.width,n.config.height,n.config.matrix);
 const toCell=(p)=>[Math.min(n.config.width-1,Math.max(0,Math.floor(p[0]/n.config.cell_px))),
                     Math.min(n.config.height-1,Math.max(0,Math.floor(p[1]/n.config.cell_px)))];
 const [sx,sy]=toCell(n.position),[tx,ty]=toCell(point);
 const finder=new PF.AStarFinder({diagonalMovement:PF.DiagonalMovement.Never});
 const cells=finder.findPath(sx,sy,tx,ty,grid);
 if(!cells.length)throw new Error('A* route is blocked for '+actor.info.id);
 const route=cells.slice(1).map(p=>[(p[0]+0.5)*n.config.cell_px,(p[1]+0.5)*n.config.cell_px]);
 route.push(point.slice());
 n.route=route;
}
for(const actor of actors){
 const conf=navConfig?.actors?.[actor.info.id];
 if(!conf)continue;
 actor.movingFrames=actor.info.actions.flatMap((s,i)=>s===conf.moving_action?[i]:[]);
 actor.restFrames=actor.info.actions.flatMap((s,i)=>
   !['walk','run','stairs_up','stairs_down'].includes(s)?[i]:[]);
 if(actor.movingFrames.length<12||actor.restFrames.length<12)
   throw new Error('Missing approved moving/rest pose sequences for '+actor.info.id);
 actor.navigation={config:conf, position:[actor.info.box[0],actor.info.box[1]],route:[],
                   nextTarget:0,moving:false,progress:0};
 buildRoute(actor, conf.waypoints[0]);
}
function moveNPC(actor,dt){
 const n=actor.navigation;
 if(!n)return;
 let budget=Math.min(dt,0.05)*n.config.speed_px_s;
 let travel=0, iterations=0;
 while(budget>0.001 && iterations++<32){
   if(!n.route.length){
     n.nextTarget=(n.nextTarget+1)%n.config.waypoints.length;
     buildRoute(actor,n.config.waypoints[n.nextTarget]);
     if(!n.route.length)break;
   }
   const to=n.route[0];const dx=to[0]-n.position[0],dy=to[1]-n.position[1];
   const distance=Math.hypot(dx,dy);
   if(distance<0.001){n.route.shift();continue;}
   const amount=Math.min(distance,budget);
   n.position[0]+=dx/distance*amount;n.position[1]+=dy/distance*amount;
   travel+=amount;budget-=amount;
   if(amount>=distance-0.001)n.route.shift();
 }
 n.moving=travel>0.001;
}
let elapsed=0, paused=false;
function update(dt=0){
 for(const a of actors){
  const info=a.info;
  let f=(Math.floor(elapsed*cfg.fps)+info.phase)%a.textures.length;
  if(a.navigation){
    moveNPC(a,dt);
    const selection=a.navigation.moving?a.movingFrames:a.restFrames;
    f=selection[Math.floor(elapsed*cfg.fps)%selection.length];
    a.node.position.set(a.navigation.position[0],a.navigation.position[1]);
  } else {
    const d=info.locomotion ? sample(info.locomotion.path,f):[0,0];
    a.node.position.set(info.box[0]+d[0],info.box[1]+d[1]);
  }
  if(f!==a.last){a.visual.texture=a.textures[f];a.last=f;}
 }
}
update();
app.ticker.add(t=>{if(!paused){const dt=Math.min(t.deltaMS,50)/1000;elapsed+=dt;update(dt);}});
app.canvas.addEventListener('pointerdown',()=>{paused=!paused;document.body.classList.toggle('paused',paused);});
window.__livingWorld={pause:()=>{paused=true;},play:()=>{paused=false;},actors:actors.map(a=>a.info.id)};
})().catch(e=>{const err=document.getElementById('error');err.textContent='Animation cannot start: '+e.message;err.style.display='block';console.error(e);});'''

PIXILICENSE='The MIT License\n\nCopyright (c) 2013-2023 Mathew Groves, Chad Engler\n\nPermission is hereby granted, free of charge, to any person obtaining a copy\nof this software and associated documentation files (the "Software"), to deal\nin the Software without restriction, including without limitation the rights\nto use, copy, modify, merge, publish, distribute, sublicense, and/or sell\ncopies of the Software, and to permit persons to whom the Software is\nfurnished to do so, subject to the following conditions:\n\nThe above copyright notice and this permission notice shall be included in\nall copies or substantial portions of the Software.\n\nTHE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR\nIMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,\nFITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE\nAUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER\nLIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,\nOUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN\nTHE SOFTWARE.'

def build_html(verified_zip,out,pixi_js=None,max_html_mib=150,pathfinding_js=None):
    scene=load_scene(verified_zip)
    engine,code=bundle_path(pixi_js)
    if not ('PIXI' in code or 'Pixi' in code):reject('PixiJS distribution missing API')
    # Avoid accidental HTML/script element termination in all inline script blocks.
    code=re.sub(r'</script',r'<\/script',code,flags=re.I)
    path_code=''
    if scene['browserNavigation']:
        pf_path,pf_js=locate_pathfinding(pathfinding_js)
        path_code=re.sub(r'</script',r'<\/script',pf_js,flags=re.I)
    html='<!--\nPixiJS open-source browser engine\n'+PIXILICENSE+'\n-->\n' + '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no"><title>Living Image Animator | PixiJS 2.5D</title><style>html,body{margin:0;height:100%;overflow:hidden;background:#090d19;color:#e2e7f7;font-family:system-ui}#viewport{width:100%;height:100%;display:flex;align-items:center;justify-content:center}canvas{display:block;image-rendering:pixelated;touch-action:manipulation}#error{display:none;position:absolute;left:12px;bottom:12px;background:#380e19;color:white;max-width:90%;padding:12px;border-radius:5px;z-index:10}</style></head><body><div id="viewport"></div><div id="error" role="alert"></div><script>''' + code + '''</script><script>''' + path_code + '''</script><script id="lia-scene" type="application/json">''' + json_inline(scene) + '''</script><script>''' + APP_JS.replace('</script','<\\/script') + '''</script></body></html>'''
    encoded=html.encode('utf8')
    if len(encoded)>max_html_mib*1024*1024:reject('Verified scene too large for safe one-file HTML; reduce PNG frame sizes without changing cels')
    out=Path(out).resolve();out.parent.mkdir(parents=True,exist_ok=True)
    tmp=out.with_suffix('.tmp');tmp.write_bytes(encoded);os.replace(tmp,out)
    return out,{'actors':len(scene['actors']),'unique_pose_pngs':len(scene['spriteData']),
                'engine':'PixiJS 8.23.0 supplied from local genuine distribution','single_html':True,
                'bytes':len(encoded),'no_deformation':True,
                'pathfinding':'PathFinding.js A* 0.4.18' if scene['browserNavigation'] else None,
                'navigated_actors':len(scene['browserNavigation']['actors']) if scene['browserNavigation'] else 0}

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--approved-zip',required=True,type=Path)
    p.add_argument('--out',required=True,type=Path)
    p.add_argument('--pixi-js',type=Path)
    p.add_argument('--pathfinding-js',type=Path)
    a=p.parse_args()
    print(json.dumps(build_html(a.approved_zip,a.out,a.pixi_js,pathfinding_js=a.pathfinding_js)[1],ensure_ascii=False))
