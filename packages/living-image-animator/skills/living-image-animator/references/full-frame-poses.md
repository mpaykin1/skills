# Full-frame authored pose schema v0.5 (release protocol)

**Never deform an illustration into movement**. Supply a real frame-by-frame sequence for *every* identified person and animal. All pixels within a character sprite must come from that separately authored pose. Output compositing does not rotate, warp, scale selectively, generate, morph or interpolate character bodies.

## Scene example (abbreviated)

```json
{
  "version": 3,
  "mode": "full-frame-pose-sprites",
  "seamless": true,
  "inventory": {"actors": ["roof_cat", "reader"]},
  "actors": [
    {
      "id": "roof_cat", "role": "cat", "z": 20,
      "source_mask": "masks/roof_cat.png",
      "box": [172, 119, 70, 78], "phase_frames": 12,
      "clips": [
        {"action":"groom","frames":[
          {"png":"poses/roof_cat/groom_000.png", "joints":{"root":[35,48],"head":[26,23],"left_paw":[14,46],"right_paw":[45,43]}},
          {"png":"poses/roof_cat/groom_001.png", "joints":{"root":[35,48],"head":[26,23],"left_paw":[14,46],"right_paw":[45,42]}}
        ]},
        {"action":"stretch","frames":["... 12+ annotated full-image pose objects ..."]}
      ]
    },
    {"id":"reader", "role":"human", "source_mask":"masks/reader.png",
     "box":[200,300,90,110], "phase_frames":17, "clips":["... read + turn_page ..."]}
  ],
  "lights":[], "particles":[], "day_night":{"enabled":false}
}
```

The example above is **structural, not executable**: every action needs its complete 12+ poses and all visible characters need valid authored frame paths. Use each actor's fixed pixel `box=[x,y,width,height]` in ORIGINAL source pixel coordinates. Every RGBA pose PNG for an actor must have exactly width×height pixels with the character and its held object registered inside the box. `source_mask` is a full-image grayscale mask at ORIGINAL source dimensions. `joints` coordinates are integer/float **sprite-local** pixels; `root` is the pelvis, torso base or animal body's center; at least two other real visible anatomical joints must be tracked in every pose. Joint locations must match artwork, never invented to manipulate metrics.

Each `clips[].frames` is one independently authored full-character PNG **per final 24fps frame**. Clip order is chronological, and the full loop concatenates the clips in listed order. All images are drawn relative to the same anchor. Never place a single static image into a 24-frame list and claim that creates motion.

## Release quality gates

- No character omitted: inventory IDs equal rendered actor IDs.
- >=2 distinct actively articulated actions per character and active occupancy >=60%.
- Every active action 12+ 24fps frames, 8+ unique independently authored PNGs. A still hold in an active action at most 2 frames; idle hold max 6.
- Each action must show at least 22% silhouette difference **after subtracting simple rigid translation**, and two distal joints each move >=22% of source pose's height relative to the root (4px minimum). Root may move with a true walk, but alone never earns credit.
- No abrupt adjacent shape jumps >43% changed actor pixels, no adjacent joint jumps >18% body height (10px floor), no final-to-first seam jump >12%. These are conservative geometric checks, not proof of coherent anatomy; inspect the GIF and increase frames near large actions to ensure natural continuity.
- All actor cycles must divide the total GIF frame count exactly. Different lengths and phase offsets stagger their behaviors. Example 48s × 24fps = 1152 output frames; actor cycles can be 96/144/192/288/384 frames.
- No warping, rotation of source-extracted bones, interpolation or text-to-video morphing of approved character images.
- For true source-faithful characters, missing hidden arms, legs, rear views and object interactions require redraw and identity review before rendering. A single flattened still does not contain those unseen poses.
- `pose_sequence_delivery.py` validates visible action PNGs separately from changes to background, clouds, lighting, camera, particles and other actors. Outputs `living_scene.gif` and `living_scene_assets.zip` only after passing.

Tooling: Pixelorama/OpenToonz for authored sprite frames, SAM2 for identity-locked masking, IOPaint for background reconstruction, FFmpeg for GIF export. RIFE and ToonCrafter must not produce the final character frames because inferred optical-flow deforming or generative interpolation can break strict character identity/artwork consistency.
