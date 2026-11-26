#!/usr/bin/env bash
set -euo pipefail
# First setup requires internet; generated HTML is offline.
cd "$(dirname "$0")/.."
PYTHON=${PYTHON:-python3}
if [ ! -d .venv ]; then "$PYTHON" -m venv .venv; fi
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install --index-url https://download.pytorch.org/whl/cpu torch torchvision
.venv/bin/python -m pip install pillow numpy trimesh 'opencv-python-headless>=4.10,<5' huggingface_hub
.venv/bin/python -m pip install 'git+https://github.com/microsoft/MoGe.git'
if [ ! -f vendor/Depth-Anything-V2/depth_anything_v2/dpt.py ]; then
  command -v git >/dev/null || { echo 'Git required for official Depth Anything V2'; exit 1; }
  mkdir -p vendor
  git clone --depth 1 https://github.com/DepthAnything/Depth-Anything-V2.git vendor/Depth-Anything-V2
fi
if [ ! -f vendor/MobileSAM/mobile_sam/__init__.py ]; then
  command -v git >/dev/null || { echo 'Git required for official MobileSAM'; exit 1; }
  mkdir -p vendor
  git clone --depth 1 https://github.com/ChaoningZhang/MobileSAM.git vendor/MobileSAM
fi
printf 'CPU-only MoGe-2 + Depth Anything V2 Small + MobileSAM + OpenCV 4 prepared. First inference downloads checkpoints.\n' 
printf 'Run: .venv/bin/python scripts/build_location.py photo.jpg -o location.html\n'
