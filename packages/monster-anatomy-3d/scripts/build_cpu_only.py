#!/usr/bin/env python3
"""GPU-free end-to-end Blender anatomical creature build.

No network downloads, CUDA, SkinTokens or TRELLIS.2 inference. Blender uses CPU
for procedural modelling, skinning and glTF export. Source is a Blender scene
with one MONSTER_RIG; when absent, generate an original monster blockout.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import shutil
import subprocess
import sys

BASE=Path(__file__).resolve().parent


def call(*parts):
    subprocess.run([str(x) for x in parts],check=True)


def main():
    p=argparse.ArgumentParser(description='Monster Anatomy 3D: CPU-only Blender build')
    p.add_argument('--blender',default='blender')
    p.add_argument('--output-dir',default='build/monster-cpu')
    p.add_argument('--input-blend',default='',help='Existing .blend with MONSTER_RIG; defaults to new original blockout')
    p.add_argument('--skin-method',choices=('auto','proximity'),default='auto')
    p.add_argument('--scipy-skin-smooth',action='store_true',help='Real SciPy CPU surface diffusion on NEW unweighted muscle/skin meshes only')
    p.add_argument('--scipy-python',default=sys.executable,help='External CPU Python with numpy and scipy==1.17.0')
    p.add_argument('--scipy-iterations',type=int,default=3)
    p.add_argument('--scipy-strength',type=float,default=0.35)
    p.add_argument('--pymeshlab-audit',action='store_true',help='CPU geometry safety inspection before rigging')
    p.add_argument('--pymeshlab-clean-static',action='store_true',help='Repair eligible, unrigged static triangle meshes via real PyMeshLab CPU')
    p.add_argument('--pymeshlab-python',default=sys.executable,help='External CPU Python with PyMeshLab installed')
    p.add_argument('--manifold-cpu',action='store_true',help='Real Manifold3D CPU union of 2+ safe static muscle/body solids, adds reference only')
    p.add_argument('--manifold-objects',default='',help='Comma separated exact unskinned static mesh names; auto detect MUSCLE_/BODY_/SHELL_')
    p.add_argument('--manifold-python',default=sys.executable,help='External Python with manifold3d==3.5.5, trimesh and numpy')
    p.add_argument('--xatlas-uv',action='store_true',help='CPU UV atlas for monster meshes with no UVs; preserve skin/morphs')
    p.add_argument('--xatlas-python',default=sys.executable,help='External Python containing xatlas==0.0.11 + numpy')
    p.add_argument('--xatlas-allow-noop',action='store_true',help='Permit no new UV sets when every mesh already has UVs')
    p.add_argument('--pbr-cpu',action='store_true',help='Pillow 12.3.0 CPU PBR textures from xatlas UVs')
    p.add_argument('--pbr-size',type=int,choices=(128,256,512,1024,2048),default=512)
    p.add_argument('--pbr-wetness',type=float,default=0.35,help='0=dry original roughness; 1=wet glossy skin')
    p.add_argument('--pbr-python',default=sys.executable,help='CPU Python with Pillow==12.3.0')
    p.add_argument('--gltf-optimize',action='store_true',help='CPU-only glTF-Transform safe post-export dedup; preserves source GLB')
    p.add_argument('--gltf-mode',choices=('safe','meshopt'),default='safe',help='meshopt needs extra Three.js decoder')
    p.add_argument('--gltf-transform-bin',default='',help='Official installed gltf-transform CLI path')
    p.add_argument('--trimesh-audit',action='store_true',help='Optional Trimesh CPU mesh topology audit on final uncompressed GLB')
    p.add_argument('--trimesh-strict',action='store_true',help='Fail on non-manifold edges or inconsistent winding (open boundaries remain advisory)')
    p.add_argument('--trimesh-python',default=sys.executable,help='CPU Python with trimesh==4.11.1 and numpy')
    p.add_argument('--meshoptimizer',action='store_true',help='Official gltfpack v1.3 CPU optimizer after glTF-Transform; Khronos gate required')
    p.add_argument('--meshoptimizer-mode',choices=('safe','compressed'),default='safe',help='compressed needs MeshoptDecoder in Three.js')
    p.add_argument('--gltfpack-bin',default='',help='Exact official gltfpack executable (or vendor/gltfpack-v1.3)')
    p.add_argument('--gltf-validate',action='store_true',help='Run official Khronos glTF-Validator on CPU, before/after optional optimization')
    p.add_argument('--gltf-validate-strict-warnings',action='store_true',help='Reject Khronos warnings as well as errors')
    p.add_argument('--gltf-validator-package',default='',help='Directory of official installed gltf-validator npm package')
    p.add_argument('--gltf-validator-node',default='',help='Path to Node.js executable')
    p.add_argument('--no-sprite-stacking',action='store_true',help='Legacy GLB-only output; TRUE Sprite Stacking is default')
    p.add_argument('--sprite-clip',default='ALL',help='Baked rig Action to produce complete 3D stacks')
    p.add_argument('--sprite-frames',type=int,default=12,help='Number of independent posed full stacks')
    p.add_argument('--sprite-xy-size',type=int,choices=(64,96,128,192,256),default=96)
    p.add_argument('--sprite-z-slices',type=int,choices=(32,48,64,96,128),default=64)
    p.add_argument('--sprite-allow-open',action='store_true',help='Opt in to thin open mesh shell voxelization')
    p.add_argument('--workbench-copies',action='store_true')
    p.add_argument('--skip-morphs',action='store_true',help='Keep existing shapes intact; bypass muscle morph generation')
    p.add_argument('--mocap-video',default='',help='CPU Open Mocap body-motion video')
    p.add_argument('--mocap-side-video',default='',help='Optional synchronized second camera video')
    p.add_argument('--mocap-landmarks',default='',help='Existing authentic Open Mocap CPU landmark JSON')
    p.add_argument('--mocap-clip',default='MOCAP_WALK',help='New unique NLA clip name')
    p.add_argument('--mocap-bone-map',default='',help='Explicit mapping of MONSTER_RIG bones to 40 landmarks')
    p.add_argument('--mocap-mirror',action='store_true')
    a=p.parse_args()
    if a.trimesh_strict and not a.trimesh_audit:p.error('--trimesh-strict requires --trimesh-audit')
    if not 1<=a.scipy_iterations<=8 or not 0<=a.scipy_strength<=0.65:p.error('SciPy iterations 1..8; strength 0..0.65')
    if a.manifold_objects and not a.manifold_cpu:p.error('--manifold-objects requires --manifold-cpu')
    if a.pbr_cpu and not a.xatlas_uv:p.error('--pbr-cpu requires --xatlas-uv (no ambiguous pre-existing UV use)')
    if not 0<=a.pbr_wetness<=1:p.error('--pbr-wetness must be 0..1')
    if a.meshoptimizer and a.gltf_optimize and a.gltf_mode!='safe':p.error('glTF-Transform meshopt output cannot be fed into gltfpack; use --gltf-mode safe')
    if a.gltf_mode!='safe' and not a.gltf_optimize:p.error('--gltf-mode requires --gltf-optimize')
    if a.gltf_validate_strict_warnings and not a.gltf_validate:p.error('--gltf-validate-strict-warnings needs --gltf-validate')
    if a.mocap_video and a.mocap_landmarks:p.error('Use only one of --mocap-video / --mocap-landmarks')
    if a.mocap_side_video and not a.mocap_video:p.error('--mocap-side-video requires --mocap-video')
    blender=Path(a.blender).expanduser() if '/' in a.blender or '\\' in a.blender else shutil.which(a.blender)
    if not blender or not Path(blender).is_file():p.error('Blender CPU executable missing; install Blender 4.5 LTS and supply --blender path')
    output=Path(a.output_dir).expanduser().resolve();output.mkdir(parents=True,exist_ok=True)
    raw=output/'monster_cpu_base.blend';skin=output/'monster_cpu_skinned.blend'
    if a.input_blend:
        src=Path(a.input_blend).expanduser().resolve()
        if not src.is_file() or src.suffix.lower()!='.blend':p.error('--input-blend must point to an existing .blend')
        raw=src
    else:
        # Original CPU-generated animated monster, no GPU and no downloads.
        call(blender,'--background','--factory-startup','--python-exit-code','3',
             '--python',BASE/'build_monster.py','--', '--blend',raw,
             '--output',output/'monster_cpu_base.glb')
    if a.pymeshlab_audit or a.pymeshlab_clean_static:
        cleaned=output/'monster_cpu_pymeshlab.blend'
        mesh_stats=output/'monster_cpu_pymeshlab.json'
        if cleaned.exists() or mesh_stats.exists():p.error('PyMeshLab output already exists; use a new --output-dir')
        command=[blender,'--background','--factory-startup','--python-exit-code','3',
             '--python',BASE/'pymeshlab_blender_bridge.py','--','--blend',raw,
             '--output-blend',cleaned,'--output-json',mesh_stats,
             '--python-bin',a.pymeshlab_python]
        if a.pymeshlab_clean_static:command.append('--clean-static')
        call(*command)
        raw=cleaned
    if a.manifold_cpu:
        reference=output/'monster_cpu_manifold_guide.blend'
        cmd=[blender,'--background','--factory-startup','--python-exit-code','3',
             '--python',BASE/'manifold3d_blender_bridge.py','--',
             '--blend',raw,'--output-blend',reference,'--python-bin',a.manifold_python]
        if a.manifold_objects:cmd+=['--objects',a.manifold_objects]
        call(*cmd)
        raw=reference
    skin_cmd=[blender,'--background','--factory-startup','--python-exit-code','3',
         '--python',BASE/'cpu_skinning_blender.py','--','--blend',raw,
         '--output-blend',skin,'--method',a.skin_method]
    if a.scipy_skin_smooth:
        skin_cmd+=['--scipy-skin-smooth','--scipy-python',a.scipy_python,
                   '--scipy-iterations',a.scipy_iterations,'--scipy-strength',a.scipy_strength]
    call(*skin_cmd)
    final=output/'monster_cpu_animated.blend';glb=output/'monster_cpu_animated.glb'
    if a.skip_morphs:
        # Export the same CPU-skinned character and preserve pre-existing clips.
        call(blender,'--background','--factory-startup','--python-exit-code','3',
             '--python',BASE/'cpu_skinning_blender.py','--','--blend',skin,
             '--output-blend',final,'--output-glb',glb)
    else:
        extra=['--workbench-copies'] if a.workbench_copies else []
        call(blender,'--background','--factory-startup','--python-exit-code','3',
             '--python',BASE/'blender_sculpt_bridge.py','--','--blend',skin,
             '--output-blend',final,'--output-glb',glb,*extra)
    if not final.exists() or not glb.exists():raise RuntimeError('CPU scene/GLB not generated')
    if a.mocap_video or a.mocap_landmarks:
        motion_blend=output/'monster_cpu_mocap.blend'
        motion_glb=output/'monster_cpu_mocap.glb'
        command=[sys.executable,BASE/'open_mocap_cpu_worker.py',
                 '--blender',blender,'--blend',final,'--output-blend',motion_blend,
                 '--output-glb',motion_glb,'--clip',a.mocap_clip]
        if a.mocap_video:command+=['--video',a.mocap_video]
        else:command+=['--landmarks',a.mocap_landmarks]
        if a.mocap_side_video:command+=['--side-video',a.mocap_side_video]
        if a.mocap_bone_map:command+=['--bone-map',a.mocap_bone_map]
        if a.mocap_mirror:command+=['--mirror']
        call(*command)
        final,glb=motion_blend,motion_glb
    if a.xatlas_uv:
        atlas_blend=output/'monster_cpu_xatlas.blend'
        atlas_glb=output/'monster_cpu_xatlas.glb'
        cmd=[blender,'--background','--factory-startup','--python-exit-code','3',
             '--python',BASE/'xatlas_blender_bridge.py','--',
             '--blend',final,'--source-glb',glb,
             '--output-blend',atlas_blend,'--output-glb',atlas_glb,
             '--python-bin',a.xatlas_python]
        if a.xatlas_allow_noop:cmd+=['--allow-noop']
        call(*cmd)
        final,glb=atlas_blend,atlas_glb
    if a.pbr_cpu:
        pbr_blend=output/'monster_cpu_pbr.blend'
        pbr_glb=output/'monster_cpu_pbr.glb'
        if pbr_blend.exists() or pbr_glb.exists():p.error('PBR outputs already exist; new --output-dir needed')
        call(blender,'--background','--factory-startup','--python-exit-code','3',
             '--python',BASE/'pillow_pbr_blender.py','--',
             '--blend',final,'--source-glb',glb,
             '--output-blend',pbr_blend,'--output-glb',pbr_glb,
             '--texture-dir',output/'monster_cpu_pbr_textures',
             '--python-bin',a.pbr_python,'--size',a.pbr_size,'--wetness',a.pbr_wetness)
        final,glb=pbr_blend,pbr_glb
    def validate_glb(asset):
        command=[sys.executable,BASE/'gltf_validator_worker.py','--input',asset]
        if a.gltf_validator_package:command+=['--package-dir',a.gltf_validator_package]
        if a.gltf_validator_node:command+=['--node',a.gltf_validator_node]
        if a.gltf_validate_strict_warnings:command+=['--strict-warnings']
        call(*command)
    if a.trimesh_audit:
        # Inspect the final uncompressed GLB after UV/PBR, before compressors.
        guard=[a.trimesh_python,BASE/'trimesh_cpu_guard.py','--input',glb]
        if a.trimesh_strict:guard.append('--strict')
        call(*guard)
    if a.gltf_validate:validate_glb(glb)
    if a.gltf_optimize:
        final_glb=output/('monster_cpu_meshopt.glb' if a.gltf_mode=='meshopt' else 'monster_cpu_safe.glb')
        if final_glb.exists():p.error('Final optimized GLB already exists; choose new --output-dir')
        installed=BASE.parent/'vendor'/'gltf-transform-node'/'node_modules'/'.bin'/(
            'gltf-transform.cmd' if sys.platform.startswith('win') else 'gltf-transform')
        cmd=[sys.executable,BASE/'gltf_transform_worker.py','--input',glb,
             '--output',final_glb,'--mode',a.gltf_mode]
        cli=a.gltf_transform_bin or (str(installed) if installed.is_file() else '')
        if cli:cmd+=['--cli',cli]
        call(*cmd)
        glb=final_glb
        if a.gltf_validate:validate_glb(glb)
    if a.meshoptimizer:
        destination=output/('monster_cpu_gltfpack_compressed.glb' if a.meshoptimizer_mode=='compressed' else 'monster_cpu_gltfpack_safe.glb')
        if destination.exists():p.error('gltfpack output exists; use a different --output-dir')
        command=[sys.executable,BASE/'meshoptimizer_cpu_worker.py',
                 '--input',glb,'--output',destination,'--mode',a.meshoptimizer_mode,
                 '--validate-khronos']
        if a.gltfpack_bin:command+=['--gltfpack-bin',a.gltfpack_bin]
        if a.gltf_validator_package:command+=['--validator-package',a.gltf_validator_package]
        if a.gltf_validator_node:command+=['--validator-node',a.gltf_validator_node]
        call(*command)
        glb=destination
    if not a.no_sprite_stacking:
        sprite_dir=output/'monster_sprite_stacking'
        cmd=[sys.executable,BASE/'build_sprite_stacking.py',
             '--input-blend',final,'--blender',blender,'--output',sprite_dir,
             '--clip',a.sprite_clip,'--frames',a.sprite_frames,
             '--xy-size',a.sprite_xy_size,'--z-slices',a.sprite_z_slices]
        if a.sprite_allow_open:cmd.append('--allow-open')
        call(*cmd)
        print('PRIMARY sprite stack:',sprite_dir/'stack'/'clip.json')
    print('CPU Blender scene:',final)
    print('CPU rigged GLB:',glb)

if __name__=='__main__':main()
