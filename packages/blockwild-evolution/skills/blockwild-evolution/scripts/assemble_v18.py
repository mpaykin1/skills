#!/usr/bin/env python3
"""Source-preserving GPU diorama extension for the owner's existing v17 autonomous HTML."""
from pathlib import Path
import argparse,hashlib
p=argparse.ArgumentParser();p.add_argument('original',type=Path);p.add_argument('out',type=Path)
p.add_argument('--assets',type=Path,default=Path('build/blockwild_gpu18/gpu_volumes.json'))
a=p.parse_args()
s=a.original.read_text();atlas=a.assets.read_text()
js=(Path(__file__).parent/'gpu_v18_renderer.js').read_text()
needle='__BW18_GPU_VOLUME_DATA__';assert needle in js
js=js.replace(needle,atlas)
ending='</script>\n</body></html>'
assert ending in s[-500:], 'v17 original end-of-file marker missing, refusing modification'
assert 'const BW18 =' not in s, 'Refusing to double-inject GPU bridge'
result=s.replace(ending,'\n'+js+'\n'+ending)
a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(result)
assert result.startswith(s[:s.rindex(ending)]),'original game payload changed'
print('HTML',a.out,'bytes',a.out.stat().st_size,'SHA256',hashlib.sha256(a.out.read_bytes()).hexdigest())
