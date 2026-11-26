#!/usr/bin/env python3
"""Design a bounded, original procedural CSG architecture recipe for a Fusion world.

This script never imports arbitrary JS or third-party asset content. The runtime
uses three-bvh-csg on water-tight primitive brushes. Meshes come from the same
CSG results for Three visuals, Rapier static trimesh and MeshBVH index.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

SCHEMA = 'meta-game-fusion.csg-architecture.v1'
STYLE_PALETTE = {
    'ink': '#535764', 'ember': '#57454b', 'horror': '#303b3b',
    'dream': '#666078', 'pixel': '#535d5f', 'nocturne': '#35454e',
}


def create_plan(world: dict[str,Any], seed: int = 257) -> dict[str,Any]:
    if not isinstance(world,dict) or not isinstance(world.get('nodes'),list):
        raise ValueError('Missing Fusion world nodes')
    if type(seed) is not int or seed < -2**31 or seed > 2**31 - 1:
        raise ValueError('Invalid CSG seed')
    nodes=[n for n in world['nodes'] if isinstance(n,dict) and n.get('type') in ('scene','mechanic')]
    if len(nodes)>24: raise ValueError('CSG stage count exceeds safe limit')
    markers=world.get('markers') or {}
    if not isinstance(markers,dict):raise ValueError('Malformed world markers')
    styles=(world.get('visual_direction') or {}).get('by_node') or {}
    structures=[]
    for i,n in enumerate(nodes):
        scene_id=n.get('id')
        p=markers.get(scene_id)
        if not isinstance(scene_id,str) or not isinstance(p,dict):continue
        z=p.get('z')
        if not isinstance(z,(int,float)) or not math.isfinite(z) or not -150<=z<=150:
            raise ValueError('Invalid CSG stage marker')
        style=styles.get(scene_id,n.get('visual_style','nocturne'))
        if style not in STYLE_PALETTE:style='nocturne'
        # Portal aperture reaches the floor and has >= 10 m clear width, enough for
        # the existing Recast corridor and the single Rapier hero/guide capsules.
        key=int.from_bytes(hashlib.sha256(f'{seed}:{scene_id}'.encode()).digest()[:2],'big')
        width=15.6 + (key%4)*.2
        height=10.2+(key%3)*.3
        opening_width=10.7
        structures.append({
            'id':f'portal_{i+1}', 'scene_id':scene_id,'kind':'gothic-portal',
            'z':round(float(z)-6.4,3),'width':round(width,3),
            'height':round(height,3),'depth':1.65,'opening_width':opening_width,
            'opening_straight_height':4.0,'arch_radius':opening_width/2,
            'palette':STYLE_PALETTE[style], 'style':style,
            'collider':'static-trimesh-exact-csg','navmesh':'open-corridor',
            'animated':False, 'author':'meta-game-fusion-original-procedural',
        })
    return {
        'schema':SCHEMA, 'engine':'three-bvh-csg@0.0.18',
        'three':'three@0.186.1','bvh':'three-mesh-bvh@0.9.18',
        'module':'src/csg-architecture.js','origin':'procedural-owned-geometry',
        'physics_authority':'Rapier','navmesh_authority':'Recast',
        'dynamic_and_skinned_input_forbidden':True,
        'no_assets_silently_replaced':True,'seed':seed,'structures':structures,
    }


def main() -> None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--world',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--seed',type=int,default=257)
    args=p.parse_args()
    if args.world.resolve()==args.output.resolve():p.error('Input and output cannot be identical')
    data=json.loads(args.world.read_text(encoding='utf8'))
    plan=create_plan(data,args.seed)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    if args.output.exists():p.error('Refuse to overwrite a pre-existing plan')
    args.output.write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'structures':len(plan['structures']),'output':str(args.output)}))


if __name__=='__main__':main()
