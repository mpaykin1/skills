# BLOCKWILD v15 · coherent CPU volume-relief + artistic comparison

- Model authority: `build_sunlit_volume_sprites.py` + `build_blockwild_v14_actors.py` original authored voxel source. Not recovered Unity meshes. Actor: 4 stable character variants × 8 directions × 5 poses = 160 original 3D-derived animation frames.
- Build-time renderer: `volumetric_relight.py` uses SciPy Gaussian fields + Numba parallel CPU ray casting + Pillow alpha compositing and source-material detail preservation. Licenses: Numba BSD-2-Clause, SciPy BSD-3-Clause, NumPy BSD-3-Clause, Pillow HPND. No binaries or model weights vendored. Does not claim to execute Blender.
- HTML: original 14,505 source chunks and climate/terrain bytes unchanged; all world archives stay embedded. Volumetric source volumes bake into RGBA sprites. Art mode runs via existing Canvas2D render loop; native WebGL2 renderer not replaced. 3D butterfly variants, true foliage props, world-space ray lighting and foreground sculpted stone parapet.
- Our skills: **Hero Animator** preserves 8 rotations and pose identity; **Meta Game Fusion** provides the horizontal true-volume sprite canon; **Voxel Atmosphere Engine** supplies lighting guidance; **Game Style Forge** provides compositing and palette; **Blockwild Visual Benchmark** uses actual reference screenshot Lab cumulative-histogram W1; **Godot to HTML** can later recover actual Unity assets; **Skill Nexus** maintains stable routes. Do not assert integrations were exercised when only skill instructions were consulted.
- Measured reference proxy: `LAB W1 = weighted mean of 1D CDF differences on 64-bin Lab channels`, weights (0.48,0.31,0.21); user-supplied portrait reference cropped to same ratio. `decrease% = (v14-v15)/v14 * 100`. This is **palette proximity**, not universal graphic beauty or original Unity fidelity.
- Quality gate: Playwright Chromium system executable must load 178 assets in both 390×844 and 844×390 with no JS errors and animation frames changing. In this environment only extracted art probe loaded; navigating full 49-MB `file://` returns `ERR_BLOCKED_BY_ADMINISTRATOR`, so its native runtime remains unverified.
- No automatic independent skill/plugin updates; optional future updates through Plugin Creator with explicit version and repo change.

## Commands

```sh
python scripts/build_v15_relief_atlas.py --v14-html /source/v14.html --out-assets /tmp/v15_assets.json
python scripts/assemble_v15.py --base-html /source/v14.html --assets-json /tmp/v15_assets.json --out-html /output/BLOCKWILD_v15.html
```

All original playable movement mechanics remain the v14 mechanisms. No invented Unity PBR rig, AI, or physics recovery. Verify actual game before shipping as fully validated playable Unity equivalence.
