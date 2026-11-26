#!/usr/bin/env python3
"""LDtk (.ldtk + optional external level JSON) -> Tiled-compatible Godot/Blender world layers.

Only authoritative LDtk IntGrid and Entity data are used. Actor art/cels are
preserved byte for byte and the motion gate runs BEFORE this bridge.
See https://ldtk.io/json/ ; LDtk is MIT-licensed, editor not bundled.
"""
from __future__ import annotations
import copy
import json
import math
import os
import re
import tempfile
import zipfile
from pathlib import Path
from PIL import Image

class LDtkBridgeError(ValueError): pass

def block(m): raise LDtkBridgeError('LDtk blocked: '+str(m))
def finite(v): return type(v) in (int,float) and math.isfinite(v)
def safe(root, name):
    if not isinstance(name,str) or not name or '\\' in name or ':' in name:
        block('Expected safe relative file name')
    if Path(name).is_absolute() or any(x in ('','.','..') for x in name.split('/')):
        block('Unsafe map/texture path: '+name)
    root=Path(root).resolve();path=(root/name).resolve()
    if root not in path.parents or not path.is_file():block('Missing/outside map source: '+name)
    return path

def read_json(path,limit=16_000_000):
    if path.stat().st_size>limit:block('Map file too large')
    try:data=json.loads(path.read_text('utf-8'))
    except (OSError,ValueError,UnicodeError) as ex:block('Invalid source JSON: '+str(ex))
    if not isinstance(data,dict):block('LDtk JSON root must be an object')
    return data

def levels_in(project):
    # LDtk supports both legacy root levels[] and MultiWorld worlds[].levels[].
    worlds=project.get('worlds')
    if worlds:
        if not isinstance(worlds,list):block('Invalid MultiWorld worlds list')
        out=[]
        for w in worlds:
            if not isinstance(w,dict) or not isinstance(w.get('levels'),list):block('Invalid LDtk world')
            out.extend(w['levels'])
        return out
    levels=project.get('levels',[])
    if not isinstance(levels,list):block('Invalid LDtk levels')
    return levels

def select_level(project,folder,requested):
    levels=levels_in(project)
    if not levels:block('LDtk project has no levels')
    if requested is None:
        if len(levels)!=1:block('Multiple LDtk levels; explicit scene.ldtk.level identifier/iid required')
        candidates=levels
    else:
        candidates=[lv for lv in levels if isinstance(lv,dict) and requested in (lv.get('identifier'),lv.get('iid'))]
    if len(candidates)!=1:block('Level selection is missing or ambiguous')
    summary=candidates[0]
    ext=summary.get('externalRelPath')
    referenced=[]
    if ext:
        f=safe(folder,ext);level=read_json(f);referenced.append((ext,f.read_bytes()))
        for k in ('iid','identifier','pxWid','pxHei'):
            if summary.get(k) is not None and level.get(k) is not None and level[k]!=summary[k]:
                block('External LDtk level '+k+' does not match project level summary')
        level={**summary,**level}
    else:level=summary
    if not isinstance(level.get('layerInstances'),list):
        block('Level layers unavailable; export external level JSON alongside .ldtk')
    return level,referenced

def validate_layers(level):
    layers=level['layerInstances']
    ids=[layer.get('__identifier') for layer in layers if isinstance(layer,dict)]
    if len(ids)!=len(layers) or len(set(ids))!=len(ids) or not all(isinstance(x,str) and x for x in ids):
        block('LDtk level must have unique named layer instances')
    return {layer['__identifier']:layer for layer in layers}

def grid_rects(grid,values,source_size):
    """Maximal vertical merge of horizontal IntGrid runs, without pixel guessing."""
    w=grid.get('__cWid');h=grid.get('__cHei');g=grid.get('__gridSize')
    csv=grid.get('intGridCsv')
    if not all(type(x) is int and x>0 for x in (w,h,g)) or w*h>1_000_000:
        block('Invalid or huge LDtk IntGrid geometry')
    if not isinstance(csv,list) or len(csv)!=w*h or not all(type(x) is int and x>=0 for x in csv):
        block('LDtk IntGrid must have original intGridCsv per-cell integer data')
    dx=grid.get('__pxTotalOffsetX',0);dy=grid.get('__pxTotalOffsetY',0)
    if not all(finite(v) for v in (dx,dy)) or dx or dy:
        block('LDtk IntGrid pixel offset is unsupported; register level at [0,0]')
    if (w*g,h*g)!=tuple(source_size):block('LDtk IntGrid dimensions differ from original image')
    active={};out=[]
    for iy in range(h):
        spans=[];ix=0
        while ix<w:
            if csv[iy*w+ix] not in values:ix+=1;continue
            st=ix
            while ix<w and csv[iy*w+ix] in values:ix+=1
            spans.append((st,ix-st))
        updated={}
        for k in spans:
            if k in active:
                r=active[k];r[3]+=g;updated[k]=r
            else:updated[k]=[k[0]*g,iy*g,k[1]*g,g]
        out.extend(r for k,r in active.items() if k not in updated)
        active=updated
    out.extend(active.values())
    return out

def rect_poly(r):
    x,y,w,h=r
    return [[x,y],[x+w,y],[x+w,y+h],[x,y+h]]

def valid_box(box,size):
    if len(box)!=4 or not all(finite(v) for v in box):block('Invalid entity bounds')
    x,y,w,h=box
    if w<=1 or h<=1 or x<0 or y<0 or x+w>size[0] or y+h>size[1]:
        block('LDtk geometry outside original scene dimensions')
    return [round(float(v),5) for v in box]

def entity_position(ent,layer):
    xy=ent.get('px');pivot=ent.get('__pivot',[0,0]);
    if not (isinstance(xy,list) and len(xy)==2 and all(finite(v) for v in xy)):
        block('LDtk entity needs finite px=[x,y]')
    if not (isinstance(pivot,list) and len(pivot)==2 and all(finite(v) and 0<=v<=1 for v in pivot)):
        block('LDtk entity requires __pivot=[0..1,0..1]')
    ox=layer.get('__pxTotalOffsetX',0);oy=layer.get('__pxTotalOffsetY',0)
    if not all(finite(n) for n in (ox,oy)):block('Malformed LDtk entity layer offset')
    return float(xy[0]+ox),float(xy[1]+oy),pivot

def entities_from(layer,classes,size):
    geometry={'walkable':[],'obstacle':[],'waypoint':{},'portals':[]}
    if layer is None:return geometry
    if layer.get('__type')!='Entities':block('Requested LDtk marker layer is not Entities')
    for ent in layer.get('entityInstances',[]):
        if not isinstance(ent,dict):block('Malformed LDtk entity')
        name=ent.get('__identifier')
        role=next((r for r,declared in classes.items() if declared==name),None)
        if role is None:continue
        px,py,pivot=entity_position(ent,layer)
        if role in ('walkable','obstacle'):
            w=ent.get('width');h=ent.get('height')
            if not finite(w) or not finite(h):block(name+': invalid size')
            box=valid_box([px-w*pivot[0],py-h*pivot[1],w,h],size)
            geometry[role].append(rect_poly(box) if role=='walkable' else box)
            continue
        if not 0<=px<=size[0] or not 0<=py<=size[1]:block('LDtk waypoint outside canvas')
        fields=ent.get('fieldInstances',[])
        if not isinstance(fields,list):block('LDtk entity fields must be array')
        names=[f.get('__value') for f in fields if isinstance(f,dict) and f.get('__identifier')=='Name']
        token=(names[0] if len(names)==1 and isinstance(names[0],str) and names[0] else ent.get('iid'))
        if not isinstance(token,str) or not token or token in geometry['waypoint']:
            block('Door/stairs/waypoint requires unique Name field or IID')
        geometry['waypoint'][token]=[round(px,5),round(py,5)]
        if role in ('door','stairs'):
            geometry['portals'].append({'id':token,'kind':role,'point':[round(px,5),round(py,5)],
                                        'runtime_transition':False})
    return geometry

def apply_ldtk(assets_zip, original_scene, source_png):
    """Merge LDtk into ALREADY approved ZIP after Tiled; preserve all GIF/pose bytes."""
    original_scene=Path(original_scene).resolve();root=original_scene.parent
    config=read_json(original_scene)
    cc=config.get('ldtk')
    if cc is None:return False
    if not isinstance(cc,dict):block('scene.ldtk must be object')
    with Image.open(source_png) as img:source_size=img.size
    path=safe(root,cc.get('project'))
    if path.suffix.lower() not in ('.ldtk','.json'):block('LDtk native project must be .ldtk JSON')
    doc=read_json(path)
    if not isinstance(doc.get('jsonVersion'),str):block('Not a native LDtk project (missing jsonVersion)')
    lv,extra=select_level(doc,path.parent,cc.get('level'))
    if [lv.get('pxWid'),lv.get('pxHei')]!=list(source_size):
        block('Selected LDtk level must match whole source illustration (no implicit projection)')
    layers=validate_layers(lv)
    walk=[];obstacles=[];waypoints={};portals=[]
    gname=cc.get('intgrid_layer')
    if gname is not None:
        grid=layers.get(gname)
        if not grid or grid.get('__type')!='IntGrid':block('Missing IntGrid layer: '+str(gname))
        vwalk=cc.get('walkable_values');vblock=cc.get('obstacle_values')
        if not isinstance(vwalk,list) or not vwalk or not all(type(i) is int and i>0 for i in vwalk):
            block('Explicit positive walkable_values required')
        if not isinstance(vblock,list) or not all(type(i) is int and i>0 for i in vblock):
            block('Explicit obstacle_values list required')
        if set(vwalk)&set(vblock):block('Walkable/blocked IntGrid classes overlap')
        walk.extend(rect_poly(r) for r in grid_rects(grid,set(vwalk),source_size))
        obstacles.extend(grid_rects(grid,set(vblock),source_size))
    markers=cc.get('entity_layer')
    if markers is not None:
        types=cc.get('entity_types',{'walkable':'Walkable','obstacle':'Obstacle','waypoint':'Waypoint','door':'Door','stairs':'Stairs'})
        if not isinstance(types,dict) or set(types)-{'walkable','obstacle','waypoint','door','stairs'} or not all(isinstance(v,str) and v for v in types.values()) or len(set(types.values()))!=len(types):
            block('LDtk entity_types must have distinct identifier strings')
        if markers not in layers:block('Entity marker layer missing '+str(markers))
        data=entities_from(layers[markers],types,source_size)
        walk.extend(data['walkable']);obstacles.extend(data['obstacle']);waypoints.update(data['waypoint']);portals+=data['portals']
    if not walk:block('Selected LDtk level has no explicitly marked walkable geometry')
    source_files={'project/ldtk/original_project.ldtk':path.read_bytes(),
                  'project/ldtk/scene.original.json':original_scene.read_bytes()}
    for idx,(_,payload) in enumerate(extra):
        source_files[f'project/ldtk/external_level_{idx:03d}.json']=payload
    planes=[]
    for i,entry in enumerate(cc.get('image_layers',[])):
        if not isinstance(entry,dict) or not isinstance(entry.get('png'),str) or not finite(entry.get('z_index')):
            block('LDtk image_layers requires png,z_index')
        if not -1000<=entry['z_index']<=1000:block('LDtk z_index outside valid range')
        related=entry.get('layer')
        if related is not None and related not in layers:block('Linked LDtk layer not in selected level: '+str(related))
        source=safe(root,entry['png'])
        with Image.open(source) as png:
            if png.format!='PNG' or png.size!=source_size:block('LDtk image plate must be source-registered PNG')
            lo,hi=png.convert('RGBA').getchannel('A').getextrema()
            if lo==255 or hi==0:block('LDtk image plate requires real transparency')
        alias=f'ldtk_layers/layer_{i:03d}.png';source_files['project/inputs/'+alias]=source.read_bytes()
        planes.append({'png':alias,'z_index':float(entry['z_index']),
                       'name':str(related or 'LDtk-depth-'+str(i)),'visible':True})
    settings=cc.get('navigation_actors',{})
    if not isinstance(settings,dict):block('ldtk.navigation_actors must be object')
    nav={}
    for actor,rule in settings.items():
        if not isinstance(rule,dict) or not isinstance(rule.get('waypoint_names'),list):
            block('LDtk actor navigation requires waypoint_names')
        names=rule['waypoint_names'];speed=rule.get('speed_px_s',24)
        if len(names)<2 or len(names)>64 or any(not isinstance(n,str) or n not in waypoints for n in names):
            block(str(actor)+': missing/invalid named LDtk waypoints')
        if not finite(speed) or not 2<=speed<=500:block('Invalid actor navigation speed')
        nav[actor]={'waypoints':[waypoints[n] for n in names],'speed_px_s':float(speed)}
    assets_zip=Path(assets_zip).resolve()
    with zipfile.ZipFile(assets_zip,'r') as orig:
        if orig.testzip() is not None:block('Original pose ZIP is corrupt')
        old=orig.namelist()
        if len(old)!=len(set(old)) or 'scene.json' not in old or 'motion_gate.json' not in old:
            block('Missing/duplicate verified source scene members')
        gate=json.loads(orig.read('motion_gate.json'))
        if gate.get('all_actors_pass') is not True:block('Original animation gate has not passed')
        scene=json.loads(orig.read('scene.json'))
        if scene.get('inventory')!=config.get('inventory'):
            block('Original verified character inventory changed')
        godot=copy.deepcopy(scene.get('godot',{}));blender=copy.deepcopy(scene.get('blender',{}))
        if not isinstance(godot,dict) or not isinstance(blender,dict):block('Godot/Blender source invalid')
        glist=godot.setdefault('walkable_polygons',[]);olist=godot.setdefault('obstacles',[])
        nmap=godot.setdefault('navigation_actors',{});gplanes=godot.setdefault('layers',[])
        bplanes=blender.setdefault('layers',[])
        if any(k in nmap for k in nav):block('Tiled/Godot/LDtk navigation actor assignment collides')
        glist.extend(walk);olist.extend(obstacles);nmap.update(nav)
        if len(glist)>32 or len(olist)>128:block('Godot navigation shape limits exceeded; simplify LDtk geometry')
        gplanes.extend({'png':p['png'],'z_index':p['z_index']} for p in planes)
        bplanes.extend(planes)
        scene['godot']=godot;scene['blender']=blender
        scene['ldtk_compiled']={'level':lv.get('identifier'),'iid':lv.get('iid'),
            'walkable_polygons_added':len(walk),'collision_rects_added':len(obstacles),
            'doors_stairs':portals,'navigation_actor_ids':sorted(nav),
            'image_planes_added':len(planes),'no_generated_character_frames':True,
            'source':'official LDtk JSON'}
        source_files['project/ldtk/navigation_annotations.json']=json.dumps(
            scene['ldtk_compiled'],ensure_ascii=False,indent=2).encode('utf-8')
        if any(n in old for n in source_files):block('LDtk asset member name conflicts with prior editor')
        fd,temp=tempfile.mkstemp(suffix='.zip',prefix='lia_ldtk_',dir=str(assets_zip.parent))
        os.close(fd)
        try:
            with zipfile.ZipFile(temp,'w') as dest:
                for info in orig.infolist():
                    content=json.dumps(scene,ensure_ascii=False,indent=2).encode('utf8') if info.filename=='scene.json' else orig.read(info.filename)
                    dest.writestr(info,content)
                for n,payload in source_files.items():
                    dest.writestr(n,payload,compress_type=zipfile.ZIP_DEFLATED,compresslevel=6)
            with zipfile.ZipFile(temp) as verify:
                if verify.testzip() is not None:block('LDtk result ZIP corrupt')
            os.replace(temp,assets_zip)
        finally:
            if os.path.exists(temp):os.unlink(temp)
    return True
