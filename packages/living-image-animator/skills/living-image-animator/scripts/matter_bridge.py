#!/usr/bin/env python3
"""Source-verified PixiJS+PathFinding.js+Matter.js autonomous HTML.

All images and level geometry come from original validated ZIP; Matter.js adds
collision/trigger simulation ONLY to already-authored, already-certified 2D poses.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import re
from pathlib import Path
import zipfile
from pixijs_bridge import load_scene, bundle_path, json_inline, PIXILICENSE
from pathfinding_vendor import locate as locate_pathfinding
from matter_vendor import locate as locate_matter

class MatterBridgeError(ValueError):pass

def fail(msg):raise MatterBridgeError('Matter.js bridge blocked: '+str(msg))
def number(x):return type(x) in (float,int) and math.isfinite(x)

def validate_scene(approved_zip):
    # Existing project, pose, identity, motion, and source PNG checks all stay mandatory.
    scene=load_scene(approved_zip)
    nav=scene.get('browserNavigation')
    if not isinstance(nav,dict) or not nav.get('actors'):
        fail('Real Godot/Tiled/LDtk navigation actors required; physics cannot be inferred from a flat illustration')
    with zipfile.ZipFile(approved_zip,'r') as z:
        cfg=json.loads(z.read('scene.json'))
    geometry=cfg.get('godot',{})
    if not isinstance(geometry,dict):fail('Authored godot collision metadata required')
    obstacles=geometry.get('obstacles',[])
    if not isinstance(obstacles,list) or len(obstacles)>128:fail('Invalid authored obstacle list')
    safe_obstacles=[]
    for rect in obstacles:
        if not isinstance(rect,list) or len(rect)!=4 or not all(number(v) for v in rect):fail('Obstacle has invalid rectangle')
        x,y,w,h=rect
        if x<0 or y<0 or w<=1 or h<=1 or x+w>scene['width'] or y+h>scene['height']:
            fail('Obstacle outside original source pixel geometry')
        safe_obstacles.append([float(x),float(y),float(w),float(h)])
    matter=cfg.get('matter',{})
    if not isinstance(matter,dict):fail('scene.matter must be an object')
    sensors=matter.get('sensors',[])
    if not isinstance(sensors,list) or len(sensors)>64:fail('Too many physical triggers')
    seen=set(); safe_sensors=[]
    for item in sensors:
        if not isinstance(item,dict):fail('Sensor must be object')
        id=item.get('id');bounds=item.get('rect');kind=item.get('type','trigger')
        if not isinstance(id,str) or not re.fullmatch('[A-Za-z0-9_-]{1,64}',id) or id in seen:
            fail('Duplicate or unsafe trigger identifier')
        if not isinstance(kind,str) or kind not in ('door','stairs','trigger','checkpoint'):
            fail('Unsupported trigger type')
        seen.add(id)
        if not isinstance(bounds,list) or len(bounds)!=4 or not all(number(v) for v in bounds):
            fail('Trigger requires exact original-pixel rectangle')
        x,y,w,h=bounds
        if x<0 or y<0 or w<=0 or h<=0 or x+w>scene['width'] or y+h>scene['height']:
            fail('Trigger outside original illustration')
        safe_sensors.append({'id':id,'type':kind,'rect':list(map(float,bounds))})
    # Never modify full-body PNG bytes or pose schemas. Original motion metadata remains.
    scene['physics']={'engine':'Matter.js','version':'0.20.0','obstacles':safe_obstacles,
                      'sensors':safe_sensors,'gravity':[0,0],'fixed_step_ms':1000/60,
                      'actor_collision':True,'source_authored_geometry':True}
    return scene

def build_html(approved_zip,out,pixi_js=None,pathfinding_js=None,matter_js=None,max_html_mib=150):
    scene=validate_scene(approved_zip)
    _,px=bundle_path(pixi_js)
    _,pf=locate_pathfinding(pathfinding_js)
    _,mj=locate_matter(matter_js)
    js=Path(__file__).resolve().with_name('matter_runtime.js').read_text('utf8')
    scripts=[]
    for script in (px,pf,mj):
        scripts.append('<script>'+re.sub(r'</script',r'<\\/script',script,flags=re.I)+'</script>')
    comment='Matter.js 0.20.0 MIT: https://github.com/liabru/matter-js . License in upstream distribution; retain original license headers.'
    html=('<!doctype html><html lang="ru"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">'
        '<title>Living Image Animator — interactive 2.5D physics</title>'
        '<style>html,body{margin:0;height:100%;overflow:hidden;background:#080e17;touch-action:none}'
        '#viewport{width:100%;height:100%;display:flex;align-items:center;justify-content:center}'
        'canvas{display:block;image-rendering:pixelated;touch-action:none}'
        '#error{display:none;position:fixed;left:10px;bottom:10px;background:#29101b;color:#fff;padding:12px;border-radius:6px;font:13px system-ui;max-width:90%;z-index:4}'
        '</style></head><body><div id="viewport"></div><div id="error" role="alert"></div>'
        '<!-- '+comment+' -->'+''.join(scripts)+
        '<script id="lia-scene" type="application/json">'+json_inline(scene)+'</script>'+
        '<script>'+re.sub(r'</script',r'<\\/script',js,flags=re.I)+'</script></body></html>')
    if len(html.encode('utf8'))>max_html_mib*1024*1024:fail('One-file HTML exceeds available browser memory budget')
    dest=Path(out).resolve();dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(html,'utf8')
    return dest,{'engine':'Matter.js 0.20.0 + PixiJS 8.23.0 + PathFinding.js 0.4.18',
       'navigated_actors':len(scene['browserNavigation']['actors']),
       'obstacles':len(scene['physics']['obstacles']),'sensors':len(scene['physics']['sensors']),
       'original_png_frames':sum(len(a['frames']) for a in scene['actors']),
       'offline':True,'no_character_deformation':True,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest()}

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--approved-zip',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True);ap.add_argument('--pixi-js',type=Path)
    ap.add_argument('--pathfinding-js',type=Path);ap.add_argument('--matter-js',type=Path)
    a=ap.parse_args();print(json.dumps(build_html(a.approved_zip,a.out,a.pixi_js,a.pathfinding_js,a.matter_js)[1],ensure_ascii=False))
