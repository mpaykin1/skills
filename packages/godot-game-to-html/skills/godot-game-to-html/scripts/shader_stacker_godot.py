#!/usr/bin/env python3
"""One-command Godot 4 bridge into the existing official Shader-Stacker skill.

Accepts real sprite stack manifests, Godot-compatible slice strips, original static
GLB or an authored 4-view PNG with --four-views; all other plugin tools remain.
"""
from pathlib import Path
import subprocess
import sys

BRIDGE=Path(__file__).resolve().parents[2]/'godot-shader-stacker-bridge'/'scripts'/'stack_to_godot.py'
if __name__=='__main__':
    if not BRIDGE.is_file():sys.exit('ERROR: Shader-Stacker bridge is missing')
    sys.exit(subprocess.call([sys.executable,str(BRIDGE),*sys.argv[1:]]))
