# ComfyUI ↔ Krita / OpenToonz / Pixelorama — authentic 2D cel candidates

Official upstream: https://github.com/Comfy-Org/ComfyUI (GPL-3.0, subject to license terms). API docs: https://github.com/Comfy-Org/docs/blob/main/development/comfyui-server/comms_routes.mdx ; official example: https://github.com/Comfy-Org/ComfyUI/blob/master/script_examples/basic_api_example.py . This plugin is an independently written **REST API client**, not a copy of the ComfyUI executable or models. The ComfyUI application, compatible workflow nodes and model checkpoints must be separately installed. Some workflows call paid remote model services; use only free local OSS nodes/models as user requires.

## Why this integration exists

SAM 2 extracts original-subject masks, MMPose measures real human motion, DeepLabCut measures animal motion, and ControlNet Aux measures 2D pose references. None can draw independent stable 24fps sprites. ComfyUI can run user-selected *local* generative workflows to propose **genuinely different full-character images** conditioned on those reference assets, without the adapter deforming a static bitmap. Krita, OpenToonz and Pixelorama receive its output as editable original-pixel RGBA PNG frames and contact sheets for deliberate correction. Only genuinely approved, annotated complete cels may enter the existing full-scene GIF/ZIP renderer.

## Source scene fields (candidate stage only)

```json
{
  "actors": [{
    "id":"cowboy_01", "role":"human", "box":[80,100,96,120],
    "clips":[{
      "action":"fire", "comfyui_candidate": {
        "workflow_api_json":"workflows/cowboy_fire.api.json",
        "output_node":"9", "frame_count":24
      }
    }]
  }]
}
```

A workflow must be real ComfyUI **API-format node-ID JSON**, exported by the author from ComfyUI, with one specified output node saving **exactly `frame_count` full RGBA PNGs**, with canvas dimensions equal to the actor `box` width and height and transparent background. No model weights or workflow are invented. Reference image / pose / mask must be explicitly authored as graph inputs and genuinely present on the running ComfyUI server; this bridge does **not** automatically guess or inject a ControlNet graph. The output node must be a persistent SaveImage-like output (not `PreviewImage`). No API secrets are accepted.

Run `python scripts/comfyui_pose_candidates.py --scene scene.json --out output --comfyui-url http://127.0.0.1:8188`. The script talks only to localhost `/prompt`, `/history/{prompt_id}`, `/view` with strict no-redirect HTTP, validates authentic output node/frame count, RGBA transparency, original dimensions, 8+ unique poses, and rejects frozen triplets. No interpolation, no skeleton part rotation, no optical flow, no crop-resize, no generated inbetweens by the adapter. It writes `comfyui_pose_candidates.zip` with:

- `poses/<actor>/<clip>/frame_NNNN.png` — exact ComfyUI output PNG bytes, one full character per frame
- `opentoonz_levels/<actor>/<clip>/<actor>.NNNN.png` — exact byte copies, numbered for import as image level
- `pixelorama_import/<actor>/<clip>.png` — grid of same original RGBA cells for slicing in Pixelorama
- `workflows/<actor>/<clip>.json` and `manifest.json` — validated source graph, frame ordering, source pixel SHA-256, ComfyUI prompt ID and authoritative `CANDIDATE_ONLY` status

The clip output can be manually retouched in Krita (new `.kra`), OpenToonz (`.tnz`), or Pixelorama (`.pxo`). Use the original source character's face, outfit, perspective, identity and limb/contact/reference notes, then add **manual genuine per-frame `joints` markers** (`root` + ≥2 relevant anatomical points) and `support` annotations where running/walking. For horses use 4 actual hoof contacts. Only at that point replace `comfyui_candidate` with the normal existing `krita_sequence` / `opentoonz_scene` / `pixelorama_project` / authored `frames` schema, preserving the unaltered pose quality gates. Run original `scripts/blender_delivery.py` or `scripts/godot_delivery.py` (or `scripts/unified_delivery.py` for GIF/ZIP only), never bypass `pose_sequence_delivery.py`.

## Strict limitations

- *Candidate generation is not animation completion*. Do not label a candidate ZIP as a complete animated GIF/asset release or assert 95–100% anatomy, character identity, continuity or style. The models can change faces, clothes and anatomy. Human visual review and original full-pose validation remain mandatory.
- ComfyUI generated images are distinct generative cels, **not automatically identity-locked**. Source identity, realistic contact, loop seam and smooth high amplitude must be confirmed in final artwork.
- Missing ComfyUI runtime, invalid graph, no weights, unavailable custom node, JPEG/opaque or incorrect-size images, frame mismatches, wrong IDs and network redirection all block candidate export.
- This adapter does not download ComfyUI itself, generate paid API calls, install checkpoints, synthesize full-figure poses without a real model, extract SAM 2/MMPose tracks or manipulate original sprite geometry. This is an integration of their independently generated assets through user-supplied workflow graphs.
