"""Monster Anatomy 3D starter: creates a real skinned mesh + animated armature + GLB in Blender.

This original script makes a muscular concept blockout with separate volumetric muscle
meshes. For scientific-style attachment-defined muscles, install and use the genuine
MyoGeneratorRemix addon from scripts/download_myogenerator.py.

Execute: blender --background --python scripts/build_monster.py -- --output monster.glb
"""
import sys, argparse, math
from pathlib import Path
import bpy
from mathutils import Vector

P=Vector

def V(x,y,z): return P((x,y,z))

def make_material(name, color, rough=0.89):
    mat=bpy.data.materials.new(name)
    mat.diffuse_color=(*color,1.0)
    mat.use_nodes=True
    bsdf=mat.node_tree.nodes.get('Principled BSDF')
    if bsdf:
        bsdf.inputs['Base Color'].default_value=(*color,1)
        bsdf.inputs['Roughness'].default_value=rough
    return mat

def build_rig():
    D={
     'root':(V(.0,0,1.72),V(.0,0,2.14),None),
     'pelvis':(V(.0,0,2.14),V(-.13,0,2.39),'root'),
     'spine':(V(-.13,0,2.39),V(-.56,0,2.91),'pelvis'),
     'neck':(V(-.56,0,2.91),V(-.98,0,2.69),'spine'),
     'head':(V(-.98,0,2.69),V(-1.31,0,2.56),'neck'),
    }
    for side,s in [('L',1),('R',-1)]:
        shoulder=V(-.51,s*.38,2.92)
        elbow=V(-.19,s*.61,2.04) if s==1 else V(-.05,s*.57,2.12)
        wrist=V(-1.14,s*.71,1.75) if s==1 else V(.65,s*.74,1.41)
        fingertips=V(-1.35,s*.74,1.30) if s==1 else V(.91,s*.78,1.10)
        hip=V(.06,s*.24,2.12)
        knee=V(.43,s*.44,1.30) if s==1 else V(-.08,s*.46,1.18)
        ankle=V(-.18,s*.51,.36) if s==1 else V(.58,s*.52,.36)
        toes=V(-.35,s*.51,.16) if s==1 else V(.77,s*.52,.14)
        D.update({
          'upperarm_'+side:(shoulder,elbow,'spine'),
          'forearm_'+side:(elbow,wrist,'upperarm_'+side),
          'hand_'+side:(wrist,fingertips,'forearm_'+side),
          'thigh_'+side:(hip,knee,'pelvis'),
          'shin_'+side:(knee,ankle,'thigh_'+side),
          'foot_'+side:(ankle,toes,'shin_'+side)
        })
    rig_data=bpy.data.armatures.new('Monster_Anatomical_Skeleton')
    rig=bpy.data.objects.new('MONSTER_RIG',rig_data)
    bpy.context.collection.objects.link(rig)
    bpy.context.view_layer.objects.active=rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    for name,(start,end,parent) in D.items():
        e=rig_data.edit_bones.new(name)
        e.head=start; e.tail=end; e.roll=0.0
    for name,(start,end,parent) in D.items():
        if parent: rig_data.edit_bones[name].parent=rig_data.edit_bones[parent]
    bpy.ops.object.mode_set(mode='OBJECT')
    rig.select_set(False)
    rig_data.display_type='STICK'
    return rig,D

def add_skin(obj,rig,bone_a,bone_b=None,blend=False):
    obj.parent=rig
    if blend and bone_b:
        a=obj.vertex_groups.new(name=bone_a)
        b=obj.vertex_groups.new(name=bone_b)
        N=len(obj.data.vertices)
        segments=max(1,(N//12)-1)
        for i in range(N):
            t=(i//12)/segments
            wa=max(.08,1-t); wb=max(.08,t)
            a.add([i],wa/(wa+wb),'REPLACE')
            b.add([i],wb/(wa+wb),'REPLACE')
    else:
        g=obj.vertex_groups.new(name=bone_a)
        g.add(list(range(len(obj.data.vertices))),1.0,'REPLACE')
    mod=obj.modifiers.new('Muscle Skinning','ARMATURE'); mod.object=rig
    return obj

def loft(name, path, radii, material, rig, bone_a, bone_b=None, sides=12, steps=24):
    # Cubic Bezier path with elliptical rings and variable anatomically motivated belly profile.
    path=[P(p) for p in path]
    assert len(path)==4 and len(radii)==4
    points=[]
    rads=[]
    for j in range(steps+1):
        t=j/steps; k=1-t
        cen=(k**3)*path[0]+3*k*k*t*path[1]+3*k*t*t*path[2]+(t**3)*path[3]
        r=k**3*radii[0]+3*k*k*t*radii[1]+3*k*t*t*radii[2]+t**3*radii[3]
        points.append(cen); rads.append(max(.002,r))
    verts=[];faces=[]
    for j,cen in enumerate(points):
        tangent=(points[min(steps,j+1)]-points[max(0,j-1)]).normalized()
        n=tangent.cross(V(0,1,0))
        if n.length<.01: n=tangent.cross(V(0,0,1))
        n.normalize(); b=tangent.cross(n).normalized()
        radius=rads[j]
        for i in range(sides):
            theta=2*math.pi*i/sides
            # Slight noncircular cross-section produces a believable tendinous bundle.
            pt=cen + n*math.cos(theta)*radius + b*math.sin(theta)*radius*.76
            verts.append(tuple(pt))
    for j in range(steps):
        for i in range(sides):
            a=j*sides+i; a1=j*sides+(i+1)%sides
            c=(j+1)*sides+i; c1=(j+1)*sides+(i+1)%sides
            faces.append((a,a1,c1,c))
    faces.append(tuple(reversed(tuple(range(sides)))))
    faces.append(tuple(steps*sides+i for i in range(sides)))
    mesh=bpy.data.meshes.new(name+'_mesh'); mesh.from_pydata(verts,[],faces); mesh.update()
    obj=bpy.data.objects.new(name,mesh); bpy.context.collection.objects.link(obj)
    obj.data.materials.append(material)
    for f in mesh.polygons: f.use_smooth=True
    # Ring-aware skinning, tapered along the muscle between the two bone parents.
    obj.parent=rig
    g1=obj.vertex_groups.new(name=bone_a)
    g2=obj.vertex_groups.new(name=bone_b) if bone_b else None
    if g2:
        for j in range(steps+1):
            t=j/steps
            wa=max(0.04, 1-t); wb=max(0.04,t); norm=wa+wb
            idx=list(range(j*sides,(j+1)*sides))
            g1.add(idx,wa/norm,'REPLACE');g2.add(idx,wb/norm,'REPLACE')
    else:
        g1.add(list(range(len(verts))),1.0,'REPLACE')
    mod=obj.modifiers.new('Armature deformation','ARMATURE');mod.object=rig
    return obj

def ellipsoid(name, center, scale, mat, rig, bone):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=28,ring_count=16,location=center)
    o=bpy.context.object;o.name=name
    o.scale=scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    o.data.materials.append(mat)
    for f in o.data.polygons:f.use_smooth=True
    g=o.vertex_groups.new(name=bone)
    g.add(list(range(len(o.data.vertices))),1.0,'REPLACE')
    o.parent=rig
    m=o.modifiers.new('Bone skinning','ARMATURE');m.object=rig
    return o

def create_body(rig,D):
    muscle=make_material('Ash gray tendon-covered musculature',(.25,.247,.255))
    muscle_light=make_material('Gray muscle mass',(.38,.37,.365))
    tendon=make_material('Dark sinew',(.112,.107,.12))
    bone=make_material('Pale skull and knuckles',(.46,.455,.43))
    # Core: both front and back separated muscle groups, pronounced backward shoulder hump.
    loft('bent thoracic erectors',[V(.14,0,2.28),V(.32,0,2.64),V(.40,0,3.30),V(-.58,0,3.01)], [.09,.40,.52,.16],muscle_light,rig,'pelvis','spine')
    loft('left scapular trapezius',[V(-.41,.10,2.93),V(-.16,.29,3.29),V(.34,.45,3.27),V(.43,.28,2.55)], [.045,.40,.34,.04],muscle,rig,'spine','upperarm_L')
    loft('right scapular trapezius',[V(-.41,-.10,2.93),V(-.16,-.29,3.29),V(.34,-.45,3.27),V(.43,-.28,2.55)], [.045,.40,.34,.04],muscle,rig,'spine','upperarm_R')
    loft('pectoral left',[V(-.41,.08,2.83),V(-.56,.27,2.74),V(-.46,.47,2.54),V(-.50,.36,2.48)],[.065,.21,.17,.045],muscle_light,rig,'spine','upperarm_L')
    loft('pectoral right',[V(-.41,-.08,2.83),V(-.56,-.27,2.74),V(-.46,-.47,2.54),V(-.50,-.36,2.48)],[.065,.21,.17,.045],muscle_light,rig,'spine','upperarm_R')
    loft('abdominal wall',[V(-.44,0,2.55),V(-.43,0,2.33),V(-.18,0,2.12),V(.0,0,2.04)], [.09,.21,.16,.07],tendon,rig,'spine','pelvis')
    loft('neck anterior tendon',[V(-.52,0,2.85),V(-.78,.07,2.72),V(-1.04,.06,2.57),V(-1.2,0,2.59)], [.15,.11,.065,.025],tendon,rig,'neck','head')
    ellipsoid('hairless skull',V(-1.32,0,2.59),(.235,.188,.25),bone,rig,'head')
    ellipsoid('prominent jaw',V(-1.37,0,2.45),(.18,.14,.085),muscle,rig,'head')
    for side,s in [('L',1),('R',-1)]:
        shoulder=V(-.51,s*.38,2.92)
        elbow=D['upperarm_'+side][1]
        wrist=D['forearm_'+side][1]
        hand=D['hand_'+side][1]
        hip=D['thigh_'+side][0]
        knee=D['thigh_'+side][1]
        ankle=D['shin_'+side][1]
        toes=D['foot_'+side][1]
        loft('deltoid_'+side,[shoulder,shoulder+V(.02,s*.08,-.10),shoulder+V(.13,s*.08,-.27),elbow],[.075,.22,.18,.035],muscle_light,rig,'spine','upperarm_'+side)
        loft('triceps_'+side,[shoulder,shoulder+V(.08,s*.06,-.21),elbow+V(-.08,0,.16),elbow],[.07,.18,.16,.04],muscle,rig,'upperarm_'+side)
        loft('forearm flexors_'+side,[elbow,elbow+V(-.25,0,-.06),wrist+V(.25,0,.08),wrist],[.05,.16,.12,.018],muscle_light,rig,'forearm_'+side)
        loft('forearm extensor tendon_'+side,[elbow+V(.01,-s*.08,0),elbow+V(-.22,-s*.08,-.05),wrist+V(.19,-s*.08,.08),wrist],[.02,.055,.035,.009],tendon,rig,'forearm_'+side)
        ellipsoid('claw knuckle_'+side,wrist,(.10,.11,.085),bone,rig,'hand_'+side)
        for fi in range(3):
            spread=(fi-1)*.09
            p0=wrist+V(0,spread,0)
            p1=hand+V(-.04,spread*1.35,0)
            direction=(p1-p0)
            loft('finger %s_%d'%(side,fi),[p0,p0+direction*.32,p0+direction*.67,p1],[.024,.033,.019,.004],bone,rig,'hand_'+side)
        loft('gluteus_'+side,[hip+V(-.10,s*.025,.17),hip+V(.06,s*.08,.06),knee+V(.02,s*.05,.22),knee],[.09,.24,.24,.04],muscle,rig,'pelvis','thigh_'+side)
        loft('quadriceps_'+side,[hip,hip+V(.08,s*.08,-.25),knee+V(.02,s*.02,.20),knee],[.06,.23,.18,.025],muscle_light,rig,'thigh_'+side)
        loft('hamstring_'+side,[hip+V(.16,0,0),hip+V(.20,s*.08,-.18),knee+V(.17,s*.08,.23),knee],[.045,.19,.15,.022],tendon,rig,'thigh_'+side)
        loft('calf belly_'+side,[knee,knee+V(.05,s*.07,-.10),ankle+V(-.035,0,.38),ankle],[.04,.15,.10,.015],muscle,rig,'shin_'+side)
        loft('Achilles tendon_'+side,[knee+V(.10,0,-.10),knee+V(.18,s*.05,-.33),ankle+V(.08,s*.03,.14),ankle],[.025,.04,.031,.012],tendon,rig,'shin_'+side)
        loft('elongated foot_'+side,[ankle,ankle+V(.04,0,-.08),toes+V(-.03,0,.04),toes],[.055,.09,.06,.008],bone,rig,'foot_'+side)
    return muscle

def make_action(rig,name,frames,samples):
    # Each clip uses articulated bones, not mesh warping, and returns to the initial pose.
    for pb in rig.pose.bones: pb.rotation_mode='XYZ'
    act=bpy.data.actions.new(name)
    rig.animation_data_create(); rig.animation_data.action=act
    for f, pose in samples:
        for pb in rig.pose.bones:
            rotation=pose.get(pb.name,(0,0,0))
            pb.rotation_euler=tuple(rotation)
            pb.keyframe_insert(data_path='rotation_euler',frame=f,group=pb.name)
    # Blender action NLA strips are exported as named glTF animation clips.
    rig.animation_data.action=None
    tr=rig.animation_data.nla_tracks.new();tr.name=name
    tr.strips.new(name,1,act)
    return act

def animate(rig):
    breath={'spine':(.035,0,.025),'neck':(-.02,0,-.015),'head':(.01,.02,0),
            'upperarm_L':(.024,0,.012),'upperarm_R':(-.022,0,-.011)}
    make_action(rig,'IDLE_BREATH',48,[(1,{}),(13,breath),(25,{}),(37,{k:tuple(-x*.8 for x in v) for k,v in breath.items()}),(49,{})])
    def walk(a):
        return {'thigh_L':(.31*a,0,.035),'thigh_R':(-.31*a,0,-.035),
                'shin_L':(-.22 if a>0 else .05,0,0),'shin_R':(-.22 if a<0 else .05,0,0),
                'upperarm_L':(-.2*a,0,0),'upperarm_R':(.2*a,0,0),
                'spine':(.035,0,.075*a),'neck':(.02,0,-.045*a)}
    make_action(rig,'STALK_LOOP',40,[(1,walk(0)),(11,walk(1)),(21,walk(0)),(31,walk(-1)),(41,walk(0))])
    attack={'spine':(-.23,0,-.15),'neck':(.18,0,.16),'head':(-.16,.09,0),
            'upperarm_L':(-1.04,.02,-.14),'forearm_L':(-.74,0,.18),
            'upperarm_R':(-.66,0,.22),'forearm_R':(-.35,0,-.20),'pelvis':(.08,0,.02)}
    recoil={'spine':(.12,0,.075),'upperarm_L':(.28,0,.1),'upperarm_R':(.2,0,-.1)}
    make_action(rig,'GRAB_ATTACK',42,[(1,{}),(12,recoil),(20,attack),(27,attack),(40,{}),(42,{})])

def setup_stage():
    world=bpy.context.scene.world
    if world: world.color=(.20,.20,.20)
    bpy.ops.object.light_add(type='AREA',location=(1.1,-3.6,5.0))
    key=bpy.context.object;key.name='Large soft key';key.data.energy=500;key.data.shape='DISK';key.data.size=4
    bpy.ops.object.light_add(type='AREA',location=(-2.1,2.7,4.3))
    rim=bpy.context.object;rim.name='Soft rim';rim.data.energy=380;rim.data.size=3
    bpy.ops.object.camera_add(location=(-5.6,-7.5,3.4))
    cam=bpy.context.object
    direction=V(-.28,0,1.85)-cam.location
    cam.rotation_euler=direction.to_track_quat('-Z','Y').to_euler()
    bpy.context.scene.camera=cam

def export_glb(path):
    bpy.ops.export_scene.gltf(filepath=str(path),export_format='GLB',export_animations=True,
        export_apply=False,export_cameras=False,export_lights=False)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--output',default='monster_anatomy.glb')
    ap.add_argument('--blend',default='')
    argv=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    args=ap.parse_args(argv)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    rig,_data=build_rig()
    create_body(rig,_data)
    setup_stage()
    animate(rig)
    for o in bpy.context.selected_objects:o.select_set(False)
    path=Path(args.output).resolve();path.parent.mkdir(parents=True,exist_ok=True)
    if args.blend:
        file=Path(args.blend).resolve();file.parent.mkdir(parents=True,exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(file))
    try:
        export_glb(path)
    except Exception as e:
        raise RuntimeError('GLB export failed; install and enable Blender glTF 2.0 exporter') from e
    print('Built GLB:',path)
    print('Muscle geometries:',sum(1 for o in bpy.data.objects if o.type=='MESH'))
    print('Actions:',[a.name for a in bpy.data.actions])

if __name__=='__main__': main()
