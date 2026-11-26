#!/usr/bin/env python3
"""Make an arranged GLB city from authentic user-art facade volumes.
Rendering / infinite-city runtime uses Three.js; this script exports geometry only.
"""
import argparse
import json
from pathlib import Path
import numpy as np
import trimesh


def build(asset_folder, output_path, seed=11, cols=8, rows=3):
    folder=Path(asset_folder)
    assets={k:folder/f'{k}.glb' for k in ('tower','bridge','island')}
    for k,p in assets.items():
        if not p.exists(): raise FileNotFoundError(f'Required {k}: {p}')
    templates={k:trimesh.load(p,force='scene') for k,p in assets.items()}
    rng=np.random.default_rng(seed)
    world=trimesh.Scene()
    layout=[]
    def place(kind,position,scale=1,rotation=0):
        obj=templates[kind]
        j=len(layout)
        position=np.asarray(position,dtype=float)
        m=trimesh.transformations.translation_matrix(position)
        m=m@trimesh.transformations.rotation_matrix(rotation,[0,1,0])
        m=m@trimesh.transformations.scale_matrix(scale)
        for n in obj.graph.nodes_geometry:
            local,gname=obj.graph.get(n)
            mesh=obj.geometry[gname]
            world.add_geometry(mesh,geom_name=f'{kind}_{j}_{gname}',
                               node_name=f'{kind}_{j}_{n}',transform=m@local)
        layout.append({'kind':kind,'position':position.tolist(),
                       'scale':float(scale),'rotation_y':float(rotation)})
    for row in range(rows):
        y=row*20-8
        for col in range(cols):
            x=(col-(cols-1)/2)*16
            kind='tower'
            z=float(rng.uniform(-8,4))
            scale=float(rng.uniform(.75,1.55))
            place(kind,[x+rng.uniform(-2,2),y+rng.uniform(-5,7),z],scale,rng.uniform(-.4,.4))
            if (col+row)%3 == 0:
                place('island',[x+8,y+15+rng.uniform(0,9),z-5],float(rng.uniform(.9,1.4)))
            if col<cols-1 and row%2 == 0:
                place('bridge',[x+8,y+4,z+1],float(rng.uniform(.55,.88)))
    output_path=Path(output_path)
    output_path.parent.mkdir(parents=True,exist_ok=True)
    world.export(output_path,file_type='glb')
    output_path.with_suffix('.json').write_text(json.dumps({'seed':seed,'placements':layout},indent=2),encoding='utf8')
    return len(layout)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('assets_dir');p.add_argument('output');p.add_argument('--seed',type=int,default=11)
    p.add_argument('--cols',type=int,default=8);p.add_argument('--rows',type=int,default=3)
    a=p.parse_args()
    print(f'{build(a.assets_dir,a.output,a.seed,a.cols,a.rows)} placed models -> {a.output}')
if __name__=='__main__':main()
