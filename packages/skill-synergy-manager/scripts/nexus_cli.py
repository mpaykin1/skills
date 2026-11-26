#!/usr/bin/env python3
"""Nexus CLI dispatcher: discovery and execution of explicitly selected upstream harnesses."""
import argparse, json, os, shutil, subprocess, sys
from pathlib import Path

REG = json.loads((Path(__file__).resolve().parents[1] / "assets/nexus-cli-registry.json").read_text())
def check(name):
    spec = REG["tools"][name]
    exe = shutil.which("cli-anything-" + name)
    native = next((p for n in spec["native"] if (p := shutil.which(n))), None)
    # Presence is not execution verification; some backends require a service or GUI.
    return {"tool": name, "harness": exe, "native": native,
            "status": "candidate" if exe and native else "backend_unverified" if exe else "missing_harness"}

def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("inventory")
    h = sub.add_parser("help-tool")
    h.add_argument("tool", choices=REG["tools"])
    r = sub.add_parser("run")
    r.add_argument("--workspace", required=True)
    r.add_argument("--timeout", type=int, default=120)
    r.add_argument("tool", choices=REG["tools"])
    r.add_argument("arguments", nargs=argparse.REMAINDER)
    a = p.parse_args()
    if a.cmd == "inventory":
        print(json.dumps([check(n) for n in REG["tools"]], indent=2))
        return 0
    s = check(a.tool)
    if not s["harness"]:
        print(json.dumps(s), file=sys.stderr)
        return 3
    if a.cmd == "help-tool":
        return subprocess.run([s["harness"], "--help"], timeout=30).returncode
    ws = Path(a.workspace).resolve(strict=True)
    if not ws.is_dir() or not 1 <= a.timeout <= 900:
        p.error("workspace must be a directory; timeout 1..900")
    args = a.arguments
    if args[:1] == ["--"]:
        args = args[1:]
    if not args:
        p.error("explicit reviewed tool arguments required")
    # No shell, no ambient auth tokens; not an OS sandbox. Run trusted commands only.
    env = {k:v for k,v in os.environ.items() if k in ("PATH","HOME","LANG","LC_ALL","TMPDIR","DISPLAY","XDG_RUNTIME_DIR","VIRTUAL_ENV")}
    try:
        return subprocess.run([s["harness"], *args], cwd=ws, env=env, timeout=a.timeout).returncode
    except subprocess.TimeoutExpired:
        print("tool timeout", file=sys.stderr)
        return 124

if __name__ == "__main__":
    sys.exit(main())
