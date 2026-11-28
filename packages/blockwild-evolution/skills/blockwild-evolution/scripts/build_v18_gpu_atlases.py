"""Render actual author-made occupancy volumes to reproducible GPU RGBA & normal atlases.
All assets are derived from the same licensed authored source voxel arrays used in v16/v17.
Does not claim original Unity mesh/texture extraction.
"""
from pathlib import Path
import numpy as np, json, io, base64, sys, argparse
from PIL import Image
from scipy.ndimage import gaussian_filter
BASE=Path(__file__).parent
parser=argparse.ArgumentParser()
parser.add_argument('--out-dir',type=Path,default=Path('build/blockwild_gpu18'))
args=parser.parse_args()
DEST=args.out_dir.resolve();DEST.mkdir(parents=True,exist_ok=True)
base=(BASE/'build_sunlit_volume_sprites.py').read_text()
ns={'__name__':'_volume_recipe'}
exec(base[:base.index('\nmodels={')],ns)
ns['ns']=ns
s16=(BASE/'build_v16_volume_props.py').read_text()
exec(s16[s16.index('N=48;H=64; P='):s16.index('\nmodels={')],ns)
# v16 defs bind functions to same global namespace
model16={
 'v16_fountain':ns['fountain'](),'v16_rose_arch':ns['rose_arch'](),
 'v16_bench':ns['gilded_bench'](),'v16_lantern':ns['lantern'](),
 'v16_urn_rose':ns['flower_urn'](0),'v16_urn_cream':ns['flower_urn'](1),
 'v16_cherry0':ns['cherry_tree'](0),'v16_cherry1':ns['cherry_tree'](1),
 'v16_cypress':ns['cypress'](0),'v16_citrus':ns['citrus_tree'](2),
 'v16_carved_urn':ns['carved_urn'](),
}
s17=(BASE/'build_v17_volumes.py').read_text()
exec(s17[s17.index("P=ns['P']"):s17.index('\nmodels={')],ns)
model17={'v17_wisteria_pergola':ns['pergola'](),'v17_royal_pedestal':ns['royal_pedestal'](),
'v17_lily_well':ns['turquoise_well'](),'v17_ivy_pillar':ns['foliage_pillar']()}
models={**model16,**model17}
# Back-ported exact authored 3D character recipes from the approved v14 eight-view
# generator. Each pose/identity is held in ONE physical volume and rotated on GPU.
ns['namespace']=ns
s14=(BASE/'build_blockwild_v14_actors.py').read_text()
exec(s14[s14.index('# Additional materials:'):s14.index('\nmodels={', s14.index('# Additional materials:'))],ns)
for variant,archetype in [(-1,'hero'),(0,'citizen0'),(1,'citizen1'),(2,'citizen2')]:
 for pose in range(5):
  models[f'gpu_{archetype}_{pose}']=ns['character'](variant,pose)
for name,mesh in {'tree0':ns['rich_tree'](0),'tree1':ns['rich_tree'](1),'tree2':ns['rich_tree'](2),
                  'pillar':ns['rich_column'](),'column':ns['column'](False),'arch':ns['arch'](),
                  'flowers':ns['flowerbed'](),'bush':ns['bush']()}.items():
 models[name]=mesh
P=ns['P']
out={};
for name,v in models.items():
  assert v.shape==(64,48,48),(name,v.shape)
  # Occupancy-derived normals in source axis: [height, depth, width].
  density=gaussian_filter((v>0).astype('float32'),sigma=(0.78,0.72,0.72))
  dy,dz,dx=np.gradient(density)
  # outward normals (-spatial gradient), stable top-up fallback for interior.
  norm=np.stack((-dx,-dy,-dz),axis=-1)
  mag=np.linalg.norm(norm,axis=-1,keepdims=True)
  norm=np.divide(norm,np.maximum(mag,1.e-4));
  norm=np.where(mag>.002,norm,np.array([0,1,0],dtype='float32'))
  nm=np.clip((norm*.5+.5)*255,0,255).astype('uint8')
  palettes=np.zeros((256,3),dtype='uint8')
  for idx,rgb in P.items():palettes[int(idx)]=np.array(rgb[:3],dtype='uint8')
  rgba=np.zeros((64,48,48,4),dtype='uint8');rgba[:,:,:,:3]=palettes[v]
  rgba[:,:,:,3]=np.where(v!=0,255,0).astype('uint8')
  normals=np.zeros_like(rgba);normals[:,:,:,:3]=nm;normals[:,:,:,3]=rgba[:,:,:,3]
  layers=[]
  for pixels in [rgba,normals]:
   a=np.zeros((48*8,48*8,4),dtype='uint8')
   for h in range(64):
     yy,xx=divmod(h,8)
     a[yy*48:(yy+1)*48,xx*48:(xx+1)*48]=pixels[h]
   out_file=DEST/(name+('_albedo.png' if pixels is rgba else '_normals.png'))
   im=Image.fromarray(a,'RGBA');buf=io.BytesIO();im.save(buf,format='PNG',optimize=True,compress_level=7);dat=buf.getvalue()
   out_file.write_bytes(dat)
   layers.append('data:image/png;base64,'+base64.b64encode(dat).decode())
  out[name]={'albedo':layers[0],'normal':layers[1], 'layers':64,'side':48,'voxels':int((v!=0).sum())}
  print(name, 'voxels=',out[name]['voxels'],'atlasKB=',int(sum(len(i) for i in layers)*.75/1024),flush=True)
path=DEST/'gpu_volumes.json';path.write_text(json.dumps(out,separators=(',',':')))
print('OUTPUT',path, 'size',path.stat().st_size,flush=True)
