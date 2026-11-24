"""Transfer an artist-confirmed MyoGeneratorRemix muscle mesh onto the monster rig.

Requires paired ZA_ORIGIN_<tag> / ZA_INSERTION_<tag> meshes (their positions
come from artist-adjustable Z-Anatomy terminology guides, not ground truth).
Only attaches actual existing MyoGeneratorRemix meshes; never invents shapes.
"""
from __future__ import annotations
from mathutils import Vector


def marker_pair(tag, bpy):
    return (bpy.data.objects.get('ZA_ORIGIN_'+tag),
            bpy.data.objects.get('ZA_INSERTION_'+tag))


def attach_myo_mesh(obj, rig, origin, insertion):
    if obj.type!='MESH':raise ValueError('Expected existing muscle mesh')
    a=origin.get('attachment_bone');b=insertion.get('attachment_bone')
    if not a or not b or a not in rig.data.bones or b not in rig.data.bones:
        raise ValueError('Origin and insertion must reference existing bones')
    start=origin.matrix_world.translation.copy()
    finish=insertion.matrix_world.translation.copy()
    line=finish-start
    if line.length<1e-5:raise ValueError('Muscle attachment anchors are coincident')
    if obj.parent and obj.parent!=rig:raise RuntimeError('Muscle already has a different parent: '+obj.name)
    # Disallow silently replacing already-painted artisanal muscle weights.
    if obj.vertex_groups or any(mod.type=='ARMATURE' for mod in obj.modifiers):
        raise RuntimeError('Existing rig weights/modifiers on '+obj.name+' must be reviewed manually')
    vg_a=obj.vertex_groups.new(name=a)
    vg_b=obj.vertex_groups.new(name=b) if a!=b else None
    for v in obj.data.vertices:
        world=obj.matrix_world@v.co
        t=max(.0,min(1.,float((world-start).dot(line)/line.length_squared)))
        if vg_b is None:vg_a.add([v.index],1.,'REPLACE')
        else:
            vg_a.add([v.index],max(.02,1-t),'REPLACE')
            vg_b.add([v.index],max(.02,t),'REPLACE')
    world_mat=obj.matrix_world.copy()
    obj.parent=rig
    obj.matrix_world=world_mat
    modifier=obj.modifiers.new('Myo muscle to Monster Rig','ARMATURE')
    modifier.object=rig
    obj['monster_muscle']=True
    obj['source_myo']='MyoGeneratorRemix artist-created mesh'
    obj['origin_marker']=origin.name;obj['insertion_marker']=insertion.name
    obj['flex_bone']=b
    obj['bone_weighting']='linear origin/insertion; manually paint for anatomical realism'
    return obj


def auto_attach_myo(bpy,rig):
    attached=[]
    for obj in list(bpy.data.objects):
        if obj.type!='MESH' or not obj.name.endswith('_muscle') or obj.parent==rig:
            continue
        tag=str(obj.get('monster_muscle_tag') or obj.name[:-len('_muscle')])
        origin,insertion=marker_pair(tag,bpy)
        if origin is None or insertion is None:continue
        attach_myo_mesh(obj,rig,origin,insertion)
        attached.append(obj.name)
    return attached
