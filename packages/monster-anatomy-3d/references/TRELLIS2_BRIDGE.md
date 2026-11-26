# TRELLIS.2 + Monster Anatomy 3D — fifth upstream integration

Upstream: https://github.com/microsoft/TRELLIS.2
Pinned Git commit: `75fbf0183001ed9876c8dbb35de6b68552ee08bd` (main verified Nov 2026)
Copyright Microsoft Corporation; original model and code MIT. Check separately licensed dependencies: nvdiffrast and nvdiffrec.
Model: `microsoft/TRELLIS.2-4B` (Hugging Face, auto-download when first invoked with access).
System prerequisites from official README: Linux, NVIDIA GPU with 24 GB VRAM minimum, CUDA toolkit ~12.4, Conda; deployment is not in a normal browser or mobile game.

## Why / actual interoperable data

1. **TRELLIS.2** `scripts/trellis2_generate.py --input drawing.png --output draft.glb --repo vendor/TRELLIS.2 --pipeline 512` uses the official real `Trellis2ImageTo3DPipeline.from_pretrained`, `pipeline.run`, O-Voxel `to_glb` to create a textured static mesh (base color, metallic, roughness and opaque alpha unless manually configured). Model weights download on a CUDA workstation. Renderer not run in the skill archive.
2. **Blender 4.5** `scripts/trellis_surface_bridge.py --blend prior.blend --trellis-glb draft.glb --output-blend new.blend --output-json nearest_anchors.json` actually imports glTF geometry/materials, uniformly fits its height to the existing rig and stores it as `TRELLIS_REFERENCE_NON_EXPORT`. No fake plane or primitive substitution. `--rotate-z` lets the sculptor correct front-facing orientation.
3. **Z-Anatomy** anatomy markers are compared in 3D to the generated surface via KDTree nearest points and per-anchor distances; these are *hypotheses*, not recovered biological origins/insertions. They are exported as `trellis_surface_anchors.json` for review.
4. **MPFB2** stays reference-only; use its donor rig and proportional data as anatomical scaffolding. TRELLIS2 output is not reclassified as human or secretly swapped for MPFB.
5. **MyoGeneratorRemix** muscle objects are separately sculpted and skinned to the original `MONSTER_RIG`. TRELLIS output is visible as a shape/texture reference in editable `.blend`; it is intentionally *not* auto-rigged, so retopology/weight transfer are explicit subsequent processes. No GLB replacement unless actually skinned and evaluated.

## Installation

`python scripts/download_trellis2.py --dest vendor/TRELLIS.2` downloads the exact official commit with recursively initialized submodules, checking SHA and expected source paths. The source is not the 4B checkpoint and does not include the CUDA environment.

Inside official checkout on a Linux NVIDIA workstation: `. ./setup.sh --new-env --basic --flash-attn --nvdiffrast --nvdiffrec --cumesh --o-voxel --flexgemm`. Inspect the third-party installer before running it, and obey separate dependency licenses. Model downloads require storage and network access. Generate using this installed Python, e.g. `conda run -n trellis2 python scripts/trellis2_generate.py --input assets/monster_reference.png --output build/monster/trellis_draft.glb --repo vendor/TRELLIS.2`.

Full orchestration: `python scripts/build_with_anatomy.py --blender blender --trellis-glb build/monster/trellis_draft.glb --output-dir build/monster`. If CUDA is already installed: `--trellis-input assets/monster_reference.png --trellis-python /path/to/trellis2/python`.

## Quality and truth contract

- One image leaves back, limbs and occluded joints guessed. Preserve character identity; compare the 3D generated draft to front/side reference views. No claim of final anatomical correctness.
- TRELLIS2 is static, not an actual rigged animated creature. Avoid passing raw high-poly reconstructed mesh to game GLB as if it were a skinned muscle.
- Neither Blender nor NVIDIA GPU nor model weights are bundled. Test CUDA inference/Blender stage before stating they ran. If network blocked, source checkout not present; the vendor folder contains only Microsoft official example and MIT notice, plus reproducible pinned downloader.
- Keep raw generated GLB and original reference for auditing silhouette; do not repaint or replace approved design with generic human donor.
