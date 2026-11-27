# BLOCKWILD Evolution 0.7 — Living Light Garden v17

This is a **source-preserving addition** to the user's local BLOCKWILD v16 autonomous HTML. The original user-provided Unity ZIP is not redistributed. The 3D garden props are new explicitly procedural **48 × 48 × 64 occupied RGBA source volumes**. A CPU renderer bakes their projected images and metadata for the existing **Canvas2D artistic view**. This is NOT a full 3D WebGL renderer of those assets and NOT recovered original Unity meshes.

## Interoperability

- **Voxel Game Creator / Blender Model Animation Enhancer**: deliver authorized watertight `GLB` or a voxel occupancy grid `uint8[y,z,x]`, plus palette and provenance. Convert static geometry to a common `stack.json`/RGBA slice set. Do not sample/bake rigged motion into one pose.
- **META GAME FUSION + Sprite Stacking Grunge**: `RGBA` layers and `size`, `base`, `layers`, optional `surface_voxels`; keep alpha silhouette. The v17 alpha-silhouette ground-shadow adapter adds soft depth without touching the geometry or collision physics.
- **Hero Animator / Living Image Animator**: use the already approved, consistent eight-view five-pose hero and NPC atlases. v17 NEVER replaces these 160 frames. Seven independently moving previously authored butterfly projections are drawn using the same original asset family, without a second RAF.
- **Voxel Atmosphere Engine / Game Style Forge**: share one existing animation clock, the same `royalP(x,z,y)` world projection, ambient sun light and the water plane coordinates. No competing composer, scene root, movement loop or remote CDN.
- **BLOCKWILD Visual Benchmark**: compare actual aligned screenshots in 390×844/844×390, with a fixed camera/seed/time and the user's portrait/landscape references. The three-channel Lab histogram CDF distance captures only palette differences; Laplacian variance captures edge detail; neither measures artistic beauty or actual recovered Unity fidelity.
- **Skill Nexus**: consume reproducible full-HTML artifacts and source hashes, not invented visual PASS statuses.

## Reproducible build

Dependencies: Python, NumPy, Pillow, SciPy if required by the base volume renderer. The game HTML itself adds none. The `build_v17_volumes.py` script imports **only** its co-located `build_sunlit_volume_sprites.py` and `build_v16_volume_props.py` geometry functions.

```bash
python skills/blockwild-evolution/scripts/build_v17_volumes.py --out /tmp/v17_assets.json
python skills/blockwild-evolution/scripts/assemble_v17.py --base BLOCKWILD_v16_ROYAL_VOLUME_GARDEN_OFFLINE.html --assets /tmp/v17_assets.json --out BLOCKWILD_v17_LIVING_LIGHT_SPRITE_STACKING_OFFLINE.html
```

The assembler matches an explicit v16 insertion marker and rejects absent/ambiguous base files. It never modifies the source base HTML. For local art-only Chromium comparison, add `--probe` with `--base` set to the v16 art probe.

## Measured evidence boundary

Full v17 file size 53,770,363 bytes; the current build loads **193/193** sprite assets in Chromium with both mobile orientations, arrow-key movement and the source-world toggle. Original v16 had 189. Native original-world **WebGL2**, actual original Unity Texture2D/Mesh asset extraction and source chunk loading behavior are *not* proven by this art-mode test. Required next step: original Mesh/Texture2D extraction via AssetRipper/UnityPy on a permitted host, then physically genuine volumetric sprites with normals, true sun occlusion and renderer verification.

User references: given original JPG portrait and GIF landscape. A pixel 1D Lab CDF metric with weights L=.55,a=.25,b=.20, independent histograms at normalized 300×500 computes palette distances: portrait 0.052654→0.050224 (**4.615% distance reduction**), landscape 0.088834→0.088441 (**0.443% reduction**). Mean relative reduction 2.529% — NOT general graphical-quality improvement. Soft shadows reduced Laplacian-variance sharpness; this is expected and must not be silently reported as improvement in micro-detail.
