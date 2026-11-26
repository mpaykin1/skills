#!/usr/bin/env python3
"""Add genuine nipplejs 1.0.4 touch joystick to previously approved Matter.js 2D gameplay.

The original full-body RGBA sprite pixels and authored animation clips are NEVER
modified. Matter.js stays the sole collision solver; PathFinding.js remains
responsible for click-to-move and non-player A* routes.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import zipfile
from matter_bridge import validate_scene
from nipplejs_vendor import locate

class NippleBridgeError(ValueError):pass

def fail(message):raise NippleBridgeError('nipplejs controls blocked: '+str(message))

def replace_once(src,old,new,where):
    count=src.count(old)
    if count!=1:fail('Original physical HTML template changed at '+where+f' ({count} matches)')
    return src.replace(old,new,1)

def read_controls(approved_zip):
    checked=validate_scene(approved_zip)  # validates actual PNG cels, A* and Matter physics
    with zipfile.ZipFile(approved_zip,'r') as z:
        if z.testzip() is not None:fail('Original source ZIP corrupt')
        cfg=json.loads(z.read('scene.json'))
        if json.loads(z.read('motion_gate.json')).get('all_actors_pass') is not True:
            fail('Original character motion gate is not passed')
    raw=cfg.get('browser_controls',{})
    if not isinstance(raw,dict):fail('browser_controls must be an object')
    allow={'player_actor','speed_multiplier','joystick_px','deadzone','tap_to_move','keyboard','show_desktop'}
    if set(raw)-allow:fail('Unknown browser_controls keys: '+str(sorted(set(raw)-allow)))
    roster=checked['browserNavigation']['actors']
    if not roster:fail('At least one author-approved navigator is required for joystick control')
    actor=raw.get('player_actor')
    if actor is None:
        actor=next(a['id'] for a in checked['actors'] if a['id'] in roster)
    if not isinstance(actor,str) or actor not in roster:
        fail('player_actor must identify a real verified navigable actor')
    def float_range(key,default,minvalue,maxvalue):
        x=raw.get(key,default)
        if type(x) not in (int,float) or not math.isfinite(x) or not minvalue<=x<=maxvalue:
            fail(f'{key} must be a finite number {minvalue}..{maxvalue}')
        return float(x)
    for key in ('tap_to_move','keyboard','show_desktop'):
        if key in raw and type(raw[key]) is not bool:fail('Expected boolean '+key)
    size=raw.get('joystick_px',120)
    if type(size) is not int or not 80<=size<=180:fail('joystick_px must be integer 80..180')
    return {'player_actor':actor,'speed_multiplier':float_range('speed_multiplier',1,0.5,1.5),
            'joystick_px':size,'deadzone':float_range('deadzone',.13,.05,.32),
            'tap_to_move':raw.get('tap_to_move',True),'keyboard':raw.get('keyboard',True),
            'show_desktop':raw.get('show_desktop',False),'approved_actor_count':len(checked['actors']),
            'engine':'nipplejs 1.0.4 + real Matter.js 0.20.0 + PathFinding.js 0.4.18'}

CONTROL_INITIALIZATION=r''' const LIA_CTRL=JSON.parse(document.getElementById('lia-controls').textContent);
 const heldKeys=new Set();let joystickVector={x:0,y:0};let controlledActor=null;
 let manualTapRoute=false;
 function controlVector(){
   let x=joystickVector.x,y=joystickVector.y;
   if(LIA_CTRL.keyboard){
     if(heldKeys.has('ArrowLeft')||heldKeys.has('KeyA'))x-=1;
     if(heldKeys.has('ArrowRight')||heldKeys.has('KeyD'))x+=1;
     if(heldKeys.has('ArrowUp')||heldKeys.has('KeyW'))y-=1;
     if(heldKeys.has('ArrowDown')||heldKeys.has('KeyS'))y+=1;
   }
   const mag=Math.hypot(x,y);
   if(mag<=LIA_CTRL.deadzone)return {x:0,y:0};
   return {x:x/Math.max(1,mag),y:y/Math.max(1,mag)};
 }
 function clampControlsToGrid(nx,ny,config){
   const x=Math.floor(nx/config.cell_px), y=Math.floor(ny/config.cell_px);
   return x>=0&&y>=0&&x<config.width&&y<config.height&&config.matrix[y][x]===0;
 }
'''

PLAYER_VELOCITY=r'''     if(a===controlledActor){
       const v=controlVector(),speed=n.config.speed_px_s*LIA_CTRL.speed_multiplier/60;
       if(v.x!==0||v.y!==0){
         // Manual control overrides A*. Never apply a teleport or warp source cels.
         manualTapRoute=false;n.route=[];n.stalled=0;
         const p=body.position;
         let vx=v.x*speed,vy=v.y*speed;
         if(!clampControlsToGrid(p.x+vx,p.y+vy,n.config)){
           // Independent axis collision allows graceful wall sliding.
           if(clampControlsToGrid(p.x+vx,p.y,n.config))vy=0;
           else if(clampControlsToGrid(p.x,p.y+vy,n.config))vx=0;
           else{vx=0;vy=0;}
         }
         Matter.Body.setVelocity(body,{x:vx,y:vy});n.moving=!!(vx||vy);
         continue;
       }
       if(!manualTapRoute){
         Matter.Body.setVelocity(body,{x:0,y:0});n.moving=false;continue;
       }
     }
'''

PLAYER_SETUP=r''' const selected=actors.find(a=>a.nav&&a.info.id===LIA_CTRL.player_actor);
 if(!selected)throw new Error('Original source-authored playable character is missing');
 controlledActor=selected;controlledActor.nav.route=[];
 const joystickLib=window.nipplejs;
 if(!joystickLib||typeof joystickLib.create!=='function')
   throw new Error('Genuine nipplejs 1.0.4 UMD did not initialize');
 const controlZone=document.getElementById('lia-joystick-zone');
 if(!controlZone)throw new Error('Fixed joystick zone is absent');
 if(LIA_CTRL.show_desktop)controlZone.classList.add('lia-always-visible');
 const joystick=joystickLib.create({
   zone:controlZone,mode:'static',position:{left:'50%',top:'50%'},
   color:'rgba(213,230,247,0.84)',size:LIA_CTRL.joystick_px,
   fadeTime:0,restOpacity:0.75,restJoystick:true,
   multitouch:false,maxNumberOfJoysticks:1
 });
 joystick.on('move',(evt,data)=>{
   const eventData=data||evt?.data;
   if(!eventData?.vector)return;
   const rawX=Number(eventData.vector.x),rawY=Number(eventData.vector.y);
   const force=Math.min(1,Math.max(0,Number(eventData.force)||0));
   if(!Number.isFinite(rawX)||!Number.isFinite(rawY))return;
   // nipplejs vector.y is UP-positive; PixiJS and Matter world Y is DOWN-positive.
   joystickVector={x:Math.max(-1,Math.min(1,rawX*force)),
                   y:-Math.max(-1,Math.min(1,rawY*force))};
 });
 joystick.on('end',()=>{joystickVector={x:0,y:0};});
 if(LIA_CTRL.keyboard){
   const gameKeys=new Set(['KeyW','KeyA','KeyS','KeyD','ArrowLeft','ArrowRight','ArrowUp','ArrowDown']);
   window.addEventListener('keydown',e=>{
     if(!gameKeys.has(e.code)||e.altKey||e.ctrlKey||e.metaKey)return;
     if(e.target&&/INPUT|TEXTAREA|SELECT/.test(e.target.tagName))return;
     e.preventDefault();heldKeys.add(e.code);
   });
   window.addEventListener('keyup',e=>{if(gameKeys.has(e.code)){heldKeys.delete(e.code);e.preventDefault();}});
 }
 window.addEventListener('blur',()=>{heldKeys.clear();joystickVector={x:0,y:0};});
 document.addEventListener('visibilitychange',()=>{
   if(document.hidden){heldKeys.clear();joystickVector={x:0,y:0};}
 });
'''

STICK_CSS='''
#lia-joystick-zone{display:none;position:fixed;left:max(16px,env(safe-area-inset-left));bottom:max(16px,env(safe-area-inset-bottom));width:146px;height:146px;z-index:6;touch-action:none;pointer-events:auto;user-select:none;-webkit-user-select:none}
@media (pointer:coarse){#lia-joystick-zone{display:block}}
#lia-joystick-zone.lia-always-visible{display:block}
@media (max-width:380px){#lia-joystick-zone{width:130px;height:130px}}
'''

def patch_html(physics_html,out_html,approved_zip,nipple_js):
    meta=read_controls(approved_zip)
    _,lib=locate(nipple_js)
    src=Path(physics_html).read_text('utf8')
    if 'Matter.Engine.create' not in src or 'PF.AStarFinder' not in src or '<script id="lia-scene"' not in src:
        fail('This is not an authentic previous Matter.js + A* offline HTML')
    # Keep original validated data script, RGBA frames and engine scripts unchanged.
    scene_match=re.search(r'<script id="lia-scene" type="application/json">(.*?)</script>',src,re.S)
    if not scene_match:fail('Previous original scene JSON missing')
    original_sha=hashlib.sha256(scene_match.group(1).encode('utf8')).hexdigest()
    lib=re.sub(r'</script',r'<\\/script',lib,flags=re.I)
    src=replace_once(src,'</style></head>','\n'+STICK_CSS+'</style></head>','touch control layer')
    src=replace_once(src,'<div id="error" role="alert"></div>',
       '<div id="error" role="alert"></div><div id="lia-joystick-zone" aria-label="Фиксированный джойстик движения"></div>',
       'actual joystick touch target')
    src=replace_once(src,'<script id="lia-scene"',
       '<script>/* Original nipplejs 1.0.4 MIT; attribution retained in package. */\n'+lib+'</script>'+
       '<script id="lia-controls" type="application/json">'+json.dumps(meta,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')+'</script>'+
       '<script id="lia-scene"','original nipplejs UMD')
    src=replace_once(src,' const pathfinder=new PF.AStarFinder',CONTROL_INITIALIZATION+' const pathfinder=new PF.AStarFinder','controls input state')
    src=replace_once(src,'     const n=a.nav;if(!n)continue;\n     const body=n.body;',
      '     const n=a.nav;if(!n)continue;\n     const body=n.body;\n'+PLAYER_VELOCITY,'physics movement override')
    src=replace_once(src,'     if(!n.route.length){\n       n.waypointIndex=',
      '     if(!n.route.length){\n       if(a===controlledActor){manualTapRoute=false;Matter.Body.setVelocity(body,{x:0,y:0});n.moving=false;continue;}\n       n.waypointIndex=',
       'manual path stop')
    src=replace_once(src,' const selected=actors.find(a=>a.nav);',PLAYER_SETUP,'approved player and fixed joystick')
    src=replace_once(src,'   if(routeTo(selected,[x,y]))selected.nav.waypointIndex=0;',
      '   if(LIA_CTRL.tap_to_move && routeTo(selected,[x,y])){manualTapRoute=true;selected.nav.waypointIndex=0;}',
      'tap-to-move controls')
    src=replace_once(src,"   pause:()=>{paused=true;},play:()=>{paused=false;},physics:'Matter.js 0.20.0'};",
      "   pause:()=>{paused=true;},play:()=>{paused=false;},physics:'Matter.js 0.20.0',"+
      "controls:'nipplejs 1.0.4',playerId:LIA_CTRL.player_actor,joystick,keyboard:LIA_CTRL.keyboard};",
      'public game controls')
    scene_match2=re.search(r'<script id="lia-scene" type="application/json">(.*?)</script>',src,re.S)
    if not scene_match2 or hashlib.sha256(scene_match2.group(1).encode('utf8')).hexdigest()!=original_sha:
        fail('Authentic original player/pose JSON unexpectedly changed')
    if len(src.encode('utf8'))>150*1024*1024:fail('HTML exceeds offline browser size budget')
    dest=Path(out_html).resolve();dest.parent.mkdir(parents=True,exist_ok=True)
    if dest.exists():fail('Use a fresh output directory; cannot overwrite previous published HTML')
    tmp=dest.with_suffix('.tmp');tmp.write_text(src,'utf8');os.replace(tmp,dest)
    return dest,{'engine':meta['engine'],'player_actor':meta['player_actor'],
       'approved_actor_count':meta['approved_actor_count'],
       'mobile_fixed_joystick':True,'keyboard':meta['keyboard'],
       'matter_collision':True,'pathfinding_click_to_move':meta['tap_to_move'],
       'source_scene_sha256':original_sha,'source_character_pngs_unchanged':True,
       'offline':True,'bytes':dest.stat().st_size,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest()}

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--approved-zip',type=Path,required=True)
    a.add_argument('--physics-html',type=Path,required=True);a.add_argument('--out',type=Path,required=True)
    a.add_argument('--nipple-js',type=Path);s=a.parse_args()
    print(json.dumps(patch_html(s.physics_html,s.out,s.approved_zip,s.nipple_js)[1],ensure_ascii=False))
