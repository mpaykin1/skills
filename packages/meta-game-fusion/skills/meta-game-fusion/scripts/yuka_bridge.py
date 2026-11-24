#!/usr/bin/env python3
"""Bounded YUKA steering plan; Recast is route authority, Rapier is physics authority.

No imported NPC art, source games, or hero actions are modified. All authored
patrol positions are constrained to the central floor of the existing world.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path

ENGINE='yuka@0.7.8'
STYLES=frozenset({'ink','nocturne','horror','ember','dream','pixel'})
PATROLS=[
    {'id':'sentinel-1','start':{'x':0.8,'y':1.25,'z':-7.5},'end':{'x':0.6,'y':1.25,'z':-17.0}},
    {'id':'sentinel-2','start':{'x':-0.4,'y':1.25,'z':-35.5},'end':{'x':0.4,'y':1.25,'z':-51.0}},
]

def make_plan(world:dict)->dict:
    if world.get('schema')!='meta-game-fusion.physics-world.v1':
        raise ValueError('YUKA accepts only a generated MGF physics world')
    nodes=[n for n in world.get('nodes',[]) if isinstance(n,dict) and n.get('type') in ('scene','mechanic')]
    if len(nodes)>24:raise ValueError('Too many stages for bounded NPC AI')
    visual=world.get('visual_direction') or {}
    default=visual.get('default','nocturne')
    if default not in STYLES:raise ValueError('Unsupported NPC atmospheric style')
    style_map=visual.get('by_node') or {}
    if not isinstance(style_map,dict):raise ValueError('Invalid scene styles')
    cues={}
    for node in nodes:
        nid=node.get('id')
        if not isinstance(nid,str) or not nid or len(nid)>128 or nid in cues:
            raise ValueError('Unsafe stage ID for NPC scene cue')
        style=style_map.get(nid,node.get('visual_style',default))
        if style not in STYLES:raise ValueError('Unknown NPC scene style')
        cues[nid]={'style':style,'behavior':'patrol-and-investigate'}
    if len(world.get('assets') or [])>128:raise ValueError('Excess asset count')
    for patrol in PATROLS:
        for pt in (patrol['start'],patrol['end']):
            if not all(isinstance(pt.get(k),(int,float)) and not isinstance(pt.get(k),bool)
                       and math.isfinite(pt[k]) and abs(pt[k])<110 for k in ('x','y','z')):
                raise ValueError('Invalid NPC patrol coordinates')
    return {'schema':'meta-game-fusion.npc-ai.v1','engine':ENGINE,
        'adapter':'src/ai-yuka.js','patrols':PATROLS,'scene_cues':cues,
        'max_patrols':2,'scout_count':1,'tick_hz':60,
        'steering':'YUKA FollowPathBehavior + ArriveBehavior',
        'route_source':'Recast Detour NavMesh (no straight-line bypass)',
        'navigation_authority':'Recast','physics_authority':'Rapier',
        'sensory_source':'MeshBVH static line of sight + player interaction',
        'world_events':'Rete/Ink chapter switch; manual interaction to investigate',
        'hero_input_only':True,'approved_imported_characters_replaced':False,
        'render':'independent original articulated Three.js NPCs',
        'mobile_quality':'fixed 2 NPC budget, no unbounded search'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['inspect'])
    p.add_argument('--world',required=True)
    a=p.parse_args()
    try:
        wpath=Path(a.world).resolve(strict=True)
        if wpath.is_symlink() or not wpath.is_file() or wpath.stat().st_size>4_000_000:
            raise ValueError('Invalid world manifest')
        world=json.loads(wpath.read_text('utf-8'))
        print(json.dumps(make_plan(world),ensure_ascii=False,indent=2))
    except (ValueError,TypeError,OSError,KeyError) as e:p.exit(2,f'{e}\n')

if __name__=='__main__':main()
