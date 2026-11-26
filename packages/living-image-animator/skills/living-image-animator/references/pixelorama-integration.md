# Pixelorama ↔ Living Image Animator — working headless CLI bridge

**Actual source:** [Pixelorama](https://github.com/Orama-Interactive/Pixelorama) (MIT license). Use **Pixelorama >= 1.2.4**; this version fixes a CLI `--output` export failure. Pixelorama is a separate desktop application, not copied into this skill.

## Data flow

1. Artist creates every actual character pose in Pixelorama on a RGBA canvas identical to the character's pixel `box` dimensions. Save editable `.pxo` with the final composited frame image data; all frames must show the SAME full character, not cropped/extracted rotating parts.
2. Provide `joints_json` annotation file with one `[x,y]` coordinate map **per frame**. At least `root` plus two visible anatomical landmarks. Annotations must be drawn from real pixels; they are not synthesized by the bridge.
3. The integrated release command calls Pixelorama headless, reads its real frame count, exports spritesheet PNG, unpacks **individual full-character RGBA frames**, and rewrites `scene.json` to the v0.5 schema. `pose_sequence_delivery.py` checks identity-sensitive continuity, joint sweep, visible silhouette change, non-frozen animation, then GIF/ZIP; invalid/missing frames fail closed.
4. ZIP also includes original editable `.pxo` projects and landmark JSON, not just flattened PNGs. Re-exports invalidate the source SHA-256 if artist modifies a project without recompilation.

## Scene fields

For each `actors[].clips[]` authored in Pixelorama use:

```json
{"action":"gesture","pixelorama_project":"pixelorama/resident/gesture.pxo","joints_json":"pixelorama/resident/gesture.joints.json"}
```

Joint sidecar `gesture.joints.json`: `{ "frames": [ { "root": [20,36], "left_hand": [10,16], "right_hand": [34,19] }, ... ] }` with **exactly one map per Pixelorama project frame**, coordinates within the actor box. Same `root`/landmark names across frames. Scene-level `inventory`, `source_mask`, `box`, all actors and clip metadata remain as in `full-frame-poses.md`.

## One-command usage

```bash
python scripts/pose_sequence_delivery.py source.png \\
  --scene scene.json --out output --seconds 48 --fps 24 \\
  --pixelorama /path/to/Pixelorama.x86_64
```

Or use environment variable `PIXELORAMA_BIN=/path/to/Pixelorama.x86_64`. Desktop Pixelorama on Linux/macOS/Windows is required for `.pxo` export; this does not run in the browser. The bridge handles `--headless --quit -- PROJECT.pxo --framecount` and `--spritesheet --export --direction 0 --output ...`. All arguments passed through subprocess without a shell, source paths confined to scene root.

**Limits:** Pixelorama does not magically generate missing poses from a flattened picture. The artist or an approved pose generation tool must create actual key/in-between frames. Do not claim a complete animated GIF without compiling and validating all pixel-locked cast frames. Do not use RIFE/warp/skeleton rotation on character frames. No bundled Pixelorama executable, trained model or automatic pose generator.
