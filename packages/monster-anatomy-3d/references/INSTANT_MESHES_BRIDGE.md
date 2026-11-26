# Instant Meshes v0.6 — retopology without losing monster identity

## Why this is part of the anatomy pipeline

The 5 existing systems create a complex author-controlled monster:
MyoGeneratorRemix supplies individually sculpted muscle bellies; Z-Anatomy
supplies anatomical anchor references; MPFB2 supplies a *non-exported* donor;
TRELLIS.2 supplies a *non-exported* static surface draft; Blender creates and
animates one `MONSTER_RIG` with flex/stretch corrective shape keys.

**Instant Meshes** is the sixth open-source component, running after muscle
sculpt/animation. It creates lighter, field-aligned polygon meshes for the
real animated monster WITHOUT replacing the silhouette with a proxy. It does
**not** transfer rig weights, skinning, UV maps or morphs by itself. Our Blender
adapter implements those transfers and refuses unsafe results.

## Architecture

1. `scripts/download_instant_meshes.py` retrieves a pinned official Git checkout,
   including nested submodules, and builds `Instant Meshes` with CMake.
2. `scripts/instant_blender_bridge.py --phase prepare` exports raw local-space
   rest coordinates of eligible game meshes only. Neither MPFB donor nor atlas
   nor TRELLIS static references is used as a replacement game mesh.
3. `scripts/instant_meshes_worker.py` invokes official CLI `--deterministic
   --rosy 4 --posy 4 --faces N --crease 48 --output out.obj in.obj` per part.
4. `scripts/instant_blender_bridge.py --phase finish` projects reduced topology
   back onto the *original* mesh surface, reconstructs vertex-group weights and
   Blender armature modifiers; copies material index, UV mapping, corrective
   shape-key geometry and morph NLA actions/clips to the LOD.
5. `.blend` retains original full-resolution game meshes (hidden and marked as
   backup), plus newly animated meshes tagged `IM_LOD_...`. Only the LOD meshes,
   remaining original small meshes, and `MONSTER_RIG` are selected for GLB.
6. If distances, bounding box, source armature, shape keys or NLA clips fail
   to survive, the batch fails explicitly; the original `.blend` and `.glb`
   remain untouched and usable.

## Single action

Use the integrated pipeline: 

```bash
python scripts/build_with_anatomy.py --blender blender --instant-retopo --instant-ratio 0.4
```

If the official binary already exists, avoid network/build with:

```bash
python scripts/build_with_anatomy.py --blender blender --offline \
  --instant-retopo --instant-bin '/absolute/path/to/Instant Meshes'
```

When a prepared `.blend` already exists, directly run:

```bash
python scripts/instant_meshes_worker.py --blender blender \
  --instant-bin '/absolute/path/to/Instant Meshes' \
  --blend monster_blender_sculpt_ready.blend \
  --output-blend monster_instant_retopo.blend \
  --output-glb monster_instant_retopo.glb --ratio 0.4
```

## Hard limitations

- **No rigging from Instant Meshes**; transfers are Blender-side approximations,
  not deforming finite element physics.
- The geometric transfer uses surface projection/barycentric interpolation.
  Complex UV seams and texel alignment may need artist correction.
- Extremely thin claws, open surfaces, self-intersections and non-manifold
  tissues can fail remeshing, and should be retained unmodified.
- Dense shape-key meshes may produce large GLBs; compare the actual GLB and
  rendered animation before release. Do not report ">50% savings" without files.
- Upstream source/binaries not contained in the plugin ZIP, and Blender 4.5
  is not installed in ChatGPT's environment. Installation and runtime remain
  pending without network access. Never claim tested Blender runtime or a
  new game link without launching one.
- Preserve source BSD notice when distributing Instant Meshes binaries; Blender
  and MPFB code are GPL, while MPFB base assets are CC0; Z-Anatomy model rights
  must be reviewed independently for commercial games.
