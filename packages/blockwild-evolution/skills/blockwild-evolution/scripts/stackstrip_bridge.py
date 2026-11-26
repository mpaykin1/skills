#!/usr/bin/env python3
"""Independent bridge for danielwh2/sprite-stacking's MIT-licensed slice-strip PNG.
Accept a horizontal strip of evenly sized bottom-to-top RGBA layers and create
an isometric, alpha-preserving sprite plus pivot metadata for BLOCKWILD v12.
No upstream source is executed. Source slices and their original colors remain
unchanged in the input; baked output is only a visual derivative.
"""
import argparse,hashlib,io,json
from pathlib import Path
from PIL import Image,ImageDraw


def bake(input_path:Path, count:int, output:Path, meta:Path, xy=1.92, lift=2.57, threshold=10):
    raw=input_path.read_bytes();img=Image.open(io.BytesIO(raw)).convert('RGBA')
    w,h=img.size
    if count<1 or w%count!=0: raise ValueError('Input width must be a multiple of layer count.')
    side=w//count
    if side>192 or count>128 or h>192: raise ValueError('Bounded atlas: <=192px slice side, <=128 slices.')
    # PNG slice strip is original per-height RGBA, not 4-view artwork.
    slices=[img.crop((k*side,0,(k+1)*side,h)) for k in range(count)]
    width=max(220,int((side+h)*xy+64));height=max(220,int(count*lift+(side+h)*xy*.5+50))
    anchorx=width//2;anchory=height-24
    out=Image.new('RGBA',(width,height));g=ImageDraw.Draw(out,'RGBA')
    occ=[s.getchannel('A') for s in slices]
    for layer,s in enumerate(slices):
        pix=s.load();a=occ[layer].load()
        for z in range(h):
            for x in range(side):
                cr,cg,cb,alpha=pix[x,z]
                if alpha<=threshold:continue
                top=layer==count-1 or occ[layer+1].getpixel((x,z))<=threshold
                xside=x==side-1 or a[x+1,z]<=threshold
                zside=z==h-1 or a[x,z+1]<=threshold
                if not top and not xside and not zside: continue
                sx=anchorx+(x-z)*xy
                sy=anchory+(x+z-(side+h-2)/2)*xy*.47-layer*lift
                def shade(f):return (min(255,int(cr*f)),min(255,int(cg*f)),min(255,int(cb*f)),alpha)
                if xside:
                    g.polygon(((sx+xy,sy),(sx,sy+xy*.47),(sx,sy+xy*.47+lift),(sx+xy,sy+lift)),fill=shade(.68))
                if zside:
                    g.polygon(((sx,sy+xy*.47),(sx-xy,sy),(sx-xy,sy+lift),(sx,sy+xy*.47+lift)),fill=shade(.84))
                if top:
                    g.polygon(((sx,sy-xy*.47),(sx+xy,sy),(sx,sy+xy*.47),(sx-xy,sy)),fill=shade(1.06))
    bounds=out.getbbox()
    if not bounds: raise ValueError('All source slices are transparent.')
    x0=max(0,bounds[0]-3);y0=max(0,bounds[1]-3);x1=min(width,bounds[2]+3);y1=min(height,bounds[3]+3)
    output.parent.mkdir(parents=True,exist_ok=True)
    out.crop((x0,y0,x1,y1)).save(output,optimize=True)
    record={'format':'blockwild-stack-sprite/1','source_format':'sprite-stacking horizontal bottom-to-top RGBA strip',
     'source_sha256':hashlib.sha256(raw).hexdigest(),'output_sha256':hashlib.sha256(output.read_bytes()).hexdigest(),
     'layers':count,'slice_pixels':[side,h],'size':[x1-x0,y1-y0],'base':[anchorx-x0,anchory-y0],
     'source':str(input_path),'asset':str(output)}
    meta.write_text(json.dumps(record,indent=2))
    return record

if __name__=='__main__':
    a=argparse.ArgumentParser()
    a.add_argument('strip',type=Path);a.add_argument('--layers',type=int,required=True)
    a.add_argument('--output',type=Path,required=True);a.add_argument('--meta',type=Path,required=True)
    a.add_argument('--xy',type=float,default=1.92);a.add_argument('--lift',type=float,default=2.57)
    p=a.parse_args()
    print(json.dumps(bake(p.strip,p.layers,p.output,p.meta,p.xy,p.lift),indent=2))
