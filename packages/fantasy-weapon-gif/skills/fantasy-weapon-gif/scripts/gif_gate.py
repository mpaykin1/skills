#!/usr/bin/env python3
"""Plan, inspect and assemble actual independently rendered RGBA poses. Pillow required."""
import argparse, hashlib, json, math
from pathlib import Path
from PIL import Image, ImageDraw, ImageSequence, ImageChops

KEYS = ['CENTER','UP','DOWN','CENTER_RETURN','RIGHT','LEFT']
ANGLES = [(0,0),(0,90),(0,-90),(0,0),(90,0),(-90,0)]
REVIEW = ['all_views','full_silhouette','same_hands','same_weapon','smooth_and_seamless','outward']
def require(ok,msg):
    if not ok: raise ValueError(msg)
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,o): Path(p).write_text(json.dumps(o,indent=2,ensure_ascii=False),encoding='utf-8')
def safe(base,p):
    q=(base/p).resolve(); require(q.is_relative_to(base.resolve()),'path outside package'); return q
def lock(ref,out):
    record={'hands_sha256':sha(ref)}
    if Path(out).exists(): require(read(out)==record,'hand identity locked; explicit new session required')
    else: write(out,record)
def plan(out):
    frames=[]; keys={}
    for i,(a,b) in enumerate(zip(ANGLES,ANGLES[1:]+ANGLES[:1])):
        keys[KEYS[i]]=len(frames)
        n=math.ceil(max(abs(b[0]-a[0]),abs(b[1]-a[1]))/3)*2
        for j in range(n):
            t=j/n; s=t*t*t*(10+t*(-15+6*t))
            frames.append({'yaw':round(a[0]+(b[0]-a[0])*s,4),'pitch':round(a[1]+(b[1]-a[1])*s,4),'ms':240 if j==0 and KEYS[i] in ('UP','DOWN','RIGHT','LEFT') else 40})
    write(out,{'keys':keys,'frames':frames,'notice':'target angles only; not observed frame evidence'})
def load(manifest):
    p=Path(manifest); m=read(p); base=p.parent.resolve(); frames=m['frames']; keys=m['keys']; images=[]; hashes=[]
    for f in frames:
        fp=safe(base,f['file']); require(fp.suffix.lower()=='.png','PNG required')
        with Image.open(fp) as im:
            require(im.mode=='RGBA','true RGBA required'); im=im.copy()
        images.append(im); hashes.append(hashlib.sha256(im.tobytes()).hexdigest())
    return m,base,frames,keys,images,hashes
def digest(m,frames,keys,hashes):
    return hashlib.sha256(json.dumps({'frames':frames,'keys':keys,'pixel_hashes':hashes,'angle_source':m['angle_source'],'hands_mode':m['hands_mode']},sort_keys=True,separators=(',',':')).encode()).hexdigest()
def sheet(manifest,out):
    m,base,frames,keys,images,hashes=load(manifest)
    w,h=images[0].size; scale=min(1,340/max(w,h)); w,h=max(1,int(w*scale)),max(1,int(h*scale)); canvas=Image.new('RGB',(w*3,(h+24)*2),(32,33,37)); d=ImageDraw.Draw(canvas)
    for j,k in enumerate(KEYS):
        im=images[keys[k]].resize((w,h),Image.Resampling.NEAREST); x=(j%3)*w;y=(j//3)*(h+24); canvas.paste(im,(x,y+24),im); d.text((x+5,y+4),k,fill='white')
    canvas.save(out); print('frame_digest:',digest(m,frames,keys,hashes)); print('weapon_sha256:',sha(safe(base,m['weapon_reference'])))
def validate(m,base,frames,keys,images,hashes):
    require(m['angle_source'] in ['visual','render'],'actual observed angle source required')
    require(m['hands_mode'] in ['visible','hidden'],'invalid hands mode')
    if m['hands_mode']=='visible': require(read(safe(base,m['session_lock']))['hands_sha256']==sha(safe(base,m['hands_reference'])),'session hands mismatch')
    require(set(keys)==set(KEYS),'missing key poses'); ids=[keys[k] for k in KEYS]; n=len(frames)
    require(ids[0]==0 and all(a<b for a,b in zip(ids,ids[1:])) and ids[-1]<n,'wrong order')
    require(all(isinstance(i,int) for i in ids),'key indexes must be ints')
    size=images[0].size; w,h=size
    for i,im in enumerate(images):
        require(im.size==size,'canvas changes')
        a=im.getchannel('A'); box=a.getbbox(); require(box and a.getextrema()==(0,255),'empty/no transparent background or no opaque pixels')
        margin=max(1,round(min(w,h)*0.02)); require(box[0]>=margin and box[1]>=margin and box[2]<=w-margin and box[3]<=h-margin,f'frame {i} clipped or too close to border')
    for k,angle in zip(KEYS,ANGLES):
        f=frames[keys[k]]; require(max(abs(f['yaw']-angle[0]),abs(f['pitch']-angle[1]))<=3,f'{k}: missing full angle')
        if k in ('UP','DOWN','RIGHT','LEFT'): require(200<=f['ms']<=300,f'{k}: endpoint hold missing')
    for i,f in enumerate(frames):
        y,p=f['yaw'],f['pitch']; require(math.isfinite(y) and math.isfinite(p) and abs(y)<=90.01 and abs(p)<=90.01 and min(abs(y),abs(p))<=3,'invalid angle or combined axis')
        require(isinstance(f['ms'],int) and f['ms']%10==0 and (f['ms']==40 or (i in [keys[k] for k in ('UP','DOWN','RIGHT','LEFT')] and 200<=f['ms']<=300)),'timing invalid')
        j=(i+1)%n; g=frames[j]; require(max(abs(y-g['yaw']),abs(p-g['pitch']))<=8,'angular jump')
        # Identical adjacent poses are not movement (including loop seam).
        require(hashes[i]!=hashes[j],f'duplicate adjacent frame {i}')
    for s,e in zip(ids,ids[1:]+[n]):
        group=frames[s:e]+[frames[e%n]]; require(e-s>=12,'too few independent intermediate frames')
        require(len(set(hashes[s:e]))>=math.ceil((e-s)*.9),'repeated poses in motion')
        a,b=group[0],group[-1]; axis='yaw' if abs(a['yaw']-b['yaw'])>abs(a['pitch']-b['pitch']) else 'pitch'; other='pitch' if axis=='yaw' else 'yaw'; sign=1 if b[axis]>a[axis] else -1
        require(all(abs(f[other])<=3 for f in group),'wrong axis')
        require(all((g[axis]-f[axis])*sign>=-0.15 for f,g in zip(group,group[1:])),'reversal inside segment')
    require(len({hashes[keys[k]] for k in ('CENTER','UP','DOWN','RIGHT','LEFT')})==5,'key views are duplicates')
    r=m['review']; require(all(r.get(k) is True for k in REVIEW),'actual visual review incomplete')
    require(r.get('frame_digest')==digest(m,frames,keys,hashes),'review stale or missing'); require(r.get('weapon_sha256')==sha(safe(base,m['weapon_reference'])),'weapon review stale')
def build(manifest,out):
    m,base,frames,keys,images,hashes=load(manifest); validate(m,base,frames,keys,images,hashes)
    # Sample all frames for one shared palette; reserve index 255 for transparency.
    samples=[]
    for im in images:
        thumb=im.copy(); thumb.thumbnail((128,128),Image.Resampling.NEAREST)
        samples.extend((r,g,b) for r,g,b,a in thumb.getdata() if a>=128)
    require(samples,'no opaque samples'); strip=Image.new('RGB',(256,math.ceil(len(samples)/256))); strip.putdata(samples+[(0,0,0)]*((-len(samples))%256)); pal=strip.quantize(colors=255,method=Image.Quantize.MEDIANCUT); palette=pal.getpalette()[:765]+[0,0,0]; pal.putpalette(palette)
    result=[]
    for im in images:
        q=im.convert('RGB').quantize(palette=pal,dither=Image.Dither.NONE); pix=bytearray(q.tobytes()); alpha=im.getchannel('A').tobytes()
        for i,a in enumerate(alpha):
            if a<128: pix[i]=255
            elif pix[i]==255: pix[i]=min(range(255),key=lambda j:sum((palette[3*j+k]-im.getpixel((i%im.width,i//im.width))[k])**2 for k in range(3)))
        q=Image.frombytes('P',im.size,bytes(pix)); q.putpalette(palette); q.info['transparency']=255; result.append(q)
    dest=Path(out); require(dest.suffix.lower()=='.gif','GIF output required'); tmp=dest.with_name(dest.stem+'.partial.gif')
    try:
        result[0].save(tmp,save_all=True,append_images=result[1:],duration=[f['ms'] for f in frames],loop=0,transparency=255,disposal=2,optimize=False)
        with Image.open(tmp) as gif:
            require(gif.n_frames==len(result),'GIF merged/lost poses'); require(gif.info.get('loop')==0,'missing loop')
            for i,fr in enumerate(ImageSequence.Iterator(gif)):
                require(fr.info.get('duration')==frames[i]['ms'],'GIF timing altered')
                actual=fr.convert('RGBA'); expected=result[i].convert('RGBA'); require(actual.getchannel('A').tobytes()==expected.getchannel('A').tobytes(),'GIF alpha altered')
                diff=ImageChops.difference(actual.convert('RGB'),expected.convert('RGB')); require(not Image.composite(diff,Image.new('RGB',diff.size),expected.getchannel('A')).getbbox(),'GIF color/frame altered')
        tmp.replace(dest)
    finally:
        if tmp.exists(): tmp.unlink()
    print('STRUCTURE OK; final visual playback review still required')
def main():
    parser=argparse.ArgumentParser(); sub=parser.add_subparsers(dest='cmd',required=True)
    for cmd,params in [('lock',['ref','out']),('plan',['out']),('sheet',['manifest','out']),('build',['manifest','out'])]:
        p=sub.add_parser(cmd)
        for param in params:p.add_argument(param)
    a=parser.parse_args(); kw=vars(a); cmd=kw.pop('cmd'); globals()[cmd](**kw)
if __name__=='__main__':
    try: main()
    except (ValueError,KeyError,OSError,TypeError,IndexError) as e: raise SystemExit('BLOCKED: '+str(e))
