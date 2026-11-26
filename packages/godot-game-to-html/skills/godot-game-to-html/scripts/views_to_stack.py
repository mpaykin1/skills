#!/usr/bin/env python3
"""Short entry to the actual danielwh2/sprite-stacking → META GAMES bridge."""
from pathlib import Path
import subprocess
import sys

BRIDGE = Path(__file__).resolve().parents[2] / 'sprite-stacking-four-views' / 'scripts' / 'views_to_stack.py'
if __name__ == '__main__':
    if not BRIDGE.is_file():
        sys.exit('ERROR: sprite-stacking-four-views module is missing from the plugin')
    sys.exit(subprocess.call([sys.executable, str(BRIDGE), *sys.argv[1:]]))
