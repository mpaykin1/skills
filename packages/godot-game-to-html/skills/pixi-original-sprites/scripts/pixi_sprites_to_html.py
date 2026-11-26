#!/usr/bin/env python3
"""Pack original UnityPy/Godot 2D assets into a single PixiJS HTML visual scene.

Uses the official PixiJS 8.23.0 browser bundle installed locally. Offline at runtime;
no auto-created gameplay, synthesized sprites or image deformation.
"""
from __future__ import annotations
import argparse
import base64
import json
import mimetypes
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

PIN='8.23.0'
SUFFIX={'.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.webp':'image/webp','.gif':'image/gif'}
LAYER={'background':0,'midground':10000,'foreground':20000,'screen':30000}

HTML='''<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no"><title>__TITLE__</title>
<style>html,body{margin:0;width:100%;height:100%;overflow:hidden;background:__COLOR__;touch-action:none}canvas{display:block}#status{position:fixed;left:12px;top:12px;color:#eef3f6;background:#141820cc;padding:8px 12px;border-radius:8px;font:13px system-ui;z-index:20;display:none}#toolbar{position:fixed;right:12px;bottom:12px;display:none;z-index:20;gap:8px}button{border:1px solid #aaa6;background:#1c2235cc;color:#fff;padding:8px 16px;border-radius:9px;font:14px system-ui}</style></head>
<body><div id="status"></div><div id="toolbar"><button id="prev">◀</button><button id="page"></button><button id="next">▶</button></div>
<script>__PIXI_BUNDLE__</script><script>
const SCENE=JSON.parse(new TextDecoder().decode(Uint8Array.from(atob('__SCENE_B64__'),c=>c.charCodeAt(0))));
const LAYER={background:0,midground:10000,foreground:20000,screen:30000};
(async()=>{const status=document.getElementById('status');function error(e){status.textContent='PixiJS: '+String(e);status.style.display='block'}
try{
if(!globalThis.PIXI)throw Error('PixiJS runtime was not loaded');
const p=globalThis.PIXI;
const app=new p.Application();await app.init({resizeTo:window,background:SCENE.background||'#0b1220',antialias:SCENE.antialias!==false,resolution:Math.min(devicePixelRatio||1,2),preference:'webgl'});
document.body.appendChild(app.canvas);
const root=new p.Container();root.sortableChildren=true;app.stage.addChild(root);
const textures=new Map();
async function texture(key){if(textures.has(key))return textures.get(key);const img=new Image();img.src=SCENE.resources[key];if(!img.src)throw Error('Missing image '+key);await img.decode();const t=p.Texture.from(img);if(SCENE.pixelArt)t.source.scaleMode='nearest';textures.set(key,t);return t;}
let pages=[];const catalog=SCENE.mode==='catalog';
if(catalog){const n=SCENE.sprites.length;const count=30;for(let j=0;j<n;j+=count)pages.push(SCENE.sprites.slice(j,j+count));}else pages=[SCENE.sprites];
let current=0,objects=[];const pointer={x:0,y:0};
async function showPage(index){current=index;for(const entry of objects){root.removeChild(entry.view);entry.view.destroy({children:true});}objects=[];
const specs=pages[index]||[];let order=0;
for(const spec of specs){const frames=[];for(const key of spec.frames){frames.push(await texture(key));}
if(!frames.length)continue;
const view=frames.length>1?new p.AnimatedSprite(frames):new p.Sprite(frames[0]);
view.anchor.set(spec.anchor[0],spec.anchor[1]);view.alpha=spec.alpha;view.rotation=spec.rotation;view.zIndex=(LAYER[spec.layer]||0)+(spec.z||0)+order/100000;
view.x=spec.x;view.y=spec.y;
const fit=spec.maxDimension>0?Math.min(1,spec.maxDimension/Math.max(frames[0].width,frames[0].height,1)):1;
view.scale.set(spec.scaleX*fit,spec.scaleY*fit);
if(spec.blend&&spec.blend!=='normal')view.blendMode=spec.blend;
if(frames.length>1){view.animationSpeed=spec.fps/60;view.loop=spec.loop;view.play();}
root.addChild(view);objects.push({view,x:spec.x,y:spec.y,parallax:spec.parallax});
if(catalog){const text=new p.Text({text:spec.name.slice(0,40),style:{fontFamily:'Arial',fontSize:13,fill:0xd7e4ee,wordWrap:true,wordWrapWidth:175}});text.x=spec.x-82;text.y=spec.y+74;text.zIndex=view.zIndex+0.00001;root.addChild(text);objects.push({view:text,x:text.x,y:text.y,parallax:0});}
order++;
}
if(catalog)document.getElementById('page').textContent=(index+1)+' / '+pages.length;
}
const bar=document.getElementById('toolbar');if(catalog&&pages.length>1){bar.style.display='flex';document.getElementById('prev').onclick=()=>showPage((current+pages.length-1)%pages.length).catch(error);document.getElementById('next').onclick=()=>showPage((current+1)%pages.length).catch(error);}
function resize(){const scale=Math.min(innerWidth/SCENE.width,innerHeight/SCENE.height);root.scale.set(scale);root.position.set((innerWidth-SCENE.width*scale)*.5,(innerHeight-SCENE.height*scale)*.5);}resize();window.addEventListener('resize',resize);
window.addEventListener('pointermove',e=>{pointer.x=(e.clientX/innerWidth-.5)*2;pointer.y=(e.clientY/innerHeight-.5)*2;},{passive:true});
app.ticker.add(()=>{for(const obj of objects){if(!obj.parallax)continue;obj.view.x=obj.x-pointer.x*obj.parallax;obj.view.y=obj.y-pointer.y*obj.parallax*.5;}});
await showPage(0);
}catch(e){error(e);console.error(e);}
})();</script></body></html>'''


def locate_bundle(explicit: str|None, install: bool)->Path:
    candidates=[]
    if explicit:candidates.append(Path(explicit).expanduser())
    runtime=Path(__file__).resolve()
    candidates += [runtime.parent/'vendor'/'pixi.min.js',runtime.parents[2]/'node_modules'/'pixi.js'/'dist'/'pixi.min.js',Path.cwd()/'node_modules'/'pixi.js'/'dist'/'pixi.min.js',Path.home()/'.cache'/'meta-games'/'pixi.js' / PIN/'node_modules'/'pixi.js'/'dist'/'pixi.min.js']
    for p in candidates:
        if p.is_file():
            data=p.read_bytes()
            if len(data)<100000:raise ValueError('Suspiciously small PixiJS bundle: '+str(p))
            return p
    if not install:raise RuntimeError('PixiJS bundle absent. Pass --pixi-js /path/to/pixi.min.js or allow npm install.')
    npm=shutil.which('npm');
    if not npm:raise RuntimeError('npm missing; install Node.js or pass --pixi-js /path/to/pixi.min.js')
    cache=Path.home()/'.cache'/'meta-games'/'pixi.js'/PIN
    cache.mkdir(parents=True,exist_ok=True)
    cmd=[npm,'install','--prefix',str(cache),'--ignore-scripts','--no-audit','--no-fund','--no-save','--package-lock=false','pixi.js@'+PIN]
    subprocess.run(cmd,check=True,timeout=240)
    dest=cache/'node_modules'/'pixi.js'/'dist'/'pixi.min.js'
    if not dest.is_file():raise RuntimeError('PixiJS browser bundle not installed as expected: '+str(dest))
    return dest


def normalize_scene(src:Path, max_sprites:int)->tuple[dict,Path]:
    data=json.loads(src.read_text(encoding='utf-8-sig'))
    if not isinstance(data,dict):raise ValueError('Manifest must be a JSON object')
    if src.name=='unitypy_manifest.json' or ('items' in data and data.get('extractor')=='UnityPy'):
        entries=[]
        for item in data.get('items',[]):
            if item.get('kind') not in ('Sprite','Texture2D'):continue
            for file in item.get('files',[]):
                if str(file).lower().endswith(('.png','.jpg','.webp')):
                    entries.append((item.get('name',Path(file).stem),file))
        entries=entries[:max_sprites]
        if not entries:raise ValueError('UnityPy manifest has no exported Sprite/Texture2D images')
        sprites=[]
        for i,(name,file) in enumerate(entries):
            col=i%5;row=(i%30)//5
            sprites.append({'name':name,'frames':[file], 'layer':'midground','x':120+col*220,'y':110+row*190,'scale':1,'anchor':[.5,.5],'maxDimension':140,'fps':12})
        return {'title':'Original UnityPy sprite catalog','width':1200,'height':1200,'background':'#121a25','mode':'catalog','sprites':sprites},src.parent
    return data,src.parent


def normalize_sprites(scene:dict,root:Path,max_mb:int)->dict:
    width=int(scene.get('width',1280));height=int(scene.get('height',720))
    if not 64<=width<=8192 or not 64<=height<=8192:raise ValueError('Invalid scene dimensions')
    color=scene.get('background','#0b1220')
    if not re.fullmatch(r'#[a-fA-F0-9]{6}',str(color)):raise ValueError('background must be #RRGGBB')
    entries=scene.get('sprites',scene.get('entities'))
    if not isinstance(entries,list) or not entries:raise ValueError('Scene requires nonempty sprites array')
    if len(entries)>500:raise ValueError('At most 500 sprites per manifest')
    resources={};result=[];used=0
    for idx,entry in enumerate(entries):
        if not isinstance(entry,dict):raise ValueError('Sprite entry must be object')
        files=entry.get('frames',[])
        if not files:
            file=entry.get('file',entry.get('image'))
            files=[file] if file else []
        if not isinstance(files,list) or not files or len(files)>240:raise ValueError('Sprite must include file or 1..240 frames')
        keys=[]
        for f in files:
            if not isinstance(f,str) or re.match(r'^(https?://|data:|file://)',f,re.I):raise ValueError('Only local original image files allowed')
            path=(root/f).resolve(strict=True)
            if not path.is_relative_to(root.resolve()):raise ValueError('Image outside manifest directory: '+f)
            if path.suffix.lower() not in SUFFIX:raise ValueError('Unsupported image file: '+f)
            key=path.relative_to(root.resolve()).as_posix()
            if key not in resources:
                raw=path.read_bytes();used+=len(raw)
                if used>max_mb*1024*1024*0.70:raise ValueError('Image data exceeds safe HTML size; increase --max-mb or reduce images')
                resources[key]='data:'+SUFFIX[path.suffix.lower()]+';base64,'+base64.b64encode(raw).decode()
            keys.append(key)
        anchor=entry.get('anchor',[.5,.5]);
        if not isinstance(anchor,list) or len(anchor)!=2:raise ValueError('anchor must be [x,y]')
        scale=entry.get('scale',1)
        sx=float(entry.get('scaleX',scale));sy=float(entry.get('scaleY',scale))
        if 'maxDimension' in entry:
            # Catalog scale is computed after Image decode in runtime rather than modifying image.
            sx=sy=1
        spec={'name':str(entry.get('name',Path(files[0]).stem)),'frames':keys,'layer':entry.get('layer','midground'),
              'x':float(entry.get('x',width/2)),'y':float(entry.get('y',height/2)),
              'scaleX':sx,'scaleY':sy,'anchor':[float(anchor[0]),float(anchor[1])],
              'alpha':float(entry.get('alpha',1)),'rotation':float(entry.get('rotation',0)),
              'z':float(entry.get('z',idx)),'fps':float(entry.get('fps',12)),'loop':bool(entry.get('loop',True)),
              'parallax':float(entry.get('parallax',0)),'blend':entry.get('blend','normal'),
              'maxDimension':float(entry.get('maxDimension',0))}
        if spec['layer'] not in LAYER:raise ValueError('Invalid layer: '+str(spec['layer']))
        if not -8<=spec['scaleX']<=8 or not -8<=spec['scaleY']<=8:raise ValueError('scale exceeds limits')
        if not 0<=spec['alpha']<=1 or not 0<spec['fps']<=60:raise ValueError('alpha or fps out of range')
        result.append(spec)
    return {'title':str(scene.get('title','Original 2D scene')),'width':width,'height':height,
            'mode':scene.get('mode','scene'),'background':color,'pixelArt':bool(scene.get('pixelArt',False)),
            'antialias':bool(scene.get('antialias',True)),'sprites':result,'resources':resources}


def create(src:Path,out:Path,pixi:Path,max_mb:int,force:bool=False)->None:
    src=src.resolve(strict=True);out=out.resolve()
    if out.exists() and not force:raise ValueError('Output already exists; use --force to overwrite: '+str(out))
    scene,root=normalize_scene(src,500)
    payload=normalize_sprites(scene,root,max_mb)
    js=pixi.read_text(encoding='utf-8')
    js=re.sub(r'</script',r'<\\/script',js,flags=re.I)
    serial=base64.b64encode(json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode('utf-8')).decode()
    title=re.sub(r'[<>"\'&]','',payload['title'])[:90]
    html=HTML.replace('__TITLE__',title).replace('__COLOR__',payload['background']).replace('__PIXI_BUNDLE__',js).replace('__SCENE_B64__',serial)
    size=len(html.encode('utf-8'))
    if size>max_mb*1024*1024:raise ValueError('Output exceeds --max-mb; reduce assets')
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(html,encoding='utf-8')
    print(out)


def main():
    a=argparse.ArgumentParser(description='Original UnityPy/Godot sprites -> standalone PixiJS visual HTML (not a game port)')
    a.add_argument('manifest',type=Path,help='scene JSON with original sprite coordinates, or UnityPy unitypy_manifest.json for catalog')
    a.add_argument('--out',type=Path,required=True)
    a.add_argument('--pixi-js',help='Locally installed PixiJS v8.23.0 dist/pixi.min.js browser bundle')
    a.add_argument('--no-install',action='store_true',help='Require local browser bundle, no network during build')
    a.add_argument('--max-mb',type=int,default=256)
    a.add_argument('--force',action='store_true')
    p=a.parse_args()
    if not 1<=p.max_mb<=2048:raise ValueError('--max-mb must be 1..2048')
    bundle=locate_bundle(p.pixi_js,not p.no_install)
    create(p.manifest,p.out,bundle,p.max_mb,p.force)

if __name__=='__main__':
    try:main()
    except (OSError,ValueError,RuntimeError,subprocess.CalledProcessError,subprocess.TimeoutExpired) as e:sys.exit('ERROR: '+str(e))
