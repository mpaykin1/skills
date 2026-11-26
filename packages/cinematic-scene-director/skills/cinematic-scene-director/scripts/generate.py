#!/usr/bin/env python3
import argparse, json, subprocess
from pathlib import Path
p=argparse.ArgumentParser(); p.add_argument('--repo',type=Path,required=True); p.add_argument('--python',type=Path,required=True); p.add_argument('--out',type=Path,required=True); p.add_argument('--room',choices=['DiningRoom','Bathroom','Bedroom','Kitchen','LivingRoom'],default='LivingRoom'); p.add_argument('--seeds',nargs='+',type=int,default=[0]); p.add_argument('--fast',action='store_true'); a=p.parse_args()
repo=a.repo.resolve(); exe=a.python.resolve(); out=a.out.resolve(); out.mkdir(parents=True,exist_ok=True)
commit=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()
for seed in dict.fromkeys(a.seeds):
    dest=out/f'seed-{seed}'; dest.mkdir(exist_ok=False)
    cmd=[str(exe),'-m','infinigen_examples.generate_indoors','--seed',str(seed),'--task','coarse','--output_folder',str(dest),'-g','singleroom.gin']
    if a.fast: cmd.append('fast_solve.gin')
    cmd+=['-p','compose_indoors.terrain_enabled=False',f'restrict_solving.restrict_parent_rooms=["{a.room}"]']
    subprocess.run(cmd,cwd=repo,check=True)
    if not (dest/'scene.blend').is_file(): raise RuntimeError('Infinigen did not produce scene.blend')
    (dest/'source.json').write_text(json.dumps({'commit':commit,'seed':seed,'room':a.room,'preview':a.fast},indent=2))
