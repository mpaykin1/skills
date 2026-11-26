# Rhubarb Lip Sync 1.14.0 × Howler.js × full-body original 2.5D cels

Open source: https://github.com/DanielSWolf/rhubarb-lip-sync (MIT, Daniel Wolf). Rhubarb's original **CLI** is external and must be installed separately; network-blocked environments cannot claim to have downloaded or run it. It analyzes WAVE/Ogg Vorbis; source MP3 is converted using genuine FFmpeg to temporary mono 16 kHz PCM WAV, while Howler continues to play the untouched original file.

## Why this genuinely complements previous OSS

- **Howler.js 2.2.4** is the sole playback clock and original spatial/actor sound source. Rhubarb's cue timestamps are sampled from `Howl.seek()` when that actor's voice is actually playing, including pause/resume. A real tap starts browser sound on mobile.
- **Rhubarb v1.14.0** with `--recognizer phonetic` supports non-English recordings including Russian (less accurate than English PocketSphinx, so artist review is important). English `pocketSphinx` is optional. It exports real JSON (`A B C D E F X`) and OpenToonz Preston Blair DAT at original FPS. Optional actual `dialog_file` can improve recognition.
- **Krita / OpenToonz / Pixelorama** supply *separately drawn complete RGBA body images* with unique mouth shapes. There is absolutely **no mouth overlay, face mesh rig, cutout warp or AI synthesis**. Only author-provided full-body cels pass. For every already-approved source pose index, make **seven** complete image variants; their pixels **outside a small original mouth rectangle must be byte-for-byte equal** to the approved body pose. At least 4 mouth shapes actually differ for each index.
- **PixiJS 8** swaps an entire original full-body `PIXI.Sprite.texture` using exact Rhubarb cue and original character frame index after the already-running original animation ticker. If a voice isn't playing, the original authored body pose plays unmodified. The original environment, camera, CullerPlugin, tilemap, particles and original visibility/physics are unaffected.
- **FFmpeg** retains its existing MP4/WebM outputs. The lipsync HTML is an **additional** separate browser export; don't claim existing video output contains speaking mouth variants until that actual scene video is separately re-rendered and checked.

## Scene schema

Original source `scene.json` must also contain an approved `pixi.audio.sounds` entry with the same `sound_id`, `mode="actor"`, `actor_id`, and **`loop=false`**. Dialogue files must be original WAV/OGG/MP3. Every specified actor must exist in the already verified motion gate/actor roster.

```json
{
  "pixi": {
    "audio": {"sounds": [
      {"id":"healer_voice","file":"audio/healer.wav","mode":"actor","actor_id":"healer","loop":false,"volume":0.7}
    ]},
    "lipsync": {"speakers": [
      {"actor_id":"healer","sound_id":"healer_voice", "viseme_dir":"visemes/healer",
       "mouth_roi":[18,8,10,7],"recognizer":"phonetic", "dialog_file":"audio/healer.txt"}
    ]}
  }
}
```

`mouth_roi` is local to the original actor frame canvas `[x,y,width,height]`. The sample values are illustrative, not inferred from a source picture. For N source frames (original actor clip arrays concatenated), each mouth directory must have exactly the corresponding full-body alpha images for the seven mouth states, in these paths:

```
visemes/healer/A/000.png ... A/{N-1}.png
visemes/healer/B/000.png ... B/{N-1}.png
visemes/healer/C/000.png ... C/{N-1}.png
visemes/healer/D/000.png ... D/{N-1}.png
visemes/healer/E/000.png ... E/{N-1}.png
visemes/healer/F/000.png ... F/{N-1}.png
visemes/healer/X/000.png ... X/{N-1}.png
```

All pixel data (including alpha) OUTSIDE the specified mouth rectangle must be identical to original already-approved full-body base frames; invalid image sizes, new identities, changed clothes/eyes/limbs/root or more than 35 MB of mouth variants block the build. The original source animation must independently pass two actions, >=60% active frames, >=12 frames/action, >=8 distinct source drawings, >=22% full-body silhouette and two genuine joint excursions, genuine loop 40–60s 24+FPS, original foot-contact and anti-warp requirements. Rhubarb mouth movement does **not** count toward those full-body gates.

## Exact flow and one-command build

`scripts/rhubarb_lipsync_delivery.py` first runs the **full unchanged** `howler_delivery.py` stage, which in turn runs the whole original GIF and ZIP validation, Godot/Blender, PixiJS atlases, original Tiled+LDtk, A* navigation, actual @pixi/tilemap, camera, filters, GPU particles and native CullerPlugin. It requires a real locally available Howler bundle. New audio, viseme source images, DAT files and Rhubarb cues are packaged without removing other artifacts.

```bash
python scripts/rhubarb_lipsync_delivery.py source.png --scene scene.json --out output \
  --fps 24 --seconds 48 --rhubarb /path/to/rhubarb \
  --pixi-js /path/to/pixi.min.js --viewport-js /path/to/pixi-viewport.js \
  --filters-js /path/to/pixi-filters.js --particles-js /path/to/pixi-particles.js \
  --tilemap-js /path/to/pixi-tilemap.js --howler-js /path/to/howler.min.js
```

Existing `--fetch-pixi`, `--fetch-viewport`, `--fetch-filters`, `--fetch-particles`, `--fetch-tilemap` and `--fetch-howler` options may be used when npm/network is available. `--ffmpeg` converts original MP3 speech for Rhubarb, never invents a recording. Rhubarb's CLI is a separate genuine executable and must be supplied. The emitted `living_scene_pixi_lipsync.html` is fully standalone when its true source engines and painted cels were available. New `living_scene_lipsync.zip` contains the HTML, real mouth PNGs, cues JSON, OpenToonz DAT and MIT license, and is additionally appended to original `living_scene_assets.zip` without overwriting any previous source sprite or verified gate.

Never claim a public game URL without genuine publication. Never claim actual generated speech or a working video until it has been rendered with actual voice and character art.
