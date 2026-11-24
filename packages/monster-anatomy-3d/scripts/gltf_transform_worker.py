#!/usr/bin/env python3
"""Safe CPU-only post-export GLB optimization using official glTF-Transform CLI.

- No CUDA, neural inference, Blender, third-party Python libs or source overwrite.
- Conservative default: 'dedup' only, preserving accessible standard glTF 2.0.
- Optional meshopt is NOT lossless vertex-precision guarantee and needs a decoder.
- Protects mesh primitive layouts, joint hierarchy, clip timing/channel structure,
  morph targets, texture attachments and scene transforms before atomic publish.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile

CLI_VERSION='4.5.1'
COMPRESSED_EXT={'EXT_meshopt_compression','KHR_draco_mesh_compression'}

def read_glb(path):
    p=Path(path)
    with p.open('rb') as f:
        header=f.read(12)
        if len(header)!=12: raise ValueError('GLB is truncated')
        magic,version,declared=struct.unpack('<4sII',header)
        if magic!=b'glTF' or version!=2 or declared!=p.stat().st_size:
            raise ValueError('Invalid GLB 2.0 header or length')
        length,kind=struct.unpack('<II',f.read(8))
        if kind!=0x4e4f534a or length<2 or length>declared-20:
            raise ValueError('GLB JSON chunk missing or malformed')
        chunk=f.read(length)
        if len(chunk)!=length:raise ValueError('Incomplete GLB JSON')
    doc=json.loads(chunk.decode('utf-8').rstrip(' \t\n\r\0'))
    if doc.get('asset',{}).get('version')!='2.0':raise ValueError('Only glTF 2.0 supported')
    return doc


def asset_fingerprint(g, *, allow_quantization=False):
    """Semantic fingerprint independent of deduped accessor/material index numbering."""
    nodes=g.get('nodes',[]); meshes=g.get('meshes',[]); skins=g.get('skins',[])
    acc=g.get('accessors',[]); mats=g.get('materials',[])

    def name(idx):
        if not (isinstance(idx,int) and 0<=idx<len(nodes)):
            raise ValueError('GLB references an invalid node')
        # An unnamed node that is renumbered is deliberately rejected.
        return nodes[idx].get('name') or f'@node_{idx}'

    def accessor(idx):
        if not (isinstance(idx,int) and 0<=idx<len(acc)):
            raise ValueError('GLB references an invalid accessor')
        a=acc[idx]
        return ((a.get('count'),a.get('type')) if allow_quantization else (a.get('count'),a.get('type'),a.get('componentType'),bool(a.get('normalized',False))))

    def primitive(p):
        attrs=p.get('attributes',{})
        desc=tuple(sorted((key,accessor(value)) for key,value in attrs.items()))
        targets=tuple(tuple(sorted((key,accessor(value)) for key,value in t.items()))
                      for t in p.get('targets',[]))
        mid=p.get('material')
        material=mats[mid].get('name',f'@mat_{mid}') if mid is not None else None
        return (p.get('mode',4),material,desc,targets,accessor(p['indices']) if 'indices' in p else None)

    skin_data=[]
    for skin in skins:
        skin_data.append((tuple(name(i) for i in skin.get('joints',[])),
                          name(skin['skeleton']) if 'skeleton' in skin else None,
                          accessor(skin['inverseBindMatrices']) if 'inverseBindMatrices' in skin else None))

    mesh_links=[]
    for idx,node in enumerate(nodes):
        if 'mesh' not in node:continue
        mesh=meshes[node['mesh']]
        skin_idx=node.get('skin')
        skin=skin_data[skin_idx] if skin_idx is not None else None
        mesh_links.append((name(idx),skin,tuple(primitive(p) for p in mesh.get('primitives',[])),
                           tuple(mesh.get('weights',[]))))

    def node_xform(n):
        return tuple((k,tuple(n[k])) for k in ('translation','rotation','scale','matrix') if k in n)

    hierarchy=[]
    for idx,n in enumerate(nodes):
        hierarchy.append((name(idx),tuple(name(x) for x in n.get('children',[])),node_xform(n)))

    animations=[]
    for idx,a in enumerate(g.get('animations',[])):
        channels=[]
        samplers=a.get('samplers',[])
        for c in a.get('channels',[]):
            s=samplers[c['sampler']]
            t=c.get('target',{})
            channels.append((name(t['node']) if 'node' in t else '@pointer',t.get('path'),
                             s.get('interpolation','LINEAR'),accessor(s['input']),accessor(s['output'])))
        animations.append((a.get('name',f'@animation_{idx}'),tuple(sorted(channels,key=str))))
    animations.sort(key=str)
    # Compare effective material slot paths, including nested PBR texture links.
    # Index numbering may be deduplicated but texture names remain if supplied.
    slot_fingerprint=[]
    textures=g.get('textures',[]);images=g.get('images',[])
    for mat_id,mat in enumerate(mats):
        def walk(obj,path=''):
            if isinstance(obj,dict):
                if 'index' in obj and path.endswith('Texture'):
                    ref=obj['index']
                    if not isinstance(ref,int) or ref<0 or ref>=len(textures):
                        raise ValueError('Invalid material texture reference')
                    tex=textures[ref];source_idx=tex.get('source')
                    source_name=(images[source_idx].get('name') or f'@image_{source_idx}') if source_idx is not None else '@texture_extension'
                    slot_fingerprint.append((mat.get('name',f'@mat_{mat_id}'),path,source_name))
                for k,v in obj.items():walk(v,path+'.'+k if path else k)
            elif isinstance(obj,list):
                for z,item in enumerate(obj):walk(item,path+'.'+str(z))
        walk(mat)
    return {
        'skins':sorted(skin_data,key=str),
        'mesh_links':sorted(mesh_links,key=str),
        'nodes':sorted(hierarchy,key=str),
        'animations':animations,
        'scenes':len(g.get('scenes',[])),
        'scene_roots':sorted(tuple(name(n) for n in s.get('nodes',[])) for s in g.get('scenes',[])),
        'texture_slots':sorted(slot_fingerprint),
        'image_count':len(g.get('images',[])),
        'texture_count':len(g.get('textures',[])),
        'material_count':len(mats),
    }


def resolve_cli(explicit=None):
    value=explicit or os.environ.get('GLTF_TRANSFORM_BIN') or shutil.which('gltf-transform')
    if not value:raise FileNotFoundError('glTF-Transform missing; run: python scripts/install_gltf_transform.py --install')
    if os.path.dirname(value) or value.startswith('.'):
        path=Path(value).expanduser().resolve()
        if not path.is_file():raise FileNotFoundError('CLI file not found: '+str(path))
        return str(path)
    result=shutil.which(value)
    if not result:raise FileNotFoundError('CLI executable not found: '+value)
    return result


def main(argv=None):
    p=argparse.ArgumentParser(description='CPU-only glTF-Transform GLB integrity-preserving postpass')
    p.add_argument('--input',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--mode',choices=('safe','meshopt'),default='safe')
    p.add_argument('--cli',default=None,help='Path to official gltf-transform CLI')
    p.add_argument('--timeout',type=int,default=900)
    p.add_argument('--overwrite',action='store_true')
    a=p.parse_args(argv)
    source=a.input.expanduser().resolve();output=a.output.expanduser().resolve()
    if source==output or source.suffix.lower()!='.glb' or output.suffix.lower()!='.glb':p.error('Use separate input/output .glb paths')
    if not source.is_file():p.error('Input .glb missing')
    if output.exists() and not a.overwrite:p.error('Output already exists')
    if not 10<=a.timeout<=7200:p.error('--timeout must be 10..7200')
    try:
        before=read_glb(source)
        first=asset_fingerprint(before,allow_quantization=(a.mode=='meshopt'))
        cli=resolve_cli(a.cli)
        with tempfile.TemporaryDirectory(prefix='gltf-transform-',dir=str(output.parent) if output.parent.is_dir() else None) as temp:
            work=Path(temp)
            stage=work/'dedup.glb'
            command=[cli,'dedup',str(source),str(stage)]
            done=subprocess.run(command,capture_output=True,text=True,timeout=a.timeout,check=False)
            if done.returncode:raise RuntimeError('dedup failed: '+done.stderr[-700:])
            current=stage
            if a.mode=='meshopt':
                dest=work/'meshopt.glb'
                done=subprocess.run([cli,'meshopt',str(current),str(dest),'--level','medium'],
                                    capture_output=True,text=True,timeout=a.timeout,check=False)
                if done.returncode:raise RuntimeError('meshopt failed: '+done.stderr[-700:])
                current=dest
            if not current.is_file():raise RuntimeError('CLI produced no GLB')
            after=read_glb(current)
            final=asset_fingerprint(after,allow_quantization=(a.mode=='meshopt'))
            changes=[k for k in first if first[k]!=final[k]]
            if changes:raise RuntimeError('Protected glTF structures changed: '+', '.join(changes))
            old_ext=set(before.get('extensionsRequired',[]))|set(before.get('extensionsUsed',[]))
            new_ext=set(after.get('extensionsRequired',[]))|set(after.get('extensionsUsed',[]))
            additional=new_ext-old_ext
            if a.mode=='safe' and additional:
                raise RuntimeError('Safe optimization introduced new extension: '+', '.join(sorted(additional)))
            if a.mode=='meshopt':
                if additional-{'EXT_meshopt_compression','KHR_mesh_quantization'}:
                    raise RuntimeError('Unexpected compression extensions: '+', '.join(sorted(additional)))
                if 'EXT_meshopt_compression' not in new_ext:
                    raise RuntimeError('meshopt command did not produce meshopt compression')
            # Do not publish larger artifacts. Real compression is not guaranteed.
            chosen=current if current.stat().st_size<source.stat().st_size else source
            output.parent.mkdir(parents=True,exist_ok=True)
            temp_dest=work/'accepted.glb'
            shutil.copyfile(chosen,temp_dest)
            os.replace(temp_dest,output)
        ratio=(1-output.stat().st_size/source.stat().st_size)*100
        print(f'glTF-Transform {a.mode}: {ratio:.1f}% smaller; protected structure unchanged; output {output}')
        if a.mode=='meshopt' and chosen!=source:
            print('Three.js requires GLTFLoader.setMeshoptDecoder(MeshoptDecoder) for this file')
        return 0
    except (OSError,RuntimeError,ValueError,IndexError,KeyError,TypeError,subprocess.TimeoutExpired) as e:
        print('glTF-Transform ERROR:',e,file=sys.stderr)
        return 2

if __name__=='__main__':
    raise SystemExit(main())
