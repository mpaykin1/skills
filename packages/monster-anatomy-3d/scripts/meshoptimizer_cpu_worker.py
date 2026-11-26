#!/usr/bin/env python3
"""Official gltfpack CPU postpass with non-destructive GLB identity checks.

Safe for a production character: if material, skin, morph, clip or UV contracts
change, reject output. No silent LOD/simplification, texture conversion or bake.
Requires official gltfpack v1.3, installed separately.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile

from gltf_transform_worker import read_glb

SUPPORTED_EXTENSIONS={
'KHR_lights_punctual','KHR_materials_anisotropy','KHR_materials_clearcoat',
'KHR_materials_diffuse_transmission','KHR_materials_dispersion',
'KHR_materials_emissive_strength','KHR_materials_ior','KHR_materials_iridescence',
'KHR_materials_pbrSpecularGlossiness','KHR_materials_sheen','KHR_materials_specular',
'KHR_materials_transmission','KHR_materials_unlit','KHR_materials_variants',
'KHR_materials_volume','KHR_mesh_quantization','KHR_texture_basisu',
'KHR_texture_transform','EXT_meshopt_compression','EXT_texture_webp',
'EXT_mesh_gpu_instancing',
}
MESHOPT_EXT={'EXT_meshopt_compression'}


def glb_binary(path:Path):
    with path.open('rb') as f:
        f.seek(12)
        n,kind=struct.unpack('<II',f.read(8))
        if kind!=0x4e4f534a:raise ValueError('Missing GLB JSON')
        f.seek(n,1)
        header=f.read(8)
        if len(header)!=8:return b''
        size,kind=struct.unpack('<II',header)
        if kind!=0x004e4942:raise ValueError('Invalid GLB binary chunk')
        payload=f.read(size)
        if len(payload)!=size:raise ValueError('Truncated GLB binary data')
        return payload


def fingerprint(doc:dict, bin_data:bytes)->dict:
    nodes=doc.get('nodes',[]); meshes=doc.get('meshes',[]); mats=doc.get('materials',[])
    accessors=doc.get('accessors',[]); buffers=doc.get('buffers',[])
    if len(buffers)>1 or any('uri' in b for b in buffers):
        raise ValueError('Standalone GLB must not load external buffers')
    if any(img.get('uri','').startswith(('http:','https:','/')) or ('uri' in img and not img['uri'].startswith('data:')) for img in doc.get('images',[])):
        raise ValueError('External image paths are forbidden for standalone game GLB')
    def label(i):
        if not isinstance(i,int) or i<0 or i>=len(nodes):raise ValueError('Invalid node index')
        return nodes[i].get('name') or f'@unnamed-{i}'
    def accessory(i):
        if not isinstance(i,int) or i<0 or i>=len(accessors):raise ValueError('Invalid accessor')
        x=accessors[i];return (x.get('type'),x.get('componentType'),bool(x.get('normalized',False)))
    def image_data(im):
        if 'bufferView' in im:
            bv=doc.get('bufferViews',[])[im['bufferView']]
            off=bv.get('byteOffset',0);end=off+bv['byteLength']
            if off<0 or end>len(bin_data):raise ValueError('Image bufferView out of bounds')
            binary=bin_data[off:end]
        elif 'uri' in im and im['uri'].startswith('data:'):
            import base64
            binary=base64.b64decode(im['uri'].split(',',1)[1],validate=True)
        else:raise ValueError('Image lacks self-contained source')
        return (im.get('mimeType'),hashlib.sha256(binary).hexdigest())
    image_info=[image_data(im) for im in doc.get('images',[])]
    textures=doc.get('textures',[])
    def texture_label(idx):
        tx=textures[idx]
        source=tx.get('source',tx.get('extensions',{}).get('EXT_texture_webp',{}).get('source',-1))
        if source<0 or source>=len(image_info):raise ValueError('Texture source invalid')
        sampler=doc.get('samplers',[])[tx['sampler']] if 'sampler' in tx else {}
        return (image_info[source],tuple(sorted(sampler.items())))
    def named_mat(i):
        if i is None:return None
        if i<0 or i>=len(mats):raise ValueError('Material index out of range')
        m=mats[i]
        name=m.get('name') or f'@material-{i}'
        # Fingerprint visuals, including PBR factor values, alpha, texture slots and extension keys.
        slots=[]
        def walk(value,path=''):
            if isinstance(value,dict):
                if path.endswith('Texture') and 'index' in value:
                    slots.append((path,texture_label(value['index']),tuple(sorted((k,json.dumps(v,sort_keys=True)) for k,v in value.items() if k!='index'))))
                else:
                    for k,v in value.items():walk(v,path+'.'+k if path else k)
        walk(m)
        pbr=m.get('pbrMetallicRoughness',{})
        factors=(tuple(pbr.get('baseColorFactor',[1,1,1,1])),pbr.get('metallicFactor',1),pbr.get('roughnessFactor',1),
                 tuple(m.get('emissiveFactor',[0,0,0])),m.get('alphaMode','OPAQUE'),m.get('alphaCutoff',.5),
                 bool(m.get('doubleSided',False)),tuple(sorted(m.get('extensions',{}))))
        return (name,factors,tuple(sorted(slots,key=str)))
    skins=[]
    for s in doc.get('skins',[]):
        names=[label(j) for j in s.get('joints',[])]
        if len(set(names))!=len(names):raise ValueError('Duplicate/ambiguous bone names')
        skins.append((tuple(names),label(s['skeleton']) if 'skeleton' in s else None,
                      accessory(s['inverseBindMatrices']) if 'inverseBindMatrices' in s else None))
    parents={}
    for i,n in enumerate(nodes):
        for ch in n.get('children',[]):
            if label(ch) in parents:raise ValueError('Node has ambiguous parents')
            parents[label(ch)]=label(i)
    hierarchy=sorted((label(i),parents.get(label(i)),tuple((k,tuple(n[k])) for k in ('translation','rotation','scale','matrix') if k in n)) for i,n in enumerate(nodes))
    links=[]
    for i,n in enumerate(nodes):
        if 'mesh' not in n:continue
        mesh=meshes[n['mesh']]
        parts=[]
        for p in mesh.get('primitives',[]):
            attrs=p.get('attributes',{})
            unsupported=[k for k in attrs if k.startswith('_') and k not in ('_ID','_BATCHID') and not k.startswith('_FEATURE_ID_')]
            if unsupported:raise ValueError('Unsupported custom vertex attributes: '+str(unsupported))
            targets=p.get('targets',[])
            parts.append((named_mat(p.get('material')),p.get('mode',4),
                          tuple(sorted(attrs.keys())),
                          tuple(tuple(sorted(t.keys())) for t in targets),
                          tuple((k,accessory(v)) for k,v in sorted(attrs.items()))))
        links.append((label(i),skins[n['skin']] if 'skin' in n else None,
                      tuple(parts),tuple(mesh.get('weights',[])),
                      tuple(mesh.get('extras',{}).get('targetNames',[]))))
    anim=[]
    for idx,a in enumerate(doc.get('animations',[])):
        channels=[]
        for c in a.get('channels',[]):
            sampler=a.get('samplers',[])[c['sampler']]
            target=c.get('target',{})
            channels.append((label(target['node']) if 'node' in target else '@pointer',
                             target.get('path'),sampler.get('interpolation','LINEAR'),
                             accessory(sampler['input']),accessory(sampler['output'])))
        anim.append((a.get('name') or f'@animation-{idx}',tuple(sorted(channels,key=str))))
    if len({x[0] for x in anim})!=len(anim):raise ValueError('Duplicate animation names')
    extensions=set(doc.get('extensionsUsed',[]))|set(doc.get('extensionsRequired',[]))
    if extensions-SUPPORTED_EXTENSIONS:raise ValueError('Unsupported glTF extension: '+str(sorted(extensions-SUPPORTED_EXTENSIONS)))
    return dict(skins=sorted(skins,key=str),hierarchy=hierarchy,meshes=sorted(links,key=str),
                animations=sorted(anim,key=str),images=sorted(image_info),
                materials=sorted((named_mat(i) for i in range(len(mats))),key=str),
                scenes=len(doc.get('scenes',[])),scene_roots=sorted(tuple(label(x) for x in s.get('nodes',[])) for s in doc.get('scenes',[])))


def find_exe(explicit):
    installed=Path(__file__).resolve().parent.parent/'vendor'/'gltfpack-v1.3'/('gltfpack.exe' if os.name=='nt' else 'gltfpack')
    candidate=explicit or os.environ.get('GLTFPACK_BIN') or (str(installed) if installed.is_file() else '') or shutil.which('gltfpack')
    if not candidate:raise FileNotFoundError('Official gltfpack missing: python scripts/install_meshoptimizer_cpu.py --dest vendor/gltfpack-v1.3')
    if os.path.sep in candidate or candidate.startswith('.'):
        path=Path(candidate).expanduser().resolve()
        if not path.is_file():raise FileNotFoundError('gltfpack not found: '+str(path))
        return str(path)
    match=shutil.which(candidate)
    if not match:raise FileNotFoundError('gltfpack not on PATH: '+candidate)
    return match


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--mode',choices=('safe','compressed'),default='safe')
    p.add_argument('--gltfpack-bin',default='')
    p.add_argument('--timeout',type=int,default=600)
    p.add_argument('--validate-khronos',action='store_true',help='Require official Khronos glTF Validator before/after compression')
    p.add_argument('--validator-package',default='')
    p.add_argument('--validator-node',default='')
    a=p.parse_args(argv)
    source=a.input.expanduser().resolve();output=a.output.expanduser().resolve()
    if not source.is_file() or source.suffix.lower()!='.glb':p.error('Input .glb missing')
    if source==output or output.suffix.lower()!='.glb':p.error('Specify a distinct output .glb')
    if output.exists():p.error('Output already exists; use a new path, original never replaced')
    if not 10<=a.timeout<=7200:p.error('Timeout must be 10..7200 seconds')
    try:
        original=read_glb(source)
        if 'EXT_meshopt_compression' in (set(original.get('extensionsUsed',[]))|set(original.get('extensionsRequired',[]))):
            raise ValueError('Already meshopt-compressed GLB must not be passed to gltfpack; use glTF-Transform safe mode before this stage')
        before=fingerprint(original,glb_binary(source))
        def validate(path):
            cmd=[sys.executable,str(Path(__file__).with_name('gltf_validator_worker.py')),'--input',str(path)]
            if a.validator_package:cmd+=['--package-dir',a.validator_package]
            if a.validator_node:cmd+=['--node',a.validator_node]
            done=subprocess.run(cmd,text=True,capture_output=True,check=False,timeout=min(a.timeout,300))
            if done.returncode:raise RuntimeError('Khronos Validator rejected GLB: '+(done.stderr or done.stdout)[-1100:])
        if a.validate_khronos:validate(source)
        exe=find_exe(a.gltfpack_bin)
        with tempfile.TemporaryDirectory(prefix='meshoptimizer-',dir=str(output.parent) if output.parent.is_dir() else None) as tmp:
            candidate=Path(tmp)/'candidate.glb'
            cmd=[exe,'-i',str(source),'-o',str(candidate),'-kn','-km','-ke','-noq']
            if a.mode=='compressed':cmd.append('-c')
            done=subprocess.run(cmd,text=True,capture_output=True,check=False,timeout=a.timeout)
            if done.returncode:raise RuntimeError('Official gltfpack failed: '+(done.stderr or done.stdout)[-1100:])
            if not candidate.is_file() or candidate.stat().st_size<28:raise RuntimeError('gltfpack did not produce a valid GLB')
            final=read_glb(candidate)
            after=fingerprint(final,glb_binary(candidate))
            changed=sorted(key for key in before if before[key]!=after[key])
            if changed:raise RuntimeError('Protected anatomy/character data changed: '+', '.join(changed))
            old=set(original.get('extensionsUsed',[]))|set(original.get('extensionsRequired',[]))
            new=set(final.get('extensionsUsed',[]))|set(final.get('extensionsRequired',[]))
            if old-new:raise RuntimeError('Missing source glTF extensions: '+str(sorted(old-new)))
            added=new-old
            if added-(MESHOPT_EXT if a.mode=='compressed' else set()):
                raise RuntimeError('Unexpected new glTF extensions: '+str(sorted(added)))
            if a.mode=='compressed' and 'EXT_meshopt_compression' not in new:
                raise RuntimeError('Requested meshopt compression missing in GLB')
            if a.validate_khronos:validate(candidate)
            selected=candidate
            if a.mode=='safe' and candidate.stat().st_size>=source.stat().st_size:
                selected=source
            output.parent.mkdir(parents=True,exist_ok=True)
            with tempfile.NamedTemporaryFile(prefix='meshoptimizer-stage-',suffix='.glb',dir=str(output.parent),delete=False) as stage:
                staging=Path(stage.name)
            try:
                shutil.copyfile(selected,staging)
                if output.exists():raise FileExistsError('Output appeared during process; refusing overwrite')
                os.replace(staging,output)
            finally:
                staging.unlink(missing_ok=True)
        pre=source.stat().st_size;post=output.stat().st_size
        print(f'[meshoptimizer/gltfpack] {a.mode}: {pre} -> {post} bytes; source unchanged; skins/morphs/animations/material slots protected')
        if a.mode=='compressed':print('[Three.js] Must ship MeshoptDecoder with GLTFLoader.setMeshoptDecoder(MeshoptDecoder)')
        return 0
    except (OSError,ValueError,RuntimeError,IndexError,KeyError,TypeError,subprocess.TimeoutExpired) as exc:
        print('[meshoptimizer] ERROR:',str(exc),file=sys.stderr)
        return 2

if __name__=='__main__':raise SystemExit(main())
