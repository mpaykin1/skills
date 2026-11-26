# Open-source components — actual integration versus optional recommendations

- Krita (https://github.com/KDE/krita) — frame-by-frame raster art and PNG image sequence export in GUI. **Integrated as verified RGBA PNG sequence reader**, preserving `.kra`, joint annotations and exact exported cels. No claim that this plugin invokes Krita GUI or reads `.kra` frames directly. GPL software not bundled.
- OpenToonz (https://github.com/opentoonz/opentoonz) — native `.tnz` via installed `tcomposer`; original 24fps transparent full-character drawings to PNG; native editing projects preserved. Installed binary separately required when `.tnz` used.
- Pixelorama (https://github.com/Orama-Interactive/Pixelorama) — native `.pxo` via installed >=1.2.4 CLI; sprite sheet→individual true PNG cels, no synthetic poses. Binary installed separately.
- MMPose (https://github.com/open-mmlab/mmpose) — human gait guidance from supplied video, not art or animal gait. Local model/checkpoints required for video inference. Original separate license applies.
- OpenToonz MCP (https://github.com/konkomaji/opentoonz-mcp) — **not integrated**; optional timeline automation, needs external security review.
- SAM 2 (https://github.com/facebookresearch/sam2) — **not integrated**; optional foreground segmentation, no pose generation.
- GroundingDINO (https://github.com/IDEA-Research/GroundingDINO) — **not integrated**; optional actor detection.
- IOPaint (https://github.com/Sanster/IOPaint) — **not integrated**; optional scene inpaint. Pose compositor uses OpenCV for background inpainting.
- ComfyUI (https://github.com/Comfy-Org/ComfyUI) — **not integrated**; optional independent pose proposal, not approved final art until each cel identity-checked.
- RIFE (https://github.com/hzwer/Practical-RIFE) — optional atmosphere/background effects ONLY; prohibited for characters under pose identity contract.
- FFmpeg (https://github.com/FFmpeg/FFmpeg) — used by `pose_sequence_delivery.py` to encode GIF after all individual character pose validation passes.

Final: `scripts/unified_delivery.py` compiles native Krita sequence first, OpenToonz .tnz then Pixelorama .pxo, exchanges exact original RGBA cels across three editors, and runs the strict independent-pose and locomotion rendering gates. Native `.kra/.tnz/.pxo` editing projects are preserved, not fabricated. Neither importing image sequences nor adding OSS projects can create unseen poses automatically.
