---
name: music-musescore-bridge
description: Use for game music composition, MusicXML/MIDI arrangement, score transposition, parts export and SYMPHONIA chapter transitions with the existing music skill and CLI-Anything.
---
# MuseScore notation bridge
Invoke alongside the music skill for any workflow requiring score editing or MIDI export. Preserve all existing modules, original motifs and source scores. MuseScore is an offline notation backend, not a replacement for generative music or the live Tone.js engine.

Canonical installer and dispatcher: https://github.com/mpaykin1/skills/tree/a3a239aca51dcee7a979c878fcd7d3460531c9ca/packages/skill-synergy-manager . Use scripts/install_musescore_cli.sh only in a disposable Linux x86_64 worker. Official MuseScore Studio 4.6.5 AppImage checksum pinned; upstream CLI-Anything commit 34f519533bc175d2fe287ab8316b0dd99bb9cc43. Python dependencies are version-pinned but not hash-locked. Installation in a temporary runner is not persistent installation in ChatGPT. Verify actual native export before claiming success.

Pipeline: NotaGen/Magenta/Music21/Tonal -> MusicXML -> MuseScore transposition, parts, MIDI export -> existing Mido and Music21 validation -> FluidSynth/Salamander -> Librosa/Rubber Band/SoundFile/FFmpeg -> Tone.js adaptive playback. Preserve motif IDs, seed, meter, pitch, timing, tempo map and sample-aligned boundaries. For intentional transposition verify expected pitch shift rather than identical pitches. No unlicensed input, paid services or Muse Sounds requirement. Keep sources immutable and use distinct output paths. For Z23 Overture/Adagio preserve chapter IDs and the existing live adaptive engine. Use original music only. If the native runtime is unavailable, use existing verified music generation; do not claim MuseScore was used.

Example from package root on the provisioned worker:
```
python3 scripts/nexus_cli.py run --workspace /absolute/job --timeout 180 musescore -- --json export midi -i /absolute/job/motif.musicxml -o /absolute/job/motif.mid
```
Parse the result and use Mido to verify actual note events, meter and tempo against the source. For native scores use .mscz and export MusicXML/MIDI with separate output. Never confuse a successful help call with rendered music. Do not automatically publish or change the game. GitHub Actions workflow: https://github.com/mpaykin1/skills/actions/workflows/nexus-musescore.yml .
