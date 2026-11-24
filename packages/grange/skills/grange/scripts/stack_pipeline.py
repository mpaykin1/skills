#!/usr/bin/env python3
"""Grange sprite stacking: textured RGBA XY slices, rigid 3D part poses,
shared orthographic camera, depth-correct first-hit volume traversal.
Source art must be authored separately. No shape generator or fake extrusion.
Derived from the sibling Sprite Stacking Grunge render_stack.py DDA design.
"""
import argparse, hashlib, json, math, tempfile, re
from pathlib import Path
import numpy as np
from PIL import Image, ImageSequence


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p): return json.loads(Path(p).read_text(encoding='utf8'))
def finite(v,n):
    a=np.asarray(v,float)
    if a.shape!=(n,) or not np.isfinite(a).all(): raise ValueError('invalid vector')
    return a

def load_stack(path, expected):
    path=Path(path)
    if sha(path)!=expected: raise ValueError('stack manifest fingerprint mismatch')
    m=read(path); names=m['layers']; hashes=m['layer_sha256']
    if len(names)<3 or len(set(names))!=len(names) or len(hashes)!=len(names): raise ValueError('ordered distinct source slices required')
    out=[]
    for name,h in zip(names,hashes):
        f=(path.parent/name).resolve()
        if not f.is_relative_to(path.parent.resolve()) or sha(f)!=h: raise ValueError('slice source changed or outside stack')
        with Image.open(f) as im:
            if im.format!='PNG' or im.mode!='RGBA': raise ValueError('source slices must be RGBA PNG')
            out.append(np.array(im))
    v=np.stack(out); occ=v[...,3]>=128
    if not occ.any() or np.count_nonzero(occ.any(axis=(1,2)))<3: raise ValueError('empty or flat stack')
    if len({np.packbits(x).tobytes() for x in occ if x.any()})<2: raise ValueError('identical extruded silhouette: not independently authored volume')
    spacing=finite(m['spacing'],3); pivot=finite(m['pivot'],3)
    if np.any(spacing<=0): raise ValueError('spacing must be positive')
    return v,spacing,pivot

def rotation(deg):
    x,y,z=np.radians(finite(deg,3)); a,b,c=np.cos([x,y,z]); d,e,f=np.sin([x,y,z])
    return np.array([[c,-f,0],[f,c,0],[0,0,1]])@np.array([[b,0,e],[0,1,0],[-e,0,b]])@np.array([[1,0,0],[0,a,-d],[0,d,a]])

def rays(size,aa,radius,yaw,pitch):
    a,b=np.radians([yaw,pitch]); right=np.array([np.cos(a),np.sin(a),0]); eye=np.array([np.sin(a)*np.cos(b),-np.cos(a)*np.cos(b),np.sin(b)]); up=np.cross(eye,right)
    n=size*aa; c=(np.arange(n)+.5-n/2)*2*radius/n
    origins=(c[None,:,None]*right-c[:,None,None]*up+eye*(radius*2)).reshape(-1,3)
    return origins,-eye

def trace(v,s,pivot,o,d):
    # Grid DDA with slab clipping; transparent cells never occlude another part.
    nz,ny,nx=v.shape[:3]; dims=np.array([nx,ny,nz]); half=dims*s/2; o=o+pivot
    d=d.copy(); d[np.abs(d)<1e-12]=0; moving=d!=0; safe=np.where(moving,d,1.)
    ta=(-half-o)/safe; tb=(half-o)/safe
    start=np.maximum(np.where(moving,np.minimum(ta,tb),-np.inf).max(1),0);end=np.where(moving,np.maximum(ta,tb),np.inf).min(1)
    active=np.flatnonzero(np.all(moving|((o>=-half)&(o<=half)),axis=1)&(end>start)); depth=np.full(len(o),np.inf); color=np.zeros((len(o),4),np.uint8)
    if not active.size:return depth,color
    pos=o[active]+(start[active]+min(s)*1e-8)[:,None]*d
    cell=np.clip(np.floor((pos+half)/s).astype(int),0,dims-1); step=np.sign(d).astype(int)
    tmax=np.where(moving,((cell+(step>0))*s-half-o[active])/safe,np.inf); tdelta=np.where(moving,s/np.abs(safe),np.inf); t=start[active]
    for _ in range(int(dims.sum())+3):
        if not active.size:break
        rgb=v[cell[:,2],ny-1-cell[:,1],cell[:,0]]; hit=rgb[:,3]>=128
        color[active[hit]]=rgb[hit];color[active[hit],3]=255;depth[active[hit]]=t[hit]
        keep=~hit; active=active[keep];cell=cell[keep];tmax=tmax[keep]
        if not active.size:break
        t=tmax.min(1); axes=tmax<=t[:,None]+1e-10;cell+=axes*step;tmax=np.where(axes,tmax+tdelta,tmax)
        keep=(t<end[active])&((cell>=0)&(cell<dims)).all(1);active=active[keep];cell=cell[keep];tmax=tmax[keep];t=t[keep]
    return depth,color

def render(recipe):
    path=Path(recipe).resolve(); m=read(path); base=path.parent
    if m.get('schema')!='grange-stack-v1':raise ValueError('unknown schema')
    source=base/m['source_art'];
    if sha(source)!=m['source_art_sha256']:raise ValueError('source art changed')
    size=int(m['size']);aa=int(m.get('aa',1)); radius=float(m['radius']);duration=int(m['duration_ms']); parts=m['parts'];poses=m['frames']
    if not (16<=size<=320 and aa in (1,2) and 12<=len(poses)<=24 and duration>=20 and duration%10==0 and math.isfinite(radius) and radius>0): raise ValueError('Grange frame/size/timing limits')
    if not parts or len(set(p['id'] for p in parts))!=len(parts) or any(not re.fullmatch(r'[a-zA-Z0-9_-]+',p['id']) for p in parts):raise ValueError('unique parts required')
    cache={}
    def get(spec):
        f=base/spec['stack']; h=spec['stack_sha256']; key=(f,h)
        if key not in cache:cache[key]=load_stack(f,h)
        return cache[key]
    for part in parts:get(part)
    result=[];masks=[]; labels=[]
    for pose in poses:
        yaw,pitch=finite(pose['camera'],2)
        if not -90<=pitch<=90:raise ValueError('pitch outside +/-90')
        o,d=rays(size,aa,radius,yaw,pitch); best=np.full(len(o),np.inf); pixels=np.zeros((len(o),4),np.uint8);ids=np.zeros(len(o),np.int32)
        moves=pose.get('parts',{})
        if not set(moves).issubset({p['id'] for p in parts}):raise ValueError('unknown animated part')
        for k,part in enumerate(parts,1):
            q=moves.get(part['id'],{}); spec=part
            if 'stack' in q:
                if part.get('kind')!='authored_pose':raise ValueError('rigid part cannot swap stack identity')
                spec=q
            v,s,pivot=get(spec);t=finite(q.get('translation',part.get('translation',[0,0,0])),3);r=rotation(q.get('rotation_deg',part.get('rotation_deg',[0,0,0])))
            # A single scale and common world frame; object may not leave view.
            depth,col=trace(v,s,pivot,(o-t)@r,d@r); hit=depth<best;best[hit]=depth[hit];pixels[hit]=col[hit];ids[hit]=k
        n=size*aa; im=Image.fromarray(pixels.reshape(n,n,4));
        if aa>1: im=im.resize((size,size),Image.Resampling.LANCZOS)
        a=np.array(im);visible=a[...,3]>=128
        if not visible.any() or visible[0].any() or visible[-1].any() or visible[:,0].any() or visible[:,-1].any():raise ValueError('empty/clipped stack render')
        result.append(im); per={}
        for k,part in enumerate(parts,1):
            mask=Image.fromarray((ids.reshape(n,n)==k).astype(np.uint8)*255)
            if aa>1:mask=mask.resize((size,size),Image.Resampling.BOX)
            per[part['id']]=np.asarray(mask)>=128
        body=np.logical_or.reduce([per[p['id']] for p in parts if p.get('role','body')=='body']) if any(p.get('role','body')=='body' for p in parts) else visible
        masks.append(body&visible);labels.append(per)
    return result,masks,labels,duration,m.get('once',False)

def save_gif(frames,dest,duration,once):
    samples=[]
    for im in frames:
        a=np.asarray(im);rgb=a[a[...,3]>=128,:3];samples.append(rgb[::max(1,len(rgb)//3500)])
    sample=np.concatenate(samples);palette=Image.fromarray(sample.reshape(1,-1,3),'RGB').quantize(colors=255,method=Image.Quantize.MEDIANCUT)
    pal=palette.getpalette()[:765]+[0,0,0];palette.putpalette(pal);out=[]
    for im in frames:
        p=im.convert('RGB').quantize(palette=palette,dither=Image.Dither.NONE);idx=np.array(p);opaque=np.asarray(im)[...,3]>=128
        if ((idx==255)&opaque).any():idx[(idx==255)&opaque]=int(np.argmin(np.sum(np.array(pal[:765]).reshape(255,3).astype(float)**2,axis=1)))
        idx[~opaque]=255;f=Image.fromarray(idx,'P');f.putpalette(pal);out.append(f)
    opts={} if once else {'loop':0}
    out[0].save(dest,save_all=True,append_images=out[1:],duration=duration,disposal=2,transparency=255,optimize=False,**opts)
    with Image.open(dest) as f:
        if f.n_frames!=len(frames):raise ValueError('GIF merged duplicate frames')
    if Path(dest).stat().st_size>1500000:raise ValueError('GIF size exceeds Grange limit')

def build(recipe,dest):
    fs,ms,parts,duration,once=render(recipe);save_gif(fs,dest,duration,once);return fs,ms,parts

def verify(recipe,candidate,entries=None):
    with tempfile.TemporaryDirectory() as tmp:
        out=Path(tmp)/'render.gif';_,masks,_=build(recipe,out)
        if sha(out)!=sha(candidate):raise ValueError('P39 GIF does not reproduce from source stack; no sprite-stacking proof')
        if entries is not None:
            if len(entries)!=len(masks):raise ValueError('stack mask/frame count differs')
            for e,m in zip(entries,masks):
                with Image.open(e['body_mask']) as im: other=np.array(im.convert('L'))>=128
                if other.shape!=m.shape or np.count_nonzero(other&m)/max(1,np.count_nonzero(other|m))<.95:raise ValueError('P40 body masks disagree with actual depth renderer')
        return {'route':'sprite-stacking','recipe_sha256':sha(recipe),'reproduced_gif_sha256':sha(out),'frames':len(masks)}

def main():
    p=argparse.ArgumentParser();p.add_argument('recipe',type=Path);p.add_argument('output',type=Path);p.add_argument('--verify',action='store_true');a=p.parse_args()
    if a.verify:print(json.dumps(verify(a.recipe,a.output)));return
    a.output.mkdir(parents=True,exist_ok=True);fs,ms,parts=build(a.recipe,a.output/'animation.gif');(a.output/'body').mkdir(exist_ok=True);(a.output/'frames').mkdir(exist_ok=True)
    for i,(f,m,pp) in enumerate(zip(fs,ms,parts)):
        f.save(a.output/'frames'/f'{i:04}.png');Image.fromarray(m.astype('uint8')*255).save(a.output/'body'/f'{i:04}.png')
        for name,mask in pp.items():
            folder=a.output/'parts'/name;folder.mkdir(parents=True,exist_ok=True);Image.fromarray(mask.astype('uint8')*255).save(folder/f'{i:04}.png')
if __name__=='__main__':main()
