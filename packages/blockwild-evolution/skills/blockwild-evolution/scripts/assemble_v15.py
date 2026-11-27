"""Non-destructive, deterministic v14 -> v15 single-file HTML assembly."""
from pathlib import Path
import json,hashlib
import argparse
parser=argparse.ArgumentParser(description='Assemble standalone BLOCKWILD v15 from authorized v14 and volume atlas')
parser.add_argument('--base-html',type=Path,required=True)
parser.add_argument('--assets-json',type=Path,required=True)
parser.add_argument('--out-html',type=Path,required=True)
parser.add_argument('--out-probe',type=Path,default=None)
parser.add_argument('--base-probe',type=Path,default=None)
args=parser.parse_args()
W=Path(__file__).resolve().parent.parent/'templates'
replacements=json.loads(args.assets_json.read_text())
fx=(W/'v15_scene.js').read_text()+'\n'+(W/'v15_fx.js').read_text()
START='const ROYAL_ART={SPRITES:'
END='// Load from this file\'s embedded original gzip asynchronously; fallback remains playable.'
ARTPROBE_END='function gameLoop(){'

def patch(source,probe=False):
 i=source.index(START)+len(START)
 old,used=json.JSONDecoder().raw_decode(source[i:])
 assert len(old)==168 and len(replacements)==178
 assert set(old).issubset(replacements)
 # The entire native v14 prefix remains byte-for-byte unchanged.
 source=source[:i]+json.dumps(replacements,separators=(',',':'))+source[i+used:]
 # Lighting-responsive turquoise secondary pool is inserted in the actual 2.5D terrain painter.
 pool=(W/'v15_canal.js').read_text()
 marker=' // The teal reflecting pool is physically beneath its sandstone copings.'
 assert marker in source
 source=source.replace(marker,pool+'\n'+marker,1)
 if probe:
  loc=source.index(ARTPROBE_END)
 else:
  loc=source.index(END)
 source=source[:loc]+fx+'\n'+source[loc:]
 # Wider isometric composition: original physical world coords unchanged,
 # camera reveals pond, original architectures and additional garden props.
 source=source.replace('Math.max(10,Math.min(W/29,H/23,26))','Math.max(8,Math.min(W/38,H/29,24))')
 source=source.replace('Math.max(.44,Math.min(W/400,H/660,1.36))','Math.max(.35,Math.min(W/490,H/880,1.24))')
 return source

p=args.base_html
out=args.out_html
original=p.read_text()
new=patch(original)
out.write_text(new)
probe=(args.base_probe.read_text() if args.base_probe else None)
newProbe=patch(probe,probe=True) if probe else None
# The same in-game BW15Canvas filter applies to both the probe and full HTML.
if args.out_probe and newProbe:
 args.out_probe.write_text(newProbe)
print('SOURCE',p.stat().st_size,'BUILT',out.stat().st_size,'DELTA',out.stat().st_size-p.stat().st_size)
print('NATIVE PREFIX SHA unchanged',hashlib.sha256(original[:original.index(START)].encode()).hexdigest()==hashlib.sha256(new[:new.index(START)].encode()).hexdigest())
print('Assets',len(replacements),'art-probe',len(newProbe) if newProbe else None,'runtime fx',len(fx))
