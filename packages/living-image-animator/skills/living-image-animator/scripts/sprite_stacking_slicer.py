#!/usr/bin/env python3
"""Original-art four-view silhouette intersection into REAL transparent horizontal sprite slices.

No AI-generated backs, repeated 2D cards, deformed actor cels or fake full-3D from
one photograph. Geometry needs 4 actual orthographic author-approved source views.
"""
from __future__ import annotations
import io, math
from pathlib import Path
import numpy as np
from PIL import Image

class StackSlicerError(ValueError): pass

def reject(msg):raise StackSlicerError('Sprite stacking source blocked: '+str(msg))

def _rgba(src, label):
    if isinstance(src,(str,Path)):data=Path(src).read_bytes()
    elif isinstance(src,bytes):data=src
    else:reject(label+' must be an original PNG file or original file bytes')
    if len(data)>16_000_000:reject(label+' input is too large')
    try:
        with Image.open(io.BytesIO(data)) as im:
            if im.format!='PNG':reject(label+' must be original PNG (no JPEG/AI-generated replacement)')
            arr=np.array(im.convert('RGBA'),dtype=np.uint8)
    except (OSError,ValueError) as ex:reject(label+' image decode failed: '+str(ex))
    if not 8<=arr.shape[1]<=512 or not 8<=arr.shape[0]<=512:reject(label+' dimensions must be 8..512')
    alpha=arr[:,:,3]
    if int(np.count_nonzero(alpha>30))<20 or np.all(alpha==255):
        reject(label+' requires a visible object on a truly transparent canvas')
    return arr

def _fit(array,w,h,label,allow_resample):
    if array.shape[:2]==(h,w):return array
    if not allow_resample:reject(label+f' view size {array.shape[1]}x{array.shape[0]}, requires {w}x{h}; no silent distortion')
    # Explicit opt-in only. Preserve discrete original texture colors without neural interpolation.
    return np.asarray(Image.fromarray(array,'RGBA').resize((w,h),Image.Resampling.NEAREST))

def carve_views(views:dict[str,bytes],slices:int=32,allow_resample:bool=False):
    """Four silhouettes: top=(x,depth), side=(depth,height), front/back=(x,height).

    Slice 0 is BOTTOM; colors are sampled ONLY from the supplied view pixels.
    Back view is mirrored into common world-x orientation (seen from behind).
    """
    if not isinstance(views,dict) or set(views)!={'top','side','front','back'}:
        reject('Exactly top, side, front and back original views required for honest 360-degree volume')
    if type(slices) is not int or not 8<=slices<=96:reject('8..96 slices required')
    if type(allow_resample) is not bool:reject('allow_resample must be boolean')
    top=_rgba(views['top'],'top');side=_rgba(views['side'],'side')
    front=_rgba(views['front'],'front');back=_rgba(views['back'],'back')
    depth,width=top.shape[:2];height=front.shape[0]
    if min(width,depth,height)<8:reject('Volume too small')
    front=_fit(front,width,height,'front',allow_resample)
    back=_fit(back,width,height,'back',allow_resample)
    side=_fit(side,depth,height,'side',allow_resample)
    # Consistent bottom-up y in all four views.
    opacity_top=top[:,:,3]
    out=[];nonempty=0;shapes=set()
    for k in range(slices):
        yy=min(height-1,max(0,int(round((height-1)*(1-(k+.5)/slices)))))
        f=front[yy];b=back[yy,::-1];s=side[yy]
        mask=(opacity_top>70)&(f[:,3][None,:]>70)&(b[:,3][None,:]>70)&(s[:,3][:,None]>70)
        if not np.any(mask):
            out.append(Image.new('RGBA',(width,depth)));continue
        # True 3D intersection: color each boundary from the corresponding REAL view.
        # Unlit inner volumes use the author's original top texture; never invented patterns.
        rgba=top.copy()
        # Back boundary is at greater depth; front boundary at smaller depth.
        edge_front=mask & ~np.pad(mask[:-1],((1,0),(0,0)),constant_values=False)
        edge_back=mask & ~np.pad(mask[1:],((0,1),(0,0)),constant_values=False)
        edge_left=mask & ~np.pad(mask[:,:-1],((0,0),(1,0)),constant_values=False)
        edge_right=mask & ~np.pad(mask[:,1:],((0,0),(0,1)),constant_values=False)
        rgba[edge_front,:3]=np.broadcast_to(f[None,:,:3],rgba[:,:,:3].shape)[edge_front]
        rgba[edge_back,:3]=np.broadcast_to(b[None,:,:3],rgba[:,:,:3].shape)[edge_back]
        side_rgb=np.broadcast_to(s[:,None,:3],rgba[:,:,:3].shape)
        rgba[edge_left|edge_right,:3]=side_rgb[edge_left|edge_right]
        rgba[:,:,3]=np.where(mask,opacity_top,0)
        out.append(Image.fromarray(rgba,'RGBA'))
        nonempty+=1
        shapes.add(mask.tobytes())
    if nonempty<max(4,slices//5):reject('Too few valid 3D cross-sections; views conflict or object is thin')
    if len(shapes)<3:reject('Views produce identical repeated profiles; supply distinct genuine volume layers')
    return out,{'source_four_views':True,'width':width,'depth':depth,'height':height,
                'slices':slices,'nonempty_slices':nonempty,'distinct_profiles':len(shapes),
                'inferred_from_single_view':False,'character_deformation':False}

def pack_slices(layers:list[Image.Image],max_dimension:int=4096)->tuple[bytes,int,int,int]:
    if not layers:reject('Empty stack')
    w,d=layers[0].size
    if any(im.size!=(w,d) or im.mode!='RGBA' for im in layers):reject('Slice dimensions/pixel modes differ')
    if len(layers)>96:reject('Too many slices')
    cols=min(len(layers),max(1,min(max_dimension//w,math.ceil(math.sqrt(len(layers))))))
    rows=math.ceil(len(layers)/cols)
    if rows*d>max_dimension:reject('Atlas exceeds 4096 texture limit')
    atlas=Image.new('RGBA',(cols*w,rows*d))
    for i,im in enumerate(layers):atlas.paste(im,((i%cols)*w,(i//cols)*d))
    buf=io.BytesIO();atlas.save(buf,format='PNG',compress_level=8,optimize=True)
    if len(buf.getvalue())>8_000_000:reject('Slice atlas exceeds 8 MB')
    return buf.getvalue(),cols,w,d

if __name__=='__main__':
    import argparse,json
    p=argparse.ArgumentParser(description='Carve original four-view PNGs into real horizontal sprite-stack atlas')
    for s in ('top','side','front','back'):p.add_argument('--'+s,required=True)
    p.add_argument('--out',required=True);p.add_argument('--slices',type=int,default=32)
    p.add_argument('--allow-resample',action='store_true');a=p.parse_args()
    layers,meta=carve_views({k:Path(getattr(a,k)).read_bytes() for k in ('top','side','front','back')},a.slices,a.allow_resample)
    data,cols,w,d=pack_slices(layers);Path(a.out).parent.mkdir(parents=True,exist_ok=True);Path(a.out).write_bytes(data)
    print(json.dumps({**meta,'atlas_columns':cols,'atlas_bytes':len(data)}))
