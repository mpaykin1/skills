#!/usr/bin/env python3
"""Validate exact generated ESSL vertex/fragment pairs without a GPU."""
import argparse,json,re,shutil,subprocess,sys
from pathlib import Path

def main():
 p=argparse.ArgumentParser()
 p.add_argument("manifest",type=Path)
 a=p.parse_args()
 root=a.manifest.resolve(strict=True).parent
 exe=shutil.which("glslangValidator") or shutil.which("glslang")
 if not exe: raise RuntimeError("glslang missing; no CPU validation")
 data=json.loads(a.manifest.read_text())
 pairs=data["pairs"]
 if not isinstance(pairs,list) or not pairs: raise ValueError("nonempty pairs required")
 version=subprocess.run([exe,"--version"],capture_output=True,text=True,check=True,timeout=10).stdout.strip()
 seen=set(); results=[]
 for pair in pairs:
  ident=pair["id"]; profile=pair["profile"]
  if not isinstance(ident,str) or not ident or ident in seen: raise ValueError("unique shader id required")
  seen.add(ident)
  if profile not in ("100","300 es"): raise ValueError("explicit WebGL ESSL profile required")
  files=[]
  for key,suffix in (("vertex",".vert"),("fragment",".frag")):
   f=(root/pair[key]).resolve(strict=True)
   if not f.is_relative_to(root) or f.suffix!=suffix or not f.is_file(): raise ValueError("shader outside manifest root or wrong stage")
   src=f.read_text(encoding="utf-8")
   # GLSL permits comments and whitespace before #version. Require an explicit profile.
   head=re.sub(r"/\*.*?\*/|//[^\n]*","",src,flags=re.S).lstrip()
   if not re.match(r"#\s*version\s+"+re.escape(profile)+r"\s*(?:\n|$)",head): raise ValueError(f"{ident}: wrong/missing #version {profile}")
   if re.search(r"^\s*#\s*include\b",head,re.M): raise ValueError(f"{ident}: unresolved include")
   files.append(str(f))
  # Link under OpenGL ES source semantics, not SPIR-V.
  r=subprocess.run([exe,"-l",*files],cwd=root,capture_output=True,text=True,timeout=60)
  results.append({"id":ident,"profile":profile,"pass":r.returncode==0,"exit":r.returncode,"diagnostic":(r.stdout+r.stderr).strip()})
 print(json.dumps({"compiler":version,"scope":"CPU GLSL ES syntax and link only","pairs":results},ensure_ascii=False,indent=2))
 return 0 if all(r["pass"] for r in results) else 1

if __name__=="__main__":
 try: sys.exit(main())
 except (OSError,ValueError,KeyError,TypeError,RuntimeError,subprocess.SubprocessError) as e:
  print(json.dumps({"status":"blocked","reason":str(e)},ensure_ascii=False),file=sys.stderr);sys.exit(2)
