#!/usr/bin/env python3
"""Gap-targeted OSS scouting. Never downloads/executes repository code or installs dependencies."""
import argparse
import datetime as dt
import json
import os
import sys
import urllib.parse
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUERIES = {
    "managed_gameplay": "C# .NET managed assembly decompiler Unity",
    "unity_assets": "Unity asset texture mesh extractor",
    "world_streaming": "voxel chunk meshing streaming engine",
    "sprite_stack_fidelity": "sprite stacking volumetric 3D PNG slicing",
    "offline_dependencies": "JavaScript bundle single file offline wasm",
    "mobile_controls": "touch game joystick JavaScript",
    "geometry_optimization": "meshoptimizer gltf compression WebGL",
    "actor_animation": "sprite atlas animation frame exporter"
}
ALLOWED = {"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "Zlib"}
SEPARATE_ONLY = {"GPL-3.0", "GPL-3.0-only", "GPL-3.0-or-later", "AGPL-3.0", "AGPL-3.0-only", "MPL-2.0"}


def github(path, token):
    req = urllib.request.Request("https://api.github.com"+path,headers={
        "Accept": "application/vnd.github+json", "User-Agent": "Blockwild-Evolution-OSS-Scout/0.1",
        **({"Authorization":"Bearer "+token} if token else {})})
    with urllib.request.urlopen(req,timeout=12) as response:
        return json.load(response)


def rank(repo, desired):
    lic = ((repo.get("license") or {}).get("spdx_id") or "UNKNOWN")
    score = (55 if desired.lower() in (repo.get("description") or "").lower() else 25)
    if lic in ALLOWED: score += 24
    elif lic in SEPARATE_ONLY: score += 5
    else: score -= 50
    if repo.get("archived") or repo.get("disabled"): score -= 60
    if repo.get("pushed_at"):
        try:
            if (dt.datetime.now(dt.timezone.utc)-dt.datetime.fromisoformat(repo["pushed_at"].replace("Z","+00:00"))).days < 365: score += 10
        except ValueError: pass
    score += min(8,int(repo.get("stargazers_count") or 0)//1000)
    return score


def run(diag, online, max_repos):
    gap = (diag.get("bottlenecks") or [{"id": "unity_assets"}])[0]["id"]
    seeds = json.loads((ROOT / "assets" / "oss-seeds.json").read_text(encoding="utf-8"))["candidates"]
    candidates = []
    query = QUERIES.get(gap,"WebGL 3D game performance")
    for s in seeds:
        if s["purpose"] == gap:
            candidates.append({**s, "source":"curated_seed", "status":"license_reference_only_not_locally_installed", "sha":None})
    result = {"schema":"blockwild-evolution.scout/1","gap":gap,"query":query,"online_requested":online,
              "online_available":False,"candidates":candidates,"notice":"OSS discovery is not installation or integration."}
    if online:
        try:
            token=os.getenv("GITHUB_TOKEN","")
            response=github("/search/repositories?"+urllib.parse.urlencode({"q":query+" in:name,description,readme", "sort":"updated", "order":"desc", "per_page": min(max_repos,10)}),token)
            result["online_available"]=True
            for x in response.get("items",[]):
                lic = ((x.get("license") or {}).get("spdx_id") or "UNKNOWN")
                if lic == "UNKNOWN": continue
                item = {"repo":x.get("full_name"),"link":x.get("html_url"),"description":x.get("description"),
                        "license":lic,"purpose":gap,"default_branch":x.get("default_branch"),
                        "pushed_at":x.get("pushed_at"),"archived":x.get("archived"),
                        "score":rank(x,gap),"status":"online_metadata_only_not_reviewed_or_installed","sha":None}
                # The exact revision is pinned if GitHub permits the second request.
                try:
                    sha=github("/repos/"+x["full_name"]+"/commits/"+urllib.parse.quote(x["default_branch"],safe=""),token).get("sha")
                    if isinstance(sha,str) and len(sha)==40: item["sha"]=sha
                except (urllib.error.URLError, TimeoutError, KeyError): pass
                candidates.append(item)
        except (urllib.error.HTTPError,urllib.error.URLError,TimeoutError) as err:
            result["online_error"]=str(err)
    unique={}
    for a in candidates:
        k=a["repo"].lower()
        if k not in unique or (a.get("sha") and not unique[k].get("sha")):
            unique[k]=a
    result["candidates"] = sorted(unique.values(),key=lambda a:a.get("score",0),reverse=True)[:max_repos]
    return result


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--diagnosis",required=True)
    ap.add_argument("--online",action="store_true")
    ap.add_argument("--max",type=int,default=6)
    ap.add_argument("--json")
    a=ap.parse_args()
    data=json.loads(Path(a.diagnosis).read_text(encoding="utf-8"))
    res=run(data,a.online,max(1,min(a.max,15)))
    output=json.dumps(res,ensure_ascii=False,indent=2)+"\n"
    if a.json: Path(a.json).write_text(output,encoding="utf-8")
    else: print(output)

if __name__=="__main__":
    main()
