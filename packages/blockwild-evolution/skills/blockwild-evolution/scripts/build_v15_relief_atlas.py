"""BLOCKWILD v15: baked volumetric relighting + original-source detail fusion.
Author-created assets only. No downloaded models or fonts; no original world edits.
Dependencies only at build-time: NumPy, SciPy, Pillow, Numba.
"""
import sys,json,io,math,base64,time,hashlib
from pathlib import Path
import numpy as np
from scipy.ndimage import rotate
from PIL import Image,ImageEnhance
sys.path.insert(0,str(Path(__file__).parent))
from volumetric_relight import render_smooth
import argparse
parser=argparse.ArgumentParser(description='BLOCKWILD v14 3D source volumes -> PBR-baked v15 RGBA atlas')
parser.add_argument('--v14-html',type=Path,required=True)
parser.add_argument('--out-assets',type=Path,required=True)
args=parser.parse_args()
ROOT=Path(__file__).resolve().parent
html=args.v14_html.read_text()
start='const ROYAL_ART={SPRITES:'
i=html.index(start)+len(start)
legacy,_=json.JSONDecoder().raw_decode(html[i:])
src=(ROOT/'build_sunlit_volume_sprites.py').read_text()
ns={};exec(src[:src.index('\nmodels={')],ns)
code=(ROOT/'build_blockwild_v14_actors.py').read_text()
ns['namespace']=ns
exec(code[code.index('# Additional materials'):code.index('\nmodels={')],ns)
ell,block=ns['ell'],ns['block'];palette=ns['PALETTE'];

def rich_arch():
 v=ns['namespace']['arch']()
 # Inset medieval masonry seams and gold crest; all real source voxels.
 for y in range(12,49,8):
  for x0,x1 in [(5,12),(36,43)]:
   block(v,x0-2,x1+1,y,y+1,28,30,3)
   block(v,x0,x1,y+1,y+2,29,30,31)
 for x in range(9,40,6):
  block(v,x,x+3,50,52,28,31,3)
  block(v,x+1,x+2,57,59,27,30,51)
 ell(v,(24,57,30),(2.8,2.9,1.3),4)
 ell(v,(24,57,31.7),(1.6,1.5,.9),55)
 # 3D vines with separate leaves and subtle blossoms.
 for k in range(34):
  y=16+k%31
  x=10 if k%2 else 39
  z=28+(k%3)
  if y<46:
   ell(v,(x,y,z),(1.2,2.7,1.6),10 if k%3 else 12)
   if k%6==0:ell(v,(x+1,y+2,z+1),(1.0,1.3,1.0),18)
 return v

def volume_butterfly(phase=0,kind=0):
 v=np.zeros((64,48,48),np.uint8)
 # One coherent small 3D body + independently posed bilateral wings.
 ox=24;oy=33;oz=24
 ell(v,(ox,oy,oz),(1.6,5.5,1.7),27)
 ell(v,(ox,oy+5,oz),(2,1.8,1.6),28)
 spread=[12,7,4,8][phase]
 for sign in (-1,1):
  ell(v,(ox+sign*spread*.67,oy+2,oz),(max(2.4,spread*.63),6,2.7),18 if kind==0 else 19)
  ell(v,(ox+sign*(spread*.68),oy-3,oz),(max(2.2,spread*.52),4.5,2.2),14 if kind==0 else 16)
  ell(v,(ox+sign*(spread*.65),oy+2,oz+1),(2.5,3,1.4),55)
 return v

def decode_obj(p):return Image.open(io.BytesIO(base64.b64decode(p['uri'].split(',',1)[1]))).convert('RGBA')
def encode_obj(im,base,layers):
 buf=io.BytesIO();im.save(buf,'PNG',optimize=True,compress_level=8)
 return {'uri':'data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode('ascii'), 'base':list(base),'size':list(im.size),'layers':int(layers)}

def mix(orig,new,original_share):
 # Blend PBR relief with the exact original material/eye details in identical
 # 3D projections. Retain the material identity of every individual actor.
 a=Image.new('RGBA',(320,302));b=a.copy()
 oa=decode_obj(orig);na=decode_obj(new)
 a.paste(na,(160-new['base'][0],256-new['base'][1]))
 b.paste(oa,(160-orig['base'][0],256-orig['base'][1]))
 im=Image.blend(a,b,original_share)
 # Do not lose the original costume highlights or pupils to a diffusion blur.
 # Saturation is restrained to avoid fluorescent moss/plastic.
 im=ImageEnhance.Color(im).enhance(1.075)
 bounds=im.getbbox();margin=4
 if not bounds:return orig
 x0=max(0,bounds[0]-margin);y0=max(0,bounds[1]-margin)
 x1=min(320,bounds[2]+margin);y1=min(302,bounds[3]+margin)
 return encode_obj(im.crop((x0,y0,x1,y1)),(160-x0,256-y0),new['layers'])

out={};stat={}
props={'tree0':ns['rich_tree'](0),'tree1':ns['rich_tree'](1),'tree2':ns['rich_tree'](2),'tree3':ns['rich_tree'](3),'tree4':ns['rich_tree'](4),
       'pillar':ns['rich_column'](),'column':ns['namespace']['column'](False),
       'arch':rich_arch(),'flowers':ns['namespace']['flowerbed'](),'bush':ns['namespace']['bush']()}
for name,vol in props.items():
 fresh=render_smooth(vol,palette,scale=1.5)
 share=.63 if name.startswith('tree') else (.54 if name in ('arch','pillar','column') else .73)
 out[name]=mix(legacy[name] if name in legacy else ns['render_volume'](vol),fresh,share)
 print('prop',name,round(len(out[name]['uri'])/1024),flush=True)

DIRS=('front','front_right','right','back_right','back','back_left','left','front_left')
start=time.time()
for variant,name in [(-1,'hero'),(0,'citizen0'),(1,'citizen1'),(2,'citizen2')]:
 for pose in range(5):
  vol=ns['character'](variant,pose)
  for k,face in enumerate(DIRS):
   key=f'{name}_{face}_{pose}'
   rotated=rotate(vol,angle=k*45,axes=(1,2),reshape=False,order=0,mode='constant',cval=0,prefilter=False)
   fresh=render_smooth(rotated,palette,scale=1.5)
   out[key]=mix(legacy[key],fresh,.61)
  print('baked',name,'pose',pose,'elapsed',round(time.time()-start,1),flush=True)
# Small separately posed volumetric flying creatures.
for kind in range(2):
 for phase in range(4):
  key=f'butterfly{kind}_{phase}'
  out[key]=render_smooth(volume_butterfly(phase,kind),palette,scale=1.5)
print('TOTAL',len(out),'bytes',sum(len(x['uri']) for x in out.values()),'seconds',time.time()-start)
args.out_assets.parent.mkdir(parents=True,exist_ok=True)
args.out_assets.write_text(json.dumps(out,separators=(',',':'))) 
