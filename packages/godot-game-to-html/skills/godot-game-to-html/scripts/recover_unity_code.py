#!/usr/bin/env python3
"""Recover C# source from explicitly authorized Unity MONO managed DLLs via ILSpyCmd.

Separate source extraction from playable WebGL export. This never runs game binaries.
IL2CPP native code requires a different pipeline; no fake C# restoration.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

from install_ilspycmd import resolve as resolve_ilspy, VERSION as ILSPY_VERSION

DEFAULT_DLLS = ("Assembly-CSharp.dll", "Assembly-CSharp-firstpass.dll", "Assembly-UnityScript.dll")
VALID_DLL = re.compile(r"^[A-Za-z0-9_.-]+\.dll$", flags=re.IGNORECASE)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fp:
        while True:
            chunk = fp.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def input_root(source: Path) -> Path:
    if source.is_file() and source.name.lower().endswith('.exe'):
        data_dir = source.with_name(source.stem + '_Data')
        
        if not data_dir.is_dir():
            raise ValueError("Unity executable without matching *_Data folder; pass the game data folder")
        return data_dir
    return source


def find_assemblies(source: Path, names: tuple[str, ...], max_files: int = 24) -> tuple[list[Path], list[str]]:
    source = source.expanduser().resolve(strict=True)
    source = input_root(source)
    if source.is_symlink():
        raise ValueError("Symlink inputs are not accepted")
    for name in names:
        if not VALID_DLL.fullmatch(name) or name.startswith('.'):
            raise ValueError("Assembly name must be a simple DLL basename: " + name)
    name_set = {name.lower() for name in names}
    candidates: list[Path] = []
    markers: list[str] = []
    if source.is_file():
        if source.suffix.lower() != '.dll':
            raise ValueError("Pass a Mono DLL or Unity game folder/_Data directory")
        if source.stat().st_size > 256 * 1024 * 1024:
            raise ValueError("Assembly exceeds 256 MB limit")
        return [source], markers
    if not source.is_dir():
        raise ValueError("Input is not a file or directory")
    # Limit traversal to depth <= 6, avoid infinite symlink traversal and huge caches.
    for root, dirs, files in os.walk(source, followlinks=False):
        root_path = Path(root)
        depth = len(root_path.relative_to(source).parts)
        dirs[:] = [x for x in dirs if not (root_path / x).is_symlink() and x not in ('Library','Temp','Logs','.git','node_modules') and depth < 6]
        for filename in files:
            path = root_path / filename
            lower = filename.lower()
            if path.is_symlink():
                continue
            if lower in name_set:
                if path.stat().st_size > 256 * 1024 * 1024:
                    raise ValueError("Assembly exceeds 256 MB limit: " + str(path))
                candidates.append(path.resolve())
            elif lower in ('global-metadata.dat', 'gameassembly.dll', 'libil2cpp.so'):
                markers.append(str(path.relative_to(source)))
    # Prefer DLLs from a game's Managed dir, then deduplicate matching names.
    candidates.sort(key=lambda p: (0 if p.parent.name.lower() == 'managed' else 1, len(p.parts), str(p)))
    selected: list[Path] = []
    used_names: set[str] = set()
    for p in candidates:
        if p.name.lower() in used_names:
            continue
        used_names.add(p.name.lower())
        selected.append(p)
        if len(selected) >= max_files:
            break
    return selected, markers[:30]


def recover(source: Path, out: Path, *, ilspy: str | None = None,
            install: bool = True, extra_assembly: tuple[str, ...] = (), timeout: int = 900,
            max_files: int = 24) -> dict[str, Any]:
    source = source.expanduser().resolve(strict=True)
    out = out.expanduser().resolve()
    if out == source or source in out.parents or out in source.parents:
        raise ValueError("Output and input must be separate, without overlapping paths")
    if out.exists() and any(out.iterdir()):
        raise ValueError("Output destination must be empty: " + str(out))
    names = DEFAULT_DLLS + extra_assembly
    assemblies, il2cpp = find_assemblies(source, names, max_files=max_files)
    if not assemblies:
        if il2cpp:
            raise RuntimeError("IL2CPP game detected (" + ", ".join(il2cpp[:4]) + "): ILSpy cannot recover native IL2CPP gameplay. Use an IL2CPP-specific authorized workflow.")
        raise RuntimeError("Mono Assembly-CSharp.dll not found. Specify a Unity *_Data folder or managed DLL")
    executable = resolve_ilspy(ilspy, install=install)
    version_result = subprocess.run([executable, '--version'], capture_output=True, text=True, timeout=30)
    if version_result.returncode != 0:
        raise RuntimeError("ILSpyCmd is not runnable: " + (version_result.stderr or '')[-700:])
    version = (version_result.stdout or version_result.stderr).strip()[:256]
    if ilspy is None and ILSPY_VERSION not in version:
        raise RuntimeError("Expected pinned ILSpyCmd " + ILSPY_VERSION + ", found " + version)
    out.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {
        'tool': 'ILSpyCmd', 'tool_expected_version': ILSPY_VERSION, 'tool_actual_version': version,
        'source': str(source), 'assemblies': [], 'il2cpp_markers': il2cpp,
        'mode': 'managed_csharp_source_only', 'playable_html': False,
    }
    for assembly in assemblies:
        relative_name = assembly.stem
        target = out / 'csharp' / relative_name
        target.mkdir(parents=True, exist_ok=True)
        cmd = [executable, '--disable-updatecheck', '--project', '--nested-directories',
               '--outputdir', str(target), '--referencepath', str(assembly.parent), str(assembly)]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            raise RuntimeError(f"ILSpy failed on {assembly.name}: " + (result.stderr or result.stdout)[-1200:])
        sources = sorted(target.rglob('*.cs'))
        if not sources:
            raise RuntimeError("No decompiled C# files produced for " + assembly.name)
        manifest['assemblies'].append({
            'name': assembly.name, 'source_path': str(assembly), 'sha256': sha256(assembly),
            'folder': str(target.relative_to(out)), 'cs_files': len(sources),
            'project_files': len(list(target.rglob('*.csproj'))),
        })
    (out / 'ilspy_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Recover authorized Unity MONO C# with real ILSpyCmd")
    parser.add_argument('source', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--ilspy', help='Optional existing ILSpyCmd executable')
    parser.add_argument('--no-install', action='store_true', help='Require locally installed ILSpyCmd')
    parser.add_argument('--extra-assembly', action='append', default=[], help='Additional .dll filename to include')
    parser.add_argument('--timeout', type=int, default=900)
    args = parser.parse_args()
    if args.timeout < 1 or args.timeout > 7200:
        parser.error('timeout must be 1..7200 seconds')
    result = recover(args.source, args.out, ilspy=args.ilspy, install=not args.no_install,
                     extra_assembly=tuple(args.extra_assembly), timeout=args.timeout)
    print("ILSpy recovered " + str(sum(x['cs_files'] for x in result['assemblies'])) +
          " decompiled C# source files into " + str(args.out))
    if result['il2cpp_markers']:
        print('WARNING: IL2CPP markers also present; extracted managed DLLs may not represent the full game', file=sys.stderr)


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as e:
        sys.exit('ERROR: ' + str(e))
