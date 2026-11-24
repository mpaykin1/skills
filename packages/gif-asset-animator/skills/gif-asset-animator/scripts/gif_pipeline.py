"""Transparent full-frame GIF export and packaging. Dependencies: Pillow, NumPy."""
import argparse
from pathlib import Path
import hashlib
import json
import zipfile
import numpy as np
from PIL import Image, GifImagePlugin, ImageSequence

BAYER = np.array([[0,8,2,10],[12,4,14,6],[3,11,1,9],[15,7,13,5]])

def indexed(im, dither=False):
    a=np.asarray(im.convert('RGBA'))
    h,w=a.shape[:2]
    alpha=a[:,:,3]
    threshold=np.tile((BAYER+.5)*16,((h+3)//4,(w+3)//4))[:h,:w] if dither else 127
    visible=alpha>threshold
    rgb=a[:,:,:3].copy()
    # Train palette on visible pixels only; hidden RGB never consumes palette colors.
    samples=rgb[visible]
    if len(samples):
        training=Image.fromarray(samples.reshape(1,-1,3),'RGB')
        pal=training.quantize(colors=255,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE)
        palette=(pal.getpalette() or [])[:765]; palette += [0]*(765-len(palette))
        # Duplicate existing first color at 255 to prevent an unused black slot winning quantization.
        pal.putpalette(palette+palette[:3])
        q=Image.fromarray(rgb,'RGB').quantize(palette=pal,dither=Image.Dither.NONE)
        indices=np.array(q); indices[(indices==255)&visible]=0; indices[~visible]=255
    else:
        palette=[0]*765; indices=np.full((h,w),255,np.uint8)
    out=Image.fromarray(indices,'P'); out.putpalette(palette+palette[:3]); out.info['transparency']=255
    return out,visible

def validate(path, expected=None, once=None, empty_last=False, masks=None):
    with Image.open(path) as im:
        assert im.format=='GIF', 'not GIF'
        n=im.n_frames; loop=im.info.get('loop'); size=im.size
        if expected is not None: assert n==expected, f'frame count {n} != {expected}'
        if once is not None: assert (loop is None if once else loop==0), 'wrong loop mode'
        hashes=set(); has_alpha=False; last=None
        for i,fr in enumerate(ImageSequence.Iterator(im)):
            assert fr.info.get('duration',0)>0, 'zero duration'
            rgba=fr.convert('RGBA'); alpha=np.array(rgba.getchannel('A')); last=alpha
            has_alpha |= bool((alpha==0).any())
            if masks is not None: assert np.array_equal(alpha>0,masks[i]), f'alpha mismatch frame {i}'
            hashes.add(hashlib.sha256(rgba.tobytes()).digest())
        assert has_alpha, 'no transparent pixels'
        assert len(hashes)>1, 'static GIF'
        if empty_last: assert not last.any(), 'last frame not empty'
        return {'file':str(path),'size':size,'frames':n,'loop':loop,'distinct_frames':len(hashes)}

def encode(folder,out,duration,once,empty_last,dither):
    paths=sorted(Path(folder).glob('*.png'))
    assert 10<=len(paths)<=16, 'expected 10–16 numbered PNG frames'
    assert duration>=20 and duration%10==0,'duration must be >=20 ms and divisible by 10'
    frames=[]; masks=[]; size=None
    for p in paths:
        with Image.open(p) as im:
            assert 'A' in im.getbands() or 'transparency' in im.info, f'missing alpha: {p}'
            if size is None: size=im.size
            assert im.size==size, 'mixed canvas sizes'
            f,m=indexed(im,dither); frames.append(f); masks.append(m)
    assert not empty_last or once,'empty-last is for one-shots'
    if empty_last: assert not masks[-1].any(),'last source frame must be empty'
    info={'background':255,'transparency':255,'optimize':False}
    if not once: info['loop']=0
    header,_=GifImagePlugin.getheader(frames[0],info=info)
    out=Path(out); out.parent.mkdir(parents=True,exist_ok=True)
    try:
        with out.open('wb') as f:
            f.writelines(header)
            for fr in frames:
                f.writelines(GifImagePlugin.getdata(fr,duration=duration,transparency=255,disposal=2,include_color_table=True,optimize=False))
            f.write(b';')
        return validate(out,len(frames),once,empty_last,masks)
    except Exception:
        out.unlink(missing_ok=True); raise

def extract(src,dst):
    dest=Path(dst);dest.mkdir(parents=True,exist_ok=True)
    with Image.open(src) as im:
        for i,fr in enumerate(ImageSequence.Iterator(im)):
            fr.convert('RGBA').save(dest/f'{i:04d}.png')
        return {'frames':im.n_frames,'size':im.size}

def pack(out,paths):
    names=[Path(p).name for p in paths]; assert len(names)==len(set(names)), 'duplicate names'
    for p in paths: validate(p)
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for p in paths: z.write(p,Path(p).name)
    with zipfile.ZipFile(out) as z:
        assert z.testzip() is None and z.namelist()==names
        for p in paths: assert z.read(Path(p).name)==Path(p).read_bytes()
    return {'archive':out,'files':names}

def main():
    p=argparse.ArgumentParser(); s=p.add_subparsers(dest='cmd',required=True)
    e=s.add_parser('encode');e.add_argument('folder');e.add_argument('out');e.add_argument('--duration',type=int,default=90);e.add_argument('--once',action='store_true');e.add_argument('--empty-last',action='store_true');e.add_argument('--dither',action='store_true')
    e=s.add_parser('extract');e.add_argument('source');e.add_argument('destination')
    e=s.add_parser('inspect');e.add_argument('file')
    e=s.add_parser('pack');e.add_argument('out');e.add_argument('files',nargs='+')
    a=p.parse_args()
    if a.cmd=='encode': result=encode(a.folder,a.out,a.duration,a.once,a.empty_last,a.dither)
    elif a.cmd=='extract': result=extract(a.source,a.destination)
    elif a.cmd=='inspect': result=validate(a.file)
    else: result=pack(a.out,a.files)
    print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__': main()
