#!/usr/bin/env python3
"""Local licensed audio planner for original META GAME FUSION game builds.

Howler owns audio only. YUKA/Recast/Rapier/Ink remain authoritative for their
respective concerns. No external URLs, third-party recordings, or source writes.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

ENGINE='howler@2.2.4'
SCHEMA='meta-game-fusion.spatial-audio.v1'
STYLES={'ink','nocturne','ember','horror','dream','pixel'}
TRACKS=('wind','drone','step','rune')
MAX_BYTES=2_000_000
MIX={
 'ink':{'wind':.26,'drone':.12},
 'nocturne':{'wind':.30,'drone':.22},
 'ember':{'wind':.16,'drone':.27},
 'horror':{'wind':.24,'drone':.32},
 'dream':{'wind':.20,'drone':.14},
 'pixel':{'wind':.18,'drone':.13},
}


def digest(p:Path)->str:
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(256*1024),b''):h.update(block)
    return h.hexdigest()


def make_plan(world:dict,project:Path)->dict:
    if world.get('schema')!='meta-game-fusion.physics-world.v1':
        raise ValueError('Spatial audio requires generated MGF physics world')
    root=project.resolve(strict=True)
    audio=root/'public'/'audio'
    if not audio.is_dir() or audio.is_symlink():raise ValueError('Original audio pack missing')
    license_file=audio/'SOURCE.txt'
    if not license_file.is_file() or license_file.is_symlink() or 'Original deterministic synthesized MGF' not in license_file.read_text('utf8'):
        raise ValueError('Original audio provenance not found')
    sounds={}
    for track in TRACKS:
        entries=[]
        for ext in ('ogg','mp3'):
            f=audio/f'{track}.{ext}'
            if not f.is_file() or f.is_symlink() or not 200<f.stat().st_size<=MAX_BYTES:
                raise ValueError('Missing/untrusted audio: '+str(f))
            entries.append({'uri':f'/audio/{track}.{ext}','sha256':digest(f),'bytes':f.stat().st_size})
        sounds[track]={'sources':entries,'origin':'original-synthesized','license':'authored-demo'}
    stages={}
    direction=world.get('visual_direction') or {}
    per_node=direction.get('by_node') or {}
    base=direction.get('default','nocturne')
    nodes=[n for n in world.get('nodes',[]) if n.get('type') in ('scene','mechanic')]
    if len(nodes)>24 or base not in STYLES or not isinstance(per_node,dict):
        raise ValueError('Invalid audio stage count/styles')
    for n in nodes:
        name=n.get('id')
        style=per_node.get(name,n.get('visual_style',base))
        if not isinstance(name,str) or not 1<=len(name)<=128 or name in stages or style not in STYLES:
            raise ValueError('Invalid stage/audio style')
        p=(world.get('markers') or {}).get(name)
        if not isinstance(p,dict) or not all(isinstance(p.get(a),(int,float)) for a in ('x','y','z')):
            raise ValueError('Missing audio stage marker: '+name)
        stages[name]={'style':style,'mix':MIX[style],'source_marker':name}
    return {'schema':SCHEMA,'engine':ENGINE,'adapter':'src/spatial-audio.js',
            'audio_locked_until_user_gesture':True,'user_can_mute':True,
            'channels':{'ambient':['wind','drone'],'events':['step','rune']},
            'assets':sounds,'scene_cues':stages,'max_voices':8,
            'spatial_source':'Rapier player and NPC positions + camera listener',
            'npc_behavior_source':'YUKA via Recast',
            'story_source':'Rete/Ink validated scene events',
            'screenfx_source':'Postprocessing quality (independent mute)',
            'external_audio':False,'original_game_audio_untouched':True}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=('inspect',))
    p.add_argument('--project',required=True)
    args=p.parse_args()
    project=Path(args.project)
    try:
        w=json.loads((project/'public'/'world.json').read_text(encoding='utf8'))
        print(json.dumps(make_plan(w,project),ensure_ascii=False,indent=2))
    except (OSError,ValueError,KeyError,TypeError) as e:p.exit(2,f'{e}\n')

if __name__=='__main__':main()
