#!/usr/bin/env python3
"""Read-only BLOCKWILD source/HTML census. No third-party imports, no archive extraction."""
import argparse
import hashlib
import json
import os
import re
import sys
import zipfile
from pathlib import Path


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def scan_zip(path):
    out = {"present": False}
    if not path:
        return out
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"ZIP not found: {p}")
    with zipfile.ZipFile(p) as z:
        infos = [i for i in z.infolist() if not i.is_dir()]
        by_ext = {}
        for i in infos:
            k = Path(i.filename).suffix.lower() or "(no extension)"
            e = by_ext.setdefault(k, {"files": 0, "uncompressed_bytes": 0})
            e["files"] += 1
            e["uncompressed_bytes"] += i.file_size
        unity_assets = [i for i in infos if re.search(r"(?:\.assets$|\.bundle$|\.resS$|\.resource$|/resources\.assets$)", i.filename, re.I)]
        managed = [i for i in infos if "/managed/" in i.filename.lower() and i.filename.lower().endswith(".dll")]
        game_dll = [i for i in managed if i.filename.lower().endswith("bw.runtime.dll")]
        voxel = [i for i in infos if i.filename.lower().endswith(("continent.bin", "capital.bin"))]
        out = {
            "present": True,
            "filename": p.name,
            "size_bytes": p.stat().st_size,
            "sha256": sha256(p),
            "entries": len(infos),
            "total_uncompressed_bytes": sum(i.file_size for i in infos),
            "by_extension": by_ext,
            "unity_assets_files": len(unity_assets),
            "unity_assets_uncompressed_bytes": sum(i.file_size for i in unity_assets),
            "managed_dlls": len(managed),
            "bw_runtime_dll": bool(game_dll),
            "bw_runtime_size_bytes": game_dll[0].file_size if game_dll else None,
            "original_world_binary_files": [i.filename for i in voxel],
            "native_unity_project_source_detected": any(i.filename.endswith(".unity") or i.filename.endswith(".unitypackage") for i in infos),
        }
    return out


def scan_html(path):
    if not path:
        return {"present": False}
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"HTML not found: {p}")
    b = p.read_bytes()
    s = b.decode("utf-8", "replace")
    # These regexes only identify explicit network dependencies, not arbitrary URLs in notes or licenses.
    external = sorted(set(re.findall(r'''(?:src|href)\s*=\s*["'](https?://[^"']+)''', s, re.I)))
    js_network = sorted(set(re.findall(r'''\b(?:fetch|importScripts)\s*\(\s*["'](https?://[^"']+)''', s)))
    out = {
        "present": True,
        "filename": p.name,
        "size_bytes": len(b),
        "sha256": hashlib.sha256(b).hexdigest(),
        "contains_inline_js": bool(re.search(r"<script(?![^>]*\bsrc=)", s, re.I)),
        "script_count": len(re.findall(r"<script\b", s, re.I)),
        "uses_webgl2": "webgl2" in s.lower(),
        "uses_request_animation_frame": "requestAnimationFrame" in s,
        "uses_sprite_stack": bool(re.search(r"sprite.?stack|stackLayer|stack_atlas|stackAtlas", s, re.I)),
        "uses_world_chunk_loader": bool(re.search(r"loadNative|loadAllNative|loadSource|loadChunk|chunkIndex|sourceAtlas|atlasScreenPoint", s, re.I)),
        "uses_gzip_decoder": "DecompressionStream" in s,
        "uses_touch_controls": bool(re.search(r"touchstart|touchmove|pointerdown|id=.stick.|id=.joystick.", s, re.I)),
        "uses_audio": "<audio" in s.lower() or "AudioContext" in s,
        "explicit_external_urls": external,
        "explicit_network_script_urls": js_network,
        "runtime_network_free_static_check": not (external or js_network),
        "embedded_source_data_identifiers": [x for x in ("CAPITAL", "CONTINENT", "SOURCE_VOXELS", "SOURCE_ATLAS") if x in s],
        "full_gameplay_parity": None,
        "runtime_frame_rate": None,
        "actual_source_model_import_coverage": None,
        "actual_actor_animations_verified": None,
        "sprite_stack_coverage_verified": None,
    }
    return out


def weaknesses(src, html):
    items = []
    if src.get("bw_runtime_dll"):
        items.append({"id": "managed_gameplay", "priority": 100,
                      "reason": "Managed BW.Runtime.dll is present in original ZIP; parity with HTML not established",
                      "evidence": "source ZIP /Managed/BW.Runtime.dll", "confidence": "high"})
    if src.get("unity_assets_files", 0):
        items.append({"id": "unity_assets", "priority": 96,
                      "reason": "Unity serialized assets exist; original asset recovery/visual parity is unverified",
                      "evidence": f"{src['unity_assets_files']} Unity asset file(s) in ZIP", "confidence": "high"})
    if html.get("uses_world_chunk_loader") and src.get("original_world_binary_files"):
        items.append({"id": "world_streaming", "priority": 75,
                      "reason": "Source world and loader exist; boundary/collision/memory behavior requires browser validation",
                      "evidence": "source binary and chunk/atlas loader signals", "confidence": "medium"})
    if html.get("uses_sprite_stack"):
        items.append({"id": "sprite_stack_fidelity", "priority": 66,
                      "reason": "Stacking code found; coverage must be measured against original mesh/voxel inventory",
                      "evidence": "render-source markers in HTML", "confidence": "medium"})
    if not html.get("runtime_network_free_static_check", True):
        items.append({"id": "offline_dependencies", "priority": 97,
                      "reason": "Explicit external dependencies in an HTML advertised as offline",
                      "evidence": "HTML src/href or literal remote fetch", "confidence": "high"})
    if not html.get("uses_touch_controls", False):
        items.append({"id": "mobile_controls", "priority": 85,
                      "reason": "No touch control markers found (static heuristic only)",
                      "evidence": "HTML source search", "confidence": "low"})
    if not html.get("present"):
        items.append({"id": "missing_html", "priority": 110,
                      "reason": "No playable HTML provided", "evidence": "file list", "confidence": "high"})
    if not src.get("present"):
        items.append({"id": "missing_source", "priority": 105,
                      "reason": "Original source ZIP unavailable", "evidence": "file list", "confidence": "high"})
    return sorted(items, key=lambda x: x["priority"], reverse=True)


def diagnose(zip_path=None, html_path=None):
    src, html = scan_zip(zip_path), scan_html(html_path)
    return {"schema": "blockwild-evolution.diagnosis/1", "source_zip": src, "offline_html": html,
            "bottlenecks": weaknesses(src, html),
            "coverage": {"original_data_embedded": None, "original_gameplay_recovered": None,
                         "original_unity_models_extracted": None, "verified_visible_sprites": None},
            "notes": "Percentages left null until independently measured. No browser run performed by this scan."}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", dest="zip_path", help="Original Windows game ZIP")
    ap.add_argument("--html", dest="html_path", help="Current standalone HTML")
    ap.add_argument("--json", dest="json_path", help="Write JSON here")
    args = ap.parse_args()
    obj = diagnose(args.zip_path, args.html_path)
    pretty = json.dumps(obj, ensure_ascii=False, indent=2)
    if args.json_path:
        Path(args.json_path).write_text(pretty + "\n", encoding="utf-8")
    else:
        print(pretty)

if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, zipfile.BadZipFile, ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(2)
