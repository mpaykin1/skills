#!/usr/bin/env python3
"""One entry point from the parent Godot/Unity skill to official sprite-sheet-helper."""
from pathlib import Path
import subprocess
import sys

BRIDGE = Path(__file__).resolve().parents[2] / 'sprite-sheet-helper-bridge' / 'scripts' / 'export_atlas.py'
if __name__ == '__main__':
    if not BRIDGE.is_file():
        sys.exit('ERROR: sprite-sheet-helper-bridge is missing')
    sys.exit(subprocess.call([sys.executable, str(BRIDGE), *sys.argv[1:]]))
