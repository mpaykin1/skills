#!/usr/bin/env python3
"""Record exact OSS provenance only when the real adapter and new game artifacts exist."""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

SAFE = {"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "Zlib"}
SEPARATE = {"GPL-3.0", "GPL-3.0-only", "GPL-3.0-or-later", "AGPL-3.0", "MPL-2.0"}

def sha(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024), b""): h.update(b)
    return h.hexdigest()

def main():
    ap=argparse.ArgumentParser(description="Admission provenance gate: no code execution")
    ap.add_argument("--scout",required=True)
    ap.add_argument("--repo",required=True)
    ap.add_argument("--adapter",required=True)
    ap.add_argument("--game",required=True)
    ap.add_argument("--license-file",required=True)
    ap.add_argument("--output",required=True)
    a=ap.parse_args()
    scout=json.loads(Path(a.scout).read_text(encoding="utf-8"))
    c=next((x for x in scout.get("candidates",[]) if x.get("repo","").lower()==a.repo.lower()),None)
    if c is None: ap.error("Repository is absent from actual scout results")
    if c.get("license") not in SAFE|SEPARATE: ap.error("Unverified or unsupported license")
    if not re.fullmatch(r"[a-fA-F0-9]{40}", c.get("sha") or ""):
        ap.error("Exact upstream commit SHA is required; seed metadata alone is insufficient")
    paths=[Path(a.adapter),Path(a.game),Path(a.license_file)]
    if any(not p.is_file() or p.stat().st_size<30 for p in paths): ap.error("Adapter, new game, and reviewed license must exist as nonempty files")
    record={"schema":"blockwild-evolution.oss-admission/1", "status":"review_ready_not_runtime_verified",
            "upstream_repo":c["repo"],"upstream_sha":c["sha"],"license":c["license"],
            "license_mode": "isolated-tool-review-required" if c["license"] in SEPARATE else "library-license-and-notices-review-required",
            "artifacts":{n:{"sha256":sha(p),"bytes":p.stat().st_size} for n,p in zip(("adapter","game","license"),paths)},
            "warning":"This proves pinned provenance + existing output files, not correct gameplay/visual fidelity or executed installation."}
    Path(a.output).write_text(json.dumps(record,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(str(a.output))

if __name__=="__main__":
    main()
