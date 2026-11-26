"""Apply only the selected lighting changes, never camera or geometry."""
import argparse,json,sys
from pathlib import Path
import bpy
p=argparse.ArgumentParser();p.add_argument('--recipe',required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);r=json.loads(a.recipe)
if a.out.exists():raise FileExistsError(a.out)
c=bpy.data.collections.get('CSD Directing')
if not c:raise ValueError('Missing director collection')
for o in c.objects:
    if o.type=='LIGHT':
        o.data.energy*=r['energy'][o.name.removeprefix('CSD ')]
        if o.data.type=='AREA':o.data.size*=r['size']
bpy.ops.wm.save_as_mainfile(filepath=str(a.out.resolve()))
