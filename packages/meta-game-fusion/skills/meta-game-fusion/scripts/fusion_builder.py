#!/usr/bin/env python3
"""META GAME FUSION: deterministic Three.js game assembly.

No source project modification, no eval of imported code, no inferred media rights.
This orchestrates the existing Rete -> Rapier/Recast/Ink/PostFX template with
new living-world visual composition, secure asset gate and immutable sources.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import shutil
import tempfile
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
from typing import Any

import rapier_bridge
from bvh_bridge import create_plan
from meshopt_bridge import audit_project as audit_meshopt
from quarks_bridge import make_plan as make_quarks_plan
from yuka_bridge import make_plan as make_yuka_plan
from ecs_bridge import make_plan as make_ecs_plan
from xstate_bridge import make_plan as make_xstate_plan
from csg_bridge import create_plan as create_csg_plan
from rete_bridge import read_json, ensure_output_not_in_source, BLUEPRINT_SCHEMA
from scancode_bridge import lookup, load_json, sha, INDEX_SCHEMA, SCHEMA as RIGHTS_SCHEMA

BUILD_SCHEMA = 'meta-game-fusion.unified-three-build.v1'
STACK_SCHEMA = 'meta-game-fusion.sprite-stacking.v1'
HEX = re.compile(r'^[a-f0-9]{64}$')
STYLES = rapier_bridge.VISUAL_STYLES


def _index_source(library:Path)->dict[tuple[str,str],tuple[str,Path]]:
    path=library/'fusion-index.json'
    if not path.is_file():raise ValueError('First index source games with fusion.py')
    data=load_json(path, 40_000_000)
    if data.get('schema')!=INDEX_SCHEMA:raise ValueError('Unexpected source index schema')
    out={}
    for game in data.get('games',[]):
        gid=game.get('id');root=Path(game.get('source_root','')).expanduser().resolve()
        for f in game.get('files',[]):
            rel=f.get('path');digest=f.get('sha256')
            if not isinstance(rel,str) or not rel or not HEX.fullmatch(str(digest)):
                continue
            p=PurePosixPath(rel)
            if p.is_absolute() or '..' in p.parts or '\\' in rel:continue
            out[(gid,rel)]=(digest,root.joinpath(*p.parts))
    return out


def asset_gate(library:Path, blueprint:dict[str,Any]|None)->int:
    """Fail closed before conversion/copy if requested model reuse lacks rights or is stale."""
    if blueprint is None:return 0
    if blueprint.get('schema')!=BLUEPRINT_SCHEMA or blueprint.get('runtime_executable') is not False:
        raise ValueError('Only validated, non-executable Rete blueprints accepted')
    models={}
    for step in blueprint.get('scene_plan',[]):
        if not isinstance(step,dict):raise ValueError('Malformed scene plan')
        for doc in step.get('resources',[]):
            if not isinstance(doc,dict):raise ValueError('Malformed scene component')
            if doc.get('kind')=='model':
                key=(doc.get('game'),doc.get('file'),doc.get('source_sha256'))
                models[key]=doc
    if not models:return 0
    path=library/'scancode-rights.json'
    if not path.is_file():raise ValueError('Asset reuse requires local ScanCode rights inventory')
    inventory=load_json(path,64_000_000)
    if inventory.get('schema')!=RIGHTS_SCHEMA:raise ValueError('Unexpected ScanCode rights schema')
    src_index=_index_source(library)
    opt_path=library/'optimized-model-library.json'
    if not opt_path.is_file():raise ValueError('No optimized GLB library for requested models')
    opt=read_json(opt_path,25_000_000)
    approved={(v.get('game'),v.get('path'),v.get('source_sha256')):v for v in opt.get('models',[]) if isinstance(v,dict)}
    for key,doc in models.items():
        game,rel,digest=key
        origin=src_index.get((game,rel))
        if not origin or origin[0]!=digest:raise ValueError('Model source not indexed/hash mismatch: '+str(rel))
        source=origin[1]
        if not source.is_file() or source.is_symlink() or sha(source)!=digest:
            raise ValueError('Model source changed: '+str(rel))
        record=lookup(inventory,game,rel,digest)
        if not record or record.get('status') not in ('reviewed_exception','permissive_detected'):
            raise ValueError('Asset rights not cleared by ScanCode: '+str(rel))
        if not doc.get('approved_for_reuse') or doc.get('license_scan_blocked'):
            raise ValueError('Model not individually approved for reuse: '+str(rel))
        model=approved.get(key)
        if not model or model.get('approved_for_reuse') is not True:
            raise ValueError('No approved optimized asset for '+str(rel))
        op=model.get('optimization') or {}
        if op.get('status') not in ('existing','optimized') or op.get('output')!=doc.get('optimized_output'):
            raise ValueError('Model optimization record missing/changed: '+str(rel))
        asset=rapier_bridge.limited_path(library,op['output'])
        if not asset.is_file() or asset.is_symlink() or sha(asset)!=op.get('output_sha256'):
            raise ValueError('Optimized model hash mismatch: '+str(rel))
    return len(models)


def create_concept_world(world:dict[str,Any],concept:str,style:str,seed:int)->None:
    """An original minimal explorable chapter chain; no invented Ink or borrowed mechanics."""
    text=concept.strip()[:150]
    if not text or any(ord(c)<32 for c in text):raise ValueError('Concept should be nonempty printable text')
    node_names=['Порог','Следы','Тайна','Возвращение']
    themes=list(STYLES)
    index=themes.index(style)
    nodes=[{'id':'start','type':'start','title':'Начало'}]
    links=[];last='start'
    for i in range(3):
        nid=f'chapter_{i+1}'
        st=themes[(index+(i*2))%len(themes)]
        nodes.append({'id':nid,'type':'scene','title':node_names[i]+': '+text,'visual_style':st})
        links.append({'id':f'flow_{i+1}','source':last,'target':nid,'sourceOutput':'flow','targetInput':'flow'})
        last=nid
    nodes.append({'id':'ending','type':'ending','title':node_names[-1]+': '+text})
    links.append({'id':'flow_4','source':last,'target':'ending','sourceOutput':'flow','targetInput':'flow'})
    rapier_bridge.check_world_graph({'nodes':nodes,'connections':links})
    scenes=[v for v in nodes if v['type']=='scene']
    world['title']=text;world['nodes']=nodes;world['connections']=links
    world['markers']={n['id']:{'x':0.,'y':1.35,'z':float(-9-13*i)} for i,n in enumerate(scenes)}
    world['visual_direction']['by_node']={n['id']:n['visual_style'] for n in scenes}
    world['assets']=[]
    world['source']='user-authored-concept';world['seed']=seed


def build(args:argparse.Namespace)->dict[str,Any]:
    library=Path(args.library).expanduser().resolve(strict=True)
    dest=Path(args.out).expanduser().resolve()
    if dest.exists():raise ValueError('Output exists; select a NEW directory to avoid overwrites')
    ensure_output_not_in_source(dest,library)
    if dest==rapier_bridge.ROOT or rapier_bridge.ROOT in dest.parents:
        raise ValueError('Output cannot overwrite plugin templates')
    if dest==library or library in dest.parents or dest in library.parents:
        raise ValueError('Output must be outside library')
    if args.blueprint and args.concept:raise ValueError('Choose either --blueprint or --concept')
    bp=read_json(Path(args.blueprint).expanduser().resolve(strict=True),6_000_000) if args.blueprint else None
    count=asset_gate(library,bp)
    dest.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix='.mgf-build-',dir=dest.parent))
    try:
        rapier_bridge.prepare(SimpleNamespace(library=str(library),out=str(stage),blueprint=args.blueprint,
            workbench=args.workbench,visual_style=args.visual_style))
        world_file=stage/'public'/'world.json'
        world=read_json(world_file,4_000_000)
        if args.concept:create_concept_world(world,args.concept,args.visual_style,args.seed)
        stack_dir=stage/'public'/'sprite-stacks'
        stack_path=stack_dir/'manifest.json'
        if not stack_path.is_file():
            raise ValueError('Sprite Stacking template volume atlases missing')
        if getattr(args,'sprite_stack_source',None):
            import_path=Path(args.sprite_stack_source).expanduser().resolve(strict=True)
            if import_path.is_symlink() or import_path==library or import_path in library.parents:
                raise ValueError('Refusing source slice import from unsafe path')
            from sprite_stack_bridge import compile_source
            stack_manifest=compile_source(import_path,stack_dir,preserve_existing=True)
        else:
            stack_manifest=json.loads(stack_path.read_text('utf-8'))
        if stack_manifest.get('schema')!=STACK_SCHEMA or not stack_manifest.get('assets'):
            raise ValueError('SpriteStack template manifest malformed')
        world['sprite_stacking']={
            'schema':STACK_SCHEMA,'primary_renderer':True,'manifest':'/sprite-stacks/manifest.json',
            'sha256':sha(stack_path),'generated_volume_count':len(stack_manifest['assets']),
            'source_preservation':'no visual replacement of approved external graphics',
            'collision_authority':'Rapier','navigation_authority':'Recast',
            'mesh_source':'true horizontal RGBA volume slices, never one PNG extrusion',
            'horizon_views':'orthographic projections from the SAME 3D slice volume',
            'quality':'mobile sprite atlas batching, static instancing and depth alpha mask',
            'animation':'full coherent pose stacks, player actions only by input',
            'legacy_mechanical_GLBS':'preserved separately from sprite render layers'
        }
        world['renderer']='three@0.186.1'
        world['scene_composer']={'engine':'three@0.186.1','module':'src/living-world.js',
             'procedural_decorations_only':True,'sprite_stack_primary':True,'seed':args.seed,'max_animated_stages':24,
             'hero_actions_input_only':True,'static_collision_source':'Rapier'}
        world['spatial_index']={'engine':'three-mesh-bvh@0.9.18','mode':'runtime-static-triangle-bvh',
             'module':'src/spatial-bvh.js','manifest':'/bvh-manifest.json',
             'physics_authority':'Rapier','navigation_authority':'Recast',
             'animated_and_skinned_models_excluded':True}
        world['csg_architecture']=create_csg_plan(world,args.seed)
        world['csg_architecture']['backend']='manifold-3d@3.5.5'
        world['visual_geometry_pipeline']={'engine':'meshoptimizer@1.3.0',
             'encoding':'EXT_meshopt_compression (optional, glTF-Transform profile meshopt)',
             'decoder':'src/meshopt-loader.js','integrity':'SHA-256 before GLTFLoader parse',
             'geometry_scope':'approved visual GLBs only',
             'physics_authority':'Rapier','navigation_authority':'Recast',
             'mesh_bvh_after_decoding':True,
             'animated_actor_identity_preserved':True}
        rapier_bridge.write_json(world_file,world)
        spatial_plan=create_plan(stage,world) # Fails closed on every approved GLB hash.
        meshopt_manifest=audit_meshopt(stage,world) # Exact bytes / declared EXT_meshopt_compression
        from ktx2_bridge import audit_project as audit_ktx2
        ktx2_manifest=audit_ktx2(stage,world) # Bound KHR_texture_basisu images / SHA-256
        compressed={e['src']:e['compression'] for e in meshopt_manifest['assets']}
        texture_compressed={e['src']:e['texture_compression'] for e in ktx2_manifest['assets']}
        for model_asset in world.get('assets',[]):
            model_asset['compression']=compressed[model_asset['src']]
            model_asset['texture_compression']=texture_compressed[model_asset['src']]
        world['texture_pipeline']={'encoder':'Basis Universal via glTF-Transform CLI + KTX-Software 4.4.0+',
            'texture_profiles':['ktx2-etc1s','ktx2-uastc','mobile-ktx2'],
            'loader':'src/meshopt-loader.js (GLTFLoader + KTX2Loader)',
            'transcoder':'Three.js pinned basis_transcoder.* staged from installed npm package',
            'manifest':'/ktx2-manifest.json', 'verified_textures':ktx2_manifest['compressed_textures'],
            'geometry':'meshoptimizer','physics':'Rapier','navigation':'Recast'}
        world['particle_fx']=make_quarks_plan(world)
        world['npc_ai']=make_yuka_plan(world)
        world['entity_system']=make_ecs_plan(world)
        world['behavior_machine']=make_xstate_plan(world)
        from audio_bridge import make_plan as make_audio_plan
        world['audio'] = make_audio_plan(world,stage)
        world['gltf_validation']={
            'authority':'Khronos glTF-Validator@2.0.0-dev.3.10',
            'gate':'scripts/validate-assets.mjs (predev + prebuild)',
            'approved_model_count':len(world.get('assets',[])),
            'status':'pending-installed-npm' if world.get('assets') else 'no-imported-GLB',
            'hash_pinned':True,'allows_external_resources':False,
            'independent_of':'visual inspection and game browser verification'}
        rapier_bridge.write_json(world_file,world)
        out_assets=world.get('assets',[])
        if bp and len({x.get('id') for x in out_assets})!=count:
            raise ValueError('Some requested approved GLB models could not be copied; refusing partial build')
        manifest={'schema':BUILD_SCHEMA,'engine':'three@0.186.1',
             'components':{'code':'Tree-sitter','asset_import':'Assimp','glb':'glTF-Transform',
                 'index':'Qdrant','graph':'Rete.js','narrative':'inkjs','physics':'Rapier',
                 'navigation':'Recast','spatial':'three-mesh-bvh','architecture':'three-bvh-csg','geometry_compression':'meshoptimizer@1.3.0','gltf_validation':'Khronos glTF-Validator@2.0.0-dev.3.10','texture_compression':'Basis Universal KTX2','solid_csg':'Manifold','fx':'Postprocessing','particles':'three.quarks@0.18.0','agent_steering':'YUKA@0.7.8','entity_system':'bitecs@0.4.0','npc_statecharts':'xstate@5.33.4','sprite_stacking':'real RGBA volume slices + low-angle same-stack views','spatial_audio':'howler@2.2.4','verification':'Playwright','rights':'ScanCode'},
             'chapters':len([v for v in world['nodes'] if v['type'] in ('scene','mechanic')]),
             'approved_asset_count':len(out_assets),'bvh_static_models':sum(a['mode']=='static-raycast' for a in spatial_plan['model_assets']),
             'original_sources_untouched':True,
             'csg_portals':len(world['csg_architecture']['structures']),
             'csg_collision_source':'same-result-triangle-mesh',
             'meshopt_visual_assets':meshopt_manifest['compressed_assets'],
             'meshopt_total_assets':meshopt_manifest['number_of_assets'],
             'ktx2_textures':ktx2_manifest['compressed_textures'],
             'ktx2_models':ktx2_manifest['models_with_ktx2'],
             'meshopt_integrity':'sha256-export-and-browser',
             'solid_csg_backend':'manifold-3d@3.5.5',
             'gltf_validation_gate':'required predev/prebuild before approved GLB loading',
             'sprite_stacking':'RGBA-volume-slice-atlas @ 2.4.0',
             'sprite_stacks':len(stack_manifest['assets']),
             'particle_engine':'three.quarks@0.18.0',
             'particle_emitters':world['particle_fx']['max_emitters'],
             'particle_budget':world['particle_fx']['max_particles'],
             'agent_engine':'yuka@0.7.8',
             'agent_patrols':world['npc_ai']['max_patrols'],
             'agent_physics_authority':'Rapier',
             'ecs_engine':'bitecs@0.4.0','ecs_authority':'Rapier read-only spatial; Rete/Ink event-driven',
             'ecs_actor_budget':world['entity_system']['max_entities'],
             'ecs_scene_count':len(world['entity_system']['stages']),
             'statechart_engine':'xstate@5.33.4',
             'statechart_agents':len(world['behavior_machine']['agents'])+1,
             'statechart_source':'bitECS player interactions + Rete/Ink chapters',
             'audio_engine':'howler@2.2.4','audio_tracks':len(world['audio']['assets']),
             'audio_user_gesture_required':True,'audio_provenance':'original-synthesized',
             'builder_version':'2.4.0', 'npm_deps_required':True}
        rapier_bridge.write_json(stage/'fusion-build.json',manifest)
        stage.rename(dest) # Same parent, atomic when both paths are on one filesystem.
    except Exception:
        shutil.rmtree(stage,ignore_errors=True)
        raise
    return {'out':str(dest),'chapters':manifest['chapters'], 'models':manifest['approved_asset_count']}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['build'])
    p.add_argument('--library',required=True,help='Indexed read-only games, metadata kept outside sources')
    p.add_argument('--out',required=True,help='New project location outside sources and plugin')
    p.add_argument('--blueprint',help='Validated Rete scene blueprint')
    p.add_argument('--workbench',help='Approved Ink stories workbench')
    p.add_argument('--concept',help='New original explorable three-chapter concept without imported game media')
    p.add_argument('--visual-style',choices=STYLES,default='ink')
    p.add_argument('--seed',type=int,default=257)
    p.add_argument('--sprite-stack-source',help='Additional explicitly approved source volume stacks; merges with original scene assets')
    a=p.parse_args()
    try:print(json.dumps(build(a),ensure_ascii=False))
    except (OSError,ValueError,KeyError,TypeError,FileNotFoundError) as e:p.exit(2,str(e)+'\n')

if __name__=='__main__':main()
