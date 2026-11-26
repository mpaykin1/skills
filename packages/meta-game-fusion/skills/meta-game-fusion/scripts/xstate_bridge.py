#!/usr/bin/env python3
"""Declare/pin audited XState behavior transitions for existing YUKA NPCs.

No source-game code/characters replaced. The authored world has a fixed state
machine and a bounded stage registry. No user-provided executable transitions.
"""
from __future__ import annotations
import json
from pathlib import Path

SCHEMA='meta-game-fusion.behavior-machines.v1'
ENGINE='xstate@5.33.4'

def make_plan(world:dict)->dict:
    ecs=world.get('entity_system') or {}
    npc=world.get('npc_ai') or {}
    stages=ecs.get('stages')
    patrols=npc.get('patrols')
    if (ecs.get('schema')!='meta-game-fusion.ecs-world.v1' or
        ecs.get('engine')!='bitecs@0.4.0' or
        npc.get('engine')!='yuka@0.7.8' or
        ecs.get('position_authority')!='Rapier' or
        ecs.get('navigation_authority')!='Recast' or
        ecs.get('steering_authority')!='YUKA'):
        raise ValueError('XState requires the pinned bitECS / YUKA authority contract')
    if (not isinstance(stages,list) or not 1<=len(stages)<=24 or
        not all(isinstance(s,str) and len(s)<=128 and s.replace('-','').replace('_','').isalnum() for s in stages) or
        len(stages)!=len(set(stages))):
        raise ValueError('Invalid XState stage registry')
    if (not isinstance(patrols,list) or len(patrols)>2 or len(patrols)==0 or
        [a.get('id') for a in patrols]!=['sentinel-1','sentinel-2'][:len(patrols)]):
        raise ValueError('XState requires trusted YUKA sentinel IDs')
    return {'schema':SCHEMA,'engine':ENGINE,'module':'src/behavior-xstate.js',
        'event_authority':'bitECS','steering_authority':'YUKA',
        'navigation_authority':'Recast','position_authority':'Rapier',
        'hero_actions_input_only':True,'stages':list(stages),
        'agents':[a['id'] for a in patrols],
        'npc_states':['patrol','investigate','return','recover'],
        'guide_states':['idle','following','arrived','blocked'],
        'allowed_events':['SCENE','PLAYER_SIGNAL','REACHED','BLOCKED','TIMEOUT','RETRY'],
        'investigation_seconds':7.5,'recovery_seconds':1.25,
        'max_machine_actors':3,'source_assets_untouched':True,
        'runtime_dependency_bundled':False,'runtime_validation':'pending npm installation'}

def audit(project:Path)->dict:
    project=project.resolve(strict=True)
    w=project/'public/world.json'
    if w.is_symlink() or not w.is_file() or w.stat().st_size>4_000_000:
        raise ValueError('Untrusted game manifest')
    world=json.loads(w.read_text('utf-8'))
    expected=make_plan(world)
    if world.get('behavior_machine')!=expected:
        raise ValueError('XState behavior machine manifest mismatch')
    adapter=project/'src/behavior-xstate.js'
    if not adapter.is_file() or adapter.is_symlink():
        raise ValueError('Missing XState runtime adapter')
    pkg=json.loads((project/'package.json').read_text('utf-8'))
    if pkg.get('dependencies',{}).get('xstate')!='5.33.4':
        raise ValueError('Unpinned XState 5.33.4 runtime')
    return {'engine':ENGINE,'agents':expected['agents'],'stages':len(expected['stages'])}

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['audit']);p.add_argument('--project',type=Path,required=True)
    a=p.parse_args()
    try:print(json.dumps(audit(a.project),ensure_ascii=False))
    except (OSError,ValueError,KeyError,TypeError,json.JSONDecodeError) as e:p.exit(2,str(e)+'\n')
