"""Z-Anatomy -> Monster Anatomy 3D -> MyoGeneratorRemix anchor bridge.

Blender 4.2+ background script. Reads external Z-Anatomy Blender template
for a *name* inventory, does not redistribute or export atlas meshes.
Creates physical reference mesh anchor pairs and a CSV to guide the
MyoGeneratorRemix origin/insertion reconstruction. No automated physiological
fibre simulation is claimed.

Usage:
 blender -b --python scripts/z_anatomy_bridge.py -- \
   --blend monster.blend --z-zip vendor/Z-Anatomy/Z-Anatomy.zip \
   --output-blend monster_anatomy_guides.blend --output-csv muscle_anchors.csv
"""
from __future__ import annotations
import argparse, csv, json, re, sys, tempfile, zipfile
from pathlib import Path
import bpy
from mathutils import Vector, Matrix

# Anatomical muscle reference names. Rig bones are custom to the monster and
# deliberately do not pretend to be human anatomical models.
# (name, origin bone, origin rest position, insertion bone, insertion rest position,
#  sides, reference alias)
MUSCLE_PLAN = [
    ('trapezius', 'spine', .77, 'upperarm_{s}', .06, 'bilateral', 'trapezius'),
    ('deltoid', 'spine', .91, 'upperarm_{s}', .24, 'bilateral', 'deltoid'),
    ('pectoralis_major', 'spine', .72, 'upperarm_{s}', .28, 'bilateral', 'pectoralis major'),
    ('latissimus_dorsi', 'spine', .43, 'upperarm_{s}', .45, 'bilateral', 'latissimus dorsi'),
    ('biceps_brachii', 'upperarm_{s}', .07, 'forearm_{s}', .18, 'bilateral', 'biceps brachii'),
    ('brachialis', 'upperarm_{s}', .34, 'forearm_{s}', .11, 'bilateral', 'brachialis'),
    ('triceps_brachii', 'upperarm_{s}', .11, 'forearm_{s}', .09, 'bilateral', 'triceps brachii'),
    ('forearm_flexors', 'forearm_{s}', .15, 'hand_{s}', .04, 'bilateral', 'flexor'),
    ('gluteus_maximus', 'pelvis', .26, 'thigh_{s}', .24, 'bilateral', 'gluteus maximus'),
    ('rectus_femoris', 'thigh_{s}', .10, 'shin_{s}', .06, 'bilateral', 'rectus femoris'),
    ('biceps_femoris', 'thigh_{s}', .11, 'shin_{s}', .11, 'bilateral', 'biceps femoris'),
    ('gastrocnemius', 'thigh_{s}', .91, 'shin_{s}', .68, 'bilateral', 'gastrocnemius'),
    ('soleus', 'shin_{s}', .18, 'foot_{s}', .09, 'bilateral', 'soleus'),
    ('tibialis_anterior', 'shin_{s}', .17, 'foot_{s}', .15, 'bilateral', 'tibialis anterior'),
    ('sternocleidomastoid', 'neck', .14, 'head', .22, 'midline', 'sternocleidomastoid'),
    ('rectus_abdominis', 'spine', .17, 'pelvis', .24, 'midline', 'rectus abdominis'),
]

def find_startup_blend(archive: Path, output_dir: Path):
    """Extract one .blend from the Z-Anatomy application template, never exec code."""
    if not archive.is_file():
        raise FileNotFoundError('Z-Anatomy.zip missing; run download_z_anatomy.py first')
    with zipfile.ZipFile(archive) as z:
        candidates=[i for i in z.infolist() if i.filename.lower().endswith('.blend') and not i.is_dir()]
        if not candidates:
            raise ValueError('Atlas archive has no .blend file. Install template in Blender and pass --atlas-blend instead.')
        candidates.sort(key=lambda i:(not i.filename.lower().endswith('startup.blend'), len(i.filename)))
        selected=candidates[0]
        if selected.file_size > 1024*1024*1024:
            raise ValueError('Too large for safe reference indexing')
        output_dir.mkdir(parents=True,exist_ok=True)
        to=output_dir/'z_anatomy_atlas_index.blend'
        with z.open(selected) as inp, to.open('wb') as out:
            import shutil
            shutil.copyfileobj(inp,out)
    return to

def atlas_inventory(atlas_blend: Path):
    """Inspect Blender library names without appending any licensed model data."""
    if atlas_blend is None: return []
    if not atlas_blend.is_file():
        raise FileNotFoundError(str(atlas_blend))
    with bpy.data.libraries.load(str(atlas_blend), link=False) as (source, dest):
        names=list(source.objects) + list(source.meshes)
    return sorted(set(names))

def matches_for(alias, inventory):
    needle=re.sub(r'[^a-z0-9]+','',alias.lower())
    matches=[]
    for name in inventory:
        compact=re.sub(r'[^a-z0-9]+','',name.lower())
        if needle in compact:
            matches.append(name)
    return matches[:8]

def point_on_rest_bone(rig, bone_name, fraction):
    b=rig.data.bones.get(bone_name)
    if b is None: raise ValueError('Required rig bone missing: '+bone_name)
    return rig.matrix_world @ b.head_local.lerp(b.tail_local, fraction)

def make_marker(collection, rig, name, bone_name, pos, color):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=12,ring_count=8,radius=.035,location=pos)
    obj=bpy.context.object
    obj.name=name
    for other in list(obj.users_collection): other.objects.unlink(obj)
    collection.objects.link(obj)
    # Parent to bone yet preserve the original world rest-space location.
    obj.matrix_world=Matrix.Translation(pos)
    obj.parent=rig
    obj.parent_type='BONE'
    obj.parent_bone=bone_name
    obj.matrix_world=Matrix.Translation(pos)
    material=bpy.data.materials.get('Z-ANATOMY '+color)
    if material is None:
        material=bpy.data.materials.new('Z-ANATOMY '+color)
        material.diffuse_color= (0.13,0.63,0.96,1) if color=='ORIGIN' else (1,.40,.18,1)
    obj.data.materials.append(material)
    obj['reference_source']='Z-Anatomy anatomical muscle terminology, not licensed geometry'
    obj['attachment_bone']=bone_name
    obj['role']=color
    return obj

def prepare_guides(rig, atlas_names, csv_path):
    old=bpy.data.collections.get('Z_ANATOMY_ATTACHMENTS')
    if old: bpy.data.collections.remove(old,do_unlink=True)
    collection=bpy.data.collections.new('Z_ANATOMY_ATTACHMENTS')
    bpy.context.scene.collection.children.link(collection)
    rows=[]
    for muscle,ob,ofrac,ib,ifrac,mode,alias in MUSCLE_PLAN:
        sides=('L','R') if mode=='bilateral' else ('',)
        for side in sides:
            b0=ob.format(s=side);b1=ib.format(s=side)
            tag=muscle+('_'+side if side else '')
            if rig.data.bones.get(b0) is None or rig.data.bones.get(b1) is None:
                continue
            pos0=point_on_rest_bone(rig,b0,ofrac)
            pos1=point_on_rest_bone(rig,b1,ifrac)
            origin=make_marker(collection,rig,'ZA_ORIGIN_'+tag,b0,pos0,'ORIGIN')
            insertion=make_marker(collection,rig,'ZA_INSERTION_'+tag,b1,pos1,'INSERTION')
            found=matches_for(alias,atlas_names)
            rows.append({'muscle':tag,'anatomical_name':alias,
                'origin_bone':b0,'insertion_bone':b1,
                'origin_mesh':origin.name,'insertion_mesh':insertion.name,
                'origin_xyz':','.join(f'{v:.5f}' for v in pos0),
                'insertion_xyz':','.join(f'{v:.5f}' for v in pos1),
                'atlas_name_matches':'; '.join(found),
                'status':'REVIEW — hypothetical attachment; sculpt/confirm before generating muscle'})
    csv_path.parent.mkdir(parents=True,exist_ok=True)
    with csv_path.open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]) if rows else ['muscle'])
        writer.writeheader();writer.writerows(rows)
    return rows

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--blend',required=True,help='Base monster .blend created by build_monster.py')
    parser.add_argument('--z-zip',default='',help='Optional downloaded Z-Anatomy.zip')
    parser.add_argument('--atlas-blend',default='',help='Optional installed Z-Anatomy template startup.blend')
    parser.add_argument('--output-blend',default='monster_with_anatomy_guides.blend')
    parser.add_argument('--output-csv',default='muscle_anchors.csv')
    parser.add_argument('--output-index',default='z_anatomy_matches.json')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    bpy.ops.wm.open_mainfile(filepath=str(Path(args.blend).resolve()))
    bpy.context.scene.frame_set(1)
    rig=bpy.data.objects.get('MONSTER_RIG')
    if rig is None or rig.type!='ARMATURE':raise ValueError('MONSTER_RIG armature missing from --blend')
    inventory=[]
    if args.atlas_blend:
        inventory=atlas_inventory(Path(args.atlas_blend).resolve())
    elif args.z_zip:
        with tempfile.TemporaryDirectory(prefix='z_anatomy_') as temp:
            inventory=atlas_inventory(find_startup_blend(Path(args.z_zip), Path(temp)))
    rows=prepare_guides(rig,inventory,Path(args.output_csv).resolve())
    # No atlas geometry is appended or exported. Names are metadata only.
    index={'atlas_objects_inspected':len(inventory),'found_muscle_aliases':sum(bool(r['atlas_name_matches']) for r in rows),
           'muscle_pairs':len(rows),'model_source':'Z-Anatomy/Models-of-human-anatomy',
           'notice':'Atlas references are not included in this generated scene; attachment sites are conceptual guides.'}
    Path(args.output_index).resolve().write_text(json.dumps(index,indent=2),encoding='utf8')
    target=Path(args.output_blend).resolve();target.parent.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(target))
    print('Saved',target,'with',len(rows),'muscle reference pairs, matched atlas name count',index['found_muscle_aliases'])

if __name__=='__main__':main()
