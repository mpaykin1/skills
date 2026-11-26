"""BlenderProc offline pass. Open full authored scene, not reconstructed geometry."""
import blenderproc as bproc
import argparse, json
from pathlib import Path
import bpy
import numpy as np
import imageio.v2 as imageio

p=argparse.ArgumentParser();p.add_argument('--scene',required=True);p.add_argument('--focus',required=True);p.add_argument('--camera',required=True);p.add_argument('--recipe',required=True);p.add_argument('--out',required=True);p.add_argument('--frame',type=int,default=1);p.add_argument('--samples',type=int,default=32);a=p.parse_args()
bproc.init()
bpy.ops.wm.open_mainfile(filepath=str(Path(a.scene).resolve()),load_ui=False)
s=bpy.context.scene;s.frame_set(a.frame)
f=s.objects.get(a.focus);c=s.objects.get(a.camera)
if not f or f.type!='MESH' or not c or c.type!='CAMERA':raise ValueError('Exact focus mesh and camera required')
recipe=json.loads(a.recipe);lights=bpy.data.collections.get('CSD Directing')
if not lights:raise ValueError('Run director.py first')
for o in lights.objects:
    if o.type=='LIGHT':
        role=o.name.removeprefix('CSD ')
        if role not in recipe['energy']:raise ValueError('Unexpected light: '+o.name)
        o.data.energy*=recipe['energy'][role]
        if o.data.type=='AREA':o.data.size*=recipe['size']
for o in s.objects:
    if o.type=='MESH':o['category_id']=int(o==f)
# Work on a temporary camera, preserving authored camera animation and lens.
pose=np.array(c.evaluated_get(bpy.context.evaluated_depsgraph_get()).matrix_world)
cam=bpy.data.objects.new('CSD measure camera',c.data.copy());s.collection.objects.link(cam);s.camera=cam
s.frame_start=a.frame;s.frame_end=a.frame
bproc.camera.set_resolution(640,360)
bproc.camera.add_camera_pose(pose,frame=a.frame)
s.frame_start=a.frame;s.frame_end=a.frame+1
s.render.engine='CYCLES';s.cycles.device='CPU';s.use_nodes=False
bproc.renderer.set_max_amount_of_samples(a.samples)
bproc.renderer.enable_depth_output(activate_antialiasing=False)
bproc.renderer.enable_normals_output()
bproc.renderer.enable_segmentation_output(map_by=['category_id'],default_values={'category_id':0})
data=bproc.renderer.render()
if len(data['colors'])!=1:raise RuntimeError('Expected exactly one frame')
key=next((k for k in ('category_id_segmaps','segmap','segmaps') if k in data),None)
if key is None:raise RuntimeError('Missing category segmentation: '+str(data.keys()))
mask=np.asarray(data[key][0]).squeeze()==1
rgb=np.asarray(data['colors'][0])[...,:3];depth=np.asarray(data['depth'][0]).squeeze();normals=np.asarray(data['normals'][0])
if mask.shape!=rgb.shape[:2] or depth.shape!=mask.shape:raise RuntimeError('Pass dimensions mismatch')
if not np.any(mask):raise RuntimeError('Focus is not visible')
out=Path(a.out);out.mkdir(parents=True,exist_ok=False)
imageio.imwrite(out/'rgb.png',rgb.astype(np.uint8) if rgb.dtype==np.uint8 else np.uint8(np.clip(rgb,0,1)*255))
imageio.imwrite(out/'focus.png',mask.astype(np.uint8)*255)
np.savez_compressed(out/'passes.npz',rgb=rgb,mask=mask,depth=depth,normals=normals)
