"""Run only in Blender with an approved, aligned metarig or an existing approved Rigify rig."""
import argparse, hashlib, json, math, pathlib, sys
import bpy
from mathutils import Matrix
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from nla_layers import compose
p=argparse.ArgumentParser();p.add_argument('--config',required=True,type=pathlib.Path);p.add_argument('--out',required=True,type=pathlib.Path);a=p.parse_args(sys.argv[sys.argv.index('--')+1:]); cfg=json.loads(a.config.read_text());out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
source=pathlib.Path(bpy.data.filepath); assert source.is_file() and hashlib.sha256(source.read_bytes()).hexdigest()==cfg['source_sha256'], 'source mismatch'
assert any(k=='rigify' or k.endswith('.rigify') for k in bpy.context.preferences.addons.keys()),'Rigify not enabled'
def select(obj):
    if bpy.context.object and bpy.context.object.mode!='OBJECT': bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
if cfg['mode']=='generate':
    raise ValueError('use Rigify producer for generation')
    meta=bpy.data.objects[cfg['metarig']]; assert meta.type=='ARMATURE'; select(meta)
    assert bpy.ops.pose.rigify_generate.poll(),'Rigify context unavailable'
    assert 'FINISHED' in bpy.ops.pose.rigify_generate(), 'generation failed'
    rig=meta.data.rigify_target_rig
    assert rig and any(b.name.startswith('DEF-') and b.use_deform for b in rig.data.bones), 'no generated deform rig'
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'generated.blend')); print('Generated rig only: requires reviewed binding and authored actions');sys.exit(0)
assert cfg['mode']=='sample';rig=bpy.data.objects[cfg['rig']];assert rig.type=='ARMATURE' and any(b.name.startswith('DEF-') and b.use_deform for b in rig.data.bones),'not Rigify deform rig'
meshes=[bpy.data.objects[n] for n in cfg['meshes']];assert meshes and all(o.type=='MESH' and any(m.type=='ARMATURE' and m.object==rig for m in o.modifiers) for o in meshes),'approved mesh binding missing'
scene=bpy.context.scene;fps=float(scene.render.fps)/scene.render.fps_base;assert fps>0
required={'idle','walk','run','jump_start','jump_loop','jump_land','light_attack','heavy_attack','air_attack'};assert required<=set(cfg['clips']),'missing actions'
assert rig.animation_data and not any(not t.mute for t in rig.animation_data.nla_tracks),'mute NLA tracks for isolated actions'
# Blender Z-up -> glTF Y-up. Rig-local positions, converted to metres.
unit=scene.unit_settings.scale_length or 1.0
bones=cfg['bones'];assert {'foot_l','foot_r','sword','hip'}<=set(bones)
for n in bones.values():assert n in rig.pose.bones,n
def pos(v):return [float(v.x*unit),float(v.z*unit),float(-v.y*unit)]
clips={};ad=rig.animation_data
for name,spec in cfg['clips'].items():
    act=bpy.data.actions[spec['action']]; cleanup=compose(rig,spec)
    start,end=spec['start'],spec['end'];assert isinstance(start,int) and isinstance(end,int) and start<end and end-start<=600
    assert act.frame_range[0]<=start and end<=act.frame_range[1],'clip outside authored range'
    frames=[];contacts=spec.get('contacts',{});events=spec.get('events',[])
    for k in ('foot_l','foot_r'):
        for lo,hi in contacts.get(k,[]):assert start<=lo<hi<=end
    if name in ('walk','run'): assert all(contacts.get(k) for k in ('foot_l','foot_r')),'foot contact intervals required'
    expected={'light_attack':'light_hit','heavy_attack':'heavy_hit','air_attack':'air_hit','jump_start':'takeoff','jump_land':'land'}.get(name)
    if expected:assert sum(e['cue']==expected for e in events)==1,'missing or duplicate authored cue'
    for e in events:assert start<=e['frame']<=end and e['bone'] in bones
    for f in range(start,end+1):
        scene.frame_set(f); dg=bpy.context.evaluated_depsgraph_get();r=rig.evaluated_get(dg)
        points={k:pos(r.pose.bones[n].head) for k,n in bones.items()}
        world={k:pos(r.matrix_world@r.pose.bones[n].head) for k,n in bones.items()}
        assert all(math.isfinite(v) for d in (points,world) for xyz in d.values() for v in xyz)
        basis=Matrix(((1,0,0),(0,0,1),(0,-1,0)))
        q=(basis @ r.pose.bones[bones['sword']].matrix.to_3x3().normalized() @ basis.transposed()).to_quaternion()
        frames.append({'frame':f,'time':(f-start)/fps,'local':points,'world':world,'sword_quaternion_xyzw':[q.x,q.y,q.z,q.w]})
    clips[name]={'fps':fps,'frames':frames,'contacts':contacts,'events':events,'root_velocity_mps':spec.get('root_velocity_mps',[0,0,0]),'action':act.name,'layers':spec.get('layers',[])}
    cleanup()
(out/'rig-motion.json').write_text(json.dumps({'schema':'rigify-motion-v1','source_sha256':cfg['source_sha256'],'hero_id':cfg['hero_id'],'layer_recipe_sha256':hashlib.sha256(a.config.read_bytes()).hexdigest(),'axes':'gltf-y-up-metres','clips':clips},allow_nan=False))
print('Layered evaluated motion sampled; identical NLA evaluation required for GLB/volume baking. No visual approval.')
