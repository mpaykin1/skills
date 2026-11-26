#!/usr/bin/env python3
"""Blender 4.5 CPU bridge: add UV atlas without touching monster anatomy.

Runs official xatlas-python in a separate Python process, then remaps its chart
UV coordinates onto the original Blender mesh LOOP UV layer. No topology edit:
original bones, skin weights, shapes, NLA tracks, names, materials and mesh
vertex indices stay intact. This is a new output scene, not a destructive edit.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile


def parse():
    p=argparse.ArgumentParser()
    p.add_argument('--blend',required=True)
    p.add_argument('--source-glb',required=True)
    p.add_argument('--output-blend',required=True)
    p.add_argument('--output-glb',required=True)
    p.add_argument('--python-bin',default=sys.executable,help='External CPU Python with xatlas==0.0.11 + numpy')
    p.add_argument('--uv-name',default='XATLAS_CPU')
    p.add_argument('--rig-name',default='MONSTER_RIG')
    p.add_argument('--allow-noop',action='store_true')
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    src=Path(a.blend).resolve();baseline=Path(a.source_glb).resolve()
    out=Path(a.output_blend).resolve();glb=Path(a.output_glb).resolve()
    for ip in [src,baseline]:
        if not ip.is_file():p.error('Missing input: '+str(ip))
    if src.suffix.lower()!='.blend' or baseline.suffix.lower()!='.glb':p.error('BLEND + GLB source required')
    if out.suffix.lower()!='.blend' or glb.suffix.lower()!='.glb':p.error('Outputs must be .blend and .glb')
    if len({src,baseline,out,glb})<4:p.error('Input/output paths must be distinct')
    if out.exists() or glb.exists():p.error('Outputs already exist; provide a new output directory')
    if not a.uv_name or len(a.uv_name)>50:p.error('Invalid UV layer name')
    return a


def glb_semantics(path):
    with open(path,'rb') as f:
        head=f.read(12)
        if len(head)!=12:raise ValueError('Invalid GLB')
        magic,version,size=struct.unpack('<4sII',head)
        if magic!=b'glTF' or version!=2 or size!=Path(path).stat().st_size:
            raise ValueError('Invalid GLB header/size')
        clen,typ=struct.unpack('<II',f.read(8))
        if typ!=0x4e4f534a or clen>50_000_000:raise ValueError('Invalid GLB JSON')
        doc=json.loads(f.read(clen))
    nodes=doc.get('nodes',[]);meshes=doc.get('meshes',[])
    def name(i):return nodes[i].get('name') or '@'+str(i)
    anim=[]
    for i,a in enumerate(doc.get('animations',[])):
        targets=[]
        for ch in a.get('channels',[]):
            t=ch.get('target',{})
            targets.append((name(t['node']) if 'node' in t else '@extension',t.get('path','')))
        anim.append((a.get('name') or '@'+str(i),tuple(sorted(targets))))
    skins=sorted(tuple(sorted(name(i) for i in s.get('joints',[]))) for s in doc.get('skins',[]))
    primitives=sorted(tuple(sorted(len(p.get('targets',[])) for p in m.get('primitives',[]))) for m in meshes)
    return {'animations':sorted(anim),'skins':skins,'morph_primitive_targets':primitives,
            'mesh_count':len(meshes),'material_count':len(doc.get('materials',[])),
            'morph_target_names':sorted(tuple(m.get('extras',{}).get('targetNames',[])) for m in meshes),
            'extensions_required':sorted(doc.get('extensionsRequired',[])),
            'doc':doc}


def geometry_fingerprint(ob):
    h=hashlib.sha256();me=ob.data
    for v in me.vertices:
        h.update(struct.pack('<3f',*v.co))
        for vg in v.groups:h.update(struct.pack('<If',vg.group,vg.weight))
    for p in me.polygons:
        h.update(struct.pack('<II',p.material_index,p.loop_total))
        for i in p.vertices:h.update(struct.pack('<I',i))
    if me.shape_keys:
        for kb in me.shape_keys.key_blocks:
            h.update(kb.name.encode('utf-8'))
            for k in kb.data:h.update(struct.pack('<3f',*k.co))
    for m in me.materials:h.update((m.name if m else '').encode('utf-8'))
    for vg in ob.vertex_groups:h.update(vg.name.encode('utf-8'))
    return h.digest()


def eligible(ob,rig):
    from blender_sculpt_bridge import is_monster_mesh
    if not is_monster_mesh(ob,rig):return False
    if ob.hide_render or ob.get('non_exportable_reference'):return False
    if ob.data.users!=1:return False
    if ob.data.uv_layers:return False   # NEVER rewrite a texture map, including lightmaps.
    if len(ob.data.vertices)<3 or len(ob.data.polygons)<2 or len(ob.data.vertices)>300_000:
        return False
    # With an image texture but no UV, a new UV set could change the appearance.
    for mat in ob.data.materials:
        if mat and mat.use_nodes and any(n.type=='TEX_IMAGE' for n in mat.node_tree.nodes):
            return False
    return True


def triangles_payload(ob):
    mesh=ob.data
    mesh.calc_loop_triangles()
    triangles=[]
    for tri in mesh.loop_triangles:
        tris=tuple(int(x) for x in tri.vertices)
        lps=tuple(int(x) for x in tri.loops)
        if len(set(tris))<3:raise ValueError('Degenerate face in '+ob.name)
        triangles.append({'v':tris,'l':lps})
    if len(triangles)<2:raise ValueError('Not enough faces')
    return {'format':'monster-xatlas-triangles-v1','name':ob.name,
            'vertices':[list(map(float,v.co)) for v in mesh.vertices],
            'triangles':triangles,'loop_count':len(mesh.loops)}


def main():
    import bpy
    a=parse()
    if tuple(bpy.app.version[:2])<(4,2):raise RuntimeError('Requires Blender 4.2+')
    src=Path(a.blend).resolve();out=Path(a.output_blend).resolve()
    dstglb=Path(a.output_glb).resolve()
    baseline=glb_semantics(Path(a.source_glb).resolve())
    # Real CPU native extension must be present; abort before writing any files.
    probe=subprocess.run([a.python_bin,'-c',
       "import xatlas,numpy,importlib.metadata as m;assert m.version('xatlas')=='0.0.11'"],
       capture_output=True,text=True,check=False,timeout=30)
    if probe.returncode:
        raise RuntimeError('Official xatlas==0.0.11 missing in external CPU Python. '
                           'Run scripts/install_xatlas_cpu.py --install. '
                           +probe.stderr[-300:])
    bpy.ops.wm.open_mainfile(filepath=str(src))
    rig=bpy.data.objects.get(a.rig_name)
    if not rig or rig.type!='ARMATURE':raise RuntimeError('Original MONSTER_RIG not found')
    from blender_sculpt_bridge import is_monster_mesh,save_selected_glb
    targets=[ob for ob in bpy.data.objects if is_monster_mesh(ob,rig)]
    if not targets:raise RuntimeError('No real monster meshes in original scene')
    before={ob.name:geometry_fingerprint(ob) for ob in targets}
    actions={x.name for x in bpy.data.actions}
    rig_bones=tuple(b.name for b in rig.data.bones)
    changes=[];skips=[]
    with tempfile.TemporaryDirectory(prefix='monster-xatlas-cpu-') as td:
        folder=Path(td)
        for ob in targets:
            if not eligible(ob,rig):
                skips.append(ob.name+': existing UV, textured, reference or unsafe topology')
                continue
            with (folder/'input.json').open('w',encoding='utf-8') as f:
                json.dump(triangles_payload(ob),f,separators=(',',':'))
            output=folder/'result.json'
            cmd=[a.python_bin,str(Path(__file__).with_name('xatlas_cpu_worker.py')),
                 '--input',folder/'input.json','--output',output]
            result=subprocess.run([str(c) for c in cmd],capture_output=True,text=True,timeout=900,check=False)
            if result.returncode:
                # Safe skip; never leave the scene half-edited due to atlas failure.
                skips.append(ob.name+': '+(result.stderr or result.stdout)[-350:].strip())
                continue
            data=json.loads(output.read_text(encoding='utf-8'))
            if data.get('name')!=ob.name or data.get('format')!='monster-xatlas-loop-uv-v1':
                raise RuntimeError('xatlas result metadata mismatch')
            coords=data['loop_uv']
            if len(coords)!=len(ob.data.loops) or len(data.get('loop_uv',[]))!=data['loop_count']:
                raise ValueError('Atlas loop count changed')
            if any(len(uv)!=2 or not all(math.isfinite(v) and -1e-3<=v<=1.001 for v in uv) for uv in coords):
                raise ValueError('Malformed xatlas UV coordinates')
            layer=ob.data.uv_layers.new(name=a.uv_name,do_init=False)
            for i,xy in enumerate(coords):layer.data[i].uv=xy
            if geometry_fingerprint(ob)!=before[ob.name]:
                raise RuntimeError('Original mesh/rig/morph geometry mutated for '+ob.name)
            changes.append(ob.name)
    if not changes and not a.allow_noop:
        raise RuntimeError('xatlas applied no UVs. Models may already have UVs or require manual mesh triangulation. '+str(skips[:4]))
    if {x.name for x in bpy.data.actions}!=actions or tuple(b.name for b in rig.data.bones)!=rig_bones:
        raise RuntimeError('Source animation or bones changed')
    for ob in targets:
        if geometry_fingerprint(ob)!=before[ob.name]:raise RuntimeError('Geometry changed: '+ob.name)
    out.parent.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out))
    dstglb.parent.mkdir(parents=True,exist_ok=True)
    # Uses the exact existing GLB export policy: NLA tracks for hero + morphs.
    save_selected_glb(dstglb,rig,targets)
    current=glb_semantics(dstglb)
    compare=('animations','skins','morph_primitive_targets','morph_target_names','mesh_count','material_count','extensions_required')
    mismatches=[key for key in compare if baseline[key]!=current[key]]
    if mismatches:
        dstglb.unlink(missing_ok=True)
        out.unlink(missing_ok=True)
        raise RuntimeError('xatlas GLB export would change protected asset structure: '+', '.join(mismatches))
    if changes and not any('TEXCOORD_0' in p.get('attributes',{}) for m in current['doc'].get('meshes',[]) for p in m.get('primitives',[])):
        dstglb.unlink(missing_ok=True)
        out.unlink(missing_ok=True)
        raise RuntimeError('Blender did not export the generated UVs to GLB')
    print(json.dumps({'uv_meshes':changes,'skipped':skips,'glb':str(dstglb)},ensure_ascii=False))

if __name__=='__main__':main()
