"""CPU bake of new original BLOCKWILD garden decor from occupancy volumes.
All coordinates/materials in a single 48x48x64 source model; no image extrusion.
"""
from pathlib import Path
import numpy as np, math, base64, io, json, argparse
from PIL import Image, ImageFilter
import sys
# This script lives beside existing v16 and base slice generators in the same skill.
src=Path(__file__).resolve().parent
ns={'__name__':'_recipe'};ns['ns']=ns
r=(src/'build_sunlit_volume_sprites.py').read_text();exec(r[:r.index('\nmodels={')],ns)
src16=(src/'build_v16_volume_props.py').read_text();exec(src16[src16.index('N=48;H=64;'):src16.index('\nmodels={')],ns)
P=ns['P'];P.update({98:(170,153,126),99:(243,216,146),100:(179,145,199),101:(203,182,230),102:(111,135,88),103:(249,230,196),104:(157,100,71),105:(224,210,181),106:(247,244,218),107:(78,116,91)})
H=64;N=48
block=ns['block'];ell=ns['ell'];XX=ns['XX'];YY=ns['YY'];ZZ=ns['ZZ'];cylinder=ns['cylinder'];render=ns['render_crisp']
def new():return np.zeros((64,48,48),np.uint8)
def pergola():
 v=new();rng=np.random.default_rng(1722)
 # Delicate true stone arched arbor with walk-through void.
 for x0 in (7,36):
  block(v,x0,x0+5,0,47,17,33,70)
  block(v,x0-2,x0+7,0,5,14,36,72)
  for y in (9,19,30,39):block(v,x0-1,x0+6,y,y+2,16,34,105)
 block(v,8,41,47,52,16,34,71)
 block(v,5,44,52,57,15,35,73)
 for x in range(9,41,4):
  block(v,x,x+1,50,56,15,18,72)
  ell(v,(x,55,18),(2,1.5,2),99)
 # Deep green creeper volume with hanging blue-violet wisteria blossoms.
 for side in (0,1):
  x0=9 if side==0 else 39
  for y in range(11,59):
   x=x0+2*math.sin(y*.28+side)
   z=18+3*math.sin(y*.21+side*2)
   ell(v,(x,y,z),(1.6,1.6,1.6),107)
   if y%5==0:
    ell(v,(x+(-2 if side else 2),y+2,z+1),(3,3,3),79)
    ell(v,(x+(-2 if side else 2),y+1,z-1),(2.3,4,2.1),100 if y%3 else 101)
 for x in range(9,40,4):
  ell(v,(x,58,18),(3.5,2.8,4),80)
  for h in range(0,9,2):
   ell(v,(x,57-h,16+math.sin(x+h)*3),(1.9,2.5,1.8),100 if h%4 else 101)
 return v

def royal_pedestal():
 v=new()
 # Polished plinth with carved gilded masonry cornice and authentic depth.
 block(v,9,39,0,4,9,39,72)
 block(v,13,35,4,13,13,35,70)
 block(v,10,38,13,16,10,38,73)
 block(v,12,36,16,22,12,36,71)
 for i in range(4):
  x=13+i*7
  block(v,x,x+2,17,19,11,13,99)
  block(v,x,x+2,17,19,35,37,99)
 for z in (12,35):
  for x in range(15,35,7):ell(v,(x,18,z),(1.5,1.5,1.5),99)
 # true 3D stone celestial orb / illuminated object, 8-direction consistent
 ell(v,(24,32,24),(9.8,11.6,9.8),74)
 ell(v,(24,34,24),(8.6,9.0,8.6),90)
 for a in np.linspace(0,math.tau,12,endpoint=False):
  ell(v,(24+7*math.cos(a),34+2*math.sin(a*2),24+7*math.sin(a)),(1.0,1.2,1.0),99)
 ell(v,(24,47,24),(4,4,4),106)
 return v

def turquoise_well():
 v=new()
 cylinder(v,24,24,21,0,3,72)
 cylinder(v,24,24,21,3,7,71,16)
 cylinder(v,24,24,17,3,4,75)
 for i in range(16):
  a=i*math.tau/16
  ell(v,(24+18*math.cos(a),8,24+18*math.sin(a)),(2,2,2),73)
 for x,z in [(15,19),(27,29),(34,20),(21,34)]:
  ell(v,(x,5,z),(4,1.3,3),79)
  for k in range(5):
   angle=k*math.tau/5;ell(v,(x+math.cos(angle)*2,7,z+math.sin(angle)*2),(1.7,1,1.7),103)
  ell(v,(x,8,z),(1.2,1,1.2),74)
 # central relief marble vase and sparkling surface height
 cylinder(v,24,24,5,5,12,70)
 cylinder(v,24,24,7,12,15,73,4)
 ell(v,(24,17,24),(4,4.5,4),76)
 return v

def foliage_pillar():
 v=new();rng=np.random.default_rng(9)
 block(v,9,39,0,6,12,36,72)
 block(v,13,35,6,47,16,32,70)
 for y in [11,25,39,47]:block(v,11,37,y,y+3,14,34,71)
 for y in range(11,48,6):
  for z in (14,33):ell(v,(24,y,z),(3.3,3,1),74)
 for side in (0,1):
  x=10 if side==0 else 38
  for y in range(8,58):
   z=24+7*math.sin(y*.15+side)
   ell(v,(x+math.sin(y*.26+side)*2,y,z),(1.5,2,1.5),107)
   if y%7==0:
    ell(v,(x,y+1,z+2),(4,3,4),80)
    ell(v,(x+1,y+3,z+2),(1.7,1.6,1.7),83 if y%2 else 82)
 ell(v,(24,52,24),(9,4,9),70)
 cylinder(v,24,24,7,54,58,73)
 ell(v,(24,61,24),(3,3,3),106)
 return v

models={'v17_wisteria_pergola':pergola(),'v17_royal_pedestal':royal_pedestal(),
        'v17_lily_well':turquoise_well(),'v17_ivy_pillar':foliage_pillar()}
a=argparse.ArgumentParser();a.add_argument('--out',default='v17_assets.json');opts=a.parse_args();out={}
for name,v in models.items():
 spec=render(v);assert spec and spec['layers']
 im=Image.open(io.BytesIO(base64.b64decode(spec['uri'].split(',',1)[1]))).convert('RGBA')
 im.putalpha(im.getchannel('A').filter(ImageFilter.GaussianBlur(.36)))
 buf=io.BytesIO();im.save(buf,format='PNG',optimize=True,compress_level=8)
 spec['uri']='data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode();spec['surface_voxels']=int((v!=0).sum())
 out[name]=spec
 (Path(opts.out).parent / (name+'.png')).write_bytes(buf.getvalue())
 print(name, 'size',spec['size'],'layers',spec['layers'],'voxels',spec['surface_voxels'])
Path(opts.out).parent.mkdir(parents=True,exist_ok=True)
Path(opts.out).write_text(json.dumps(out,separators=(',',':')))
print('DONE',len(out),'genuine occupancy volumes')
