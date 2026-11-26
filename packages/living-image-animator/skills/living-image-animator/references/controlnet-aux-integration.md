# ComfyUI ControlNet Aux ↔ Living Image Animator (v0.12)

Source: https://github.com/comfyorg/comfyui-controlnet-aux (upstream extension also at https://github.com/Fannovel16/comfyui_controlnet_aux). It supplies pose-preprocessor nodes DWPose, OpenPose, AnimalPose. This plugin supplies a **real format/API adapter**, not the ComfyUI application, pretrained weights or automatic complete pose artwork.

## Required workflow

1. Obtain an actual **sequential video/image batch** and run DWPose/OpenPose for humans, AnimalPose (AP-10K) for cats, dogs or other supported animals in a separately installed ComfyUI with comfyui-controlnet-aux. The extension exposes `openpose_json` in outputs, including `/history/<prompt_id>` and saved keypoint JSON. Reference-only: static single-frame poses, repeated cels and inferred body keypoints cannot substitute for motion.
2. Supply `controlnet_aux_pose` in each appropriate actor of `scene.json` (example below), pointing to its real exported JSON, or to the local ComfyUI prompt history. Explicitly set schema and source fps. A pose frame must have exactly one identified person or animal; tracking among several is **not** automatically solved and ambiguous frames must be segmented into individual guides before use.
3. The adapter `scripts/controlnet_aux_bridge.py` parses real `pose_keypoints_2d` (OpenPose 18 / BODY25) or AP-10K `animals` 17-keypoint arrays, rejects low-confidence and missing crucial joints, validates normalized/pixel coordinates, continuity and meaningful gait. It never fabricates absent joints, image frames or actor identities.
4. The mandatory `scripts/controlnet_aux_delivery.py` invokes the existing untouched `unified_delivery.py` (which retains MMPose, DeepLabCut, Krita/OpenToonz/Pixelorama, foot contact and full authored cels) only after validating each ControlNet Aux guide. The JSON sources, normalized guides and measurements are included in the existing asset ZIP. The final renderer still blocks static actors, tiny pose amplitudes, missing world paths, slide/teleport, inadequate foot contacts and false GIFs.
5. Use these reference joint tracks to author genuinely new 24fps whole-character RGBA poses in Krita/Pixelorama/OpenToonz; then pass their cels through the normal renderer. Reference points do not themselves create those cels. No deformation of any approved character image is permitted.

## Input to add under `actors[]`

Human example (one actual batch of OpenPose 18 pose JSON frames):

```json
"controlnet_aux_pose": {
  "schema": "openpose18",
  "json": "references/human_walk.openpose.json",
  "fps": 24,
  "confidence": 0.3
}
```

Alternative BODY25 uses `"schema":"body25"`; animal uses `"schema":"ap10k"`, with `"json":"references/cat_run.ap10k.json"`. Optional `"history_json":"references/comfy_history.json"` and `"node_id":"37"` supports saved ComfyUI history outputs containing `openpose_json`. If the history contains multiple prompt IDs, also supply `"history_prompt_id":"<exact prompt-id>"`. To read a **live locally running** ComfyUI history, use `"prompt_id":"<id>"`, `"node_id":"37"` and CLI `--comfyui-url http://127.0.0.1:8188`. The URL is restricted to local HTTP loopback; nonlocal URLs are forbidden. No network calls occur for file-backed JSON. No ComfyUI executable is required for already exported JSON.

### Supported actual JSON structure

Human `[{"people":[{"pose_keypoints_2d":[x,y,c,...]}],"canvas_width":512,"canvas_height":512}, ...]`, with 18 or 25 keypoints (one actual person per frame). Animal `[{"version":"ap10k","animals":[[[x,y,c],...17]] ,"canvas_width":512,"canvas_height":512}, ...]`. For both formats one **different-time frame** of keypoint data per batch item is mandatory, minimum 12 frames. `openpose_json` may wrap the JSON array as a single string as emitted by the extension. Reject multi-target frames to prevent silent identity swaps.

## Final entrypoint

```bash
python scripts/controlnet_aux_delivery.py source.png --scene scene.json --out output --seconds 48 --fps 24
```

Add `--pixelorama` or `--opentoonz` only when the source clips need those executables. Original DeepLabCut/MMPose references still work if present, and are checked independently. A failure in any stage stops the output. Source-specific model checkpoint licenses apply; neither source weights nor pretrained models are bundled.

**Known boundary:** Motion reference != guaranteed new art. ComfyUI-ControlNet Aux creates pose guidance and does not itself produce reliable complete identity-locked walk/run sprites from a flattened illustration. New pose images still need a separate authored generation/drawing stage and visual approval.
