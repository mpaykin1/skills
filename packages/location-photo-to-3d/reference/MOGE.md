# Upstream MoGe-2 source contract

Repo: https://github.com/microsoft/MoGe
Model: https://huggingface.co/Ruicheng/moge-2-vits-normal
Based on upstream 2026 README and `moge/scripts/infer.py` CLI.
The skill does not vendor upstream source or model weights.

CLI: `python -m moge.scripts.infer -i PHOTO --version v2 --pretrained Ruicheng/moge-2-vits-normal --device cpu --resize 640 --resolution_level 3 -o OUT --glb --maps`.

Output: `OUT/<photo stem>/mesh.glb` textured source photo, `fov.json` original camera estimated FOV; optional depth and points.

Upstream coordinate conversion: camera world X right, Y up, Z backwards, image camera at origin looking along -Z; UV converted to GL convention by upstream export.

CPU float32 used; `--fp16` omitted. First-run downloads weights and dependencies; offline HTML generated after inference.
