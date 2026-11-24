import argparse, hashlib, html, io, json, pathlib, zipfile
from PIL import Image, ImageChops

def read(p):
    with Image.open(p) as im:
        if im.format != 'GIF': raise ValueError(f'{p}: not GIF')
        loop=im.info.get('loop'); frames=[]; times=[]
        for i in range(im.n_frames):
            im.seek(i); frames.append(im.convert('RGBA')); times.append(im.info.get('duration',0))
    return frames,times,loop

def save(frames,p,ms):
    if not frames or len({f.size for f in frames})!=1: raise ValueError('inconsistent frames')
    out=[]
    for f in frames:
        f=f.convert('RGBA'); q=f.convert('RGB').quantize(colors=255,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE)
        alpha=f.getchannel('A'); q.paste(255,mask=alpha.point(lambda a:255 if a<128 else 0)); pal=q.getpalette(); q.putpalette((pal+[0]*768)[:768]); out.append(q)
    out[0].save(p,save_all=True,append_images=out[1:],duration=ms,loop=0,disposal=2,transparency=255,optimize=False)

def difference(a,b):
    # Premultiplication excludes hidden RGB under transparent pixels.
    a=a.convert('RGBa'); b=b.convert('RGBa'); h=ImageChops.difference(a.convert('RGBA'),b.convert('RGBA')).histogram(); return sum((i%256)*v for i,v in enumerate(h))/(4*a.width*a.height)

def inspect(p,s):
    f,t,l=read(p); w,h=f[0].size
    if not 6<=len(f)<=10 or l!=0 or min(t)<=0 or len(set(t))!=1: raise ValueError(f'{p}: frame count/timing/loop')
    if w<s.get('min_width',1) or h<s.get('min_height',1) or s.get('square',False) and w!=h: raise ValueError(f'{p}: dimensions')
    for im in f:
        lo,hi=im.getchannel('A').getextrema()
        if s.get('transparent',True) and (lo,hi)!=(0,255): raise ValueError(f'{p}: missing transparency or object')
        if not s.get('transparent',True) and lo!=255: raise ValueError(f'{p}: unexpected transparency')
    unique=len({hashlib.sha256(im.tobytes()).digest() for im in f})
    if unique<3: raise ValueError(f'{p}: not enough distinct frames')
    changes=[difference(f[i],f[(i+1)%len(f)]) for i in range(len(f))]
    if changes[-1]>max(changes[:-1])*1.8+0.5: raise ValueError(f'{p}: potential loop jump')
    seam=s.get('seam','none')
    if seam not in ('none','x','xy'): raise ValueError('invalid seam')
    # Compare actual opposing edges. This is a heuristic, not a visual guarantee.
    for im in f:
        if seam in ('x','xy') and difference(im.crop((0,0,1,h)),im.crop((w-1,0,w,h)))>14: raise ValueError(f'{p}: horizontal edge mismatch')
        if seam=='xy' and difference(im.crop((0,0,w,1)),im.crop((0,h-1,w,h)))>14: raise ValueError(f'{p}: vertical edge mismatch')
    return dict(s,width=w,height=h,frames=len(f),duration_ms=t[0],loop=l)

def tile(p,out,axes):
    frames,t,_=read(p); w,h=frames[0].size; ny=2 if axes=='xy' else 1; ff=[]
    for f in frames:
        im=Image.new('RGBA',(2*w,ny*h))
        for y in range(ny):
            for x in range(2): im.paste(f,(x*w,y*h))
        ff.append(im)
    save(ff,out,t)

def pack(folder,spec,out):
    import re,tempfile
    folder=pathlib.Path(folder); entries=json.loads(pathlib.Path(spec).read_text())['assets']; names=[e['name'] for e in entries]
    if not names or len(names)!=len(set(names)) or any(not re.fullmatch(r'[a-zA-Z0-9_-]+',n) for n in names): raise ValueError('invalid names')
    meta=[inspect(folder/(e['name']+'.gif'),e) for e in entries]
    if {p.stem for p in folder.glob('*.gif')}!=set(names): raise ValueError('missing or unexpected GIFs')
    gallery=['<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>GIF assets</title><style>body{background:#191b20;color:#eee;font:16px system-ui}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px}figure{margin:0;background:#333;padding:12px}img{max-width:100%;display:block;margin:auto}figcaption{padding:8px;overflow-wrap:anywhere}</style><main>']
    out=pathlib.Path(out); tmp=out.with_suffix('.tmp.zip')
    with tempfile.TemporaryDirectory() as td, zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED) as z:
        for m in meta:
            n=m['name']; src=folder/(n+'.gif'); arc='assets/'+n+'.gif'; z.write(src,arc)
            gallery.append(f'<figure><img src="{arc}" alt="{n}"><figcaption>{n} · {m["width"]}×{m["height"]} · {m["frames"]} кадров</figcaption>')
            if m.get('seam','none')!='none':
                preview=pathlib.Path(td)/(n+'.gif'); tile(src,preview,m['seam']); pa='seams/'+n+'.gif'; z.write(preview,pa); gallery.append(f'<img src="{pa}" alt="tile preview">')
            gallery.append('</figure>')
        z.writestr('gallery.html',''.join(gallery)+'</main></html>'); z.writestr('manifest.json',json.dumps({'assets':meta},ensure_ascii=False,indent=2))
    with zipfile.ZipFile(tmp) as z:
        if z.testzip(): raise ValueError('ZIP CRC failed')
        if not all('assets/'+n+'.gif' in z.namelist() for n in names): raise ValueError('ZIP missing asset')
    tmp.replace(out)

if __name__=='__main__':
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest='cmd',required=True)
    b=sub.add_parser('build'); b.add_argument('folder'); b.add_argument('out'); b.add_argument('--ms',type=int,default=160)
    t=sub.add_parser('tile'); t.add_argument('asset'); t.add_argument('out'); t.add_argument('--axes',choices=['x','xy'],default='x')
    k=sub.add_parser('pack'); k.add_argument('folder'); k.add_argument('spec'); k.add_argument('out'); a=p.parse_args()
    if a.cmd=='build':
        frames=[Image.open(q).convert('RGBA') for q in sorted(pathlib.Path(a.folder).glob('*.png'))]; assert 6<=len(frames)<=10; save(frames,a.out,a.ms)
    elif a.cmd=='tile': tile(a.asset,a.out,a.axes)
    else: pack(a.folder,a.spec,a.out)
