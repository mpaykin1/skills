#!/usr/bin/env python3
"""Export the approved sprite-stack source to an actual Godot 4 Shader Stacker project.

This is an additional Godot artifact. Genuine MPL-2.0 Shader Stacker source is
vendored in the plugin's vendor/ShaderStacker tree; no graphics are fabricated.
The original source-GIF/poses/art ZIP and original Godot project are immutable.
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
import tempfile
import zipfile
from pathlib import Path
from PIL import Image
from pixijs_bridge import load_scene
from sprite_stack_bridge import stack, fail as stack_fail

ROOT=Path(__file__).resolve().parents[3]
UPSTREAM=ROOT/'vendor'/'ShaderStacker'
LICENSE=Path(__file__).resolve().parent.parent/'references'/'LICENSE.shader-stacker.txt'
class ShaderStackerError(ValueError):pass

def fail(msg): raise ShaderStackerError('Godot Shader Stacker blocked: '+str(msg))

def safe_id(id):
    if not isinstance(id,str) or not re.fullmatch('[a-zA-Z][a-zA-Z0-9_-]{0,50}',id):fail('Invalid object/actor ID')
    return id

def stack_atlas(root,manifest_path,expected_pose_sha=None):
    data,bytes_used=stack(root,manifest_path,expected_pose_sha)
    if not 8<=data['depth']<=160: fail('Cannot create Shader Stacker atlas from this number of slices')
    size=data['size'];cols=[]
    for uri in data['slices']:
        if not uri.startswith('data:image/png;base64,'):fail('Original RGBA slice PNG required')
        with Image.open(io.BytesIO(base64.b64decode(uri.split(',',1)[1],validate=True))) as im:
            if im.format!='PNG' or im.size!=(size,size):fail('Source slice size changed')
            cols.append(im.convert('RGBA').copy())
    # Official addon: one-column sheet, bottom physical slice in the BOTTOM row.
    result=Image.new('RGBA',(size,size*len(cols)),(0,0,0,0))
    for i,img in enumerate(cols):result.paste(img,(0,size*(len(cols)-i-1)))
    # Byte-accurate roundtrip check on original source RGBA pixels.
    for i,img in enumerate(cols):
        if result.crop((0,size*(len(cols)-i-1),size,size*(len(cols)-i))).tobytes()!=img.tobytes():
            fail('Source PNG slice pixel mismatch after Godot packing')
    buf=io.BytesIO();result.save(buf,format='PNG',compress_level=6)
    dx,dy,dz=data['spacing']
    if abs(dx-dy)>max(dx,dy)*.025:fail('Shader Stacker needs same X/Y source scale for honest 2D layer projection')
    pitch=dz/dx
    if not .02<=pitch<=16:fail('Godot SpriteStack pitch outside native 0.02–16 px per layer')
    return buf.getvalue(),{'depth':len(cols),'slice_px':size,'pitch':pitch,
       'source_sha256':data['sha256'],'source_pose_sha256':data['source_pose_sha256'],
       'original_gpu_bytes':bytes_used,'stack_path':manifest_path}

GDSCRIPT=r'''extends Node2D
## Source pixels and original full-body poses are never transformed or generated.
const StackScript = preload("res://addons/ShaderStacker/SpriteStack/SpriteStack.gd")
const CameraScript = preload("res://addons/ShaderStacker/StackCamera/StackCamera.gd")
var stacks: Array[Node2D] = []
var animated: Array[Dictionary] = []
var orbiting: bool = false
var camera_node: Camera2D

func _ready() -> void:
    var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string("res://stacker/scene.json"))
    if not (parsed is Dictionary):
        push_error("Original Sprite Stacking scene manifest missing")
        return
    camera_node = CameraScript.new()
    camera_node.name = "StackCamera"
    camera_node.enabled = true
    camera_node.position = Vector2(float(parsed["canvas"][0])*0.5,float(parsed["canvas"][1])*0.5)
    camera_node.zoom = Vector2(1.0,0.8)
    add_child(camera_node)
    for item in parsed["objects"]:
        var stack_node = _create_stack(item)
        stacks.append(stack_node)
    for item in parsed["actors"]:
        var original = get_node_or_null("OriginalWorld/" + str(item["id"]))
        if original == null or original.sprite == null:
            push_error("Missing original approved source actor: " + str(item["id"]))
            continue
        var stack_node = _create_stack(item)
        stack_node.position = original.position
        original.sprite.visible = false
        animated.append({"original":original,"stack":stack_node,"frames":item["frames"],"last":-1})

func _create_stack(item: Dictionary) -> Node2D:
    var node = StackScript.new()
    node.name = "OriginalStack_" + str(item["id"])
    var path: String = str(item.get("texture", ""))
    if path == "" and item.has("frames"):
        path = str(item["frames"][0])
    node.sprite_sheet = load(path)
    if node.sprite_sheet == null:
        push_error("Missing original source stack sheet: " + path)
    node.layers = int(item["layers"])
    node.pitch = float(item["pitch"])
    node.yaw = deg_to_rad(float(item.get("yaw_degrees",0.0)))
    node.z = int(item.get("height",0))
    node.position = Vector2(float(item["position"][0]),float(item["position"][1]))
    # Official renderer doubles pixel size; scale back to source canvas registration.
    node.scale = Vector2(0.5,0.5)
    add_child(node)
    return node

func _process(_delta: float) -> void:
    for record in animated:
        var actor = record["original"]
        var cel_idx: int = actor.images.find(actor.sprite.texture)
        if cel_idx < 0 or cel_idx >= record["frames"].size():
            push_error("Original approved actor pose/frame not available")
            continue
        if cel_idx != int(record["last"]):
            record["stack"].sprite_sheet = load(str(record["frames"][cel_idx]))
            record["last"] = cel_idx
        record["stack"].position = actor.position

func _unhandled_input(event: InputEvent) -> void:
    if event is InputEventMouseButton:
        if event.button_index == MOUSE_BUTTON_LEFT:
            orbiting = event.pressed
        if event.pressed and event.button_index == MOUSE_BUTTON_WHEEL_UP:
            camera_node.zoom *= 1.07
        if event.pressed and event.button_index == MOUSE_BUTTON_WHEEL_DOWN:
            camera_node.zoom /= 1.07
    elif event is InputEventMouseMotion and orbiting:
        _rotate_stacks(float(event.relative.x)*0.008)
    elif event is InputEventScreenDrag:
        _rotate_stacks(float(event.relative.x)*0.008)
    elif event is InputEventKey and event.pressed and not event.echo:
        if event.keycode == KEY_Q:
            _rotate_stacks(-0.09)
        elif event.keycode == KEY_E:
            _rotate_stacks(0.09)

func _rotate_stacks(arc: float) -> void:
    for node in stacks:
        node.yaw += arc
    for item in animated:
        item["stack"].yaw += arc
'''

SCENE='''[gd_scene load_steps=3 format=3]

[ext_resource type="PackedScene" path="res://Main.tscn" id="1_world"]
[ext_resource type="Script" path="res://stacker/stack_world.gd" id="2_stack"]

[node name="LivingWorldShaderStacker" type="Node2D"]
script = ExtResource("2_stack")

[node name="OriginalWorld" parent="." instance=ExtResource("1_world")]
'''

def project(approved_zip,scene_path,godot_zip,out, *,godot_binary=None):
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    approved_zip=Path(approved_zip).resolve();scene_path=Path(scene_path).resolve()
    original=load_scene(approved_zip)  # Previous full-body motion/identity gate.
    with zipfile.ZipFile(approved_zip) as z:
        if z.testzip() is not None:fail('Original GIF source asset ZIP corrupt')
        saved=json.loads(z.read('scene.json'))
        motion=json.loads(z.read('motion_gate.json'))
        if motion.get('all_actors_pass') is not True:fail('Original motion gate not passed')
    source=json.loads(scene_path.read_text('utf8'))
    cfg=source.get('sprite_stacking')
    if not isinstance(cfg,dict) or cfg!=saved.get('sprite_stacking'):
        fail('Approved original sprite_stacking declaration missing or changed')
    objects=cfg.get('objects',[]);actors=cfg.get('actors',[])
    if not isinstance(objects,list) or not isinstance(actors,list) or not(objects or actors):
        fail('At least one source-authored stack object or actor required')
    if len(objects)+len(actors)>100:fail('Maximum 100 original stack entities')
    if cfg.get('environment_only',False) and actors:
        fail('Environment-only scene cannot claim approved 3D actors')
    eligible=cfg.get('eligible_object_ids',[])
    if not isinstance(eligible,list) or not eligible or len(set(eligible))!=len(eligible):
        fail('Full source inventory required for genuine >=90% coverage')
    if not all(isinstance(x,str) for x in eligible):fail('Invalid eligible source IDs')
    compiled=[];animated=[];attached=set();assetbytes=0
    with tempfile.TemporaryDirectory(prefix='shader_stacker_') as temp:
        dest=Path(temp);(dest/'stacker'/'textures').mkdir(parents=True)
        for rel in sorted(UPSTREAM.rglob('*')):
            if not rel.is_file():continue
            target=dest/'addons'/'ShaderStacker'/rel.relative_to(UPSTREAM)
            target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(rel,target)
        for required in ['SpriteStack/SpriteStack.gd','StackCamera/StackCamera.gd','Reset2D/Reset2D.gd','plugin.cfg','init.gd']:
            if not (dest/'addons'/'ShaderStacker'/required).is_file():fail('Authentic Godot source missing: '+required)
        for item in objects:
            oid=safe_id(item.get('id'))
            if oid in attached:fail('Duplicate stack object')
            attached.add(oid)
            xy=item.get('position')
            if not isinstance(xy,list) or len(xy)!=3 or any(type(x) not in (int,float) or not math.isfinite(x) for x in xy):fail('Godot stack requires original [x,y,z] position')
            sheet,info=stack_atlas(scene_path.parent,item.get('stack'))
            assetbytes+=info['original_gpu_bytes']
            path='stacker/textures/'+oid+'.png';(dest/path).write_bytes(sheet)
            compiled.append({'id':oid,'texture':'res://'+path,'layers':info['depth'],
              'pitch':info['pitch'],'position':[xy[0],xy[1]],'height':xy[2],
              'yaw_degrees':float(item.get('yaw',0.0)), 'source':info['source_sha256']})
        approved_ids={a['id']:a for a in original['actors']}
        with zipfile.ZipFile(approved_zip) as z:
            for actor in actors:
                ident=safe_id(actor.get('actor_id'))
                if ident in attached or ident not in approved_ids:fail('3D stack actor not in approved original pose cast')
                attached.add(ident)
                pose=next(a for a in saved['actors'] if a['id']==ident)
                clips=actor.get('clips')
                if not isinstance(clips,dict) or set(clips)!={c['action'] for c in pose['clips']}:
                    fail('Every approved original full-body action requires complete independent 3D stack poses')
                frames=[];reference=None
                for clip in pose['clips']:
                    paths=clips[clip['action']]
                    if not isinstance(paths,list) or len(paths)!=len(clip['frames']):fail('Original clip frame count mismatched')
                    for stackfile,frame in zip(paths,clip['frames']):
                        sha=hashlib.sha256(z.read('project/inputs/'+frame['png'])).hexdigest()
                        sheet,info=stack_atlas(scene_path.parent,stackfile,sha)
                        current=(info['depth'],info['slice_px'],info['pitch'])
                        if reference is None:reference=current
                        if current!=reference:fail('Pose stacks must share fixed geometry registration')
                        assetbytes+=info['original_gpu_bytes']
                        destfile=f'stacker/textures/{ident}_{len(frames):04d}.png'
                        (dest/destfile).write_bytes(sheet);frames.append('res://'+destfile)
                bx=approved_ids[ident]['box'];animated.append({'id':ident,'frames':frames,
                    'layers':reference[0],'pitch':reference[2],'position':[bx[0],bx[1]],'height':0})
        required_ratio=cfg.get('coverage_min',.9)
        if type(required_ratio) not in (int,float) or not .75<=required_ratio<=1:fail('Invalid original stack coverage threshold')
        actual=len(attached)/len(eligible)
        if not attached.issubset(set(eligible)) or actual<max(.9,required_ratio):
            fail('Godot stack coverage below 90% of author-declared object inventory')
        if assetbytes>256_000_000:fail('Original slice texture memory beyond 256 MB budget')
        if not cfg.get('environment_only',False) and set(approved_ids)!=set(a['id'] for a in animated):
            fail('Original certified actors need 3D poses in a non-environment-only Godot stack scene')
        with zipfile.ZipFile(godot_zip) as g:
            if g.testzip() is not None:fail('Original Godot project corrupt')
            for member in g.infolist():
                if member.is_dir():continue
                parts=Path(member.filename).parts
                if not parts or parts[0]!='living_scene_godot' or '..' in parts or len(parts)<2:
                    fail('Invalid original Godot archive path')
                sub=Path(*parts[1:]);path=dest/sub
                if path.exists():fail('Original Godot project conflicts with new addon')
                path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(g.read(member))
        for name in ['project.godot','Main.tscn','scripts/main.gd']:
            if not (dest/name).exists():fail('Original validated Godot project missing '+name)
        origin=(dest/'project.godot').read_text('utf8')
        # New Godot variant alone opts in to the addon. Prior project archive is unchanged.
        origin=origin.replace('run/main_scene="res://Main.tscn"','run/main_scene="res://StackWorld.tscn"')
        if '[editor_plugins]' not in origin:
            origin+='\n[editor_plugins]\nenabled=PackedStringArray("res://addons/ShaderStacker/plugin.cfg")\n'
        (dest/'project.godot').write_text(origin,'utf8')
        # Prevent ghost double-geometry in the variant: require a source-authored plate.
        clean=(cfg.get('background') or source.get('sprite_stacking_game',{}).get('clean_plate'))
        if objects:
            if not isinstance(clean,str) or not clean:fail('Real clean source background PNG required to avoid duplicated buildings')
            from sprite_stack_bridge import within
            cleanfile=within(scene_path.parent,clean)
            with Image.open(cleanfile) as im:
                if im.format!='PNG' or im.size!=(original['width'],original['height']):
                    fail('Artist-cleaned background must be original-size PNG')
                if im.getbbox() is None:fail('Empty environment source plate')
            shutil.copyfile(cleanfile,dest/'textures'/'background.png')
        (dest/'StackWorld.tscn').write_text(SCENE,'utf8')
        (dest/'stacker'/'stack_world.gd').write_text(GDSCRIPT,'utf8')
        (dest/'stacker'/'scene.json').write_text(json.dumps({'canvas':[original['width'],original['height']],
                     'objects':compiled,'actors':animated,'source_gate':True},ensure_ascii=False,indent=2),'utf8')
        (dest/'addons'/'ShaderStacker'/'LICENSE').write_bytes(LICENSE.read_bytes())
        (dest/'addons'/'ShaderStacker'/'SOURCE.txt').write_text(
            'Shader Stacker by Karl Phillips / CoolDotty (x3cca).\n'
            'Source: https://github.com/x3cca/Shader-Stacker\n'
            'Pinned source commit: 21d86ab62140b0d08ea217982036e3cb184afed5\n'
            'MPL 2.0 source code preserved in addons/ShaderStacker.\n'
            'Editor SVG icons are locally authored replacements (not original project icons).\n','utf8')
        if godot_binary:
            binary=shutil.which(str(godot_binary)) or (str(Path(godot_binary).resolve()) if Path(godot_binary).is_file() else None)
            if not binary:fail('Requested actual Godot4 binary not installed')
            check=subprocess.run([binary,'--headless','--editor','--path',str(dest),'--quit'],
                capture_output=True,text=True,timeout=150,check=False)
            if check.returncode:fail('Real Godot4 project import failed: '+(check.stdout+check.stderr)[-1900:])
        result=out/'living_scene_godot_shader_stacker.zip'
        if result.exists():fail('Existing Godot Shader Stacker output; use a new folder')
        with zipfile.ZipFile(result,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            for path in sorted(dest.rglob('*')):
                if path.is_file() and '.godot' not in path.parts:
                    z.write(path,'living_scene_godot_shader_stacker/'+path.relative_to(dest).as_posix())
        with zipfile.ZipFile(result) as z:
            if z.testzip():fail('Exported Godot4 Shader Stacker project became corrupt')
        return result,{'native_addon':'Shader Stacker 4.x (source plugin.cfg 4.0.4)',
          'stacked_objects':len(compiled),'stacked_actors':len(animated),
          'source_inventory_coverage':actual,'source_character_pngs_unchanged':True,
          'godot_import_checked':bool(godot_binary),'plugin_source':'x3cca/Shader-Stacker',
          'separate_godot_variant':True,'original_asset_zip_unchanged':True,
          'sha256':hashlib.sha256(result.read_bytes()).hexdigest()}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--approved-zip',required=True,type=Path)
    p.add_argument('--scene',required=True,type=Path)
    p.add_argument('--godot-zip',required=True,type=Path)
    p.add_argument('--out',required=True,type=Path);p.add_argument('--godot')
    a=p.parse_args()
    result,meta=project(a.approved_zip,a.scene,a.godot_zip,a.out,godot_binary=a.godot)
    print(json.dumps({'file':str(result),**meta},ensure_ascii=False))
