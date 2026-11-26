#!/usr/bin/env python3
"""Convert REAL source RGBA layers/strips/GLB/four views into Godot 4 Shader-Stacker project.

Original files never overwritten. Official pinned MPL-2.0 addon is copied without edits.
Godot/Shader-Stacker provides 2.5D viewport sorting, not volumetric GLSL or gameplay recovery.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
from PIL import Image
from PIL.PngImagePlugin import PngInfo
from install_shader_stacker import resolve as load_addon, COMMIT, URL

HERE=Path(__file__).resolve().parent
SKILLS=HERE.parents[1]
FOUR=SKILLS/'sprite-stacking-four-views'/'scripts'/'views_to_stack.py'
GLB=SKILLS/'sprite-stacking-priority'/'scripts'/'stack_from_glb.py'
MAX_LAYERS=192
MAX_ITEMS=64
MAX_PIXEL_BYTES=128*1024*1024


def sha(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as fp:
        for part in iter(lambda:fp.read(1024*1024),b''):h.update(part)
    return h.hexdigest()


def safe_path(base:Path,relative:str) -> Path:
    if not isinstance(relative,str) or not relative or '\\' in relative or Path(relative).is_absolute():
        raise ValueError('Layer path must be relative to its stack')
    maybe=base/relative
    if maybe.is_symlink():raise ValueError('Symlinked source slice rejected')
    path=maybe.resolve(strict=True)
    if base not in path.parents:raise ValueError('Slice path escapes source folder')
    return path


def rgba(path:Path) -> Image.Image:
    if path.is_symlink():raise ValueError('Symlinked PNG rejected')
    with Image.open(path) as im:
        if im.format!='PNG':raise ValueError('Source must be PNG')
        if im.mode!='RGBA':raise ValueError('Source slices must be RGBA PNG; no art conversion')
        if not all(1<=n<=512 for n in im.size):raise ValueError('Slices must be 1..512 px')
        return im.copy()


def as_volume(source:Path,slices:int|None=None,frames:int=1):
    """Return list of independent bottom-first frames, preserving exact RGBA pixels."""
    if source.is_dir() and (source/'stack.json').is_file():source=source/'stack.json'
    if source.suffix.lower()=='.json':
        if source.name!='stack.json':raise ValueError('JSON input must be stack.json or scene-stacks.json')
        meta=json.loads(source.read_text('utf8'))
        layers=meta.get('layers')
        if not isinstance(layers,list) or not 1<=len(layers)<=MAX_LAYERS or len(set(layers))!=len(layers):
            raise ValueError('stack.json needs 1..192 distinct bottom-first slice paths')
        pictures=[rgba(safe_path(source.parent,name)) for name in layers]
        spacing=meta.get('spacing')
        if not isinstance(spacing,list) or len(spacing)!=3 or not all(isinstance(v,(int,float)) and math.isfinite(v) and v>0 for v in spacing):
            raise ValueError('stack.json requires three finite positive spacings')
        if slices and slices!=len(pictures):raise ValueError('--slices does not match stack.json')
        volumes=[pictures]
    elif source.suffix.lower()=='.png':
        with Image.open(source) as im:
            if im.format!='PNG' or im.mode!='RGBA':raise ValueError('Source must be RGBA PNG slice-strip')
            n=slices or (int(im.info['slices']) if str(im.info.get('slices','')).isdigit() else None)
            f=frames if frames!=1 else (int(im.info['frames']) if str(im.info.get('frames','')).isdigit() else 1)
            if not n or not (1<=n<=MAX_LAYERS) or not (1<=f<=24):
                raise ValueError('Slice strip needs embedded slices metadata or --slices N; up to 24 frames')
            if im.width%n or im.height%f:raise ValueError('Strip dimensions not divisible by slice/frame count')
            w,h=im.width//n,im.height//f
            if not 1<=w<=512 or not 1<=h<=512:raise ValueError('Slice dimensions outside Godot asset budget')
            im.load()
            volumes=[[im.crop((z*w,frame*h,(z+1)*w,(frame+1)*h)) for z in range(n)] for frame in range(f)]
        spacing=[1.0,1.0,1.0]
    else:raise ValueError('Expected stack.json, stack folder, or official PNG slice strip')
    n=len(volumes[0]); size=volumes[0][0].size
    if any(len(frame)!=n or any(im.size!=size for im in frame) for frame in volumes):
        raise ValueError('Frame volumes must share slice dimensions and layer count')
    if n*len(volumes)*size[0]*size[1]*4>MAX_PIXEL_BYTES:raise ValueError('Volume data exceeds 128 MiB')
    if any(not any(im.getchannel('A').getbbox() for im in frame) for frame in volumes):
        raise ValueError('Empty volume frame')
    return volumes,spacing


def save_column(vol:list[Image.Image], target:Path):
    """Godot upstream exact contract: bottom slice occupies BOTTOM row; top slice first row."""
    w,h=vol[0].size
    col=Image.new('RGBA',(w,h*len(vol)))
    for i,p in enumerate(vol):
        col.paste(p,(0,(len(vol)-1-i)*h))
    target.parent.mkdir(parents=True,exist_ok=True)
    info=PngInfo();info.add_text('layers',str(len(vol)));info.add_text('order','bottom-first-in-last-row')
    col.save(target,pnginfo=info,optimize=True)


def parse_scene_source(src:Path,out:Path,xy:int,z:int,four_views:bool,slices:int|None,allow_shell:bool):
    if src.is_dir() and (src/'stack.json').is_file():return [{'stack':src/'stack.json','position':[0.,0.,0.],'rotation':[0.,0.,0.]}]
    if src.is_file() and src.suffix.lower()=='.json' and src.name!='stack.json':
        d=json.loads(src.read_text('utf8'))
        data=d.get('stacks')
        if not isinstance(data,list) or not 1<=len(data)<=MAX_ITEMS:raise ValueError('Scene requires 1..64 stack instances')
        result=[]
        for item in data:
            if not isinstance(item,dict) or 'stack' not in item:raise ValueError('Invalid scene stack item')
            if item.get('frames'):raise ValueError('Godot source stack animation not generated automatically: use separate approved pose states')
            st=safe_path(src.parent,item['stack'])
            if st.is_dir():st=st/'stack.json'
            position=item.get('position',[0,0,0]);rotation=item.get('rotation',[0,0,0])
            if any(not isinstance(a,list) or len(a)!=3 or not all(isinstance(v,(float,int)) and math.isfinite(v) for v in a) for a in [position,rotation]):
                raise ValueError('Invalid stack world position/rotation')
            scale=item.get('scale',[1,1,1])
            if not isinstance(scale,list) or len(scale)!=3 or not all(isinstance(v,(int,float)) and math.isfinite(v) and v>0 for v in scale):
                raise ValueError('Invalid source stack scale')
            if any(abs(v-1.0)>1e-6 for v in scale) or any(abs(v)>1e-6 for v in rotation[:2]):
                raise ValueError('Godot 2.5D cannot preserve nonuniform/3D scale or pitch/roll; keep this scene in Three.js')
            result.append({'stack':st,'position':position,'rotation':rotation})
        return result
    if src.suffix.lower()=='.png' and four_views:
        if not FOUR.is_file():raise RuntimeError('Existing danielwh2 four-view carver is missing')
        dest=out/'_source_stacks'/'four-views'
        cmd=[sys.executable,str(FOUR),str(src),'--out',str(dest),'--no-html']
        if slices:cmd+=['--slices',str(slices)]
        subprocess.run(cmd,check=True,timeout=600)
        return [{'stack':dest/'stack-data'/'stack.json','position':[0.,0.,0.],'rotation':[0.,0.,0.]}]
    if src.suffix.lower()=='.glb':
        if not GLB.is_file():raise RuntimeError('Existing GLB-to-slices converter missing')
        dest=out/'_source_stacks'/'glb'
        cmd=[sys.executable,str(GLB),str(src),'--out',str(dest),'--xy',str(xy),'--z',str(z)]
        if allow_shell:cmd.append('--allow-shell')
        subprocess.run(cmd,check=True,timeout=1200)
        return [{'stack':dest/'stack.json','position':[0.,0.,0.],'rotation':[0.,0.,0.]}]
    return [{'stack':src,'position':[0.,0.,0.],'rotation':[0.,0.,0.]}]


def gd_string(value:str)->str:
    return json.dumps(value,ensure_ascii=False)


def write_project(dest:Path,items:list[dict], addon:Path,license_path:Path|None, source:Path, existing_project:bool=False) -> None:
    target=dest/'addons'/'ShaderStacker'
    if not target.exists():shutil.copytree(addon,target,symlinks=False)
    lic=dest/'THIRD_PARTY_LICENSES';lic.mkdir(exist_ok=True)
    if not license_path or not license_path.is_file():
        raise RuntimeError('Missing upstream MPL-2.0 license; refusing release')
    shutil.copy2(license_path,lic/'ShaderStacker-MPL-2.0.txt')
    if not existing_project:
        (dest/'project.godot').write_text('''; Derived Godot 4 sprite-stack visual viewer. Original game is NOT replaced.\nconfig_version=5\n\n[application]\nconfig/name="META GAMES Sprite Stacking / Shader-Stacker"\nrun/main_scene="res://generated/Main.tscn"\nconfig/features=PackedStringArray("4.0")\n\n[display]\nwindow/size/viewport_width=960\nwindow/size/viewport_height=640\nwindow/stretch/mode="canvas_items"\n\n[editor_plugins]\nenabled=PackedStringArray("res://addons/ShaderStacker/plugin.cfg")\n\n[rendering]\nrenderer/rendering_method="gl_compatibility"\ntextures/canvas_textures/default_texture_filter=0\n''',encoding='utf8')
    else:
        config=dest/'project.godot'
        raw=config.read_text(encoding='utf8')
        addon_ref='res://addons/ShaderStacker/plugin.cfg'
        section=re.search(r'(?ms)^\[editor_plugins\]\s*\n(.*?)(?=^\[|\Z)',raw)
        if section:
            block=section.group(1)
            match=re.search(r'(?m)^enabled\s*=\s*PackedStringArray\(([^\n]*)\)\s*$',block)
            if match:
                if addon_ref not in match.group(1):
                    values=match.group(1).strip()
                    values=values+(', ' if values else '')+gd_string(addon_ref)
                    replacement=match.group(0).replace(match.group(1), values)
                    block=block[:match.start()]+replacement+block[match.end():]
                    raw=raw[:section.start(1)]+block+raw[section.end(1):]
            else:
                if re.search(r'(?m)^enabled\s*=',block):
                    raise ValueError('Unsupported existing editor_plugins.enabled syntax; refusing to rewrite original project configuration')
                raw=raw[:section.start(1)]+'enabled=PackedStringArray('+gd_string(addon_ref)+')\n'+raw[section.start(1):]
        else:
            raw+='\n[editor_plugins]\nenabled=PackedStringArray('+gd_string(addon_ref)+')\n'
        config.write_text(raw,encoding='utf8')
    script='''extends Node2D\n# Preview controls only. Does NOT change original game logic or pose animation.\nvar dragging := false\nvar last_mouse := Vector2.ZERO\n@onready var camera: Camera2D = $StackCamera\n\nfunc _unhandled_input(event: InputEvent) -> void:\n    if event is InputEventMouseButton:\n        if event.button_index == MOUSE_BUTTON_LEFT:\n            dragging = event.pressed\n            last_mouse = event.position\n        elif event.pressed and event.button_index == MOUSE_BUTTON_WHEEL_UP:\n            camera.zoom *= 1.08\n        elif event.pressed and event.button_index == MOUSE_BUTTON_WHEEL_DOWN:\n            camera.zoom /= 1.08\n    elif event is InputEventMouseMotion and dragging:\n        camera.rotation += event.relative.x * 0.008\n\nfunc _process(delta: float) -> void:\n    if Input.is_key_pressed(KEY_Q): camera.rotation -= delta * 0.9\n    if Input.is_key_pressed(KEY_E): camera.rotation += delta * 0.9\n    var step := 240.0 * delta\n    if Input.is_key_pressed(KEY_A): camera.position.x -= step\n    if Input.is_key_pressed(KEY_D): camera.position.x += step\n    if Input.is_key_pressed(KEY_W): camera.position.y -= step\n    if Input.is_key_pressed(KEY_S): camera.position.y += step\n'''
    gen=dest/'generated';gen.mkdir(exist_ok=True)
    (gen/'main.gd').write_text(script,encoding='utf8')
    ext=['[gd_scene load_steps='+str(4+len(items))+' format=3]',
         '[ext_resource type="Script" path="res://addons/ShaderStacker/StackCamera/StackCamera.gd" id="1"]',
         '[ext_resource type="Script" path="res://addons/ShaderStacker/SpriteStack/SpriteStack.gd" id="2"]',
         '[ext_resource type="Script" path="res://generated/main.gd" id="3"]']
    for idx,item in enumerate(items):
        tex=f'res://generated/stack_{idx:03}.png'
        ext.append(f'[ext_resource type="Texture2D" path={gd_string(tex)} id="t{idx}"]')
    nodes=['[node name="Main" type="Node2D"]','script = ExtResource("3")',
           '[node name="StackCamera" type="Camera2D" parent="."]',
           'enabled = true','zoom = Vector2(0.9, 0.7)','script = ExtResource("1")']
    for idx,item in enumerate(items):
        x,y,z=item['position'];w,h=item['slice_size']
        # Projected 2D arrangement only; preserve authored 3D transforms in generated/stack_manifest.json.
        px=round(x*2,4);py=round(y*2 - z*2,4)
        nodes.extend([f'[node name="Stack_{idx:03}" type="Node2D" parent="." groups=["meta_stacks"]]',
                      f'position = Vector2({px}, {py})',
                      'script = ExtResource("2")',
                      f'sprite_sheet = ExtResource("t{idx}")',
                      f'layers = {item["layers"]}',
                      f'pitch = {item["pitch"]:.6g}',
                      f'yaw = {item["yaw"]:.6g}'])
    (gen/'Main.tscn').write_text('\n\n'.join(ext+nodes)+'\n',encoding='utf8')
    # Separate instantiable asset scene does not include a new camera or controls.
    cext=['[gd_scene load_steps='+str(2+len(items))+' format=3]',
      '[ext_resource type="Script" path="res://addons/ShaderStacker/SpriteStack/SpriteStack.gd" id="2"]']
    for idx,_ in enumerate(items):
        cext.append(f'[ext_resource type="Texture2D" path="res://generated/stack_{idx:03}.png" id="t{idx}"]')
    cnodes=['[node name="SpriteStackAssets" type="Node2D"]']
    for idx,item in enumerate(items):
        x,y,z=item['position']
        cnodes.extend([f'[node name="Stack_{idx:03}" type="Node2D" parent="."]',
                       f'position = Vector2({x*2:.6g}, {y*2-z*2:.6g})',
                       'script = ExtResource("2")',
                       f'sprite_sheet = ExtResource("t{idx}")',
                       f'layers = {item["layers"]}',
                       f'pitch = {item["pitch"]:.6g}',
                       f'yaw = {item["yaw"]:.6g}'])
    (gen/'SpriteStackAssets.tscn').write_text('\n\n'.join(cext+cnodes)+'\n',encoding='utf8')

    (gen/'stack_manifest.json').write_text(json.dumps({'source':str(source),'upstream':URL,
        'commit':COMMIT,'license':'MPL-2.0','items':items,'render':'Godot 4 2.5D SpriteStack/StackCamera; native game unaffected',
        'source_fidelity':'RGBA pixel copies; separate source art; viewing angles limited to Godot 2.5D projection'},
        ensure_ascii=False,indent=2),encoding='utf8')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source',type=Path,help='Original stack.json/stack folder/strip PNG/GLB/scene-stacks.json')
    p.add_argument('--out',type=Path,required=True,help='New, empty folder for derived Godot 4 project')
    p.add_argument('--slices',type=int,help='Slice count for a plain strip or four-view carving')
    p.add_argument('--frames',type=int,default=1,help='Only one STATIC pose is supported for Shader-Stacker demo')
    p.add_argument('--four-views',action='store_true',help='Route input 4-view PNG through existing danielwh2 carver')
    p.add_argument('--xy',type=int,default=128)
    p.add_argument('--z',type=int,default=64)
    p.add_argument('--allow-shell',action='store_true')
    p.add_argument('--addon',help='Existing official Shader-Stacker addon/repository; otherwise install pinned Git commit')
    p.add_argument('--no-install',action='store_true',help='No git fetch for official addon')
    p.add_argument('--project-template',type=Path,help='Copy an original Godot 4 project to --out and add addon/scene without changing its main scene')
    a=p.parse_args()
    source=a.source.expanduser().resolve(strict=True)
    dest=a.out.expanduser().resolve()
    if a.frames!=1:raise ValueError('Animated source stacks require authored separate full-pose states; no fabricated animation')
    if a.slices is not None and not 1<=a.slices<=MAX_LAYERS:raise ValueError('Slice count must be 1..192')
    if not 16<=a.xy<=384 or not 8<=a.z<=192:raise ValueError('GLB conversion grid outside 16..384 x 8..192')
    if source==dest or source in dest.parents or (source.is_dir() and dest in source.parents) or (source.is_file() and dest==source.parent):
        raise ValueError('Derived output and original source must be disjoint')
    if dest.exists() and any(dest.iterdir()):raise ValueError('Output folder must be empty; no overwriting')
    template=None
    if a.project_template:
        template=a.project_template.expanduser().resolve(strict=True)
        if not template.is_dir() or not (template/'project.godot').is_file():
            raise ValueError('--project-template needs original Godot 4 project folder')
        if template==dest or template in dest.parents or dest in template.parents:
            raise ValueError('Original Godot project and output must be disjoint')
        for folder,dirs,files in os.walk(template,followlinks=False):
            for name in dirs+files:
                if (Path(folder)/name).is_symlink():
                    raise ValueError('Template has a symlink: cannot safely copy')
    addon, license_path=load_addon(a.addon,a.no_install)
    if template:
        if (template/'addons'/'ShaderStacker').exists():
            raise ValueError('Template already contains ShaderStacker; refusing to overwrite')
        if (template/'generated').exists():
            raise ValueError('Template already contains generated/; refusing to overwrite')
        shutil.copytree(template,dest,dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('.godot','.git','__pycache__','*.tmp'))
    else:
        dest.mkdir(parents=True,exist_ok=True)
    sources=parse_scene_source(source,dest,a.xy,a.z,a.four_views,a.slices,a.allow_shell)
    if len(sources)>MAX_ITEMS:raise ValueError('Too many source stacks')
    results=[]
    for idx,item in enumerate(sources):
        stack=item['stack']
        frames,spacing=as_volume(stack,a.slices if stack.suffix.lower()=='.png' else None,a.frames)
        if len(frames)>1:raise ValueError('Input contains animated frames. Supply one explicitly approved pose')
        vol=frames[0]
        target=dest/'generated'/f'stack_{idx:03}.png'
        save_column(vol,target)
        pitch=max(0.15,min(16,spacing[2]/((spacing[0]+spacing[1])*0.5)))
        results.append({'source':str(stack),'sha256':sha(stack),'sheet_sha256':sha(target),
            'sheet':f'generated/stack_{idx:03}.png','layers':len(vol),'slice_size':list(vol[0].size),
            'position':item['position'],'rotation':item['rotation'],'yaw':item['rotation'][2],
            'pitch':pitch,'spacing':spacing})
    write_project(dest,results,addon,license_path,source,existing_project=bool(template))
    print('Godot 4 Shader-Stacker project:',dest)
    print('Official MPL-2.0 SpriteStack, StackCamera; original files untouched; items:',len(results))


if __name__=='__main__':
    try:main()
    except (ValueError,RuntimeError,OSError,subprocess.SubprocessError) as e:sys.exit('ERROR: '+str(e))
