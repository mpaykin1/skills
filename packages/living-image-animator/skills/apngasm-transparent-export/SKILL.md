---
name: apngasm-transparent-export
description: Optional apngasm 3.x CPU-only animated transparent PNG export for the existing Living Image Animator, consuming exactly the already validated original full-body 2D/2.5D PNG cels. Keeps the GIF, source ZIP, Godot, Blender, PixiJS, Tiled, LDtk and all other OSS unchanged.
---

# APNG export within Living Image Animator

This is a **supplementary mode of living-image-animator**, NOT a separate artwork generator. Read `../living-image-animator/SKILL.md` and `../living-image-animator/references/apngasm-integration.md` before use. All original SAM2, MMPose, DeepLabCut, ControlNet Aux, ComfyUI, Krita, OpenToonz, Pixelorama, Tiled/LDtk, Godot/Blender and full-cel sprite animation quality gates remain mandatory. Output real CPU-built transparent full-character APNG, not processed GIF, deformed images, or fabricated artist poses. No separate engine may be claimed when absent. Do not weaken or delete PixiJS CullerPlugin optimization or any previous stage. No reports/evidence unless user requests them.

Call `python ../living-image-animator/scripts/apngasm_delivery.py <source.png> --scene <scene.json> --out <output> --build-apngasm --per-action`, or pass an actual installed `--apngasm` path. Existing source PNG pose cels and license remain available in returned ZIP. All visible moving actors retain stable identities, non-static body poses, full-foot contacts and large amplitude. Actor APNGs are extra exportable assets for browser HTML, not a replacement for PixiJS collision/AI physics or world trajectories. Do not claim standalone game hosted without publishing.
