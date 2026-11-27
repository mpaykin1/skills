#!/usr/bin/env python3
import argparse,json
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument("log",type=Path);p.add_argument("--expect")
a=p.parse_args();errors=[]
for line in a.log.read_text().splitlines():
 if not line.startswith("VVL_ERROR|"):continue
 _,ident,message=line.split("|",2);s=(ident+" "+message).lower()
 if any(k in s for k in ("sync-hazard","barrier","layout","lifetime","destroy")):skills=["game-style-forge","godot-game-to-html"]
 elif any(k in s for k in ("shader","pipeline","spir-v")):skills=["game-style-forge","glslang-shader-bridge"]
 elif any(k in s for k in ("image","texture","descriptor","sampler")):skills=["game-style-forge","godot-game-to-html","sprite-stacking-grunge"]
 elif any(k in s for k in ("buffer","vertex","index")):skills=["game-style-forge","meta-game-fusion","blender-model-animation-enhancer"]
 else:skills=["skill-synergy-manager"]
 errors.append({"vuid":ident,"skills":skills,"message":message})
print(json.dumps({"errors":errors,"scope":"native Vulkan only; routing hints require source inspection"},ensure_ascii=False))
if a.expect and [e["vuid"] for e in errors]!=[a.expect]:raise SystemExit(1)
