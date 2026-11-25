#!/usr/bin/env python3
"""Fail-closed preflight for proposed Skill Nexus OSS integrations.

This validates provenance and user-supplied gate metadata, not execution of CI,
visual tests, or licence legal analysis. Run actual checks independently.
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

PERMISSIVE = {"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "Zlib", "0BSD"}
PROTECTED = (".github/workflows/", "meta6/", "protected/", "secrets/", "bots/core/")
FIELDS = ("upstream_url", "upstream_commit", "license_spdx", "plugin_id", "version", "changed_files", "gates")
GATES = ("license", "build", "interop", "visual", "regression")


def preflight(item, root):
    errors = []
    if not isinstance(item, dict):
        return ["candidate must be a JSON object"]
    for key in FIELDS:
        if key not in item:
            errors.append(f"missing: {key}")
    url = item.get("upstream_url", "")
    if not isinstance(url, str) or not re.fullmatch(r"https://(?:www\.)?github\.com/[^/\s]+/[^/\s]+/?", url):
        errors.append("upstream_url must be an exact GitHub repository HTTPS URL")
    commit = item.get("upstream_commit")
    if not isinstance(commit, str) or not re.fullmatch(r"[a-f0-9]{40}", commit):
        errors.append("upstream_commit must be a complete 40-hex commit SHA")
    lic = item.get("license_spdx")
    if lic not in PERMISSIVE:
        errors.append("license requires manual approval or is missing; allowed auto candidates: " + ", ".join(sorted(PERMISSIVE)))
    if not isinstance(item.get("plugin_id"), str) or not item["plugin_id"].startswith(("plugins_", "plugin_", "Plugin_")):
        errors.append("plugin_id must be an existing verified backend plugin ID")
    if not isinstance(item.get("version"), str) or not re.fullmatch(r"\d+\.\d+\.\d+", item["version"]):
        errors.append("version must be SemVer MAJOR.MINOR.PATCH")
    files = item.get("changed_files")
    if not isinstance(files, list) or not files:
        errors.append("changed_files must be nonempty")
    else:
        seen = set()
        for f in files:
            if not isinstance(f, dict) or not isinstance(f.get("path"), str):
                errors.append("file entry requires path and sha256")
                continue
            name = f["path"]
            safe = (Path(name).as_posix() == name and not name.startswith("/") and
                    ".." not in Path(name).parts and not any(name.startswith(p) for p in PROTECTED))
            if not safe or name in seen:
                errors.append(f"unsafe or duplicate path: {name}")
                continue
            seen.add(name)
            path = root / name
            try:
                if not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
                    raise ValueError("missing or outside root")
                actual = hashlib.sha256(path.read_bytes()).hexdigest()
                if actual != f.get("sha256"):
                    errors.append(f"sha256 mismatch: {name}")
            except (OSError, ValueError) as ex:
                errors.append(f"invalid file {name}: {ex}")
    gates = item.get("gates", {})
    if not isinstance(gates, dict):
        errors.append("gates must be an object")
    else:
        for name in GATES:
            if gates.get(name) != "pass":
                errors.append(f"gate not pass: {name}")
        if item.get("affects_game") and gates.get("gameplay") != "pass":
            errors.append("gameplay gate not pass")
        if item.get("affects_performance") and gates.get("benchmark") != "pass":
            errors.append("benchmark gate not pass")
    return errors


def main():
    p = argparse.ArgumentParser()
    p.add_argument("candidate", type=Path)
    p.add_argument("--root", type=Path, default=Path.cwd())
    args = p.parse_args()
    try:
        item = json.loads(args.candidate.read_text(encoding="utf-8"))
        errors = preflight(item, args.root)
    except (OSError, ValueError, json.JSONDecodeError) as ex:
        errors = [str(ex)]
    for problem in errors:
        print(problem, file=sys.stderr)
    print("PASS (metadata preflight only)" if not errors else "BLOCKED")
    return 1 if errors else 0

if __name__ == "__main__":
    sys.exit(main())
