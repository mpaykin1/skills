"""CPU Cycles OSL -> linear UV-space map candidates; no source project mutation."""
import argparse, hashlib, json, math, sys
from pathlib import Path
import bpy
import numpy as np
from cycles.osl import update_script_node

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def require(ok,msg):
    if not ok: raise RuntimeError(msg)

def main():
    p=argparse.ArgumentParser();p.add_argument('--preset',choices=['cloth','steel'],required=True);p.add_argument('--base',nargs=3,type=float,required=True);p.add_argument('--detail',type=float,default=.65);p.add_argument('--size',type=int,default=1024);p.add_argument('--threads',type=int,default=4);p.add_argument('--out',type=Path,required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);
    require(bpy.app.version[:2]==(4,5),'requires reviewed Blender 4.5 LTS');require(a.size in (256,512,1024,2048),'size');require(1<=a.threads<=32 and 0<a.detail<=1 and all(math.isfinite(v) and 0<v<=1 for v in a.base),'parameters');require(not a.out.exists(),'output already exists');out=a.out.resolve();out.mkdir(parents=True);shader=Path(__file__).resolve().parents[1]/'shaders/meta_surface.osl'
    bpy.ops.wm.read_factory_settings(use_empty=True)
    s=bpy.context.scene;s.render.engine='CYCLES';s.cycles.device='CPU';s.cycles.shading_system=True;require(s.cycles.shading_system,'OSL unavailable');s.cycles.samples=8;s.cycles.use_denoising=False;s.render.threads_mode='FIXED';s.render.threads=a.threads;s.render.resolution_x=s.render.resolution_y=a.size;s.render.resolution_percentage=100;s.render.image_settings.file_format='OPEN_EXR';s.render.image_settings.color_depth='32';s.render.image_settings.color_mode='RGB';s.render.film_transparent=False;s.view_settings.view_transform='Standard';s.view_settings.look='None';s.view_settings.exposure=0;s.view_settings.gamma=1
    bpy.ops.mesh.primitive_plane_add(size=2);plane=bpy.context.object
    bpy.ops.object.camera_add(location=(0,0,3),rotation=(0,0,0));cam=bpy.context.object;cam.data.type='ORTHO';cam.data.ortho_scale=2;s.camera=cam
    mat=bpy.data.materials.new('META OSL maps');mat.use_nodes=True;plane.data.materials.append(mat);nt=mat.node_tree;nt.nodes.clear();uv=nt.nodes.new('ShaderNodeTexCoord');node=nt.nodes.new('ShaderNodeScript');node.mode='INTERNAL';node.script=bpy.data.texts.new('meta_surface.osl');node.script.write(shader.read_text());require(update_script_node(node,lambda level,msg: print(level,msg)),'OSL compile failed');require(all(x in node.outputs for x in ['Albedo','Roughness','Height']),'missing OSL outputs');nt.links.new(uv.outputs['UV'],node.inputs['UV']);node.inputs['Base'].default_value=(*a.base,1);node.inputs['Steel'].default_value=int(a.preset=='steel');node.inputs['Detail'].default_value=a.detail
    e=nt.nodes.new('ShaderNodeEmission');e.inputs['Strength'].default_value=1;o=nt.nodes.new('ShaderNodeOutputMaterial');nt.links.new(e.outputs['Emission'],o.inputs['Surface']);maps={}
    for name in ['Albedo','Roughness','Height']:
        nt.links.new(node.outputs[name],e.inputs['Color']);path=out/(name+'.exr');s.render.filepath=str(path);bpy.ops.render.render(write_still=True);require(path.is_file(),'render missing');im=bpy.data.images.load(str(path),check_existing=False);require(tuple(im.size)==(a.size,a.size),'render dimensions');arr=np.empty(a.size*a.size*4,np.float32);im.pixels.foreach_get(arr);arr=arr.reshape(a.size,a.size,4)[::-1,:,:3].copy();require(np.isfinite(arr).all() and arr.min()>=-1e-5 and arr.max()<=1.001,'invalid linear output');require(float(arr.std(axis=(0,1)).max())>1e-5,'flat output');f=out/(name+'.npy');np.save(f,np.clip(arr,0,1),allow_pickle=False);maps[name]={'file':f.name,'sha256':sha(f),'exr_sha256':sha(path)};bpy.data.images.remove(im)
    manifest={'schema':'meta-osl-linear-v1','backend':'cycles-cpu-osl','blender_version':bpy.app.version_string,'shader_sha256':sha(shader),'preset':a.preset,'base_linear':a.base,'detail':a.detail,'size':a.size,'maps':maps,'approved':False};(out/'linear.json').write_text(json.dumps(manifest,indent=2))
if __name__=='__main__': main()
