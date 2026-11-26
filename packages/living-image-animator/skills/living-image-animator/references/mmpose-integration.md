# MMPose v1 bridge: measured human movement -> authored full-cel 2D sprites

Upstream: https://github.com/open-mmlab/mmpose , Apache-2.0 source. Read model and dataset/checkpoint terms separately. MMPose's stable v1 API is `from mmpose.apis import MMPoseInferencer` and `MMPoseInferencer(pose2d='human')`; unlike MMPose 0.x, APIs changed. The bridge never vendors model weights or claims installed PyTorch.

## Supported inputs

- Single human per source video, visible both legs. Headless extraction: `python scripts/mmpose_bridge.py --video motion_refs/actor_walk.mp4 --out motion/actor_walk.json --mode walk`.
- Or `--guide motion/actor_walk.json --mode walk` for JSON already extracted from true inference. This validation path works without installing MMPose.
- Standard output contains `engine=mmpose`, `keypoint_schema=coco17`, measured per-frame named keypoints with confidence scores, original video FPS and original video filename. The bridge rejects frames without reliable shoulders/hips/knees/ankles or ambiguous multiple subjects and checks actual alternating leg motion. The confidence gate is >=0.30 for necessary joints, 12+ source frames, no fabricated frames. No automatic human-to-cat model substitution.

## Connected use in scene.json

```json
{
  "inventory": {"actors": ["resident"]},
  "actors": [{
    "id":"resident", "role":"human", "box":[110,145,65,92],
    "source_mask":"masks/resident.png", "phase_frames":0,
    "clips":[
      {"action":"walk", "pixelorama_project":"pixelorama/resident/walk.pxo", "joints_json":"pixelorama/resident/walk.joints.json", "support_sequence":["left","left","left","double","right","right","right","double","left","left","left","double"]},
      {"action":"wave", "opentoonz_scene":"opentoonz/resident/wave.tnz", "joints_json":"opentoonz/resident/wave.joints.json", "start_frame":1, "frame_count":12, "dependencies":[]}
    ],
    "locomotion": {
      "mode":"walk", "mmpose_guide":"motion/resident_walk.json",
      "path":[{"frame":0,"dx":0,"dy":0},{"frame":12,"dx":72,"dy":0},{"frame":24,"dx":0,"dy":0}]
    }
  }]
}
```

This is a *schema illustration*, NOT a complete valid scene. Values, pose clips, contacts, source masks, landmarks, returns and route MUST match real approved artwork and satisfy strict checks; don't copy it as generated animation. Per-character cycle must divide GIF total frames. `mmpose_guide` and `mmpose_video` are mutually exclusive. If video is provided, unified delivery infers it at runtime and adds original video plus measured JSON to ZIP. Measured track is validated before rendering, not blindly accepted.

## Correct separation of responsibilities

MMPose provides an evidence-based motion *guide* (poses over time). OpenToonz/Pixelorama artist-author each complete transparent body frame in the desired style. The scene's independently authored `locomotion.path` moves that unchanged sprite across floor/stairs as the correct action plays. `locomotion.py` checks joint alternation, planted feet, speed continuity and minimum on-screen displacement. When original videos show a treadmill or moving camera, scene-space motion must be authored explicitly; NEVER infer world travel from keypoint fluctuations alone. Extracted bones cannot be warped into final characters. Reference gait metrics are not proof of artistic accuracy and must not replace the final visual inspection.
