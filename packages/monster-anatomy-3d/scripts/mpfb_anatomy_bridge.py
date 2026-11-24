"""Blender 4.2+: connect MPFB's CC0 humanoid donor to the Monster Anatomy rig.

Requires *enabled* upstream MPFB 2 extension, plus input .blend containing
MONSTER_RIG and optionally Z_ANATOMY_ATTACHMENTS from z_anatomy_bridge.py.
Creates a real MPFB mesh+skinned game-engine armature and its own bone-parented
reference points. Preserves the original creature and its MyoGenerator guide
markers. No unreviewed retargeting, skin deformation, or physics is implied.

Run:
 blender --background --python scripts/mpfb_anatomy_bridge.py -- \\
    --blend build/monster/monster_with_anatomy_guides.blend \\
    --output-blend build/monster/monster_mpfb_anatomy.blend \\
    --output-json build/monster/mpfb_bone_correspondence.json \\
    --output-csv build/monster/mpfb_anchor_correspondence.csv
"""
from __future__ import annotations
import argparse
import csv
import importlib
import json
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

MPFB_BONE_MAP = {
    'root':'Root', 'pelvis':'pelvis', 'spine':'spine_02',
    'neck':'neck_01', 'head':'head',
    'upperarm_L':'upperarm_l', 'upperarm_R':'upperarm_r',
    'forearm_L':'lowerarm_l', 'forearm_R':'lowerarm_r',
    'hand_L':'hand_l', 'hand_R':'hand_r',
    'thigh_L':'thigh_l', 'thigh_R':'thigh_r',
    'shin_L':'calf_l', 'shin_R':'calf_r',
    'foot_L':'foot_l', 'foot_R':'foot_r',
}

MACRO_FIELDS = ('height', 'weight', 'muscle', 'proportions')

def dynamic_import(absolute_package_str, key):
    # Mirrors MPFB's public script_samples/01_create_a_basic_human.py import pattern.
    for name in tuple(sys.modules):
        if name.endswith(absolute_package_str):
            module = importlib.import_module(name)
            if not hasattr(module, key): raise AttributeError(name + ' missing ' + key)
            return getattr(module, key)
    raise RuntimeError(
        'MPFB 2 extension is not enabled in this Blender instance. '
        'Install/enable MPFB from vendor/MPFB2/src/mpfb or the official Blender Extensions listing. '
        'Re-run with --skip-mpfb to retain the two-tool pipeline.'
    )

def move_to_collection(obj, destination):
    for c in tuple(obj.users_collection): c.objects.unlink(obj)
    destination.objects.link(obj)

def bone_position(rig, name, fraction):
    bone=rig.data.bones.get(name)
    if bone is None: raise ValueError(f'Missing rig bone {rig.name}/{name}')
    fraction=max(0.,min(1.,fraction))
    return rig.matrix_world @ bone.head_local.lerp(bone.tail_local, fraction)

def segment_fraction(rig, bone, position):
    data=rig.data.bones[bone]
    p=rig.matrix_world.inverted_safe() @ position
    axis=data.tail_local-data.head_local
    return max(0.,min(1.,float((p-data.head_local).dot(axis)/max(axis.length_squared,1.e-8))))

def create_marker(collection, rig, bone, fraction, name, role, source_za):
    p=bone_position(rig, bone, fraction)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=12,ring_count=8,radius=.027,location=p)
    obj=bpy.context.object
    obj.name=name
    move_to_collection(obj,collection)
    obj.parent=rig
    obj.parent_type='BONE'
    obj.parent_bone=bone
    obj.matrix_world=Matrix.Translation(p)
    obj['mpfb_donor_reference']=True
    obj['role']=role
    obj['source_za_marker']=source_za
    obj['non_exportable_reference']=True
    return obj

def find_pairs(monster_rig, donor_rig, ref_collection):
    out=[]
    for key in sorted(bpy.data.objects.keys()):
        if not key.startswith('ZA_ORIGIN_'): continue
        tag=key[len('ZA_ORIGIN_'):]
        origin=bpy.data.objects.get('ZA_ORIGIN_'+tag)
        insertion=bpy.data.objects.get('ZA_INSERTION_'+tag)
        if not origin or not insertion: continue
        a=origin.get('attachment_bone')
        b=insertion.get('attachment_bone')
        mapped_a=MPFB_BONE_MAP.get(a)
        mapped_b=MPFB_BONE_MAP.get(b)
        if not mapped_a or not mapped_b: continue
        if donor_rig.data.bones.get(mapped_a) is None or donor_rig.data.bones.get(mapped_b) is None:
            continue
        # Re-use the Z-Anatomy guide's normalized origin/insertion positions.
        # The transfer is a normalized bone-position correspondence, NOT a
        # scientific measurement of tendon attachment sites.
        frac0=segment_fraction(monster_rig,a,origin.matrix_world.translation)
        frac1=segment_fraction(monster_rig,b,insertion.matrix_world.translation)
        p0=create_marker(ref_collection,donor_rig,mapped_a,frac0,'MPFB_ORIGIN_'+tag,'ORIGIN',origin.name)
        p1=create_marker(ref_collection,donor_rig,mapped_b,frac1,'MPFB_INSERTION_'+tag,'INSERTION',insertion.name)
        out.append({
            'muscle':tag,
            'monster_origin':origin.name,'monster_insertion':insertion.name,
            'mpfb_origin':p0.name,'mpfb_insertion':p1.name,
            'monster_origin_bone':a,'monster_insertion_bone':b,
            'mpfb_origin_bone':mapped_a,'mpfb_insertion_bone':mapped_b,
            'origin_bone_fraction':round(frac0,5),'insertion_bone_fraction':round(frac1,5),
            'status':'art-directed reference only; confirm anatomy before MyoGeneratorRemix creation',
        })
    return out

def create_donor(options):
    HumanService=dynamic_import('mpfb.services.humanservice','HumanService')
    TargetService=dynamic_import('mpfb.services.targetservice','TargetService')
    HumanObjectProperties=dynamic_import('mpfb.entities.objectproperties','HumanObjectProperties')
    mesh=HumanService.create_human()
    if mesh is None or mesh.type!='MESH': raise RuntimeError('MPFB failed to create base mesh')
    for field in MACRO_FIELDS:
        HumanObjectProperties.set_value(field, float(getattr(options,field)), entity_reference=mesh)
    TargetService.reapply_macro_details(mesh)
    rig=HumanService.add_builtin_rig(mesh,'game_engine')
    if rig is None or rig.type!='ARMATURE': raise RuntimeError('MPFB game_engine rig creation failed')
    mesh.name='MPFB_REFERENCE_MESH'
    rig.name='MPFB_REFERENCE_RIG'
    collection=bpy.data.collections.new('MPFB_CC0_REFERENCE_BODY')
    bpy.context.scene.collection.children.link(collection)
    move_to_collection(mesh,collection)
    move_to_collection(rig,collection)
    rig.location.x += float(options.reference_offset_x)
    rig['reference_only']=True
    rig['source']='MPFB2 / MakeHumanCommunity CC0 assets'
    mesh['reference_only']=True
    mesh['source']='MPFB2 / MakeHumanCommunity CC0 assets'
    for obj in (mesh,rig): obj.hide_render=True
    return rig,mesh

def collect_lengths(monster_rig, mpfb_rig):
    correspondence=[]
    for a,b in MPFB_BONE_MAP.items():
        ma=monster_rig.data.bones.get(a)
        mb=mpfb_rig.data.bones.get(b)
        if ma is None or mb is None: continue
        mlen=float((monster_rig.matrix_world.to_3x3() @ (ma.tail_local-ma.head_local)).length)
        dlen=float((mpfb_rig.matrix_world.to_3x3() @ (mb.tail_local-mb.head_local)).length)
        correspondence.append({'monster_bone':a,'mpfb_bone':b,'monster_length':round(mlen,5),
                               'mpfb_length':round(dlen,5),
                               'monster_to_reference_ratio':round(mlen/max(dlen,1.e-7),5)})
    return correspondence

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--blend',required=True)
    p.add_argument('--output-blend',required=True)
    p.add_argument('--output-json',required=True)
    p.add_argument('--output-csv',required=True)
    p.add_argument('--height',type=float,default=.83)
    p.add_argument('--weight',type=float,default=.08)
    p.add_argument('--muscle',type=float,default=.62)
    p.add_argument('--proportions',type=float,default=.48)
    p.add_argument('--reference-offset-x',type=float,default=3.8)
    options=p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    for field in MACRO_FIELDS:
        if not 0<=getattr(options,field)<=1: p.error(f'{field} must be 0..1')
    bpy.ops.wm.open_mainfile(filepath=str(Path(options.blend).expanduser().resolve()))
    monster=bpy.data.objects.get('MONSTER_RIG')
    if monster is None or monster.type!='ARMATURE': raise ValueError('Monster armature MONSTER_RIG is missing')
    if bpy.data.objects.get('MPFB_REFERENCE_RIG'):
        raise RuntimeError('This scene already contains an MPFB donor; use a clean anatomy-guided input')
    donor,mesh=create_donor(options)
    references=bpy.data.collections.new('MPFB_TO_MYOGENERATOR_GUIDES')
    bpy.context.scene.collection.children.link(references)
    pairs=find_pairs(monster,donor,references)
    bones=collect_lengths(monster,donor)
    if len(bones)<15: raise RuntimeError(f'Incompatible MPFB rig: only {len(bones)} of 17 matched')
    if bpy.data.objects.get('ZA_ORIGIN_trapezius_L') and len(pairs)<25:
        raise RuntimeError(f'Z-Anatomy markers found but only {len(pairs)} matched')
    out={
        'sources':{'MPFB':'makehumancommunity/mpfb2 @ 9de0707fdc88438d7c53a1a2ac7937d9221e2431',
                   'Z-Anatomy':'bone-parented monster attachment guides, if present',
                   'MyoGeneratorRemix':'editable origin/insertion surface pairs; muscle generation is separate'},
        'donor_mesh':mesh.name,'donor_rig':donor.name,
        'bone_correspondences':bones,'muscle_anchor_correspondences':len(pairs),
        'macro_parameters':{f:getattr(options,f) for f in MACRO_FIELDS},
        'warning':'Donor is a reference, not automatically reshaped into the horror creature. Muscle sites are heuristic.',
    }
    target=Path(options.output_json).expanduser().resolve();target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding='utf8')
    csv_path=Path(options.output_csv).expanduser().resolve();csv_path.parent.mkdir(parents=True,exist_ok=True)
    with csv_path.open('w',newline='',encoding='utf8') as csv_file:
        cols=['muscle','monster_origin','monster_insertion','mpfb_origin','mpfb_insertion',
              'monster_origin_bone','monster_insertion_bone','mpfb_origin_bone','mpfb_insertion_bone',
              'origin_bone_fraction','insertion_bone_fraction','status']
        writer=csv.DictWriter(csv_file,fieldnames=cols)
        writer.writeheader();writer.writerows(pairs)
    dest=Path(options.output_blend).expanduser().resolve();dest.parent.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(dest))
    print(f'MPFB donor saved to {dest}; {len(bones)} skeleton correspondences and {len(pairs)} muscle anchor pairs')
    print('The previously exported monster_base.glb does not include the MPFB reference human.')

if __name__=='__main__': main()
