#!/usr/bin/env python3
"""Vendored source already ships inside plugin. Resolve engine dependencies and bundle when npm is online."""
import subprocess, sys
from pathlib import Path
root=Path(__file__).resolve().parent
steps=[['node','./verify-vendor.mjs'], ['npm','install','--ignore-scripts','--no-audit','--no-fund'], ['npm','run','build']]
for cmd in steps:
    result=subprocess.run(cmd,cwd=root)
    if result.returncode:
        print('Vendor source remains present. Runtime resolution/bundle incomplete; requires npm access for three, three-mesh-bvh, esbuild.',file=sys.stderr)
        raise SystemExit(result.returncode)
print('All three user-supplied libraries linked; runtime build generated:',root/'dist/advanced_effects.bundle.mjs')
