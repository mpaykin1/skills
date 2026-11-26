"""Blender 4.5 LTS worker. Run only in Blender, on an authorized original .blend."""
import argparse, json, math, subprocess, sys
from pathlib import Path
import bpy
from mathutils import Vector

def main():
    p=argparse.ArgumentParser(); p.add_argument('--rig',required=True); p.add_argument('--action',required=True); p.add_argument('--output',required=True); p.add_argument('--solver-python',required=True); p.add_argument('--radius',type=float,required=True); p.add_argument('--contacts',required=True,help='JSON list of {bone,start,end} in frame numbers; [] for floating/mechanical rig'); p.add_argument('--anchors',default='[]'); p.add_argument('--confirm-unintended-root-jitter',action='store_true',required=True); a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    src=Path(bpy.data.filepath).resolve(); out=Path(a.output).resolve()
    if not src.is_file() or out==src or out.exists() or out.suffix!='.blend' or not out.parent.is_dir(): raise ValueError('new .blend output required')
    if bpy.app.version[:2]!=(4,5): raise ValueError('Blender 4.5 LTS required')
    obj=bpy.data.objects[a.rig]; ad=obj.animation_data; sc=bpy.context.scene
    if obj.type!='ARMATURE' or obj.parent or obj.constraints or obj.library or not ad or not ad.action or ad.action.name!=a.action or len(ad.nla_tracks) or len(ad.drivers) or ad.action.users>1: raise ValueError('requires local unparented rig with exclusive active action, no object constraints/drivers/NLA')
    act=ad.action
    if len(act.slots)!=1 or len(act.layers)!=1 or len(act.layers[0].strips)!=1 or not ad.action_slot: raise ValueError('single slot/layer/strip only')
    bag=act.layers[0].strips[0].channelbag(ad.action_slot)
    if bag is None: raise ValueError('no action channelbag')
    curves=list(bag.fcurves); root=sorted([c for c in curves if c.data_path=='location'],key=lambda c:c.array_index)
    if [c.array_index for c in root]!=[0,1,2] or any(c.data_path.startswith('delta_') for c in curves): raise ValueError('explicit XYZ object root location required')
    if any(c.modifiers or c.mute or c.lock or c.sampled_points or any(k.interpolation!='LINEAR' for k in c.keyframe_points) for c in root): raise ValueError('requires dense linear root keys; no modifiers')
    if any(b.constraints for b in obj.pose.bones): raise ValueError('constraints require artist-directed rig workflow')
    if any(o.animation_data and o.animation_data.drivers for o in sc.objects): raise ValueError('scene drivers require separate inspection')
    if len(root[0].keyframe_points)<6: raise ValueError('at least six authored frames required')
    times=[float(k.co.x) for k in root[0].keyframe_points]; start=round(times[0]); frames=list(range(start,start+len(times)))
    if times!=frames or any([float(k.co.x) for k in c.keyframe_points]!=frames for c in root) or list(act.frame_range)!=[frames[0],frames[-1]]: raise ValueError('root must cover full action on every integer frame')
    contacts=json.loads(a.contacts); anchors=json.loads(a.anchors)
    if not isinstance(contacts,list) or not isinstance(anchors,list) or any(type(x)!=int or x not in frames for x in anchors): raise ValueError('invalid contact or anchor specification')
    for c in contacts:
        if c['bone'] not in obj.pose.bones or c['start'] not in frames or c['end'] not in frames or c['end']<=c['start']: raise ValueError('bad contact interval')
    original_frame=sc.frame_current; original_subframe=sc.frame_subframe
    def sample():
        positions=[]; poses=[]; world=[]
        for f in frames:
            sc.frame_set(f); bpy.context.view_layer.update(); ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
            positions.append(list(ev.location)); poses.append(tuple(tuple(v for row in b.matrix_basis for v in row) for b in ev.pose.bones)); world.append({c['bone']:tuple(ev.matrix_world @ ev.pose.bones[c['bone']].head) for c in contacts})
        return positions,poses,world
    before,poses,world=sample(); values=[[float(c.keyframe_points[i].co.y) for c in root] for i in range(len(frames))]
    if any((Vector(x)-Vector(y)).length>1e-5 for x,y in zip(before,values)): raise ValueError('evaluated root does not match raw channels')
    # Lock all declared contact frames, not merely the endpoints.
    locked=sorted(set([f-start for f in anchors]+[f-start for c in contacts for f in range(c['start'],c['end']+1)]))
    req={'p':values,'fps':sc.render.fps/sc.render.fps_base,'radius':a.radius,'anchors':locked}
    proc=subprocess.run([a.solver_python,str(Path(__file__).with_name('blender_root_solver.py'))],input=json.dumps(req),text=True,capture_output=True,check=True,timeout=180)
    result=json.loads(proc.stdout); q=result['positions']
    for k,curve in enumerate(root):
        for i,key in enumerate(curve.keyframe_points): key.co.y=q[i][k]
        curve.update()
    after,newposes,newworld=sample()
    if any((Vector(x)-Vector(y)).length>1e-5 for x,y in zip(after,q)): raise ValueError('evaluated output mismatch')
    if any(abs(x-y)>1e-6 for pa,pb in zip(poses,newposes) for ba,bb in zip(pa,pb) for x,y in zip(ba,bb)): raise ValueError('local bone pose changed')
    for c in contacts:
        for f in range(c['start'],c['end']+1):
            i=f-start
            if (Vector(world[i][c['bone']])-Vector(newworld[i][c['bone']])).length>1e-5: raise ValueError('contact position changed')
    sc.frame_set(original_frame,subframe=original_subframe); bpy.ops.wm.save_as_mainfile(filepath=str(out),copy=True)
    if not out.is_file(): raise RuntimeError('save failed')
    print('AQ_BLENDER_RESULT '+json.dumps({k:v for k,v in result.items() if k!='positions'},allow_nan=False))

if __name__=='__main__': main()
