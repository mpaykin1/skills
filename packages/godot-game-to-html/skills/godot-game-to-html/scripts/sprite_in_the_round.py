#!/usr/bin/env python3
"""Short entry for the official MIT sprite-in-the-round ↔ META GAMES sprite stack bridge."""
from pathlib import Path
import subprocess
import sys
BRIDGE=Path(__file__).resolve().parents[2]/'sprite-in-the-round-bridge'/'scripts'/'round_bridge.py'
if __name__=='__main__':
    if not BRIDGE.is_file():sys.exit('ERROR: sprite-in-the-round-bridge is missing')
    sys.exit(subprocess.call([sys.executable,str(BRIDGE),*sys.argv[1:]]))
