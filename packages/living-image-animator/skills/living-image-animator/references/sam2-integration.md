# SAM 2 ↔ Krita / Pixelorama / OpenToonz — original-pixel image/video masks

**Upstream:** https://github.com/facebookresearch/sam2 (SAM 2 code and model weights Apache-2.0; inspect separately bundled third-party dependencies). The Python adapter `scripts/sam2_bridge.py` calls the official `build_sam2` + `SAM2ImagePredictor` image API and `build_sam2_video_predictor` tracking API. It does **not** fabricate masks if the model, PyTorch or weights are missing.

## Purpose, boundaries

SAM 2 segments prompt-selected **already visible subjects**, including people, horses, carriages and train windows, into stable RGBA authoring layers and L masks. Krita paints missing poses, Pixelorama and OpenToonz author actual 2D frame cels; DeepLabCut and MMPose handle motion references. **SAM 2 is not an animation generator.** Reference-video frames are not interchangeable with hand-authored full-pose sprites and cannot be used to bypass silhouette, joint, foot-contact and no-deformation gates.

## Example scene additions

For an original source 1024×768:

```json
{
  "sam2": {
    "model_cfg": "configs/sam2.1/sam2.1_hiera_s.yaml",
    "checkpoint": "/local/model/path/sam2.1_hiera_small.pt",
    "device": "cuda", "max_video_frames": 120
  },
  "actors": [{
    "id": "horse_01", "role": "animal", "box": [120,170,220,260],
    "sam2_prompt": {
      "box": [125,185,334,420],
      "points": [{"xy":[200,250],"label":1},{"xy":[320,210],"label":0}],
      "min_score": 0.0
    },
    "sam2_video_prompt": {
      "video": "references/horse.mp4",
      "box": [92,105,302,382],
      "points": [{"xy":[180,190],"label":1}]
    },
    "clips": ["... authentic Pixelorama/Krita/OpenToonz action sequences ..."]
  }]
}
```

This is a **structural excerpt**. Every actor still needs 2+ real, complete separate full-body action clips, stable `inventory.actors` and original-size action registration. For a source image, `sam2_prompt` produces `source_mask` replacing the previous scene mask (an existing mask is not mandatory for this actor). Point coordinates/box refer to the original source image, NOT the sprite crop. For `sam2_video_prompt`, point and box coordinates refer to the **original resolution of the reference video**. A single reference video is supported per scene; use multiple scenes for multiple video inputs. Non-SAM2 actors keep their original masks unchanged.

## Pipeline

1. Run the same `scripts/unified_delivery.py ...` command as before. It now calls SAM2 **before** Krita/Pixelorama/OpenToonz pose compilation.
2. `sam2_bridge` loads genuine checkpoint via the official model API, checks prompt geometry, segments the original image, requires ≥95% of mask inside the actor's declared crop, blocks empty/excessively large/overlapping subject masks, and writes the **full-canvas** grayscale mask plus **source-derived** transparent original-size crop. Only original source pixels are present. Segmentation data is stored in `sam2_segmentation` metadata.
3. Optional real video tracking: OpenCV decodes JPEG frames, official SAM2 video predictor adds independently specified actor prompts and propagates over up to 240 frames; every named actor must have an actual mask for every frame. Exports numbered full-frame masks, not generated animation cels. Uses `sam2_video_prompt.video` relative to original scene directory.
4. The compiled scene is passed unchanged into `krita_bridge`, then OpenToonz `tcomposer`, Pixelorama `.pxo` and genuine `pixelorama_handoff`. The existing **strict** pose/gait/identity and GIF/ZIP validator remains in force. Generated SAM2 masks and transparent reference layers are kept in the ZIP under `project/animation_sources/inferred/compiled_sam2_scene/sam2_generated/`; tracked video masks under `.../inferred/sam2_generated/video_masks/`.
5. Retain original source project files, cropped reference layers, editable art sources and contact landmarks. Refine incorrect masks/prompts manually: the model can merge horse+human or omit limbs, particularly for tiny pixel characters.

## Installation dependency

`sam2` is NOT bundled. In a GPU-capable environment install official SAM 2 + matching PyTorch, and download an official SAM 2.1 checkpoint; set `scene.sam2.checkpoint` or the `SAM2_CHECKPOINT` environment variable. PyTorch and model licenses/availability must be verified; do not auto-download or run arbitrary weights. Only when model + checkpoint are present can a SAM2-generated mask be called real. Without these dependencies the animation task fails closed if any SAM2 prompt is requested. Existing scenes without SAM2 prompts remain supported.

## Validation requirements

- Every actor ID stable; humans and horses separated when painted as separate entities.
- Every mask corresponds to the correct source image resolution and a real prompt; >12% overlap relative to smaller subject mask is blocked (except negligible sub-15-pixel overlaps).
- No numerical scores or mask count certify faithful artwork; visually inspect small legs, bridles, reins, weapons and occlusions. Fix source mask when incomplete.
- SAM2 never changes exported character pose RGB pixels and never manufactures 24fps character movement from a still or video mask.
- Fail closed for missing checkpoint/module, invalid pose/art, segmentation mismatches, missing frame tracking, frozen characters, feet sliding, poor clip continuity or unmatched cast.
