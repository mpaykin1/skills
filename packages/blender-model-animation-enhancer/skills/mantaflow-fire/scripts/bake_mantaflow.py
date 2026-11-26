"""Run only inside a disposable Blender 4.5 LTS background process."""
import argparse, json, sys, math
from pathlib import Path
import bpy
from mathutils import Vector
p=argparse.ArgumentParser(); p.add_argument('--out',required=True); p.add_argument('--resolution',type=int,default=64); p.add_argument('--frames',type=int,default=48); p.add_argument('--warmup',type=int,default=48); a=p.parse_args(sys.argv[sys.argv.index('--')+1:]); out=Path(a.out).resolve()
if not 32<=a.resolution<=128 or not 16<=a.frames<=64 or not 24<=a.warmup<=120: raise ValueError('bounded CPU job required')
out.mkdir(parents=True,exist_ok=False)
if bpy.app.version[:2]!=(4,5) or not bpy.app.build_options.fluid: raise RuntimeError('Blender 4.5 LTS with fluid support required')
bpy.ops.wm.read_factory_settings(use_empty=True); s=bpy.context.scene; s.frame_start=1; s.frame_end=a.warmup+a.frames; s.render.fps=24

def cube(name,loc,scale):
    bpy.ops.mesh.primitive_cube_add(size=2,location=loc); o=bpy.context.object; o.name=name; o.scale=scale; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); return o

def activate(o):
    bpy.ops.object.select_all(action='DESELECT'); o.select_set(True); bpy.context.view_layer.objects.active=o

source=cube('Fuel source',(0,0,.35),(.58,.38,.20)); fm=source.modifiers.new('Mantaflow fuel','FLUID'); fm.fluid_type='FLOW'; bpy.context.view_layer.update(); f=fm.flow_settings; f.flow_type='BOTH'; f.flow_behavior='INFLOW'; f.fuel_amount=1.25; f.density=.8; source.hide_render=True
box=cube('Gas domain',(0,0,1.8),(1.5,1.5,1.8)); dm=box.modifiers.new('Mantaflow gas','FLUID'); dm.fluid_type='DOMAIN'; bpy.context.view_layer.update(); d=dm.domain_settings; d.domain_type='GAS'; d.resolution_max=a.resolution; d.cache_type='ALL'; d.cache_directory=str(out/'cache'); d.cache_frame_start=1; d.cache_frame_end=s.frame_end; d.cache_data_format='OPENVDB'; d.use_adaptive_domain=False; d.use_noise=True; d.noise_scale=2
mat=bpy.data.materials.new('Smoke and flame'); mat.use_nodes=True; nodes=mat.node_tree.nodes; nodes.clear(); vol=nodes.new('ShaderNodeVolumePrincipled'); vol.inputs['Density'].default_value=2.4; vol.inputs['Density Attribute'].default_value='density'; vol.inputs['Blackbody Intensity'].default_value=1.8; vol.inputs['Temperature Attribute'].default_value='temperature'; vol.inputs['Color'].default_value=(.23,.20,.18,1); output=nodes.new('ShaderNodeOutputMaterial'); mat.node_tree.links.new(vol.outputs['Volume'],output.inputs['Volume']); box.data.materials.append(mat)
# Blackbody intensity is modulated by flame, not smoke temperature alone.
flame=nodes.new('ShaderNodeAttribute'); flame.attribute_name='flame'; multiply=nodes.new('ShaderNodeMath'); multiply.operation='MULTIPLY'; multiply.inputs[1].default_value=3.0; mat.node_tree.links.new(flame.outputs['Fac'],multiply.inputs[0]); mat.node_tree.links.new(multiply.outputs[0],vol.inputs['Blackbody Intensity'])
s.world=bpy.data.worlds.new('Ambient'); s.world.use_nodes=True; s.world.node_tree.nodes['Background'].inputs[0].default_value=(.18,.18,.18,1); s.world.node_tree.nodes['Background'].inputs[1].default_value=.5
bpy.ops.object.camera_add(location=(0,-9,2.1)); cam=bpy.context.object; cam.rotation_euler=(Vector((0,0,1.8))-cam.location).to_track_quat('-Z','Y').to_euler(); cam.data.type='ORTHO'; cam.data.ortho_scale=4.2; s.camera=cam
s.render.engine='CYCLES'; s.cycles.device='CPU'; s.cycles.samples=24; s.cycles.use_denoising=False; s.render.resolution_x=192; s.render.resolution_y=256; s.render.resolution_percentage=100; s.render.film_transparent=True; s.render.image_settings.file_format='PNG'; s.render.image_settings.color_mode='RGBA'; s.view_settings.view_transform='AgX'
activate(box); bpy.ops.wm.save_as_mainfile(filepath=str(out/'fire.blend')); result=bpy.ops.fluid.bake_all();
if 'FINISHED' not in result or not list((out/'cache').rglob('*.vdb')): raise RuntimeError('no real Mantaflow VDB cache')
frames=out/'frames'; frames.mkdir();
for i,frame in enumerate(range(a.warmup+1,s.frame_end+1)):
    s.frame_set(frame); s.render.filepath=str(frames/f'{i:03d}.png'); bpy.ops.render.render(write_still=True)
(out/'bake.json').write_text(json.dumps({'source':'blender-mantaflow','blender':bpy.app.version_string,'fps':24,'frames':a.frames,'resolution':a.resolution,'warmup':a.warmup,'camera':'orthographic','width_m':3.15,'height_m':4.2},indent=2)); print('MANTAFLOW_RENDER_COMPLETE')
