#!/usr/bin/env python3
"""Godot 4 project exporter for already-validated original full-cel GIF assets.

Does NOT generate or deform character poses. Exports exact PNG bytes, authored
world trajectories, optional authored navigation mesh/obstacles, and a runnable
Godot 4 project. The previous full-cel renderer is always the release gate.
"""
from __future__ import annotations
import argparse
import io
import json
import math
import re
import shutil
import subprocess
import zipfile
from pathlib import Path
from PIL import Image


class GodotBridgeError(ValueError):
    pass


def fail(s):
    raise GodotBridgeError('Godot bridge blocked: '+str(s))


def safe_slug(raw, used):
    ident=str(raw)
    if not ident or len(ident)>160:
        fail('Invalid character ID')
    slug=re.sub(r'[^a-zA-Z0-9_-]+','_',ident).strip('_')
    if not slug or slug.lower() in used:
        fail('Missing or colliding actor sprite slug '+ident)
    used.add(slug.lower())
    return slug


def inside_member(raw):
    if not isinstance(raw,str) or not raw or '\\' in raw or raw.startswith('/') or ':' in raw:
        fail('Invalid source texture member '+repr(raw))
    pieces=raw.split('/')
    if any(part in ('','.','..') for part in pieces):
        fail('Unsafe source texture member '+raw)
    return raw


def positive(v):
    return type(v) in (int,float) and math.isfinite(v) and v>0


def validate_polygon(vertices,size):
    if not isinstance(vertices,list) or not 3<=len(vertices)<=128:
        fail('Navigation polygon must have 3-128 source-pixel coordinates')
    xy=[]
    for v in vertices:
        if not isinstance(v,list) or len(v)!=2 or not all(type(x) in (int,float) and math.isfinite(x) for x in v):
            fail('Invalid navigation polygon vertex')
        if not(0<=v[0]<=size[0] and 0<=v[1]<=size[1]):
            fail('Navigation polygon goes beyond canvas')
        xy.append((float(v[0]),float(v[1])))
    area=abs(sum(xy[i][0]*xy[(i+1)%len(xy)][1]-xy[(i+1)%len(xy)][0]*xy[i][1] for i in range(len(xy))))/2
    if area<16:fail('Navigation polygon area too small')
    return [[x,y] for x,y in xy]


def point_inside_polygon(point,poly):
    x,y=point;inside=False;j=len(poly)-1
    for i in range(len(poly)):
        xi,yi=poly[i];xj,yj=poly[j]
        if (yi>y)!=(yj>y) and x < (xj-xi)*(y-yi)/(yj-yi)+xi:
            inside=not inside
        j=i
    return inside


def read_png(container,member,expect_size=None,require_alpha=False):
    try:
        data=container.read(member)
    except KeyError:
        fail('Required verified art missing from ZIP: '+member)
    try:
        with Image.open(io.BytesIO(data)) as im:
            if im.format != 'PNG':fail('Authored asset is not PNG: '+member)
            if expect_size and im.size!=tuple(expect_size):
                fail('Source sprite dimensions mismatch '+member)
            if require_alpha:
                alpha=im.convert('RGBA').getchannel('A')
                mn,mx=alpha.getextrema()
                if mx==0 or mn==255:
                    fail('Sprite must contain real transparent silhouette: '+member)
            return data,im.size
    except GodotBridgeError:
        raise
    except Exception as e:
        fail('Corrupt verified PNG '+member+': '+str(e))


def validate_navigation(conf, actor_data, size):
    godot=conf.get('godot',{})
    if not isinstance(godot,dict):fail('godot settings must be object')
    raw_polys=godot.get('walkable_polygons',[])
    if not isinstance(raw_polys,list) or len(raw_polys)>32:fail('Invalid navigation polygon list')
    polygons=[validate_polygon(poly,size) for poly in raw_polys]
    ids={str(a['id']):a for a in actor_data}
    movers=godot.get('navigation_actors',{})
    if not isinstance(movers,dict):fail('godot.navigation_actors must be an object')
    normalized={}
    for aid,settings in movers.items():
        if aid not in ids:fail('Unknown navigation actor '+aid)
        if not polygons:fail('A real authored navigation polygon is required for interactive navigation')
        actions={a for a in ids[aid]['actions']}
        moving={'walk','run','stairs_up','stairs_down'}
        if not (actions & moving):
            fail('Navigation actor '+aid+' has no approved walking/running PNG cels')
        if not actions - moving:
            fail('Navigation actor '+aid+' needs a real non-locomotive full-pose activity at stops')
        if not isinstance(settings,dict):fail('Navigation settings must be object')
        waypoints=settings.get('waypoints',[])
        if not isinstance(waypoints,list) or len(waypoints)<2 or len(waypoints)>64:
            fail('Navigation actor needs at least two source-pixel waypoints')
        clean=[]
        for point in waypoints:
            if not isinstance(point,list) or len(point)!=2 or not all(type(n) in (int,float) and math.isfinite(n) for n in point):
                fail('Invalid navigation waypoint')
            if not any(point_inside_polygon(point,poly) for poly in polygons):
                fail('Navigation waypoint outside authored navigable region')
            clean.append([float(point[0]),float(point[1])])
        speed=settings.get('speed_px_s',24)
        if not positive(speed) or not 2<=speed<=500:
            fail('Invalid navigation speed')
        normalized[aid]={'waypoints':clean,'speed_px_s':float(speed)}
    obstacles=godot.get('obstacles',[])
    if not isinstance(obstacles,list) or len(obstacles)>128:
        fail('Invalid obstacle list')
    for rect in obstacles:
        if not isinstance(rect,list) or len(rect)!=4 or not all(type(n) in (int,float) and math.isfinite(n) for n in rect):
            fail('Obstacle rectangle must be [x,y,w,h] source pixels')
        x,y,w,h=rect
        if w<=1 or h<=1 or x<0 or y<0 or x+w>size[0] or y+h>size[1]:
            fail('Invalid obstacle rectangle bounds')
    return {'walkable_polygons':polygons,'navigation_actors':normalized,'obstacles':obstacles}


def compile_project(verified_zip:Path,output:Path,godot_binary=None,fps:int=24):
    verified_zip=Path(verified_zip).resolve();output=Path(output).resolve()
    if not verified_zip.is_file():fail('Verified GIF asset ZIP missing')
    project=output/'godot_project';project.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(verified_zip,'r') as src:
        if src.testzip() is not None:fail('Source ZIP is corrupt')
        try:
            scene=json.loads(src.read('scene.json'))
            gate=json.loads(src.read('motion_gate.json'))
        except (KeyError,ValueError) as e:
            fail('Verified pose scene/motion gate missing: '+str(e))
        if not gate.get('all_actors_pass'):
            fail('Original 2D pose gate has not accepted every actor')
        actors=scene.get('actors',[])
        inventory=scene.get('inventory',{}).get('actors',[])
        if not actors or set(inventory)!={a.get('id') for a in actors}:
            fail('Unverified or incomplete character inventory')
        _,(width,height)=read_png(src,'source.png')
        background,_=read_png(src,'background_clean.png',(width,height))
        (project/'textures').mkdir(exist_ok=True)
        (project/'textures'/'background.png').write_bytes(background)
        (project/'sprites').mkdir(exist_ok=True)
        (project/'data').mkdir(exist_ok=True)
        (project/'scripts').mkdir(exist_ok=True)
        compiled=[];used=set()
        for actor in actors:
            aid=str(actor['id']);slug=safe_slug(aid,used)
            box=actor.get('box',[])
            if not isinstance(box,list) or len(box)!=4 or any(type(x) is not int for x in box):
                fail('Invalid actor bounding box '+aid)
            x,y,w,h=box
            if w<8 or h<8 or x<0 or y<0 or x+w>width or y+h>height:
                fail('Actor box outside original illustration '+aid)
            clips=actor.get('clips',[])
            if len(clips)<2:fail('No validated multi-action clips for '+aid)
            imgs=[];actions=[];supports=[]
            for clip in clips:
                action=clip.get('action')
                frames=clip.get('frames',[])
                if not isinstance(action,str) or len(frames)<12:
                    fail('Missing genuine animation frames for '+aid)
                if len({f.get('png') for f in frames})<8:
                    fail('Frozen or duplicated pose sources for '+aid+'/'+action)
                for frame in frames:
                    original=inside_member(frame.get('png'))
                    # The existing verified pose composer preserves exact originals here.
                    member='project/inputs/'+original
                    data,_=read_png(src,member,(w,h),require_alpha=True)
                    n=len(imgs)
                    rel=f'sprites/{slug}/{n:04d}.png'
                    file=project/rel
                    file.parent.mkdir(parents=True,exist_ok=True)
                    file.write_bytes(data) # byte-exact authentic cel; absolutely no deformation
                    imgs.append('res://'+rel)
                    actions.append(action)
                    supports.append(frame.get('support'))
            if len(imgs)<24:fail('Not enough actual poses for '+aid)
            cycle=len(imgs)
            phase=actor.get('phase_frames',0)
            if type(phase) is not int or not 0<=phase<cycle:
                fail('Invalid phase for '+aid)
            locomotion=actor.get('locomotion')
            if locomotion:
                if not isinstance(locomotion.get('path'),list) or len(locomotion['path'])<3:
                    fail('Real world trajectory missing for '+aid)
                last=locomotion['path'][-1]
                if last.get('frame')!=cycle:
                    fail('Authored trajectory cycle mismatched for '+aid)
            compiled.append({'id':aid,'sprite_paths':imgs,'actions':actions,'supports':supports,
                             'box':box,'z_index':int(actor.get('z',0)),
                             'phase_frames':phase,'locomotion':locomotion})
        navigation=validate_navigation(scene,compiled,(width,height))
        godot_layers=[]
        godot_conf=scene.get('godot',{})
        for index,layer in enumerate(godot_conf.get('layers',[])):
            if not isinstance(layer,dict) or 'png' not in layer or 'z_index' not in layer:
                fail('Author-supplied 2.5D layer needs png and z_index')
            original=inside_member(layer['png'])
            data,_=read_png(src,'project/inputs/'+original,(width,height))
            name=f'textures/layer_{index:03d}.png'
            (project/name).write_bytes(data)
            godot_layers.append({'texture':'res://'+name,'z_index':int(layer['z_index'])})
        data={'schema':'lia-godot-1','fps':fps,'width':width,'height':height,'actors':compiled,
              'layers':godot_layers,**navigation}
        (project/'data'/'scene.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf8')

    (project/'project.godot').write_text(PROJECT_GODOT.replace('__WIDTH__',str(width)).replace('__HEIGHT__',str(height)),'utf8')
    (project/'Main.tscn').write_text(MAIN_TSCN,'utf8')
    (project/'scripts'/'main.gd').write_text(MAIN_GD,'utf8')
    (project/'scripts'/'actor.gd').write_text(ACTOR_GD,'utf8')
    if godot_binary:
        exe=shutil.which(str(godot_binary)) or (str(Path(godot_binary).resolve()) if Path(godot_binary).is_file() else None)
        if not exe:fail('Godot executable not installed (optional runtime verification requested)')
        proc=subprocess.run([exe,'--headless','--editor','--path',str(project),'--quit'],
                            capture_output=True,text=True,timeout=120,check=False)
        if proc.returncode:
            fail('Godot headless project import failed: '+(proc.stderr+'\n'+proc.stdout)[-2500:])
    package=output/'living_scene_godot.zip'
    with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as dst:
        for p in sorted(project.rglob('*')):
            if p.is_file() and '.godot' not in p.parts:
                dst.write(p,'living_scene_godot/'+p.relative_to(project).as_posix())
    with zipfile.ZipFile(package) as dst:
        if dst.testzip() is not None or 'living_scene_godot/project.godot' not in dst.namelist():
            fail('Godot project archive corrupt')
    return package,{'actors':len(compiled),'godot_navigation_actors':len(navigation['navigation_actors']),
                    'godot_runtime_verified':bool(godot_binary)}


PROJECT_GODOT='''config_version=5

[application]
config/name="Living Image Animator · Full Cel World"
run/main_scene="res://Main.tscn"

[display]
window/size/viewport_width=__WIDTH__
window/size/viewport_height=__HEIGHT__
window/stretch/mode="canvas_items"

[rendering]
renderer/rendering_method="gl_compatibility"
renderer/rendering_method.mobile="gl_compatibility"
textures/canvas_textures/default_texture_filter=0
'''

MAIN_TSCN='''[gd_scene load_steps=2 format=3]

[ext_resource type="Script" path="res://scripts/main.gd" id="1_main"]

[node name="LivingWorld" type="Node2D"]
script = ExtResource("1_main")
'''

MAIN_GD=r'''extends Node2D
## Godot 4 living scene from verified original 24fps hand-painted PNG cels.
const ActorScript = preload("res://scripts/actor.gd")
var config: Dictionary = {}

func _ready() -> void:
    var data_text: String = FileAccess.get_file_as_string("res://data/scene.json")
    var parsed: Variant = JSON.parse_string(data_text)
    if not (parsed is Dictionary):
        push_error("Invalid exported source-authored scene JSON")
        return
    config = parsed
    var background := Sprite2D.new()
    background.name = "Original_Clean_Background"
    background.texture = load("res://textures/background.png")
    background.centered = false
    background.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
    background.z_index = -100
    add_child(background)
    for layer in config.get("layers", []):
        var plane := Sprite2D.new()
        plane.texture = load(layer["texture"])
        plane.centered = false
        plane.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
        plane.z_index = int(layer["z_index"])
        add_child(plane)
    _create_navigation_regions()
    _create_obstacles()
    for settings in config["actors"]:
        var character = ActorScript.new()
        add_child(character)
        character.setup(settings, float(config.get("fps",24.0)),
            config.get("navigation_actors",{}).get(settings["id"],{}))

func _create_navigation_regions() -> void:
    for poly in config.get("walkable_polygons",[]):
        var points := PackedVector2Array()
        for v in poly:
            points.append(Vector2(float(v[0]),float(v[1])))
        var triangles: PackedInt32Array = Geometry2D.triangulate_polygon(points)
        if triangles.size() < 3:
            push_error("Authored Godot navigation polygon could not triangulate")
            continue
        var navpoly := NavigationPolygon.new()
        navpoly.vertices = points
        for ix in range(0,triangles.size(),3):
            navpoly.add_polygon(PackedInt32Array([triangles[ix],triangles[ix+1],triangles[ix+2]]))
        var region := NavigationRegion2D.new()
        region.navigation_polygon = navpoly
        add_child(region)

func _create_obstacles() -> void:
    for bounds in config.get("obstacles",[]):
        var object := StaticBody2D.new()
        var collision := CollisionShape2D.new()
        var shape := RectangleShape2D.new()
        shape.size = Vector2(float(bounds[2]),float(bounds[3]))
        collision.shape = shape
        object.position = Vector2(float(bounds[0])+shape.size.x/2.0,float(bounds[1])+shape.size.y/2.0)
        object.add_child(collision)
        add_child(object)
        # Godot RVO avoidance: obstacles have author-supplied static outlines.
        # This steers local velocity; the StaticBody2D still guarantees contact.
        var obstacle := NavigationObstacle2D.new()
        var hw: float = float(bounds[2])*0.5
        var hh: float = float(bounds[3])*0.5
        obstacle.position = object.position
        obstacle.vertices = PackedVector2Array([
            Vector2(-hw,-hh),Vector2(hw,-hh),Vector2(hw,hh),Vector2(-hw,hh)])
        obstacle.avoidance_enabled = true
        add_child(obstacle)
'''

ACTOR_GD=r'''extends CharacterBody2D
## Two gameplay modes: exact source animation timeline; explicit authored nav waypoints.
## No bone/mesh/optical flow/warp is ever used on imported sprites.
var sprite: Sprite2D
var nav: NavigationAgent2D
var images: Array[Texture2D] = []
var actions: PackedStringArray = PackedStringArray()
var box: Array = []
var path: Array = []
var waypoints: Array = []
var waypoint_index: int = 0
var base_position: Vector2 = Vector2.ZERO
var phase_frames: int = 0
var fps: float = 24.0
var elapsed: float = 0.0
var moving_speed: float = 24.0
var navigated: bool = false
var walk_indices: PackedInt32Array = PackedInt32Array()
var idle_indices: PackedInt32Array = PackedInt32Array()

func setup(cfg: Dictionary, target_fps: float, nav_config: Dictionary) -> void:
    name = str(cfg["id"])
    fps = target_fps
    box = cfg["box"]
    base_position = Vector2(float(box[0]),float(box[1]))
    position = base_position
    phase_frames = int(cfg.get("phase_frames",0))
    path = cfg.get("locomotion",{}).get("path",[]) if cfg.get("locomotion") is Dictionary else []
    for filename in cfg["sprite_paths"]:
        var texture: Texture2D = load(filename)
        if texture == null:
            push_error("Missing authentic animation frame: "+str(filename))
            return
        images.append(texture)
    var preferred_move: String = str(cfg.get("locomotion",{}).get("mode","walk")) if cfg.get("locomotion") is Dictionary else "walk"
    for action in cfg["actions"]:
        actions.append(str(action))
        var i := actions.size()-1
        if str(action) == preferred_move:
            walk_indices.append(i)
        elif not str(action) in ["walk","run","stairs_up","stairs_down"]:
            idle_indices.append(i)
    sprite = Sprite2D.new()
    sprite.centered = false
    sprite.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
    sprite.z_index = int(cfg.get("z_index",0))
    add_child(sprite)
    if images.size()>0:
        sprite.texture = images[phase_frames % images.size()]
    if not nav_config.is_empty():
        navigated = true
        waypoints = nav_config["waypoints"]
        moving_speed = float(nav_config.get("speed_px_s",24.0))
        var collision := CollisionShape2D.new()
        var circle := CircleShape2D.new()
        circle.radius = max(2.0,min(float(box[2]),float(box[3]))*0.14)
        collision.position = Vector2(float(box[2])*0.5,float(box[3])*0.84)
        collision.shape = circle
        add_child(collision)
        nav = NavigationAgent2D.new()
        nav.path_desired_distance = max(2.0,circle.radius)
        nav.target_desired_distance = max(3.0,circle.radius)
        nav.avoidance_enabled = true
        add_child(nav)
        nav.velocity_computed.connect(_on_safe_velocity)
        call_deferred("_start_nav")
    else:
        collision_layer = 0
        collision_mask = 0

func _start_nav() -> void:
    if nav == null or waypoints.is_empty(): return
    nav.target_position = Vector2(float(waypoints[0][0]),float(waypoints[0][1]))

func _process(delta: float) -> void:
    if images.is_empty(): return
    elapsed += delta
    var i := (int(floor(elapsed*fps))+phase_frames) % images.size()
    if navigated:
        var selected: PackedInt32Array = walk_indices if velocity.length()>=2.0 else idle_indices
        if selected.size()>0:
            var j := int(floor(elapsed*fps)) % selected.size()
            i = selected[j]
    sprite.texture = images[i]
    if not navigated and not path.is_empty():
        var offset: Vector2 = _sample_path(float(i))
        position = base_position + offset

func _physics_process(_delta: float) -> void:
    if not navigated or nav == null:return
    if nav.is_navigation_finished():
        velocity = Vector2.ZERO
        nav.velocity = Vector2.ZERO
        if waypoints.is_empty():return
        waypoint_index = (waypoint_index+1)%waypoints.size()
        nav.target_position = Vector2(float(waypoints[waypoint_index][0]),float(waypoints[waypoint_index][1]))
        return
    # NavAgent gives the next route point each physics tick. CharacterBody2D
    # collisions block walls, rather than moving a sprite through them.
    var next: Vector2 = nav.get_next_path_position()
    var delta_pos: Vector2 = next-global_position
    var requested_velocity: Vector2 = delta_pos.normalized()*moving_speed if delta_pos.length()>1.0 else Vector2.ZERO
    # NavigationAgent2D computes collision-aware avoidance via its signal.
    nav.velocity = requested_velocity

func _on_safe_velocity(safe_velocity: Vector2) -> void:
    velocity = safe_velocity
    move_and_slide()

func _sample_path(t: float) -> Vector2:
    if path.is_empty():return Vector2.ZERO
    if t<=float(path[0]["frame"]):return Vector2(float(path[0]["dx"]),float(path[0]["dy"]))
    for ix in range(1,path.size()):
        var prev: Dictionary = path[ix-1]
        var next: Dictionary = path[ix]
        if t<=float(next["frame"]):
            var u: float = (t-float(prev["frame"]))/(float(next["frame"])-float(prev["frame"]))
            u = u*u*(3.0-2.0*u)
            return Vector2(lerpf(float(prev["dx"]),float(next["dx"]),u),
                           lerpf(float(prev["dy"]),float(next["dy"]),u))
    var end: Dictionary = path[-1]
    return Vector2(float(end["dx"]),float(end["dy"]))
'''


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--asset-zip',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--godot',help='Optional installed Godot binary for headless import verification')
    a=ap.parse_args()
    package,stats=compile_project(a.asset_zip,a.out,a.godot)
    print(json.dumps({'godot_project_zip':str(package),**stats},ensure_ascii=False))

if __name__=='__main__':main()
