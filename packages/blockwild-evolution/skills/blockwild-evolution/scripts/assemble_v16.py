"""Rebuild an offline BLOCKWILD v16 from the owner's v15 HTML and approved
reference image material. The original world's embedded data is never edited.
The 3D-authored sprites must be baked with build_v16_volume_props.py first.
"""
from pathlib import Path
import argparse,base64,hashlib,json
P=argparse.ArgumentParser(description='Build fully embedded offline BLOCKWILD v16')
P.add_argument('--base-html',type=Path,required=True)
P.add_argument('--assets-json',type=Path,required=True)
P.add_argument('--stone-texture',type=Path,required=True)
P.add_argument('--out-html',type=Path,required=True)
P.add_argument('--base-probe',type=Path,default=None)
P.add_argument('--out-probe',type=Path,default=None)
a=P.parse_args()
templates=Path(__file__).resolve().parent.parent/'templates'
assets=json.loads(a.assets_json.read_text())
if len(assets)!=11:raise ValueError('Need exactly 11 source-volume props, received '+str(len(assets)))
for k,v in assets.items():
 if not k.startswith('v16_') or 'data:image/png;base64,' not in v['uri'] or 'layers' not in v:
  raise ValueError('Invalid named source-volume sprite '+k)
stone='data:image/png;base64,'+base64.b64encode(a.stone_texture.read_bytes()).decode()
new='\n// BLOCKWILD v16 — generated true volumetric RGBA additions\nconst BW16_EXTRA_SPRITES='+json.dumps(assets,separators=(',',':'))+';\n'+'const BW16_STONE_ALBEDO='+json.dumps(stone)+';\n'+(templates/'v16_floor.js').read_text()+'\n'+(templates/'v16_scene.js').read_text()+'\n'
floor_marker=' // A second shallow garden canal with copings on the front-left path,'
marker="// Load from this file's embedded original gzip asynchronously; fallback remains playable."
source=a.base_html.read_text()
if source.count(marker)!=1 or source.count(floor_marker)!=1 or 'const BW16_EXTRA_SPRITES' in source:
 raise ValueError('Expected intact v15 base with exactly one insertion point')
worlddata_before=source[:source.index('const ROYAL_ART={SPRITES:')]
source=source.replace(floor_marker,' bw16DrawFloorTexture(g,W,H,U,center);\n'+floor_marker,1)
source=source.replace(marker,new+marker,1)
source=source.replace('<title>BLOCKWILD — V11 · Enhanced Materials and Light · Offline</title>',
'<title>BLOCKWILD v16 · Royal Volume Garden · Offline</title>',1)
# Ensure source world's embedded data survived untouched (except the HTML title)
worlddata_after=source[:source.index('const ROYAL_ART={SPRITES:')]
worlddata_after=worlddata_after.replace('<title>BLOCKWILD v16 · Royal Volume Garden · Offline</title>',
'<title>BLOCKWILD — V11 · Enhanced Materials and Light · Offline</title>',1)
if worlddata_before!=worlddata_after:raise RuntimeError('Source archive changed during build')
a.out_html.parent.mkdir(parents=True,exist_ok=True);a.out_html.write_text(source)
if a.base_probe:
 if not a.out_probe:raise ValueError('--out-probe required with --base-probe')
 probe=a.base_probe.read_text()
 if floor_marker not in probe or 'function gameLoop(){' not in probe:raise ValueError('Unsupported standalone art-probe')
 probe=probe.replace(floor_marker,' bw16DrawFloorTexture(g,W,H,U,center);\n'+floor_marker,1)
 probe=probe.replace('function gameLoop(){',new+'\nfunction gameLoop(){',1)
 a.out_probe.write_text(probe)
print('Build',a.out_html,a.out_html.stat().st_size,'SHA256',hashlib.sha256(a.out_html.read_bytes()).hexdigest())
