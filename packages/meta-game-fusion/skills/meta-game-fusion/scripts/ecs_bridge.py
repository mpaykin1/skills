#!/usr/bin/env python3
"""bitECS 0.4.0 glue for the immutable, licensed META GAME FUSION game template.

Creates a declarative stage/authority manifest. Does not execute third-party
project source or generate player controls. Rapier stays physically authoritative.
"""
from __future__ import annotations
import json
import re
from pathlib import Path

ENGINE='bitecs@0.4.0'
SCHEMA='meta-game-fusion.ecs-world.v1'
SAFE_ID=re.compile(r'^[A-Za-z0-9_-]{1,128}$')


def make_plan(world:dict)->dict:
    nodes=world.get('nodes')
    if not isinstance(nodes,list) or len(nodes)>128:
        raise ValueError('ECS requires bounded authored scene graph')
    stages=[]
    for node in nodes:
        if not isinstance(node,dict):raise ValueError('Malformed scene graph node')
        if node.get('type') in ('scene','mechanic'):
            stage=node.get('id')
            if not isinstance(stage,str) or not SAFE_ID.fullmatch(stage):
                raise ValueError('Unsafe ECS stage ID')
            stages.append(stage)
    if not stages or len(stages)>24 or len(set(stages))!=len(stages):
        raise ValueError('ECS requires 1-24 unique stage IDs')
    return {'schema':SCHEMA,'engine':ENGINE,'module':'src/ecs-runtime.js',
      'stages':stages,'max_entities':16,'position_authority':'Rapier',
      'navigation_authority':'Recast','steering_authority':'YUKA',
      'hero_actions_input_only':True,
      'event_types':['scene:enter','player:interact','dialogue:state','quality:mode'],
      'component_types':['Position','Velocity','Player','Scout','Sentinel','AudioEmitter'],
      'static_scene_models_excluded':True,'rights_gate':'ScanCode + SHA-256 + Khronos glTF-Validator',
      'upstream_binary_bundled':False,'npm_dependency_required':True}


def audit(project:Path)->dict:
    project=project.resolve(strict=True)
    world_file=project/'public'/'world.json'
    if world_file.is_symlink() or not world_file.is_file() or world_file.stat().st_size>4_000_000:
        raise ValueError('Missing or unsafe world.json')
    world=json.loads(world_file.read_text('utf-8'))
    plan=make_plan(world)
    if world.get('entity_system')!=plan:raise ValueError('ECS world manifest changed')
    adapter=project/'src'/'ecs-runtime.js'
    if not adapter.is_file() or adapter.is_symlink():raise ValueError('Missing ECS runtime')
    package=json.loads((project/'package.json').read_text('utf-8'))
    if package.get('dependencies',{}).get('bitecs')!='0.4.0':
        raise ValueError('ECS dependency not pinned')
    return {'engine':ENGINE,'scenes':len(plan['stages']),'source':str(adapter)}


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['audit'])
    p.add_argument('--project',type=Path,required=True)
    a=p.parse_args()
    try:print(json.dumps(audit(a.project),ensure_ascii=False))
    except (ValueError,KeyError,OSError,json.JSONDecodeError) as ex:p.exit(2,str(ex)+'\n')
