#!/usr/bin/env python3
"""Optional genuine glTF2/GLB 3D textured horizontal slice stack exports.

Source is exclusively the same approved alpha PNG stack atlas used by the real
PixiJS physical game. Trimesh only writes glTF geometry; it does NOT generate
new characters, animate them, infer missing views or change their original art.
"""
from __future__ import annotations
import base64,hashlib,io,json,zipfile
from pathlib import Path
from PIL import Image

class SpriteStackGLBError(ValueError):pass

def export_one(atlas_record,destination,step=1,scale=1):
    try:import numpy as np;import trimesh
    except ImportError as ex:raise SpriteStackGLBError('Real trimesh + NumPy required for glTF authoring; install their actual open source packages') from ex
    if not isinstance(atlas_record,dict):raise SpriteStackGLBError('Approved sprite atlas required')
    b64=atlas_record.get('atlas','')
    if not b64.startswith('data:image/png;base64,'):raise SpriteStackGLBError('Original PNG atlas data URI required')
    raw=base64.b64decode(b64.split(',',1)[1],validate=True)
    if hashlib.sha256(raw).hexdigest()!=atlas_record.get('sha256'):
        raise SpriteStackGLBError('Original sprite-stack source hash mismatch')
    with Image.open(io.BytesIO(raw)) as im:
        if im.format!='PNG':raise SpriteStackGLBError('Sprite atlas not PNG')
        image=im.convert('RGBA').copy()
    count=atlas_record['slices'];cols=atlas_record['columns'];w=atlas_record['width'];d=atlas_record['depth']
    if count<8 or count>96 or image.width<cols*w or image.height<((count+cols-1)//cols)*d:
        raise SpriteStackGLBError('Invalid actual cross-section atlas geometry')
    mat=trimesh.visual.material.PBRMaterial(baseColorTexture=image,metallicFactor=0,roughnessFactor=1,
                                            alphaMode='BLEND',doubleSided=True)
    out=trimesh.Scene()
    for i in range(count):
        top=(i//cols)*d;left=(i%cols)*w
        # Preserve PNG texture rows, including transparent alpha and original brush texture.
        u0=left/image.width;u1=(left+w)/image.width
        v0=1-top/image.height;v1=1-(top+d)/image.height
        height=i*float(step)*float(scale)
        verts=np.array([[-w*.5*scale,height,-d*.5*scale],[w*.5*scale,height,-d*.5*scale],
                        [w*.5*scale,height,d*.5*scale],[-w*.5*scale,height,d*.5*scale]],dtype=float)
        uv=np.array([[u0,v0],[u1,v0],[u1,v1],[u0,v1]])
        mesh=trimesh.Trimesh(vertices=verts,faces=np.array([[0,1,2],[0,2,3]]),process=False,
                             visual=trimesh.visual.TextureVisuals(uv=uv,material=mat))
        out.add_geometry(mesh,geom_name=f'slice_{i:03d}',node_name=f'slice_{i:03d}')
    file=Path(destination).resolve();file.parent.mkdir(parents=True,exist_ok=True)
    if file.exists():raise SpriteStackGLBError('Original exported GLB already exists; no overwrite')
    data=out.export(file_type='glb')
    if not isinstance(data,bytes) or not data.startswith(b'glTF'):
        raise SpriteStackGLBError('Trimesh did not generate a genuine binary glTF file')
    file.write_bytes(data)
    return {'slices':count,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),
            'original_rgba_png':atlas_record['sha256'],'export':'real glTF 2.0 3D textured planes',
            'material_alpha_mode':'BLEND','original_pose_timing':'not modified'}

def export_from_compiled(compiled,destination,all_poses=False):
    """One GLB per architectural state/prop; optionally each original actor pose."""
    destination=Path(destination).resolve()
    if destination.exists() and any(destination.iterdir()):
        raise SpriteStackGLBError('Use a new empty GLB output directory')
    destination.mkdir(parents=True,exist_ok=True)
    manifest=[]
    for obj in compiled['objects']:
        for state,atlas in obj['states'].items():
            dest=destination/'world'/obj['id']/(state+'.glb')
            stats=export_one(atlas,dest,obj['step_px'],obj['scale'])
            manifest.append({'object':obj['id'],'state':state,'path':dest.relative_to(destination).as_posix(),**stats})
    for actor in compiled['actors']:
        frames=actor['frames'] if all_poses else actor['frames'][:1]
        for i,atlas in enumerate(frames):
            dest=destination/'actors'/actor['id']/(f'{i:04d}.glb')
            stats=export_one(atlas,dest,actor['step_px'])
            manifest.append({'actor':actor['id'],'pose':i,'original_frame':atlas['source_frame'],
                             'path':dest.relative_to(destination).as_posix(),**stats})
    if not manifest:raise SpriteStackGLBError('No genuine original 3D sprite-stack volumes')
    data={'engine':'trimesh source-PNG glTF 2.0','all_actor_poses':bool(all_poses),
          'glb_files':manifest,'source_art_replaced':False,'original_motion_gate_required':True}
    (destination/'manifest.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf8')
    return data

if __name__=='__main__':
    import argparse
    from sprite_stacking_bridge import config_from_source
    ap=argparse.ArgumentParser();ap.add_argument('--approved-zip',type=Path,required=True)
    ap.add_argument('--scene',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--all-poses',action='store_true');a=ap.parse_args()
    compiled=config_from_source(a.approved_zip,a.scene)
    result=export_from_compiled(compiled,a.out,a.all_poses)
    print(json.dumps({'glb_count':len(result['glb_files']),'source_art_replaced':False}))
