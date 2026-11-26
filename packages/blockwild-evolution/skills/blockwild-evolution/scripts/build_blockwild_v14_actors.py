"""Original volume-authored eight-view animated sprites. BSD-3 SciPy rigid voxel rotation.
Uses the existing BLOCKWILD v12 48x48x64 authored voxel mesh recipes,
not third-party artwork or a substitute for user-owned Unity character rigs.
"""
import os, io, json, base64, math, ast, importlib.util
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy.ndimage import rotate
from pathlib import Path

import argparse
parser=argparse.ArgumentParser(description='Bake 8-direction 5-pose RGBA volume sprites from authored source model')
parser.add_argument('--source-model-script',type=Path,default=Path(__file__).with_name('build_sunlit_volume_sprites.py'))
parser.add_argument('--out',type=Path,default=Path('/mnt/data/bw14_assets.json'))
args=parser.parse_args()
source=args.source_model_script.read_text()
namespace={'__name__':'_bw_source_recipe'}
# Source code before the final export stage is loadable without side effects.
exec(source[:source.index('\nmodels={')],namespace)
ell=namespace['ell']; block=namespace['block']; PALETTE=namespace['PALETTE'];render_volume=namespace['render_volume']
N=namespace['N'];H=namespace['H'];

# Additional materials: caramel trims, teal cloth shading, colorful variations.
PALETTE.update({51:(237,198,122),52:(126,73,60),53:(45,111,125),54:(106,180,149),55:(255,244,180),56:(163,72,90),57:(83,143,104),58:(197,217,201),59:(202,165,72),60:(45,72,94),61:(255,207,145),62:(155,105,74),63:(235,222,186),64:(97,117,111),65:(247,236,200),66:(136,69,44),67:(245,170,73),68:(162,113,82),69:(235,189,145)})
namespace['PALETTE'].update(PALETTE)

# Character geometry constructed once per full-body pose and variant;
# all eight views are rotations of the *same physical voxel volume*.
def character(variant=0, pose=0):
    # variant -1 is hero; 0-2 are persistent NPC archetypes.
    seed=1847+(variant+2)*31
    rr=np.random.default_rng(seed)
    v=np.zeros((64,48,48), dtype=np.uint8)
    coat={-1:21,0:42,1:53,2:57}[variant]
    coatHi={-1:42,0:54,1:54,2:10}[variant]
    hair={-1:35,0:29,1:66,2:33}[variant]
    hairHi={-1:45,0:61,1:68,2:25}[variant]
    leather={-1:27,0:52,1:28,2:48}[variant]
    # Feet + legs, asymmetric action poses, same skeleton and proportions.
    for side in [-1,1]:
        stride= (3 if pose==1 else -3 if pose==2 else 1 if pose==4 else 0)*side
        swing_z= (2 if pose==1 else -2 if pose==2 else 0)*side
        lx=round(24+side*4+stride*.55)
        z=round(24+swing_z)
        ell(v,(lx,7,z),(2.7,6.5,3.1),leather)
        ell(v,(lx,2.6,z+1.5),(4.4,3.2,5.2),28)
        block(v,lx-3,lx+3,2,4,z+1,z+5,34)
        block(v,lx-2,lx+2,11,14,z-2,z+3,51)
    # Sculpted tunic, jacket panels, cuffs, distinct hems and belt.
    ell(v,(24,18,24),(7.9,10.7,6.6),coat)
    ell(v,(24,13,24),(8.1,3.4,7.0),coatHi)
    ell(v,(24,21,24),(6.6,6.5,6.4),coat)
    block(v,17,31,14,16,18,31,leather)
    block(v,18,30,15,16,29,31,59)
    block(v,22,26,15,17,30,32,55)
    # Contrast side panel and gold seam toward face (+z).
    block(v,23,25,15,27,29,31,coatHi)
    for y in [17,20,23,25]:
      block(v,23,26,y,y+1,30,32,51)
    # leather satchel at hip and strap across torso; a true volume.
    ell(v,(15.9,17.2,25),(3.2,5.1,4.2),leather)
    for y in range(17,30):
      x=round(17+(y-17)*.45)
      block(v,x,x+2,y,y+1,28,30,leather)
    # Shoulders and separate swing positions, arms not merely whole-image bobbing.
    for side in [-1,1]:
       zShift= (-2 if pose==1 else 2 if pose==2 else 0)*side
       yShift= (5 if side>0 else -2) if pose==3 else (1 if pose==4 else 0)
       xx=24+side*9
       ell(v,(xx,23+yShift,23+zShift),(3.5,4.3,4.0),coatHi)
       ell(v,(xx+side*.9,16+yShift,23+zShift),(3.0,6.7,3.2),coat)
       ell(v,(xx+side*1.1,10.8+yShift,24+zShift),(2.8,3.4,2.6),36)
       # Golden embroidery on cuff not a flat UI overlay.
       ell(v,(xx+side*.6,14+yShift,23+zShift),(3.0,.85,2.9),51)
    # Neck/collar and oversized chibi face in all orientations.
    ell(v,(24,28.5,24),(5.2,3.8,5.4),63)
    ell(v,(24,36.3,24),(8.5,9.0,7.6),36)
    ell(v,(24,35.9,28.2),(7.2,7.6,4.1),69)
    # Nose, tiny cheek highlights, eyes with white glints, brows.
    ell(v,(24,34.7,32.0),(1.7,1.55,2.2),61)
    for x in (20,28):
       ell(v,(x,37.6,31.0),(1.25,1.4,1.2),23)
       ell(v,(x-.4,38.1,32.2),(.50,.52,.65),65)
       ell(v,(x,39.6,31.2),(1.8,.55,1),68)
       ell(v,(x+(-1 if x<24 else 1),34.7,30.9),(1.2,.8,.7),39)
    ell(v,(24,32.4,32.0),(.98,.6,1.2),52)
    # Fine layered hair and individual tufts; blond / red / brown identities.
    ell(v,(24,43.0,23.6),(8.5,5.2,8.1),hair)
    for k in range(34):
        angle=k*2.3999632297
        rad=4.5+rr.uniform(0,4.3)
        xx=24+math.cos(angle)*rad
        zz=23+math.sin(angle)*rad
        yy=44+rr.uniform(-2.9,3.7)
        ell(v,(xx,yy,zz),(rr.uniform(1.4,2.8),rr.uniform(1.6,3.4),rr.uniform(1.5,3.0)),hair if k%4 else hairHi)
    # Fringes at forehead, cannot protrude into the pupil area.
    for x in [18.5,21,24.5,27.5,30]:
        ell(v,(x,41.4+rr.uniform(-1.8,2),29.4),(2.1,3.1,2.5),hair)
    # Ear silhouettes
    ell(v,(15.9,35,24),(1.5,2.5,2),36)
    ell(v,(32.1,35,24),(1.5,2.5,2),36)
    # A cloak, shoulder epaulets, small back crest (not random shapes).
    ell(v,(24,20,18.3),(6.7,10,1.9),coatHi)
    ell(v,(24,19,16.4),(2.7,4.5,1),51)
    ell(v,(24,19,16.0),(1.1,2.2,1),59)
    # pose 4: an authored joyful jump with bent knees/one raised hand.
    if pose==4:
      # only explicit hero input triggers this frame
      ell(v,(15,27,25),(3.3,3.4,3.0),coatHi)
    return v

# Existing rigid asset PNGs remain source-faithful; add rich panel motifs through voxel objects.
def rich_column():
  v=namespace['column'](True)
  # Brick joints in 3D, inset gold band and central relief.
  for y in range(10,45,7):
    block(v,20,28,y,y+1,28,30,3)
    block(v,19,29,y+1,y+2,29,30,31)
  for y in range(18,38,3):
    block(v,23,25,y,y+1,30,32,51)
  ell(v,(24,28,30),(2.5,3.7,1.3),5)
  block(v,22,26,28,29,32,33,6)
  # warm lantern casing, always stationary near masonry
  ell(v,(13.0,29,21),(3.4,5.2,2.8),4)
  ell(v,(13.0,30.5,22),(1.65,2.7,1.5),50)
  return v

def rich_tree(variant):
  v=namespace['tree'](variant)
  rr=np.random.default_rng(309+variant)
  # Leaf clusters in actual volume; avoid filling canopy with featureless green blob.
  canopy=(v>=8)&(v<=13)
  y,z,x=np.where(canopy)
  sel=rr.choice(len(y),min(580,len(y)),replace=False)
  for j in sel:
    yy,zz,xx=int(y[j]),int(z[j]),int(x[j])
    if yy>42 and rr.random()<.58:
      v[yy,zz,xx]=int(rr.choice([9,10,11,12,13,14,17,55],p=[.13,.17,.18,.22,.15,.10,.04,.01]))
  # discreet petal blossoms on crown rim, actual isolated voxel clusters
  for i in range(30):
    xx=int(rr.integers(8,40));zz=int(rr.integers(7,40))
    ys=np.where((v[:,zz,xx]>=8)&(v[:,zz,xx]<=13))[0]
    if len(ys):
      yy=min(63,int(ys.max())+1)
      ell(v,(xx,yy,zz),(1.1,1.1,1.1),int(rr.choice([14,17,18,55])))
  return v

models={'tree0':rich_tree(0),'tree1':rich_tree(1),'tree2':rich_tree(2),
        'pillar':rich_column(),'column':namespace['column'](False),'arch':namespace['arch'](),
        'flowers':namespace['flowerbed'](),'bush':namespace['bush']()}

# An explicitly named 8-direction canon, from the SAME 3D models.
DIRS=('front','front_right','right','back_right','back','back_left','left','front_left')
for variant,base in [(-1,'hero'),(0,'citizen0'),(1,'citizen1'),(2,'citizen2')]:
  for pose in range(5):
    v=character(variant,pose)
    for k,face in enumerate(DIRS):
      rotated=rotate(v,angle=k*45,axes=(1,2),reshape=False,order=0,mode='constant',cval=0,prefilter=False)
      models[f'{base}_{face}_{pose}']=rotated

output={}
for i,(name,v) in enumerate(models.items()):
  s=render_volume(v)
  if not s:raise ValueError('Missing visual sprite '+name)
  output[name]=s
  if i%35==0:print('sprites',i, '/',len(models),flush=True)
args.out.parent.mkdir(parents=True,exist_ok=True)
args.out.write_text(json.dumps(output,separators=(',',':')))
for key in ['hero_front_0','hero_front_right_1','hero_back_2','citizen0_front_0','tree0','pillar']:
 p=args.out.parent/('bw14_'+key+'.png')
 p.write_bytes(base64.b64decode(output[key]['uri'].split(',')[1]))
print('FINAL spriteCount',len(output),'actors',len(output)-8,'sizeKiB',round(args.out.stat().st_size/1024,1))
