# Composable source-authentic sprite-stack scenes

Usage:

```bash
python skills/sprite-stacking-priority/scripts/stack_scene_to_html.py original_static_scene.glb --out out/volume-scene
python skills/sprite-stacking-priority/scripts/stack_scene_to_html.py original_static_scene.glb --out out/volume-scene --assets-only
python skills/sprite-stacking-priority/scripts/stack_scene_to_html.py original_Unity_project --out out/volume-world --unity /path/to/trusted/Unity
```

The original engine gameplay (`godot_to_web.py`, `unity_to_web.py`) is **never** replaced by this visual conversion. `stack_scene_to_html.py` composes the pre-existing `stack_from_glb.py` and `stack_to_html.py`, not a new fabricated art generator. Each source GLB node is sliced separately with the original world transform baked into an independent derivative mesh; source GLB remains unchanged. Subsequent game movement must transform each **whole** stack around its authored hinge/pivot, not shear or stretch layers, and keep original collider state under Godot/Unity/Rapier as applicable. The generated viewer itself does not implement that game-state binding.

Input expectations: GLB2 self-contained PBR/UV0 or original vertex/face-color source; no unknown external texture URIs. Skinned or animated GLBs cannot safely be frozen — keep original GLB or provide independent complete approved volume pose stacks. Transparent/refractive materials, volumetric fog, wet glass, weather and native postFX cannot be automatically preserved in binary occupancy. Source metadata includes SHA256, original scene node name and original 4×4 transform. No extrapolated invisible sides from a painted photograph, no repeated decorative patterns or invented colors.

GPU limits: 32 independent texture volumes per HTML scene, original existing 128 MiB RGBA payload budget, plus actual device-specific `MAX_3D_TEXTURE_SIZE` enforcement. For more source objects author a scene/area split and keep original engine rendering for unsupported nodes. Do not silently discard any source node to meet a target stack percentage.

The upgraded runtime defaults to original-color output and offers optional relief shading. All complete-pose volume animations start paused; they play only on an explicit button press. No automatic player attacks. The original engine is required to synchronize game world, characters and collisions for an actual playable adaptation. Visual comparison via Playwright/Pixelmatch is required before substituting stacked derivatives for approved original GLB rendering.
