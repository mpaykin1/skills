#!/usr/bin/env python3
"""Tiled JSON object/image layers -> original-pixel Godot + Blender depth annotations.

Tiled upstream: https://github.com/mapeditor/tiled .  JSON map export is an
interchange file, not a claim that the native Tiled editor is bundled or run.

No sprite image or verified motion gate is modified.  This only creates source-
registered walking polygons, collision rectangles, named waypoint routes, and
transparent depth planes from explicitly authored Tiled layers.
"""
from __future__ import annotations
import io
import json
import math
import os
import tempfile
import zipfile
from pathlib import Path
from PIL import Image

class TiledBridgeError(ValueError): pass

def bad(msg): raise TiledBridgeError('Tiled integration blocked: '+str(msg))
def number(v): return type(v) in (int,float) and math.isfinite(v)
def safe_file(root,relative):
    if not isinstance(relative,str) or not relative or '\\' in relative or ':' in relative:
        bad('Invalid relative path: '+repr(relative))
    pp=Path(relative)
    if pp.is_absolute() or any(p in ('','.','..') for p in relative.split('/')):
        bad('Unsafe relative path: '+relative)
    root=Path(root).resolve();f=(root/pp).resolve()
    if root not in f.parents or not f.is_file():bad('Missing or unsafe source file: '+relative)
    return f

def coords(v,which):
    if not isinstance(v,dict) or not number(v.get('x')) or not number(v.get('y')):
        bad(which+': expected finite x/y')
    return float(v['x']),float(v['y'])

def polygon_area(pts):
    return abs(sum(pts[i][0]*pts[(i+1)%len(pts)][1]-pts[(i+1)%len(pts)][0]*pts[i][1] for i in range(len(pts))))/2

def object_origin(obj,layer):
    if obj.get('visible',True) is not True or layer.get('visible',True) is not True:
        bad('Mapped Tiled objects/layers must be visible and not hidden')
    if obj.get('rotation',0) != 0:bad('Rotated geometry is unsupported; supply unrotated explicit shapes')
    x,y=coords(obj,'object')
    dx,dy=layer.get('offsetx',0),layer.get('offsety',0)
    if not number(dx) or not number(dy):bad('Invalid Tiled layer offset')
    return x+dx,y+dy

def rect(obj,layer,canvas):
    if obj.get('ellipse') or obj.get('point') or obj.get('polygon') or obj.get('polyline') or obj.get('gid') or obj.get('template'):
        bad('Collision objects must be axis-aligned rectangles')
    x,y=object_origin(obj,layer);w,h=obj.get('width',0),obj.get('height',0)
    if not all(map(number,[w,h])) or w<=1 or h<=1 or x<0 or y<0 or x+w>canvas[0] or y+h>canvas[1]:
        bad('Collision rectangle must be inside original source image')
    return [round(x,4),round(y,4),round(float(w),4),round(float(h),4)]

def nav_polygon(obj,layer,canvas):
    x,y=object_origin(obj,layer)
    if any(obj.get(k) for k in ('ellipse','point','polyline','gid','template')):
        bad('Walkable objects must be simple polygons or rectangles')
    if 'polygon' in obj:
        pts=[]
        for pt in obj['polygon']:
            px,py=coords(pt,'polygon point');pts.append([round(x+px,4),round(y+py,4)])
    else:
        _,_,w,h=rect(obj,layer,canvas)
        pts=[[x,y],[x+w,y],[x+w,y+h],[x,y+h]]
    if not 3<=len(pts)<=128 or polygon_area(pts)<16:
        bad('Walkable polygon has insufficient area/vertices')
    if any(not 0<=p[0]<=canvas[0] or not 0<=p[1]<=canvas[1] for p in pts):
        bad('Walkable polygon lies outside original source image')
    return pts

def point(obj,layer,canvas):
    if obj.get('point') is not True or any(obj.get(k) for k in ('polygon','polyline','gid','template','ellipse')):
        bad('Waypoints must be point objects (Tiled point=true)')
    x,y=object_origin(obj,layer)
    if not 0<=x<=canvas[0] or not 0<=y<=canvas[1]:bad('Waypoint is outside source image')
    return [round(x,4),round(y,4)]

def object_layer(layers,name):
    matched=[v for v in layers if isinstance(v,dict) and v.get('name')==name]
    if len(matched)!=1 or matched[0].get('type')!='objectgroup':
        bad('Expected one Tiled objectgroup layer named '+str(name))
    return matched[0]

def image_layer(layers,name):
    matched=[v for v in layers if isinstance(v,dict) and v.get('name')==name]
    if len(matched)!=1 or matched[0].get('type')!='imagelayer':
        bad('Expected one Tiled imagelayer named '+str(name))
    return matched[0]

def compile_geometry(scene_path,source_size):
    scene_path=Path(scene_path).resolve();root=scene_path.parent
    scene=json.loads(scene_path.read_text('utf8'))
    tc=scene.get('tiled')
    if tc is None:return None
    if not isinstance(tc,dict):bad('scene.tiled must be object')
    mp=safe_file(root,tc.get('map_json'))
    if mp.suffix.lower()!='.json':bad('Export the native Tiled map as JSON; .tmx without JSON export is unsupported')
    raw=mp.read_bytes()
    if len(raw)>12_000_000:bad('Tiled map JSON exceeds safe limit')
    cfg=json.loads(raw)
    if not isinstance(cfg,dict) or cfg.get('type')!='map' or cfg.get('orientation')!='orthogonal':
        bad('Only orthogonal Tiled JSON maps are supported; isometric coordinates need explicit projection')
    if cfg.get('infinite',False):bad('Infinite/chunked maps are unsupported for source-registered scenes')
    scalars=[cfg.get(k) for k in ('width','height','tilewidth','tileheight')]
    if any(type(x) is not int or x<=0 for x in scalars):bad('Invalid Tiled source dimensions')
    w,h,tw,th=scalars
    if [w*tw,h*th]!=list(source_size):bad('Tiled map resolution differs from original illustration')
    layers=cfg.get('layers')
    if not isinstance(layers,list) or len(layers)>150:bad('Invalid Tiled layers list')
    if any(layer.get('type')=='group' for layer in layers if isinstance(layer,dict)):
        bad('Group/nested layers are unsupported; export named top-level layers')
    godot=json.loads(json.dumps(scene.get('godot',{})))
    blender=json.loads(json.dumps(scene.get('blender',{})))
    if not isinstance(godot,dict) or not isinstance(blender,dict):bad('Godot/Blender settings must be objects')
    if 'walkable_layer' not in tc or 'obstacle_layer' not in tc:
        bad('Explicit walkable_layer and obstacle_layer names required; no screenshot guessing')
    walk=object_layer(layers,tc['walkable_layer']);block=object_layer(layers,tc['obstacle_layer'])
    polygons=[nav_polygon(o,walk,source_size) for o in walk.get('objects',[])]
    obstacles=[rect(o,block,source_size) for o in block.get('objects',[])]
    if not polygons:bad('Tiled walkable layer has no real authored polygon')
    godot['walkable_polygons']=list(godot.get('walkable_polygons',[]))+polygons
    godot['obstacles']=list(godot.get('obstacles',[]))+obstacles
    nav_cfg=tc.get('navigation_actors',{})
    if not isinstance(nav_cfg,dict):bad('tiled.navigation_actors must be object')
    existing=godot.get('navigation_actors',{})
    if not isinstance(existing,dict):bad('godot.navigation_actors must be object')
    if nav_cfg:
        wp=object_layer(layers,tc.get('waypoint_layer'))
        waypoints={}
        for o in wp.get('objects',[]):
            name=o.get('name')
            if not isinstance(name,str) or not name or name in waypoints:bad('Named waypoints must be unique')
            waypoints[name]=point(o,wp,source_size)
        for actor,request in nav_cfg.items():
            if actor in existing:bad('Duplicate Godot/Tiled navigation definition for '+actor)
            if not isinstance(request,dict) or not isinstance(request.get('waypoint_names'),list) or len(request['waypoint_names'])<2:
                bad(actor+': supply >=2 named Tiled waypoints')
            names=request['waypoint_names']
            if any(n not in waypoints for n in names):bad(actor+': missing Tiled waypoint reference')
            speed=request.get('speed_px_s',24)
            if not number(speed) or not 2<=speed<=500:bad(actor+': invalid navigation speed')
            existing[actor]={'waypoints':[waypoints[n] for n in names],'speed_px_s':float(speed)}
    godot['navigation_actors']=existing
    images={}
    image_cfg=tc.get('image_layers',[])
    if not isinstance(image_cfg,list) or len(image_cfg)>64:bad('Too many Tiled image layers')
    g_layers=godot.setdefault('layers',[])
    b_layers=blender.setdefault('layers',[])
    maproot=mp.parent
    for i,decl in enumerate(image_cfg):
        if not isinstance(decl,dict) or not isinstance(decl.get('layer'),str):bad('Invalid Tiled image layer binding')
        layer=image_layer(layers,decl['layer'])
        if layer.get('visible',True) is not True or layer.get('opacity',1)!=1:
            bad('Exported source-registered depth image must be fully visible and opaque layer opacity')
        if any(layer.get(k,0)!=0 for k in ('x','y','offsetx','offsety')):
            bad('Image depth layer has offset; precompose original canvas and re-export')
        if layer.get('repeatx') or layer.get('repeaty'):
            bad('Repeating depth image layers are not source registered')
        z=decl.get('z_index')
        if not number(z) or not -1000<=z<=1000:bad('Source-authored depth z_index required')
        png=safe_file(maproot,layer.get('image'))
        if png.suffix.lower()!='.png':bad('Tiled depth plates must be PNG')
        with Image.open(png) as image:
            if image.format!='PNG' or image.size!=tuple(source_size):bad('Tiled depth PNG must match original source dimensions')
            lo,hi=image.convert('RGBA').getchannel('A').getextrema()
            if lo==255 or hi==0:bad('Tiled depth plane needs true transparency and visible pixels')
        alias='tiled_layers/layer_%02d.png'%i
        if any(v.get('png')==alias for v in g_layers+b_layers):bad('Tiled image layer output collides with original artwork')
        entry={'name':str(decl['layer']),'png':alias,'z_index':float(z),'visible':True}
        g_layers.append({'png':alias,'z_index':float(z)})
        b_layers.append(entry)
        images['project/inputs/'+alias]=png.read_bytes()
    scene['godot']=godot;scene['blender']=blender
    scene['tiled_compiled']={'map':'original Tiled JSON','projection':'orthogonal','actors_with_routes':sorted(nav_cfg),
                            'walkable_polygons_added':len(polygons),'obstacles_added':len(obstacles),
                            'source_registered_image_planes_added':len(images),'no_generated_animation':True}
    return scene,raw,images

def apply_tiled(assets_zip,original_scene,source_png):
    """Atomic source ZIP update *after* approved pose gate, *before* Godot/Blender.

    Replaces only scene metadata, NEVER original pose PNGs, masks or gate result.
    The original Tiled JSON and image layers are preserved for editing.
    """
    original_scene=Path(original_scene).resolve();assets_zip=Path(assets_zip).resolve()
    with Image.open(source_png) as src: size=src.size
    result=compile_geometry(original_scene,size)
    if result is None:return False
    updated,map_json,images=result
    with zipfile.ZipFile(assets_zip,'r') as old:
        if old.testzip() is not None:bad('Original verified ZIP is damaged')
        files=old.namelist()
        if len(files)!=len(set(files)):bad('Original ZIP contains duplicate members')
        if 'scene.json' not in files or 'motion_gate.json' not in files:bad('Missing original motion certification')
        gate=json.loads(old.read('motion_gate.json'))
        if gate.get('all_actors_pass') is not True:bad('Original animation gate was not passed')
        before=json.loads(old.read('scene.json'))
        if before.get('inventory')!=updated.get('inventory'):
            bad('Verified scene actor roster differs from source Tiled scene')
        # Upstream editor compilers rewrote .tnz/.pxo -> real PNG paths.
        # Keep those exact rendered actor entries and original motion metadata.
        before['godot']=updated['godot'];before['blender']=updated['blender']
        before['tiled_compiled']=updated['tiled_compiled']
        additions={'project/tiled/original_map.json':map_json,
                   'project/tiled/scene.original.json':original_scene.read_bytes(),**images}
        if any(name in files for name in additions):bad('Tiled assets collide with verified source ZIP')
        fd,tmp=tempfile.mkstemp(suffix='.zip',prefix='lia_tiled_',dir=str(assets_zip.parent))
        os.close(fd)
        try:
            with zipfile.ZipFile(tmp,'w') as new:
                for info in old.infolist():
                    # Preserve exact original asset bytes and ZIP member attributes.
                    content=json.dumps(before,ensure_ascii=False,indent=2).encode('utf8') if info.filename=='scene.json' else old.read(info.filename)
                    new.writestr(info,content)
                for name,content in additions.items():
                    new.writestr(name,content,compress_type=zipfile.ZIP_DEFLATED,compresslevel=6)
            with zipfile.ZipFile(tmp) as final:
                if final.testzip() is not None:bad('Updated Tiled ZIP failed CRC validation')
            os.replace(tmp,assets_zip)
        finally:
            if os.path.exists(tmp):os.unlink(tmp)
    return True
