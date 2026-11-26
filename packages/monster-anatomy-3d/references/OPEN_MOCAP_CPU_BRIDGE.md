# Open Mocap CPU → Monster Anatomy 3D v1.0.0

Upstream: https://github.com/Larenju-Rai/open-mocap-blender
Git source revision: `1ec7457dad228661cbd8a1d98163e8288d3f7db5`.
Code MIT, copyright 2025 Larenju Rai; see `vendor/OpenMocap-UPSTREAM-LICENSE.txt`.

## Integration

**No GPU.** The bundled CPU-only port `vendor/open_mocap_cpu_pose.py` adapts the exact upstream design of `MathUtility.normalize_coordinates` and `PoseTracking.detect_pose`: 33 MediaPipe/cvzone pose landmarks plus 7 derived anatomical centroids (40 positions × XYZ), with optional side-camera depth. It does not vendor the original Blender UI, videos or GPU models. The official add-on only supports Blender 4.0.0 and earlier; **do not register it into Blender 4.5**. The standalone port runs with CPython 3.10, pinned cvzone/MediaPipe/OpenCV CPU packages. No CUDA, torch, NVIDIA, or model checkpoint.

`open_mocap_cpu_capture.py`: parses a real source video, preserves frame count, fills missing detections using interpolation without inventing motion, and optionally reads a synchronized side view. Exposes the same 40 joint indices as Open Mocap. The optional `download_open_mocap.py` downloads **only the pinned original source Python files**, excluding copyright-sensitive example videos; it is not required for the port. Full clone is not bundled.

`open_mocap_retarget_blender.py`: loads an already skinned `.blend` with `MONSTER_RIG` in CPU Blender 4.5+, maps known 15 body bones to MediaPipe joints (or uses explicit JSON map), derives orientation changes from the first observed video frame, creates a NEW named Action + NLA strip, reuses `rigger_monster_blender.py` to bake `ANATOMY_FLEX`/`ANATOMY_STRETCH` muscle morph tracks, and validates geometry/UV/weights/material signatures + the previously named NLA clips before accepting a game GLB. Existing original rig and animations stay in source and new scene.

The character never changes. The video provides only movement; no new mesh, morphology, textures or hero identity. Bone rotations are approximate from 2D tracking; world root movement, contact-locked feet, full finger motion and attack intention cannot be reliably inferred.

## CPU build and optional mocap

Default CPU build (no motion video or new packages):

```sh
python scripts/build_with_anatomy.py --blender blender
```

With a real video of a walking person (requires optional CPU dependencies):

```sh
python -m pip install -r requirements-open-mocap-cpu.txt
python scripts/build_with_anatomy.py --blender blender --mocap-video walk.mp4 --mocap-clip MOCAP_WALK
```

Use `--cpu-input-blend original.blend` to retarget the same existing monster. `--mocap-side-video side.mp4` accepts exact same frame count and FPS only. `--mocap-mirror` flips lateral orientation. `--mocap-landmarks captured.json` skips video capture. `--mocap-bone-map map.json` accepts explicit `{ "bone_name": [source_landmark_index, target_landmark_index] }`; for unknown rigs mappings are mandatory rather than guessed.

Direct call without rebuilding:

```sh
python scripts/open_mocap_cpu_worker.py --blender blender --blend monster_cpu_animated.blend --video walk.mp4 --output-blend walk.blend --output-glb walk.glb --clip MOCAP_WALK
```

Outputs include a new `.blend`, a new `.glb` and, for video inputs, the tracked 40-landmark JSON. The default path is still entirely CPU-only and needs neither video libraries nor external downloads.

## Safety and requirements

- Blender 4.5+ is CPU-only, as are the OpenCV/MediaPipe inference wheels for this path. The upstream add-on is not loaded into Blender 4.5.
- Original source image, monster character, mesh/weights, skeleton, materials and existing Action/NLA names remain intact; no deforming the image as a sprite.
- Every new clip is opt-in by supplying a video or landmarks file. Game actions remain triggered only by player/game input.
- Videos belong to their owners; no third-party video assets are redistributed.
- This is a real source-derived CPU pose tracker and Blender retarget algorithm, not neural image-to-3D, fully automatic animator-grade retarget or photorealistic character creation.
- The integration here was syntax-checked; actual motion extraction and Blender export require video + optional CPU dependencies + installed Blender and have not been exercised in this runtime.
