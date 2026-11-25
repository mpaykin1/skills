#!/usr/bin/env python3
"""Derive one actionable improvement cycle from read-only diagnosis and skill contracts."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def cycle(diagnosis, routes):
    problems = diagnosis.get("bottlenecks", [])
    if not problems:
        return {"status": "needs_manual_profile", "message": "No verified issue detected; capture real browser profiles and source parity"}
    p = problems[0]
    mapped = [x for x in routes["routes"] if x["gap"] == p["id"]]
    return {"status": "proposed_not_applied", "bottleneck": p["id"], "priority": p["priority"],
            "reason": p["reason"], "route": mapped,
            "next_action": {
                "managed_gameplay": "Decompile BW.Runtime.dll with pinned ILSpy; map C# systems to actual HTML behavior",
                "unity_assets": "Extract authorized Unity textures/meshes with UnityPy; compare and integrate unmodified originals",
                "world_streaming": "Demonstrate chunk crossing and collider continuity under memory limits",
                "sprite_stack_fidelity": "Build real horizontal RGBA slices from one original mesh or volume and validate 8 views",
                "offline_dependencies": "Inline and verify external runtime dependencies without changes to source game assets",
                "mobile_controls": "Restore fixed mobile joystick and portrait/landscape input",
                "missing_html": "Locate latest valid autonomous HTML and compare with original ZIP",
                "missing_source": "Locate the actual user-provided Windows ZIP"
            }.get(p["id"], "Reproduce problem, apply one improvement and verify rendered behavior"),
            "acceptance": "New independently playable game file; compare before/after, preserve source SHA, no invented progress", 
            "publish": "Only after real browser/asset checks, in a safe game branch. Update this skill only for reusable improvements."}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--diagnosis", required=True)
    ap.add_argument("--routes", default=str(ROOT / "assets" / "skill-routes.json"))
    ap.add_argument("--json")
    a=ap.parse_args()
    data=json.loads(Path(a.diagnosis).read_text())
    routes=json.loads(Path(a.routes).read_text())
    out=json.dumps(cycle(data,routes),ensure_ascii=False,indent=2)
    if a.json: Path(a.json).write_text(out+"\n")
    else: print(out)

if __name__ == "__main__":
    main()
