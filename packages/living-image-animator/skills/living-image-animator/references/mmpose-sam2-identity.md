# MMPose × SAM 2: identity-locked human motion reference in crowded 2D/2.5D footage

Sources: https://github.com/open-mmlab/mmpose and https://github.com/facebookresearch/sam2 . MMPose v1 uses `MMPoseInferencer` and yields a generator for video frames. SAM 2 video predictor yields an individually tracked mask for each prompted object ID. Both software stacks and model weights are **external**, never bundled or silently downloaded.

## Problem solved

Previously `mmpose_bridge.py` refused any frame containing more than one person, so train ambushes, crowds and mounted soldiers could not be processed as human gait references. The new `mmpose_sam2_bridge.py` uses the **original SAM 2 per-actor mask at the corresponding source-video frame** to select a single COCO17 MMPose pose from any number of human detections. It does not apply MMPose human joints to horses or other animals. Quadruped motion remains DeepLabCut.

## One actor, one shared video

Declare BOTH in the original `scene.json` actor:

```json
{
  "id":"rider_01", "role":"human",
  "sam2_video_prompt":{
    "video":"references/train_ambush.mp4",
    "box":[160,70,280,310],
    "points":[{"xy":[200,160],"label":1}]
  },
  "locomotion":{
    "mode":"walk",
    "mmpose_video":"references/train_ambush.mp4",
    "path":"... genuine closed source-relative route ..."
  }
}
```

This is a STRUCTURAL EXCERPT, not a complete playable scene. Actors still require original pose frames, mask/box, registered joints and genuine contacts. `sam2_video_prompt.video` and `locomotion.mmpose_video` must resolve to the exact same source file. All tracked frames are checked without resampling or interpolation; SAM 2 default `max_video_frames=120`, maximum 240. Match the *entire* actual reference clip length to the generated masks (trim video if necessary). `MMPose` is only invoked for human locomotion references. Walking/running/stairs pose quality and source cel release gates are unchanged.

If `locomotion.mmpose_guide` is supplied instead, its original `source_video` field must exactly match the SAM 2 source video filename. The existing authentic guide is cross-checked against every real SAM 2 mask without running MMPose again. This route can work offline after masks have been generated.

## Actual execution

1. `unified_delivery.py` invokes installed SAM 2 image/video predictor **before** MMPose inference; tracked masks are actually written at `output/sam2_generated/video_masks/<actor_id>/00000.png` etc.
2. For each original video frame `i`, `mmpose_sam2_bridge.py` validates mask file `i` at original video width × height. A frame must have a unique valid human candidate with ≥3 of 4 shoulder/hip landmarks and ≥2 of 4 knee/ankle landmarks inside its mask, plus confidence ≥0.30 for required keypoints.
3. Several candidates matching the same identity, no candidate, nonfinite joints, missing masks, resolution/frame-count discrepancy, wrong source video, or implausible torso teleport **block final release**. Zero-frame fallbacks or duplicate keypoints are prohibited.
4. The selected COCO17 track is written to the same `mmpose` JSON format as before and fed to the original `gait_metrics`, independent painted cels and motion gate. The SAM 2 masks and measured guide are included in the same GIF/ZIP final asset pack.
5. Krita, OpenToonz `.tnz`, Pixelorama `.pxo`, ControlNet Aux, DeepLabCut, Godot 4 and Grease Pencil downstream exports remain intact. Only whole authored RGBA drawings may be animated; the measured pose may guide artists but is NEVER a deformable character skeleton.

The bridge does **not** infer the identities of untouched humans automatically: an explicit SAM 2 prompt is required for each human to be tracked. For riders, segment horse and rider as separate actors. Unclear occluded ankles or overlapping bodies must fail and require corrected source footage/prompts, rather than fabricated human pose data.
