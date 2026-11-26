"""Blender 4.5: non-destructive OpenSubdiv on an approved 3D source copy.
Run via blender --background SOURCE.blend --python-exit-code 1 --python refine.py -- CONFIG OUTDIR
"""
import argparse, hashlib, json, math, sys
from pathlib import Path
import bpy

def digest(p):
    with open(p,'rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()

def snapshot(obj, deps):
    ev=obj.evaluated_get(deps); me=ev.to_mesh()
    try:
        if not me.vertices: raise ValueError(f'empty mesh {obj.name}')
        me.calc_loop_triangles(); lo=[math.inf]*3; hi=[-math.inf]*3
        for v in me.vertices:
            p=ev.matrix_world @ v.co
            if not all(math.isfinite(x) for x in p): raise ValueError('nonfinite vertex')
            for i,x in enumerate(p): lo[i]=min(lo[i],x);hi[i]=max(hi[i],x)
        return {'triangles':len(me.loop_triangles),'vertices':len(me.vertices),'min':lo,'max':hi}
    finally: ev.to_mesh_clear()

def bones(rigs,deps):
    return {o.name:{b.name: [float(x) for row in b.matrix for x in row] for b in o.evaluated_get(deps).pose.bones} for o in rigs}

def main():
    a=argparse.ArgumentParser();a.add_argument('config',type=Path);a.add_argument('out',type=Path);a=a.parse_args(sys.argv[sys.argv.index('--')+1:]);cfg=json.loads(a.config.read_text());src=Path(bpy.data.filepath).resolve()
    if bpy.app.version[:2]!=(4,5): raise ValueError('requires reviewed Blender 4.5 LTS')
    if not src.is_file() or digest(src)!=cfg['source_sha256']: raise ValueError('source hash mismatch')
    if not cfg.get('hero_id') or cfg.get('approved_source') is not True: raise ValueError('approved true 3D source required')
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    frames=cfg['sample_frames'];limit=int(cfg.get('max_total_triangles',500000));drift=float(cfg.get('max_bounds_shift_m',0.015));
    if not frames or len(frames)>120 or any(type(f)!=int for f in frames) or not 1<=limit<=2000000 or not math.isfinite(drift) or not 0<drift<=0.05: raise ValueError('invalid budget or frames')
    scene=bpy.context.scene;old=scene.frame_current;plan=cfg['meshes'];names=[e['object'] for e in plan]
    if not names or len(names)!=len(set(names)): raise ValueError('duplicate or empty mesh plan')
    objs=[bpy.data.objects[n] for n in names];rigs=[bpy.data.objects[n] for n in cfg['rigs']]
    if not rigs or any(o.type!='ARMATURE' for o in rigs) or any(o.type!='MESH' or o.library or o.data.library or o.override_library for o in objs): raise ValueError('local meshes and rig required')
    if scene.unit_settings.system!='METRIC' or abs(scene.unit_settings.scale_length-1)>1e-6: raise ValueError('explicit metre scale required')
    def sample():
        rows=[]
        for f in frames:
            scene.frame_set(f);bpy.context.view_layer.update();deps=bpy.context.evaluated_depsgraph_get()
            rows.append({'frame':f,'objects':{o.name:snapshot(o,deps) for o in objs},'bones':bones(rigs,deps)})
        return rows
    before=sample()
    # Limit based on evaluated pre-subdiv face corners (worst-case first refinement) before allocating.
    total=0
    for e,o in zip(plan,objs):
        level=e['levels'];role=e['role'];
        if type(level)!=int or level not in (0,1,2) or role not in ('cloth','body','hair','armor','blade','hilt'): raise ValueError('unsupported level or role')
        if any(m.type=='SUBSURF' for m in o.modifiers): raise ValueError('existing subdivision: review separately, no stacking')
        if level and role in ('blade','hilt','armor'):
            attr=o.data.attributes.get('crease_edge')
            if not e.get('approved_hard_edges') or not attr or attr.domain!='EDGE' or not any(x.value>=0.99 for x in attr.data): raise ValueError('hard-surface needs reviewed edge creases; otherwise level 0')
        peak=0
        for f in frames:
            scene.frame_set(f);bpy.context.view_layer.update();ev=o.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh()
            try: peak=max(peak,2*sum(len(p.vertices) for p in me.polygons)*4**(level-1) if level else max(1,len(me.polygons))*max(2,max((len(p.vertices)-2 for p in me.polygons),default=2)))
            finally: ev.to_mesh_clear()
        total+=peak
        if total>limit: raise ValueError('estimated mesh budget exceeded')
    for e,o in zip(plan,objs):
        if not e['levels']: continue
        m=o.modifiers.new('META_OpenSubdiv','SUBSURF');m.subdivision_type='CATMULL_CLARK';m.levels=m.render_levels=e['levels'];m.quality=4;m.use_creases=True;m.uv_smooth='PRESERVE_BOUNDARIES';m.boundary_smooth='PRESERVE_CORNERS'
        # Appended after deformation; do not apply to rest skin or alter source mesh data.
    after=sample()
    for b,c in zip(before,after):
        if sum(x['triangles'] for x in c['objects'].values())>limit: raise ValueError('actual triangle budget exceeded')
        for n,v in b['objects'].items():
            w=c['objects'][n]
            if max(abs(x-y) for k in ('min','max') for x,y in zip(v[k],w[k]))>drift: raise ValueError(f'bounding extent drift: {n} frame {b["frame"]}')
        for rig,bs in b['bones'].items():
            if set(bs)!=set(c['bones'][rig]) or any(max(abs(x-y) for x,y in zip(v,c['bones'][rig][n]))>1e-5 for n,v in bs.items()): raise ValueError('evaluated rig changed')
    scene.frame_set(old);target=out/'refined.blend';bpy.ops.wm.save_as_mainfile(filepath=str(target),copy=True)
    if digest(src)!=cfg['source_sha256']: raise ValueError('source changed')
    manifest={'schema':'meta-opensubdiv-v1','hero_id':cfg['hero_id'],'parent_sha256':cfg['source_sha256'],'derived_sha256':digest(target),'recipe_sha256':digest(a.config),'blender_version':bpy.app.version_string,'meshes':plan,'max_total_triangles':limit,'max_bounds_shift_m':drift,'frames':[{'frame':b['frame'],'before':b['objects'],'after':c['objects']} for b,c in zip(before,after)],'visual_approved':False}
    (out/'subdiv.json').write_text(json.dumps(manifest,indent=2));print(target)
if __name__=='__main__': main()
