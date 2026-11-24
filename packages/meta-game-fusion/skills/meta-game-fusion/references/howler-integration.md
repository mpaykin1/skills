# Howler.js 2.2.4 — spatial living audio for META GAME FUSION

Upstream: https://github.com/goldfire/howler.js — MIT license; npm `howler@2.2.4`; [license](../vendor/howler/LICENSE.md). Full upstream package is NOT bundled; generated game installs the pinned npm package. This archive includes original authored adapters and original synthesized OGG+MP3. No external audio URLs/CDN/runtime downloads.

## Component flow

1. `scripts/audio_synthesis.py` deterministically generates 4 **new**, CPU-only, loopable sounds (wind, drone, step, rune) using NumPy and optional locally installed ffmpeg; outputs `templates/rapier-world/public/audio/`. These are **not** copied from external game audio.
2. `scripts/audio_bridge.py.make_plan(world, project)` uses source provenance marker, exact file SHA256, byte limits, safe audio filenames, and authored Rete/Ink stage styles to build `world.audio`. Called by both `rapier_bridge.prepare` and `fusion_builder.build`; the latter regenerates the plan after concept nodes are finalized.
3. The generated game pins `howler@2.2.4` in `package.json`. `scripts/verify-audio.mjs` blocks dev/build if required sound assets differ from SHA256, disappear, or are symlinked. This is separate from GLB's glTF-Validator and ScanCode rights gates.
4. `src/spatial-audio.js` owns a bounded Howler pool: 2 ambient channels (wind, machinery) + step and rune effects. The ONLY supported sources are local `/audio/*.ogg`, `/audio/*.mp3` copied in the project. No uploads, media fetch from internet, autoplay, UI spoofing, silent substitution or third-party sample packs.
5. The desktop/mobile sound button (keyboard `M` shortcut) is the **only unlock action**. Initial state is muted. On user input Howler resumes its WebAudio context as permitted by the browser, then crossfades ambience. The sound button remains separate from FX quality; mute immediately stops all sounds.
6. Scene changes from Rete/Ink call `audio.enter(stageId)` for mood crossfade. Ink dialogues call `audio.setDialogue(true)` for -9 dB ducking; normal music level returns on exit. Real interactions call `audio.pulse(playerPosition)` and inform YUKA separately. Never generate an event that changes player movement.
7. On each frame, camera controls the WebAudio listener, true Rapier player positions and grounded state trigger footsteps, and the two YUKA NPC positions produce spatial steps when they physically move. Recast gives paths, YUKA gives intent; Rapier resolves actual positions and collisions. `postprocessing` controls 2D visuals independently. Quality Eco reduces secondary NPC voices; no dependency on visual FX for hearing.
8. `Qdrant` catalogs the actual authored adapter and SHA-256 for discoverability. Audio assets have their own provenance and hashes; do not use ScanCode positive license detection as permission to copy arbitrary recordings.

## Restrictions

- **No audible PASS claim** without installed npm dependencies, real click/tap, and browser audio playback inspection. The audio listener and actor positions can be observed via read-only telemetry (`window.__MGF_STATE__().audio`) but telemetry is NOT proof of hearing actual sound.
- User-supplied recordings require explicit reuse rights, inclusion in a reviewed manifest, and a different asset path; the standard demo never overwrites the original.
- Mobile browsers require first user input. Some mute settings, disabled audio contexts, codecs, and device audio permissions may prevent playback; report it, don't claim successful sound.
- For offline, standalone `file://` HTML, a separate full bundling operation must embed the Howler runtime AND all sound bytes; a Vite source folder or a linked script alone is not autonomous HTML.
- Do not auto-start speech or music; existing original scripts, animation identities, Rapier and Recast ownership remain unaffected.

## Rebuild original media

```sh
python skills/meta-game-fusion/scripts/audio_synthesis.py --out skills/meta-game-fusion/templates/rapier-world/public/audio
```

Generated game: `npm install` then `npm run dev`; Vite performs GLB validation and source audio preflight. Actual runtime requires a browser. The demo is a source project, not a deployed game.
