#!/usr/bin/env python3
"""Add the *genuine* SpriteStack2D Godot 4 addon to the original approved Godot game.

Real author-painted Z slices -> orthographic 2x2 projection -> native addon visual hull.
This NEVER alters original Z slices or original 2D full-body pose sources. Godot's
existing actor.gd remains authoritative for animation timing and physics;
new volume views follow the exact selected original sprite frame by identity.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import io
import json
import math
import re
import shutil
import subprocess
import zipfile
from pathlib import Path
import numpy as np
from PIL import Image
from pixijs_bridge import load_scene
from sprite_stack_bridge import stack, within, StackError
from spritestack2d_vendor import validate, REV

class Stack2DBridgeError(ValueError):pass

def fail(s):raise Stack2DBridgeError('SpriteStack2D Godot export blocked: '+str(s))

def number(value,minimum,maximum,label):
    if type(value) not in (int,float) or not math.isfinite(value) or not minimum<=value<=maximum:
        fail(f'{label} must be a finite number between {minimum} and {maximum}')
    return float(value)

def safe_id(s):
    if not isinstance(s,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,59}',s):fail('Unsafe stack object/actor identifier')
    return s

def project_orthographic_sheets(original_stack:dict)->bytes:
    """Four source-pixel projections, no synthetic pixels or hidden-surface inference.

    Addon requires 2x2 4-face canvas, equal cells, top and side point LEFT.
    Top art is turned clockwise because original GDScript turns it CCW.
    """
    layers=[]
    for uri in original_stack['slices']:
        if not uri.startswith('data:image/png;base64,'):fail('Original stack source must be literal original PNG data')
        raw=base64.b64decode(uri.split(',',1)[1],validate=True)
        with Image.open(io.BytesIO(raw)) as im:layers.append(np.asarray(im.convert('RGBA'),dtype=np.uint8))
    v=np.stack(layers)     # bottom z=0 -> top z=N-1; y=front toward large indices
    n,w_y,w_x,_=v.shape
    if w_x!=w_y:fail('True source stacks must have square matching XY slices')
    cell=max(w_x,n)
    if cell>512:fail('Native addon source cell exceeds 512px budget')
    xyoff=(cell-w_x)//2
    top=np.zeros((cell,cell,4),dtype=np.uint8)
    front=np.zeros_like(top);side=np.zeros_like(top);back=np.zeros_like(top)
    # Topmost original painted pixel in each authored XY column.
    for z in range(n):
        sl=v[z];hit=sl[:,:,3]>0
        region=top[xyoff:xyoff+w_y,xyoff:xyoff+w_x]
        region[hit]=sl[hit]
    # Complete original XY/Z projection: every non-empty pixel is copied exactly
    # from one existing Z slice, not resampled or fabricated.
    for z in range(n):
        sl=v[z];row=cell-1-z
        for y in range(w_y):
            hits=sl[y,:,3]>0
            cols=np.flatnonzero(hits)
            front[row,xyoff+cols]=sl[y,cols]
        for y in range(w_y-1,-1,-1):
            hits=sl[y,:,3]>0
            cols=np.flatnonzero(hits)
            back[row,cell-1-(xyoff+cols)]=sl[y,cols]
        for x in range(w_x):
            hits=sl[:,x,3]>0
            ys=np.flatnonzero(hits)
            side[row,cell-1-(xyoff+ys)]=sl[ys,x]
    # Underlying source XY plan is rotated anti-clockwise by the upstream addon.
    top_face=Image.fromarray(top,'RGBA').transpose(Image.Transpose.ROTATE_270)
    sheet=Image.new('RGBA',(cell*2,cell*2))
    for pos,pixels in [((0,0),top_face),((cell,0),Image.fromarray(front,'RGBA')),
                       ((0,cell),Image.fromarray(side,'RGBA')),
                       ((cell,cell),Image.fromarray(back,'RGBA'))]:sheet.paste(pixels,pos)
    buf=io.BytesIO();sheet.save(buf,'PNG',compress_level=7)
    return buf.getvalue()

def _artist_sheet(root,relative):
    path=within(root,relative)
    if path.stat().st_size>12_000_000:fail('Artist original four-view PNG exceeds 12MiB')
    raw=path.read_bytes()
    with Image.open(io.BytesIO(raw)) as img:
        if img.format!='PNG' or img.mode not in ('RGBA','LA','P'):
            fail('Four artist-provided faces must be transparent original PNG')
        w,h=img.size
        if w!=h or w%2!=0 or w//2>512 or w//2<16:fail('SpriteStack2D 2x2 face sheet must contain square matching cells')
        a=np.asarray(img.convert('RGBA').getchannel('A'))
        c=w//2
        for xx,yy in [(0,0),(c,0),(0,c),(c,c)]:
            q=a[yy:yy+c,xx:xx+c]
            if np.max(q)==0:fail('Every TOP FRONT SIDE BACK authored view must contain original painted pixels')
        if np.min(a)==255:fail('Four original views need true transparent background')
    return raw

def stack_sheet(root,relative,expected_pose_sha,faces,cache):
    cachekey=(relative,expected_pose_sha,faces)
    if cachekey in cache:return cache[cachekey]
    genuine,raw_budget=stack(root,relative,expected_pose_sha)
    if faces:
        sheet=_artist_sheet(root,faces)
        method='author_original_4view_sheet'
    else:
        sheet=project_orthographic_sheets(genuine)
        method='orthographic_original_rgba_slice_projection'
    cache[cachekey]=(sheet,{'source_stack_sha256':genuine['sha256'],'projection':method,
                           'source_stack_layers':genuine['depth'],'source_stack_file':relative,
                           'source_pose_sha256':expected_pose_sha,'original_unmodified':True})
    return cache[cachekey]

def config(approved_zip,scene_path,root,project_dir):
    approved=load_scene(approved_zip)
    with zipfile.ZipFile(approved_zip) as z:
        if z.testzip():fail('Original full-cel animation ZIP is corrupt')
        original=json.loads(z.read('scene.json'))
        if json.loads(z.read('motion_gate.json')).get('all_actors_pass') is not True:
            fail('Original full-body source pose quality gate did not pass')
        exact=json.loads(scene_path.read_text('utf8'))
        if (exact.get('inventory')!=original.get('inventory') or exact.get('sprite_stacking')!=original.get('sprite_stacking') or exact.get('sprite_stack2d',{})!=original.get('sprite_stack2d',{})):
            fail('Godot stacks must match already approved source inventory and 3D stack declarations')
        cfg=original.get('sprite_stacking')
        if not isinstance(cfg,dict) or cfg.get('enabled',True) is not True:
            fail('Original scene.sprite_stacking must already contain genuine approved Z-slice stacks')
        adapter=exact.get('sprite_stack2d',{})
        if not isinstance(adapter,dict) or set(adapter)-{'world_positions','face_sheets','actor_offsets','directions','x_rotations','z_distance','shadow','clean_plate'}:
            fail('Unsupported scene.sprite_stack2d addon options')
        dirs=adapter.get('directions',16)
        if type(dirs) is not int or dirs not in (4,8,16,32,64,90,120,180,360):fail('Godot native stack direction budget must be 4/8/16/32/64/90/120/180/360')
        camera=number(adapter.get('x_rotations',65),1,90,'native Godot stack camera elevation')
        zd=adapter.get('z_distance',1)
        if type(zd) is not int or not 0<=zd<=16:fail('z_distance must be 0..16 pixels')
        shadow=adapter.get('shadow',False)
        if type(shadow) is not bool:fail('shadow must be boolean')
        face_sheets=adapter.get('face_sheets',{})
        world_positions=adapter.get('world_positions',{})
        actor_offsets=adapter.get('actor_offsets',{})
        for label,thing in [('face_sheets',face_sheets),('world_positions',world_positions),('actor_offsets',actor_offsets)]:
            if not isinstance(thing,dict):fail(label+' must be an object')
        sources=cfg.get('objects',[]);actor_sources=cfg.get('actors',[])
        if not isinstance(sources,list) or not isinstance(actor_sources,list) or not (sources or actor_sources):
            fail('No source-authored stacks declared in original scene')
        if len(sources)+len(actor_sources)>100:fail('Too many authored sprite volumes for Godot source scene')
        # Stack painted objects only over a genuinely author-cleaned source plate.
        # The previous 2D Godot ZIP still retains its original unmodified background.
        if sources:
            clean=adapter.get('clean_plate')
            if not isinstance(clean,str):fail('A source-authored sprite_stack2d.clean_plate is required with static stacked objects to avoid duplicated original architecture')
            clean_path=within(root,clean)
            with Image.open(clean_path) as plate:
                if plate.format!='PNG' or plate.size!=(approved['width'],approved['height']):
                    fail('Stacked native Godot background must be original source-aligned PNG')
                if plate.mode not in ('RGB','RGBA','P'):
                    fail('Source-clean plate requires color PNG')
            shutil.copyfile(clean_path,project_dir/'textures/background.png')
        actors={a['id']:a for a in original['actors']}
        if cfg.get('environment_only',False) and actor_sources:fail('environment_only scene cannot quietly include 3D actors')
        bound={a.get('actor_id') for a in actor_sources}
        if not cfg.get('environment_only',False) and bound!=set(actors):
            fail('A full Godot 3D cast must have original frame stacks for EVERY certified actor')
        ids=set()
        for e in sources:
            if not isinstance(e,dict):fail('Invalid source stack object')
            name=safe_id(e.get('id'))
            if name in ids:fail('Duplicate stack object identifier')
            ids.add(name)
        for e in actor_sources:
            name=safe_id(e.get('actor_id'))
            if name not in actors or name in ids:fail('Duplicate/unknown original stack actor')
            ids.add(name)
        eligible=cfg.get('eligible_object_ids',[])
        if not isinstance(eligible,list) or not eligible or len(set(eligible))!=len(eligible):fail('The original full-coverage sprite stack inventory is missing')
        if not ids.issubset(set(eligible)):fail('Stacked objects are not in approved source inventory')
        coverage=number(cfg.get('coverage_min',.9),.75,1,'stack coverage minimum')
        if len(ids)/len(eligible)<coverage:fail('Unstacked source inventory below original minimum coverage')
        if set(face_sheets)-{o.get('stack') for o in sources if isinstance(o,dict)}-{p for a in actor_sources for seq in (a.get('clips') or {}).values() for p in seq}:
            fail('face_sheets references undeclared source stack manifests')
        path=project_dir/'stack2d'
        path.mkdir(parents=True,exist_ok=True)
        cell_budget=0;total_sheets=0;original_files={};sheet_cache={};stored={};objects=[];outactors=[]
        copied_source_paths=set();copied_source_bytes=0
        def save_sheet(rel,pose=None):
            nonlocal cell_budget,total_sheets
            faces=face_sheets.get(rel)
            binary,meta=stack_sheet(root,rel,pose,faces,sheet_cache)
            h=hashlib.sha256(binary).hexdigest()
            with Image.open(io.BytesIO(binary)) as im:rgba_bytes=im.width*im.height*4
            if h not in stored:
                cell_budget+=rgba_bytes;total_sheets+=1
                if cell_budget>160_000_000 or total_sheets>250:
                    fail('Native Godot sprite view cache >160MB or >250 authored view sequences; use original source lower-LOD packs')
                output=f'stack2d/views/{h[:20]}.png'
                (project_dir/output).parent.mkdir(parents=True,exist_ok=True)
                (project_dir/output).write_bytes(binary)
                stored[h]='res://'+output
            # Preserve editable original source slices and stack manifest byte-for-byte.
            nonlocal copied_source_bytes
            if rel not in original_files:
                original_path=within(root,rel)
                manifest=json.loads(original_path.read_text('utf8'))
                original_members=[(original_path,Path(rel))]
                for layer in manifest['layers']:
                    member=(Path(rel).parent/layer).as_posix()
                    original_members.append((within(root,member),Path(member)))
                for source_file,member in original_members:
                    relname=member.as_posix()
                    if relname in copied_source_paths:continue
                    copied_source_paths.add(relname)
                    copied_source_bytes+=source_file.stat().st_size
                    if copied_source_bytes>256_000_000:fail('Original source Z-slice archive exceeds 256MiB; use an authored source LOD')
                    output=project_dir/'stack2d/source'/member
                    output.parent.mkdir(parents=True,exist_ok=True)
                    shutil.copyfile(source_file,output)
            original_files[rel]=meta
            return stored[h]
        for item in sources:
            name=safe_id(item['id'])
            if item.get('motion') or item.get('parent'):
                # Existing Three.js/PixiJS retains those mechanisms. Do not claim a rigid
                # source-world hinge runs via this native Godot-only view node.
                fail('Rigid parent/hinge stack requires the existing Three.js/PixiJS motion engine; native Godot SpriteStack2D output supports independently static source objects')
            if name not in world_positions:fail('Add source-pixel sprite_stack2d.world_positions for '+name+'; 3D coordinates cannot be guessed as 2D map pixels')
            xy=world_positions[name]
            if not isinstance(xy,list) or len(xy)!=2:fail('world_positions.'+name+' must be source [x,y]')
            x=number(xy[0],0,approved['width'],'x');y=number(xy[1],0,approved['height'],'y')
            objects.append({'id':name,'sheet':save_sheet(item['stack']),'xy':[x,y],
                            'yaw':number(item.get('yaw',0),-360,360,'object yaw'),
                            'z':int(number(item['position'][2],-10000,10000,'object z')) if isinstance(item.get('position'),list) and len(item['position'])==3 else 0})
        original_project_scene=json.loads((project_dir/'data/scene.json').read_text('utf8'))
        godot_actors={a['id']:a for a in original_project_scene['actors']}
        for item in actor_sources:
            name=safe_id(item['actor_id'])
            if name not in godot_actors:fail('Original Godot actor missing '+name)
            source_actor=actors[name];clips=item.get('clips')
            if not isinstance(clips,dict) or set(clips)!={c['action'] for c in source_actor['clips']}:
                fail('All original actor actions must supply whole-body 3D pose stacks')
            offset=actor_offsets.get(name,[source_actor['box'][2]*.5,source_actor['box'][3]*.5])
            if not isinstance(offset,list) or len(offset)!=2:fail('actor_offsets must be 2D source-pixel offsets')
            off=[number(c,-2048,2048,'actor stack art offset') for c in offset]
            paths=[];source_count=0
            for clip in source_actor['clips']:
                views=clips[clip['action']]
                if not isinstance(views,list) or len(views)!=len(clip['frames']):
                    fail('One original full-volume stack required per original pose for '+name+'/'+clip['action'])
                clip_sheets=[]
                for rel,fr in zip(views,clip['frames']):
                    pose_data=z.read('project/inputs/'+fr['png'])
                    path=save_sheet(rel,hashlib.sha256(pose_data).hexdigest())
                    paths.append(path);clip_sheets.append(path)
                    source_count+=1
                if clip['action']!='idle':
                    if len(set(clip_sheets))<8:
                        fail(name+'/'+clip['action']+': 3D actor poses remain static or reused; >=8 distinct full-volume painted poses required, not just unique manifest provenance')
                    silhouettes=set()
                    for face in clip_sheets:
                        sheetpath=project_dir/face.removeprefix('res://')
                        with Image.open(sheetpath) as image:
                            silhouettes.add(hashlib.sha256(image.getchannel('A').tobytes()).digest())
                    if len(silhouettes)<4:
                        fail(name+'/'+clip['action']+': 3D source silhouette does not actually animate; need >=4 distinct approved body shapes')
            if len(set(paths))<16:fail(name+': overall native Godot full-volume sequence contains fewer than 16 distinct authored 3D poses')
            if len(paths)!=len(godot_actors[name]['sprite_paths']):fail('Godot original actor PNG roster changed')
            outactors.append({'actor_id':name,'sheets':paths,'offset':off,'yaw':number(item.get('yaw',0),-360,360,'actor yaw')})
        return {'engine':'SpriteStack2D','upstream_commit':REV,'projection_warning':'Four orthographic projections preserve source pixels but visual-hull carving may fill hidden cavities; original GLSL Z-slice renderer is reference truth',
                'quality_gate':'unchanged_original_full_body_pose_gate','all_actors_stacked':len(outactors)==len(actors),
                'fps':original_project_scene['fps'],'config':{'directions':dirs,'x_rotations':camera,'z_distance':zd,'shadow':shadow},
                'objects':objects,'actors':outactors,'source_stack_evidence':original_files,
                'source_image_rgba_modified':False,'source_3d_stacks_modified':False,
                'derived_sheet_count':total_sheets,'derived_view_memory_bytes':cell_budget,'source_z_stack_bytes_included':copied_source_bytes}

STACK_WORLD=r'''extends Node2D
## Real MIT SpriteStack2D addon + original independently painted full-body animation.
## The previously authored ActorScript remains the sole movement/physics authority.
const StackClass = preload("res://addons/sprite_stack_2d/sprite_stack_2d.gd")
var world: Node2D
var active: Array = []
var settings: Dictionary = {}

func _ready() -> void:
    var payload: Variant = JSON.parse_string(FileAccess.get_file_as_string("res://data/spritestack2d.json"))
    if not (payload is Dictionary):
        push_error("Approved SpriteStack2D data missing")
        return
    settings = payload.get("config", {})
    var main: PackedScene = load("res://Main.tscn")
    world = main.instantiate()
    add_child(world)
    for object in payload.get("objects", []):
        var volume = _new_stack(object["sheet"],float(object.get("yaw",0.0)))
        volume.name = str(object["id"])
        volume.position = Vector2(float(object["xy"][0]),float(object["xy"][1]))
        volume.z_index = int(object.get("z",0))
        add_child(volume)
    for data in payload.get("actors", []):
        var aid: String = str(data["actor_id"])
        var character = world.get_node_or_null(NodePath(aid))
        if character == null or character.sprite == null:
            push_error("Approved original Godot actor unavailable: "+aid)
            continue
        if data["sheets"].size() != character.images.size():
            push_error("Original complete-pose source count changed: "+aid)
            continue
        var visual = _new_stack(data["sheets"][0],float(data.get("yaw",0.0)))
        visual.name = "OriginalFullVolumePose"
        visual.position = Vector2(float(data["offset"][0]),float(data["offset"][1]))
        character.add_child(visual)
        # Original actor still updates its source sprite timeline and all collisions.
        # Only the visual output of this EXACT actor is replaced by native 3D slices.
        character.sprite.visible = false
        active.append({"actor":character,"visual":visual,"sheet_paths":data["sheets"],"last":0})

func _new_stack(path: String,yaw:float) -> Node2D:
    var node = StackClass.new()
    node.texture = load(path)
    if node.texture == null:push_error("Original source-derived SpriteStack2D views missing: "+path)
    node.pixelated = true
    node.directions = int(settings.get("directions",16))
    node.x_rotations = float(settings.get("x_rotations",65.0))
    node.z_distance = int(settings.get("z_distance",1))
    node.y_rotations = yaw
    node.enable_shadow = bool(settings.get("shadow",false))
    node.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
    return node

func _process(_delta:float) -> void:
    for item in active:
        var actor = item["actor"]
        var idx:int = actor.images.find(actor.sprite.texture)
        if idx < 0 or idx >= item["sheet_paths"].size():
            push_error("Unapproved actor pose texture during Godot SpriteStack2D playback")
            continue
        if idx != int(item["last"]):
            item["visual"].texture = load(item["sheet_paths"][idx])
            item["last"] = idx
'''

STACK_SCENE='''[gd_scene load_steps=2 format=3]
[ext_resource type="Script" path="res://scripts/stack_world.gd" id="1_stack"]
[node name="LivingStackWorld" type="Node2D"]
script = ExtResource("1_stack")
'''

def project(approved_zip,scene_path,existing_godot,addon,output,godot_binary=None):
    approved_zip=Path(approved_zip).resolve();scene_path=Path(scene_path).resolve()
    existing_godot=Path(existing_godot).resolve();output=Path(output).resolve()
    if output.exists():fail('Destination exists; use a new artifact directory')
    for file in ['project.godot','Main.tscn','scripts/main.gd','scripts/actor.gd','data/scene.json']:
        if not (existing_godot/file).is_file():fail('Previously validated original Godot project is incomplete: '+file)
    upstream,lic=validate(addon)
    shutil.copytree(existing_godot,output,ignore=shutil.ignore_patterns('.godot'))
    target=output/'addons/sprite_stack_2d';target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copytree(upstream,target,ignore=shutil.ignore_patterns('*.uid','*.import'))
    (output/'LICENSE.SpriteStack2D.txt').write_bytes(lic.read_bytes())
    payload=config(approved_zip,scene_path,scene_path.parent,output)
    (output/'data/spritestack2d.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),'utf8')
    (output/'scripts/stack_world.gd').write_text(STACK_WORLD,'utf8')
    (output/'StackWorld.tscn').write_text(STACK_SCENE,'utf8')
    project_config=(output/'project.godot').read_text('utf8')
    needle='run/main_scene="res://Main.tscn"'
    if project_config.count(needle)!=1:fail('Original source Godot project main_scene changed unexpectedly')
    project_config=project_config.replace(needle,'run/main_scene="res://StackWorld.tscn"',1)
    project_config+='\n[editor_plugins]\nenabled=PackedStringArray("res://addons/sprite_stack_2d/plugin.cfg")\n'
    (output/'project.godot').write_text(project_config,'utf8')
    if godot_binary:
        exe=shutil.which(str(godot_binary)) or (str(Path(godot_binary).resolve()) if Path(godot_binary).is_file() else None)
        if not exe:fail('Godot executable missing')
        p=subprocess.run([exe,'--headless','--editor','--path',str(output),'--quit'],capture_output=True,text=True,timeout=150,check=False)
        if p.returncode:fail('Native Godot SpriteStack2D editor import failed: '+(p.stderr+'\n'+p.stdout)[-1700:])
    archive=output.parent/'living_scene_godot_spritestack2d.zip'
    if archive.exists():fail('Existing native Godot stack package must not be overwritten')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=7) as z:
        for p in sorted(output.rglob('*')):
            if p.is_file() and '.godot' not in p.parts:z.write(p,'living_scene_godot_spritestack2d/'+p.relative_to(output).as_posix())
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None:fail('Native Godot package is corrupt')
    return archive,{'actor_volumes':len(payload['actors']),'environment_volumes':len(payload['objects']),
                   'original_actor_count':len(load_scene(approved_zip)['actors']),
                   'original_poses_unchanged':True,'original_godot_project_preserved':True,
                   'native_godot_verified':bool(godot_binary),'derived_view_sheets':payload['derived_sheet_count'],
                   'upstream_revision':REV}

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--approved-zip',type=Path,required=True)
    a.add_argument('--scene',type=Path,required=True);a.add_argument('--godot-project',type=Path,required=True)
    a.add_argument('--addon-root',type=Path,required=True);a.add_argument('--out',type=Path,required=True)
    a.add_argument('--godot');v=a.parse_args()
    print(json.dumps(project(v.approved_zip,v.scene,v.godot_project,v.addon_root,v.out,v.godot)[1],ensure_ascii=False))
