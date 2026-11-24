#!/usr/bin/env python3
"""Run INSIDE Blender 4.5 LTS or Blender 5.x via --background --python.

Builds a native editable .blend with image-sequence planes in true XYZ depth,
optional genuinely authored GPv3 ink strokes, and exact pixel-root trajectories.
No rig/mesh transformations of drawn character pixels are used.
"""
from __future__ import annotations
import json
import math
import sys
from pathlib import Path
import bpy


def fail(msg):
    raise RuntimeError('LIA Blender: '+str(msg))


def _arguments():
    args=sys.argv
    if '--' not in args:fail('pass project directory after --')
    rem=args[args.index('--')+1:]
    if len(rem)!=1:fail('exactly one project directory required')
    base=Path(rem[0]).resolve()
    if not (base/'data'/'scene.json').is_file():fail('compiled scene.json missing')
    return base


def new_emissive(name,path,sequence=1,phase=0):
    mat=bpy.data.materials.new(name)
    mat.use_nodes=True
    if hasattr(mat,'surface_render_method'):
        mat.surface_render_method='DITHERED'
    nodes=mat.node_tree.nodes
    nodes.clear()
    tex=nodes.new('ShaderNodeTexImage')
    tex.image=bpy.data.images.load(str(path),check_existing=False)
    tex.interpolation='Closest'
    tex.extension='CLIP'
    if sequence>1:
        tex.image.source='SEQUENCE'
        tex.image_user.frame_duration=sequence
        tex.image_user.frame_start=1
        tex.image_user.frame_offset=phase
        tex.image_user.use_cyclic=True
        tex.image_user.use_auto_refresh=True
    emi=nodes.new('ShaderNodeEmission')
    transp=nodes.new('ShaderNodeBsdfTransparent')
    mix=nodes.new('ShaderNodeMixShader')
    output=nodes.new('ShaderNodeOutputMaterial')
    links=mat.node_tree.links
    links.new(tex.outputs['Color'],emi.inputs['Color'])
    links.new(tex.outputs['Alpha'],mix.inputs[0])
    links.new(transp.outputs[0],mix.inputs[1])
    links.new(emi.outputs[0],mix.inputs[2])
    links.new(mix.outputs[0],output.inputs['Surface'])
    return mat


def plane(name,x,y,z,w,h,ppu,texture):
    # Pixel positions are top-left anchored. UVs are 1:1; no character mesh warp.
    v=[(0,0,0),(0,0,-h/ppu),(w/ppu,0,-h/ppu),(w/ppu,0,0)]
    mesh=bpy.data.meshes.new(name+'_quad')
    mesh.from_pydata(v,[],[(0,1,2,3)])
    mesh.update()
    uv=mesh.uv_layers.new(name='OriginalPixels')
    for loop,uvp in zip(mesh.polygons[0].loop_indices,((0,1),(0,0),(1,0),(1,1))):
        uv.data[loop].uv=uvp
    obj=bpy.data.objects.new(name,mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.location=(x,y,z)
    obj.data.materials.append(texture)
    return obj


def _sample_path(points,t):
    if t<=points[0]['frame']:return float(points[0]['dx']),float(points[0]['dy'])
    if t>=points[-1]['frame']:return float(points[-1]['dx']),float(points[-1]['dy'])
    for a,b in zip(points,points[1:]):
        if a['frame']<=t<=b['frame']:
            u=(t-a['frame'])/(b['frame']-a['frame'])
            u=u*u*(3-2*u)
            return (a['dx']+(b['dx']-a['dx'])*u,a['dy']+(b['dy']-a['dy'])*u)
    fail('unreachable locomotion path')


def animate_actor(obj,actor,scene_total,ppu):
    loco=actor.get('locomotion')
    if not loco:return
    path=loco.get('path',[])
    cycle=int(actor['frame_count'])
    phase=int(actor['phase_frames'])
    first_x,first_y= obj.location.x,obj.location.z
    # Key every final-frame position to preserve the exact existing 2D cubic route.
    # Only the *root plane origin* moves; its original RGBA pixels remain untouched.
    for tick in range(scene_total+1):
        local=(tick+phase)%cycle
        dx,dy=_sample_path(path,local)
        obj.location.x=first_x+dx/ppu
        obj.location.z=first_y-dy/ppu
        obj.keyframe_insert('location',frame=tick+1)
    for fc in obj.animation_data.action.fcurves:
        if fc.data_path=='location':
            for key in fc.keyframe_points:key.interpolation='LINEAR'


def create_gp3_ink(data,ppu,height):
    if bpy.app.version < (4,3,0):fail('Grease Pencil v3 requires Blender >=4.3, recommended >=4.5')
    if hasattr(bpy.data,'grease_pencils_v3'):
        datablock=bpy.data.grease_pencils_v3.new('HandAuthored_Ink_GPv3')
    elif hasattr(bpy.data,'grease_pencils'):
        datablock=bpy.data.grease_pencils.new('HandAuthored_Ink_GPv3')
    else:fail('Grease Pencil v3 API not present')
    obj=bpy.data.objects.new('GreasePencil_Editable_Ink',datablock)
    bpy.context.scene.collection.objects.link(obj)
    # Blank frame stays available for manual ink painting without fabricating ink.
    if not data:
        layer=datablock.layers.new('Artist_Ink',set_active=True)
        layer.frames.new(1)
        return obj
    for spec in data:
        layer=datablock.layers.new(spec['id'],set_active=True)
        material=bpy.data.materials.new('Ink_'+spec['id'])
        bpy.data.materials.create_gpencil_data(material)
        material.grease_pencil.color=tuple(spec['rgba'])
        material.grease_pencil.show_stroke=True
        datablock.materials.append(material)
        mi=len(datablock.materials)-1
        for item in spec['keyframes']:
            frame=layer.frames.new(int(item['frame']))
            drawing=frame.drawing
            points=item['points']
            drawing.add_strokes([len(points)])
            # In GPv3, strokes are drawing geometry, not deforming a character sprite.
            stroke=drawing.strokes[0]
            stroke.material_index=mi
            for p,coord in zip(stroke.points,points):
                px,py=coord
                p.position=((px-data_width/2)/ppu,-float(spec['z_index'])*.002,
                            (height/2-py)/ppu)
                p.radius=float(spec['width_px'])/ppu/2.0
                p.opacity=float(spec['rgba'][3])
    return obj


def main():
    base=_arguments()
    data=json.loads((base/'data'/'scene.json').read_text('utf8'))
    width,height=int(data['width']),int(data['height'])
    fps,total=int(data['fps']),int(data['frames'])
    ppu=float(data['pixels_per_unit'])
    global data_width
    data_width=width
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    sc=bpy.context.scene
    sc.render.fps=fps
    sc.frame_start=1
    sc.frame_end=total
    sc.render.resolution_x=width
    sc.render.resolution_y=height
    sc.render.resolution_percentage=100
    if hasattr(sc.render,'film_transparent'):sc.render.film_transparent=False
    bgmat=new_emissive('Source_Background',base/'textures'/'background.png')
    plane('Background_Source_Clean',-width/2/ppu,0.6,height/2/ppu,width,height,ppu,bgmat)
    for entry in data['layers']:
        if not entry['visible']:continue
        name=str(entry['name'])
        mat=new_emissive('Layer_'+name,base/entry['file'])
        plane('Layer_'+name,-width/2/ppu,-entry['z_index']*.002,height/2/ppu,width,height,ppu,mat)
    for actor in data['actors']:
        name=str(actor['slug']);x,y,w,h=actor['box']
        mat=new_emissive('Actor_'+name,base/'sprites'/name/'0000.png',
                         int(actor['frame_count']),int(actor['phase_frames']))
        obj=plane('Actor_'+name,(x-width/2)/ppu,-int(actor['z_index'])*.002,
                  (height/2-y)/ppu,w,h,ppu,mat)
        obj['source_id']=str(actor['id'])
        obj['source_box_px']=json.dumps(actor['box'])
        obj['action_cycle']=json.dumps(actor['actions'])
        animate_actor(obj,actor,total,ppu)
    create_gp3_ink(data.get('gp_strokes',[]),ppu,height)
    bpy.ops.object.camera_add(location=(0,-15,0),rotation=(math.pi/2,0,0))
    cam=bpy.context.object
    cam.name='Camera_Registered_Source_2_5D'
    cam.data.type='ORTHO'
    cam.data.ortho_scale=height/ppu
    sc.camera=cam
    sc.frame_set(1)
    # Do NOT pack sequence images: every authentic source PNG is retained in ZIP.
    for img in bpy.data.images:
        if img.filepath and not img.filepath.startswith('//'):
            try:img.filepath=bpy.path.relpath(img.filepath,start=str(base))
            except Exception:pass
    bpy.ops.wm.save_as_mainfile(filepath=str(base/'living_scene.blend'))
    print('LIA_BLENDER_NATIVE_BLEND_CREATED',base/'living_scene.blend')

if __name__=='__main__':main()
