"""BLOCKWILD v16: build artist-authored true 3D volume RGBA sprite-stacks (CPU only).
Uses the same 48x48x64 physically occupied source volumes as v15; all assets new
additions, no replacements of characters, and all source-world bytes remain untouched.
"""
import argparse, io, json, base64, math, time
from pathlib import Path
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

ap=argparse.ArgumentParser()
ap.add_argument('--recipes',type=Path,default=Path(__file__).with_name('build_sunlit_volume_sprites.py'))
ap.add_argument('--enhancer',type=Path,default=Path(__file__).with_name('volumetric_relight.py'))
ap.add_argument('--out',type=Path,default=Path('build/bw16_assets.json'))
args=ap.parse_args()
ns={'__name__':'_recipe'}; raw=args.recipes.read_text()
exec(raw[:raw.index('\nmodels={')],ns)
N=48;H=64; P=ns['PALETTE'];ell=ns['ell'];block=ns['block'];XX=ns['XX'];YY=ns['YY'];ZZ=ns['ZZ'];render_crisp=ns['render_volume']
P.update({
70:(211,198,183),71:(241,224,195),72:(159,152,137),73:(196,162,112),
74:(232,187,75),75:(27,142,171),76:(104,217,217),77:(210,249,222),
78:(22,94,77),79:(60,117,75),80:(136,178,97),81:(242,202,106),
82:(224,154,188),83:(255,222,217),84:(245,242,204),85:(36,86,109),
86:(76,116,170),87:(255,188,92),88:(145,74,96),89:(204,175,128),
90:(243,222,157),91:(195,212,163),92:(184,118,65),93:(129,78,60),
94:(218,229,202),95:(49,155,138),96:(253,238,191),97:(89,151,97)
})

def new():return np.zeros((H,N,N),dtype=np.uint8)
def cylinder(v,xc,zc,r,y0,y1,mat,inner=0):
 m=(XX[0]-xc)**2+(ZZ[0]-zc)**2
 ring=(m<=r*r)&(m>=inner*inner)
 v[max(0,y0):min(H,y1),ring]=mat

def frieze(v,y,extent):
 for x in range(10,39,4):
  if x<extent or x>48-extent:continue
  block(v,x,x+2,y,y+1,16,18,74)
  block(v,x,x+2,y,y+1,30,32,74)

def flower_urn(variant=0):
 v=new(); rr=np.random.default_rng(614+variant)
 cylinder(v,24,24,10,0,3,72);cylinder(v,24,24,6,3,10,70)
 cylinder(v,24,24,8,9,13,71);cylinder(v,24,24,13,13,17,70,7)
 cylinder(v,24,24,10,17,19,73,7)
 cylinder(v,24,24,8,14,16,93)
 for i in range(36):
  a=2*math.pi*i/36;xx=24+8*math.cos(a);zz=24+8*math.sin(a)
  ell(v,(xx,17,zz),(1.2,1.1,1.2),74 if i%3 else 81)
 for i in range(45):
  x=float(rr.uniform(15,33));z=float(rr.uniform(15,33));yy=float(rr.uniform(17,26))
  ell(v,(x,yy,z),(3.5,4.5,3.7),int(rr.choice([78,79,80,97])))
 for i in range(27):
  x=float(rr.uniform(15,33));z=float(rr.uniform(16,32));yy=int(np.where(v[:,int(z),int(x)]>0)[0].max() if np.any(v[:,int(z),int(x)]>0) else 21)
  ell(v,(x,min(56,yy+2),z),(1.8,1.9,1.8),int(rr.choice([82,83,84,87])))
  if i%3==0:ell(v,(x,min(59,yy+3),z),(1,1,1),74)
 return v

def gilded_bench():
 v=new()
 for x in [10,33]:
  block(v,x,x+5,0,9,13,34,70);block(v,x,x+5,9,12,12,35,73)
  for z in [15,31]:block(v,x+1,x+4,1,10,z,z+2,74)
 block(v,11,39,12,16,12,36,71)
 block(v,12,38,15,18,13,35,70)
 block(v,11,38,17,43,34,37,73)
 block(v,12,37,19,41,32,35,70)
 for y in [23,29,35]:block(v,13,36,y,y+1,31,34,74)
 for x in range(16,36,5):
  block(v,x,x+1,19,40,30,31,89)
  ell(v,(x,37,31),(1.4,1.6,1.2),81)
 return v

def fountain():
 v=new()
 cylinder(v,24,24,20,0,4,72);cylinder(v,24,24,20,4,7,71,15)
 cylinder(v,24,24,18,2,4,75);cylinder(v,24,24,16,3,4,76)
 for yy,rr in [(6,19),(7,19),(8,18),(9,15)]:cylinder(v,24,24,rr,yy,yy+1,73,max(2,rr-3))
 cylinder(v,24,24,5,9,32,70)
 cylinder(v,24,24,8,31,33,73)
 cylinder(v,24,24,11,33,36,71,7)
 cylinder(v,24,24,10,36,38,74,8)
 cylinder(v,24,24,3,38,46,73)
 ell(v,(24,47,24),(4,5,4),74)
 # Sculpted jets follow plausible 3D ballistic arcs, not painted circles.
 for ang in np.linspace(0,2*math.pi,12,endpoint=False):
  for k in range(17):
   a=k/16;rad=3+14*a
   yy=44+6*math.sin(math.pi*a)-33*(a*a)
   x=24+math.cos(ang)*rad;z=24+math.sin(ang)*rad
   ell(v,(x,yy,z),(1.0,1.3,1.0),int([76,77,75][k%3]))
 return v

def rose_arch():
 v=new();rr=np.random.default_rng(2001)
 # Two robust stone columns and actual arched traversable void.
 for x0,x1 in [(6,13),(35,42)]:
  block(v,x0,x1,0,46,18,31,70)
  block(v,x0-2,x1+2,0,6,16,33,72)
  for y in range(8,43,7):block(v,x0-1,x1+1,y,y+2,16,33,73)
  for y in range(10,43,10):block(v,x0,x1,y,y+1,30,32,74)
 block(v,6,42,46,52,18,31,70)
 block(v,4,44,52,56,16,33,71)
 block(v,8,40,56,58,20,30,74)
 # Arch keystones and carved reliefs, source geometry remains an authentic volume.
 for x in range(9,40,5):
  block(v,x,x+1,49,55,16,18,72)
  ell(v,(x,54,16),(1.5,1.5,1.0),81)
 # Fragrant climbing roses across pillars: actual connected stalks and flowers.
 for side in (0,1):
  a=9 if side==0 else 39
  for y in range(10,54):
   x=a+1.5*math.sin(y*.21+side);z=16+3*math.sin(y*.17+side)
   ell(v,(x,y,z),(1.7,1.7,1.7),79)
   if y%5==0:
    ell(v,(x+2.1,y+2,z),(3,2.5,3),int(rr.choice([78,79,80])))
    ell(v,(x+3.1,y+3,z),(1.6,1.6,1.6),int(rr.choice([82,83,84])))
 for x in range(8,40,4):
  ell(v,(x,57,18),(3.6,3,3),int(rr.choice([78,79,80])))
  if x%2==0:ell(v,(x,59,18),(1.5,1.3,1.4),82)
 return v

def lantern():
 v=new()
 cylinder(v,24,24,7,0,5,72);cylinder(v,24,24,4,5,37,73)
 cylinder(v,24,24,8,35,39,74);cylinder(v,24,24,7,39,49,85)
 cylinder(v,24,24,6,40,48,81)
 for x,z in [(18,24),(30,24),(24,18),(24,30)]:
  ell(v,(x,45,z),(1.2,7.0,1.2),74)
 cylinder(v,24,24,9,49,52,74);ell(v,(24,56,24),(4,5,4),74)
 return v

def cherry_tree(variant=0):
 v=ns['tree'](variant);rr=np.random.default_rng(11311+variant)
 canopy=(v>=8)&(v<=13)
 old=np.where(canopy)
 choice=rr.choice(len(old[0]),int(len(old[0])*.35),replace=False)
 yy,zz,xx=[a[choice] for a in old]
 for y,z,x in zip(yy,zz,xx):
  if y<39:continue
  r=rr.random();v[y,z,x]=84 if r<.1 else (82 if r<.36 else 83 if r<.63 else 80)
 for i in range(110):
  x=int(rr.integers(5,44));z=int(rr.integers(5,43))
  ids=np.where(canopy[:,z,x])[0]
  if len(ids)>0:
   y=int(ids.max())
   ell(v,(x,y+1,z),(1.1,1,1.1),int(rr.choice([82,83,84,87])))
 return v

def cypress(variant=0):
 v=new();rr=np.random.default_rng(212+variant)
 for y in range(1,54):
  r=2.6 if y>11 else 3.5
  ell(v,(24,y,24),(r,2,r),92)
 for i,(yc,wide) in enumerate([(20,10),(28,12),(36,10),(44,8),(51,5)]):
  for k in range(18):
   ang=(2*math.pi*k/18)+i*.3
   rad=wide*rr.uniform(.65,1.0)
   x=24+math.cos(ang)*rad;z=24+math.sin(ang)*rad
   ell(v,(x,yc+rr.uniform(-4,4),z),(4.5,6.8,4.5),int(rr.choice([78,79,80,97])))
 return v

def citrus_tree(variant=0):
 v=ns['tree'](variant);rr=np.random.default_rng(940+variant)
 for i in range(105):
  x=int(rr.integers(4,44));z=int(rr.integers(4,44))
  ys=np.where((v[:,z,x]>=8)&(v[:,z,x]<=13))[0]
  if len(ys)==0:continue
  y=int(rr.choice(ys));
  if y<39:continue
  if ((y>=63 or v[min(63,y+1),z,x]==0) or x<10 or x>37):
   ell(v,(x,y,z),(1.6,1.5,1.6),87)
 return v

def carved_urn():
 v=new();
 cylinder(v,24,24,11,0,4,71);cylinder(v,24,24,6,4,14,72)
 ell(v,(24,23,24),(11,11,11),70)
 cylinder(v,24,24,10,31,36,73,5)
 cylinder(v,24,24,8,36,39,74,5)
 for k in range(14):
  ang=k*math.tau/14
  for y in range(19,31):
   r=11*(1-.15*abs(24-y)/10)
   x=24+math.cos(ang)*r;z=24+math.sin(ang)*r
   ell(v,(x,y,z),(1.1,1.1,1.1),81)
 return v

models={
 'v16_fountain':fountain(), 'v16_rose_arch':rose_arch(),
 'v16_bench':gilded_bench(), 'v16_lantern':lantern(),
 'v16_urn_rose':flower_urn(0),'v16_urn_cream':flower_urn(1),
 'v16_cherry0':cherry_tree(0),'v16_cherry1':cherry_tree(1),
 'v16_cypress':cypress(0),'v16_citrus':citrus_tree(2),
 'v16_carved_urn':carved_urn()
}
# Favor native transparent source slices and crystalline detail; only slight
# edge smoothing. Existing character atlas is completely immutable.
out={}; t=time.time()
for name,v in models.items():
 spec=render_crisp(v)
 if spec is None:raise RuntimeError('missing volume: '+name)
 # Gold-relief style uses rounded edges only on silhouette, preserving fine facets.
 im=Image.open(io.BytesIO(base64.b64decode(spec['uri'].split(',',1)[1]))).convert('RGBA')
 # Keep RGB edges crisp; soften only the alpha matte.
 a=im.getchannel('A').filter(ImageFilter.GaussianBlur(.34))
 im.putalpha(a)
 buf=io.BytesIO();im.save(buf,'PNG',optimize=True,compress_level=8)
 spec['uri']='data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode()
 spec['surface_voxels']=int(np.sum(v!=0))
 out[name]=spec
 print(name,spec['size'],spec['layers'],'voxel cells',spec['surface_voxels'],'elapsed',round(time.time()-t,1),flush=True)
 if args.out.parent.exists(): (args.out.parent/(name+'.png')).write_bytes(buf.getvalue())
args.out.parent.mkdir(parents=True,exist_ok=True)
args.out.write_text(json.dumps(out,separators=(',',':')))
print('COMPLETE',len(out),'assets',round(args.out.stat().st_size/1024,1),'KiB',flush=True)
