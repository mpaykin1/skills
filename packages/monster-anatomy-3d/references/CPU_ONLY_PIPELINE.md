# CPU-only Monster Anatomy 3D: full compatibility contract

## Real CPU functions
- Blender 4.5 modelling, sculpt, skeleton, NLA animation and glTF/GLB export; physically renderable Eevee/Cycles on CPU where appropriate.
- Original `scripts/build_monster.py`: full original skin/animations without AI. No GPU.
- New `scripts/cpu_skinning_blender.py`: CPU bone-heat weights for only previously unweighted meshes, deterministic proximity fallback if heat is infeasible. Protect original skinned meshes; retain materials, UV, shape keys, armature, original action clips and topology. The four-influence limit applies to proximity fallback; Blender bone heat can assign more and glTF may prune at export, so inspect resulting weights before claiming 4 total.
- `scripts/blender_sculpt_bridge.py` for flex/stretch muscle morphs baked along animation clips (algorithmic artistic approximation, not physiology).
- CPU optional: MPFB2 (human anatomy reference only), Z-Anatomy (guide only, license review), MyoGeneratorRemix (artist-driven individual muscles), Instant Meshes (CPU retopology), Rigger (CPU IK/FK/motion retarget), Pose Shape Keys (manual corrective authoring).

## Explicit GPU disabled functions
- TRELLIS.2 image-to-3D inference (needs NVIDIA 24 GB VRAM); do not call. It is **not** an automatic CPU image-to-3D reconstruction.
- SkinTokens TokenRig neural rigging (needs NVIDIA 14 GB VRAM); do not call, even with `--use_skeleton`. Retain only provenance/source references. Its checkpoints are not downloaded.

## One-shot build

`python scripts/build_with_anatomy.py --blender blender --output-dir build/monster-cpu`

Creates editable `monster_cpu_animated.blend` and rigged `monster_cpu_animated.glb`. Blender binary must exist on CPU machine; if absent fail with a clear error. Default path never fetches any internet asset.

For a pre-existing monster .blend:

`python scripts/build_with_anatomy.py --blender blender --cpu-input-blend /path/monster.blend --cpu-skip-morphs`

The rig MUST be named `MONSTER_RIG`. Existing morphology and animations are not replaced; generated outputs are separate files. CPU weights are heuristics and skinning result must be visually reviewed for joints and limb silhouette before claiming game-ready quality. No character identity substitution or mesh global-squash effects.

## Scope

Even a many-core CPU cannot practically run the GPU-only large diffusion/transformer pipelines as written. CPU-only covers Blender geometry, skeletal animation, native skinning and source tools. For full photorealistic new geometry from a drawing, use artist-provided mesh/sculpt, not a false claim of TRELLIS model execution.


## Trimesh CPU topology inspection (v1.7.0)

After xatlas/Pillow PBR and before glTF-Transform/meshoptimizer, opt in to `--trimesh-audit`. The pinned independent `trimesh==4.11.1` installation uses only CPU and reads the final uncompressed GLB without modifying bones, skin weights, morphs, UVs or animation. Collapsed geometry is rejected; open boundaries are advisory; `--trimesh-strict` additionally rejects winding and nonmanifold edge errors. The existing Khronos Validator remains the final glTF format checker. See `references/TRIMESH_CPU_BRIDGE.md`.
