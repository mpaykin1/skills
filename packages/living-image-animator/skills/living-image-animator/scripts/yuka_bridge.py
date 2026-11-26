#!/usr/bin/env python3
"""Add authentic YUKA NPC steering/chase onto approved PixiJS+Matter+Nipple HTML.

Original RGBA cels, character identities, authored world routes, and source
motion gate are unchanged. YUKA owns AI decisions/steering, A* owns routing,
and Matter.js is the sole collision/trigger solver.
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
from nipplejs_bridge import read_controls
from matter_bridge import validate_scene
from yuka_vendor import locate

class YukaBridgeError(ValueError):pass

def fail(message):raise YukaBridgeError('YUKA game AI export blocked: '+str(message))
def numeric(value,minval,maxval,name):
    if type(value) not in (int,float) or not math.isfinite(value) or not minval<=value<=maxval:
        fail(f'{name} must be a finite value in [{minval}, {maxval}]')
    return float(value)
def one(src,old,new,desc):
    count=src.count(old)
    if count!=1:fail(f'Approved Matter/nipplejs template changed at {desc}: {count} matches')
    return src.replace(old,new,1)

def config_from_approved(approved_zip):
    scene=validate_scene(approved_zip)
    controls=read_controls(approved_zip)
    with zipfile.ZipFile(approved_zip) as z:
        if z.testzip() is not None:fail('Original source animation ZIP is corrupt')
        cfg=json.loads(z.read('scene.json'))
        gate=json.loads(z.read('motion_gate.json'))
    if gate.get('all_actors_pass') is not True:fail('Complete original figure animation quality gate failed')
    raw=cfg.get('browser_ai')
    if not isinstance(raw,dict) or set(raw)-{'agents'}:
        fail('Author must provide scene.browser_ai.agents; unknown keys refused')
    agents=raw.get('agents')
    if not isinstance(agents,list) or not 1<=len(agents)<=12:
        fail('Author must declare 1..12 AI actors; no invented NPCs')
    nav=scene['browserNavigation']['actors']
    cast={a['id']:a for a in scene['actors']}
    player=controls['player_actor']
    registered=set();out=[]
    max_size=max(scene['width'],scene['height'])
    for entry in agents:
        allowed={'actor_id','mode','detection_radius_px','forget_radius_px','forget_after_s',
                 'repath_interval_s','speed_multiplier'}
        if not isinstance(entry,dict) or set(entry)-allowed:fail('Unknown or invalid source-authored NPC declaration')
        aid=entry.get('actor_id')
        if not isinstance(aid,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',aid):fail('NPC actor_id required')
        if aid==player:fail('Player controlled via nipplejs cannot be controlled by NPC AI')
        if aid in registered:fail('Duplicate NPC actor_id '+aid)
        if aid not in cast or aid not in nav:fail('NPC must be a real validated, navigable painted actor: '+aid)
        registered.add(aid)
        mode=entry.get('mode','patrol_chase')
        if mode not in ('patrol','patrol_chase'):fail('AI mode must be patrol or patrol_chase')
        radius=numeric(entry.get('detection_radius_px',min(110,max_size*.2)),8,max_size,'detection_radius_px')
        forget=numeric(entry.get('forget_radius_px',min(max_size,max(130,radius*1.8))),radius,max_size,'forget_radius_px')
        expire=numeric(entry.get('forget_after_s',1.2),.25,5,'forget_after_s')
        repath=numeric(entry.get('repath_interval_s',.5),.25,3,'repath_interval_s')
        speed=numeric(entry.get('speed_multiplier',1),.5,1.4,'speed_multiplier')
        if len(nav[aid]['waypoints'])<2:fail('Approved authored patrol must have >=2 real waypoints: '+aid)
        out.append({'actor_id':aid,'mode':mode,'detection_radius_px':radius,
                    'forget_radius_px':forget,'forget_after_s':expire,
                    'repath_interval_s':repath,'speed_multiplier':speed})
    return {'engine':'YUKA','version':'0.7.8','player_actor':player,'agents':out,
            'original_cast_count':len(cast),'approved_animation_gate':True,
            'navigation':'PathFinding.js A*','physics':'Matter.js 0.20.0'}


def patch_html(controls_html,out_html,approved_zip,yuka_js):
    data=config_from_approved(approved_zip)
    _,vendor=locate(yuka_js)
    html=Path(controls_html).resolve().read_text('utf8')
    if 'window.nipplejs' not in html or 'Matter.Engine.create' not in html or 'PF.AStarFinder' not in html:
        fail('Expected already approved genuine PixiJS+Matter+PathFinding.js+nipplejs player HTML')
    regex=r'<script id="lia-scene" type="application/json">(.*?)</script>'
    original=re.search(regex,html,re.S)
    if not original:fail('Original approved character scene missing from HTML')
    basehash=hashlib.sha256(original.group(1).encode('utf8')).hexdigest()
    vendor=re.sub(r'</script',r'<\\/script',vendor,flags=re.I)
    ai=json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
    html=one(html,'<script id="lia-controls" type="application/json">',
        '<script>/* Genuine YUKA 0.7.8; MIT; original LICENSE in accompanying ZIP. */\n'+vendor+'</script>'+ 
        '<script id="lia-ai" type="application/json">'+ai+'</script>'+ 
        '<script id="lia-controls" type="application/json">','genuine YUKA runtime')
    code=Path(__file__).with_name('yuka_ai_runtime.js').read_text('utf8')
    html=one(html,' const pathfinder=new PF.AStarFinder({diagonalMovement:PF.DiagonalMovement.Never});',
        ' const pathfinder=new PF.AStarFinder({diagonalMovement:PF.DiagonalMovement.Never});\n'+code,
        'YUKA agents and steering on original A*')
    html=one(html,' function stepPhysics(){',' function stepPhysics(){\n   yukaClock+=1/60;',
             'fixed-step AI clock')
    html=one(html,'     // Waypoint changes happen ONLY after an actually reached point, no teleport.',
        '     if(yukaAgents.has(a.info.id))yukaDecide(a);\n'+
        '     // Waypoint changes happen ONLY after an actually reached point, no teleport.',
        'state transition before waypoint resolution')
    html=one(html,'     if(!n.route.length){\n       if(a===controlledActor)',
        '     if(!n.route.length){\n'+
        "       if(yukaAgents.has(a.info.id) && yukaAgents.get(a.info.id).state==='chase'){"+
        'Matter.Body.setVelocity(body,{x:0,y:0});n.moving=false;continue;}\n'+
        '       if(a===controlledActor)',
        'chasing NPC cannot become patrol without actually leaving chase state')
    html=one(html,'     Matter.Body.setVelocity(body,{x:dx*scale,y:dy*scale});',
        '     const aiVelocity=yukaSteer(a);\n'+
        '     Matter.Body.setVelocity(body,aiVelocity||{x:dx*scale,y:dy*scale});',
        'YUKA directed velocity with Matter collision')
    html=one(html,'       routeTo(a,n.config.waypoints[n.waypointIndex]);\n     }\n   }\n }\n function smoothstep',
        '       const agent=yukaAgents.get(a.info.id);\n'+
        "       if(agent&&agent.state==='chase')agent.nextRepath=0;\n"+
        '       else routeTo(a,n.config.waypoints[n.waypointIndex]);\n'+
        '     }\n   }\n }\n function smoothstep',
        'stalled NPC re-paths to target only through real A*')
    checked=re.search(regex,html,re.S)
    if not checked or hashlib.sha256(checked.group(1).encode('utf8')).hexdigest()!=basehash:
        fail('Published original source/pose scene was modified by NPC integration')
    if len(html.encode('utf8'))>150*1024*1024:fail('Browser artifact exceeds 150 MiB')
    dest=Path(out_html).resolve();dest.parent.mkdir(parents=True,exist_ok=True)
    if dest.exists():fail('Refusing to overwrite another HTML; use a new output directory')
    temp=dest.with_suffix('.tmp');temp.write_text(html,encoding='utf8');os.replace(temp,dest)
    return dest,{'engine':'YUKA 0.7.8','npc_count':len(data['agents']),
                 'player_actor':data['player_actor'],'behavior_modes':list(sorted(set(x['mode'] for x in data['agents']))),
                 'pathfinding':'PathFinding.js 0.4.18','collision':'Matter.js 0.20.0',
                 'mobile_controls':'nipplejs 1.0.4','characters_repainted':0,
                 'source_scene_sha256':basehash,'offline':True,'bytes':dest.stat().st_size,
                 'sha256':hashlib.sha256(dest.read_bytes()).hexdigest()}

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--approved-zip',type=Path,required=True)
    p.add_argument('--controls-html',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--yuka-js',type=Path)
    a=p.parse_args();print(json.dumps(patch_html(a.controls_html,a.out,a.approved_zip,a.yuka_js)[1],ensure_ascii=False))
