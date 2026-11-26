# Blender Grease Pencil v3 × Godot × Living Image Animator — native 2.5D

Blender upstream: https://github.com/blender/blender (GPL). GPv3 API changed in Blender 4.3; require Blender 4.5 LTS or Blender 5.x for native scene building. Official docs: https://docs.blender.org/api/4.5/bpy.types.GreasePencilDrawing.html and https://docs.blender.org/manual/en/4.5/advanced/command_line/arguments.html . Blender is NOT bundled. A generated Python scene builder is not itself a `.blend`.

## Integrated delivery

**Only full validation path:** `scripts/blender_delivery.py` calls `godot_delivery.py` first. Thus ControlNet Aux reference validation, SAM2 masks, human MMPose, DeepLabCut quadrupeds, Krita, OpenToonz, Pixelorama, no-deformation full-cel gate, real locomotion, and Godot 4 export remain required. Only AFTER verified original `living_scene.gif` + `living_scene_assets.zip` + `living_scene_godot.zip` exist, `blender_bridge.py` exports matching original asset bytes into Blender's source scene kit. The optional real Blender executable runs `blender_build_scene.py` via `--background --factory-startup --python-exit-code 3 --python ... -- PATH`, saving an actual `.blend`. Do not claim the binary build worked if no Blender executable was run.

- All original `project/inputs/<clip frame PNG>` source cels stay byte-exact in `sprites/<stable actor ID>/0000.png...`, played by Blender Image Texture **sequence nodes** at native 24+ fps; no mesh skinning of living characters, no fake poses, no optical flow.
- `scene['actors']`, full-cel action order, phase offsets, original `box`, and `locomotion.path` are copied exactly from the validated scene. Blender keyframes only the **root plane location** (at original world positions) and uses the existing cubic trajectory interpolation; painted original sprites are not transformed or deformed.
- `background_clean.png` is placed as a full-canvas emissive plane behind the characters. Full-canvas artist-authored PNG depth plates from `blender.layers` (or previous `godot.layers`) are placed on separate planes at genuine different Blender Y-depths for 2.5D occlusions. Missing source alpha plates reject export. The source camera is orthographic/front-on by default to preserve exact pixel composition; do not advertise optical parallax unless a separately authored camera shot/perspective has been tested.
- A real editable native **Grease Pencil v3** object is created. If `blender.gp_strokes` is supplied, author-defined real pixel-space stroke points and exposure keyframes become GPv3 `drawing.add_strokes` geometry. If no authored ink paths exist, create a blank editable Grease Pencil layer — never invent/trace outlines from the raster automatically or claim they animated. Ink can be further painted in Blender manually.
- Godot's original `NavigationAgent2D` and `CharacterBody2D` remain inside the Godot project; Blender's scene is an **editable cinematic/2.5D authoring project**, not a Godot runtime or a navigation simulator. Neither executable is bundled.

## Optional original scene metadata

```json
{
  "blender": {
    "pixels_per_unit": 100,
    "layers": [
      {"name":"foreground_tree","png":"layers/foreground_tree.png","z_index":40,"visible":true}
    ],
    "gp_strokes": [
      {"id":"ink_outline_01","rgba":[0.09,0.08,0.13,1],"width_px":2,"z_index":41,
       "keyframes":[
         {"frame":1,"points":[[10,15],[20,20],[28,18]]},
         {"frame":13,"points":[[12,15],[21,21],[30,19]]}
       ]}
    ]
  }
}
```

These points are painted/annotated artist data. Pixels `[x,y]` are from the original image top-left. `z_index` controls depth and occlusion (higher -> closer). Authored GP frame numbers range `1..seconds*fps`. Each GP stroke needs at least two valid points and a real color. `blender.layers` overrides inherited `godot.layers`; they must be source-registered transparent PNG plates in `project/inputs/`, as already gathered by the previous Godot stage. Grease Pencil keyframe holds do not count toward the required character animation, which is always from full-cel painted PNGs.

## Commands

```bash
python scripts/blender_delivery.py source.png --scene scene.json --out output --seconds 48 --fps 24 \
 --opentoonz /path/to/tcomposer --pixelorama /path/to/Pixelorama \
 --godot /path/to/godot --blender /path/to/blender
```

Optional editor binaries are required only for clips using those native projects. `--godot` and `--blender` explicitly request an actual native execution check. Without `--blender`, the exporter creates a reproducible Blender **source kit** containing `build_blender.py`, the validated PNG sequences, 2.5D scene definition and original JSON, **but not a fabricated `.blend`**. A generated `.blend` is included only after Blender actually runs successfully. Deliver `living_scene_blender.zip` and embed the same kit in `living_scene_assets.zip` at `project/blender/living_scene_blender.zip`.

## Release blockers

Missing actor, low silhouette/joint amplitude, absent painted cels, wrong dimensions/alpha, identity drift, missing masks, broken world path, ZIP corruption, malformed depth/GP coordinates, executable error or missing actual native output => block the affected result and do not claim a finished real Blender project. This stage never bypasses previous validators or substitutes GPU render for authentic approved animation.
