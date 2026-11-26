---
name: music-audacity-bridge
description: Offline CLI-Anything Audacity-style audio timeline editing for game music and sound effects; preserves existing MUSIC engines.
---
# Audacity CLI bridge
Source https://github.com/HKUDS/CLI-Anything/tree/34f519533bc175d2fe287ab8316b0dd99bb9cc43/audacity/agent-harness
Installer: https://github.com/mpaykin1/skills/blob/main/packages/skill-synergy-manager/scripts/install_audacity_cli.sh
The pinned harness renders via its own Python WAV DSP, NOT native Audacity. Native Audacity installation is not needed for this backend. Never call it native Audacity editing or claim .aup3 compatibility. Use only PCM WAV; non-WAV presets in upstream can write WAV bytes under the wrong extension. Keep source WAV immutable, preconvert with existing FFmpeg to stereo PCM16 48kHz; avoid internal resampling. Use original or licensed inputs.
Pipeline: NotaGen/Magenta/Music21/Mido/MuseScore -> FluidSynth/Salamander -> Audacity-style timeline (trim, align, gain, labels, SFX and track assembly) -> Pedalboard for scene acoustics -> Librosa checks -> SoundFile for exact sample loop boundaries -> FFmpeg for delivery masters -> Tone.js/loop player. Never normalize stems independently or use lossy output as a sample-exact loop. Preserve motif, phase, meter, BPM, sample offset and chapter ID. Avoid clipping and validate non-silence and correct WAV headers; use existing native audio tools for high-quality time stretch and effects. Do not run Python DSP in game frame.
Run in disposable workspace with absolute paths, --json, and source/output separation. Example:
```sh
cli-anything-audacity --json project new --sample-rate 48000 --channels 2 -o /absolute/job/project.json
cli-anything-audacity --json --project /absolute/job/project.json track add --name SFX
cli-anything-audacity --json --project /absolute/job/project.json clip add 0 /absolute/job/source.wav --start 0
cli-anything-audacity --json --project /absolute/job/project.json export render /absolute/job/mix.wav --preset wav
```
Inspect actual PCM samples and verify timeline. If backend unavailable keep existing FFmpeg/SoundFile pipeline. No claim of live integration without actual game output.
