"""Conservative glTF Transform delivery candidates, including animated GLB.
No automatic approval, no edits to canonical sprite layers, no network installation.
"""
import argparse, hashlib, json, shutil, struct, subprocess, tempfile
from pathlib import Path
from gltf_validation import validate as validate_khronos
from meshopt_pack import inspect, digest, SUPPORTED

COMP = {5120:1,5121:1,5122:2,5123:2,5125:4,5126:4}
WIDTH = {'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}
COMPRESSED = {'EXT_meshopt_compression','KHR_meshopt_compression','KHR_draco_mesh_compression'}

def payload(path):
    data=Path(path).read_bytes(); n=struct.unpack_from('<I',data,12)[0]; p=20+n
    if p==len(data): return b''
    length,kind=struct.unpack_from('<I4s',data,p)
    if kind!=b'BIN\0': raise ValueError('Expected embedded BIN chunk')
    return data[p+8:p+8+length]

def acc(d,i,bin_data,exact):
    a=d['accessors'][i]; v=d['bufferViews'][a['bufferView']]
    if a.get('sparse') or v.get('buffer',0)!=0: raise ValueError('Sparse or multi-buffer accessor: keep source')
    result={'type':a['type'],'count':a['count']}
    if not exact: return result
    if COMPRESSED.intersection(v.get('extensions',{})): raise ValueError('Exact check requires decoded accessors')
    width=COMP[a['componentType']]*WIDTH[a['type']]; stride=v.get('byteStride',width)
    start=v.get('byteOffset',0)+a.get('byteOffset',0); end=start+(a['count']-1)*stride+width
    if a['count']<1 or stride<width or start<0 or end>len(bin_data) or end>v.get('byteOffset',0)+v['byteLength']: raise ValueError('Accessor range invalid')
    h=hashlib.sha256()
    for j in range(a['count']): h.update(bin_data[start+j*stride:start+j*stride+width])
    return {**result,'componentType':a['componentType'],'normalized':a.get('normalized',False),'sha256':h.hexdigest()}

def signature(path,exact=True):
    d=inspect(path); b=payload(path)
    used=set(d.get('extensionsUsed',[]))|set(d.get('extensionsRequired',[]))
    if used-SUPPORTED or 'KHR_draco_mesh_compression' in used: raise ValueError('Unknown/unsupported extensions: keep source')
    if exact and used&COMPRESSED: raise ValueError('Use original uncompressed source for exact checks')
    A=lambda i:acc(d,i,b,exact)
    # Preserve animation targets by index (deliberately reject reordered scene graphs).
    nodes=[]
    for n in d.get('nodes',[]):
        nodes.append({**{k:n[k] for k in ('name','mesh','skin','camera','weights','extras','extensions') if k in n},'children':n.get('children',[]), 'translation':n.get('translation',[0,0,0]),'rotation':n.get('rotation',[0,0,0,1]),'scale':n.get('scale',[1,1,1]),'matrix':n.get('matrix')})
    skins=[]
    for s in d.get('skins',[]):
        skins.append({**{k:v for k,v in s.items() if k!='inverseBindMatrices'},'inverseBindMatrices':A(s['inverseBindMatrices']) if 'inverseBindMatrices' in s else None})
    animations=[]
    for a in d.get('animations',[]):
        channels=[]
        for c in a['channels']:
            sampler=a['samplers'][c['sampler']]
            channels.append({'target':c['target'],'interpolation':sampler.get('interpolation','LINEAR'),'input':A(sampler['input']),'output':A(sampler['output']),'extras':c.get('extras'),'extensions':c.get('extensions')})
        animations.append({'name':a.get('name'),'extras':a.get('extras'),'extensions':a.get('extensions'),'channels':sorted(channels,key=lambda x:json.dumps(x['target'],sort_keys=True))})
    meshes=[]
    for m in d.get('meshes',[]):
        primitives=[]
        for p in m['primitives']:
            if p.get('mode',4)!=4: raise ValueError('Only triangular meshes supported')
            primitives.append({**{k:v for k,v in p.items() if k not in ('attributes','indices','targets','mode')},'mode':4,'attributes':{k:A(i) for k,i in p['attributes'].items()},'indices':A(p['indices']) if 'indices' in p else None,'targets':[{k:A(i) for k,i in t.items()} for t in p.get('targets',[])]})
        meshes.append({**{k:v for k,v in m.items() if k!='primitives'},'primitives':primitives})
    # Preserve embedded image bytes and texture/material references. No image transcoding in this branch.
    images=[]
    for i in d.get('images',[]):
        if 'bufferView' in i:
            v=d['bufferViews'][i['bufferView']]; start=v.get('byteOffset',0); end=start+v['byteLength']
            if v.get('buffer',0)!=0 or start<0 or end>len(b): raise ValueError('Invalid embedded image')
            ih=hashlib.sha256(b[start:end]).hexdigest()
        else: raise ValueError('Require bufferView-embedded images for conservative audit')
        images.append({**{k:v for k,v in i.items() if k!='bufferView'},'sha256':ih})
    return {'nodes':nodes,'skins':skins,'animations':animations,'meshes':meshes,'images':images,'textures':d.get('textures',[]),'samplers':d.get('samplers',[]),'materials':d.get('materials',[]),'scenes':d.get('scenes',[]),'scene':d.get('scene',0),'cameras':d.get('cameras',[]),'extensions':d.get('extensions',{}),'extras':d.get('extras')}

def require_equal(a,b):
    for k in a:
        if a[k]!=b[k]: raise ValueError('Conservative preservation check failed: '+k+'; retain source')

def build(a):
    source=Path(a.source).resolve(); exact=signature(source); structural=signature(source,False)
    source_validation=validate_khronos(source)
    exe=shutil.which(a.cli)
    if not exe: raise RuntimeError('Install official @gltf-transform/cli in the authorized runtime; no mock encoder')
    out=Path(a.out).resolve()
    if out.exists(): raise FileExistsError(out)
    # Work in a temporary directory. Failed checks never publish a manifest or replace source.
    out.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=out.parent) as tmp:
        root=Path(tmp); original=root/'source.glb'; shutil.copyfile(source,original)
        dedup=root/'dedup.glb'
        subprocess.run([exe,'dedup',str(original),str(dedup),'--materials','false','--meshes','false','--skins','false','--textures','false'],check=True)
        require_equal(exact,signature(dedup))
        validate_khronos(dedup)
        candidate=root/'candidate.glb'
        if a.meshopt:
            subprocess.run([exe,'meshopt',str(dedup),str(candidate),'--level','medium'],check=True)
            if not (set(inspect(candidate).get('extensionsUsed',[])) & {'EXT_meshopt_compression'}): raise ValueError('Expected supported EXT_meshopt_compression output')
            require_equal(structural,signature(candidate,False))
        else: shutil.copyfile(dedup,candidate)
        candidate_validation=validate_khronos(candidate)
        if digest(original)!=source_validation['sha256']: raise ValueError('Source changed during optimization')
        if candidate.stat().st_size>=original.stat().st_size: raise ValueError('No size saving; retain source')
        version=subprocess.run([exe,'--version'],capture_output=True,text=True,check=True).stdout.strip()
        def record(p): return {'path':p.name,'sha256':digest(p),'bytes':p.stat().st_size}
        m={'schema':'cover-pack-runtime-mesh/1','source':record(original),'candidate':record(candidate),'encoder':'glTF Transform','version':version,'mode':'dedup+meshopt' if a.meshopt else 'dedup-accessors','status':'review-required','approved':False,'exactDedupAccessorCheck':True,'candidateCheck':'structural only; decoded animation and visual review required' if a.meshopt else 'conservative exact accessor audit; decoded visual review required'}
        m['khronosValidation']={'source':source_validation,'candidate':candidate_validation}
        out.mkdir();shutil.copyfile(original,out/original.name);shutil.copyfile(candidate,out/candidate.name)
        (out/'runtime-mesh.json').write_text(json.dumps(m,indent=2)+'\n')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',required=True);p.add_argument('--out',required=True);p.add_argument('--cli',default='gltf-transform');p.add_argument('--meshopt',action='store_true');a=p.parse_args();build(a)
if __name__=='__main__':main()
