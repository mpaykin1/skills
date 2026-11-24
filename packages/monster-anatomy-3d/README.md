# Monster Anatomy 3D v2.0.0 — SPRITE STACKING FIRST / CPU

**True horizontal sprite stacking is the primary visible game representation.** The unchanged anatomical 3D monster and its Blender rig produce independently posed RGB-alpha volume layers for every real motion action (idle, stalk, attack, plus captured real motions). Runtime Three.js/WebGL2 raymarches those volumes from arbitrary 3D viewpoints rather than substituting a billboard, GIF, or primitive mesh. This preserves anatomy and the original model across every pose. Source `.blend`/`.glb` remains available for authoring, physics, and fallback.

From a real existing GLB, no Blender or GPU required:

```bash
python scripts/build_with_anatomy.py --sprite-source monster.glb --output-dir build/sprite-monster
```

From a rigged Blender scene, automatically bake all real action stacks:

```bash
python scripts/build_sprite_stacking.py --input-blend monster.blend --blender blender --output build/monster-stacks
```

**Both require external CPU Python `numpy scipy trimesh Pillow`.** See `references/SPRITE_STACKING_PRIMARY.md` for 360 GIF, transparent slice atlases, mobile quality settings and `runtime/sprite_stack_three.js` usage. No image-only extrusion, no NVIDIA, no CUDA. The original Blender-native pipeline and all previous 18-source integrations are retained. GPU-only TRELLIS.2 and SkinTokens neural inference remain disabled.

---

# Monster Anatomy 3D v1.9.0 — CPU-only default

**Runs on a CPU-only computer with Blender 4.5+. No NVIDIA GPU, CUDA, neural checkpoints, or online API required for the default build.**

The default `scripts/build_with_anatomy.py` is now a CPU pipeline (same as `scripts/build_cpu_only.py`). It creates an original skinned, animated 3D monster, preserves source mesh, binds any eligible new unweighted muscle/skin geometry to `MONSTER_RIG` using Blender bone heat (falling back to analytical proximity weights) and bakes visible muscle flex/stretch morph animation, producing `.blend` and `.glb` for Three.js. Blender uses CPU for these operations; external GPU stages never run.

Run on a CPU-only computer with Blender already installed:

```bash
python scripts/build_with_anatomy.py --blender blender --output-dir build/monster-cpu
```

For an existing edited Blender creature with `MONSTER_RIG`:

```bash
python scripts/build_with_anatomy.py --blender blender --cpu-input-blend /path/to/monster.blend --cpu-skip-morphs
```

For artist-created new muscle meshes that have no weights, `cpu_skinning_blender.py` adds CPU armature weights while leaving existing weighted meshes, materials, UVs, shape keys, and clips intact. It does not replace your creature with a generic humanoid. CPU proximity weights are a **rigging approximation**, not biomechanical muscle simulation, and may need manual paint cleanup. CPU geometry from a single drawing is a concept blockout, not an AI reconstruction.

**Optional CPU-only ecosystem:** `--full-external-cpu` activates existing MyoGeneratorRemix, Z-Anatomy, MPFB2, Instant Meshes, Rigger and Pose Shape Keys integrations (each requires its respective checked-out CPU-capable source/Blender addon). Full external mode may fetch missing sources unless `--offline` is used. Blender raster rendering with Eevee may use graphics hardware; this default headless modelling and glTF export pipeline does not require an NVIDIA GPU.

**Disabled GPU-only systems:** SkinTokens (NVIDIA >=14GB) and Microsoft TRELLIS.2 (NVIDIA >=24GB) cannot run in this CPU-only workflow. Their prior documentation is retained for provenance, but neural inference is never an automatic step. Static meshes exported elsewhere can still be imported to Blender and rigged on CPU.

**Important:** The current ChatGPT execution container does not contain Blender, so actual animation/GLB generation is not proven here. Reproducible Python source and plugin package are provided.

## Existing source integrations

**Eight cooperating open-source projects:** MyoGeneratorRemix × Z-Anatomy × MPFB2 × Blender 4.5 LTS × Microsoft TRELLIS.2 × Instant Meshes × Rigger × Pose Shape Keys.

- **MyoGeneratorRemix**: artists create true editable 3D muscle bellies between origin/insertion attachment regions.
- **Z-Anatomy**: terminology and labeled guide references, separate from commercial game exports.
- **MPFB2**: CC0 humanoid donor basemesh and game-engine armature used only for anatomical comparison.
- **Blender**: anatomically guided mesh deformation, two shape-key contractions per muscle, NLA morph animation synchronized to rig clips, optional high-resolution sculpt copies, and filtered animated GLB export.
- **TRELLIS.2**: actual image-to-3D PBR static draft on an NVIDIA CUDA workstation. Imported real GLB becomes non-exportable high-resolution sculpt/shape reference for anatomy; it never silently replaces the rigged monster.
- **Instant Meshes**: high-resolution skinned body and muscle meshes are remeshed to lower-density field-aligned topology. Our Blender bridge interpolates vertex skin weights, UVs, original morph shape keys and animation NLA tracks onto new LOD meshes, preserving the original rigged geometry for rollback.

One integrated command on a networked Blender workstation:

```sh
python scripts/build_with_anatomy.py --blender blender --output-dir build/monster --workbench-copies
```

To bootstrap official Blender 4.5.16 LTS first, use `--install-blender` instead of `--blender blender` (Windows x64 / Linux x64 only). The installer verifies its SHA-256 checksum from the official Blender release. A separate `python scripts/download_blender.py --source-only` clones pinned official GPL source, but does not compile it.

Outputs: animated `monster_muscle_deform.glb`, editable `monster_blender_sculpt_ready.blend`, anatomical marker CSV and MPFB correspondence JSON. **The provided creature is still an original 3D blockout**; realism of source anatomy, downstream MyoGeneratorRemix muscle sculpting, painted deformations and validation need Blender. These scripts do not constitute an automatic one-image-to-finished-monster neural model.

Blender itself was **not downloaded** into the current ChatGPT runtime: official websites were unreachable due to DNS. Runtime validation of this integration in actual Blender remains pending. The ZIP is full *skill and bridge source code* only, not a Blender binary.

Details: [Blender 4.5 bridge](references/BLENDER_45_BRIDGE.md), [MPFB2 bridge](references/MPFB2_BRIDGE.md), [Z-Anatomy bridge](references/Z_ANATOMY_BRIDGE.md), [MyoGeneratorRemix workflow](references/MYOGENERATOR_WORKFLOW.md).

## CPU-only guarantee

See [`references/CPU_ONLY_PIPELINE.md`](references/CPU_ONLY_PIPELINE.md). GPU-only original modules remain as archival/optional source references but are prohibited in default execution.

## PyMeshLab CPU mesh repair — tenth integration (v1.1.0)

The optional PyMeshLab **2025.7.post1** CPU worker (GNU GPL v3, independently installed) removes duplicate vertices/faces, zero-area triangles and unused vertices from **previously unrigged, untextured, static triangle meshes only**. Source materials, animated anatomy, weights, UV, shape keys and NLA stay unchanged. This stage runs before CPU skinning/Rigger, so newly imported sculpt meshes can be repaired before being attached to `MONSTER_RIG`.

```sh
python -m pip install 'pymeshlab==2025.7.post1' numpy
python scripts/build_with_anatomy.py --blender blender --cpu-input-blend your_unrigged_monster.blend --pymeshlab-clean-static
```

For read-only eligibility inspection: `--pymeshlab-audit`. Both require PyMeshLab in the external Python interpreter; `--pymeshlab-python` selects a different executable. Other CPU build stages remain available even without PyMeshLab. No GPU/CUDA needed.

Source: [PyMeshLab](https://github.com/cnr-isti-vclab/PyMeshLab) (GPL v3); pinned downloader `scripts/download_pymeshlab.py`. Offline use requires a local wheel or installed library. **Repository clone and runtime Blender test were not possible inside this environment (DNS blocked and Blender absent).**

Full safety rules: [PyMeshLab CPU bridge](references/PYMESHLAB_CPU_BRIDGE.md).


## Ninth source: Open Mocap CPU (v1.0.0)

Added **Open Mocap** from Larenju Rai (MIT, official pinned commit). Its original Blender 4.0 add-on is incompatible with Blender 4.5, so a separate **CPU-only code-derived Open Mocap body tracker** is bundled (`vendor/open_mocap_cpu_pose.py`). It extracts 40 real body landmarks from an MP4/MOV, preserving the 33 base points + 7 Open Mocap centroids. Our Blender 4.5 retargeter adds a new NLA motion track to the **same MONSTER_RIG** and synchronizes muscle morphs using the existing Rigger/anatomy system; it does not replace the monster or original animations. Nothing uses CUDA or GPU.

```sh
python -m pip install -r requirements-open-mocap-cpu.txt
python scripts/build_with_anatomy.py --blender blender --mocap-video motion.mp4 --mocap-clip MOCAP_WALK
```

When no motion video is given, the previous default CPU pipeline is unchanged and does not require those extra Python packages. For existing monster source, add `--cpu-input-blend my-monster.blend`. Direct use: `python scripts/open_mocap_cpu_worker.py --blender blender --blend my-monster.blend --video motion.mp4 --output-blend moved.blend --output-glb moved.glb`. See `references/OPEN_MOCAP_CPU_BRIDGE.md`.

**No actual motion or Blender run was available in the development container.** The full upstream source cannot be cloned through its blocked DNS, but the source-derived CPU tracker and its MIT license are bundled. Original full source downloader is included as an optional tool. Optional video tracking needs CPU-compatible MediaPipe, cvzone and OpenCV Python packages.


## glTF-Transform — eleventh integration (v1.2.0 CPU)

Official [glTF-Transform](https://github.com/donmccurdy/glTF-Transform) `@gltf-transform/cli@4.5.1` (MIT, Node.js >=20) is the **terminal GLB post-export step**. It cooperates with PyMeshLab/Instant Meshes geometry work, Blender/Rigger skinning, and Open Mocap clips. **CPU only**, no CUDA or GPU. The source `.blend` and original `.glb` are not overwritten.

Once on a networked CPU computer:

```sh
python scripts/install_gltf_transform.py --install
```

Then use one build command with safe optimization:

```sh
python scripts/build_with_anatomy.py --blender blender --gltf-optimize --output-dir build/monster-cpu
```

Or with an already-exported GLB, without Blender:

```sh
python scripts/gltf_transform_worker.py --input monster.glb --output monster.safe.glb --mode safe
```

`safe` mode calls the **actual upstream CLI `dedup`**, without touching textures, keyframe positions, morphs or materials, then compares animated node transforms, joints, skinning, morph targets and clip channels before publishing. If it produces a larger file, the original bytes are reused in the new output location.

`--gltf-mode meshopt` (opt-in) additionally calls upstream `meshopt --level medium`: it can reduce geometry and animation size but may quantize values, and the game **must** configure `GLTFLoader.setMeshoptDecoder(MeshoptDecoder)` if compression was applied. The default `safe` output needs **only GLTFLoader**. No gameplay FPS improvement is guaranteed. See [GLB integration](references/GLTF_TRANSFORM_CPU_BRIDGE.md).

**Current environment limitation:** Node 22 is installed, but npm registry lookup returned `EAI_AGAIN`, so the official package could not be physically downloaded or executed here. This archive includes a pinned installer, full CPU adapter and preservation checks, **not upstream source/dependencies or validated Blender/Three.js rendering**.


## Twelfth integration — Khronos glTF-Validator 2.0.0-dev.3.10 (CPU)

Official glTF-Validator checks the final GLB on CPU for errors in binary resources, skins, morph data, animation accessors, and glTF 2.0 schema. The installed official Node npm module is required; the skill does **not** pretend its presence and never changes or rewrites the source model. `--gltf-validate` runs on the output from Blender and on the output from glTF-Transform when optimization is selected. Unknown required extensions are blocked as not fully validated. No standalone test/report file is created.

On a network-enabled workstation: `python scripts/install_gltf_validator.py --install`

Run: `python scripts/build_with_anatomy.py --blender blender --gltf-optimize --gltf-validate`

For an existing GLB, no Blender: `python scripts/gltf_validator_worker.py --input game.glb`.

See [Khronos validator CPU bridge](references/GLTF_VALIDATOR_CPU_BRIDGE.md). Full original validator/npm runtime was NOT downloaded in this runtime because DNS is unavailable; actual official validator execution is NOT confirmed here.

## Thirteenth integration — xatlas CPU UV unwrapping (v1.5.0)

Official engine: https://github.com/jpcy/xatlas (MIT), Python bindings:
https://github.com/mworchel/xatlas-python (MIT, version `0.0.11`).

- Supplies UV coordinates for original monster muscles and body meshes lacking UVs.
- Uses native C++ CPU atlas generation from a separate Python environment, then
  maps UV islands to Blender **face loops** (corner attributes), not cloned game
  vertices. Thus rig weights, morphs and existing animations remain untouched.
- Refuses to overwrite any existing UV map, and conservatively excludes image-
  textured materials and reference/donor models.
- Synergy: PyMeshLab mesh cleanup → Instant Meshes quad LOD (if opted in) →
  Blender skinning + Rigger/Open Mocap animation → xatlas UVs → glTF-Transform
  optimization → Khronos GLB validation.

One-time CPU package setup (internet or local wheel cache required):

```sh
python scripts/install_xatlas_cpu.py --install
```

Then append `--xatlas-uv` to the existing CPU build command:

```sh
python scripts/build_with_anatomy.py --blender blender --xatlas-uv
```

An external Python interpreter may be passed using `--xatlas-python PATH`.
Optional `--xatlas-allow-noop` accepts scenes where UVs already exist.
The original animated GLB is not replaced; a new `.blend` and `.glb` are
written and semantically checked against the original clips, joints and morphs.

[Full bridge](references/XATLAS_CPU_BRIDGE.md). **In this ChatGPT runtime,
external downloads were blocked by DNS and Blender/xatlas aren't installed;
end-to-end UV unwrapping hasn't run here.** Upstream source can be cloned by
`scripts/download_xatlas_source.py` on a connected machine.


## Pillow 12.3.0 CPU PBR textures — fourteenth integration

**Actual Pillow processing on CPU.** After xatlas, selected new/simple monster
materials receive packed sRGB color and grayscale roughness PNG textures
derived from the monster's own rest-pose curvature and existing material color.
Wetness is controllable; no tiled noise or extraneous patterns. No skinned
geometry, existing character, UVs, morphs, animation or original artist images
are changed. New `.blend` and self-contained `.glb` are generated.

```sh
python scripts/install_pillow_cpu.py --install
python scripts/build_cpu_only.py --blender blender --xatlas-uv --pbr-cpu --pbr-wetness 0.35 --pbr-size 512
```

Pillow 12.3.0 was already installed in the integration environment, and a
CPU-generated texture fixture was inspected. Actual Blender and final glTF
rendering remain unverified without Blender.

See [Pillow bridge](references/PILLOW_PBR_CPU_BRIDGE.md).

## Fifteenth open-source integration — meshoptimizer / gltfpack v1.3 (CPU-only)

The **real official gltfpack CLI** is now the opt-in terminal GLB optimization stage after Blender, xatlas, Pillow PBR and (optional) glTF Transform. It preserves the original as a separate file, checks armature/skin hierarchy, joint names, morph target layouts, animation clips, UV channels, PBR material factors, embedded image contents and node hierarchy, and requires Khronos glTF-Validator before and after processing. Structural failures abort the stage.

Install the official CPU binary using the pinned-SHA-256 installer:

```sh
python scripts/install_meshoptimizer_cpu.py --dest vendor/gltfpack-v1.3
```

Then, with the Khronos Validator installed:

```sh
python scripts/build_with_anatomy.py --blender blender --meshoptimizer
```

With Pillow PBR and glTF Transform (no quantization/no compression between stages):

```sh
python scripts/build_with_anatomy.py --blender blender --xatlas-uv --pbr-cpu --gltf-optimize --gltf-mode safe --meshoptimizer
```

Use `--meshoptimizer-mode compressed` only if the Three.js game bundles the **MeshoptDecoder**; compressed output requires GLTFLoader configuration. Default safe mode does not introduce compression extensions. No geometry simplification or automatic texture recompression is enabled; a character is never replaced with an unapproved proxy.

See `references/MESHOPTIMIZER_CPU_BRIDGE.md`. **Native gltfpack was not downloaded in the current environment due to GitHub DNS failure**. The real official CLI has not been executed here; the pipeline's Python wiring is prepared and its runtime depends on installation.


## Trimesh — 16th CPU source (v1.8.0)

Added **Trimesh 4.11.1** (MIT) for real, CPU-only topology analysis of the exported monster. Its official Python package is independently installed. Trimesh reads the uncompressed GLB without altering the model, flags invalid or collapsed triangles, non-manifold connections and inconsistent winding, and warns about intentionally open surfaces. It runs **after** xatlas UV + Pillow PBR, **before** glTF-Transform/meshoptimizer, with Khronos Validator reserved for glTF schema correctness. No GPU or Blender required to audit an existing GLB.

```sh
python -m pip install 'trimesh==4.11.1' numpy
python scripts/trimesh_cpu_guard.py --input /path/monster.glb
python scripts/build_with_anatomy.py --blender blender --trimesh-audit
```

`--trimesh-strict` rejects non-manifold edges/inconsistent winding as well as degenerate triangles; open boundaries remain advisory. `--trimesh-python` selects a separate Python interpreter. Trimesh inspection does not simulate animated collisions, replace Rigger animation, or reconstruct muscle shapes.

Source: https://github.com/mikedh/trimesh ; license and pinned revision in `vendor/Trimesh-SOURCE.md`; workflow in `references/TRIMESH_CPU_BRIDGE.md`. Only original bridge code is bundled; the official Trimesh package is an external dependency.

## Manifold3D CPU — seventeenth source (v1.8.0)

[Manifold](https://github.com/elalish/manifold) `v3.5.5` is an official **Apache-2.0 CPU solid-CSG** engine with Python bindings `manifold3d==3.5.5`. It is paired with Trimesh CPU: **Trimesh checks all static mesh inputs and Manifold union output**, while **Manifold performs the actual constructive solid union**, and PyMeshLab can clean eligible source meshes beforehand. This is optional because topology-changing Boolean operations cannot automatically preserve skinned-hero weights, UVs, original shape keys and animations.

To build a separate, visible Blender sculpt reference from two or more CLOSED, unweighted, untextured triangle meshes named `MUSCLE_*`, `BODY_*`, `SHELL_*` or tagged `manifold_fuse=True`:

```sh
python scripts/install_manifold3d_cpu.py --install
python scripts/build_with_anatomy.py --blender blender --cpu-input-blend creature.blend --manifold-cpu
```

When you want specific inputs: append `--manifold-objects MUSCLE_CHEST_L,MUSCLE_CHEST_R`. The union is saved in the resulting `.blend` as **`MANIFOLD_SCULPT_REFERENCE`**, visible as a sculpt wire guide but **excluded from the game GLB**. The source character, its skin weights, muscles, materials, shape keys and animations are preserved. Use this as a 3D reference for manual sculpt/retopo; it does **not** automatically turn a mesh union into a finished rigged monster. Already skinned/textured geometry can be used as **read-only rest snapshot** for the guide, never as a replacement game mesh.

Scripts: `scripts/manifold3d_cpu_worker.py` (real upstream API), `scripts/manifold3d_blender_bridge.py` (read-only input, new `.blend` reference), `scripts/install_manifold3d_cpu.py` (pin and verify). Reference: `references/MANIFOLD3D_CPU_BRIDGE.md`. **Blender is not installed and Manifold3D wheel could not be downloaded in this environment**, so actual Boolean/Blender integration is *code only, not runtime validated*. CPU Python + local Blender are required; no NVIDIA, CUDA, paid services or cloud inference.


## SciPy CPU weight smoothing — eighteenth integration (v1.9.0)

Official `scipy/scipy` **v1.17.0** (BSD-3-Clause) now provides an actual sparse-graph skin-weight smoothing stage for **newly skinned muscle/skin meshes only**. It runs after Blender Bone Heat / proximity fallback and before morph animation, xatlas UV, Pillow PBR and GLB optimization. The scene's existing approved weights, shape keys, bone hierarchy, materials and animation clips are protected.

```sh
python scripts/build_with_anatomy.py --blender blender --cpu-input-blend /path/monster.blend --scipy-skin-smooth
```

The command needs an external CPU Python with SciPy and NumPy (`--scipy-python`), and Blender 4.5+. A valid CPU-only solver was exercised using the installed `scipy==1.17.0`; **Blender itself is unavailable here**, so no end-to-end rig/GLB validation is claimed. If the scene has only already-weighted meshes, no artist-painted weights are touched. See `references/SCIPY_SKIN_CPU_BRIDGE.md`.
