"""Run inside Blender. Non-destructive cinematic layout and lighting authoring."""
import argparse, json, math, random, sys
from pathlib import Path
import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
p=argparse.ArgumentParser();p.add_argument('--focus',required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--plan',type=Path);p.add_argument('--mood',choices=['noir','warm','moon'],default='noir');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]); a.out=a.out.resolve();a.out.mkdir(parents=True,exist_ok=False)
scene=bpy.context.scene; focus=scene.objects.get(a.focus)
if not focus or focus.type!='MESH': raise ValueError('Focus must be an existing mesh object')
plan=json.loads(a.plan.read_text()) if a.plan else {}; rng=random.Random(plan.get('seed',0))
def bounds(o):
    pts=[o.matrix_world@Vector(v) for v in o.bound_box];return tuple(tuple(f(p[i] for p in pts) for i in range(3)) for f in (min,max))
def overlap(a,b):return all(a[0][i]<b[1][i]-1e-4 and a[1][i]>b[0][i]+1e-4 for i in range(3))
def aim(o,target):o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()
lo,hi=bounds(focus); target=Vector([(x+y)/2 for x,y in zip(lo,hi)]); scale=max(.5,(Vector(hi)-Vector(lo)).length)
original=scene.camera
if original:
    direction=original.matrix_world.translation-target
    if direction.length<.01:direction=Vector((0,-1,.3))
else:direction=Vector((0,-1,.3))
front=Vector((direction.x,direction.y,0));front=front.normalized() if front.length>.01 else Vector((0,-1,0)); right=Vector((-front.y,front.x,0)); up=Vector((0,0,1))
# Conservative candidate positions for explicitly allowed objects; floor contact stays at original height.
keep=[(v['min'],v['max']) for v in plan.get('keepouts',[])]; meshes=[o for o in scene.objects if o.type=='MESH']
for name in plan.get('movable',[]):
    o=scene.objects.get(name)
    if not o or o==focus or o.type!='MESH' or o.parent or o.children or o.animation_data or o.constraints or o.rigid_body:continue
    old=o.location.copy();best=old.copy();bestscore=0; origbox=bounds(o); radius=min(scale*.7,1.0)
    fixed=[bounds(q) for q in meshes if q!=o];fixed=[b for b in fixed if not overlap(origbox,b)]
    for _ in range(32):
        delta=right*rng.uniform(-radius,radius)+front*rng.uniform(-radius,radius);o.location=old+delta;bpy.context.view_layer.update();box=bounds(o)
        if any(overlap(box,b) for b in fixed+keep):continue
        pos=(Vector(box[0])+Vector(box[1]))/2-target;score=abs(pos.dot(right))-.25*abs(pos.dot(front))-.2*delta.length
        base=old-target;score-=abs(base.dot(right))-.25*abs(base.dot(front))
        if score>bestscore:bestscore=score;best=o.location.copy()
    o.location=best;bpy.context.view_layer.update()
if bpy.data.collections.get('CSD Directing'): raise ValueError('Already directed: start from an undirected scene')
collection=bpy.data.collections.new('CSD Directing');scene.collection.children.link(collection)
def create(name,data,position):
    o=bpy.data.objects.new(name,data);collection.objects.link(o);o.location=position;return o
cam=create('CSD Preview Camera',bpy.data.cameras.new('CSD Preview Lens'),target+front*scale*2+up*scale*.5);cam.data.lens=42;cam.data.clip_end=max(100,scale*100)
scene.camera=cam;scene.render.resolution_x=960;scene.render.resolution_y=540;scene.render.resolution_percentage=100
# Evaluate focus framing and line of sight across camera candidates.
pts=[focus.matrix_world@Vector(v) for v in focus.bound_box];deps=bpy.context.evaluated_depsgraph_get();best=None
for distance in (1.5,2,2.6,3.3):
    for lateral in (-.5,0,.5):
        for elevation in (.15,.45,.75):
            cam.location=target+scale*(distance*front+lateral*right+elevation*up);aim(cam,target+right*scale*.12);bpy.context.view_layer.update();uv=[world_to_camera_view(scene,cam,v) for v in pts]; center=world_to_camera_view(scene,cam,target)
            if any(v.z<=0 or not(.04<v.x<.96 and .04<v.y<.96) for v in uv):continue
            d=target-cam.location;hit,_,_,_,obj,_=scene.ray_cast(deps,cam.location,d.normalized(),distance=d.length)
            if hit and obj.original!=focus:continue
            size=max(v.y for v in uv)-min(v.y for v in uv);score=1-abs(size-.48)-abs(center.x-.4)-abs(center.y-.5)
            if best is None or score>best[0]:best=(score,cam.location.copy(),cam.rotation_euler.copy())
if best is None:raise RuntimeError('No unobstructed focus camera candidate; adjust room/focus manually or through another search.')
cam.location,cam.rotation_euler=best[1:];
pal={'noir':((1,.75,.48),(.35,.55,1),(.55,.7,1)),'warm':((1,.76,.5),(.75,.8,1),(1,.45,.2)),'moon':((.55,.72,1),(.35,.45,.8),(.85,.9,1))}[a.mood]
for label,offset,power,size,color in [('Key',front*1.1-right*.8+up*1.1,180,0.7,pal[0]),('Fill',front*.7+right*1.2+up*.5,45,1.2,pal[1]),('Rim',-front*1.1+right*.3+up*1.1,220,.45,pal[2])]:
    data=bpy.data.lights.new('CSD '+label,'AREA');data.energy=power*scale**2;data.size=size*scale;data.color=color;o=create('CSD '+label,data,target+offset*scale);aim(o,target)
bpy.context.view_layer.update()
(a.out/'staging.json').write_text(json.dumps({'focus':a.focus,'seed':plan.get('seed',0),'camera':cam.name,'lights':{o.name:float(o.data.energy) for o in collection.objects if o.type=='LIGHT'}},indent=2))
scene.render.image_settings.file_format='PNG';scene.render.filepath=str(a.out/'preview.png');bpy.ops.render.render(write_still=True)
scene.camera=original or cam;bpy.ops.wm.save_as_mainfile(filepath=str(a.out/'directed.blend'))
