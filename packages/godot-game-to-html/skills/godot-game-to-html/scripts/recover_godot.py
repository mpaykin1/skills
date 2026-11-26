#!/usr/bin/env python3
"""Recover a legally controlled Godot PCK, EXE or APK with official GDRETools CLI.

GDRETools is a separate MIT-licensed dependency. Source input is *never* executed.
No modification is made to the original archive.
"""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

TOOL_TAG = 'v2.7.4'
CACHE_ROOT = Path.home() / '.cache' / 'godot-game-to-html' / 'gdretools' / TOOL_TAG
SUPPORTED = {'.pck', '.exe', '.apk'}


def find_gdre(explicit: str | None = None) -> str:
    candidates = []
    if explicit:
        candidates.append(explicit)
    else:
        env = os.getenv('GDRETOOLS_BIN')
        if env:
            candidates.append(env)
        candidates.extend(['gdre_tools', 'gdre_tools.exe', 'GDRE_tools.exe'])
        if CACHE_ROOT.exists():
            candidates.extend(str(p) for p in CACHE_ROOT.rglob('*')
                              if p.is_file() and ('gdre_tools' in p.name.lower()
                                                  or 'gdretools' in p.name.lower())
                              and (os.name == 'nt' or os.access(p, os.X_OK)))
    for candidate in candidates:
        resolved = shutil.which(str(candidate))
        if resolved:
            return resolved
        p = Path(candidate).expanduser()
        if p.is_file() and (os.name == 'nt' or os.access(p, os.X_OK)):
            return str(p.resolve())
    raise FileNotFoundError('GDRETools executable not found. Run install_gdretools.py, or pass --gdre PATH.')


def project_root(root: Path) -> Path:
    if (root / 'project.godot').is_file():
        return root
    matches = sorted(p.parent for p in root.glob('*/project.godot') if p.is_file())
    if len(matches) == 1:
        return matches[0]
    raise RuntimeError('Recovered output is not an unambiguous Godot project: project.godot missing or multiple projects found.')


def recover(source: Path, out: Path, *, gdre: str | None = None, mode: str = 'recover', timeout: int = 1800,
            key_env: str | None = None) -> Path:
    source = source.expanduser().resolve(strict=True)
    if source.is_file() and source.suffix.lower() not in SUPPORTED:
        raise ValueError('Supported binary input extensions: .pck, .exe, .apk')
    if not source.is_file() and not source.is_dir():
        raise ValueError('Source must be PCK/EXE/APK or an extracted project directory')
    out = out.expanduser().resolve()
    if out == source or out in source.parents or (source.is_dir() and source in out.parents):
        raise ValueError('Output cannot overwrite, contain, or be inside the source')
    if out.exists() and any(out.iterdir()):
        raise FileExistsError(f'Recovery destination is not empty: {out}')
    out.mkdir(parents=True, exist_ok=True)
    cli = find_gdre(gdre)
    cmd = [cli, '--headless', f'--{mode}={source}', f'--output={out}']
    if key_env:
        val = os.getenv(key_env, '')
        if len(val) != 64 or any(c not in '0123456789abcdefABCDEF' for c in val):
            raise ValueError('Encrypted archive requires a 64-hex key in the specified environment variable')
        # The key is supplied only by a user who is authorized to open this project.
        cmd.append('--key='+val)
    # Do not print the command: it can contain a key. Execution inputs are never run as programs.
    try:
        subprocess.run(cmd, check=True, timeout=timeout, cwd=str(out))
    except subprocess.CalledProcessError as err:
        raise RuntimeError(f'GDRETools failed with exit code {err.returncode}') from None
    except subprocess.TimeoutExpired:
        raise RuntimeError(f'GDRETools did not finish within {timeout}s') from None
    if mode == 'recover':
        return project_root(out)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description='GDRETools recovery for Godot -> HTML workflow')
    ap.add_argument('source', type=Path, help='.pck/.exe/.apk or extracted project folder')
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--gdre', help='Path to official GDRETools executable')
    ap.add_argument('--mode', choices=('recover', 'extract'), default='recover')
    ap.add_argument('--timeout', type=int, default=1800)
    ap.add_argument('--key-env', help='Name of environment variable holding a user-authorized decryption key')
    a = ap.parse_args()
    result = recover(a.source, a.out, gdre=a.gdre, mode=a.mode, timeout=a.timeout, key_env=a.key_env)
    print('Recovered project:' if a.mode == 'recover' else 'Extracted assets:', result)


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        sys.exit(f'ERROR: {exc}')
