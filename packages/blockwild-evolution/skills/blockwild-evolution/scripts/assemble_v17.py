from pathlib import Path
import argparse, json,hashlib
p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--assets',type=Path,default=Path('v17_assets.json'));p.add_argument('--probe',action='store_true');args=p.parse_args()
s=args.base.read_text()
a=json.loads(args.assets.read_text());assert len(a)==4
j='\nconst BW17_SPRITES='+json.dumps(a,separators=(',',':'))+';\n'+(Path(__file__).resolve().parent.parent/'templates/v17_sunlit_volume.js').read_text()+'\n'
if args.probe:
 marker='function gameLoop(){';assert marker in s and s.count(marker)==1
 s=s.replace(marker,j+'\n'+marker,1)
else:
 marker="// Load from this file's embedded original gzip asynchronously; fallback remains playable."
 assert marker in s and s.count(marker)==1
 prefix=s[:s.index('const ROYAL_ART={SPRITES:')]
 s=s.replace(marker,j+marker,1)
 assert s[:s.index('const ROYAL_ART={SPRITES:')]==prefix
s=s.replace('BLOCKWILD v16 · Royal Volume Garden · Offline','BLOCKWILD v17 · Living Light Garden · Offline')
s=s.replace('BLOCKWILD v16','BLOCKWILD v17',1)
args.out.parent.mkdir(parents=True,exist_ok=True)
args.out.write_text(s)
print('WRITTEN',args.out,'bytes',args.out.stat().st_size,'sha256',hashlib.sha256(args.out.read_bytes()).hexdigest())
