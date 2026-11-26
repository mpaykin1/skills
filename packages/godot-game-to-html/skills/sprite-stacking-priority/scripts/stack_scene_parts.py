#!/usr/bin/env python3
"""Original STATIC GLB scene -> independent actual sprite stacks -> one offline HTML.

Splits each original mesh instance using its genuine scene-graph transform,
then delegates voxel material sampling to the existing stack_from_glb.py and
volume rendering to stack_to_html.py. No generated props, AI gameplay or meshes
are presented as original. Original GLB is never modified.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import trimesh

HERE = Path(__file__).resolve().parent
MAX_OBJECTS = 32          # Existing renderer's maximum unique volume textures
MAX_FACES = 400_000       # Existing converter hard limit per part


def safe_name(s: str, index: int) -> str:
    name = re.sub(r'[^a-zA-Z0-9_-]+', '_', str(s)).strip('_')[:42] or 'object'
    return f'{index:03d}_{name}'


def inspect_scene(source: Path):
    # Avoid freezing skinned/animated authored subjects into static objects.
    from stack_from_glb import glb_info
    metadata = glb_info(source)
    for container in ('images', 'buffers'):
        for item in metadata.get(container, []):
            if item.get('uri') and not item['uri'].startswith('data:'):
                raise ValueError('External texture or buffer reference: use a self-contained original GLB')
    if metadata.get('skins') or metadata.get('animations'):
        raise ValueError('Source includes authored skinning/animations: use original GLB renderer or explicit full-pose stacks; do not freeze')
    scene = trimesh.load(source, force='scene', process=False)
    parts = []
    for node in sorted(scene.graph.nodes_geometry, key=str):
        transform, geometry_id = scene.graph.get(node)
        original = scene.geometry.get(geometry_id)
        if not isinstance(original, trimesh.Trimesh) or not len(original.faces):
            continue
        mat = np.asarray(transform, dtype=np.float64)
        if mat.shape != (4, 4) or not np.isfinite(mat).all() or abs(np.linalg.det(mat[:3, :3])) < 1e-12:
            raise ValueError(f'Invalid original node transform: {node}')
        if len(original.faces) > MAX_FACES:
            raise ValueError(f'Mesh too dense for faithful CPU conversion: {node}')
        # World transform is baked once, without altering UV0 or original images.
        mesh = original.copy()
        mesh.apply_transform(mat)
        parts.append({'node':str(node),'geometry':str(geometry_id),'mesh':mesh,
                      'transform':mat,'face_count':int(len(original.faces))})
    if not parts:
        raise ValueError('No original geometries with actual triangles found')
    return parts


def build(source:Path, output:Path, xy:int=128, z:int=64,
          allow_shell:bool=True, build_html:bool=True, no_install:bool=False, manifold:str='audit'):
    source=source.expanduser().resolve(strict=True)
    output=output.expanduser().resolve()
    if source.suffix.lower() != '.glb':
        raise ValueError('Input must be an original, self-contained .glb')
    if output == source.parent or output in source.parents or source in output.parents:
        raise ValueError('Output must not overlap original source')
    if output.exists() and any(output.iterdir()):
        raise ValueError('Output must be empty: refusing to overwrite prior generated assets')
    if not 16 <= xy <= 384 or not 8 <= z <= 192:
        raise ValueError('Grid limits: xy=16..384, z=8..192')
    if manifold=='union':raise ValueError('Do not union independent scene nodes; use direct static GLB --manifold union instead')
    parts = inspect_scene(source)
    if len(parts) > MAX_OBJECTS:
        raise ValueError(f'{len(parts)} original mesh nodes exceed the safe {MAX_OBJECTS}-volume renderer limit; split into authored scene chunks instead of silently dropping objects')
    sha=hashlib.sha256()
    with source.open('rb') as original:
        for block in iter(lambda:original.read(1024*1024),b''):sha.update(block)
    digest=sha.hexdigest()
    output.mkdir(parents=True,exist_ok=True)
    entries=[]
    for idx,part in enumerate(parts):
        sub=output/'parts'/safe_name(part['node'],idx)
        sub.mkdir(parents=True,exist_ok=True)
        # Keep identity as GLB node label, not a generic replacement geometry.
        own_scene=trimesh.Scene()
        own_scene.add_geometry(part['mesh'], node_name=part['node'], geom_name=part['geometry'])
        individual=sub/'source-part.glb'
        individual.write_bytes(own_scene.export(file_type='glb'))
        stack_folder=sub/'volume'
        cmd=[sys.executable,str(HERE/'stack_from_glb.py'),str(individual),
             '--out',str(stack_folder),'--xy',str(xy),'--z',str(z)]
        if allow_shell:cmd.append('--allow-shell')
        cmd.extend(['--manifold',manifold])
        subprocess.run(cmd, check=True, timeout=1800)
        manifest=stack_folder/'stack.json'
        info=json.loads(manifest.read_text(encoding='utf-8'))
        info['original_glb_sha256']=digest
        info['original_scene_node']=part['node']
        info['original_geometry_id']=part['geometry']
        info['original_face_count']=part['face_count']
        info['original_node_transform']=part['transform'].tolist()
        manifest.write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf-8')
        entries.append({'stack':str(manifest.relative_to(output)).replace('\\','/'),
                        'position':[0,0,0], 'rotation':[0,0,0], 'scale':[1,1,1]})
    scenejson=output/'scene.json'
    scenejson.write_text(json.dumps({'stacks':entries,'original_glb_sha256':digest,
        'kind':'independent-true-volume-stacks','original_node_count':len(parts)},ensure_ascii=False,indent=2),encoding='utf-8')
    print('ORIGINAL NODES -> INDEPENDENT STACKS:',len(parts),scenejson)
    if build_html:
        cmd=[sys.executable,str(HERE/'stack_to_html.py'),str(scenejson),
             '--out',str(output/'sprite-stacking.html')]
        if no_install:cmd.append('--no-install')
        subprocess.run(cmd,check=True,timeout=720)
        print('AUTONOMOUS 360-DEGREE VISUAL HTML:',output/'sprite-stacking.html')
    return scenejson


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source',type=Path)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--xy',type=int,default=128)
    p.add_argument('--z',type=int,default=64)
    p.add_argument('--closed-only',action='store_true',help='Reject open meshes instead of retaining real shells')
    p.add_argument('--assets-only',action='store_true',help='Build independent volume stacks and scene JSON but no HTML')
    p.add_argument('--no-install',action='store_true',help='Use local pinned npm Three.js/esbuild only')
    p.add_argument('--manifold',choices=['off','audit','normalize'],default='audit')
    a=p.parse_args()
    try:build(a.source,a.out,a.xy,a.z,not a.closed_only,not a.assets_only,a.no_install,a.manifold)
    except (ValueError,RuntimeError,OSError,ImportError,subprocess.SubprocessError) as e:
        p.exit(1,'ERROR: '+str(e)+'\n')

if __name__=='__main__':main()
