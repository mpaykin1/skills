# Z-Anatomy ↔ MyoGeneratorRemix — v0.2

Source: <https://github.com/Z-Anatomy/Models-of-human-anatomy> at commit `d14fa54355a3b484cefd08c33f6e18526d9aea85` (2026-11-22).

The Blender application template `Z-Anatomy.zip` is **not** a rigged monster. It is an atlas of human anatomy including many named anatomical mesh objects. The actual Z-Anatomy library is large (86,734,957 bytes, ~83 MiB) and is downloaded on a networked Blender workstation, not bundled in this plugin.

## Verified source API and integrity
- `scripts/download_z_anatomy.py`: downloads pinned original `Z-Anatomy.zip`, `License.txt`, `Readme.md`, checks exact expected byte sizes and git blob SHA-1s (Git tree IDs, not ad hoc file hashes), writes provenance metadata.
- `scripts/z_anatomy_bridge.py`: reads *object/mesh names* from Z-Anatomy's `startup.blend` in application-template zip using `bpy.data.libraries.load()`. Does **not** run untrusted addon code, and does **not** append atlas meshes to the commercial creature.
- Builds 30 bilateral / midline anatomical muscle attachment pairs based on **original monster rig rest-pose geometry**. The anchor positions are **approximations**, not medically verified attachment points.
- Every pair comprises two real Blender mesh marker objects `ZA_ORIGIN_*`, `ZA_INSERTION_*` parented to named rig bones. The markers are interactive selection surfaces for MyoGeneratorRemix's origin/insertion UI.
- `scripts/myo_select_anchors.py` sets the MyoGeneratorRemix `origin_object`, `insertion_object` and `muscle_Name` properties for one selected pair. It does not auto-create muscles, as registration/operator API has not been runtime-verified here.
- Full model export remains **the original creator's GLB**, without licensed atlas geometries or helper markers; the enhanced `.blend` contains the editable guides.

## Run once with network

```sh
python scripts/build_with_anatomy.py --blender blender --output-dir build/monster
```

Requires Blender >=4.2; the wrapper fetches the MyoGeneratorRemix add-on and Z-Anatomy atlas, generates the creature blockout, exports GLB, constructs atlas-to-Myo origin/insertion markers, saves `monster_with_anatomy_guides.blend` and `muscle_anchors.csv`.

Open `monster_with_anatomy_guides.blend`; install fetched MyoGeneratorRemix in Blender (Preferences → Get Extensions → Install from Disk). In Blender's Text Editor run `select_pair('trapezius_L')` after loading `myo_select_anchors.py`, then use the addon Origin/Insertion tools to sculpt the actual muscle paths and generate muscle meshes. Repeat across attachment CSV.

## License and commercial safety
Z-Anatomy `License.txt` declares CC BY-SA 4.0 for its code/models. Original BodyParts3D credit requires CC BY-SA 2.1 Japan attribution. Some included anatomy meshes are independently CC BY-NC-SA 4.0 (inner ear) or CC BY-NC 4.0 (kidney). A project using these models in commercial games cannot assume rights to redistribute them. The bridge imports **no atlas geometry** into the game GLB. Attribution & share-alike requirements apply if separately using CC BY-SA atlas assets. Preserve notices and review each model's provenance.

MyoGeneratorRemix is a separate GNU GPL-based Blender add-on. No third-party GPL code is copied into the plugin. Creating model outputs with Blender tools is a separate licensing question from distributing original source.

## Current limits
- Without Blender and original atlas binary, only source and static integration can be verified; no Blender runtime verification is claimed.
- Z-Anatomy matches are best-effort by anatomical name; archive internal blend format or object naming may vary.
- The generated bridge is **anatomy-guided rigging preparation**, not full automatic anatomy reconstruction; requires real artistic endpoint selection in MyoGeneratorRemix.
