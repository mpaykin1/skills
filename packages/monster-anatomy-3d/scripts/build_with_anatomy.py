#!/usr/bin/env python3
"""Blender pipeline: MyoGeneratorRemix + Z-Anatomy + MPFB2 + Blender + TRELLIS.2.

All upstream components are pinned and downloaded by their dedicated helpers.
The final GLB remains the ORIGINAL creature blockout; the MPFB donor mesh and
anatomy markers live in the final editable .blend only. Converting the blockout
to detailed finished muscles requires art-directed MyoGeneratorRemix operations.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / 'scripts'

def run(command):
    print('+', ' '.join(map(str,command)), flush=True)
    subprocess.run([str(x) for x in command], check=True)

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--blender', default='blender')
    p.add_argument('--full-external-cpu', action='store_true', help='Use original optional MPFB/Z-Anatomy/Myo/Rigger CPU integrations; never uses CUDA')
    p.add_argument('--cpu-input-blend', default='', help='Use existing MONSTER_RIG .blend instead of procedural starter')
    p.add_argument('--cpu-skin-method', choices=('auto','proximity'), default='auto')
    p.add_argument('--scipy-skin-smooth',action='store_true',help='CPU SciPy mesh-graph smoothing of newly generated bone weights in the default CPU pipeline')
    p.add_argument('--scipy-python',default=sys.executable,help='External CPU Python with scipy==1.17.0 and numpy')
    p.add_argument('--scipy-iterations',type=int,default=3)
    p.add_argument('--scipy-strength',type=float,default=0.35)
    p.add_argument('--cpu-skip-morphs', action='store_true')
    p.add_argument('--pymeshlab-audit',action='store_true',help='CPU-only static geometry inspection via PyMeshLab')
    p.add_argument('--pymeshlab-clean-static',action='store_true',help='Clean eligible static meshes before CPU skinning')
    p.add_argument('--pymeshlab-python',default=sys.executable,help='External Python with PyMeshLab installed')
    p.add_argument('--manifold-cpu',action='store_true',help='CPU Manifold3D Boolean sculpt reference, non-destructive, before skinning')
    p.add_argument('--manifold-objects',default='',help='Comma-separated static triangle mesh objects, or auto detect MUSCLE_/BODY_/SHELL_')
    p.add_argument('--manifold-python',default=sys.executable,help='External Python with manifold3d==3.5.5 + trimesh + numpy')
    p.add_argument('--xatlas-uv',action='store_true',help='CPU-only UV unwrap after rigging/retopo, without changing vertex topology')
    p.add_argument('--xatlas-python',default=sys.executable,help='External Python with xatlas==0.0.11 + numpy')
    p.add_argument('--xatlas-allow-noop',action='store_true',help='Keep already UV-mapped character unchanged')
    p.add_argument('--pbr-cpu',action='store_true',help='Pillow 12.3.0 PBR texture maps after xatlas')
    p.add_argument('--pbr-size',type=int,choices=(128,256,512,1024,2048),default=512)
    p.add_argument('--pbr-wetness',type=float,default=0.35)
    p.add_argument('--pbr-python',default=sys.executable)
    p.add_argument('--gltf-optimize',action='store_true',help='CPU-only glTF-Transform safe post-export dedup; preserves source GLB')
    p.add_argument('--gltf-mode',choices=('safe','meshopt'),default='safe',help='meshopt needs extra Three.js decoder')
    p.add_argument('--gltf-transform-bin',default='',help='Official installed gltf-transform CLI path')
    p.add_argument('--trimesh-audit',action='store_true',help='Optional Trimesh CPU mesh topology audit on final uncompressed GLB')
    p.add_argument('--trimesh-strict',action='store_true',help='Fail on non-manifold edges or inconsistent winding (open boundaries remain advisory)')
    p.add_argument('--trimesh-python',default=sys.executable,help='CPU Python with trimesh==4.11.1 and numpy')
    p.add_argument('--meshoptimizer',action='store_true',help='Official gltfpack v1.3 CPU optimizer after glTF-Transform; Khronos gate required')
    p.add_argument('--meshoptimizer-mode',choices=('safe','compressed'),default='safe',help='compressed needs MeshoptDecoder in Three.js')
    p.add_argument('--gltfpack-bin',default='',help='Exact official gltfpack executable (or vendor/gltfpack-v1.3)')
    p.add_argument('--gltf-validate',action='store_true',help='Run actual Khronos glTF-Validator on CPU after export')
    p.add_argument('--gltf-validate-strict-warnings',action='store_true',help='Fail if Khronos emits warnings')
    p.add_argument('--gltf-validator-package',default='',help='Official installed gltf-validator npm directory')
    p.add_argument('--gltf-validator-node',default='',help='Node.js executable path')
    p.add_argument('--mocap-video',default='',help='CPU-only Open Mocap motion from MP4/MOV video')
    p.add_argument('--mocap-side-video',default='',help='Optional synchronized side-view video')
    p.add_argument('--mocap-landmarks',default='',help='Previously captured Open Mocap 40-point JSON')
    p.add_argument('--mocap-clip',default='MOCAP_WALK',help='New unique NLA action')
    p.add_argument('--mocap-bone-map',default='',help='Explicit MONSTER_RIG bone to landmark pair map')
    p.add_argument('--mocap-mirror',action='store_true')
    p.add_argument('--sprite-source',default='',help='CPU-only: directly voxelize an existing real OBJ/GLB without Blender')
    p.add_argument('--no-sprite-stacking',action='store_true',help='Legacy Blender-only output; sprite stacking ON by default')
    p.add_argument('--sprite-clip',default='ALL')
    p.add_argument('--sprite-frames',type=int,default=12)
    p.add_argument('--sprite-xy-size',type=int,choices=(64,96,128,192,256),default=96)
    p.add_argument('--sprite-z-slices',type=int,choices=(32,48,64,96,128),default=64)
    p.add_argument('--sprite-allow-open',action='store_true')
    p.add_argument('--output-dir', default='build/monster-anatomy')
    p.add_argument('--offline', action='store_true', help='Only use existing source files; do not download')
    p.add_argument('--skip-mpfb', action='store_true', help='Produce the original two-tool scene without MPFB')
    p.add_argument('--install-blender',action='store_true',help='Download and verify official Blender 4.5.16 binary')
    p.add_argument('--skip-blender-detail',action='store_true',help='Only create the v0.3 rig/blockout references')
    p.add_argument('--workbench-copies',action='store_true',help='Add hidden high-res editable sculpt copies')
    p.add_argument('--trellis-glb',default='',help='real unrigged TRELLIS.2 output GLB to import into anatomy scene')
    p.add_argument('--trellis-input',default='',help='optional reference drawing for actual CUDA inference')
    p.add_argument('--trellis-python',default=sys.executable,help='Python executable in installed TRELLIS.2 CUDA environment')
    p.add_argument('--trellis-repo',default='',help='official TRELLIS.2 repository checkout; defaults to vendor/TRELLIS.2')
    p.add_argument('--trellis-pipeline',choices=['512','1024','1024_cascade','1536_cascade'],default='512')
    p.add_argument('--trellis-rotate-z',type=float,default=0.0,help='orientation correction for static TRELLIS.2 reference')
    p.add_argument('--instant-retopo',action='store_true',help='Run official Instant Meshes quad-retopology stage on exported monster meshes')
    p.add_argument('--instant-bin',default='',help='Exact path to compiled Instant Meshes CLI; automatically build pinned source if unset')
    p.add_argument('--instant-ratio',type=float,default=.4,help='target polygon count divided by original')
    p.add_argument('--instant-min-faces',type=int,default=220,help='skip tiny meshes without safe reduction')
    p.add_argument('--pose-shape-keys',action='store_true',help='prepare Blender Studio pose-key sculpt workbench on the existing monster mesh')
    p.add_argument('--pose-shape-keys-zip',default='',help='offline official Pose Shape Keys 1.0.0 release zip')
    p.add_argument('--rigger-controls',action='store_true',help='create preserved Rigger IK/FK controller rig in a new .blend')
    p.add_argument('--rigger-motion',default='',help='retarget a real animated GLB/FBX into the same monster, output animated GLB')
    p.add_argument('--rigger-dir',default='',help='pinned official Rigger checkout (defaults to vendor/Rigger)')
    p.add_argument('--rigger-motion-rig',default='',help='source armature name if motion has multiple rigs')
    p.add_argument('--rigger-motion-action',default='',help='specific motion clip/action')
    p.add_argument('--rigger-clip',default='RIGGER_NEW_ACTION',help='unique new motion clip name')
    p.add_argument('--rigger-bone-map',default='',help='source bone -> monster bone explicit JSON')
    p.add_argument('--rigger-in-place',action='store_true',help='drop source root travel for a looping motion')
    args = p.parse_args()
    if args.sprite_source:
        if args.full_external_cpu or args.cpu_input_blend or args.no_sprite_stacking:
            p.error('--sprite-source is an independent source-only path; no Blender or legacy mode')
        command=[sys.executable,SCRIPTS/'build_sprite_stacking.py','--input-glb',args.sprite_source,
                 '--output',str(Path(args.output_dir).resolve()/'monster_sprite_stacking'),
                 '--clip',args.sprite_clip,'--fps','12',
                 '--xy-size',str(args.sprite_xy_size),'--z-slices',str(args.sprite_z_slices)]
        if args.sprite_allow_open:command.append('--allow-open')
        run(command)
        return
    if args.meshoptimizer and args.gltf_optimize and args.gltf_mode!='safe':p.error('glTF-Transform meshopt output cannot be fed into gltfpack; use --gltf-mode safe')
    if args.gltf_mode!='safe' and not args.gltf_optimize:p.error('--gltf-mode requires --gltf-optimize')
    if args.gltf_validate_strict_warnings and not args.gltf_validate:p.error('--gltf-validate-strict-warnings needs --gltf-validate')
    if args.trimesh_strict and not args.trimesh_audit:p.error('--trimesh-strict requires --trimesh-audit')
    if args.manifold_objects and not args.manifold_cpu:p.error('--manifold-objects requires --manifold-cpu')
    if args.mocap_video and args.mocap_landmarks:p.error('Choose video OR landmarks, never both')
    if args.mocap_side_video and not args.mocap_video:p.error('Side video requires a front video')
    if not 1<=args.scipy_iterations<=8 or not 0<=args.scipy_strength<=0.65:p.error('SciPy iterations 1..8, strength 0..0.65')
    if args.scipy_skin_smooth and args.full_external_cpu:p.error('SciPy new-weight smoothing runs only in the default CPU skinning stage; omit --full-external-cpu')
    # CPU-only is the mandatory default. TRELLIS.2 neural inference is strictly
    # unavailable without NVIDIA CUDA; SkinTokens is never called from this skill.
    if args.trellis_input:
        p.error('TRELLIS.2 requires NVIDIA CUDA; CPU-only mode forbids its inference. Use existing Blender geometry instead.')
    if not args.full_external_cpu:
        incompatible=(args.trellis_glb or args.instant_retopo or args.pose_shape_keys
                      or args.rigger_controls or args.rigger_motion or args.rigger_bone_map
                      or args.skip_mpfb or args.pose_shape_keys_zip)
        if incompatible:
            p.error('External CPU add-ons require --full-external-cpu with local CPU-compatible tools. Plain CPU build has no downloads.')
        cmd=[sys.executable,SCRIPTS/'build_cpu_only.py','--blender',args.blender,
             '--output-dir',args.output_dir,'--skin-method',args.cpu_skin_method]
        if args.cpu_input_blend:cmd+=['--input-blend',args.cpu_input_blend]
        if args.no_sprite_stacking:cmd+=['--no-sprite-stacking']
        cmd+=['--sprite-clip',args.sprite_clip,'--sprite-frames',str(args.sprite_frames),
              '--sprite-xy-size',str(args.sprite_xy_size),'--sprite-z-slices',str(args.sprite_z_slices)]
        if args.sprite_allow_open:cmd+=['--sprite-allow-open']
        if args.scipy_skin_smooth:cmd+=['--scipy-skin-smooth','--scipy-python',args.scipy_python,'--scipy-iterations',str(args.scipy_iterations),'--scipy-strength',str(args.scipy_strength)]
        if args.manifold_cpu:cmd+=['--manifold-cpu','--manifold-python',args.manifold_python]
        if args.manifold_objects:cmd+=['--manifold-objects',args.manifold_objects]
        if args.pbr_cpu:cmd+=['--pbr-cpu','--pbr-python',args.pbr_python,'--pbr-size',str(args.pbr_size),'--pbr-wetness',str(args.pbr_wetness)]
        if args.xatlas_uv:cmd+=['--xatlas-uv','--xatlas-python',args.xatlas_python]
        if args.xatlas_allow_noop:cmd+=['--xatlas-allow-noop']
        if args.trimesh_audit:cmd+=['--trimesh-audit','--trimesh-python',args.trimesh_python]
        if args.trimesh_strict:cmd+=['--trimesh-strict']
        if args.meshoptimizer:cmd+=['--meshoptimizer','--meshoptimizer-mode',args.meshoptimizer_mode]
        if args.gltfpack_bin:cmd+=['--gltfpack-bin',args.gltfpack_bin]
        if args.gltf_optimize:cmd+=['--gltf-optimize','--gltf-mode',args.gltf_mode]
        if args.gltf_transform_bin:cmd+=['--gltf-transform-bin',args.gltf_transform_bin]
        if args.gltf_validate:cmd+=['--gltf-validate']
        if args.gltf_validate_strict_warnings:cmd+=['--gltf-validate-strict-warnings']
        if args.gltf_validator_package:cmd+=['--gltf-validator-package',args.gltf_validator_package]
        if args.gltf_validator_node:cmd+=['--gltf-validator-node',args.gltf_validator_node]
        if args.pymeshlab_audit:cmd+=['--pymeshlab-audit']
        if args.pymeshlab_clean_static:cmd+=['--pymeshlab-clean-static']
        if args.pymeshlab_audit or args.pymeshlab_clean_static:cmd+=['--pymeshlab-python',args.pymeshlab_python]
        if args.cpu_skip_morphs or args.skip_blender_detail:cmd+=['--skip-morphs']
        if args.workbench_copies:cmd+=['--workbench-copies']
        if args.mocap_video:cmd+=['--mocap-video',args.mocap_video]
        if args.mocap_landmarks:cmd+=['--mocap-landmarks',args.mocap_landmarks]
        if args.mocap_side_video:cmd+=['--mocap-side-video',args.mocap_side_video]
        if args.mocap_bone_map:cmd+=['--mocap-bone-map',args.mocap_bone_map]
        if args.mocap_mirror:cmd+=['--mocap-mirror']
        if args.mocap_video or args.mocap_landmarks:cmd+=['--mocap-clip',args.mocap_clip]
        if args.install_blender:
            if args.offline:p.error('--install-blender needs internet')
            run([sys.executable,SCRIPTS/'download_blender.py','--dest',ROOT/'vendor/Blender'])
            from download_blender import host_platform,VERSION
            suffix='.exe' if host_platform().startswith('windows') else ''
            cmd[cmd.index(args.blender)]=str(ROOT/'vendor/Blender'/('blender-'+VERSION+'-'+host_platform())/('blender'+suffix))
        run(cmd)
        return
    if args.cpu_input_blend:
        p.error('--cpu-input-blend is supported in the default CPU path; omit --full-external-cpu')
    if args.pymeshlab_audit or args.pymeshlab_clean_static:
        p.error('PyMeshLab repair runs in the default CPU path; omit --full-external-cpu')
    if args.pbr_cpu and not args.xatlas_uv:p.error('--pbr-cpu requires --xatlas-uv')
    if not 0<=args.pbr_wetness<=1:p.error('--pbr-wetness must be 0..1')
    if args.trimesh_strict and not args.trimesh_audit:p.error('--trimesh-strict requires --trimesh-audit')
    if args.trellis_glb and args.trellis_input:
        p.error('Specify --trellis-glb OR --trellis-input, never both')
    if args.pose_shape_keys_zip and not args.pose_shape_keys:
        p.error('--pose-shape-keys-zip requires --pose-shape-keys')
    if args.rigger_controls and args.rigger_motion:
        p.error('Select either --rigger-controls or --rigger-motion; they are separate, non-destructive stages')
    if args.rigger_bone_map and not args.rigger_motion:
        p.error('--rigger-bone-map requires --rigger-motion')
    if args.install_blender:
        if args.offline: p.error('--install-blender requires network; use --blender with an existing installation')
        run([sys.executable,SCRIPTS/'download_blender.py','--dest',ROOT/'vendor/Blender'])
        from download_blender import host_platform,VERSION
        suffix='.exe' if host_platform().startswith('windows') else ''
        args.blender=str(ROOT/'vendor/Blender'/('blender-'+VERSION+'-'+host_platform())/('blender'+suffix))
    out = Path(args.output_dir).resolve()
    out.mkdir(parents=True,exist_ok=True)
    trellis_glb=None
    trellis_repo=Path(args.trellis_repo).expanduser().resolve() if args.trellis_repo else ROOT/'vendor/TRELLIS.2'
    if args.trellis_glb:
        trellis_glb=Path(args.trellis_glb).expanduser().resolve()
        if not trellis_glb.is_file():p.error('TRELLIS.2 GLB not found: '+str(trellis_glb))
    elif args.trellis_input:
        if not Path(args.trellis_input).is_file():p.error('Image not found: '+args.trellis_input)
        if not args.offline:
            run([sys.executable,SCRIPTS/'download_trellis2.py','--dest',trellis_repo])
        else:
            run([sys.executable,SCRIPTS/'download_trellis2.py','--verify','--dest',trellis_repo])
        trellis_glb=out/'trellis_draft.glb'
        run([args.trellis_python,SCRIPTS/'trellis2_generate.py','--input',args.trellis_input,
             '--output',trellis_glb,'--repo',trellis_repo,'--pipeline',args.trellis_pipeline])
    atlas = ROOT/'vendor/Z-Anatomy/Z-Anatomy.zip' 
    if not args.offline:
        run([sys.executable,SCRIPTS/'download_myogenerator.py','--dest',ROOT/'vendor'])
        run([sys.executable,SCRIPTS/'download_z_anatomy.py','--dest',ROOT/'vendor/Z-Anatomy'])
    if not args.skip_mpfb:
        run([sys.executable,SCRIPTS/'setup_mpfb.py','--blender',args.blender,
             '--source',ROOT/'vendor/MPFB2','--install'] + (['--offline'] if args.offline else []))
    base=out/'monster_base.blend'
    glb=out/'monster_base.glb'
    run([args.blender,'--background','--python',SCRIPTS/'build_monster.py','--',
         '--blend',base,'--output',glb])
    guided = out/'monster_with_anatomy_guides.blend'
    cmd=[args.blender,'--background','--python',SCRIPTS/'z_anatomy_bridge.py','--',
         '--blend',base,'--output-blend',guided,
         '--output-csv',out/'muscle_anchors.csv','--output-index',out/'atlas_matches.json']
    if atlas.exists(): cmd += ['--z-zip',atlas]
    run(cmd)
    if args.skip_mpfb:
        final_scene=guided
    else:
        final_scene=out/'monster_three_way_anatomy.blend'
        run([args.blender,'--background','--python',SCRIPTS/'mpfb_anatomy_bridge.py','--',
             '--blend',guided,'--output-blend',final_scene,
             '--output-json',out/'mpfb_bone_correspondence.json',
             '--output-csv',out/'mpfb_anchor_correspondence.csv'])
    if trellis_glb:
        aligned=out/'monster_with_trellis_surface.blend'
        run([args.blender,'--background','--python',SCRIPTS/'trellis_surface_bridge.py','--',
             '--blend',final_scene,'--trellis-glb',trellis_glb,
             '--output-blend',aligned,'--output-json',out/'trellis_surface_anchors.json',
             '--rotate-z',args.trellis_rotate_z])
        final_scene=aligned
    if args.manifold_cpu:
        sculpt_guide=out/'monster_manifold_sculpt_guide.blend'
        cmd=[args.blender,'--background','--factory-startup','--python-exit-code','3',
             '--python',SCRIPTS/'manifold3d_blender_bridge.py','--',
             '--blend',final_scene,'--output-blend',sculpt_guide,'--python-bin',args.manifold_python]
        if args.manifold_objects:cmd+=['--objects',args.manifold_objects]
        run(cmd)
        final_scene=sculpt_guide
    if not args.skip_blender_detail:
        detailed=out/'monster_blender_sculpt_ready.blend'
        animated=out/'monster_muscle_deform.glb'
        extra=['--workbench-copies'] if args.workbench_copies else []
        run([args.blender,'--background','--python',SCRIPTS/'blender_sculpt_bridge.py','--',
             '--blend',final_scene,'--output-blend',detailed,'--output-glb',animated]+extra)
        final_scene=detailed
        glb=animated
    if args.instant_retopo:
        binary=args.instant_bin
        if not binary:
            build=ROOT/'vendor/instant-meshes-build'
            binary=str(build/('Instant Meshes.exe' if sys.platform.startswith('win') else 'Instant Meshes'))
            if not Path(binary).is_file():
                if args.offline: p.error('Instant Meshes source/binary absent; provide --instant-bin in offline mode')
                run([sys.executable,SCRIPTS/'download_instant_meshes.py',
                     '--dest',ROOT/'vendor/instant-meshes',
                     '--build','--build-dir',build])
        retopo_scene=out/'monster_instant_retopo.blend'
        retopo_glb=out/'monster_instant_retopo.glb'
        run([sys.executable,SCRIPTS/'instant_meshes_worker.py',
             '--blender',args.blender,'--instant-bin',binary,'--blend',final_scene,
             '--output-blend',retopo_scene,'--output-glb',retopo_glb,
             '--ratio',args.instant_ratio,'--min-faces',args.instant_min_faces])
        final_scene=retopo_scene
        glb=retopo_glb
    if args.rigger_controls or args.rigger_motion:
        upstream=Path(args.rigger_dir).expanduser().resolve() if args.rigger_dir else ROOT/'vendor/Rigger'
        dl=[sys.executable,SCRIPTS/'download_rigger.py','--dest',upstream]
        if args.offline:dl.append('--verify')
        run(dl)
        cmd=[sys.executable,SCRIPTS/'rigger_monster_worker.py','--blender',args.blender,
             '--rigger-dir',upstream,'--blend',final_scene]
        if args.rigger_controls:
            out_ctrl=out/'monster_Rigger_IKFK_controls.blend'
            run(cmd+['--mode','controls','--output-blend',out_ctrl])
            final_scene=out_ctrl
        else:
            out_animated=out/'monster_Rigger_retarget.glb'
            extra=['--mode','retarget','--motion',args.rigger_motion,'--output-glb',out_animated,
                   '--clip',args.rigger_clip]
            if args.rigger_motion_rig:extra+=['--motion-rig',args.rigger_motion_rig]
            if args.rigger_motion_action:extra+=['--motion-action',args.rigger_motion_action]
            if args.rigger_bone_map:extra+=['--bone-map',args.rigger_bone_map]
            if args.rigger_in_place:extra+=['--in-place']
            run(cmd+extra)
            glb=out_animated
    if args.pose_shape_keys:
        if args.skip_blender_detail:
            p.error('--pose-shape-keys requires the Blender detail stage with ANATOMY_FLEX morphs')
        ext=ROOT/'vendor/pose-shape-keys'
        fetch_cmd=[sys.executable,SCRIPTS/'download_pose_shape_keys.py','--dest',ext]
        if args.pose_shape_keys_zip:fetch_cmd+=['--zip',args.pose_shape_keys_zip]
        elif args.offline:fetch_cmd+=['--verify']
        run(fetch_cmd)
        authoring=out/'monster_pose_key_authoring.blend'
        run([args.blender,'--background','--python',SCRIPTS/'pose_shape_keys_monster.py','--',
             '--blend',final_scene,'--output-blend',authoring,'--addon-dir',ext,'--track','ATTACK'])
        final_scene=authoring
        # Sculpting/pushing the stored mesh into ANATOMY_FLEX is an intentional
        # artist step; the automatically generated GLB remains as before.
    if args.mocap_video or args.mocap_landmarks:
        # CPU-only; does not invoke SkinTokens or TRELLIS.2.
        worker=[sys.executable,SCRIPTS/'open_mocap_cpu_worker.py',
                '--blender',args.blender,'--blend',final_scene,
                '--output-blend',out/'monster_open_mocap.blend',
                '--output-glb',out/'monster_open_mocap.glb',
                '--clip',args.mocap_clip]
        if args.mocap_video:worker+=['--video',args.mocap_video]
        else:worker+=['--landmarks',args.mocap_landmarks]
        if args.mocap_side_video:worker+=['--side-video',args.mocap_side_video]
        if args.mocap_bone_map:worker+=['--bone-map',args.mocap_bone_map]
        if args.mocap_mirror:worker+=['--mirror']
        run(worker)
        final_scene=out/'monster_open_mocap.blend'
        glb=out/'monster_open_mocap.glb'
    if args.xatlas_uv:
        atlas_blend=out/'monster_xatlas_uv.blend'
        atlas_glb=out/'monster_xatlas_uv.glb'
        cmd=[args.blender,'--background','--factory-startup','--python-exit-code','3',
             '--python',SCRIPTS/'xatlas_blender_bridge.py','--',
             '--blend',final_scene,'--source-glb',glb,
             '--output-blend',atlas_blend,'--output-glb',atlas_glb,
             '--python-bin',args.xatlas_python]
        if args.xatlas_allow_noop:cmd+=['--allow-noop']
        run(cmd)
        final_scene,glb=atlas_blend,atlas_glb
    if args.pbr_cpu:
        pbr_scene=out/'monster_pillow_pbr.blend'
        pbr_glb=out/'monster_pillow_pbr.glb'
        run([args.blender,'--background','--factory-startup','--python-exit-code','3',
             '--python',SCRIPTS/'pillow_pbr_blender.py','--',
             '--blend',final_scene,'--source-glb',glb,
             '--output-blend',pbr_scene,'--output-glb',pbr_glb,
             '--texture-dir',out/'monster_pillow_pbr_textures',
             '--python-bin',args.pbr_python,'--size',args.pbr_size,'--wetness',args.pbr_wetness])
        final_scene,glb=pbr_scene,pbr_glb
    def validate_glb(asset):
        command=[sys.executable,SCRIPTS/'gltf_validator_worker.py','--input',asset]
        if args.gltf_validator_package:command+=['--package-dir',args.gltf_validator_package]
        if args.gltf_validator_node:command+=['--node',args.gltf_validator_node]
        if args.gltf_validate_strict_warnings:command+=['--strict-warnings']
        run(command)
    if args.trimesh_audit:
        guard=[args.trimesh_python,SCRIPTS/'trimesh_cpu_guard.py','--input',glb]
        if args.trimesh_strict:guard.append('--strict')
        run(guard)
    if args.gltf_validate:validate_glb(glb)
    if args.gltf_optimize:
        dest=out/('monster_final_meshopt.glb' if args.gltf_mode=='meshopt' else 'monster_final_safe.glb')
        installed=ROOT/'vendor'/'gltf-transform-node'/'node_modules'/'.bin'/(
            'gltf-transform.cmd' if sys.platform.startswith('win') else 'gltf-transform')
        command=[sys.executable,SCRIPTS/'gltf_transform_worker.py','--input',glb,'--output',dest,'--mode',args.gltf_mode]
        binary=args.gltf_transform_bin or (str(installed) if installed.is_file() else '')
        if binary:command+=['--cli',binary]
        run(command)
        glb=dest
        if args.gltf_validate:validate_glb(glb)
    if args.meshoptimizer:
        destination=out/('monster_gltfpack_compressed.glb' if args.meshoptimizer_mode=='compressed' else 'monster_gltfpack_safe.glb')
        if destination.exists():p.error('gltfpack output exists; use a different --output-dir')
        command=[sys.executable,SCRIPTS/'meshoptimizer_cpu_worker.py',
                 '--input',glb,'--output',destination,'--mode',args.meshoptimizer_mode,
                 '--validate-khronos']
        if args.gltfpack_bin:command+=['--gltfpack-bin',args.gltfpack_bin]
        if args.gltf_validator_package:command+=['--validator-package',args.gltf_validator_package]
        if args.gltf_validator_node:command+=['--validator-node',args.gltf_validator_node]
        run(command)
        glb=destination
    if not args.no_sprite_stacking:
        sprite_dir=out/'monster_sprite_stacking'
        command=[sys.executable,SCRIPTS/'build_sprite_stacking.py','--input-blend',final_scene,
                 '--blender',args.blender,'--output',sprite_dir,'--clip',args.sprite_clip,
                 '--frames',str(args.sprite_frames),'--xy-size',str(args.sprite_xy_size),
                 '--z-slices',str(args.sprite_z_slices)]
        if args.sprite_allow_open:command.append('--allow-open')
        run(command)
        print('PRIMARY sprite stack:',sprite_dir/'stack'/'clip.json')
    print('Editable anatomy scene:',final_scene)
    print('Game GLB:',glb)
    if trellis_glb:print('Static high-poly TRELLIS reference GLB:',trellis_glb)
    print('IMPORTANT: mesh-corrective flex is artistic animation, not a finite-element muscle simulation.')

if __name__=='__main__':main()
