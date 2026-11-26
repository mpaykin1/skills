#!/usr/bin/env python3
"""Reuse certified genuine horizontal Z-slices with original sprite-in-the-round CLI.

Sprite Stacking Grunge Horror/Three.js/PixiJS/Godot remain unmodified;
this additive native original upstream exporter generates separate GLB, OBJ,
VOX, 16-direction PNG, optional GIF and standalone 360 viewer.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import math
import re
import subprocess
import sys
import zipfile
from pathlib import Path
from PIL import Image, PngImagePlugin
from sprite_stack_bridge import stack as verify_stack, within
from pixijs_bridge import load_scene
from sprite_round_vendor import locate, UpstreamUnavailable, COMMIT

class RoundBridgeError(ValueError):pass

def fail(msg):raise RoundBridgeError('sprite-in-the-round export blocked: '+str(msg))

def ident(raw):
    if not isinstance(raw,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,59}',raw):fail('Unsafe source object/actor ID')
    return raw

def original_stack(root:Path, rel:str, target:Path, expected_pose:bytes|None=None):
    """Make exactly one row of unmodified RGBA stack slices, ground leftmost."""
    expected_sha=hashlib.sha256(expected_pose).hexdigest() if expected_pose is not None else None
    inspected,_=verify_stack(root,rel,expected_sha)
    if len(inspected['slices'])>160:fail('Source stack has too many slices')
    path=within(root,rel);doc=json.loads(path.read_text('utf8'))
    n=len(doc['layers']);sz=inspected['size']
    dx,dy,dz=inspected['spacing']
    if max(dx,dy,dz)/min(dx,dy,dz)>1.025:
        fail('Upstream voxel/mesh exporter assumes uniform XYZ voxel size; original non-uniform slice spacing must not be distorted')
    if sz*n>24_000 or sz*sz*n*4>96_000_000:
        fail('Original full RGBA strip exceeds safe texture/memory budget')
    sheet=Image.new('RGBA',(sz*n,sz),(0,0,0,0))
    archive_root=target.parent/'source_stack'
    if archive_root.exists():fail('Original source_stack archive already exists')
    archive_root.mkdir(parents=True)
    (archive_root/'stack.json').write_bytes(path.read_bytes())
    layers=[]
    for idx,relpng in enumerate(doc['layers']):
        p=within(path.parent,relpng)
        raw=p.read_bytes()
        preserved=archive_root/relpng
        preserved.parent.mkdir(parents=True,exist_ok=True)
        preserved.write_bytes(raw)  # Exact author source PNG, never changed
        with Image.open(io.BytesIO(raw)) as img:
            rgba=img.convert('RGBA')
            if rgba.size!=(sz,sz):fail('Original PNG slice geometry mismatch')
            alpha=rgba.getchannel('A')
            # Upstream stack.py converts all alpha to hard 0/255; fail rather than silently alter art.
            histogram=alpha.histogram()
            if sum(histogram[1:255])>0:fail('Original RGBA contains soft transparency that upstream pixel exporter would change: '+relpng)
            sheet.paste(rgba,(sz*idx,0))
        layers.append({'file':relpng,'sha256':hashlib.sha256(raw).hexdigest()})
    meta=PngImagePlugin.PngInfo();meta.add_text('slices',str(n));meta.add_text('frames','1')
    target.parent.mkdir(parents=True,exist_ok=True)
    sheet.save(target,'PNG',pnginfo=meta)
    with Image.open(target) as check:
        if check.convert('RGBA').tobytes()!=sheet.tobytes():fail('Original source alpha/color was altered while packing strip')
    return {'stack':rel,'source_stack_sha256':inspected['sha256'],'pose_sha256':expected_sha,
            'slices':n,'resolution':sz,'uniform_world_pixel_spacing':dx,
            'strip_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'original_pngs':layers,
            'original_manifest_preserved':True}

def export_one(root,rel,out,upstream,*,name,pose=None,dirs=16,vox=True,turntable=False,viewer=True,objs=True):
    ident(name)
    folder=Path(out)/name
    if folder.exists():fail('Output asset folder already exists; use a fresh destination: '+name)
    folder.mkdir(parents=True,exist_ok=False)
    source=folder/(name+'_slices.png')
    manifest=original_stack(Path(root),rel,source,pose)
    n=manifest['slices']
    command=[sys.executable,str(locate(upstream)/'scripts/stack.py'),str(source),'--count',str(n),
        '--out',str(folder),'--name',name,'--scale','1','--outline','none','--no-shadow',
        '--dirs',str(dirs),'--ppm',str(1/manifest['uniform_world_pixel_spacing'])]
    if vox:command.append('--vox')
    if turntable:command.append('--gif')
    if not viewer:command.append('--no-viewer')
    if not objs:command.append('--no-obj')
    try:
        proc=subprocess.run(command,capture_output=True,text=True,timeout=240,check=False)
    except (OSError,subprocess.TimeoutExpired) as exc:fail('Upstream authentic sprite-in-the-round failed to execute: '+str(exc))
    if proc.returncode:fail('Authentic upstream sprite exporter failed: '+(proc.stderr or proc.stdout)[-1000:])
    try:result=json.loads(proc.stdout)
    except ValueError:fail('Upstream exporter emitted invalid metadata')
    files=result.get('files',{})
    expected=['preview','glb','dirs']+(['viewer'] if viewer else [])+(['obj'] if objs else [])
    if any(k not in files for k in expected):fail('Upstream exporter omitted a mandatory file')
    flat=[]
    for value in files.values():
        for p in (value if isinstance(value,list) else [value]):
            path=Path(p).resolve()
            if folder.resolve() not in path.parents or not path.is_file() or not path.stat().st_size:
                fail('Upstream export file escaped output folder or was not generated')
            flat.append(path)
    glb=Path(files['glb'])
    if glb.open('rb').read(4)!=b'glTF':fail('Genuine binary glTF output invalid')
    if vox and 'vox' in files and Path(files['vox']).open('rb').read(4)!=b'VOX ':
        fail('Genuine VOX output invalid')
    if 'dirs' in files:
        with Image.open(files['dirs']) as img:
            if img.format!='PNG':fail('Direction atlas is not PNG')
    with Image.open(source) as img:
        if img.info.get('slices')!=str(n):fail('Original slice ordering metadata changed')
    meta={'original_stack':manifest,'upstream_commit':COMMIT,'upstream_files':{k:
        [Path(v).name for v in value] if isinstance(value,list) else Path(value).name
        for k,value in files.items()},'warnings':result.get('warnings',[]),
        'source_art_unchanged':True,'derived_mesh_lossless_original_source':False,
        'pixel_quantization_in_vox':True if vox else False}
    (folder/'export.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),'utf8')
    return meta

def scene_assets(approved_zip:Path,scene_path:Path):
    """Get ALL true authored sprite stacking objects and full-body pose stacks."""
    approved_zip=Path(approved_zip).resolve();scene_path=Path(scene_path).resolve()
    approved=load_scene(approved_zip) # unchanged original full-body motion, identity, timeline gate
    with zipfile.ZipFile(approved_zip) as z:
        if z.testzip():fail('Original approved source ZIP damaged')
        cfg=json.loads(z.read('scene.json'))
        gate=json.loads(z.read('motion_gate.json'))
        if gate.get('all_actors_pass') is not True:fail('Original full-body pose gate missing')
        supplied=json.loads(scene_path.read_text('utf8'))
        if supplied.get('inventory')!=cfg.get('inventory') or supplied.get('sprite_stacking')!=cfg.get('sprite_stacking'):
            fail('Original published scene and stacking declarations differ from the approved input')
        stacks=cfg.get('sprite_stacking')
        if not isinstance(stacks,dict) or stacks.get('enabled',True) is not True:
            fail('Original scene does not provide source-painted sprite stacks')
        static=stacks.get('objects',[]);dynamic=stacks.get('actors',[])
        if not isinstance(static,list) or not isinstance(dynamic,list):fail('Malformed original 3D source inventory')
        found=set();items=[]
        for entry in static:
            oid=ident(entry.get('id'))
            if oid in found:fail('Duplicate original volume ID')
            found.add(oid)
            items.append((oid,entry['stack'],None,'prop'))
        poses={a['id']:a for a in cfg.get('actors',[])}
        for entry in dynamic:
            actor=ident(entry.get('actor_id'))
            if actor not in poses or actor in found:fail('Original 3D character missing from validated cast')
            found.add(actor)
            clips=entry.get('clips')
            if not isinstance(clips,dict) or set(clips)!={c['action'] for c in poses[actor]['clips']}:
                fail('Independent full-body volume stacks missing for original character')
            for clip in poses[actor]['clips']:
                action=ident(clip['action']);paths=clips[action]
                if not isinstance(paths,list) or len(paths)!=len(clip['frames']):fail('Volume pose sequence length mismatched')
                for index,(rel,frame) in enumerate(zip(paths,clip['frames'])):
                    raw=z.read('project/inputs/'+frame['png'])
                    items.append((actor+'_'+action+'_'+str(index).zfill(3),rel,raw,'actor_pose'))
        eligible=stacks.get('eligible_object_ids')
        if not isinstance(eligible,list) or len(eligible)==0 or len(set(eligible))!=len(eligible):
            fail('Full source 3D object inventory missing')
        if not found.issubset(set(eligible)):fail('Unknown object not in original source inventory')
        minimum=stacks.get('coverage_min',.9)
        if type(minimum) not in (int,float) or not .75<=minimum<=1:fail('Invalid coverage requirement')
        if len(found)/len(eligible)<max(.9,minimum):fail('Original stacking inventory coverage below 90%')
        if not stacks.get('environment_only',False) and set(poses)!=set(e['actor_id'] for e in dynamic):
            fail('Full game scene requires true original 3D pose stacks for every actor')
        if len(items)>250:fail('Source volume pose count exceeds 250; select a smaller verified scene set')
        return items,{'source_characters':len(poses),'source_volume_entities':len(found),
                      'source_coverage':len(found)/len(eligible),'environment_only':stacks.get('environment_only',False)}

def export_scene(approved_zip:Path,scene_path:Path,out:Path,upstream_root:Path,*,turntable=False,limit=250):
    items,ground=scene_assets(approved_zip,scene_path)
    if len(items)>limit:fail('Source stack count exceeds user specified max: '+str(len(items)))
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    results=[]
    for name,rel,original,kind in items:
        meta=export_one(Path(scene_path).resolve().parent,rel,out,upstream_root,
                        name=name,pose=original,vox=True,turntable=turntable,viewer=kind=='prop',objs=True)
        results.append({'id':name,'kind':kind,'meta':meta})
    doc={'source':'SoAp9035/sprite-in-the-round','commit':COMMIT,'original_source_gates':True,
         'renderer':'real stack.py original CLI','scene':ground,'assets':results}
    (out/'sprite_in_the_round.json').write_text(json.dumps(doc,ensure_ascii=False,indent=2),'utf8')
    return doc

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--upstream',type=Path);p.add_argument('--stack',type=Path)
    p.add_argument('--approved-zip',type=Path);p.add_argument('--scene',type=Path)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--turntable',action='store_true');p.add_argument('--limit',type=int,default=250)
    a=p.parse_args();root=locate(a.upstream)
    if a.stack:
        asset=a.stack.resolve();print(json.dumps(export_one(asset.parent,asset.name,a.out,root,
            name=asset.parent.name if re.fullmatch('[A-Za-z][A-Za-z0-9_-]{0,59}',asset.parent.name) else 'source_stack',
            turntable=a.turntable),ensure_ascii=False))
    else:
        if not a.approved_zip or not a.scene:p.error('--approved-zip and --scene required for full scene')
        print(json.dumps(export_scene(a.approved_zip,a.scene,a.out,root,turntable=a.turntable,limit=a.limit),ensure_ascii=False))
