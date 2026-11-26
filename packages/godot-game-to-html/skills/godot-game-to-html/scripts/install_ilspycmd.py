#!/usr/bin/env python3
"""Install the official ILSpyCmd NuGet dotnet tool in an isolated user cache.

This downloads only when invoked; it never vendors ILSpy binaries into the skill.
Repository: https://github.com/icsharpcode/ILSpy (MIT).
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

VERSION = "11.2.0.10050"
CACHE = Path.home() / ".cache" / "godot-unity-to-html" / "ilspycmd" / VERSION


def installed_path(root: Path = CACHE) -> Path:
    return root / ("ilspycmd.exe" if os.name == "nt" else "ilspycmd")


def resolve(executable: str | None = None, install: bool = False) -> str:
    if executable:
        candidate = Path(executable).expanduser().resolve(strict=True)
        if not candidate.is_file():
            raise ValueError("ILSpyCmd is not a file: " + str(candidate))
        return str(candidate)
    env = os.environ.get("ILSPYCMD_EXE")
    if env:
        return resolve(env)
    candidate = installed_path()
    if candidate.is_file():
        return str(candidate)
    found = shutil.which("ilspycmd")
    if found:
        return found
    if install:
        return install_tool()
    raise RuntimeError("ILSpyCmd missing. Use --install-ilspy (requires .NET SDK 10+), or --ilspy /path/to/ilspycmd")


def install_tool() -> str:
    exe = installed_path()
    if exe.is_file():
        return str(exe)
    dotnet = shutil.which("dotnet")
    if not dotnet:
        raise RuntimeError(".NET SDK >= 10.0.100 is required for installing ilspycmd 11.2. See https://dotnet.microsoft.com/download")
    probe = subprocess.run([dotnet, "--version"], capture_output=True, text=True, check=True, timeout=30)
    version = probe.stdout.strip()
    parts = version.split("-")[0].split(".")
    try:
        if tuple(int(x) for x in parts[:3]) < (10, 0, 100):
            raise RuntimeError("ILSpyCmd 11.2 requires .NET SDK >= 10.0.100. Current: " + version)
    except (IndexError, ValueError) as e:
        raise RuntimeError("Cannot recognize dotnet SDK version: " + version) from e
    dest = CACHE
    dest.mkdir(parents=True, exist_ok=True)
    # Official NuGet feed; no --global and no modifications to the user's dotnet tools.
    cmd = [dotnet, "tool", "install", "ilspycmd", "--version", VERSION,
           "--tool-path", str(dest), "--source", "https://api.nuget.org/v3/index.json"]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=480)
    if result.returncode != 0:
        raise RuntimeError("Official ilspycmd installation failed: " + (result.stderr or result.stdout)[-1300:])
    if not exe.is_file():
        raise RuntimeError("ilspycmd installation did not create expected executable: " + str(exe))
    return str(exe)


def main() -> None:
    parser = argparse.ArgumentParser(description="Install pinned MIT ILSpyCmd without modifying global dotnet tools")
    parser.add_argument("--check", action="store_true", help="Only locate already installed ILSpyCmd")
    args = parser.parse_args()
    print(resolve(install=not args.check))


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, ValueError, subprocess.SubprocessError) as e:
        sys.exit("ERROR: " + str(e))
