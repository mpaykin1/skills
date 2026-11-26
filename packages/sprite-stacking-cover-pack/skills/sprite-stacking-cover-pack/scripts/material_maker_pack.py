"""Material Maker exported PBR maps -> approved native volume surface material variant.
Geometry, alpha, and original grid are immutable. Explicit region and projection required.
"""
import argparse, hashlib, json, shutil, subprocess
from pathlib import Path
import numpy as np
from PIL import Image
from trellis_stack import export_stack


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))


def write(p, data):
    Path(p).write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def linear(v):
    return np.where(v <= .04045, v/12.92, ((v+.055)/1.055)**2.4)


def srgb(v):
    v=np.clip(v,0,1)
    return np.where(v <= .0031308, v*12.92, 1.055*v**(1/2.4)-.055)


def sample(a, uv):
    # Repeat bilinear texture sampling; +V up. No per-view or per-frame randomness.
    h,w=a.shape[:2]; x=uv[:,0]*w-.5; y=(1-uv[:,1])*h-.5
    i=np.floor(x).astype(np.int64); j=np.floor(y).astype(np.int64)
    fx=(x-i)[:,None]; fy=(y-j)[:,None]
    return ((1-fx)*(1-fy)*a[j%h,i%w]+fx*(1-fy)*a[j%h,(i+1)%w]+(1-fx)*fy*a[(j+1)%h,i%w]+fx*fy*a[(j+1)%h,(i+1)%w])


def variant(args):
    src=Path(args.asset).resolve(); out=Path(args.out).resolve(); specp=Path(args.material).resolve(); spec=read(specp)
    if src==out or src in out.parents or out in src.parents or out.exists(): raise ValueError('Use a new sibling output directory')
    grid=src/'native_grid.npz'; meta=read(src/'stack.json')
    if spec['sourceGridSHA256']!=sha(grid): raise ValueError('Material region does not match source grid')
    if (src/'geometry-source.json').exists():
        for n,h in read(src/'geometry-source.json').items():
            if sha(src/n)!=h: raise ValueError('Geometry binding changed: '+n)
    with np.load(grid,allow_pickle=False) as f: g={k:f[k] for k in f.files}
    coords=g['coords']; rgba=np.asarray(g['rgba'],np.float32).copy(); original=rgba.copy()
    if coords.shape!=(len(rgba),3) or rgba.shape[1:]!=(4,) or not np.isfinite(rgba).all(): raise ValueError('Invalid native grid')
    root=specp.parent
    def resolve(rel):
        p=(root/rel).resolve()
        if root not in p.parents or not p.is_file(): raise ValueError('Invalid material input path: '+str(rel))
        return p
    region=resolve(spec['region']); mask=np.load(region,allow_pickle=False)
    if mask.dtype!=np.bool_ or mask.shape!=(len(coords),): raise ValueError('Region must be one boolean per native sample')
    idx=np.flatnonzero(mask & (rgba[:,3]>0))
    if not len(idx): raise ValueError('No visible selected material region')
    scale=float(spec['repeatWorldUnits']); strength=float(spec.get('detailStrength',.25)); origin=np.asarray(spec.get('projectionOrigin',[0,0,0]),float)
    if not np.isfinite(scale) or scale<=0 or not 0<=strength<=1 or origin.shape!=(3,) or not np.isfinite(origin).all(): raise ValueError('Invalid material parameters')
    xyz=(coords[idx].astype(float)+.5)*float(g['voxel_size'])+np.asarray(g.get('origin',[-.5]*3)); q=(xyz-origin)/scale
    # Native-coordinate projection, independent of output up axis. Explicit axis pair or reviewed normals.
    proj=spec['projection']; pairs={'xy':(0,1),'xz':(0,2),'yz':(1,2)}
    inputs={'region':region}; weights=None
    if proj=='triplanar':
        npth=resolve(spec['normals']); normals=np.load(npth,allow_pickle=False)
        if normals.shape!=coords.shape or not np.isfinite(normals).all(): raise ValueError('Invalid native normals')
        weights=np.abs(normals[idx])**4; denom=weights.sum(1,keepdims=True)
        if np.any(denom<=0): raise ValueError('Missing selected surface normal')
        weights/=denom; inputs['normals']=npth
    elif proj not in pairs: raise ValueError('Explicit xy/xz/yz/triplanar required')
    maps={}
    for key,rel in spec['maps'].items():
        if key not in ('baseColor','roughness','metallic','normal','height','ao','emission'): raise ValueError('Unsupported map '+key)
        p=resolve(rel); inputs[key]=p
        if key in ('normal','height','ao','emission'): continue # retain originals, not falsely bake into albedo
        a=np.asarray(Image.open(p).convert('RGB' if key=='baseColor' else 'L'),dtype=np.float32)/255
        if a.ndim==2:a=a[:,:,None]
        if key=='baseColor':a=linear(a)
        if weights is None: v=sample(a,q[:,pairs[proj]])
        else:v=sum(sample(a,q[:,pair])*weights[:,i:i+1] for i,pair in enumerate(((1,2),(0,2),(0,1))))
        maps[key]=v
    if not maps: raise ValueError('No supported sampled material maps')
    if 'baseColor' in maps:
        # Preserve approved hue: scalar luminance modulation in linear RGB, not replacement.
        lum=maps['baseColor']@np.array([.2126,.7152,.0722]); avg=max(float(lum.mean()),.05)
        factor=1+strength*np.clip(lum/avg-1,-.75,1.0)
        rgba[idx,:3]=srgb(linear(np.clip(rgba[idx,:3],0,1))*factor[:,None])
    # Only modify known native channels, never discard unsupported PBR attributes.
    attrs=np.asarray(g.get('attrs',original),np.float32).copy(); layout=json.loads(str(g.get('layout',np.array('{"base_color":[0,3],"alpha":[3,4]}')).item()))
    if attrs.ndim!=2 or attrs.shape[0]!=len(coords): raise ValueError('Invalid native attributes')
    def channel(key,width):
        if key not in layout:return None
        lo,hi=layout[key]
        if hi-lo!=width or lo<0 or hi>attrs.shape[1]: raise ValueError('Invalid channel '+key)
        return slice(lo,hi)
    base=channel('base_color',3)
    if base is None:raise ValueError('Missing native base color channel')
    attrs[idx,base]=rgba[idx,:3]
    sidecar={'indices':idx}
    for key in ('roughness','metallic'):
        if key in maps:
            s=channel(key,1); val=maps[key].astype(np.float32)
            if s is not None:
                val=(1-strength)*attrs[idx,s]+strength*val;attrs[idx,s]=val
            sidecar[key]=val
    assert np.array_equal(original[:,3],rgba[:,3]) and np.array_equal(original[~mask],rgba[~mask])
    out.mkdir(parents=True); originals=out/'material-source'; originals.mkdir()
    shutil.copy2(grid,originals/'native_grid.npz');shutil.copy2(specp,originals/'material.json');shutil.copy2(src/'stack.json',originals/'stack.json')
    for k,p in inputs.items():shutil.copy2(p,originals/(k+p.suffix))
    for n in ('native_mesh.npz','reference.png','source.glb','provenance.json','geometry-source.json'):
        if (src/n).is_file():shutil.copy2(src/n,originals/n)
    g.update(rgba=rgba,attrs=attrs,layout=np.array(json.dumps(layout)));np.savez_compressed(out/'native_grid.npz',**g)
    np.savez_compressed(out/'material_samples.npz',**sidecar)
    if (src/'native_mesh.npz').exists():
        shutil.copy2(src/'native_mesh.npz',out/'native_mesh.npz');write(out/'geometry-source.json',{n:sha(out/n) for n in ('native_grid.npz','native_mesh.npz')})
    # Keep original sampling resolution; changing it here could alter silhouettes or pivots.
    for candidate in (128,256,512,1024):
        if candidate < max(meta['size'],meta['layerCount']): continue
        extent=(np.ptp(coords,axis=0)+1)*float(g['voxel_size'])
        expected=max(float(g['voxel_size']),float(extent.max())/candidate)
        if np.isclose(expected,meta['spacing'][0],rtol=1e-7,atol=1e-12): break
    else: raise ValueError('Cannot reproduce original stack spacing')
    result=export_stack(coords,rgba,float(g['voxel_size']),out,candidate,meta['nativeUp'],g.get('origin',[-.5]*3))
    for key in ('size','layerCount','spacing','pivot','gridOrigin'):
        if not np.allclose(result[key],meta[key],rtol=1e-7,atol=1e-12): raise ValueError('Stack geometry changed: '+key)
    for n in ('asset.json','stack.json'):
        m=read(out/n);m.update(status='prototype',representation=meta['representation'],sourceKind='material-maker-map-variant',materialSamples='material_samples.npz');write(out/n,m)
    write(out/'provenance.json',{'sourceGridSHA256':sha(grid),'sourceStackSHA256':sha(src/'stack.json'),'materialSpecSHA256':sha(specp),'inputs':{k:sha(p) for k,p in inputs.items()},'selectedSamples':len(idx),'geometryAndAlphaPreserved':True,'status':'prototype; source map provenance and visual fidelity require review'})


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='mode',required=True)
    e=sub.add_parser('export');e.add_argument('--exe',required=True);e.add_argument('--graph',required=True);e.add_argument('--out',required=True)
    a=sub.add_parser('apply');a.add_argument('--asset',required=True);a.add_argument('--material',required=True);a.add_argument('--out',required=True)
    args=p.parse_args()
    if args.mode=='export':
        out=Path(args.out).resolve(); graph=Path(args.graph).resolve()
        if graph.suffix.lower()!='.ptex' or not graph.is_file() or out.exists():raise ValueError('Use existing .ptex and new output directory')
        out.mkdir(parents=True);subprocess.run([args.exe,'--export-material','--target','Blender','-o',str(out),str(graph)],check=True)
        if not list(out.rglob('*.png')):raise RuntimeError('No PNG export from Material Maker')
        shutil.copy2(graph,out/'source.ptex');write(out/'export-provenance.json',{'graphSHA256':sha(graph),'maps':{str(f.relative_to(out)):sha(f) for f in out.rglob('*.png')}})
    else:variant(args)
if __name__=='__main__':main()
