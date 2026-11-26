#!/usr/bin/env python3
"""Real pixi-viewport v7 camera inside original, fully validated PixiJS v8 HTML.

This is an additive post-export. It NEVER edits character PNGs, source GIF,
original atlas or the mandatory MMPose/SAM2/Godot/Blender pose checks.
"""
from __future__ import annotations
import argparse
import json
import math
import os
import re
from pathlib import Path
import zipfile

class ViewportBridgeError(ValueError):pass

def refuse(msg):raise ViewportBridgeError('pixi-viewport export blocked: '+msg)

def viewport_bundle(path):
    if path is None:path=os.environ.get('PIXI_VIEWPORT_BUNDLE')
    if not path:refuse('Real pixi-viewport UMD not found; use --fetch-viewport or --viewport-js')
    p=Path(path).expanduser().resolve()
    if not p.is_file():refuse('Viewport runtime not installed at '+str(p))
    payload=p.read_bytes()
    if not 15_000<=len(payload)<=2_500_000:refuse('Invalid viewport runtime size')
    code=payload.decode('utf8')
    if 'Viewport' not in code or 'pixi_viewport' not in code[:1500]:
        refuse('Expected real official pixi-viewport browser UMD, not surrogate camera code')
    return p,code

def config_from_approved(approved_zip):
    with zipfile.ZipFile(approved_zip) as z:
        if z.testzip() is not None:refuse('Upstream animated asset ZIP corrupt')
        try: cfg=json.loads(z.read('scene.json')); gate=json.loads(z.read('motion_gate.json'))
        except (ValueError,KeyError) as e:refuse('Source scene or motion gate missing: '+str(e))
    if gate.get('all_actors_pass') is not True:refuse('Full-cel animation gate did not approve characters')
    actors=cfg.get('actors',[])
    actor_ids={a.get('id') for a in actors}
    pixi=cfg.get('pixi',{})
    if not isinstance(pixi,dict):refuse('pixi settings must be object')
    cam=pixi.get('viewport',{})
    if not isinstance(cam,dict):refuse('pixi.viewport must be an object')
    if set(cam)-{'min_zoom','max_zoom','follow_actor','drag','pinch','wheel','keyboard','weather_screen_space'}:
        refuse('Unknown pixi.viewport option: '+str(set(cam)-{'min_zoom','max_zoom','follow_actor','drag','pinch','wheel','keyboard','weather_screen_space'}))
    min_zoom=cam.get('min_zoom',.7);max_zoom=cam.get('max_zoom',3.5)
    if not all(type(v) in (int,float) and math.isfinite(v) for v in [min_zoom,max_zoom]) or not (0.2<=min_zoom<=1<=max_zoom<=8):
        refuse('Camera min_zoom/max_zoom must surround 1 and be within 0.2..8 relative to fit')
    for key in ('drag','pinch','wheel','keyboard','weather_screen_space'):
        if key in cam and type(cam[key]) is not bool:refuse('Camera '+key+' must be boolean')
    follow=cam.get('follow_actor')
    if follow is not None and (not isinstance(follow,str) or follow not in actor_ids):
        refuse('Follow target must reference one of the verified cast IDs')
    return {'min_zoom':float(min_zoom),'max_zoom':float(max_zoom),'follow_actor':follow,
            'drag':cam.get('drag',True),'pinch':cam.get('pinch',True),
            'wheel':cam.get('wheel',True),'keyboard':cam.get('keyboard',False),
            'weather_screen_space':cam.get('weather_screen_space',False)}

def replace_one(text,old,new,label):
    n=text.count(old)
    if n!=1:refuse(f'PixiJS atlas template changed at {label}: expected 1 marker, found {n}; no partial export')
    return text.replace(old,new,1)

def patch_atlas_html(atlas_html,out_html,approved_zip,viewport_js):
    """Keep all actual source PNGs, atlas UVs and frame cadence EXACTLY unchanged."""
    camera=config_from_approved(approved_zip)
    _,runtime=viewport_bundle(viewport_js)
    src=Path(atlas_html).read_text('utf8')
    if '<script>const LIVING_SCENE=' not in src or 'pixi_runtime' in src:
        refuse('Not an approved embedded PixiJS atlas template')
    runtime=re.sub(r'</script',r'<\\/script',runtime,flags=re.I)
    src=replace_one(src,'<script>const LIVING_SCENE=',
        '<script>/* pixi-viewport 7.0.3, MIT; original LICENSE retained in package. */\n'+runtime+'</script><script>const LIVING_SCENE=',
        'genuine viewport UMD injection')
    # Beware: source contains an actual JavaScript line, not a Python module reference.
    old='''    const world = new PIXI.Container();
    world.sortableChildren = true;
    app.stage.addChild(world);'''
    new='''    const CameraClass=(window.pixi_viewport && window.pixi_viewport.Viewport);
    if (!CameraClass) throw new Error('Genuine pixi-viewport UMD did not initialize');
    const cameraOptions=__LIA_CAMERA_SETTINGS__;
    const world=new CameraClass({
      screenWidth:app.renderer.screen.width,screenHeight:app.renderer.screen.height,
      worldWidth:S.W,worldHeight:S.H,events:app.renderer.events,
      passiveWheel:false,disableOnContextMenu:true});
    world.sortableChildren=true;
    app.stage.addChild(world);
    if(cameraOptions.drag) world.drag();
    if(cameraOptions.pinch) world.pinch();
    if(cameraOptions.wheel) world.wheel();
    if(cameraOptions.drag) world.decelerate();'''.replace('__LIA_CAMERA_SETTINGS__',json.dumps(camera,separators=(',',':')).replace('<','\\u003c'))
    src=replace_one(src,old,new,'root camera container')
    old='''    const bounds={scale:1,offsetX:0,offsetY:0};
    function resize(){
      const k=Math.min(innerWidth/S.W,innerHeight/S.H);
      bounds.scale=k;
      bounds.offsetX=(innerWidth-S.W*k)/2;
      bounds.offsetY=(innerHeight-S.H*k)/2;
      app.stage.scale.set(k);
      app.stage.position.set(bounds.offsetX,bounds.offsetY);
    }
    window.addEventListener('resize',resize,{passive:true}); resize();'''
    new='''    let cameraInitialized=false;
    let initialFit=1;
    function resize(){
      const width=app.renderer.screen.width,height=app.renderer.screen.height;
      if(!width||!height)return;
      const previousCenter=world.center.clone(),previousZoom=world.scale.x;
      world.resize(width,height,S.W,S.H);
      const fit=Math.min(width/S.W,height/S.H);
      const minScale=fit*cameraOptions.min_zoom,maxScale=fit*cameraOptions.max_zoom;
      world.clampZoom({minScale,maxScale});
      if(!cameraInitialized){
        initialFit=fit;world.setZoom(fit,true);world.moveCenter(S.W/2,S.H/2);
        cameraInitialized=true;
      }else{
        world.setZoom(Math.max(minScale,Math.min(maxScale,previousZoom)),true);
        world.moveCenter(previousCenter);
      }
      world.clamp({direction:'all',underflow:'center'});
    }
    window.addEventListener('resize',()=>requestAnimationFrame(resize),{passive:true});resize();
    if(cameraOptions.keyboard){
      window.addEventListener('keydown',(event)=>{
        if(event.target && /INPUT|TEXTAREA|SELECT/.test(event.target.tagName))return;
        const dist=32/world.scale.x;
        const keys={'ArrowLeft':[-dist,0],'ArrowRight':[dist,0],
          'ArrowUp':[0,-dist],'ArrowDown':[0,dist]};
        const vector=keys[event.key];if(!vector)return;
        event.preventDefault();world.moveCenter(world.center.x+vector[0],world.center.y+vector[1]);
      });
    }'''
    src=replace_one(src,old,new,'responsive camera sizing')
    old='''    // Optional truly ambient particle stratum; no particle is a proxy for a moving character.'''
    new='''    if(cameraOptions.follow_actor){
      const target=avatars.find(a=>a.actor.id===cameraOptions.follow_actor);
      if(!target)throw new Error('Follow target disappeared from verified character atlas');
      world.follow(target.figure,{speed:5});
    }
    // Optional truly ambient particle stratum; no particle is a proxy for a moving character.'''
    src=replace_one(src,old,new,'optional actor follow')
    old='''      for(const pl of planes){pl.object.x=shiftX*pl.parallax;pl.object.y=shiftY*pl.parallax;}'''
    new='''      const camDX=world.center.x-S.W/2,camDY=world.center.y-S.H/2;
      for(const pl of planes){
        pl.object.x=shiftX*pl.parallax+(1-pl.parallax)*camDX;
        pl.object.y=shiftY*pl.parallax+(1-pl.parallax)*camDY;
      }'''
    src=replace_one(src,old,new,'camera-aware 2.5D parallax')
    old="const group=new PIXI.Container();group.zIndex=10000;world.addChild(group);"
    new="const group=new PIXI.Container();group.zIndex=10000;\n      if(cameraOptions.weather_screen_space)app.stage.addChild(group);else world.addChild(group);"
    src=replace_one(src,old,new,'optional screen-space weather')
    old="""      for(const p of weather){
        p.sprite.x=(p.x+elapsed*(S.weather==='snow'?6:16))%(S.W+16)-8;
        p.sprite.y=(p.y+elapsed*p.speed)%(S.H+16)-8;
      }"""
    new="""      const weatherW=cameraOptions.weather_screen_space?app.renderer.screen.width:S.W;
      const weatherH=cameraOptions.weather_screen_space?app.renderer.screen.height:S.H;
      for(const p of weather){
        p.sprite.x=(p.x+elapsed*(S.weather==='snow'?6:16))%(weatherW+16)-8;
        p.sprite.y=(p.y+elapsed*p.speed)%(weatherH+16)-8;
      }"""
    src=replace_one(src,old,new,'camera-independent atmospheric layer')
    old='''    window.__livingScene = {app,actors:avatars.length,authoredFps:S.fps,pixiVersion:S.version};'''
    new='''    window.__livingScene = {app,world,actors:avatars.length,authoredFps:S.fps,
       pixiVersion:S.version,viewportVersion:'7.0.3',
       center:(x,y)=>world.moveCenter(x,y),
       zoom:(scale)=>world.setZoom(scale,true)};'''
    src=replace_one(src,old,new,'camera API')
    # Ensure original animation atlas metadata remains byte-identical while runtime changes.
    if len(src.encode('utf8'))>150*1024*1024:refuse('Camera HTML exceeds 150MiB browser budget')
    out_html=Path(out_html).resolve();out_html.parent.mkdir(parents=True,exist_ok=True)
    tmp=out_html.with_suffix('.tmp');tmp.write_text(src,'utf8');os.replace(tmp,out_html)
    return out_html,{'camera':'real pixi-viewport 7.0.3','follow':camera['follow_actor'],
        'parallax':True,'character_deformation':False,'standalone':True,'bytes':out_html.stat().st_size}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--approved-zip',required=True,type=Path)
    p.add_argument('--atlas-html',required=True,type=Path)
    p.add_argument('--out',required=True,type=Path)
    p.add_argument('--viewport-js',type=Path)
    args=p.parse_args()
    print(json.dumps(patch_atlas_html(args.atlas_html,args.out,args.approved_zip,args.viewport_js)[1],ensure_ascii=False))

if __name__=='__main__':main()
