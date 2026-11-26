"""Build optional Meshoptimizer GLB candidates; never replace canonical volumes."""
import argparse, hashlib, json, math, shutil, struct, subprocess
from pathlib import Path
from gltf_validation import validate as validate_khronos

SUPPORTED = {'KHR_lights_punctual','KHR_materials_anisotropy','KHR_materials_clearcoat','KHR_materials_diffuse_transmission','KHR_materials_dispersion','KHR_materials_emissive_strength','KHR_materials_ior','KHR_materials_iridescence','KHR_materials_sheen','KHR_materials_specular','KHR_materials_transmission','KHR_materials_unlit','KHR_materials_variants','KHR_materials_volume','KHR_mesh_quantization','KHR_texture_basisu','KHR_texture_transform','EXT_mesh_gpu_instancing','EXT_meshopt_compression','EXT_texture_webp','KHR_meshopt_compression'}

def digest(p):
    with Path(p).open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()

def inspect(p):
    data=Path(p).read_bytes()
    if len(data)<20 or struct.unpack_from('<4sII',data)!=(b'glTF',2,len(data)): raise ValueError('Expected self-contained GLB v2')
    n,typ=struct.unpack_from('<I4s',data,12)
    if typ!=b'JSON' or n%4 or n+20>len(data): raise ValueError('Invalid GLB JSON chunk')
    d=json.loads(data[20:20+n]); offset=20+n; binary=0
    while offset<len(data):
        if offset+8>len(data): raise ValueError('Truncated chunk')
        length,kind=struct.unpack_from('<I4s',data,offset);offset+=8
        if length%4 or offset+length>len(data): raise ValueError('Invalid chunk bounds')
        if kind==b'BIN\0': binary+=length
        offset+=length
    if d.get('asset',{}).get('version')!='2.0': raise ValueError('Invalid asset version')
    for item in d.get('images',[])+d.get('buffers',[]):
        if 'uri' in item and not item['uri'].startswith('data:'): raise ValueError('External dependencies must be embedded first')
    if any(b.get('byteLength',0)>binary for b in d.get('buffers',[]) if 'uri' not in b and not b.get('extensions')): raise ValueError('Missing GLB payload')
    return d

def names(d,key):
    a=[x['name'] for x in d.get(key,[]) if x.get('name')]
    if len(set(a))!=len(a): raise ValueError('Ambiguous '+key+' names')
    return set(a)

def triangles(d):
    count=0
    for m in d.get('meshes',[]):
        for p in m['primitives']:
            if p.get('mode',4)!=4: raise ValueError('Only triangle meshes supported by this adapter')
            count+=d['accessors'][p.get('indices',p['attributes']['POSITION'])]['count']//3
    if not count: raise ValueError('No triangles')
    return count

def check_source(d):
    if (set(d.get('extensionsUsed',[]))|set(d.get('extensionsRequired',[])))-SUPPORTED: raise ValueError('Unsupported extension: retain original')
    # Deliberately conservative: animated, rigged or morphing assets must keep source until a dedicated animation-preservation path is verified.
    if d.get('animations') or d.get('skins') or any(p.get('targets') for m in d.get('meshes',[]) for p in m['primitives']): raise ValueError('Animated/skinned/morph assets: retain original GLB')
    for m in d.get('meshes',[]):
        for p in m['primitives']:
            if any(k.startswith('_') for k in p['attributes']): raise ValueError('Custom vertex attributes: retain original')
    names(d,'nodes'); names(d,'materials'); triangles(d)

def check_candidate(src,d):
    for k in ('nodes','materials'):
        if not names(src,k)<=names(d,k): raise ValueError('Named '+k+' lost')
    if (set(d.get('extensionsUsed',[]))|set(d.get('extensionsRequired',[])))-SUPPORTED: raise ValueError('Unsupported output extension')
    if 'EXT_meshopt_compression' not in d.get('extensionsUsed',[]): raise ValueError('Meshopt output missing compression extension')
    # Structural preflight only; does not establish semantic equivalence or decode validity.
    return triangles(d)

def build(a):
    source=Path(a.source).resolve();src=inspect(source);check_source(src)
    source_validation=validate_khronos(source)
    out=Path(a.out).resolve()
    if out.exists(): raise FileExistsError(out)
    if not math.isfinite(a.ratio) or not 0<a.ratio<=1: raise ValueError('Ratio must be in (0,1]')
    exe=shutil.which(a.gltfpack)
    if not exe: raise RuntimeError('Install official gltfpack; no substitute encoder')
    out.mkdir(parents=True); original=out/'source.glb';shutil.copyfile(source,original)
    command=[exe,'-i',str(original),'-o',str(out/'candidate.glb'),'-cc','-kn','-km','-ke','-noq']
    if a.ratio<1: command+=['-si',str(a.ratio)]
    # No texture conversion: the Basis atlas stage is independent.
    subprocess.run(command,check=True)
    candidate=out/'candidate.glb';d=inspect(candidate);n=check_candidate(src,d)
    candidate_validation=validate_khronos(candidate)
    if digest(original)!=source_validation['sha256']: raise ValueError('Source changed during optimization')
    version=subprocess.run([exe,'-v'],capture_output=True,text=True)
    metadata={'schema':'cover-pack-runtime-mesh/1','source':{'path':'source.glb','sha256':digest(original),'bytes':original.stat().st_size,'triangles':triangles(src)},'candidate':{'path':'candidate.glb','sha256':digest(candidate),'bytes':candidate.stat().st_size,'triangles':n},'requestedTriangleRatio':a.ratio,'gltfpackVersion':(version.stdout+version.stderr).strip(),'encoderSHA256':digest(exe),'flags':command[5:],'status':'review-required','approved':False,'note':'Static GLB derivative only; original RGBA, pivot, PBR and collisions unchanged. Requires actual decoded rendering and LPIPS/manual approval.'}
    metadata['khronosValidation']={'source':source_validation,'candidate':candidate_validation}
    (out/'runtime-mesh.json').write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf-8')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',required=True);p.add_argument('--out',required=True);p.add_argument('--gltfpack',default='gltfpack');p.add_argument('--ratio',type=float,default=1.);a=p.parse_args();build(a)
if __name__=='__main__':main()
