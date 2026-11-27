"""Read authored EXR channels with OpenImageIO and export bound float maps.
No tone mapping, hidden clipping, resampling or RGB conversion of data maps.
"""
import argparse, json, shutil, tempfile
from pathlib import Path
import numpy as np
from ocio_color import digest

ROLES={'baseColor':3,'roughness':1,'metallic':1,'normal':3,'height':1,'ao':1,'emission':3,'density':1}

def extract(pixels, names, maps):
    if pixels.ndim!=3 or pixels.shape[-1]!=len(names) or len(set(names))!=len(names) or not np.isfinite(pixels).all():
        raise ValueError('Expected finite, uniquely named HWC channels')
    result={}
    for role, item in maps.items():
        if role not in ROLES: raise ValueError('Unknown map role '+role)
        channels=item['channels']; space=item['colorSpace']
        if len(channels)!=ROLES[role] or len(set(channels))!=len(channels) or not all(c in names for c in channels): raise ValueError('Invalid channel mapping '+role)
        if role in ('baseColor','emission'):
            if not isinstance(space,str) or not space or space=='Non-Color': raise ValueError('Explicit RGB color space required')
        elif space!='Non-Color': raise ValueError('Data maps must be Non-Color')
        x=np.ascontiguousarray(pixels[:,:,[names.index(c) for c in channels]],dtype=np.float32)
        if role=='baseColor':
            # Explicit association; never infer from EXR channel names or silently divide by zero.
            alpha=item.get('alphaChannel'); association=item.get('alphaAssociation')
            if alpha is None:
                if association!='opaque': raise ValueError('Missing alpha requires opaque declaration')
                a=np.ones((*x.shape[:2],1),np.float32)
            else:
                if alpha not in names or alpha in channels or association not in ('straight','associated'): raise ValueError('Explicit alpha channel/association required')
                a=pixels[:,:,names.index(alpha):names.index(alpha)+1].astype(np.float32)
                if np.any((a<0)|(a>1)): raise ValueError('Alpha outside [0,1]')
                if association=='associated':
                    if np.any((a==0)&(x!=0)): raise ValueError('Inconsistent associated alpha')
                    x=np.divide(x,a,out=np.zeros_like(x),where=a>0)
            x=np.concatenate([x,a],axis=-1)
        if role in ('roughness','metallic','ao') and np.any((x<0)|(x>1)): raise ValueError('Normalized data outside [0,1]')
        if role=='density' and np.any(x<0): raise ValueError('Negative density')
        if not np.isfinite(x).all(): raise ValueError('Nonfinite extracted values')
        result[role]=x
    if not result: raise ValueError('No selected channels')
    return result

def read_exr(path, subimage):
    import OpenImageIO as oiio
    inp=oiio.ImageInput.open(str(path))
    if inp is None: raise RuntimeError('OpenImageIO cannot open EXR')
    try:
        if not inp.seek_subimage(subimage,0): raise ValueError('Missing EXR subimage')
        s=inp.spec(); names=list(s.channelnames)
        if s.deep or s.depth!=1 or not 1<=s.width<=4096 or not 1<=s.height<=4096 or not 1<=s.nchannels<=64 or s.width*s.height*s.nchannels>32_000_000: raise ValueError('Unsupported deep/volume/oversized EXR')
        # Float conversion is an explicit derivative. UINT and double can lose precision.
        formats=list(s.channelformats) or [s.format]
        if any(str(f) not in ('half','float') for f in formats): raise ValueError('Require half/float EXR channels')
        pixels=inp.read_image(subimage,0,0,s.nchannels,oiio.FLOAT)
        if pixels is None: raise RuntimeError('EXR decode failed')
        pixels=np.asarray(pixels,dtype=np.float32).reshape(s.height,s.width,s.nchannels)
        window=[s.x,s.y,s.width,s.height]; full=[s.full_x,s.full_y,s.full_width,s.full_height]
        if window!=full: raise ValueError('Cropped EXR window requires explicit external alignment first')
        return pixels,names,window,oiio.VERSION_STRING
    finally: inp.close()

def build(manifest,out):
    specpath=Path(manifest).resolve(); root=specpath.parent; spec=json.loads(specpath.read_text()); src=(root/spec['source']).resolve(); out=Path(out).resolve()
    if not src.is_relative_to(root) or src.suffix.lower()!='.exr' or not src.is_file() or out.exists(): raise ValueError('Require existing local EXR and new output directory')
    if digest(src)!=spec['sourceSHA256']: raise ValueError('Source EXR hash mismatch')
    subimage=spec.get('subimage',0)
    if type(subimage)!=int or subimage<0: raise ValueError('Invalid subimage')
    pixels,names,window,version=read_exr(src,subimage); maps=extract(pixels,names,spec['maps'])
    out.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=out.parent) as td:
        staged=Path(td)/'bundle';staged.mkdir();shutil.copy2(src,staged/'master.exr');shutil.copy2(specpath,staged/'source-spec.json')
        np.save(staged/'all-channels.npy',pixels,allow_pickle=False); entries={}
        for role,x in maps.items():
            p=staged/(role+'.npy');np.save(p,x,allow_pickle=False)
            entries[role]={'path':p.name,'sha256':digest(p),'colorSpace':spec['maps'][role]['colorSpace'],'channels':spec['maps'][role]['channels'],'alpha':'straight' if role=='baseColor' else None}
        if digest(staged/'master.exr')!=spec['sourceSHA256'] or digest(src)!=spec['sourceSHA256']: raise ValueError('Source changed')
        (staged/'float-maps.json').write_text(json.dumps({'schema':'cover-pack-oiio/1','sourceSHA256':spec['sourceSHA256'],'subimage':subimage,'channels':names,'window':window,'oiioVersion':version,'master':{'path':'master.exr','sha256':digest(staged/'master.exr')},'allChannels':{'path':'all-channels.npy','sha256':digest(staged/'all-channels.npy')},'maps':entries,'status':'float derivative; color and artistic review required'},indent=2)+'\n')
        staged.rename(out)

def load_bound_map(manifest,role):
    """Consumer: verify derivative and original source bytes before using values."""
    p=Path(manifest).resolve(); root=p.parent; m=json.loads(p.read_text());
    if m.get('schema')!='cover-pack-oiio/1': raise ValueError('Invalid float map manifest')
    def bound(r):
        f=(root/r['path']).resolve()
        if not f.is_relative_to(root) or digest(f)!=r['sha256']: raise ValueError('Changed float map bundle')
        return f
    if m['master']['sha256']!=m['sourceSHA256']: raise ValueError('Invalid source binding')
    bound(m['master']); r=m['maps'][role]; f=bound(r); x=np.load(f,allow_pickle=False)
    if x.dtype!=np.float32 or x.ndim!=3 or x.shape[-1]!=(4 if role=='baseColor' else ROLES[role]) or not np.isfinite(x).all(): raise ValueError('Invalid float map array')
    return x,r,f

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',required=True);p.add_argument('--out',required=True);a=p.parse_args();build(a.manifest,a.out)
