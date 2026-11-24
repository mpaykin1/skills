#!/usr/bin/env python3
"""Route native Godot sources and GDRETools-recovered releases into existing exporter."""
from __future__ import annotations
import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from recover_godot import recover

BASE = Path(__file__).resolve().parent


def main():
    ap = argparse.ArgumentParser(description='Godot project/PCK/EXE/APK -> Web or experimental one-file HTML')
    ap.add_argument('source', type=Path)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--godot', help='Path to matching Godot editor with Web templates')
    ap.add_argument('--gdre', help='Path to GDRETools executable')
    ap.add_argument('--mode', choices=('web', 'single', 'recover'), default='web')
    ap.add_argument('--key-env', help='Environment variable containing authorized GDRETools 64-hex key')
    ap.add_argument('--preset', default='Web')
    a = ap.parse_args()
    source = a.source.expanduser().resolve(strict=True)
    out = a.out.expanduser().resolve()
    if out == source or out in source.parents or (source.is_dir() and source in out.parents):
        raise ValueError('Output must be separate from source')
    if a.mode == 'recover' and source.is_dir() and (source/'project.godot').is_file():
        raise ValueError('Source is already a Godot project; recover mode is for packaged input')
    if a.mode == 'recover':
        recover(source, out/'recovered', gdre=a.gdre, key_env=a.key_env)
        print('Recovered project:', out/'recovered')
        return

    if source.is_dir() and (source/'project.godot').is_file():
        project = source
        export_from(project, out, a)
    elif source.is_dir():
        # Projects with one nested project.godot are supported by existing exporter.
        if len(list(source.glob('*/project.godot'))) != 1:
            raise ValueError('Directory does not contain exactly one Godot project')
        export_from(source, out, a)
    else:
        # Do not discard recovered sources: provide them alongside the export.
        recovered = out/'recovered'
        project = recover(source, recovered, gdre=a.gdre, key_env=a.key_env)
        export_from(project, out, a)


def export_from(project: Path, out: Path, a):
    cmd = [sys.executable, str(BASE/'godot_to_web.py'), str(project), '--out', str(out), '--mode', a.mode,
           '--preset', a.preset]
    if a.godot:
        cmd.extend(['--godot', a.godot])
    subprocess.run(cmd, check=True)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError, OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        sys.exit('ERROR: '+str(e))
