#!/usr/bin/env python3
"""Non-destructive Instant Meshes ↔ Blender bridge for anatomical monster assets.

Prepare produces local-space OBJ geometry, preserving Blender source intact.
Finish transfers rig weights, UVs, material IDs and corrective shape-key deltas
via barycentric closest-point sampling, duplicates keyframe/NLA actions, checks
surface distance, and exports the *same* MONSTER_RIG and its animation clips.

Instant Meshes alone does not preserve those attributes; this Blender adapter
rebuilds them. Original geometry remains in .blend as a hidden rollback copy
when an LOD candidate is accepted. Low quality/invalid candidates are rejected.
"""
from __future__ import annotations
import argparse
import json
import math
import sys
from pathlib import Path
from collections import defaultdict

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

EXCLUDED=('ZA_','MPFB_','SCULPT_','TRELLIS_','IM_LOD_','IM_SOURCE_')

def parse_args():
    p=argparse.ArgumentParser()
    p.add_argument('--phase',required=True,choices=('prepare','finish'))
    p.add_argument('--blend',required=True)
    p.add_argument('--work-dir',required=True)
    p.add_argument('--output-blend',default='')
    p.add_argument('--output-glb',default='')
    p.add_argument('--ratio',type=float,default=.4)
    p.add_argument('--min-faces',type=int,default=220)
    p.add_argument('--max-dist-relative',type=float,default=.04)
    p.add_argument('--mean-dist-relative',type=float,default=.012)
    return p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])

def subject_meshes():
    rig=bpy.data.objects.get('MONSTER_RIG')
    if not rig or rig.type!='ARMATURE':raise RuntimeError('MONSTER_RIG missing')
    candidates=[]
    for obj in bpy.data.objects:
        if obj.type!='MESH' or obj.parent!=rig:continue
        if obj.name.startswith(EXCLUDED):continue
        if obj.get('reference_only') or obj.get('non_exportable_reference'):continue
        candidates.append(obj)
    if not candidates:raise RuntimeError('No original monster meshes attached to MONSTER_RIG')
    return rig,candidates

def basis_coords(mesh):
    if mesh.shape_keys and mesh.shape_keys.key_blocks:
        return [v.co.copy() for v in mesh.shape_keys.key_blocks[0].data]
    return [v.co.copy() for v in mesh.vertices]

def dump_obj(mesh,filename):
    # Mesh is saved in unposed local object coordinates. Instant Meshes does not
    # need deformation modifiers, and applying an armature would destroy rest pose.
    vertices=basis_coords(mesh)
    with open(filename,'w',encoding='ascii') as f:
        f.write('# Original Monster Anatomy 3D rest-pose geometry\n')
        for v in vertices:f.write('v %.9g %.9g %.9g\n'%(v.x,v.y,v.z))
        for poly in mesh.polygons:
            if len(poly.vertices)>=3:
                f.write('f '+' '.join(str(v+1) for v in poly.vertices)+'\n')

def load_obj(filename):
    vertices=[];faces=[]
    with open(filename,'r',encoding='utf8',errors='replace') as f:
        for line in f:
            parts=line.split()
            if not parts:continue
            if parts[0]=='v' and len(parts)>=4:
                vertices.append(Vector(tuple(float(x) for x in parts[1:4])))
            elif parts[0]=='f':
                fverts=[]
                for item in parts[1:]:
                    t=int(item.split('/')[0]); idx=t-1 if t>0 else len(vertices)+t
                    if idx<0 or idx>=len(vertices):raise RuntimeError('Bad OBJ face vertex index')
                    fverts.append(idx)
                if len(fverts)>=3 and len(set(fverts))==len(fverts):faces.append(fverts)
    if len(vertices)<4 or len(faces)<16:raise RuntimeError('Instant Meshes produced unusable OBJ geometry')
    return vertices,faces

def prepare(opts,work):
    rig,meshes=subject_meshes()
    work.mkdir(parents=True,exist_ok=True)
    items=[]
    for obj in sorted(meshes,key=lambda x:x.name):
        source_faces=len(obj.data.polygons)
        if source_faces<opts.min_faces:continue
        target=max(64,int(source_faces*opts.ratio))
        if target>=int(source_faces*.9):continue
        idx=len(items)
        name='part_%03d'%idx
        dump_obj(obj.data,work/(name+'_source.obj'))
        items.append({'name':obj.name,'stem':name,'source_faces':source_faces,
                      'target_faces':target,'source_vertices':len(obj.data.vertices),
                      'shape_keys':[x.name for x in obj.data.shape_keys.key_blocks] if obj.data.shape_keys else [],
                      'vertex_groups':[x.name for x in obj.vertex_groups]})
    if not items:raise RuntimeError('No sufficiently dense meshes; cannot claim topology reduction')
    (work/'manifest.json').write_text(json.dumps({'rig':rig.name,'items':items},indent=2),encoding='utf8')
    print('Retopology candidates:',len(items))

def bary_weights(p,a,b,c):
    v0=b-a;v1=c-a;v2=p-a
    d00=v0.dot(v0);d01=v0.dot(v1);d11=v1.dot(v1)
    d20=v2.dot(v0);d21=v2.dot(v1)
    det=d00*d11-d01*d01
    if abs(det)<1e-18:return (1.,0.,0.)
    v=(d11*d20-d01*d21)/det
    w=(d00*d21-d01*d20)/det
    u=1.-v-w
    # Numerical clamping for triangle edges, do not extrapolate across gaps.
    ws=[max(0.,min(1.,x)) for x in (u,v,w)]
    total=sum(ws)
    return tuple(x/total for x in ws) if total else (1.,0.,0.)

def bb_diag(vertices):
    lo=Vector(tuple(min(v[k] for v in vertices) for k in range(3)))
    hi=Vector(tuple(max(v[k] for v in vertices) for k in range(3)))
    return (hi-lo).length,lo,hi

def clone_nla(source_keys,dest_keys):
    if not source_keys or not dest_keys or not source_keys.animation_data:return
    src=source_keys.animation_data
    dst=dest_keys.animation_data_create()
    if src.action:dst.action=src.action
    for tr in src.nla_tracks:
        new_tr=dst.nla_tracks.new()
        new_tr.name=tr.name
        for strip in tr.strips:
            if not strip.action:raise RuntimeError('NLA strip without action: '+tr.name)
            st=new_tr.strips.new(strip.name,int(round(strip.frame_start)),strip.action)
            # Retiming controls used for muscle shape-key clips.
            for prop in ('scale','repeat','blend_type','extrapolation','influence','mute','use_auto_blend'):
                try:setattr(st,prop,getattr(strip,prop))
                except (AttributeError,TypeError,ValueError):pass
        new_tr.mute=tr.mute
        if hasattr(new_tr,'is_solo'):new_tr.is_solo=tr.is_solo
    if len(dst.nla_tracks)!=len(src.nla_tracks):
        raise RuntimeError('Morph NLA clip count changed during topology transfer')

def project_morphs(src,dst,nearest,srccoords):
    old=src.data.shape_keys
    if old is None:return
    keys=old.key_blocks
    dst.shape_key_add(name='Basis',from_mix=False)
    for key in list(keys)[1:]:
        new_key=dst.shape_key_add(name=key.name,from_mix=False)
        for i,(indices,ws,point,_tri) in enumerate(nearest):
            delta=Vector((0,0,0))
            for j,w in zip(indices,ws):
                delta+=(key.data[j].co-srccoords[j])*w
            new_key.data[i].co=point+delta
        new_key.value=key.value
        new_key.slider_min=key.slider_min
        new_key.slider_max=key.slider_max
        new_key.interpolation=key.interpolation
        new_key.vertex_group=key.vertex_group
    clone_nla(old,dst.data.shape_keys)
    if len(dst.data.shape_keys.key_blocks)!=len(keys):
        raise RuntimeError('Lost corrective morph shape keys')

def transfer_data(src,dst,nearest,triangle_loops,source_polygons,src_tri_mats):
    # Object duplicate retains group names but source weights are mesh-vertex data.
    group_names={group.index:group.name for group in src.vertex_groups}
    candidate_groups={g.name:g for g in dst.vertex_groups}
    for name in group_names.values():
        if name not in candidate_groups:candidate_groups[name]=dst.vertex_groups.new(name=name)
    vertex_weights=[]
    for v in src.data.vertices:
        vertex_weights.append({g.group:g.weight for g in v.groups})
    for i,(indices,weights,_p,_tri) in enumerate(nearest):
        gathered=defaultdict(float)
        for ix,w in zip(indices,weights):
            for group,val in vertex_weights[ix].items():gathered[group]+=w*val
        s=sum(gathered.values())
        if src.vertex_groups and s<1e-5:
            raise RuntimeError('Skinning weights missing near retopologized vertex '+str(i))
        for ix,val in gathered.items():
            if val>1e-6:candidate_groups[group_names[ix]].add([i],float(val/s),'REPLACE')
    if src.vertex_groups and not any(mod.type=='ARMATURE' for mod in dst.modifiers):
        mod=dst.modifiers.new('Original Monster Armature','ARMATURE')
        mod.object=src.parent
    # UVs and material indices are inherited from nearest original face.
    for mat in src.data.materials:dst.data.materials.append(mat)
    for src_uv in src.data.uv_layers:
        uv_layer=dst.data.uv_layers.new(name=src_uv.name)
        for poly in dst.data.polygons:
            for loop in poly.loop_indices:
                v_index=dst.data.loops[loop].vertex_index
                _ix,weights,_p,vertex_tri=nearest[v_index]
                loops=triangle_loops[vertex_tri]
                u=Vector((0,0))
                for j,w in zip(loops,weights):u+=src_uv.data[j].uv*w
                uv_layer.data[loop].uv=u
    if src.data.uv_layers:
        dst.data.uv_layers.active_index=src.data.uv_layers.active_index
    for poly in dst.data.polygons:
        src_face=source_polygons[poly.index]
        poly.material_index=src_tri_mats[src_face]
        poly.use_smooth=src.data.polygons[src.data.loop_triangles[src_face].polygon_index].use_smooth

def make_lod(source,vertices,faces,opts):
    src_coords=basis_coords(source.data)
    diag,lo,hi=bb_diag(src_coords)
    if diag<1e-6:raise RuntimeError('Degenerate source mesh')
    _diagout,olo,ohi=bb_diag(vertices)
    if max((olo-lo).length,(ohi-hi).length)/diag>.08:
        raise RuntimeError('Retopo bbox changed by more than 8% of source diagonal')
    # Faces are triangulated only for sampling; output Instant Meshes quads remain quads.
    source.data.calc_loop_triangles() if hasattr(source.data,'calc_loop_triangles') else None
    looptris=source.data.loop_triangles
    tris=[tuple(t.vertices) for t in looptris]
    if not tris:raise RuntimeError('Source has no surface triangles')
    bvh=BVHTree.FromPolygons(src_coords,tris,all_triangles=True)
    src_tri_mats=[source.data.polygons[t.polygon_index].material_index for t in looptris]
    tri_loops=[tuple(t.loops) for t in looptris]
    projected=[];nearest=[];errors=[]
    for v in vertices:
        loc,normal,face_id,distance=bvh.find_nearest(v)
        if loc is None or face_id is None:raise RuntimeError('Source BVH could not find surface')
        indices=tris[face_id]
        weights=bary_weights(loc,*(src_coords[j] for j in indices))
        p=loc.copy() # Surface projection retains base sculpture details more accurately
        nearest.append((indices,weights,p,face_id))
        projected.append(p)
        errors.append(float(distance))
    if max(errors)/diag>opts.max_dist_relative or sum(errors)/len(errors)/diag>opts.mean_dist_relative:
        raise RuntimeError('Remesh deviates from original geometry beyond tolerance')
    # Track material/UV source triangle per output polygon (closest polygon centroid).
    poly_tri=[]
    for face in faces:
        centroid=sum((projected[j] for j in face),Vector((0,0,0)))/len(face)
        _p,_n,idx,_d=bvh.find_nearest(centroid)
        if idx is None:raise RuntimeError('Lost polygon material correspondence')
        poly_tri.append(idx)
    new_mesh=bpy.data.meshes.new('IM_LOD_'+source.data.name)
    new_mesh.from_pydata(projected,[],faces)
    new_mesh.update()
    lod=source.copy()
    lod.data=new_mesh
    for collection in list(lod.users_collection):collection.objects.unlink(lod)
    col=bpy.data.collections.get('IM_LOD_GAME')
    if col is None:
        col=bpy.data.collections.new('IM_LOD_GAME')
        bpy.context.scene.collection.children.link(col)
    col.objects.link(lod)
    lod.name='IM_LOD_'+source.name
    lod['retopo_source']=source.name
    lod['retopo_method']='Instant Meshes field-aligned quad remeshing'
    lod['non_exportable_reference']=False
    lod['reference_only']=False
    lod.hide_render=False
    # Preserve mesh custom properties that affect downstream behavior.
    for prop in source.data.keys():
        try:lod.data[prop]=source.data[prop]
        except (TypeError,ValueError):pass
    project_morphs(source,lod,nearest,src_coords)
    transfer_data(source,lod,nearest,tri_loops,poly_tri,src_tri_mats)
    # Original remains in the .blend for rollback, but not selected for GLB.
    source['retopo_backup']=True
    source['non_exportable_reference']=True
    source.hide_render=True
    source.hide_set(True)
    return lod,{'name':source.name,'old_faces':len(source.data.polygons),
                'new_faces':len(lod.data.polygons),
                'mean_nearest_relative':round(sum(errors)/len(errors)/diag,6),
                'max_nearest_relative':round(max(errors)/diag,6),
                'shape_keys':len(source.data.shape_keys.key_blocks) if source.data.shape_keys else 0,
                'rig_weights':len(source.vertex_groups)}

def glb_export(path,rig,game_meshes):
    for obj in bpy.context.selected_objects:obj.select_set(False)
    export=[rig]+game_meshes
    for obj in export:obj.hide_set(False);obj.select_set(True)
    bpy.context.view_layer.objects.active=rig
    bpy.ops.export_scene.gltf(filepath=str(path),export_format='GLB',use_selection=True,
        export_animations=True,export_animation_mode='NLA_TRACKS',
        export_skins=True,export_morph=True,export_force_sampling=True,
        export_apply=False,export_cameras=False,export_lights=False)
    for obj in export:obj.select_set(False)
    if not path.is_file() or path.stat().st_size<1000:raise RuntimeError('Missing or empty exported GLB')

def finish(opts,work):
    src=Path(opts.blend).resolve()
    manifest=json.loads((work/'manifest.json').read_text(encoding='utf8'))
    rig,base_meshes=subject_meshes()
    lookup={o.name:o for o in base_meshes}
    notes=[];success=0
    for entry in manifest['items']:
        output_obj=work/(entry['stem']+'_retopo.obj')
        if not output_obj.is_file():raise RuntimeError('Missing output from Instant Meshes: '+str(output_obj))
        source=lookup.get(entry['name'])
        if source is None:raise RuntimeError('Original mesh disappeared: '+entry['name'])
        try:
            vertices,faces=load_obj(output_obj)
            if len(faces)>=len(source.data.polygons)*.92:
                raise RuntimeError('Face count reduction too small')
            lod,info=make_lod(source,vertices,faces,opts)
            notes.append(info);success+=1
        except Exception as ex:
            # No destructive mutation of the original if a candidate fails.
            # If Blender file has partially created LOD, full batch aborts
            # rather than saving a corrupt or different monster.
            raise RuntimeError('Retopology rejected for '+source.name+': '+str(ex)) from ex
    if success==0:raise RuntimeError('Instant Meshes generated no usable LOD candidates')
    game_meshes=[o for o in base_meshes if not o.get('retopo_backup')]
    game_meshes += [o for o in bpy.data.objects if o.type=='MESH' and o.name.startswith('IM_LOD_')
                    and not o.get('non_exportable_reference')]
    if not game_meshes:raise RuntimeError('No game meshes retained')
    if rig.animation_data and rig.animation_data.nla_tracks:
        rig_clips={t.name for t in rig.animation_data.nla_tracks if t.strips}
        if not rig_clips:raise RuntimeError('No animation clips on MONSTER_RIG')
    out_blend=Path(opts.output_blend).resolve();out_glb=Path(opts.output_glb).resolve()
    out_blend.parent.mkdir(parents=True,exist_ok=True);out_glb.parent.mkdir(parents=True,exist_ok=True)
    bpy.context.scene.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=str(out_blend))
    glb_export(out_glb,rig,game_meshes)
    (work/'retopo_internal.json').write_text(json.dumps({'completed':success,'results':notes},indent=2),encoding='utf8')
    print('Instant Meshes restored rig/morph/material/UV on',success,'mesh objects')

def main():
    opts=parse_args()
    if not (0.1<=opts.ratio<=0.8):raise ValueError('Ratio must be 0.1..0.8')
    bpy.ops.wm.open_mainfile(filepath=str(Path(opts.blend).resolve()))
    work=Path(opts.work_dir).resolve()
    if opts.phase=='prepare':prepare(opts,work)
    else:
        if not opts.output_blend or not opts.output_glb:raise ValueError('finish requires both outputs')
        finish(opts,work)

if __name__=='__main__':main()
