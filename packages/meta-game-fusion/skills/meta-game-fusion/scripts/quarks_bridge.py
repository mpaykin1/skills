#!/usr/bin/env python3
"""Pure, deterministic VFX plan for generated Three.js worlds.

Does not modify original games, player controls, story logic, physics or licensed media.
Requires actual three.quarks npm runtime for rendered effects.
"""
from __future__ import annotations
import argparse
import json
import math
import os
from pathlib import Path
import tempfile

ENGINE = 'three.quarks@0.18.0'
STYLES = {'nocturne','ink','ember','horror','dream','pixel'}
MAX_EMITTERS = 3
MAX_PARTICLES = 246


def make_plan(world: dict) -> dict:
    if world.get('schema') != 'meta-game-fusion.physics-world.v1':
        raise ValueError('Only generated META GAME FUSION physics worlds are supported')
    if not isinstance(world.get('markers'), dict):
        raise ValueError('Missing spatial stage markers')
    nodes = [n for n in world.get('nodes', []) if isinstance(n, dict) and n.get('type') in ('scene', 'mechanic')]
    if len(nodes) > 24:
        raise ValueError('VFX stage budget exceeded (24)')
    styles = world.get('visual_direction', {})
    default = styles.get('default', 'nocturne')
    if default not in STYLES:
        raise ValueError('Unknown VFX default palette')
    per_node = styles.get('by_node') or {}
    if not isinstance(per_node, dict):
        raise ValueError('Invalid Rete/Ink scene palette map')
    stages={}
    for node in nodes:
        name=node.get('id')
        if not isinstance(name,str) or not name or name in stages:
            raise ValueError('Invalid duplicate scene ID')
        p=world['markers'].get(name)
        if not isinstance(p,dict) or any(not isinstance(p.get(c),(int,float)) or isinstance(p.get(c),bool) or not math.isfinite(p[c]) or abs(p[c])>10000 for c in ('x','y','z')):
            raise ValueError('Invalid stage marker: '+name)
        palette=per_node.get(name, node.get('visual_style',default))
        if palette not in STYLES:
            raise ValueError('Unrecognized scene style: '+name)
        stages[name]={'style':palette,'origin':{c:float(p[c]) for c in ('x','y','z')}}
    return {'schema':'meta-game-fusion.particle-fx.v1','engine':ENGINE,
            'adapter':'src/vfx-quarks.js','scene_cues':stages,
            'channels':['mist','ash','rune'],'max_emitters':MAX_EMITTERS,
            'max_particles':MAX_PARTICLES,'quality_source':'Postprocessing cinema/eco/off',
            'scene_events':'Rete/Ink only','physics_authority':'Rapier',
            'navigation_authority':'Recast','visual_only':True,
            'hero_input_only':True,'remote_media':False}


def configure(project:Path)->dict:
    root=project.resolve(strict=True)
    world_file=root/'public'/'world.json'
    package=root/'package.json'
    module=root/'src'/'vfx-quarks.js'
    if any(f.is_symlink() for f in (world_file,package,module)):
        raise ValueError('Symlinked files not accepted')
    if not all(p.is_file() for p in (world_file,package,module)):
        raise ValueError('Expected generated META GAME FUSION world with Quarks adapter')
    pkg=json.loads(package.read_text('utf-8'))
    if pkg.get('name')!='meta-game-fusion-rapier-world' or pkg.get('dependencies',{}).get('three.quarks')!='0.18.0':
        raise ValueError('Required three.quarks@0.18.0 not installed in generated template')
    world=json.loads(world_file.read_text('utf-8'))
    world['particle_fx']=make_plan(world)
    fd,name=tempfile.mkstemp(prefix='.world-vfx-',suffix='.json',dir=world_file.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f:
            json.dump(world,f,ensure_ascii=False,indent=2)
            f.write('\n')
        os.replace(name,world_file)
    finally:
        if os.path.exists(name):os.unlink(name)
    return world['particle_fx']


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['configure','inspect'])
    p.add_argument('--project',required=True)
    args=p.parse_args()
    try:
        project=Path(args.project)
        if args.command=='configure':out=configure(project)
        else:out=make_plan(json.loads((project/'public'/'world.json').read_text('utf-8')))
        print(json.dumps(out,ensure_ascii=False,indent=2))
    except (OSError,ValueError,TypeError,KeyError) as exc:
        p.exit(2,f'{exc}\n')

if __name__=='__main__':main()
