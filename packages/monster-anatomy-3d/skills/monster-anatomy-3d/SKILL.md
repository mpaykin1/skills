---
name: monster-anatomy-3d
description: "Create expressive sprite-stacked volumetric 3D horror monsters with CPU-generated RGBA cross-sections, all-view Three.js GLSL raymarch, real articulated anatomical source skeleton, muscles, animation poses, and retained GLB output. Use when a user supplies a drawing of a skeletal, muscular mutant or asks for anatomically sculpted creatures."
---

# Monster Anatomy 3D — hard rules

## V2.0 PRIMARY TECH: TRUE SPRITE STACKING (mandatory by default)

Read `references/SPRITE_STACKING_PRIMARY.md` before every creation or revision. The visible monster, muscles, outer skin and authored move states **must use true volumetric horizontal sprite stacking wherever possible**. The same 3D mesh and rig determine all rendered perspectives: +X right, +Y forward, +Z up, RGBA slices ordered bottom-to-top; user reference silhouettes and uneven physical anatomy remain unchanged. Do not use flat planes, billboard sprites, extruded 2D art, stand-in pixel blocks or unrelated rotation images. Never replace the existing hero during animation.

**Maximum sprite stacking means:** CPU bake all real MONSTER_RIG action poses into independently voxelized stacks (`scripts/export_sprite_poses_blender.py` + `scripts/sprite_stack_cpu.py`); produce transparent layers, atlas, 360 GIF, six views and `library.json`; render entirely through `runtime/sprite_stack_three.js` 3D GLSL volume raymarch with real 3D camera, depth test, nearest-surface original colors and controlled action playback. Keep Blender + MyoGeneratorRemix/Rigger/SciPy for non-visible bone motion, and `.glb` only as the authoring/proxy/collision source. Use Three.js/WebGL2 locally packaged with the game, not a screen-facing GIF.

Default `python scripts/build_with_anatomy.py --blender blender` builds the original rigged asset **and** sprite stacks for all available real body Actions. `python scripts/build_with_anatomy.py --sprite-source monster.glb` creates the stack and GIF directly on CPU without Blender. If the input is only an image, first author a plausible real 3D geometry source; DO NOT claim a photo automatically contains enough depth for genuine 360 slices. Fails closed on non-watertight inputs, unless thin shells explicitly approved. No GPU. Legacy `--no-sprite-stacking` is an explicit exception only. Do not claim Blender/Three browser proof without running them.


## CPU-ONLY DEFAULT — mandatory for this skill

**The owner has no GPU. All requested builds must run on CPU.** Never require NVIDIA, CUDA, PyTorch CUDA, Hugging Face checkpoints or remote GPU services. Never suggest/launch `scripts/trellis2_generate.py` or `scripts/skintokens_infer.py` as a normal workflow. TRELLIS.2 (24 GB NVIDIA) and SkinTokens (14 GB NVIDIA) CANNOT provide their real neural inference on this CPU-only path; do not claim otherwise. Keep those references only as unexecuted upstream documentation.

Default entry point: `python scripts/build_with_anatomy.py --blender blender --output-dir build/monster-cpu`, which dispatches to the self-contained `scripts/build_cpu_only.py`; no runtime network/download/GPU needed with installed Blender 4.5 and CPU Python numpy/scipy/trimesh/Pillow. The default pipeline creates sprite-stacked volumetric pose libraries from a procedural animated MONSTER_RIG blockout, assigns CPU-only bone weights to any eligible previously unweighted muscles, bakes anatomical flex/stretch morph tracks and exports a GLB. No GPU materials inference, Texture AI, or auto detailed one-image-to-3D claims. CPU-generated shape is a draft requiring artistic sculpting.

Existing artist-authored .blend with the same monster armature: `--cpu-input-blend existing.blend --cpu-skip-morphs` (or omit `--cpu-skip-morphs` if ANATOMY_FLEX is absent). Blender CPU `ARMATURE_AUTO` bone heat runs first and deterministic proximity weighted bone segments are fallback. Both produce at most 4 influences per vertex and preserve existing skinned meshes. End user need only start one command; do not ask for editing scripts.

External integrations (MyoGeneratorRemix, Z-Anatomy, MPFB, Instant Meshes, Rigger, Pose Shape Keys) remain CPU-capable and optional via `--full-external-cpu`, with separate CPU-compatible source installations. Offline CPU default does not demand these downloads. Preserve original geometry, character identity, rig, actions and exported visuals; halt on missing Blender or failed mesh deformation, never claim successful execution without Blender.

Read `references/CPU_ONLY_PIPELINE.md` and `scripts/cpu_skinning_blender.py` before recommending GPU workflows. For new unweighted GLB, first place mesh into a scene with MONSTER_RIG and save .blend; the CPU bridge does not invent anatomical bone correspondence from arbitrary 3D characters.

## Goal
Construct muscle-first fantasy monsters, preserving anatomical logic even when proportions are impossible. Maintain a **single consistent character** across views and animations. Never substitute generic capsules, texture-only muscles, disconnected limbs or primitive-only proxy models for a requested finished creature.

## Required production stages
1. Analyze the user's reference image using a 3D-coordinate sheet: shoulder girdle, scapulae, spine, pelvis, joints, limbs, muscle origins/insertions, silhouette, pronounced asymmetric deformations. Mark occluded anatomy as an assumption, not a measured fact.
2. Create clean 3D skeleton and joint axes before muscles. Give extreme creature anatomy a defensible mechanical structure: usable elbow/knee hinges, scapular motion, Achilles line, gripping hand and digits. Avoid impossible limb intersections and floating attachments. Distinguish shoulder muscle from dorsal hump and elongated forearm flexor bundles.
3. **Read `references/MPFB2_BRIDGE.md` and `references/Z_ANATOMY_BRIDGE.md`.** Obtain Z-Anatomy (pinned verified upstream archive) with `scripts/download_z_anatomy.py`; inspect *object names* in its Blender template via `scripts/z_anatomy_bridge.py`, produce mesh anchor pairs + CSV with anatomical muscle labels, and use those meshes as manual origin/insertion selection surfaces. All Z-Anatomy helpers are guides and **not** proven real muscle attachments. Never export Z-Anatomy geometry to a commercial GLB without provenance and separate rights review.
4. Create a non-exportable **MPFB2 anatomical donor** in Blender using `scripts/download_mpfb.py` and `scripts/mpfb_anatomy_bridge.py`. Use `HumanService.create_human()`, `HumanObjectProperties` macro parameters and `HumanService.add_builtin_rig(..., "game_engine")`. Compare 17 bone segments to the original monster rig and transfer matched *relative bone fractions* of Z-Anatomy mesh landmarks to MPFB donor, recording the map in CSV and JSON. Donor is a separate reference; NEVER replace the creature silhouette or call an MPFB humanoid body the requested finished monster. MPFB human basemesh is CC0 output; MPFB code is GPL-3. Read `references/MPFB2_BRIDGE.md`.
5. Use **upstream MyoGeneratorRemix**: source is fetched via `scripts/download_myogenerator.py` and enabled as a Blender add-on. For each muscle, select attachment regions on origin/insertion bone meshes, create editable Bezier muscle path, preview volume, adjust profile/orientation, generate final mesh; preserve the addon provenance and attribution. Read `references/MYOGENERATOR_WORKFLOW.md`. The bridge links anatomical names to the helper meshes; do not claim it automatically reconstructs human muscle fibres. Do **not** describe the addon as able to infer skeletal anatomy from a single photograph or automatically skin an entire creature; it generates individual muscles between user-specified attachments.
6. Start optionally from `scripts/build_monster.py` to create a tangible, rigged **concept blockout**, not a final MyoGenerator muscle reconstruction. Replace its placeholder muscle volumes with the addon-generated ones. Match the supplied reference silhouette from front, side and 3/4 views.
7. Add tendons and outer skin only after attachment checks. Use actual muscle volumes and believable form transitions, thin stretched skin over elbow/patella, fibrous grooves, strain at shoulder/neck. No noise texture as a substitute for sculpted geometry.
8. Skin meshes to one armature; use twist correction at limbs and corrective shape keys for shoulder, elbow, hip and knee. If extra tendrils/tongues, rig them separately within the same scene and distinct hierarchy.
9. Create looped idle breathing/sway, biped/quadruped stalk/run, attack/grab, stagger/recovery. Wide visible deliberate movement, no uncommanded attack when idle, no shape-only jitter. Footplant, no foot skating. Do not synthesize character movement solely by stretching/distorting an image.
10. Export `.blend` source, `.glb` with animation, and optional Three.js HTML with real camera/orbit + input. Verify mesh deformation, normals, scale, texture/morph inclusion, clip names, GLB size, desktop and portrait/landscape mobile.

## Quality criteria
- Every large muscle has an anatomically motivated origin and insertion and deforms around a joint. If muscle deformation is simulated only by skinning, say so; this is not physiological tissue simulation.
- Character silhouette readable at game camera distance, no exploded joints, flipped normals, topology self-intersections, missing fingers, broken pose changes.
- Keep primary anatomical topology clean; use retopology and baking for game LOD. Verify preserved silhouette after Draco/meshopt compression before calling it lossless.
- Performance optimization should not silently remove anatomy, muscles or animations.
- If Blender, network access, add-on, or a reference asset are unavailable: create the best reproducible artifact and explicitly identify the missing dependency; never claim runtime validation without running it.
- Prefer delivering a complete ready-to-run asset, not reports, snippets, or handoffs. Respect source GPL licensing and downstream game-art license separation.

## References and scripts
- `references/ANATOMY_MAP.md` — anatomical muscle layout and intended creature action.
- `references/MPFB2_BRIDGE.md` — MPFB donor, third-party model licensing, bone-length/anchor maps.
- `scripts/download_mpfb.py` — verified pinned upstream code download (local network required).
- `scripts/setup_mpfb.py` — builds official extension using Blender and optionally installs in the Blender profile.
- `scripts/mpfb_anatomy_bridge.py` — creates the MPFB real donor rig/mesh and maps 17 creature bones / 30 muscle pairs.
- `references/Z_ANATOMY_BRIDGE.md` — provenance-aware Z-Anatomy ↔ MyoGeneratorRemix interoperability; licensing.
- `scripts/download_z_anatomy.py` — fetches pinned upstream 83 MiB atlas + source notices with git blob integrity checking.
- `scripts/z_anatomy_bridge.py` — creates skeleton-mounted mesh attachment pairs, CSV, external-atlas muscle-name lookups in Blender.
- `scripts/myo_select_anchors.py` — switches Myo origin/insertion object pointers to selected attachment mesh pair.
- `scripts/build_with_anatomy.py` — end-to-end local orchestration; needs Blender + network.
- `references/MYOGENERATOR_WORKFLOW.md` — origin/insertion workflow, upstream limitations.
- `scripts/download_myogenerator.py` — fetches pinned upstream sources (not executed automatically by ChatGPT plugin).
- `scripts/build_monster.py` — original independent animated blockout; editable in Blender.

## Existing skills synergy
Hand actual `.glb` to `blender-model-animation-enhancer` for retopology/material/GLB optimization and to `hero-animator` only for hybrid 2.5D presentations. Pass skeletal clips to Three.js pipelines; never treat 2D sprite deformation as a substitute for true 3D articulation.

## MPFB three-way integration hard gate
Run `python scripts/build_with_anatomy.py --blender blender` with Blender 4.2+ and a network-capable machine. The integrated default downloads, builds and installs MPFB2, as well as fetching the two previous sources. The `--skip-mpfb` option keeps the v0.2 two-source workflow. Do NOT silently claim the MPFB donor exists when build or installation fails. `monster_base.glb` is the original blockout, not a high-fidelity MPFB creature replacement. `monster_three_way_anatomy.blend` is the rig/marker reference scene. The donor is deliberately excluded from the game GLB.

## Z-Anatomy integration hard gate
Use `python scripts/build_with_anatomy.py --blender blender` on a networked Blender-capable machine to fetch all three upstreams and create `.blend`, `.glb` and marker CSV. Z-Anatomy atlas files are not bundled with this plugin because of size and mixed licensing. `Z_ANATOMY_ATTACHMENTS` contains editable Blender bone-parented mesh markers for MyoGeneratorRemix origin/insertion selection; **not** atlas models. Atlas name matching is advisory and requires inspection. The generated GLB is only the initial rigged blockout until actual addon muscles and skinning are authored.


## Blender 4.5 LTS — fourth integration, mandatory for muscle deformation output

Read `references/BLENDER_45_BRIDGE.md` before changing the production pipeline.
Use official Blender 4.5.16 LTS, whose verified installer is `scripts/download_blender.py` (source checkout: `--source-only`). If missing, `python scripts/build_with_anatomy.py --install-blender` on a network-connected x64 workstation installs the portable binary. The source is pinned to upstream Git commit `3f6797307da591fd6feb47013bd117ec557931a7`. Do not claim software is installed in sandbox without a successful executable check.

1. Preserve `build_monster.py`'s original rig, silhouette and animated muscle geometry. NEVER replace the creature with an MPFB base human.
2. Prepare Z-Anatomy bone-parented markers and MPFB donor as the prior stages already specify. Do not export atlas/donor meshes.
3. For every actual artist-generated MyoGeneratorRemix muscle, use `scripts/myo_rig_bridge.py` and a matching `ZA_ORIGIN_<muscle>` / `ZA_INSERTION_<muscle>` pair. This gives a real skinning path to MONSTER_RIG; manually review origin/insertion, bone weights and deformations.
4. Run `scripts/blender_sculpt_bridge.py`: create distinct `ANATOMY_FLEX` / `ANATOMY_STRETCH` shape keys on the *actual existing muscle mesh*. Preserve attachment endpoints and original vertex topology; do not use mesh-global scaling or texture-only bulges.
5. Bake pose-dependent contraction to named NLA morph tracks for each rig action (`IDLE_BREATH`, `STALK_LOOP`, `GRAB_ATTACK`). Never rely solely on Blender drivers in a Three.js GLB: drivers cannot simply export as runtime muscles.
6. When sculpting is requested, include `--workbench-copies` to create a high-poly `SCULPT_WORKBENCH_NON_EXPORT` collection, sculpt the anatomical skin manually, then bake to game mesh normals without changing the approved character.
7. Export `monster_muscle_deform.glb` via GLTF `export_animation_mode='NLA_TRACKS'`, morph and skin enabled, selecting ONLY the monster rig and game creature. Deliver the `.blend` source as well. Inspect/animate the result in real Blender and Three.js before claiming a visual PASS.
8. If `bpy`/Blender unavailable, save reproducible executable scripts and precise constraints; do not claim end-to-end verification or finished real muscle simulation. This integration is artistic shape-key plus skeletal animation, not finite-element physical tissue simulation.

Integrated entry point: `python scripts/build_with_anatomy.py --blender blender --output-dir build/monster --workbench-copies`, or use `--install-blender` on a networked x64 workstation. `--skip-blender-detail` is only for backwards compatibility.


## TRELLIS.2 — fifth integrated open-source system

Before generating 3D from a monster drawing, read `references/TRELLIS2_BRIDGE.md`. Use the pinned official source installer `scripts/download_trellis2.py` to obtain Microsoft/TRELLIS.2 from GitHub with recursive submodules. Do NOT state the full source, pretrained weights or GPU runtime are bundled; only the original MIT-licensed upstream example and attribution are vendored. Official upstream requires Linux, NVIDIA GPU with at least 24 GB VRAM and CUDA; separate dependencies may have separate licenses.

- Use `scripts/trellis2_generate.py` with official `Trellis2ImageTo3DPipeline` + `o_voxel.postprocess.to_glb()` to produce real **unrigged** `trellis_draft.glb` with PBR materials. Input images with alpha are preferable; allow official background removal when no alpha. Do not claim single-image generation reconstructs hidden anatomy.
- Import the real generated mesh via `scripts/trellis_surface_bridge.py`, preserving UVs and textures and storing only in `TRELLIS_REFERENCE_NON_EXPORT`. Scale uniformly to original rig; record editable Z rotation and nearest-surface distances of every `ZA_*` muscle guide marker. Never replace the monster or its independent original game skinned meshes with an unrigged/static donor.
- MPFB2 donor and Z-Anatomy guide structures remain separately hidden from game export; MyoGeneratorRemix creates and artist-authors actual muscles and attachment curves. TRELLIS.2 supplies shape/color/detail reference for retopology and manual Blender sculpt/texture projection, not simulated muscles.
- Invoke `python scripts/build_with_anatomy.py --blender blender --trellis-glb /path/to/real_trellis2.glb` to integrate existing generated model; or use `--trellis-input assets/monster_reference.png --trellis-python /path/to/trellis2/python` on supported CUDA systems. The latter downloads source first if needed.
- Validate user-facing output only when actual CUDA inference, Blender import and resulting GLB animations were run. If unavailable, state constraints succinctly and provide executable plugin source. Never call a background-only placeholder output a finished 3D reconstruction.

## Instant Meshes integration — v0.6 hard gate

**Mandatory when a user asks for lightweight game anatomy / reduced 3D triangles:** read `references/INSTANT_MESHES_BRIDGE.md`. Apply Instant Meshes to the *actual original rigged monster meshes*, not Z-Anatomy atlas meshes, MPFB humanoid donor, TRELLIS.2 PBR draft, or a generic replacement proxy.

Run `python scripts/build_with_anatomy.py --instant-retopo --instant-ratio 0.4` on a networked Blender workstation or with `--instant-bin` already built. `scripts/download_instant_meshes.py` pins upstream SHA `7b3160864a2e1025af498c84cfed91cbfb613698` and builds it using CMake, only when needed. Preserve upstream BSD-style license text in `vendor/InstantMeshes-UPSTREAM-LICENSE.txt`. Do NOT claim source and executable installed merely because a downloader exists.

The 3-stage bridge (`scripts/instant_meshes_worker.py` and `scripts/instant_blender_bridge.py`) exports real local rest-pose mesh parts as OBJ, runs upstream Instant Meshes in CLI quad batch mode, and reimports with per-vertex barycentric transfer of original skinning, material index, UV, corrective flex/stretch key coordinates and matching morph-NLA actions. Keep the same rig and action clips. Hidden source meshes remain in the .blend for rollback and never go into game GLB. Fail closed if triangle count is not reduced, if geometry differs substantially, if weights or NLA copying fails, or when tools are unavailable. If an individual component is too thin/nonmanifold, keep the original and manually retopologize rather than silently replacing it.

**Six-tool sequence:** `reference image → TRELLIS.2 static PBR draft (optional) → Z-Anatomy/MyoGenerator muscle landmark guides + MPFB donor → Blender art-directed single skeleton muscle sculpt → Blender baked morph animation → Instant Meshes quad LOD + attribute transfer → game-ready glTF/GLB`. This is a reproducible intended integration; no Blender execution was possible in this runtime. Never claim animated GLB validation without observing outputs.

## Seven-source Rigger integration (v0.7.0)

**Read `references/RIGGER_BRIDGE.md` before generating or changing motion.** The seventh source is `asu37/Rigger` revision `c8f1d1b9a8729582c61fa0ffa9a658ec4f4f6e77`, GPL-3.0-or-later, Blender 4.2+. Source acquisition is handled by `scripts/download_rigger.py` with pin/manifest validation; never invent installed tools when DNS, Git or Blender is inaccessible.

Route original **MONSTER_RIG** through Rigger without identity replacement:
- To create real FK/IK animator controls in a new `.blend`: `python scripts/build_with_anatomy.py --blender blender --rigger-controls`. Uses `QuickRig` in `PRESERVE` mode; never `CONVERT`, never rename weights or delete source rig. Must find valid limb mapping; otherwise stop for a manual Rigger rig adjustment.
- To import real external motion, `python scripts/build_with_anatomy.py --blender blender --rigger-motion /path/run.glb --rigger-clip RUN_RIGGER`. Real source GLB/FBX required. Use `--rigger-motion-action`, `--rigger-motion-rig` or an explicit `--rigger-bone-map` for ambiguous inputs. For the **MPFB2 donor game_engine skeleton only**, use `references/MPFB_TO_MONSTER_BONE_MAP.json` (17 source→monster bone pairs) when names match. Never map arbitrary monster bones by guess.
- For existing .blend without rebuilding, use `scripts/rigger_monster_worker.py --mode retarget|controls|export` with exact paths. The backend invokes official `rigger.quick_rig`, `rigger.retarget`, or `rigger.export` in Blender, not a mock implementation.
- When retargeting, create a **new named NLA clip**, preserve all original NLA clip names and bone names, and bake a matching muscle flex/stretch morph track using true posed bone angles. Do not modify original mesh coordinates, UV, weights, morph coordinates or identity. The imported source person/rig must be excluded from the game GLB.
- Run this stage **after Instant Meshes** so the same skinned LOD and same bone names are used. Do not export MPFB/Z-Anatomy donor geometry or TRELLIS static references as finished character art.
- When external source, Blender or Rigger installation is missing: halt with a clear blocked dependency, do not claim a rigged output exists.

Deliver the current same-plugin artifact link and ZIP. The user is building one evolving skill, not asking for separate new plugins.

## Mandatory Pose Shape Keys integration for high-quality joint creasing (eighth source)

- Read `references/POSE_SHAPE_KEYS_BRIDGE.md` before authoring corrective shape keys. Use verified **Blender Studio Pose Shape Keys v1.0.0** with Blender 4.5 (official v1.1.1 requires Blender 5.0 and is incompatible with pinned Blender 4.5). License GPL-3.0-or-later. Do not silently use the latest incompatible addon.
- `scripts/download_pose_shape_keys.py` fetches the exact compatible archive from Blender's official dynamic extension index (archive SHA-256 is mandatory); offline `--zip` can use a previously downloaded official zip. Upstream GPL code must not be misrepresented as bundled or downloaded if no network access.
- Opt-in `--pose-shape-keys` creates a separate `monster_pose_key_authoring.blend` after Instant Meshes retopology and optional Rigger controls. Existing `ANATOMY_FLEX` shape keys receive real native PoseKey authoring entries linked to their `ATTACK` action/frame, aligned with the same `MONSTER_RIG`. No source mesh, vertex weights, UV, existing morph or action is overwritten by registration.
- Real corrective sculpt is ARTIST-EDITED: Set Pose, Store Evaluated Mesh, sculpt correct joint fold muscle silhouette, Overwrite Shape Keys. Never report an authoring entry as proof of completed muscle anatomy.
- Preserve motion loops and all GLB clips. Bake finished shape key corrections to NLA/action keyframes for Three.js; addon Blender metadata and drivers are not transported by glTF. Preserve one stable creature across poses, and never substitute MPFB or TRELLIS static reference.
- If Blender 4.5, official source, or validated source animation is absent, leave this optional stage disabled and truthfully mark the integration as code-only, not fully run.


## Ninth source: Open Mocap CPU (v1.0.0) — mandatory CPU-only integration

Read `references/OPEN_MOCAP_CPU_BRIDGE.md`. Official source https://github.com/Larenju-Rai/open-mocap-blender pinned at `1ec7457dad228661cbd8a1d98163e8288d3f7db5`, MIT. This skill **bundles a source-derived headless CPU port of the original Open Mocap pose tracker** (cvzone/MediaPipe's 33 base points plus 7 Open Mocap centroids). It is not a newly invented pose tracker, and does not depend on Blender 4.0, CUDA or GPU. Original GUI addon still supports only Blender <=4.0 and must NEVER be loaded into Blender 4.5. Original complete code/video repo is not bundled; optional pinned source downloader at `scripts/download_open_mocap.py`. Read `vendor/OpenMocap-SOURCE.md` and its MIT license notice.

With a user-supplied actual video and installed CPU dependencies, run `python scripts/build_with_anatomy.py --blender blender --mocap-video motion.mp4 --mocap-clip MOCAP_WALK`. `--mocap-side-video` requires exactly synchronized video for depth and `--mocap-bone-map` accepts explicit bone-to-40-point index pairs. `--cpu-input-blend` imports original monster rather than creating a new model. No video supplied? Keep existing default GPU-free Blender pipeline. The dedicated `scripts/open_mocap_cpu_worker.py` calls `open_mocap_cpu_capture.py` then `open_mocap_retarget_blender.py` on existing `.blend`. No clips/characters are invented when capture does not detect a person. Never auto-play movement in a game without player intent.

Preserve SAME `MONSTER_RIG`, vertex groups, materials, mesh geometry, original clip names, `ANATOMY_FLEX` and `ANATOMY_STRETCH`. A new NLA action drives actual bone rotations, and existing Rigger/anatomy morph helper bakes matched muscle shape key motion. Use the exact known monster bone names or explicit user-provided map. Do not claim root path, foot contact, fingers or physiological simulation from a single video. Source video is NOT a replacement for hero art. `TRELLIS.2` and `SkinTokens` remain CUDA-disabled even when Open Mocap is active.

If video dependencies are absent, surface a clear setup requirement; if Blender absent, never claim a produced GLB. This sandbox cannot verify real Blender/video motion quality without those dependencies.

## PyMeshLab CPU geometry repair — tenth source (v1.1.0)

Use [PyMeshLab CPU bridge](../../references/PYMESHLAB_CPU_BRIDGE.md). Official release v2025.7.post1, pinned PyMeshLab source `9c30334547750bcbe7126278b16739349643d04b`; GPL-3.0. Install PyMeshLab in external CPU Python, never require GPU or CUDA. Run `scripts/build_cpu_only.py --pymeshlab-audit` or `--pymeshlab-clean-static` (no implicit network). The stage **precedes CPU skinning** so it can repair new unrigged static triangular muscle/skin geometry before creating weights. Never modify original skinned `MONSTER_RIG`, animation, morphs, UVs, materials, donor/atlas reference data, or existing artist sculpt. Save new `.blend`, source untouched. If input is already skinned, perform audit only and report it as protected. Instant Meshes performs optional later LOD/retopology; PyMeshLab does not replace it. Open Mocap and Rigger remain downstream; CPU-only hard gate applies to all stages. No runtime claim without installed Blender/PyMeshLab.

## Eleventh source — glTF-Transform 4.5.1 (CPU-only)

**Read `references/GLTF_TRANSFORM_CPU_BRIDGE.md`.** Official source `donmccurdy/glTF-Transform` (MIT), installed locally with pinned `@gltf-transform/cli@4.5.1` and Node >=20 via `scripts/install_gltf_transform.py --install` on a machine with internet access. Do not promise the upstream code or npm dependencies are bundled, or that an uninstalled CLI ran.

The stage is strictly **after** CPU mesh generation, static PyMeshLab cleanup, optional Instant Meshes LOD, Rigger/Open Mocap animation and muscle morph baking. Never invoke GPU/CUDA or modify original GLB/BLEND.

For a new build: `python scripts/build_with_anatomy.py --blender blender --gltf-optimize --gltf-mode safe` (the same flags exist in `scripts/build_cpu_only.py`). For an existing GLB run `scripts/gltf_transform_worker.py --input original.glb --output smaller.glb --mode safe`. The default, safest `dedup` command introduces no extra codec and protects node hierarchy/transforms, skins, primitive attributes, morph layout and animation channels, refusing incompatible output. No actual shrinkage is guaranteed; if no size advantage, copy the original into the separate output.

Only explicit `--gltf-mode meshopt` invokes Meshoptimizer compression and **requires `MeshoptDecoder` configured in Three.js** when the GLB has `EXT_meshopt_compression`. Meshopt may change floating-point precision/appearance; never call it lossless or ship to a decoder-less standalone HTML. No texture re-encoding, neural inference, GPU or unrequested model changes. Real Blender and browser inspection still required before publication.


## Twelfth source — Khronos glTF-Validator (v1.3.0 CPU)

Read `references/GLTF_VALIDATOR_CPU_BRIDGE.md` and `vendor/glTF-Validator-SOURCE.md`. Use **actual** KhronosGroup/glTF-Validator npm `gltf-validator@2.0.0-dev.3.10` (Apache-2.0) via `scripts/install_gltf_validator.py --install` on a networked CPU workstation. Never pretend the npm package was installed or that a completed validation ran in a sandbox with blocked DNS.

The official `validateBytes` API must run against the unchanged GLB exported by the same Blender/Rigger/Open Mocap monster pipeline, and again after optional glTF-Transform optimization. Enable with `--gltf-validate` on `scripts/build_cpu_only.py` or `scripts/build_with_anatomy.py`; standalone `scripts/gltf_validator_worker.py --input monster.glb` works without Blender. Fail closed when no official validator is installed, validation has errors, or required extension is outside the pinned validator's known set. An optional strict warnings gate is available. No GPU, no model replacement, no user-facing report artifact. Do not call schema validity proof of visual correctness, performance, physics or motion quality.


## Thirteenth-source xatlas CPU-only UV preservation (v1.4.0)

Read `references/XATLAS_CPU_BRIDGE.md` before applying xatlas. Use official
`jpcy/xatlas` (MIT) through CPU `mworchel/xatlas-python==0.0.11` (MIT),
installed via `scripts/install_xatlas_cpu.py --install` in an isolated CPU
Python environment. This is a post-rig, post-LOD UV-only stage, enabled by
`--xatlas-uv` in `scripts/build_with_anatomy.py` / `scripts/build_cpu_only.py`.

**Hard requirements:**
- Preserve exactly the same game hero and rig. Never rebuild skeleton, mesh
  topology, weights, morphs or animation actions merely to generate UVs.
- Do not overwrite any existing UV layer. Never touch MPFB donor, Z-Anatomy
  atlas, TRELLIS static references, hidden workbench or image-textured meshes.
- Use official upstream `xatlas.parametrize` on CPU; its seam-split vertex
  mapping is transferred into Blender polygon corner UVs, without changing
  mesh vertices. Reject ambiguous n-gon splits, duplicate triangles, new
  geometry and invalid texture coordinates rather than deform the character.
- Structural GLB before/after comparison must preserve skins, joints, animation
  channel targets, clips, materials, morph-target counts and mesh count.
- Generate new output scene and GLB, then optionally call existing glTF-Transform
  and Khronos Validator stages. No GPU required anywhere on the default path.
- Do not claim that UV unwrapping created textures, normal maps or artist-quality
  PBR. It provides a texture coordinate atlas only. It must not be described
  as downloaded/run when external xatlas/Blender isn't actually installed.


## Fourteenth source — Pillow 12.3.0 CPU texture atlas PBR (v1.5.0)

Read `references/PILLOW_PBR_CPU_BRIDGE.md`. Pinned official `python-pillow/Pillow`
tag `12.3.0` (MIT-CMU), commit `bb1d8e8ab8d29048624d96e3ee53cecf7c13d13d`.
Use installed official package, never invent a substitute renderer. Pillow is
run in external CPU Python; Blender’s bundled Python is not modified.

Enable with `--xatlas-uv --pbr-cpu` in either build launcher; optionally
`--pbr-size 512 --pbr-wetness 0.35`. This runs after xatlas, before the
existing glTF Transform and Khronos Validator stages. Real rest-pose mesh
curvature and existing material base color/roughness are rasterized onto the
actual xatlas UV triangles into albedo/roughness PNGs; the original rig/shape
keys/UV/weight structure never changes. Copies of simple Principled materials
are connected to packed images and exported in a new separate GLB. Existing
artist textures, procedural node graphs and original materials are protected.

The skin look has no randomized texture/pattern; it only enhances actual
sculpted creases and allows opt-in damp gloss. It is *not* a normal map or
photogrammetry. CPU worker was run with real Pillow; actual Blender runtime
and appearance/Three.js verification still require a Blender installation.
No CUDA inference, no GPU dependency, no automatic model or animation replacement.


## Fifteenth source — meshoptimizer v1.3 / official gltfpack (CPU)

Read `references/MESHOPTIMIZER_CPU_BRIDGE.md`. The v1.6.0 addition includes `scripts/install_meshoptimizer_cpu.py` with release SHA-256 checks and `scripts/meshoptimizer_cpu_worker.py`, an official-CLI process bridge. **No GPU, CUDA or neural inference**. This stage is always optional and runs *after* PyMeshLab, xatlas, Pillow PBR, Blender/Rigger/Open Mocap motion, and optional glTF Transform. Use `--meshoptimizer` with the same existing `build_with_anatomy.py` entrypoint.

- When using glTF Transform together, require `--gltf-mode safe`: do not pass pre-compressed meshopt files to gltfpack.
- In gltfpack safe mode, keep named nodes/materials/extras with `-kn -km -ke`, and disable quantization (`-noq`). No simplification and no new texture encoding.
- For compressed mode `-c`, note `EXT_meshopt_compression` and require the Three.js `MeshoptDecoder` shipped with the game; this cannot be an external CDN for an autonomous HTML build.
- Guard the same MONSTER_RIG, all animation clips, muscle morph targets, topology attribute types, original PBR texture content/UV channels. Make no visual-fidelity claims solely from a structural guard; reject results losing protected structures.
- The Khronos Validator must run before and after gltfpack. Missing validator/native gltfpack causes a clear failure, never a fake PASS.
- The current runtime cannot download/build upstream gltfpack; **do not claim the binary is bundled or that a real GLB was optimized**. The CPU code integration is published for use with the official installed executable.


## Trimesh read-only CPU mesh topology gate (16th source)

- Read `references/TRIMESH_CPU_BRIDGE.md`. This stage complements PyMeshLab repair but never edits approved characters. Real `trimesh==4.11.1` must be installed (MIT; no GPU).
- The `--trimesh-audit` flag in `build_with_anatomy.py`/`build_cpu_only.py` analyzes final uncompressed GLB after xatlas/Pillow and before glTF-Transform/meshoptimizer. It checks triangles, finite coordinates, nonmanifold connections, boundary edges and winding, using an actual Trimesh `Scene` to preserve distinct mesh instances.
- Flag `--trimesh-strict` rejects nonmanifold and winding faults; open boundaries stay advisory for artist-designed thin muscle or skin membranes. Standalone: `python scripts/trimesh_cpu_guard.py --input model.glb`.
- Never use Trimesh to replace GLB export, source meshes, material graphs, skin weights, UVs, muscle shape keys, Rigger clips, Open Mocap motion, or any approved hero visual. Trimesh does not prove dynamic collision-free posing, full-skeleton correctness, or identity. Keep Khronos Validator mandatory when meshoptimizer compression is selected.
- If Python package or input GLB is absent: fail with an explicit dependency error, not a claimed successful analysis.


## Seventeenth-source Manifold3D solid-CSG CPU bridge — v1.8.0

**Read `references/MANIFOLD3D_CPU_BRIDGE.md` first.** Actual upstream: `elalish/manifold` tag `v3.5.5` (`manifold3d==3.5.5`, Apache-2.0). The project is CPU-only; this is a real optional CSG process, not fake CSG and not a neural/generative model. The orchestrator `--manifold-cpu` runs after PyMeshLab and before CPU skinning; the extended CPU path connects it before creating new muscle morphs. Pass `--manifold-objects NAME1,NAME2` only when automatic `MUSCLE_/BODY_/SHELL_` selection cannot safely identify inputs. Use a Python installation verified by `scripts/install_manifold3d_cpu.py`, supplied as `--manifold-python PATH` if needed.

**Hard identity gate**: only 2+ closed solid geometry **read-only snapshots**; the upstream source may be rigged, UV-mapped and animated but none of those attributes are copied, removed or changed. Blender quad/ngon triangulation occurs in-memory without editing the original. Never treat the Boolean result as a game-ready skinned mesh. Trimesh independently verifies source and output, Manifold3D computes CPU Boolean union. Never change the original character's mesh, skeleton, materials, UV, morphs, rigs or animations. The new union is a non-exportable, authoring-only `MANIFOLD_SCULPT_REFERENCE` in a new `.blend`. Retopology, re-skinning, UV and morphology transfer need manual artistic approval before a Boolean shell may become a game mesh. Never report an unexported wire reference as a finished game mesh.

Network blocked or Manifold3D/Blender missing: stop with clear error, never claim actual CSG ran. Existing production path must still work without `--manifold-cpu`. Preserve all other 16 source integrations and their license constraints.


## Eighteenth-source SciPy CPU smooth skin (v1.9.0)

Read `references/SCIPY_SKIN_CPU_BRIDGE.md` before invoking. Use official `scipy/scipy` **v1.17.0** (BSD-3-Clause) in an external CPU Python (installed independently, never bundled). Enable **only when requested** by passing `--scipy-skin-smooth` to `build_with_anatomy.py` or `build_cpu_only.py`, optionally `--scipy-python`, `--scipy-iterations`, `--scipy-strength`.

This follows Trimesh/PyMeshLab/Blender Bone Heat and precedes Blender shape-key sculpt and Rigger/Open Mocap animation. Actual `scipy.sparse` edge diffusion runs in a separate subprocess and transfers only bone weights of meshes that had **zero** vertex groups beforehand. Never smooth or delete already-painted weights or alter mesh data, UVs, materials, actions, skeleton, stored morph targets or the one-character identity. Connectivity-based edges stop weights crossing disconnected neighboring muscle objects. Anchors >=0.995 are locked; sparse diffusion normalized and capped to four bone influences per vertex for glTF. Reject nonfinite data and unexpected weight changes. The new stage cannot improve an already weighted model without explicit new unweighted muscles; report that nothing was modified, rather than falsely saying repaired.

Do NOT claim it is automatic anatomical sculpting, biomechanical motion, AI rigging, or that full Blender execution was validated. Missing SciPy must hard-fail if this optional stage was requested. The default CPU pipeline remains usable without SciPy, CUDA, or any GPU.
