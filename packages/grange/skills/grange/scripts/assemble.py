#!/usr/bin/env python3
"""Assemble existing transparent drawn frames, not generate artwork. Requires Pillow."""
import argparse
from pathlib import Path
from PIL import Image, ImageChops

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('source',type=Path,help='RGBA spritesheet or directory of sorted PNG frames')
p.add_argument('output',type=Path)
p.add_argument('--rows',type=int,default=4)
p.add_argument('--cols',type=int,default=4)
p.add_argument('--count',type=int)
p.add_argument('--ms',type=int,default=120)
p.add_argument('--alpha-threshold',type=int,default=128)
p.add_argument('--apng',action='store_true')
p.add_argument('--once',action='store_true')
a=p.parse_args()
if min(a.rows,a.cols)<1 or not 10<=a.ms or not 1<=a.alpha_threshold<=255:
    p.error('Invalid grid, duration or alpha threshold')
if a.source.is_dir():
    frames=[Image.open(f).convert('RGBA') for f in sorted(a.source.glob('*.png'))]
else:
    im=Image.open(a.source).convert('RGBA'); w,h=im.size
    if w%a.cols or h%a.rows: p.error('Sheet must have equally sized cells; remove borders first')
    cw,ch=w//a.cols,h//a.rows
    frames=[im.crop((c*cw,r*ch,(c+1)*cw,(r+1)*ch)) for r in range(a.rows) for c in range(a.cols)]
if a.count is not None:
    if not 2<=a.count<=len(frames): p.error('Invalid frame count')
    frames=frames[:a.count]
if len(frames)<2 or len({f.size for f in frames})!=1: p.error('Need at least 2 equal-size frames')
size=frames[0].size
masks=[]
for i,f in enumerate(frames):
    alpha=f.getchannel('A'); mask=alpha.point(lambda x:255 if x>=a.alpha_threshold else 0)
    b=mask.getbbox()
    if not b or mask.getextrema()!=(0,255): p.error(f'Frame {i}: empty or no transparent pixels')
    if b[0]==0 or b[1]==0 or b[2]==size[0] or b[3]==size[1]: p.error(f'Frame {i}: subject touches border; inspect for clipping')
    masks.append(mask)
# Ignore RGB values in fully transparent pixels for duplicate checks.
visible=[Image.composite(f.convert('RGB'),Image.new('RGB',size),m) for f,m in zip(frames,masks)]
pairs=list(zip(range(len(frames)-1),range(1,len(frames))))
if not a.once:pairs.append((len(frames)-1,0))
for i,j in pairs:
    if not ImageChops.difference(visible[i],visible[j]).getbbox() and not ImageChops.difference(masks[i],masks[j]).getbbox():p.error(f'Duplicate adjacent frames {i}, {j}')
# Sample opaque pixels from all frames for a shared 255-color palette.
samples=[]
for f,m in zip(frames,masks):
    rgb=list(f.convert('RGB').getdata()); mask=list(m.getdata()); opaque=[c for c,v in zip(rgb,mask) if v]
    samples.extend(opaque[::max(1,len(opaque)//12000)])
ref=Image.new('RGB',(len(samples),1));ref.putdata(samples)
q=ref.quantize(colors=255,method=Image.Quantize.MEDIANCUT)
palette=q.getpalette()[:765];palette += [0]*(765-len(palette)); palette += palette[:3]
# Last entry duplicates index zero: remap any visible index 255 to 0.
pal=Image.new('P',(1,1));pal.putpalette(palette)
gifs=[]
for f,m in zip(frames,masks):
    indexed=f.convert('RGB').quantize(palette=pal,dither=Image.Dither.NONE).point(list(range(255))+[0])
    indexed.putpalette(palette);indexed.paste(255,mask=ImageChops.invert(m));indexed.info['transparency']=255;gifs.append(indexed)
a.output.parent.mkdir(parents=True,exist_ok=True)
kwargs={} if a.once else {'loop':0}
gifs[0].save(a.output,format='GIF',save_all=True,append_images=gifs[1:],duration=a.ms,disposal=2,transparency=255,background=255,optimize=False,**kwargs)
with Image.open(a.output) as check:
    if check.n_frames!=len(frames): raise RuntimeError('Encoded GIF frame count differs')
    for i in range(check.n_frames):
        check.seek(i)
        if check.convert('RGBA').getchannel('A').getextrema()!=(0,255):raise RuntimeError(f'Encoded frame {i} alpha invalid')
if a.apng:
    frames[0].save(a.output.with_suffix('.png'),save_all=True,append_images=frames[1:],duration=a.ms,loop=1 if a.once else 0,disposal=1,blend=0)
print(f'{a.output}: {len(frames)} frames, {size[0]}x{size[1]}, {a.ms} ms/frame')
