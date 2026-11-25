#!/usr/bin/env python3
"""Lossless owned-plugin inventory reconciliation. Does not query remote APIs.

Example:
 python scripts/nexus_catalog_sync.py --catalog catalog.json --snapshot snapshot.json --out catalog.updated.json
Requires snapshot.complete=true after all Plugin Creator pages were read. Never
removes catalog entries; missing source files are marked as not_mirrored.
"""
import argparse
import json
from pathlib import Path


def path_is_safe(path):
    return isinstance(path, str) and path.startswith("packages/") and path.endswith("/SKILL.md") and ".." not in Path(path).parts


def sync(current, snapshot):
    if snapshot.get("complete") is not True:
        raise ValueError("snapshot incomplete: refusing to update inventory")
    plugins = snapshot.get("plugins")
    if not isinstance(plugins, list):
        raise ValueError("snapshot.plugins must be an array")
    if not isinstance(current, dict) or not isinstance(current.get("packages"), list):
        raise ValueError("catalog must contain packages array")
    ids = set()
    names = set()
    by_name = {e["name"]: e for e in current["packages"] if isinstance(e, dict) and e.get("name")}
    result = json.loads(json.dumps(current, ensure_ascii=False))
    out = {e["name"]: e for e in result["packages"] if isinstance(e, dict) and e.get("name")}
    changes = []
    for item in plugins:
        if not isinstance(item, dict):
            raise ValueError("plugin entry is not object")
        if item.get("scope") not in ("USER", "WORKSPACE"):
            continue
        pid, name, version = item.get("plugin_id"), item.get("name"), item.get("version")
        if not all(isinstance(v, str) and v for v in (pid, name, version)):
            raise ValueError("plugin has missing id/name/version")
        if pid in ids or name in names:
            raise ValueError("duplicate id/name in snapshot")
        ids.add(pid)
        names.add(name)
        old = out.get(name)
        if old and old.get("plugin_id") not in (None, pid):
            raise ValueError("plugin identity conflict for " + name)
        if old is None:
            source_path = item.get("skill_path")
            if source_path is not None and not path_is_safe(source_path):
                raise ValueError("invalid skill_path for " + name)
            new = {"name": name, "version": version, "plugin_id": pid,
                   "status": "not_mirrored", "files": 0}
            if source_path:
                new["skill"] = source_path
            if isinstance(item.get("modules"), list):
                new["known_modules"] = item["modules"]
            result["packages"].append(new)
            out[name] = new
            changes.append("added " + name)
        else:
            if old.get("version") != version or old.get("plugin_id") != pid:
                old["version"] = version
                old["plugin_id"] = pid
                # A version bump doesn't prove that source mirrors ChatGPT.
                if old.get("status") != "not_mirrored":
                    old["sync_state"] = "source_needs_verification"
                changes.append("changed " + name)
            if isinstance(item.get("modules"), list) and old.get("known_modules") != item["modules"]:
                old["known_modules"] = item["modules"]
                changes.append("modules " + name)
    # Never delete a package simply because it is absent from this snapshot.
    for name in by_name:
        if name not in names and name not in {"dev-6ae2cb844a4c819191d5941f9e371ef7"}:
            pass
    return result, sorted(set(changes))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", type=Path, required=True)
    ap.add_argument("--snapshot", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    raw_catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    updated, changes = sync(raw_catalog, snapshot)
    if changes:
        args.out.write_text(json.dumps(updated, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    elif args.out != args.catalog:
        args.out.write_text(args.catalog.read_text(encoding="utf-8"), encoding="utf-8")
    print(json.dumps({"changed": bool(changes), "changes": changes}, ensure_ascii=False))


if __name__ == "__main__":
    main()
