# Genuine Pixelorama ↔ OpenToonz 2D/2.5D cel interchange

Authoritative upstream: https://pixelorama.org/user_manual/cli/ ; https://github.com/Orama-Interactive/Pixelorama ; https://github.com/opentoonz/opentoonz . Pixelorama CLI `--framecount`, `--spritesheet`, `--direction 0`, `--export`, `--output` are documented. Release v1.2.4 fixes a broken `--output` option. Pixelorama is MIT-licensed; review licenses of extra tools independently.

The skill uses native `pixelorama_bridge.py` and native OpenToonz `tcomposer` first, then `pixelorama_handoff.py`. This is **real pixel-locked interchange**, not a generative sprite replacement or in-game skeletal rig.

**Pixelorama `.pxo` → OpenToonz:** real CLI-exported cels are checked one-by-one against the original exported spritesheet. The `.pxo` source is hash-locked, every complete frame must be PNG RGBA with transparency, and exactly the expected number of cells must be present. Output numbered OpenToonz-compatible frame files are located at `interchange_2d/opentoonz_levels/<actor>/<clip>/<actor>.0001.png` etc., in precise chronological order.

**OpenToonz `.tnz` → Pixelorama:** each transparent character frame actually rendered by `tcomposer` is joined into an RGBA grid, with `columns`, `rows`, frame count and reading order stored in `interchange_2d/interchange.json`. Import that sheet as a spritesheet in Pixelorama; slicing uses original sprite `box` size. The ZIP contains the genuine source `.tnz` separately. This conversion does not author a `.pxo` or `.tnz`, and does not invent a pose.

**Shared motion contract:** all clips retain manually supplied `joints` and `support_sequence` with exact frame alignment; support labels are checked against final exported cels. Actual locomotion is validated by the original `locomotion.py` and real full-cel compositor; moving only the stage/camera or cycling unchanged pixels is not character motion. Every actor needs two independent substantive actions.

**How the scripts connect:** `unified_delivery.py` calls `opentoonz_bridge.compile_scene` then `pixelorama_handoff.compile_and_handoff`, which calls `pixelorama_bridge.compile_scene` and writes an accurate frame-sequence index and OpenToonz/Pixelorama interoperable images. Afterward `pose_sequence_delivery.py` renders only actual frames and blocks incomplete actors. No independent 'easy' export path bypasses the guard.

**External binaries:** Pixelorama >=1.2.4 and OpenToonz `tcomposer` must be installed locally for the relevant source formats. This skill contains Python CLI bridges, not those external programs or trained models. Offline bridge validation cannot prove the real installed programs will work without an actual `.pxo`/`.tnz` source and binaries.
