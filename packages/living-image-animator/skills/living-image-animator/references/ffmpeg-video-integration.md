# FFmpeg × Living Image Animator — source-authored video with Howler ambience

Official: https://github.com/FFmpeg/FFmpeg ; license may be LGPL or GPL depending on build. Existing skill already uses FFmpeg for palette-encoded GIF. New video export is additive; it does not claim first-time installation of FFmpeg, and does not bundle the native executable.

## Export contract

- Source MUST be the fully approved `living_scene.gif` and `living_scene_assets.zip` after the complete original individual PNG actor-pose validation, original `.kra/.tnz/.pxo`, SAM 2/MMPose/DeepLabCut reference gates, authentic Tiled/LDtk scene metadata and original Godot/Blender stages. Use existing `pixijs_bridge.load_scene()` plus `motion_gate.json.all_actors_pass`. Never bypass missing actor art or character motion with camera, weather, audio, FFMPEG interpolation or a video loop.
- `scripts/ffmpeg_video_bridge.py` decodes the real original GIF and streams its original composited RGB image for each final 24+ FPS video frame, normalizing GIF's quantized centisecond duration to the project's declared 40–60s duration. No optical flow, fake in-betweens, motion-vector frames, body transforms, crop shifts, synthesized characters, or replacement PNG. H.264/AAC MP4 and VP9/Opus WebM are distributable linear video artifacts, **not** substitutes for source full-body RGBA drawings. MP4/WebM outputs are lossy and cannot restore colors already quantized in the source GIF; source APNG/lossless WebP and PNG remain the original lossless assets. For best visual fidelity in a later enhancement, add verified direct RGB frame streaming before the GIF palette stage.
- `--with-ambience` integrates actual author-provided `scene.pixi.audio.sounds[]` entries of `mode:"ambience"` only, using the same underlying input-file checks and SHA256 as `howler_bridge.audio_config`; the static soundtrack is mixed through FFmpeg with authored track volume and original master volume. `world` and `actor` spatial Howler.js sources remain in the **interactive** HTML player, **NOT** falsely positioned in the fixed linear video. Without ambience this video is silent. No synthesized sound or file substitutions. Exact author source audio preserved in ZIP.
- The video delivery runs the intact original `blender_delivery.py` first. New `living_scene_video.mp4`, `.webm`, `.zip` are separate additional outputs added to the existing source ZIP; old GIF, transparent APNG/WebP, game and editor paths stay available through their original commands. FFmpeg codecs must be truly installed; `ffprobe` checks codec, frame count, dimensions, duration and optional audio. If missing, fail before the expensive animation pass; do not silently substitute a codec or claim rendering completed.

## CLI

```bash
python scripts/ffmpeg_video_delivery.py source.png --scene scene.json --out output \
  --fps 24 --seconds 48 --format both
# With an original Howler ambience sound file specified in scene.pix.audio:
python scripts/ffmpeg_video_delivery.py source.png --scene scene.json --out output \
  --fps 24 --seconds 48 --format mp4 --with-ambience
```

`--ffmpeg /real/ffmpeg` and `--ffprobe /real/ffprobe` accept actual installed native binaries. User can also run `ffmpeg_video_bridge.py --approved-zip ... --gif ... --scene ... --out ...` on pre-existing approved original GIF/ZIP. No external network needed when FFmpeg is installed. FFmpeg installed binary licensing varies: no native binary is redistributed. Quality note: videos are compressed screen-space presentation exports; lossless transparent original actor art lives in source PNG/APNG/WebP assets.
